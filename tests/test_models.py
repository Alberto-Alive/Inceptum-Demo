from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from lablinks_poc.models import ClaimManifest, InvestigationTask, ProvenanceBundle, Request, Run


ROOT = Path(__file__).resolve().parents[1]


def load_example(path: str) -> dict:
    with (ROOT / path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def sample_run() -> dict:
    return {
        "run_id": "lablinks:run:001",
        "request_id": "lablinks:request:001",
        "claim_id": "lablinks:qsar:auroc:001",
        "claim_version": "1.0.0",
        "executing_lab": "lab-a",
        "execution_template_id": "template-qsar-rerun",
        "execution_template_version": "2026.03",
        "parameters": {
            "validation_split": "scaffold",
            "score_adjustment": 0.0,
        },
        "status": "completed",
        "outcome_type": "contradiction_detected",
        "policy_decision_id": "lablinks:policy-decision:001",
        "started_at": "2026-03-11T09:06:30+00:00",
        "finished_at": "2026-03-11T09:07:00+00:00",
        "result_summary": load_example("examples/result.json")["result_summary"],
        "provenance_id": "lablinks:provenance:001",
        "contradiction": load_example("examples/result.json")["contradiction"],
        "investigation_task_id": "lablinks:task:001",
    }


@pytest.mark.parametrize(
    ("model_type", "payload"),
    [
        (ClaimManifest, load_example("examples/claim.json")),
        (ClaimManifest, load_example("examples/claim_after_contradiction.json")),
        (Request, load_example("examples/request.json")),
        (Run, sample_run()),
        (ProvenanceBundle, load_example("examples/provenance.json")),
        (InvestigationTask, load_example("examples/investigation_task.json")),
    ],
)
def test_public_models_reject_raw_data_fields(model_type, payload) -> None:
    invalid_payload = dict(payload)
    invalid_payload["raw_data_uri"] = "lab://private/raw-data"
    with pytest.raises(ValidationError):
        model_type.model_validate(invalid_payload)


def test_seed_claim_example_starts_clean() -> None:
    claim = ClaimManifest.model_validate(load_example("examples/claim.json"))
    assert claim.status == "published"
    assert claim.links.contradictions == []
    assert claim.links.linked_tasks == []
    assert claim.last_replication_outcome is None
