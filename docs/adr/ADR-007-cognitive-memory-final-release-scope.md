# ADR-007: Cognitive Memory Final Release Scope

Status: Accepted

Date: 2026-07-02

## Context

The cognitive-memory final acceptance plan originally listed two broad items
that can grow beyond the core system:

- external comparison runs against Graphiti, Letta, Mem0, or similar systems;
- UI and deeper agent integrations.

Both are valuable product milestones, but neither is required to prove that
King Synapse has completed its own cognitive-memory loop. They also depend on
external product behavior, account setup, integration surfaces, and evaluation
formats that are outside this repository's reproducible release gates.

The final cognitive-memory release should be judged by evidence that is
available from this repo:

- visible recall;
- latent hidden activation;
- state and goal modulation;
- dominant and suppressed cognitive traces;
- predictive continuation;
- explicit post-report reinforcement;
- lifecycle support from Reflection, Merge, Forget, and Hebbian algorithms;
- full command, benchmark, and manual surface validation.

## Decision

External product comparisons are moved out of the final cognitive-memory
release scope. The current release must keep the exported long-session dataset
and benchmark as the reproducible internal comparison baseline.

UI and deeper agent integrations are also moved out of the final release scope.
They are post-final product milestones and must not block the cognitive-memory
release tag.

The final release remains blocked by internal evidence only:

1. required verification gates in `docs/COGNITIVE_MEMORY_FINAL_ACCEPTANCE.md`;
2. RFC-012 through RFC-015 freeze-review disposition;
3. dated manual CLI/MCP validation transcript paste;
4. final release note and tag evidence.

## Consequences

- The final release can be completed without calling external services.
- Graphiti, Letta, Mem0, DMR, LongMemEval, UI, and agent integrations remain
  important future evaluation and product work.
- Future comparison work should get its own benchmark note or ADR when it
  becomes release-blocking.
- The cognitive-memory release remains evidence-driven and reproducible from
  local source, tests, benchmarks, and documented manual transcripts.
