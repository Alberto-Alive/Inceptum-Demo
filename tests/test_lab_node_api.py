from __future__ import annotations

import json


CLAIM_ID = "inceptum:qsar:auroc:001"


def approved_submission(requester_lab: str, requester_endpoint: str, outputs: list[str]) -> dict:
    return {
        "claim_id": CLAIM_ID,
        "requester": {
            "lab_id": requester_lab,
            "node_endpoint": requester_endpoint,
            "agent_id": f"agent:{requester_lab}:planner",
        },
        "target_lab": "lab-a",
        "requested_action": "rerun",
        "request_purpose": "replication",
        "requested_outputs": outputs,
        "requested_template_id": "template-qsar-rerun",
        "parameter_overrides": {},
        "rationale": "Validation rerun for the published claim.",
        "agent_decision": {
            "agent_id": f"agent:{requester_lab}:planner",
            "decision_type": "request_rerun",
            "decision": "request_rerun",
            "rationale": "The planner decided a rerun is the right next action.",
            "scored_reasons": [
                {
                    "label": "claim_relevance",
                    "score": 0.9,
                    "summary": "The claim is important enough to replicate."
                }
            ]
        },
    }


def test_capabilities_and_policy_endpoints(lab_a_client) -> None:
    capability_response = lab_a_client.get("/capabilities")
    assert capability_response.status_code == 200
    capabilities = capability_response.json()
    assert capabilities["lab_id"] == "lab-a"
    assert capabilities["supported_actions"] == ["rerun"]
    assert len(capabilities["execution_templates"]) == 1

    policy_response = lab_a_client.get("/policies/policy-lab-a-rerun")
    assert policy_response.status_code == 200
    assert policy_response.json()["allowlisted_requester_labs"] == ["lab-a", "lab-b"]
    assert policy_response.json()["denied_output_classes"] == ["raw_data"]


def test_cross_lab_request_run_provenance_and_investigation_task(lab_a_client) -> None:
    request_response = lab_a_client.post(
        "/requests",
        json=approved_submission("lab-b", "http://localhost:8002", ["result_summary", "provenance"]),
    )
    assert request_response.status_code == 200
    request_payload = request_response.json()
    assert request_payload["status"] == "approved"
    assert request_payload["requester"]["lab_id"] == "lab-b"
    assert request_payload["policy_decision"]["policy_decision_id"].startswith("inceptum:policy-decision:")
    assert request_payload["agent_decision"]["decision"] == "request_rerun"

    run_response = lab_a_client.post("/runs", json={"request_id": request_payload["request_id"]})
    assert run_response.status_code == 200
    run_payload = run_response.json()
    assert run_payload["status"] == "completed"
    assert run_payload["outcome_type"] == "contradiction_detected"
    assert run_payload["contradiction"] is not None
    assert run_payload["investigation_task_id"] is not None

    result_response = lab_a_client.get(f"/runs/{run_payload['run_id']}/result")
    assert result_response.status_code == 200
    result_payload = result_response.json()
    assert result_payload["request_id"] == request_payload["request_id"]
    assert result_payload["contradiction"]["divergence"] == 0.15

    provenance_response = lab_a_client.get(f"/runs/{run_payload['run_id']}/provenance")
    assert provenance_response.status_code == 200
    provenance_payload = provenance_response.json()
    assert provenance_payload["requested_by_lab"] == "lab-b"
    assert provenance_payload["request_id"] == request_payload["request_id"]
    assert provenance_payload["policy_decision_id"] == request_payload["policy_decision"]["policy_decision_id"]
    assert provenance_payload["claim_digest"].startswith("sha256:")
    assert provenance_payload["template_digest"].startswith("sha256:")

    task_id = run_payload["investigation_task_id"]
    task_response = lab_a_client.get(f"/investigation-tasks/{task_id}")
    assert task_response.status_code == 200
    task_payload = task_response.json()
    assert task_payload["triggering_run_id"] == run_payload["run_id"]
    assert task_payload["linked_contradiction_id"] == run_payload["contradiction"]["contradiction_id"]
    assert task_payload["priority"] == "high"
    assert task_payload["possible_causes"][0]["cause"] == "validation_split_mismatch"

    claim_response = lab_a_client.get(f"/claims/{CLAIM_ID}")
    assert claim_response.status_code == 200
    claim_payload = claim_response.json()
    assert claim_payload["status"] == "under_investigation"
    assert run_payload["run_id"] == claim_payload["links"]["latest_run_id"]
    assert task_id in claim_payload["links"]["linked_tasks"]
    assert run_payload["contradiction"]["contradiction_id"] in claim_payload["links"]["contradictions"]
    assert claim_payload["last_replication_outcome"]["outcome_type"] == "contradiction_detected"


def test_demo_reset_restores_clean_claim_state(lab_a_client) -> None:
    request_response = lab_a_client.post(
        "/requests",
        json=approved_submission("lab-b", "http://localhost:8002", ["result_summary", "provenance"]),
    )
    request_payload = request_response.json()
    lab_a_client.post("/runs", json={"request_id": request_payload["request_id"]})

    reset_response = lab_a_client.post("/demo/reset")
    assert reset_response.status_code == 200
    assert reset_response.json()["restored_claim_ids"] == [CLAIM_ID]

    claim_payload = lab_a_client.get(f"/claims/{CLAIM_ID}").json()
    assert claim_payload["status"] == "published"
    assert claim_payload["links"]["contradictions"] == []
    assert claim_payload["links"]["linked_tasks"] == []
    assert claim_payload["last_replication_outcome"] is None


def test_denied_and_manual_review_policy_outcomes(lab_a_client) -> None:
    denied_response = lab_a_client.post(
        "/requests",
        json=approved_submission("lab-c", "http://localhost:8999", ["result_summary"]),
    )
    assert denied_response.status_code == 200
    assert denied_response.json()["status"] == "denied"
    assert "allowlisted" in denied_response.json()["denial_reason"]

    blocked_output_response = lab_a_client.post(
        "/requests",
        json=approved_submission("lab-b", "http://localhost:8002", ["result_summary", "raw_data"]),
    )
    assert blocked_output_response.status_code == 200
    blocked_payload = blocked_output_response.json()
    assert blocked_payload["status"] == "denied"
    assert blocked_payload["denial_reason"] == "Local policy blocks release of the requested outputs: raw_data"

    review_response = lab_a_client.post(
        "/requests",
        json=approved_submission("lab-b", "http://localhost:8002", ["result_summary", "full_artifact_bundle"]),
    )
    assert review_response.status_code == 200
    review_payload = review_response.json()
    assert review_payload["status"] == "needs_human_review"
    assert review_payload["review_required"] is True

    run_response = lab_a_client.post("/runs", json={"request_id": review_payload["request_id"]})
    assert run_response.status_code == 409
    assert "Only approved requests can be executed" in run_response.json()["detail"]


def test_internal_rerun_and_public_output_isolation(lab_a_client) -> None:
    request_response = lab_a_client.post(
        "/requests",
        json=approved_submission("lab-a", "http://localhost:8001", ["result_summary", "provenance"]),
    )
    request_payload = request_response.json()

    run_response = lab_a_client.post("/runs", json={"request_id": request_payload["request_id"]})
    run_payload = run_response.json()
    assert run_payload["contradiction"] is None
    assert run_payload["outcome_type"] == "success"

    result_response = lab_a_client.get(f"/runs/{run_payload['run_id']}/result")
    provenance_response = lab_a_client.get(f"/runs/{run_payload['run_id']}/provenance")
    public_output = json.dumps(
        {
            "result": result_response.json(),
            "provenance": provenance_response.json(),
        }
    )
    assert "lab-a://datasets/kinase-screen-v3" not in public_output
    assert "raw_data" not in public_output

    claim_response = lab_a_client.get(f"/claims/{CLAIM_ID}")
    claim_payload = claim_response.json()
    assert claim_payload["last_replication_outcome"]["outcome_type"] == "local_verification"
