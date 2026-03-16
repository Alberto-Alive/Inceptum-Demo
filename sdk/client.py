from __future__ import annotations

from typing import Any

import httpx

from inceptum_poc.models import (
    CapabilitySummary,
    ClaimManifest,
    InvestigationTask,
    Policy,
    Request,
    RequestSubmission,
    ResetResponse,
    Run,
    RunCreate,
    RunResultResponse,
    ProvenanceBundle,
)


class InceptumClient:
    def __init__(
        self,
        directory_url: str | None = None,
        node_url: str | None = None,
        timeout: float = 10.0,
    ):
        self.directory_url = directory_url.rstrip("/") if directory_url else None
        self.node_url = node_url.rstrip("/") if node_url else None
        self.timeout = timeout

    def publish_claim(self, claim: ClaimManifest) -> ClaimManifest:
        payload = self._post(self._require_directory(), "/claims", claim.model_dump(mode="json"))
        return ClaimManifest.model_validate(payload)

    def list_claims(self, query: str | None = None) -> list[ClaimManifest]:
        params = {"q": query} if query else None
        payload = self._get(self._require_directory(), "/claims", params=params)
        return [ClaimManifest.model_validate(item) for item in payload]

    def get_directory_claim(self, claim_id: str) -> ClaimManifest:
        payload = self._get(self._require_directory(), f"/claims/{claim_id}")
        return ClaimManifest.model_validate(payload)

    def get_node_claim(self, claim_id: str, node_url: str | None = None) -> ClaimManifest:
        payload = self._get(self._resolve_node(node_url), f"/claims/{claim_id}")
        return ClaimManifest.model_validate(payload)

    def submit_request(
        self,
        submission: RequestSubmission,
        node_url: str | None = None,
    ) -> Request:
        payload = self._post(
            self._resolve_node(node_url),
            "/requests",
            submission.model_dump(mode="json"),
        )
        return Request.model_validate(payload)

    def get_request(self, request_id: str, node_url: str | None = None) -> Request:
        payload = self._get(self._resolve_node(node_url), f"/requests/{request_id}")
        return Request.model_validate(payload)

    def create_run(self, run_create: RunCreate, node_url: str | None = None) -> Run:
        payload = self._post(
            self._resolve_node(node_url),
            "/runs",
            run_create.model_dump(mode="json"),
        )
        return Run.model_validate(payload)

    def get_run(self, run_id: str, node_url: str | None = None) -> Run:
        payload = self._get(self._resolve_node(node_url), f"/runs/{run_id}")
        return Run.model_validate(payload)

    def get_run_result(self, run_id: str, node_url: str | None = None) -> RunResultResponse:
        payload = self._get(self._resolve_node(node_url), f"/runs/{run_id}/result")
        return RunResultResponse.model_validate(payload)

    def get_run_provenance(
        self,
        run_id: str,
        node_url: str | None = None,
    ) -> ProvenanceBundle:
        payload = self._get(self._resolve_node(node_url), f"/runs/{run_id}/provenance")
        return ProvenanceBundle.model_validate(payload)

    def get_policy(self, policy_id: str, node_url: str | None = None) -> Policy:
        payload = self._get(self._resolve_node(node_url), f"/policies/{policy_id}")
        return Policy.model_validate(payload)

    def get_capabilities(self, node_url: str | None = None) -> CapabilitySummary:
        payload = self._get(self._resolve_node(node_url), "/capabilities")
        return CapabilitySummary.model_validate(payload)

    def list_investigation_tasks(self, node_url: str | None = None) -> list[InvestigationTask]:
        payload = self._get(self._resolve_node(node_url), "/investigation-tasks")
        return [InvestigationTask.model_validate(item) for item in payload]

    def get_investigation_task(
        self,
        task_id: str,
        node_url: str | None = None,
    ) -> InvestigationTask:
        payload = self._get(self._resolve_node(node_url), f"/investigation-tasks/{task_id}")
        return InvestigationTask.model_validate(payload)

    def reset_demo_state(
        self,
        *,
        directory: bool = False,
        node_url: str | None = None,
    ) -> ResetResponse:
        base_url = self._require_directory() if directory else self._resolve_node(node_url)
        payload = self._post(base_url, "/demo/reset", {})
        return ResetResponse.model_validate(payload)

    def _require_directory(self) -> str:
        if not self.directory_url:
            raise ValueError("directory_url is required for directory operations")
        return self.directory_url

    def _resolve_node(self, node_url: str | None = None) -> str:
        resolved = node_url or self.node_url
        if not resolved:
            raise ValueError("node_url is required for node operations")
        return resolved

    def _get(self, base_url: str, path: str, params: dict[str, Any] | None = None) -> Any:
        with httpx.Client(base_url=base_url, timeout=self.timeout) as client:
            response = client.get(path, params=params)
            response.raise_for_status()
            return response.json()

    def _post(self, base_url: str, path: str, payload: dict[str, Any]) -> Any:
        with httpx.Client(base_url=base_url, timeout=self.timeout) as client:
            response = client.post(path, json=payload)
            response.raise_for_status()
            return response.json()
