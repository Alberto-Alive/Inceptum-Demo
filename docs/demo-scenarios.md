# Demo Scenarios

## Demo 1: Core cross-lab loop

Command:

```bash
python -m demo.demo_core_flow
```

Expected flow:

1. The demo resets all services so the seeded claim starts in a clean `published` state.
2. Lab A reads its local Claim Manifest.
3. The shared directory registers the manifest.
4. Lab B discovers the published claim.
5. Lab B submits a rerun request to Lab A.
6. Lab A auto-approves the request under local policy.
7. Lab A runs the workflow locally and returns only summary outputs plus provenance.
8. The rerun diverges from the published baseline.
9. The claim itself moves to `under_investigation` and links the contradiction, latest run, and spawned task.
10. Lab A records the contradiction and creates an investigation task.

Expected outputs:

- one published `ClaimManifest`
- one approved `Request`
- one completed `Run` with a `contradiction`
- one `ProvenanceBundle`
- one updated `ClaimManifest` in `under_investigation`
- one `InvestigationTask`

## Demo 2: Within-lab coordination

Command:

```bash
python -m demo.demo_within_lab
```

Simulated roles:

- planner agent
- review/policy agent
- execution agent
- provenance/logger agent

Expected flow:

1. The demo resets Lab A to a clean published claim.
2. Planner selects the local claim object.
3. Review agent checks the local policy.
4. Execution agent submits and runs an internal rerun.
5. Provenance agent fetches lineage for the completed run.

Expected outputs:

- an approved internal `Request`
- a completed `Run` without contradiction
- a `ProvenanceBundle` for the internal rerun

## Demo 3: Policy controls

Command:

```bash
python -m demo.demo_policy_controls
```

Expected flow:

1. The demo resets Lab A to a clean published claim.
2. Lab B requests raw data from Lab A and policy denies it.
3. Lab B requests a full artifact bundle and policy moves the request to human review.

Expected outputs:

- one denied `Request`
- one `Request` in `needs_human_review`

## Demo 4: Combined scenario

Command:

```bash
python -m demo.demo_cross_lab_agents
```

Expected flow:

1. The demo resets the directory and both lab nodes.
2. Lab B planner discovers Lab A's claim.
3. Lab B review agent confirms outbound capabilities.
4. Lab B execution agent submits the rerun request to Lab A.
5. Lab A policy agent confirms approval.
6. Lab A execution agent runs locally.
7. Lab A provenance agent returns lineage.
8. Lab A investigation agent inspects the contradiction-driven task.
