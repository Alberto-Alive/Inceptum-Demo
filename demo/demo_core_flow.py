from __future__ import annotations

from demo.common import CLAIM_ID, DIRECTORY_URL, LAB_A_URL, LAB_B_URL, render_model, step
from lablinks_poc.models import AgentDecision, RequestSubmission, RequesterIdentity, RunCreate, ScoredReason
from sdk import LabLinksClient


def main() -> None:
    directory = LabLinksClient(directory_url=DIRECTORY_URL)
    lab_a = LabLinksClient(node_url=LAB_A_URL)
    lab_b = LabLinksClient(node_url=LAB_B_URL)

    directory.reset_demo_state(directory=True)
    lab_a.reset_demo_state()
    lab_b.reset_demo_state()

    step("1. Lab A publishes a claim manifest to the shared directory.", "The demo self-resets first, so the starting claim is clean, published, and machine-queryable.")
    claim = lab_a.get_node_claim(CLAIM_ID)
    directory.publish_claim(claim)
    print(render_model(claim))

    step("2. Lab B discovers the claim through the directory.", "The planner agent decides the claim is replication-worthy because only summary outputs are exposed.")
    discovered = directory.list_claims(query="kinase")
    assert any(item.claim_id == CLAIM_ID for item in discovered)
    print(f"Discovered {len(discovered)} matching claim(s).")

    step("3. Lab B inspects its local coordination capabilities.", "Local capabilities show Lab B can request reruns but not execute Lab A's private workflow.")
    print(render_model(lab_b.get_capabilities()))

    step("4. Lab B submits a rerun request to Lab A.", "The request carries planner identity, purpose, and the requested template.")
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
            parameter_overrides={},
            rationale="Reproduce the published QSAR claim under Lab B review.",
            agent_decision=AgentDecision(
                agent_id="agent:lab-b:planner",
                decision_type="request_rerun",
                decision="request_rerun",
                rationale="The claim is published, exposes only summary outputs, and should be challenged with an external replication request.",
                scored_reasons=[
                    ScoredReason(label="published_claim", score=0.98, summary="The claim is publicly discoverable."),
                    ScoredReason(label="summary_only_policy", score=0.93, summary="The policy allows a safe summary-only rerun."),
                    ScoredReason(label="replication_priority", score=0.88, summary="The assay claim is central enough to warrant replication."),
                ],
            ),
        )
    )
    assert request_record.status == "approved"
    print(render_model(request_record))

    step("5. Lab A executes the approved rerun locally.", "Execution stays inside Lab A and the returned run explicitly reports contradiction detection.")
    run = lab_a.create_run(RunCreate(request_id=request_record.request_id))
    result = lab_a.get_run_result(run.run_id)
    provenance = lab_a.get_run_provenance(run.run_id)
    assert result.contradiction is not None
    assert result.investigation_task_id is not None
    print(render_model(result))

    step("6. Lab A returns provenance without releasing raw data.", "The provenance bundle now ties request, policy decision, and digests into one audit chain.")
    print(render_model(provenance))

    step("7. The contradiction updates the claim itself.", "The claim status moves to under_investigation and links to the contradiction, latest run, and spawned task.")
    updated_claim = lab_a.get_node_claim(CLAIM_ID)
    assert updated_claim.status == "under_investigation"
    print(render_model(updated_claim))

    step("8. The contradiction creates a structured follow-up investigation task.", "The investigation loop records causes, workflow recommendation, and assigned agent role.")
    task = lab_a.get_investigation_task(result.investigation_task_id)
    print(render_model(task))

    print("\nCore flow complete.")


if __name__ == "__main__":
    main()
