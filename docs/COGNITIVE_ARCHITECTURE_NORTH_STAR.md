# Cognitive Architecture North Star

## Mission

King Synapse is an evidence-grounded cognitive infrastructure for agents. Its long-term objective is not to maximize memory volume or retrieval scores. It is to help an agent transform concrete experiences into scoped, falsifiable, transferable patterns, use those patterns to propose strategies for unseen tasks, and update the patterns from observed outcomes.

```text
Experience
    -> Evidence
    -> Pattern Candidate
    -> Validated Pattern
    -> Strategy Candidate
    -> Transfer
    -> Outcome Feedback
    -> Knowledge Evolution
```

The concise product promise is:

> Let an agent turn past events into experience, experience into patterns, and patterns into strategies for problems it has not encountered before.

## Position of King Recall

King Recall remains a required subsystem, but it is not the final cognitive product.

```text
King Synapse
|
+-- King Recall
|   +-- storage and provenance
|   +-- retrieval
|   +-- memory lifecycle
|   +-- failure and contradiction evidence
|   +-- competition and trace
|   +-- evaluation and shadow experiments
|
+-- Cognitive Learning
    +-- evidence-set formation
    +-- pattern discovery
    +-- pattern validation and falsification
    +-- analogical transfer
    +-- strategy formation
    +-- outcome-driven knowledge evolution
```

Recall answers which existing evidence should be considered. Cognitive learning must answer what generalizable structure can be induced from that evidence, when it applies, when it does not apply, and what new prediction it makes.

## Cognitive artifact ladder

### Experience

A concrete event with source, context, action, observation, and outcome provenance. An experience is evidence; it is not automatically a rule.

### Pattern Candidate

A proposed regularity induced from multiple experiences. It must preserve supporting evidence, counterexample search, applicability conditions, exclusions, predictions, falsification conditions, and confidence. It has no runtime authority.

### Validated Pattern

A Pattern Candidate that survived independent evidence and held-out transfer evaluation. Validation is conditional and scoped; it is not a universal truth claim.

### Strategy Candidate

A task-specific proposal produced by adapting one or more validated patterns to a new context. It remains shadow-only until a separate execution authorization exists.

### Outcome

An observed result from an explicitly authorized experiment. Outcomes may support, challenge, refine, supersede, or reject patterns through a separate evaluation gate.

## Epistemic rules

1. A generated explanation is not evidence.
2. Retrieval count and usage count are not outcome evidence.
3. A Pattern Candidate must cite concrete supporting memories.
4. Counterexample search is mandatory even when no counterexample is found.
5. Applicability and exclusion boundaries must be explicit.
6. A useful pattern must make a testable prediction.
7. A useful pattern must state how it could be falsified.
8. Confidence may change only from new evidence, counterexamples, observed transfer outcomes, or explicit review.
9. No pattern may promote itself because it was generated or repeatedly used.
10. No Phase 7 artifact receives runtime authority by default.

## Pattern lifecycle

```text
Proposed
    -> Supported
    -> Active
    -> Challenged
    -> Refined
    -> Active

Active
    -> Superseded

Proposed
    -> Rejected
```

Every transition requires traceable evidence and an explicit evaluation gate. There are no autonomous promotions in Phase 7.

## Research question

The main Phase 7 research question is:

> Does a structured, evidence-grounded Pattern help an agent solve an unseen target problem better than the base model, raw memory retrieval, or ordinary memory summarization, without increasing harmful negative transfer?

The core comparisons are:

```text
LLM only
Raw memories
Memory summary
Pattern Candidate
Pattern plus counterexamples and scope
```

The central metrics are:

```text
pattern_grounding
abstraction_correctness
scope_precision
counterexample_coverage
transfer_success_rate
negative_transfer_rate
hallucinated_rule_rate
strategy_quality_delta
```

## Non-goals for Phase 7.0

Phase 7.0 does not:

- implement a pattern-discovery algorithm;
- persist Pattern Candidates into the production memory schema;
- build a knowledge graph;
- change RecallEngine or CognitiveBooster;
- connect Hermes;
- execute strategies;
- enable autonomous self-improvement;
- authorize runtime or production claims.

## Current decision

The retrieval-booster research line is preserved as a bounded evidence-selection experiment, but it is no longer the mainline. The mainline is now Experience-to-Pattern-to-Transfer. Phase 7.1 should design an independent transfer benchmark before selecting or implementing a pattern induction algorithm.

## Phase 7.1 protocol status

Phase 7.1 now freezes the first Transfer Evaluation Protocol:

```text
30 scenarios
10 design cases
20 held-out cases
6 transfer categories
6 comparison arms
13 quality and safety metrics
```

The protocol adds explicit measurements for useful transfer, dangerous transfer, withholding accuracy, compression with fidelity, and explanation dependency. This is a benchmark contract only: no Pattern Discovery output has been evaluated and no outcome-performance claim is authorized.

## Phase 7.2 extraction boundary

Phase 7.2 now defines the boundary between Experience evidence and a Pattern Candidate. Extraction inputs exclude target answers and held-out transfer cases. Outputs must remain proposed artifacts with grounded provenance, explicit scope, counterexamples, prediction, falsification, bounded confidence, and no validation outcomes.

This adds an epistemic separation that remains permanent:

```text
Pattern extraction
    != Pattern validation
    != knowledge promotion
    != runtime authority
```

## Phase 7.2.1 executable extraction boundary

Phase 7.2.1 adds the first executable extraction provider without changing the North Star lifecycle. The provider produces only proposed cognition artifacts. Contract acceptance is recorded independently from abstraction-quality diagnostics, and no provider output may become validated knowledge without later evidence and outcome gates.

```text
Experience bundle
  -> deterministic bounded provider
  -> PatternStatus::Proposed
  -> contract accept/reject + explicit diagnostics
  -> no persistence / no runtime
```

The transparent weak baseline is intentionally not described as Pattern Discovery. Its low design-reference alignment is retained as research evidence rather than repaired or hidden.

## Phase 7.2.2 provider reproducibility boundary

The executable extraction boundary now includes a frozen provider-comparison layer:

```text
Experience bundle
  -> frozen provider manifest
  -> frozen prompt / parser / no-repair policy
  -> Pattern Candidate or explicit rejection/blocker
  -> evidence-grounded diagnostics
  -> no automatic knowledge authority
```

Provider identity and experimental configuration are part of the evidence record. A provider that cannot execute is represented as blocked rather than being assigned synthetic scores. Language polish is not a cognitive-quality signal; unsupported claims, evidence attribution, scope, counterexamples, prediction, and falsifiability remain the evaluated properties.
