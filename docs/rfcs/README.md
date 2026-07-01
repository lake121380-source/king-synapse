# RFC Index

RFCs define behavioral implementation contracts after the Phase 2 and Phase 3 architecture freezes.

## Rules

1. Specifications come before behavior implementation.
2. Phase 2 Recall contracts require ADR approval for breaking changes.
3. Phase 3 Memory Evolution contracts require ADR approval for breaking changes.
4. Phase 4 implementations should prefer strategies and executors behind frozen interfaces.

## Registry

| RFC | Title | Status |
| --- | --- | --- |
| RFC-001 | Architecture | Frozen by `docs/ARCHITECTURE.md` |
| RFC-002 | Graph Schema | Planned |
| RFC-003 | Memory Lifecycle | Planned |
| RFC-004 | Retrieval & Activation | Frozen by `docs/RECALL_PIPELINE.md` |
| RFC-005 | Working Memory | Frozen by `docs/WORKING_MEMORY.md` |
| RFC-006 | Consolidation Execution | Draft |
| RFC-007 | Reflection Processing | Accepted: `v0.4.10`, `v0.4.11`, `v0.4.12`, `v0.4.19` |
| RFC-008 | Hebbian Execution | Accepted: `v0.4.20`, `v0.4.21`, `v0.4.22`, `v0.4.29` |
| RFC-009 | Store Integration | Accepted: `v0.4.30`, `v0.4.31`, `v0.4.32`, `v0.4.33`, `v0.4.39` |
| RFC-010 | Adaptive Policies | Accepted: `v0.4.40`, `v0.4.41`, `v0.4.42`, `v0.4.49` |
| RFC-011 | Adaptive Memory Common Model | Implemented (frozen `v0.5.9-adaptive-common-freeze`) |
| RFC-012 | Reflection Algorithm | Draft (`v0.6.0` skeleton, `v0.6.1` NoOp, `v0.6.2` deterministic reference, `v0.6.3` benchmark, `v0.6.4` processing adapter, `v0.6.5` store mutation plan, `v0.6.6` rule-based algorithm implemented) |
| RFC-013 | Merge Algorithm | Draft (`v0.7.0` skeleton, `v0.7.1` NoOp, `v0.7.2` rule-based reference, `v0.7.3` benchmark, `v0.7.4` store adapter implemented) |
| RFC-014 | Forgetting Algorithm | Draft (`v0.8.0` skeleton, `v0.8.1` NoOp, `v0.8.2` rule-based reference, `v0.8.3` benchmark, `v0.8.4` store adapter implemented) |
| RFC-015 | Hebbian Algorithm | Draft (`v0.9.0` skeleton, `v0.9.1` NoOp, `v0.9.2` rule-based reference, `v0.9.3` benchmark, `v0.9.4` store adapter implemented) |

## Phase 4 Order

```text
P4.1 Consolidation Executor
  -> P4.2 Reflection Processor
  -> P4.3 Hebbian Executor
  -> P4.4 Store Integration
  -> P4.5 Adaptive Policies
```

## Phase 5 Order

```text
RFC-011 Adaptive Memory Common Model
  -> Importance Skeleton
  -> Event Skeleton
  -> Benchmark Harness
  -> RFC-012 Reflection Algorithm
  -> RFC-013 Merge Algorithm
  -> RFC-014 Forgetting Algorithm
  -> RFC-015 Hebbian Algorithm
```

`RFC-015` is currently the active Phase 5 focus. RFC-012 has reached its
rule-based Reflection milestone (`v0.6.6`) and remains to be freeze-reviewed;
RFC-013 now has merge lifecycle milestones through `v0.7.4`; RFC-014 now has
forget lifecycle milestones through `v0.8.4`; RFC-015 now has skeleton, NoOp,
rule-based reference, benchmark, and store-adapter milestones through `v0.9.4`.
