# King Recall Roadmap

Current milestone

鉁?Phase 1 鈥?Capture Engine
鉁?Phase 2 鈥?Recall Platform (Recall API Freeze)
鉁?Phase 3 鈥?Memory Evolution Contract (Architecture Freeze)
鉁?P4.1 鈥?Adaptive Memory Foundation (Execution Model Freeze)
鉁?P4.2 鈥?Reflection Processing (Contract Freeze)
鉁?P4.3 鈥?Hebbian Execution (Contract Freeze)
鉁?P4.4 鈥?Store Integration (Contract Freeze)
鉁?P4.5 鈥?Adaptive Policies (Contract Freeze)
鉁?v0.5.0 鈥?Architecture Freeze (Public API + SemVer Policy)
鉁?v0.5.1 鈥?Memory Importance Skeleton
鉁?v0.5.2 鈥?Memory Event Kernel + AlgorithmContext Closure
鉁?v0.5.3 鈥?Benchmark Harness Contract Freeze
鉁?v0.5.9 鈥?Adaptive Common Model Freeze (RFC-011 Implemented)
鉁?v0.6.3 鈥?Reflection Yield Benchmark (RFC-012 benchmark milestone)
鉁?v0.6.4 鈥?Reflection Processing Adapter
鉁?v0.6.5 鈥?Reflection Store Mutation Plan
鉁?v0.6.6 鈥?Rule-Based Reflection Algorithm
鉁?v0.7.0 鈥?Merge Algorithm Skeleton
鉁?v0.7.1 鈥?NoOp Merge Algorithm
鉁?v0.7.2 鈥?Rule-Based Merge Algorithm
鉁?v0.7.3 鈥?Merge Precision Benchmark
鉁?v0.7.4 鈥?Merge Store Adapter
鉁?v0.8.0 鈥?Forget Algorithm Skeleton
鉁?v0.8.1 鈥?NoOp Forget Algorithm
鉁?v0.8.2 鈥?Rule-Based Forget Algorithm
鉁?v0.8.3 鈥?Forget Precision Benchmark
鉁?v0.8.4 鈥?Forget Store Adapter
鉁?v0.9.0 鈥?Hebbian Algorithm Skeleton
鉁?v0.9.1 鈥?NoOp Hebbian Algorithm
鉁?v0.9.2 鈥?Rule-Based Hebbian Algorithm
鉁?v0.9.3 鈥?Hebbian Consistency Benchmark
鉁?v0.9.4 鈥?Hebbian Store Adapter
鉁?v0.9.5 鈥?SQLite Edge Persistence
鉁?v0.9.6 鈥?Graph Activation Booster
鉁?v0.9.7 鈥?Decayed Multi-Step Hidden Activation
鉁?v0.9.8 鈥?Edge Inspection Surface
鉁?v0.9.9 鈥?Latent Activation Probe
鉁?v0.9.10 鈥?Context-Modulated Latent Activation
鉁?v0.9.11 鈥?Query-Seeded Latent Activation
鉁?v0.9.12 鈥?Auto-Derived Latent Context
鉁?v0.9.18 鈥?Cognitive Trace Probe
鉁?v0.9.19 鈥?Trace Reinforcement Surface
鉁?v0.9.20 鈥?Trace Reinforcement Benchmark
鉁?v0.9.21 鈥?Activation Parameter Sweep
鉁?v0.9.22 鈥?Long-Horizon Cognitive Memory Benchmark
鉁?v0.9.23 鈥?Manual Validation Transcript
鉁?v0.9.24 鈥?Cognitive Network Algorithm Model
鉁?v0.9.25 鈥?Predictive Trace Continuation
鉁?v0.9.26 鈥?Exported Cognitive Session Benchmark
鉁?v0.9.26-rc 鈥?Cognitive Memory Release Candidate Evidence
鉁?v0.9.26-gate 鈥?Full Cognitive Memory Gate Validation
鉁?v0.9.26-freeze 鈥?Cognitive Memory Freeze

Status

Architecture: **Stable**

Adaptive Common Model: **Frozen**

Algorithm: **Frozen**

Current focus

Phase 2: Adaptive Cognitive Architecture.

Status: **Memory lifecycle freeze**.

Goals:

- adaptive influence
- temporal reasoning
- memory competition
- suppression

Phase 2 starts from [RFC-013 Adaptive Memory Dynamics](rfc/RFC-013-adaptive-memory-dynamics.md).
The goal is to design adaptive memory dynamics after Phase 1 and Phase 1.2
showed that the remaining bottleneck is memory influence regulation rather than
retrieval.

Phase 2.10 freezes the memory lifecycle research surface:
[Phase 2 Memory Lifecycle Final Report](eval/PHASE2_MEMORY_LIFECYCLE_FINAL_REPORT.md),
[Phase 2 Capability Boundary](eval/PHASE2_CAPABILITY_BOUNDARY.md), and
[Phase 3 Reflection Research Questions](eval/PHASE3_REFLECTION_RESEARCH_QUESTIONS.md).
The next research focus is Phase 3.0 Reflection Learning design: how experience
becomes reusable strategy.

Phase 3.0: Reflection Learning.

Status: **Design phase**.

Design RFC: [RFC-014 Reflection Learning](rfc/RFC-014-reflection-learning.md).

Evaluation design:
[Phase 3.0.1 Reflection Learning Evaluation Design](eval/PHASE3_REFLECTION_EVALUATION_DESIGN.md).

Focus:

- identify experiences worth reflection
- separate facts from lessons
- define playbook candidate formation
- connect reflected strategy back into memory competition
- measure learning as grounded future influence change, not lesson text generation

Phase 3.1: Reflection Observation.

Status: **Observation-only prototype**.

Report: `crates/eval/reports/phase3-reflection-observation.json`.

Boundary:

- generates reflection traces
- does not persist lessons
- does not create playbooks
- does not modify future influence

Phase 3.2: Lesson Candidate Evaluation.

Status: **Evaluation-only gate**.

Report: `crates/eval/reports/phase3-lesson-candidate-eval.json`.

Boundary:

- evaluates lesson candidates from reflection traces
- can return `AcceptCandidate`, `ObserveMore`, or `RejectCandidate`
- does not persist lessons
- does not create playbooks
- does not modify future influence

Phase 3.3: Controlled Lesson Promotion.

Status: **Evaluation-only promotion gate**.

Report: `crates/eval/reports/phase3-lesson-promotion.json`.

Boundary:

- promotes accepted lesson candidates only as report states
- can return `ProposedLesson`, `PlaybookCandidate`, or `NotPromoted`
- `PlaybookCandidate` is report-only and does not create a playbook
- does not write memory
- does not modify future influence

Phase 3.4: Future Influence Experiment.

Status: **Evaluation-only influence experiment**.

Report: `crates/eval/reports/phase3-future-influence.json`.

Boundary:

- compares baseline decisions with promoted-lesson-influenced decisions
- tests helpful, irrelevant, and outdated lesson scenarios
- does not write memory
- does not create playbooks
- does not modify runtime future influence

Phase 3.5: Lesson Lifecycle Evaluation.

Status: **Evaluation-only lifecycle simulation**.

Report: `crates/eval/reports/phase3-lesson-lifecycle.json`.

Boundary:

- observes lesson state transitions from `Candidate` through `Superseded`
- tests reinforcement, contradiction response, supersession, and false lesson protection
- does not persist lessons
- does not create playbooks
- does not modify runtime future influence

Phase 3.6: Final Freeze Report.

Status: **Frozen**.

Report: [Phase 3 Final Freeze Report](eval/PHASE3_FINAL_REPORT.md).

Boundary:

- Phase 3 completed and frozen
- documents experience-learning evaluation capabilities
- no new algorithms
- no core changes
- no memory mutation
- next research entry is Phase 4 Adaptive Cognition

Phase 4.1: Cognitive Influence Evaluation.

Status: **Evaluation-only influence ranking**.

Report: `crates/eval/reports/phase4-cognitive-influence.json`.

Boundary:

- ranks `Memory`, `Lesson`, and `PlaybookCandidate` inputs under the same context
- uses configurable eval-only influence weights
- outputs winning candidate, suppressed candidates, and score breakdown
- does not change core
- does not write memory
- does not change runtime influence

Phase 4.2: Cognitive Competition Model.

Status: **Evaluation-only competition simulation**.

Report: `crates/eval/reports/phase4-cognitive-competition.json`.

Boundary:

- simulates activation update, lateral inhibition, and dominant-candidate convergence
- preserves active and suppressed candidates in the trace
- records confidence gaps, activation paths, and suppression reasons
- does not replace graph or latent activation runtime
- does not write memory
- does not change runtime activation

Phase 4.3: Contextual Cognitive Weighting.

Status: **Evaluation-only contextual weighting**.

Report: `crates/eval/reports/phase4-contextual-weighting.json`.

Boundary:

- adjusts candidate influence in simulation from task, environment, constraints, temporal confidence, and reliability
- compares the same candidate across different contexts and resolves context-dependent conflicts
- records weight breakdown, final influence, and explanation trace
- does not change core
- does not write memory
- does not change runtime weighting or production ranking

Phase 4.4: Contextual Competition Integration Evaluation.

Status: **Evaluation-only context-driven competition**.

Report: `crates/eval/reports/phase4_contextual_competition_integration.json`.

Boundary:

- keeps the candidate pool fixed while changing only evaluation context
- applies context-weight profiles before deterministic competition ranking
- records dominant and suppressed candidates for each context case
- measures context flip rate, dominance consistency, suppression correctness, and ranking stability
- does not change core
- does not write memory
- does not change runtime weighting, activation, recall, or production ranking

Phase 4.5: Cognitive Competition Stability Evaluation.

Status: **Evaluation-only stability validation**.

Report: `crates/eval/reports/phase4_cognitive_competition_stability.json`.

Boundary:

- validates deterministic dominance over 100 repeated runs
- validates resistance to minor context noise in safety-critical competition
- validates evidence-driven transition from old dominant candidate to new evidence
- records oscillation rate and confirms no `A -> B -> A` instability
- does not change core
- does not write memory
- does not change runtime weighting, activation, recall, or production ranking

Phase 4 Cognitive Competition: **Complete and frozen**.

Final report: [Phase 4 Final Report](eval/PHASE4_FINAL_REPORT.md).

Validated chain:

```text
Memory Candidates
  -> Competition
  -> Contextual Weighting
  -> Dominant Candidate Emergence
  -> Stable Cognitive State
  -> Evidence Driven Transition
```

Next research entry: Phase 5 Algorithm Engineering.

Phase 2.4: Temporal Memory Dynamics.

Status: **Design**.

Design plan: [Phase 2.4 Temporal Memory Dynamics Plan](eval/PHASE2_4_TEMPORAL_MEMORY_PLAN.md).

Focus:

- how new evidence modifies the influence of old memories
- how historically valid memories become less influential
- how temporal transitions affect future decisions
- how to distinguish old-but-still-valid memories from outdated memories

Phase 6 - Full System Evaluation. Feature growth is frozen by default while the
system is validated for stability, consistency, and comparative value. See
`docs/eval/SYSTEM_VALIDATION_PLAN.md`.

Phase 5 shifts from shared-contract work to independent algorithm work. RFC-011 (Adaptive Common Model) is now frozen. RFC-012 through RFC-015 (Reflection, Merge, Forget, Hebbian) consume RFC-011 as read-only ground truth and MUST NOT extend it. Algorithm RFCs are also independent of one another 鈥?each depends only on RFC-011.

Phase 2 concluded with `v0.2.0-recall-api-freeze`. The Recall contract is now considered stable. Future work extends the platform rather than redesigning it.

Phase 3 concluded with `v0.3.9-memory-evolution-freeze`. The Memory Evolution contract layer is now considered stable. Future work should extend these interfaces instead of changing them.

P4.1 concluded with `v0.4.9-adaptive-memory-foundation`. The Adaptive Memory execution model is now considered stable. Future behavior modules should reuse the Plan -> Execute -> Report -> Sink shape.

P4.2 concluded with `v0.4.19-reflection-processing-freeze`. Reflection Processing is now contract-frozen and remains deterministic and side-effect free.

P4.3 concluded with `v0.4.29-hebbian-execution-freeze`. Hebbian Execution is now contract-frozen and remains deterministic and side-effect free.

P4.4 concluded with `v0.4.39-store-integration-freeze`. Store Integration is now contract-frozen and defines the canonical persistence boundary for Phase 4 behavior modules.

P4.5 concluded with `v0.4.49-adaptive-policies-freeze`. Adaptive Policies is now contract-frozen. Phase 4 is complete.

v0.5.0 concluded with `v0.5.0-architecture-freeze`. The whole-project public API is now stable under the compatibility policy in `docs/COMPATIBILITY.md`. Development mode shifts from **Contract-first** to **Algorithm-first**.

v0.5.9 concluded with `v0.5.9-adaptive-common-freeze`. RFC-011 is Implemented. The Adaptive Common Model (Importance, Event, Event Stream, Context, Metric, Report) is now frozen. Every subsequent algorithm RFC (RFC-012..015) depends only on RFC-011.

## Phase 5 鈥?Algorithm Implementation

Goal

Turn the frozen contracts into concrete adaptive behavior without changing any stable API.

Phase 5.0: Algorithm Integration Design.

Status: **Design-only entry point**.

Design: [Phase 5 Algorithm Integration Design](PHASE5_ALGORITHM_DESIGN.md).

Boundary:

- translates the Phase 4 cognitive competition proof into an engineering plan
- starts with inspection-only trace integration, not runtime ranking mutation
- allows only later default-off bounded booster experiments
- rejects initial RRF rewrites, reranker replacement, candidate expansion, schema changes, and default-on behavior
- requires A/B recall, MRR, latency, trace-quality, and regression gates before any production decision

Phase 5.1: Cognitive Competition Trace Integration.

Status: **Inspection-only integration complete**.

Report: `crates/eval/reports/phase5_cognitive_trace.json`.

Boundary:

- adds `CognitiveTraceEvaluator` under `crates/core/src/adaptive/cognitive_trace`
- evaluates already-returned `RecallHit` candidates into dominant, suppressed, factor, and confidence trace fields
- exposes `kr recall "query" --trace` as an explanatory surface
- does not change recall output, ranking, scores, activation, memory schema, or memory writes
- keeps the cognitive trace score explanation-only and separate from production ranking

Validated metrics:

- `trace_generation_rate = 1.0000`
- `dominant_validity = 1.0000`
- `factor_explanation_rate = 1.0000`
- `trace_determinism = 1.0000`
- `recall_regression = 0.0000`

Phase 5.2: Cognitive Trace Quality Evaluation.

Status: **Frozen - local deterministic quality gate complete; external judge pending**.

Documentation: [Phase 5.2 Cognitive Trace Quality Evaluation](eval/PHASE5_2_TRACE_QUALITY_EVALUATION.md).

Report: `crates/eval/reports/phase5_trace_quality.json`.

Freeze boundary:

- evaluates real `RecallHit` candidates against baseline retrieval metadata
- records dominant, suppressed, factor attribution, confidence, and deterministic pairwise-rubric evidence
- independently audits factor source faithfulness and reports zero hallucinated or missing factors
- keeps recall ranking, scores, activation, memory storage, schema, and runtime behavior unchanged
- freezes the local deterministic proof while leaving blinded human/LLM judging explicitly open
- does not authorize a booster, production reranking, or any default-on cognitive behavior

Validated metrics:

- `explanation_completeness = 1.0000`
- `factor_faithfulness = 1.0000`
- `trace_preference_rate = 1.0000` under `deterministic_pairwise_explanation_rubric_v1`
- `determinism = 1.0000`
- `explanation_information_gain = +0.6000`
- `retrieval_trace_alignment = 0.8333` as a diagnostic only

Freeze decision:

- local status is `PASS_LOCAL_DETERMINISTIC_QUALITY_GATE`
- `human_or_llm_judge_completed = false`; no external preference claim is made
- Phase 5.3 may begin only as an OFF-by-default bounded booster prototype with baseline/A/B comparison and rollback

Phase 5.3.1: Bounded Cognitive Booster Interface.

Status: **Frozen interface; runtime integration not started**.

Documentation: [Phase 5.3.1 Bounded Cognitive Booster Interface](PHASE5_3_1_BOUNDED_COGNITIVE_BOOSTER_INTERFACE.md) and [Phase 5.3.1 Freeze](eval/PHASE5_3_1_FREEZE.md).

Boundary:

- adds an experimental `CognitiveBooster` contract separate from mutable runtime `RecallBooster` implementations
- accepts immutable `RecallHit` candidates, `CognitiveCompetitionTrace`, and validated default-off configuration
- emits serializable shadow proposals with a `0.10` absolute bonus cap and configured candidate-prefix limit
- reconstructs baseline ranks and scores from immutable input and ignores unknown or ineligible candidate proposals
- keeps `runtime_applied = false`, `memory_mutated = false`, and leaves `RecallEngine` registration absent
- does not change ranking, scores, `activation_bonus`, memory, working memory, storage schema, or baseline recall output

Validation:

- dedicated interface tests cover default-off configuration, bounded deserialization, candidate limits, score capping, proposal filtering, deterministic no-op behavior, immutable recall signatures, and stable safety serialization
- no Recall@K, MRR, latency, regression, human-preference, or runtime-improvement claim is made
- Phase 5.3.2 is limited to a shadow ranking experiment that preserves baseline output

Phase 5.3.2: Deterministic Cognitive Booster v0 Shadow Ranking Experiment.

Status: **Frozen; runtime authorization withheld**.

Documentation: [Phase 5.3.2 Shadow Ranking Experiment](eval/PHASE5_3_2_SHADOW_RANKING_EXPERIMENT.md).

Report: `crates/eval/reports/phase5_shadow_ranking.json`.

Boundary:

- adds `DeterministicCognitiveBoosterV0` over immutable candidates and the real cognitive trace
- excludes semantic match from the bonus so the experiment measures additional cognitive factors
- creates a copied shadow order from `baseline_score + bounded_bonus` without sorting or mutating `RecallHit`
- preserves the candidate pool and uses baseline rank as the deterministic tie-breaker
- keeps baseline recall authoritative and leaves runtime registration absent
- does not write memory, change activation, change schema, or authorize production behavior

Local shadow metrics:

- `proposal_coverage = 1.0000`
- `changed_positions = 13`
- `avg_abs_rank_delta = 0.9474`
- `max_abs_rank_delta = 3`
- `max_proposed_bonus = 0.0848`
- `bounded_rate = 1.0000`
- `determinism = 1.0000`
- `shadow_recall_delta = +0.0000` at Recall@3
- `shadow_mrr_delta = -0.1250`

Decision:

- the shadow mechanism and safety gate pass
- v0 does not establish positive ranking value on the local fixture; MRR regresses
- runtime integration remains unauthorized
- any Phase 5.3.3 work must remain shadow-only and study bounded ranking authority rather than merely increasing bonus strength

Phase 5.3.3: Cognitive Ranking Policy Study.

Status: **Frozen as controlled, evaluation-only policy evidence; runtime unauthorized**.

Documentation: [Phase 5.3.3 Cognitive Ranking Policy Study](eval/PHASE5_3_3_COGNITIVE_RANKING_POLICY_STUDY.md).

Report: `crates/eval/reports/phase5_cognitive_policy.json`.

Scope and result:

- adds 42 deterministic scenarios covering temporal updates, failure override, reliability conflict, semantic traps, preference evolution, contradiction, and no-intervention cases
- compares Absolute Bonus, normalized Weighted Fusion at `alpha = 0.05/0.10/0.20`, and Margin Guard at normalized threshold `0.08`
- adds intervention precision/recall, unnecessary intervention, catastrophic regression, MRR/Recall@3, rank movement, boundedness, and determinism metrics
- runs real-trace ablations for temporal, reliability, failure, preference, and context factors
- keeps baseline authoritative, runtime application disabled, candidate pools immutable, and memory/schema/activation unchanged
- local controlled evidence favors Margin Guard, while positive production retrieval value remains unproven

Phase 5.3.4: Generalization Validation.

Status: **Frozen as controlled held-out evidence; runtime unauthorized**.

Documentation: [Phase 5.3.4 Generalization Validation](eval/PHASE5_3_4_GENERALIZATION_VALIDATION.md).

Report: `crates/eval/reports/phase5_cognitive_generalization.json`.

Scope and result:

- locks the Phase 5.3.3 Margin Guard parameters at normalized threshold `0.08` and cognitive `alpha = 0.20` before held-out execution
- freezes disjoint `30/12/21` train, validation, and held-out controlled test splits with SHA-256 dataset seals
- compares pure retrieval, confidence-only fusion, recency-only fusion, and the locked Margin Guard policy
- records held-out Margin Guard MRR `0.9524`, intervention precision `1.0000`, intervention recall `0.8824`, unnecessary intervention `0.0000`, and catastrophic regression `0.0000`
- evaluates seven factor interactions; full cognitive performs best, while failure plus temporal retains most of the measured value
- keeps runtime, storage, activation, candidate pools, and authoritative baseline behavior unchanged

Decision boundary:

- controlled policy generalization is locally supported
- end-to-end retrieval generalization, latency, user-distribution value, and production benefit remain unproven
- require an independent ground-truth end-to-end retrieval benchmark before any runtime A/B authorization
- do not register a cognitive booster with `RecallEngine` or change runtime defaults

Phase 5.3 freeze: [Cognitive Ranking Policy Freeze](eval/PHASE5_3_FREEZE.md).

Phase 5.4: Independent End-to-End Cognitive Validation.

Status: **Local implementation, deterministic protocol gate, and shadow evaluation complete; independent cognitive value not established**.

Documentation: [Phase 5.4 Independent End-to-End Cognitive Validation](eval/PHASE5_4_INDEPENDENT_END_TO_END_COGNITIVE_VALIDATION.md).

Report: `crates/eval/reports/phase5_end_to_end_cognitive.json`.

Scope and result:

- builds 24 scenarios / 144 memories through real isolated `Store` writes
- obtains the complete candidate pool, baseline order, and baseline scores from `RecallEngine::recall_profiled`; the workload contains no manual `baseline_score`
- compares retrieval, confidence-only, recency-only, failure-only, and locked Margin Guard Cognitive policies under the same `alpha = 0.20` / threshold `0.08` authority envelope
- records expected-candidate retrieval rate `1.0000`, Recall@3 `1.0000` for all policies, and zero top-1 or catastrophic regressions
- records retrieval MRR@5 `0.6667`, confidence `0.7500`, recency `0.8333`, failure `0.8333`, and cognitive `0.8333`
- verifies identical scenario label rankings and metrics across five fresh Store runs after removing entity-branch tie sensitivity from the workload vocabulary
- preserves Store, `RecallHit`, candidate pool, runtime ranking, activation, schema, and default recall behavior

Decision boundary:

- the real-score end-to-end protocol and safety gate pass
- the full cognitive policy improves the retrieval baseline but ties the strongest simple recency/failure controls
- `independent_end_to_end_value_supported = false`
- `runtime_authorization = false`
- require independently authored or external retrieval workloads, ideally with vector/reranker coverage and conflicting factor cases, before reconsidering runtime A/B

Phase 6.0: Memory Intelligence Benchmark.

Status: **Benchmark foundation complete; algorithm comparison and runtime authorization remain out of scope**.

Documentation: [Phase 6.0 Memory Intelligence Benchmark](eval/PHASE6_0_MEMORY_INTELLIGENCE_BENCHMARK.md).

Report: `crates/eval/reports/phase6_memory_intelligence_benchmark.json`.

Scope and result:

- freezes 320 repository-authored deterministic Agent-memory scenarios / 1,920 memories across 10 categories and a fixed 160/80/80 split
- writes memories through isolated real Stores and obtains top-5 ranking and scores from `RecallEngine::recall_profiled`; no artificial `baseline_score` is present
- records 224 intervention-required and 96 no-intervention cases after aligning labels with actual baseline confidence/importance/temporal semantics
- records expected-candidate retrieval `1.0000`, Recall@1 `0.3000`, Recall@3/5 `1.0000`, MRR@5 `0.6500`, NDCG@5 `0.7417`, determinism `1.0000`, and Store unchanged `1.0000`
- keeps vectors and reranking disabled for this frozen lane; the entity branch is enabled but produces zero entity candidates
- performs no cognitive, recency, failure, confidence, graph, or other algorithm comparison

Decision boundary:

- `PASS` means benchmark integrity, real-score provenance, expected-candidate reachability, determinism, and safety pass
- this is a synthetic repository-authored workload, not independent real-user or external-distribution validation
- `independent_cognitive_value_claimed = false`
- `runtime_authorization = false`
- Phase 6.1 may compare cognitive and simple baselines without changing the frozen candidate pool or runtime path
Phase 6.1: Cognitive vs Simple Baseline Evaluation.

Status: **Comparison implementation and local quality gate complete; independent attribution unresolved; no Hermes/runtime authorization**.

Documentation: [Phase 6.1 Cognitive vs Simple Baseline Evaluation](eval/PHASE6_1_COGNITIVE_BASELINE_COMPARISON.md).

Report: `crates/eval/reports/phase6_cognitive_baseline_comparison.json`.

Scope and result:

- compares retrieval, confidence-only, recency-only, failure-only, simple-combined, and unchanged Margin-Guard Cognitive policies over the frozen 320-scenario workload
- fixes `alpha = 0.20` and `threshold = 0.08`; no post-result tuning or Cognitive algorithm change is permitted
- runs full Cognitive plus temporal/failure/reliability/preference/context single-factor removals through the unchanged booster
- all policies record Recall@1 `0.3000`, Recall@3 `1.0000`, MRR@5 `0.6500`, and NDCG@5 `0.7417`; Cognitive gain versus the best simple baseline is `0.0000`
- the minimum normalized top-to-second gap is `0.101449`, so the locked `0.08` Margin Guard admits no two-candidate competitions and every policy preserves baseline order

Decision boundary:

- classify the observed metric result as case B (`Cognitive = simple baseline`) without claiming that Cognitive is merely metadata aggregation
- `attribution_resolved = false` and `zero_intervention_authority = true`; factor contribution cannot be inferred from the zero-authority operating point
- Hermes Shadow Integration is not recommended
- `runtime_authorization = false` and `production_claim_authorized = false`

Completed foundations

- v0.5.1 鈥?Memory Importance skeleton (10 tests)
- v0.5.2 鈥?Memory Event kernel + AlgorithmContext closure (20 new tests)
- v0.5.3 鈥?Benchmark harness contract (AlgorithmMetric, BenchmarkReport)
- v0.5.9 鈥?Adaptive Common Model freeze (RFC-011 Implemented)
- v0.6.3 鈥?Reflection yield benchmark (`BenchmarkReport` mapped to `ReflectionYield`)
- v0.6.4 鈥?Reflection output maps into existing Reflection Processing events
- v0.6.5 鈥?Reflection plans map into canonical StoreMutation plans
- v0.6.6 鈥?Reflection switches from deterministic reference to rule-based heuristic
- v0.7.0 鈥?Merge algorithm trait and target/output shape
- v0.7.1 鈥?NoOp merge implementation
- v0.7.2 鈥?Rule-based merge heuristic
- v0.7.3 鈥?Merge precision benchmark (`BenchmarkReport` mapped to `MergePrecision`)
- v0.7.4 鈥?Merge output maps into existing Consolidation and StoreMutation plans
- v0.8.0 鈥?Forget algorithm trait and target/output shape
- v0.8.1 鈥?NoOp forget implementation
- v0.8.2 鈥?Rule-based forget heuristic
- v0.8.3 鈥?Forget precision benchmark (`BenchmarkReport` mapped to `ForgetPrecision`)
- v0.8.4 鈥?Forget output maps into existing StoreMutation plans
- v0.9.0 鈥?Hebbian algorithm trait and target/output shape
- v0.9.1 鈥?NoOp hebbian implementation
- v0.9.2 鈥?Rule-based hebbian heuristic
- v0.9.3 鈥?Hebbian consistency benchmark (`BenchmarkReport` mapped to `HebbianConsistency`)
- v0.9.4 鈥?Hebbian edge plans map into existing StoreMutation plans
- v0.9.5 鈥?`StoreMutation::UpdateEdge` persists directed edge weights in SQLite
- v0.9.6 鈥?persisted edge weights add recall-time activation through `GraphActivationBooster`
- v0.9.7 鈥?graph activation supports capped, decayed multi-step hidden influence inside the candidate pool
- v0.9.8 鈥?persisted associative edges are inspectable through Store, CLI, and MCP surfaces
- v0.9.9 鈥?latent activation can be probed from seed memories without changing recall candidates or rankings
- v0.9.10 鈥?latent activation can be modulated by explicit state and goal terms while preserving path explanations
- v0.9.11 鈥?natural-language queries can recall visible seed memories and inspect their hidden activation paths as a separate report
- v0.9.12 鈥?query text can derive state and goal terms for latent inspection while keeping recall ranking unchanged
- v0.9.13 鈥?Chinese cognitive-chain benchmark covers visible seed recall into hidden latent influence
- v0.9.14 鈥?optional latent activation booster can add hidden-path bonus to existing recall candidates
- v0.9.15 鈥?deterministic CJK query expansion raises `multihop` Recall@10 to 1.000
- v0.9.16 鈥?CLI and MCP can reinforce co-occurring memories through the Hebbian -> StoreMutation -> SQLite path
- v0.9.17 鈥?recall surfaces can optionally reinforce top-hit co-occurrence after returning results
- v0.9.18 鈥?cognitive trace reports combine visible recall, latent activation, and context into dominant and suppressed candidates
- v0.9.19 鈥?trace surfaces can optionally reinforce visible seeds to the dominant hidden influence after reporting
- v0.9.20 鈥?trace reinforcement benchmark verifies dominant hidden influence can be learned into persisted edges
- v0.9.21 鈥?activation parameter sweep verifies latent, trace, and trace-learning guarantees across multiple settings
- v0.9.22 鈥?long-horizon cognitive-memory benchmark verifies multi-day traces in one shared memory store
- v0.9.23 鈥?manual validation transcript covers normal and empty/error cognitive-memory surfaces
- v0.9.24 鈥?cognitive network algorithm model maps human-network design into visible seeds, latent activation, dominant/suppressed candidates, and post-trace learning
- v0.9.25 鈥?predictive trace continues from the dominant candidate into ranked next hidden influences
- v0.9.26 鈥?exported cognitive-session TOML benchmark verifies visible recall, dominant hidden influence, predictive future continuation, and trace learning in one shared graph
- v0.9.26-rc 鈥?release-candidate note records cognitive-memory validation evidence and remaining final tag work
- v0.9.26-gate 鈥?full final acceptance command list passed and is recorded in the release validation note
- v0.9.26-freeze 鈥?RFC-012 through RFC-015 are freeze-reviewed by the cognitive-memory release note

Focus

- Freeze feature growth unless validation finds a bug or a reproducibility gap.
- Keep internal deterministic gates passing before interpreting external results.
- Finish Letta configuration and keep unsupported surfaces explicit.
- Add LongMemEval/DMR fetch instructions only after license and cache rules are clear.
- Re-run Graphiti and Mem0 in hosted/official modes when credentials are available.

Rules

1. Phase 5 must not change any Stable API. All work plugs in behind existing traits.
2. Frozen benchmark baselines (`reference` `Recall@10 = 1.000`, `multihop` `Recall@10 = 1.000` after ADR-006) must be preserved or explicitly renegotiated through ADR.
3. Every concrete algorithm ships with a benchmark run demonstrating baseline preservation and target-metric improvement.
4. Algorithm parameters are internal by default; promotion to Stable API requires an ADR.
5. Post-freeze rules of RFC-011 apply: uniform call shape `fn method(&self, target, ctx)`, no new top-level shared types under `adaptive/`, algorithm RFCs are independent of one another, `AlgorithmContext` never owns data, benchmarks use only public API, renaming a frozen type is breaking.

## Phase 3 Contract

> **Phase 3 must not modify the Recall contract unless an ADR explicitly approves the change.**

Rules

1. `RecallHit` schema remains frozen.
2. `RecallBoosters` are the only extension point for recall scoring.
3. Every recall-related behavior change must preserve or improve benchmark results.

## Phase 3 鈥?Memory Evolution

Status

Architecture Complete / Contract Frozen

Goal

Enable memories to evolve over time without changing the Recall Platform.

Frozen layers

- Working Memory Buffer
- Activation Booster
- Consolidation Plan
- Reflection Event
- Hebbian Reinforcement Skeleton

Contract tags

```text
v0.3.0  Working Memory Skeleton
v0.3.2  Working Memory Activation
v0.3.3  Consolidation Planning
v0.3.4  Reflection Event
v0.3.5  Hebbian Reinforcement Skeleton
v0.3.9  Memory Evolution Contract Freeze
```

## Phase 4 鈥?Adaptive Memory

Goal

Turn the frozen memory-evolution contracts into adaptive behavior while preserving the Recall and Memory Evolution contracts.

Status: **Complete**. All P4.1鈥揚4.5 milestones are contract-frozen. See the Phase 5 section above for the current focus.

Completed foundation

```text
P4.1 Consolidation Executor
  -> ConsolidationPlan
  -> ConsolidationExecutor
  -> ExecutionReport
  -> ConsolidationSink
```

Completed behavior contracts

```text
P4.2 Reflection Processing
  -> ReflectionEngine
  -> ReflectionPlan
  -> ReflectionExecutor
  -> ReflectionReport
  -> ReflectionSink

P4.3 Hebbian Execution
  -> EdgeUpdatePlan
  -> HebbianExecutor
  -> HebbianExecutionReport
  -> HebbianSink

P4.4 Store Integration
  -> StoreMutation
  -> StoreMutationDispatcher
  -> StoreMutationPlan
  -> StoreAdapter / PersistentStoreExecutor
  -> StoreExecutionReport
  -> StoreSink

P4.5 Adaptive Policies
  -> PolicyRequest
  -> AdaptivePolicyEngine
  -> PolicyReport
  -> PolicySink
```

Contract rules

1. Do not change Phase 2 Recall contracts without ADR approval.
2. Do not change Phase 3 Memory Evolution contracts without ADR approval.
3. Prefer strategy implementations over interface changes.
4. Preserve `reference` and `multihop` benchmark baselines before merging behavior changes.
5. Start each Phase 4 implementation from an RFC.

RFC sequence

```text
RFC-006 Consolidation Execution
  -> RFC-007 Reflection Processing
  -> RFC-008 Hebbian Execution
  -> RFC-009 Store Integration
  -> RFC-010 Adaptive Policies
```

## Completed Milestones

v0.2.0-recall-api-freeze

Highlights

鈥?RecallEngine
鈥?Hybrid Retrieval (RRF)
鈥?Pluggable Reranker
鈥?Explainable Recall
鈥?RecallHit Contract
鈥?RecallBooster Extension Point
鈥?Evaluation Harness

v0.3.9-memory-evolution-freeze

Highlights

鈥?WorkingMemoryBuffer
鈥?WorkingMemoryActivationBooster
鈥?ConsolidationPlan
鈥?ReflectionEvent
鈥?HebbianReinforcementEngine
鈥?Memory Evolution Contract

v0.4.9-adaptive-memory-foundation

Highlights

鈥?ConsolidationExecutor
鈥?ExecutionReport
鈥?ConsolidationSink
鈥?NoOpSink
鈥?Plan -> Execute -> Report -> Sink model

v0.4.19-reflection-processing-freeze

Highlights

鈥?ReflectionEngine
鈥?ReflectionPlan
鈥?ReflectionExecutor
鈥?ReflectionReport
鈥?ReflectionSink
鈥?NoOpReflectionSink

v0.4.29-hebbian-execution-freeze

Highlights

鈥?EdgeUpdatePlan
鈥?HebbianExecutor
鈥?HebbianExecutionReport
鈥?HebbianSink
鈥?NoOpHebbianSink

v0.4.39-store-integration-freeze

Highlights

鈥?StoreMutation
鈥?StoreMutationPlan
鈥?StoreMutationDispatcher
鈥?StoreAdapter
鈥?StoreExecutionReport
鈥?StoreSink
鈥?PersistentStoreExecutor
鈥?SQLitePersistentStoreExecutor

v0.4.49-adaptive-policies-freeze

Highlights

鈥?PolicyDecision
鈥?AdaptivePolicy
鈥?ReflectionPolicy / HebbianPolicy / ForgetPolicy / MergePolicy
鈥?PolicyRequest / PolicyReport
鈥?AdaptivePolicyEngine
鈥?DeterministicAdaptivePolicyEngine
鈥?PolicySink
鈥?NoOpPolicySink

v0.5.0-architecture-freeze

Highlights

鈥?Whole-project public API declared stable
鈥?`docs/API_SURFACE.md` (Stable / Experimental / Internal)
鈥?`docs/COMPATIBILITY.md` (SemVer, breaking-change rules, deprecation policy)
鈥?`docs/COGNITIVE_MEMORY_FINAL_ACCEPTANCE.md` (final cognitive-memory gates)
鈥?Final Architecture Rules (Trait 鈫?NoOp 鈫?Dispatcher 鈫?Report 鈫?Sink)
鈥?Layer direction (Policy 鈫?Execution 鈫?Storage)
鈥?Subsystem stack (Recall 鈫?Working Memory 鈫?Adaptive Memory 鈫?Store)
鈥?Development mode: Contract-first 鈫?Algorithm-first


## Phase 6.2 Recall Score Distribution Study

Status: **local implementation and deterministic quality gate complete; descriptive baseline only.**

Phase 6.2 was introduced after Phase 6.1 showed zero Margin Guard authority. It reuses the frozen 320-query real-RecallEngine workload and measures candidate counts, raw scores, adjacent gaps, top-relative gaps, percentiles, and fixed-threshold coverage without modifying retrieval or executing Cognitive ranking.

Observed operating point:

```text
minimum Top1-Top2 normalized gap = 0.101449
locked threshold                 = 0.080000
locked eligible scenarios        = 0 / 320
threshold 0.15 coverage          = 192 / 320 (descriptive only)
threshold 0.20 coverage          = 192 / 320 (descriptive only)
```

Decision boundary:

```text
score-distribution baseline established   yes
threshold selected                         no
Margin Guard redesigned                    no
Cognitive value evaluated                  no
Hermes Shadow Integration                  not recommended
runtime authorization                      false
```

Any later authority-policy experiment must be separately specified and pre-register its desired coverage before validation. Phase 6.2 results must not be used as an in-place threshold tuning loop.

## Phase 7.0 Cognitive Architecture Reorientation

Status: **contract implementation complete; Experience-to-Pattern becomes the research mainline; no Pattern algorithm or runtime authority.**

Phase 7.0 preserves King Recall as the evidence substrate and redirects the main research question from score intervention to knowledge formation and transfer:

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

The eval-only `PatternCandidate` contract requires multiple supporting memories, provenance, counterexample search, applicability conditions, source domains, predictions, falsification conditions, bounded confidence, and validation outcomes before non-proposed lifecycle states. All lifecycle transitions require explicit evaluation and none are autonomous.

Decision boundary:

```text
retrieval booster mainline                 stopped
Experience-to-Pattern mainline             authorized
Pattern discovery algorithm                not authorized
Pattern persistence                        not authorized
Knowledge Graph                            not authorized
autonomous self-improvement                not authorized
Hermes                                     not authorized
runtime                                    not authorized
```

Next: Phase 7.1 must design a held-out Transfer Benchmark comparing LLM-only, raw-memory, memory-summary, Pattern, and Pattern-with-counterexamples conditions. It must measure negative transfer before implementing an autonomous induction algorithm.

## Phase 7.1 Transfer Evaluation Protocol

Status: **protocol implementation complete; transfer outcome evaluation pending; Pattern algorithm and runtime remain unauthorized.**

Phase 7.1 freezes a 30-scenario benchmark with `10` design and `20` held-out cases across direct transfer, cross-domain transfer, negative transfer, scope boundaries, counterexample-sensitive decisions, and no-transfer controls.

The comparison protocol contains six arms:

```text
LLM only
raw memories
memory summary
Pattern Candidate
Pattern + scope + counterexamples
Pattern + evidence graph
```

The protocol measures grounding, abstraction correctness, scope precision, counterexample coverage, useful transfer, withholding accuracy, negative and dangerous transfer, hallucinated rules, strategy quality, compression, and explanation dependency. It explicitly records `outcome_evaluation_complete=false`: Phase 7.1 freezes the test standard but does not claim model or Pattern performance.

Decision boundary:

```text
Transfer dataset                         frozen
held-out transfer cases                  reserved
baseline comparison protocol             complete
Pattern Discovery                        not authorized
Pattern persistence                      not authorized
Hermes                                   not authorized
runtime                                  not authorized
```

Next: implement a bounded Pattern Discovery prototype against the `design` split only, freeze its prompts and rules, and only then open the held-out split for transfer evaluation.

## Phase 7.2 Evidence-Grounded Pattern Extraction Protocol

Status: **protocol complete; extraction algorithm and model evaluation remain unimplemented.**

Phase 7.2 adds a design-only extraction view over the ten Phase 7.1 design cases. Extractor inputs contain concrete experiences, outcomes, constraints, and supplied counterexamples but exclude target problems, expected transfer answers, runtime state, and every held-out case.

The eval-only output contract requires one `Proposed` Pattern Candidate with grounded evidence IDs, exact provenance, explicit scope, supplied counterexamples, prediction, falsification, empty validation outcomes, and confidence no greater than `0.75`.

Decision boundary:

```text
extraction protocol                 frozen
design fixtures                     frozen
held-out transfer cases             untouched
extraction provider                 not implemented
model evaluation                    not completed
Pattern persistence                 not authorized
Hermes                              not authorized
runtime                             not authorized
```

Next: Phase 7.2.1 may implement one bounded extraction provider against the ten design inputs only. Provider prompts and repair rules must be frozen before held-out evaluation.

## Phase 7.2.1: Bounded Pattern Extraction Provider

Status: frozen design evaluation.

The first executable provider is `deterministic_bounded_pattern_extractor_v0`, a transparent deterministic weak baseline over the ten design cases. Provider configuration, candidate limit, confidence cap, and reject-only output policy are frozen. Contract-valid outputs receive only `accepted_contract_only`.

Current result:

```text
10 provider executions
10 structurally accepted candidates
9 cases with quality diagnostics
6/6 injected invalid outputs rejected
0 held-out cases opened
0 persistence/runtime authority
```

Next gate: freeze and compare a stronger or model-backed provider on the same design cases. Do not open held-out transfer cases until provider/model/prompt/decoding/repair policy and quality scoring are frozen.

## Product Line: Hermes Agent Host A0/A1

Status: **A0 Rust Runtime Shadow and MCP tool complete; A1 isolated Hermes host complete; write authority remains closed.**

The product line is now separate from the historical Phase 7 research gates.
King Synapse owns the Canonical Packet, governance decisions, Runtime Trace,
and all memory authority. Hermes Agent 0.18.2 is a replaceable host that calls
the local stdio MCP server and presents the result to a user.

```text
Canonical Packet
    -> Rust Runtime Shadow
    -> read-only MCP profile
    -> Hermes Agent tool loop
    -> answer + Evidence + Guards + Trace
```

The A1 integration is pinned under `%LOCALAPPDATA%\king-synapse` and uses a
separate `kingsynapse` Hermes Profile. The server-side `agent_read_only` policy
exposes only `synapse_recall`, `synapse_trace`, and
`synapse_enterprise_shadow`; all direct write/reinforce/forget calls are
rejected. The frozen 20-case suite is exercised through the actual MCP stdio
binary, and two live Agent conversations cover one confirmed answer and one
withheld suspended statistic.

Next product gate: a small controlled user pilot. Do not add web/browser tools,
observation intake, autonomous learning, or durable writes until Agent traces
show that the host preserves the Runtime decisions over repeated use.

## Phase 7.2.2 Frozen Provider Capability Matrix

Status: **protocol frozen; weak baseline complete; model-backed execution blocked by authorization.**

Frozen components:

```text
PatternExtractorPrompt-v1
strict single-object JSON parser
reject-only/no-repair policy
evidence-grounded scorer
provider manifest and artifact hashes
10 design cases only
```

Current result:

```text
deterministic weak baseline  completed 10/10
DeepSeek provider            blocked_authorization 0/10
held-out cases               untouched
runtime / persistence        unauthorized
```

No LLM extraction-quality or transfer-value claim is permitted until authorization is valid and the frozen design comparison completes. The next action is to repair provider credentials or select a separately manifested model provider without changing the frozen prompt/parser/scorer after seeing held-out data.
