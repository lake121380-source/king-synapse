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
| RFC-007 | Reflection Processing | Draft |
| RFC-008 | Hebbian Reinforcement | Planned |
| RFC-009 | Forgetting | Planned |
| RFC-010 | Sleep Cycle | Planned |

## Phase 4 Order

```text
P4.1 Consolidation Executor
  -> P4.2 Reflection Processor
  -> P4.3 Hebbian Executor
  -> P4.4 Forgetting Engine
  -> P4.5 Sleep Cycle
```
