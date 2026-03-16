from __future__ import annotations

from demo.common import CLAIM_ID, LAB_A_URL, render_model, step
from inceptum_poc.models import AgentDecision, RequestSubmission, RequesterIdentity, RunCreate, ScoredReason
from sdk import InceptumClient


def main() -> None:
    lab_a = InceptumClient(node_url=LAB_A_URL)

    lab_a.reset_demo_state()

    step("Planner agent selects the local claim object.", "The demo self-resets first, so the planner starts from a clean published claim.")
    claim = lab_a.get_node_claim(CLAIM_ID)
    print(render_model(claim))

    step("Review agent checks the local rerun policy.", "Policy advertises which outputs are allowed, denied, or require review.")
    policy = lab_a.get_policy(claim.policy.policy_id)
    print(render_model(policy))

    step("Execution agent submits an internal rerun request.", "The request captures agent identity and intent even for within-lab coordination.")
    request_record = lab_a.submit_request(
        RequestSubmission(
            claim_id=CLAIM_ID,
            requester=RequesterIdentity(
                lab_id="lab-a",
                node_endpoint=LAB_A_URL,
                agent_id="agent:lab-a:execution",
            ),
            target_lab="lab-a",
            request_purpose="verification",
            requested_outputs=["result_summary", "provenance"],
            requested_template_id="template-qsar-rerun",
            parameter_overrides={},
            rationale="Internal verification before extending the claim.",
            agent_decision=AgentDecision(
                agent_id="agent:lab-a:execution",
                decision_type="request_rerun",
                decision="request_rerun",
                rationale="A local verification rerun should confirm the baseline before the claim is extended or re-published.",
                scored_reasons=[
                    ScoredReason(label="pre_publish_check", score=0.94, summary="The claim should be locally revalidated before extension."),
                    ScoredReason(label="template_ready", score=0.87, summary="The execution template is already configured for safe local use."),
                ],
            ),
        )
    )
    assert request_record.status == "approved"
    print(render_model(request_record))

    step("Execution agent runs the approved workflow locally.", "The local verification result stays close to baseline, so no contradiction is raised.")
    run = lab_a.create_run(RunCreate(request_id=request_record.request_id))
    result = lab_a.get_run_result(run.run_id)
    assert result.contradiction is None
    print(render_model(result))

    step("Provenance agent captures lineage for the internal rerun.", "The provenance bundle links the run back to the request and policy decision.")
    provenance = lab_a.get_run_provenance(run.run_id)
    print(render_model(provenance))

    print("\nWithin-lab coordination demo complete.")


if __name__ == "__main__":
    main()
