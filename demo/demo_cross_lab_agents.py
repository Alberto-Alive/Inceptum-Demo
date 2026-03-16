from __future__ import annotations

from demo.common import CLAIM_ID, DIRECTORY_URL, LAB_A_URL, LAB_B_URL, render_model, step
from inceptum_poc.models import AgentDecision, RequestSubmission, RequesterIdentity, RunCreate, ScoredReason
from sdk import InceptumClient


def main() -> None:
    directory = InceptumClient(directory_url=DIRECTORY_URL)
    lab_a = InceptumClient(node_url=LAB_A_URL)
    lab_b = InceptumClient(node_url=LAB_B_URL)

    directory.reset_demo_state(directory=True)
    lab_a.reset_demo_state()
    lab_b.reset_demo_state()

    step("Lab B planner agent discovers Lab A's claim.", "The demo self-resets first, so the planner sees a clean published claim and explicitly decides to request replication.")
    claim = lab_a.get_node_claim(CLAIM_ID)
    directory.publish_claim(claim)
    discovered = directory.get_directory_claim(CLAIM_ID)
    print(render_model(discovered))

    step("Lab B review agent checks local outbound capabilities.", "Capabilities confirm Lab B can coordinate without gaining access to Lab A raw data.")
    print(render_model(lab_b.get_capabilities()))

    step("Lab B execution agent submits the rerun request to Lab A.", "The request carries planner identity, purpose, and template intent.")
    request_record = lab_a.submit_request(
        RequestSubmission(
            claim_id=CLAIM_ID,
            requester=RequesterIdentity(
                lab_id="lab-b",
                node_endpoint=LAB_B_URL,
                agent_id="agent:lab-b:planner",
                human_sponsor="radial-reviewer",
            ),
            target_lab="lab-a",
            request_purpose="replication",
            requested_outputs=["result_summary", "provenance"],
            requested_template_id="template-qsar-rerun",
            parameter_overrides={"rerun_mode": "cross_lab_review"},
            rationale="Cross-lab validation of the published assay-score claim.",
            agent_decision=AgentDecision(
                agent_id="agent:lab-b:planner",
                decision_type="request_rerun",
                decision="request_rerun",
                rationale="The claim is externally published and should be challenged under a cross-lab replication workflow.",
                scored_reasons=[
                    ScoredReason(label="claim_visibility", score=0.97, summary="The directory exposes a published claim manifest."),
                    ScoredReason(label="external_validation_value", score=0.91, summary="A second lab can pressure-test the claim without raw data transfer."),
                    ScoredReason(label="safe_output_scope", score=0.9, summary="The requested outputs remain within policy-safe summary artifacts."),
                ],
            ),
        )
    )
    print(render_model(request_record))

    step("Lab A policy agent confirms the request is auto-approved.", "Policy remains local and no shared directory rule can override it.")
    refreshed_request = lab_a.get_request(request_record.request_id)
    assert refreshed_request.status == "approved"
    print(render_model(refreshed_request.policy_decision))

    step("Lab A execution agent runs the workflow and surfaces the contradiction.", "The run outcome is explicitly marked as contradiction_detected.")
    run = lab_a.create_run(RunCreate(request_id=request_record.request_id))
    print(render_model(lab_a.get_run_result(run.run_id)))

    step("Lab A provenance agent returns execution lineage.", "The provenance chain includes request, policy decision, and digests.")
    print(render_model(lab_a.get_run_provenance(run.run_id)))

    step("Lab A investigation agent inspects the spawned task.", "The follow-up task records causes, workflow recommendation, and assigned role.")
    task = lab_a.get_investigation_task(run.investigation_task_id)
    print(render_model(task))

    print("\nCombined cross-lab and within-lab coordination demo complete.")


if __name__ == "__main__":
    main()
