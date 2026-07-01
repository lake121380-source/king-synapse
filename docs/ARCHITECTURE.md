# Architecture

| Phase | Goal | Output |
| --- | --- | --- |
| Phase 1 | Build a reliable capture pipeline. | Capture Engine |
| Phase 2 | Build a stable, explainable recall engine. | Recall API Freeze |
| Phase 3 | Freeze memory evolution contracts without changing the recall contract. | Memory Evolution Contract Freeze |
| Phase 4 | Implement adaptive behavior behind frozen contracts. | Adaptive Memory Foundation |

## Phase 4 Development Rules

1. Behavior modules must be implemented on top of the frozen Recall Platform, Memory Evolution Contract, and Adaptive Memory Foundation.
2. New behavior should follow the established execution model: `Plan -> Execute -> Report -> Sink`.
3. New extension points should reuse the existing plugin pattern: `Trait -> NoOp -> Concrete Implementation`.
4. Changes to frozen contracts require a dedicated ADR and a new architecture milestone.
5. Every new public trait must ship with a NoOp implementation before entering the public API.

## Reflection

```text
ReflectionEvent
  -> ReflectionEngine
  -> ReflectionPlan
  -> ReflectionExecutor
  -> ReflectionReport
  -> ReflectionSink
```

Reflection remains deterministic and side-effect free until later execution phases.
