from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Request as FastAPIRequest
from pydantic import ValidationError

from inceptum_poc.config import LabNodeConfig, load_lab_node_config
from inceptum_poc.models import (
    CapabilitySummary,
    ClaimManifest,
    Contradiction,
    HealthResponse,
    InvestigationTask,
    Policy,
    PolicyDecision,
    ProvenanceBundle,
    RankedCause,
    ReplicationOutcome,
    ResetResponse,
    Request,
    RequestSubmission,
    Run,
    RunCreate,
    RunResultResponse,
    ResultSummary,
)
from inceptum_poc.storage import JsonSqliteStore
from inceptum_poc.utils import new_id, stable_digest, utc_now


class LabNodeService:
    def __init__(self, config: LabNodeConfig, store: JsonSqliteStore):
        self.config = config
        self.store = store
        self._seed()

    def _seed(self) -> None:
        for policy in self.config.policies:
            self.store.upsert("policies", policy.policy_id, policy.model_dump(mode="json"))
        for claim in self.config.claims:
            existing_claim = self.store.get("claims", claim.claim_id)
            if existing_claim is None:
                self.store.upsert("claims", claim.claim_id, claim.model_dump(mode="json"))
                continue
            try:
                ClaimManifest.model_validate(existing_claim)
            except ValidationError:
                self.store.upsert("claims", claim.claim_id, claim.model_dump(mode="json"))

    def get_claim(self, claim_id: str) -> ClaimManifest:
        payload = self.store.get("claims", claim_id)
        if payload is None:
            raise KeyError(claim_id)
        try:
            return ClaimManifest.model_validate(payload)
        except ValidationError as error:
            fallback_claim = self._config_claim(claim_id)
            if fallback_claim is None:
                raise KeyError(claim_id) from error
            self.store.upsert("claims", claim_id, fallback_claim.model_dump(mode="json"))
            return fallback_claim

    def get_policy(self, policy_id: str) -> Policy:
        payload = self.store.get("policies", policy_id)
        if payload is None:
            raise KeyError(policy_id)
        return Policy.model_validate(payload)

    def create_request(self, submission: RequestSubmission) -> Request:
        claim = self.get_claim(submission.claim_id)
        if submission.target_lab != self.config.lab_id:
            raise ValueError(
                f"Request target {submission.target_lab} does not match node {self.config.lab_id}."
            )
        policy = self.get_policy(claim.policy.policy_id)
        decision = self._evaluate_policy(submission, policy)
        now = utc_now()
        request_status = decision.outcome
        request_record = Request(
            request_id=new_id("request"),
            claim_id=submission.claim_id,
            target_lab=self.config.lab_id,
            target_claim_version=claim.version,
            requester=submission.requester,
            requested_action=submission.requested_action,
            request_purpose=submission.request_purpose,
            requested_outputs=submission.requested_outputs,
            requested_template_id=submission.requested_template_id or claim.execution_template.template_id,
            parameter_overrides=submission.parameter_overrides,
            rationale=submission.rationale,
            agent_decision=submission.agent_decision,
            status=request_status,
            policy_decision=decision,
            approved_outputs=submission.requested_outputs if decision.outcome == "approved" else [],
            review_required=decision.outcome == "needs_human_review",
            denial_reason=decision.reason if decision.outcome == "denied" else None,
            created_at=now,
            updated_at=now,
        )
        self.store.upsert("requests", request_record.request_id, request_record.model_dump(mode="json"))
        return request_record

    def get_request(self, request_id: str) -> Request:
        payload = self.store.get("requests", request_id)
        if payload is None:
            raise KeyError(request_id)
        try:
            return Request.model_validate(payload)
        except ValidationError as error:
            raise KeyError(request_id) from error

    def create_run(self, run_create: RunCreate) -> Run:
        request_record = self.get_request(run_create.request_id)
        if request_record.status != "approved":
            raise ValueError("Only approved requests can be executed")

        existing_run = self._find_run_for_request(request_record.request_id)
        if existing_run is not None:
            raise RuntimeError(existing_run.run_id)

        claim = self.get_claim(request_record.claim_id)
        baseline_result = claim.evidence.baseline_result
        if baseline_result is None:
            raise ValueError("Claim is missing baseline evidence required for reruns")
        policy = self.get_policy(claim.policy.policy_id)
        merged_parameters = self._merge_parameters(
            claim.execution_template.input_parameters,
            request_record.parameter_overrides,
        )
        started_at = utc_now()
        result_summary = self._execute(claim, request_record.requester.lab_id, merged_parameters)
        contradiction = self._detect_contradiction(
            baseline_result.metric_value,
            result_summary.metric_value,
            policy.divergence_threshold,
        )
        finished_at = utc_now()
        claim_digest = stable_digest(claim.model_dump(mode="json"))
        template_digest = stable_digest(claim.execution_template.model_dump(mode="json"))
        provenance = ProvenanceBundle(
            provenance_id=new_id("provenance"),
            run_id="pending",
            request_id=request_record.request_id,
            claim_id=claim.claim_id,
            claim_version=claim.version,
            initiated_by=request_record.requester.agent_id or "inceptum-poc-demo",
            requested_by_lab=request_record.requester.lab_id,
            executed_by_lab=self.config.lab_id,
            execution_template_id=claim.execution_template.template_id,
            execution_template_version=claim.execution_template.version,
            parameters=merged_parameters,
            outputs={"result_summary": result_summary.model_dump(mode="json")},
            started_at=started_at,
            finished_at=finished_at,
            policy_id=policy.policy_id,
            policy_decision_id=request_record.policy_decision.policy_decision_id,
            claim_digest=claim_digest,
            template_digest=template_digest,
            runtime_fingerprint={
                "executing_lab": self.config.lab_id,
                "requested_template_id": request_record.requested_template_id,
                "request_purpose": request_record.request_purpose,
            },
            environment={"node_endpoint": self.config.node_endpoint},
        )

        run_id = new_id("run")
        provenance = provenance.model_copy(update={"run_id": run_id})
        investigation_task = None
        if contradiction is not None:
            investigation_task = InvestigationTask(
                task_id=new_id("task"),
                claim_id=claim.claim_id,
                triggering_run_id=run_id,
                linked_contradiction_id=contradiction.contradiction_id,
                trigger_type="contradiction",
                summary=(
                    "Cross-lab rerun diverged from the published claim and requires follow-up "
                    "investigation before the claim is extended."
                ),
                recommended_next_step=(
                    "Compare Lab A and Lab B validation settings, rerun with matched scaffold "
                    "split parameters, and review provenance side-by-side."
                ),
                recommended_workflow="workflow:matched-scaffold-rerun",
                possible_causes=[
                    RankedCause(
                        cause="validation_split_mismatch",
                        confidence=0.92,
                        rationale="The published baseline and rerun may not have used identical scaffold partitioning.",
                    ),
                    RankedCause(
                        cause="parameter_drift",
                        confidence=0.71,
                        rationale="The rerun template may have inherited a different threshold or calibration path.",
                    ),
                    RankedCause(
                        cause="feature_pipeline_difference",
                        confidence=0.54,
                        rationale="A local feature-preparation branch could have diverged between release and rerun.",
                    ),
                ],
                priority="high",
                status="open",
                created_at=finished_at,
                assigned_lab=self.config.lab_id,
                assigned_agent_role="investigation-agent",
                context={
                    "baseline_metric_value": baseline_result.metric_value,
                    "rerun_metric_value": result_summary.metric_value,
                    "threshold": policy.divergence_threshold,
                },
            )
            self.store.upsert(
                "investigation_tasks",
                investigation_task.task_id,
                investigation_task.model_dump(mode="json"),
            )

        run_record = Run(
            run_id=run_id,
            request_id=request_record.request_id,
            claim_id=claim.claim_id,
            claim_version=claim.version,
            executing_lab=self.config.lab_id,
            execution_template_id=claim.execution_template.template_id,
            execution_template_version=claim.execution_template.version,
            parameters=merged_parameters,
            status="completed",
            outcome_type="contradiction_detected" if contradiction is not None else "success",
            policy_decision_id=request_record.policy_decision.policy_decision_id,
            started_at=started_at,
            finished_at=finished_at,
            result_summary=result_summary,
            provenance_id=provenance.provenance_id,
            contradiction=contradiction,
            investigation_task_id=investigation_task.task_id if investigation_task else None,
        )
        self.store.upsert("provenance", provenance.provenance_id, provenance.model_dump(mode="json"))
        self.store.upsert("runs", run_record.run_id, run_record.model_dump(mode="json"))
        self._update_claim_after_run(
            claim=claim,
            request_record=request_record,
            run_record=run_record,
            provenance=provenance,
            investigation_task=investigation_task,
        )

        completed_request = request_record.model_copy(
            update={"status": "completed", "updated_at": finished_at}
        )
        self.store.upsert(
            "requests",
            completed_request.request_id,
            completed_request.model_dump(mode="json"),
        )
        return run_record

    def get_run(self, run_id: str) -> Run:
        payload = self.store.get("runs", run_id)
        if payload is None:
            raise KeyError(run_id)
        try:
            return Run.model_validate(payload)
        except ValidationError as error:
            raise KeyError(run_id) from error

    def get_result(self, run_id: str) -> RunResultResponse:
        run = self.get_run(run_id)
        if run.result_summary is None:
            raise KeyError(run_id)
        return RunResultResponse(
            run_id=run.run_id,
            request_id=run.request_id,
            claim_id=run.claim_id,
            claim_version=run.claim_version,
            execution_template_id=run.execution_template_id,
            policy_decision_id=run.policy_decision_id,
            status=run.status,
            outcome_type=run.outcome_type,
            result_summary=run.result_summary,
            contradiction=run.contradiction,
            investigation_task_id=run.investigation_task_id,
        )

    def get_provenance(self, run_id: str) -> ProvenanceBundle:
        run = self.get_run(run_id)
        if run.provenance_id is None:
            raise KeyError(run_id)
        payload = self.store.get("provenance", run.provenance_id)
        if payload is None:
            raise KeyError(run.provenance_id)
        try:
            return ProvenanceBundle.model_validate(payload)
        except ValidationError as error:
            raise KeyError(run.provenance_id) from error

    def get_capabilities(self) -> CapabilitySummary:
        return CapabilitySummary(
            lab_id=self.config.lab_id,
            node_endpoint=self.config.node_endpoint,
            supported_actions=["rerun"],
            execution_templates=self.config.execution_templates,
            policies=[policy.policy_id for policy in self.config.policies],
        )

    def list_investigation_tasks(self) -> list[InvestigationTask]:
        tasks: list[InvestigationTask] = []
        for payload in self.store.list("investigation_tasks"):
            try:
                tasks.append(InvestigationTask.model_validate(payload))
            except ValidationError:
                continue
        return tasks

    def get_investigation_task(self, task_id: str) -> InvestigationTask:
        payload = self.store.get("investigation_tasks", task_id)
        if payload is None:
            raise KeyError(task_id)
        try:
            return InvestigationTask.model_validate(payload)
        except ValidationError as error:
            raise KeyError(task_id) from error

    def reset_demo_state(self) -> ResetResponse:
        cleared_tables = [
            "claims",
            "requests",
            "runs",
            "provenance",
            "investigation_tasks",
            "policies",
        ]
        self.store.clear_tables(cleared_tables)
        self._seed()
        return ResetResponse(
            status="ok",
            service="lab-node",
            cleared_tables=cleared_tables,
            restored_claim_ids=[claim.claim_id for claim in self.config.claims],
        )

    def _evaluate_policy(self, submission: RequestSubmission, policy: Policy) -> PolicyDecision:
        denied_outputs = [
            output_name
            for output_name in submission.requested_outputs
            if output_name in policy.denied_output_classes
        ]
        review_outputs = [
            output_name
            for output_name in submission.requested_outputs
            if output_name in policy.requires_human_review_for
        ]
        unsupported_outputs = [
            output_name
            for output_name in submission.requested_outputs
            if output_name not in policy.allowed_outputs
            and output_name not in policy.denied_output_classes
            and output_name not in policy.requires_human_review_for
        ]
        if submission.requested_action != "rerun":
            outcome = "denied"
            reason = "Only rerun requests are supported in this PoC."
        elif submission.requester.lab_id not in policy.allowlisted_requester_labs:
            outcome = "denied"
            reason = f"Requester lab {submission.requester.lab_id} is not allowlisted."
        elif denied_outputs:
            outcome = "denied"
            reason = "Local policy blocks release of the requested outputs: " + ", ".join(denied_outputs)
        elif review_outputs:
            outcome = "needs_human_review"
            reason = (
                "Requested outputs require human approval before release: "
                + ", ".join(review_outputs)
            )
        elif unsupported_outputs:
            outcome = "denied"
            reason = (
                "Requested outputs are not exposed by local policy: "
                + ", ".join(unsupported_outputs)
            )
        else:
            outcome = "approved"
            reason = "Requester is allowlisted and only summary outputs were requested."

        return PolicyDecision(
            policy_decision_id=new_id("policy-decision"),
            policy_id=policy.policy_id,
            outcome=outcome,
            reason=reason,
            decided_by="rule-based-policy-engine",
            decided_at=utc_now(),
        )

    def _merge_parameters(
        self,
        defaults: dict[str, Any],
        overrides: dict[str, Any],
    ) -> dict[str, Any]:
        merged = dict(defaults)
        merged.update(overrides)
        return merged

    def _execute(
        self,
        claim: ClaimManifest,
        requester_lab: str,
        parameters: dict[str, Any],
    ) -> ResultSummary:
        runtime_template = self.config.get_runtime_template(claim.execution_template.template_id)
        adjustment = (
            runtime_template.internal_adjustment
            if requester_lab == self.config.lab_id
            else runtime_template.external_adjustment
        )
        manual_adjustment = float(parameters.get("score_adjustment", 0.0))
        metric_value = round(runtime_template.baseline_metric_value + adjustment + manual_adjustment, 3)
        summary_prefix = (
            "Internal rerun remained close to the published baseline."
            if requester_lab == self.config.lab_id
            else "Cross-lab rerun diverged from the published baseline."
        )
        return ResultSummary(
            metric_name=runtime_template.metric_name,
            metric_value=metric_value,
            expected_metric_value=claim.evidence.baseline_result.metric_value if claim.evidence.baseline_result else None,
            units=runtime_template.units,
            summary=(
                f"{summary_prefix} Local execution stayed inside {self.config.display_name} "
                "and only approved summary outputs were released."
            ),
            released_outputs=["result_summary", "provenance"],
        )

    def _update_claim_after_run(
        self,
        claim: ClaimManifest,
        request_record: Request,
        run_record: Run,
        provenance: ProvenanceBundle,
        investigation_task: InvestigationTask | None,
    ) -> None:
        evidence = claim.evidence.model_copy(deep=True)
        links = claim.links.model_copy(deep=True)
        links.latest_provenance_id = provenance.provenance_id
        links.latest_run_id = run_record.run_id

        if run_record.contradiction is not None:
            if run_record.contradiction.contradiction_id not in links.contradictions:
                links.contradictions.append(run_record.contradiction.contradiction_id)
        else:
            if provenance.provenance_id not in evidence.supporting_refs:
                evidence.supporting_refs.append(provenance.provenance_id)

        if investigation_task is not None and investigation_task.task_id not in links.linked_tasks:
            links.linked_tasks.append(investigation_task.task_id)

        if run_record.contradiction is not None:
            new_status = "under_investigation"
            outcome_type = "contradiction_detected"
            summary = "Cross-lab rerun contradicted the published baseline and opened an investigation."
        elif request_record.requester.lab_id != self.config.lab_id:
            new_status = "replicated"
            outcome_type = "replication_confirmed"
            summary = "Cross-lab rerun stayed within the allowed divergence threshold."
        else:
            new_status = claim.status
            outcome_type = "local_verification"
            summary = "Local verification rerun remained close to the published baseline."

        updated_claim = claim.model_copy(
            update={
                "status": new_status,
                "updated_at": run_record.finished_at,
                "evidence": evidence,
                "links": links,
                "last_replication_outcome": ReplicationOutcome(
                    request_id=request_record.request_id,
                    run_id=run_record.run_id,
                    claim_version=claim.version,
                    outcome_type=outcome_type,
                    observed_metric_value=run_record.result_summary.metric_value,
                    summary=summary,
                    requester_lab=request_record.requester.lab_id,
                    policy_decision_id=request_record.policy_decision.policy_decision_id,
                    observed_at=run_record.finished_at,
                ),
            }
        )
        self.store.upsert("claims", updated_claim.claim_id, updated_claim.model_dump(mode="json"))

    def _detect_contradiction(
        self,
        baseline_metric_value: float,
        rerun_metric_value: float,
        threshold: float,
    ) -> Contradiction | None:
        divergence = round(abs(baseline_metric_value - rerun_metric_value), 3)
        if divergence < threshold:
            return None
        return Contradiction(
            contradiction_id=new_id("contradiction"),
            baseline_metric_value=baseline_metric_value,
            rerun_metric_value=rerun_metric_value,
            divergence=divergence,
            threshold=threshold,
            rule=f"abs(baseline-rerun) >= {threshold}",
            severity="critical" if divergence >= threshold * 1.5 else "warning",
            detected_at=utc_now(),
        )

    def _find_run_for_request(self, request_id: str) -> Run | None:
        for payload in self.store.list("runs"):
            try:
                run = Run.model_validate(payload)
            except ValidationError:
                continue
            if run.request_id == request_id:
                return run
        return None

    def _config_claim(self, claim_id: str) -> ClaimManifest | None:
        for claim in self.config.claims:
            if claim.claim_id == claim_id:
                return claim
        return None


def create_app(config_path: str, db_path: str) -> FastAPI:
    config = load_lab_node_config(config_path)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.service = LabNodeService(config=config, store=JsonSqliteStore(db_path))
        yield

    app = FastAPI(
        title=f"Inceptum Node: {config.display_name}",
        version="0.1.0",
        summary="Reusable lab node for local policy, execution, and provenance in the Inceptum PoC.",
        lifespan=lifespan,
    )

    def get_service(request: FastAPIRequest) -> LabNodeService:
        return request.app.state.service

    @app.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse(status="ok", service="lab-node", lab_id=config.lab_id)

    @app.get("/claims/{claim_id}", response_model=ClaimManifest)
    def get_claim(claim_id: str, request: FastAPIRequest) -> ClaimManifest:
        try:
            return get_service(request).get_claim(claim_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=f"Claim {claim_id} not found") from error

    @app.post("/requests", response_model=Request)
    def create_request(submission: RequestSubmission, request: FastAPIRequest) -> Request:
        try:
            return get_service(request).create_request(submission)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=f"Claim or policy not found: {error}") from error
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @app.get("/requests/{request_id}", response_model=Request)
    def get_request(request_id: str, request: FastAPIRequest) -> Request:
        try:
            return get_service(request).get_request(request_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=f"Request {request_id} not found") from error

    @app.post("/runs", response_model=Run)
    def create_run(run_create: RunCreate, request: FastAPIRequest) -> Run:
        try:
            return get_service(request).create_run(run_create)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=f"Record not found: {error}") from error
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        except RuntimeError as error:
            raise HTTPException(
                status_code=409,
                detail=f"Request already executed under run {error}",
            ) from error

    @app.get("/runs/{run_id}", response_model=Run)
    def get_run(run_id: str, request: FastAPIRequest) -> Run:
        try:
            return get_service(request).get_run(run_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=f"Run {run_id} not found") from error

    @app.get("/runs/{run_id}/result", response_model=RunResultResponse)
    def get_result(run_id: str, request: FastAPIRequest) -> RunResultResponse:
        try:
            return get_service(request).get_result(run_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=f"Result for run {run_id} not found") from error

    @app.get("/runs/{run_id}/provenance", response_model=ProvenanceBundle)
    def get_provenance(run_id: str, request: FastAPIRequest) -> ProvenanceBundle:
        try:
            return get_service(request).get_provenance(run_id)
        except KeyError as error:
            raise HTTPException(
                status_code=404,
                detail=f"Provenance for run {run_id} not found",
            ) from error

    @app.get("/policies/{policy_id}", response_model=Policy)
    def get_policy(policy_id: str, request: FastAPIRequest) -> Policy:
        try:
            return get_service(request).get_policy(policy_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=f"Policy {policy_id} not found") from error

    @app.get("/capabilities", response_model=CapabilitySummary)
    def get_capabilities(request: FastAPIRequest) -> CapabilitySummary:
        return get_service(request).get_capabilities()

    @app.get("/investigation-tasks", response_model=list[InvestigationTask])
    def list_investigation_tasks(request: FastAPIRequest) -> list[InvestigationTask]:
        return get_service(request).list_investigation_tasks()

    @app.get("/investigation-tasks/{task_id}", response_model=InvestigationTask)
    def get_investigation_task(task_id: str, request: FastAPIRequest) -> InvestigationTask:
        try:
            return get_service(request).get_investigation_task(task_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=f"Task {task_id} not found") from error

    @app.post("/demo/reset", response_model=ResetResponse)
    def reset_demo_state(request: FastAPIRequest) -> ResetResponse:
        return get_service(request).reset_demo_state()

    return app
