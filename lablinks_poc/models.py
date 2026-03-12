from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ExecutionTemplate(StrictModel):
    template_id: str
    version: str
    description: str
    input_parameters: dict[str, Any] = Field(default_factory=dict)
    released_outputs: list[str] = Field(default_factory=lambda: ["result_summary", "provenance"])


class ResultSummary(StrictModel):
    metric_name: str
    metric_value: float
    expected_metric_value: float | None = None
    units: str | None = None
    summary: str
    released_outputs: list[str] = Field(default_factory=list)


class Assertion(StrictModel):
    type: Literal[
        "hypothesis",
        "result",
        "observation",
        "method_claim",
        "negative_result",
        "replication_claim",
    ]
    subject: str
    predicate: str
    object: Any
    metric_name: str | None = None
    context: dict[str, Any] = Field(default_factory=dict)
    summary: str


class OwnerRef(StrictModel):
    lab_id: str
    node_id: str | None = None
    node_endpoint: str


class PolicyRef(StrictModel):
    policy_id: str


class ClaimRelationship(StrictModel):
    relation_type: Literal["contradicts", "replicates", "extends", "depends_on"]
    target_claim_id: str
    summary: str | None = None


class ClaimLinks(StrictModel):
    latest_provenance_id: str | None = None
    latest_run_id: str | None = None
    contradictions: list[str] = Field(default_factory=list)
    linked_tasks: list[str] = Field(default_factory=list)
    relationships: list[ClaimRelationship] = Field(default_factory=list)


class EvidenceBundle(StrictModel):
    baseline_result: ResultSummary | None = None
    supporting_refs: list[str] = Field(default_factory=list)


class RankedCause(StrictModel):
    cause: str
    confidence: float = Field(ge=0, le=1)
    rationale: str | None = None


class ScoredReason(StrictModel):
    label: str
    score: float = Field(ge=0, le=1)
    summary: str | None = None


class AgentDecision(StrictModel):
    agent_id: str
    decision_type: Literal["request_rerun", "triage_contradiction"]
    decision: str
    rationale: str
    scored_reasons: list[ScoredReason] = Field(default_factory=list)


class ReplicationOutcome(StrictModel):
    request_id: str
    run_id: str
    claim_version: str
    outcome_type: Literal["local_verification", "replication_confirmed", "contradiction_detected"]
    observed_metric_value: float
    summary: str
    requester_lab: str
    policy_decision_id: str | None = None
    observed_at: datetime


class PolicyDecision(StrictModel):
    policy_decision_id: str
    policy_id: str
    outcome: Literal["approved", "denied", "needs_human_review"]
    reason: str
    decided_by: str
    decided_at: datetime


class ClaimManifest(StrictModel):
    claim_id: str
    title: str
    assertion: Assertion
    status: Literal[
        "draft",
        "published",
        "supported",
        "contested",
        "replicated",
        "contradicted",
        "under_investigation",
        "superseded",
        "withdrawn",
    ]
    owner: OwnerRef
    policy: PolicyRef
    execution_template: ExecutionTemplate
    created_at: datetime
    updated_at: datetime
    version: str
    evidence: EvidenceBundle
    links: ClaimLinks = Field(default_factory=ClaimLinks)
    last_replication_outcome: ReplicationOutcome | None = None
    tags: list[str] = Field(default_factory=list)


class RequesterIdentity(StrictModel):
    lab_id: str
    node_endpoint: str
    agent_id: str | None = None
    human_sponsor: str | None = None


class RequestSubmission(StrictModel):
    claim_id: str
    requester: RequesterIdentity
    target_lab: str
    requested_action: Literal["rerun"] = "rerun"
    request_purpose: Literal["replication", "verification", "extension", "comparison"] = "replication"
    requested_outputs: list[str] = Field(default_factory=lambda: ["result_summary", "provenance"])
    requested_template_id: str | None = None
    parameter_overrides: dict[str, Any] = Field(default_factory=dict)
    rationale: str
    agent_decision: AgentDecision | None = None


class Request(StrictModel):
    request_id: str
    claim_id: str
    target_lab: str
    target_claim_version: str
    requester: RequesterIdentity
    requested_action: Literal["rerun"]
    request_purpose: Literal["replication", "verification", "extension", "comparison"]
    requested_outputs: list[str]
    requested_template_id: str
    parameter_overrides: dict[str, Any]
    rationale: str
    agent_decision: AgentDecision | None = None
    status: Literal["submitted", "approved", "denied", "needs_human_review", "running", "completed"]
    policy_decision: PolicyDecision
    approved_outputs: list[str] = Field(default_factory=list)
    review_required: bool = False
    denial_reason: str | None = None
    created_at: datetime
    updated_at: datetime


class RunCreate(StrictModel):
    request_id: str


class Contradiction(StrictModel):
    contradiction_id: str
    baseline_metric_value: float
    rerun_metric_value: float
    divergence: float
    threshold: float
    rule: str
    severity: Literal["warning", "critical"]
    detected_at: datetime


class Run(StrictModel):
    run_id: str
    request_id: str
    claim_id: str
    claim_version: str
    executing_lab: str
    execution_template_id: str
    execution_template_version: str
    parameters: dict[str, Any]
    status: Literal["queued", "running", "completed", "failed"]
    outcome_type: Literal["success", "contradiction_detected", "failure"] | None = None
    policy_decision_id: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    result_summary: ResultSummary | None = None
    provenance_id: str | None = None
    contradiction: Contradiction | None = None
    investigation_task_id: str | None = None


class RunResultResponse(StrictModel):
    run_id: str
    request_id: str
    claim_id: str
    claim_version: str
    execution_template_id: str
    policy_decision_id: str | None = None
    status: Literal["completed", "failed"]
    outcome_type: Literal["success", "contradiction_detected", "failure"] | None = None
    result_summary: ResultSummary
    contradiction: Contradiction | None = None
    investigation_task_id: str | None = None


class ProvenanceBundle(StrictModel):
    provenance_id: str
    run_id: str
    request_id: str
    claim_id: str
    claim_version: str
    initiated_by: str
    requested_by_lab: str
    executed_by_lab: str
    execution_template_id: str
    execution_template_version: str
    parameters: dict[str, Any]
    outputs: dict[str, Any]
    started_at: datetime
    finished_at: datetime
    policy_id: str
    policy_decision_id: str | None = None
    claim_digest: str | None = None
    template_digest: str | None = None
    runtime_fingerprint: dict[str, Any] = Field(default_factory=dict)
    environment: dict[str, str] = Field(default_factory=dict)


class InvestigationTask(StrictModel):
    task_id: str
    claim_id: str
    triggering_run_id: str
    linked_contradiction_id: str | None = None
    trigger_type: Literal["contradiction"]
    summary: str
    recommended_next_step: str
    recommended_workflow: str | None = None
    possible_causes: list[RankedCause] = Field(default_factory=list)
    priority: Literal["low", "medium", "high"] = "medium"
    status: Literal["open", "in_progress", "closed"]
    created_at: datetime
    assigned_lab: str
    assigned_agent_role: str | None = None
    context: dict[str, Any] = Field(default_factory=dict)


class Policy(StrictModel):
    policy_id: str
    lab_id: str
    name: str
    description: str
    allowlisted_requester_labs: list[str] = Field(default_factory=list)
    allowed_outputs: list[str] = Field(default_factory=lambda: ["result_summary", "provenance"])
    denied_output_classes: list[str] = Field(default_factory=list)
    requires_human_review_for: list[str] = Field(default_factory=list)
    divergence_threshold: float = Field(gt=0)


class CapabilitySummary(StrictModel):
    lab_id: str
    node_endpoint: str
    supported_actions: list[str]
    execution_templates: list[ExecutionTemplate]
    policies: list[str]


class HealthResponse(StrictModel):
    status: Literal["ok"]
    service: str
    lab_id: str | None = None


class ResetResponse(StrictModel):
    status: Literal["ok"]
    service: str
    cleared_tables: list[str]
    restored_claim_ids: list[str] = Field(default_factory=list)
