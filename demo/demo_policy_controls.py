from __future__ import annotations

from demo.common import CLAIM_ID, LAB_A_URL, LAB_B_URL, render_model, step
from inceptum_poc.models import AgentDecision, RequestSubmission, RequesterIdentity, ScoredReason
from sdk import InceptumClient


def main() -> None:
    lab_a = InceptumClient(node_url=LAB_A_URL)
    lab_a.reset_demo_state()

    step("1. Lab B requests raw data.", "The demo self-resets first, then local policy denies the request to prove governance is real.")
    denied_request = lab_a.submit_request(
        RequestSubmission(
            claim_id=CLAIM_ID,
            requester=RequesterIdentity(
                lab_id="lab-b",
                node_endpoint=LAB_B_URL,
                agent_id="agent:lab-b:planner",
            ),
            target_lab="lab-a",
            request_purpose="verification",
            requested_outputs=["result_summary", "raw_data"],
            requested_template_id="template-qsar-rerun",
            parameter_overrides={},
            rationale="Inspect the local assay rows behind the published summary.",
            agent_decision=AgentDecision(
                agent_id="agent:lab-b:planner",
                decision_type="request_rerun",
                decision="request_rerun",
                rationale="The planner wants deeper inspection but is intentionally testing whether policy blocks raw data release.",
                scored_reasons=[
                    ScoredReason(label="policy_boundary_test", score=0.95, summary="This request explicitly probes the raw-data boundary."),
                    ScoredReason(label="high_governance_signal", score=0.9, summary="A denied response will prove the governance layer is real."),
                ],
            ),
        )
    )
    assert denied_request.status == "denied"
    print(render_model(denied_request))

    step("2. Lab B requests a full artifact bundle.", "Policy keeps the request in needs_human_review instead of auto-approving it.")
    review_request = lab_a.submit_request(
        RequestSubmission(
            claim_id=CLAIM_ID,
            requester=RequesterIdentity(
                lab_id="lab-b",
                node_endpoint=LAB_B_URL,
                agent_id="agent:lab-b:planner",
            ),
            target_lab="lab-a",
            request_purpose="comparison",
            requested_outputs=["result_summary", "full_artifact_bundle"],
            requested_template_id="template-qsar-rerun",
            parameter_overrides={},
            rationale="Compare the local artifact bundle before accepting the claim.",
            agent_decision=AgentDecision(
                agent_id="agent:lab-b:planner",
                decision_type="request_rerun",
                decision="request_rerun",
                rationale="The planner is escalating to a workflow bundle request to see whether policy shifts into human review.",
                scored_reasons=[
                    ScoredReason(label="artifact_comparison_value", score=0.84, summary="A full bundle would help compare execution context."),
                    ScoredReason(label="expected_human_gate", score=0.88, summary="The planner expects this request to trigger manual review."),
                ],
            ),
        )
    )
    assert review_request.status == "needs_human_review"
    print(render_model(review_request))

    print("\nPolicy control demo complete.")


if __name__ == "__main__":
    main()
