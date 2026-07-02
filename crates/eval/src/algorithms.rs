use crate::{AlgorithmMetric, BenchmarkReport};
use serde::Deserialize;
use std::collections::BTreeMap;
use synapse_core::{
    AlgorithmContext, CognitiveTraceConfig, CognitiveTraceProbe, CognitiveTraceReport,
    DeterministicHebbianStoreMutationDispatcher, DeterministicReflectionAlgorithm, ForgetAlgorithm,
    ForgetOutput, ForgetTarget, HebbianAlgorithm, HebbianExecutor, HebbianOutput, HebbianTarget,
    InMemoryMemoryEventStream, LatentActivationContext, LatentActivationProbe, Memory, MemoryEvent,
    MemoryEventId, MemoryEventKind, MemoryEventPayload, MemoryEventStream, MemoryKind,
    MergeAlgorithm, MergeOutput, MergeTarget, PersistentStoreExecutor, PlanOnlyHebbianExecutor,
    QueryLatentActivationProbe, RecallQuery, ReflectionAlgorithm, ReflectionOutput,
    RuleBasedForgetAlgorithm, RuleBasedHebbianAlgorithm, RuleBasedMergeAlgorithm,
    RuleBasedReflectionAlgorithm, SQLitePersistentStoreExecutor, Scope, Source, Store,
    StoreMutationDispatcher, UniformImportanceEstimator, WriteInput,
};

const REFLECTION_BENCHMARK_NAME: &str = "reflection-yield";
const DETERMINISTIC_REFLECTION_BENCHMARK_NAME: &str = "reflection-yield-deterministic";
const COGNITIVE_CHAIN_BENCHMARK_NAME: &str = "cognitive-chain-recall";
const COGNITIVE_TRACE_BENCHMARK_NAME: &str = "cognitive-trace-dominance";
const TRACE_REINFORCEMENT_BENCHMARK_NAME: &str = "trace-reinforcement";
const PREDICTIVE_TRACE_BENCHMARK_NAME: &str = "predictive-trace";
const ACTIVATION_PARAMETER_SWEEP_BENCHMARK_NAME: &str = "activation-parameter-sweep";
const LONG_HORIZON_COGNITIVE_BENCHMARK_NAME: &str = "long-horizon-cognitive-memory";
const EXPORTED_COGNITIVE_SESSION_BENCHMARK_NAME: &str = "exported-cognitive-session";
const EXPANDED_COGNITIVE_REPLAY_BENCHMARK_NAME: &str = "expanded-cognitive-replay";
const MERGE_BENCHMARK_NAME: &str = "merge-precision";
const FORGET_BENCHMARK_NAME: &str = "forget-precision";
const HEBBIAN_BENCHMARK_NAME: &str = "hebbian-consistency";
const EXPORTED_COGNITIVE_SESSION_DATASET: &str =
    include_str!("../datasets/exported_cognitive_session.toml");
const EXPANDED_COGNITIVE_REPLAY_DATASET: &str =
    include_str!("../datasets/regression/expanded_cognitive_replay.toml");

/// Run the current RFC-012 Reflection benchmark.
///
/// `ReflectionYield` is the fraction of structurally eligible memories that
/// produce reflection work. As of v0.6.6, the public report uses the
/// rule-based Reflection algorithm rather than the deterministic reference.
pub fn reflection_yield_report() -> BenchmarkReport {
    reflection_yield_report_for(
        REFLECTION_BENCHMARK_NAME,
        &RuleBasedReflectionAlgorithm::default(),
    )
}

/// Run the RFC-012 deterministic reference benchmark for comparison.
pub fn deterministic_reflection_yield_report() -> BenchmarkReport {
    reflection_yield_report_for(
        DETERMINISTIC_REFLECTION_BENCHMARK_NAME,
        &DeterministicReflectionAlgorithm::default(),
    )
}

/// Run the cognitive-chain latent recall benchmark.
///
/// This benchmark models the user's core design idea: visible text can surface
/// a seed memory, then auto-derived state/goal context should activate a hidden
/// connected memory that represents subconscious or downstream influence.
pub fn cognitive_chain_recall_report() -> BenchmarkReport {
    let cases = cognitive_chain_fixture();
    let hits = cases
        .iter()
        .filter(|case| cognitive_chain_case_hits(case))
        .count();
    let recall = if cases.is_empty() {
        0.0
    } else {
        hits as f64 / cases.len() as f64
    };

    BenchmarkReport {
        benchmark: COGNITIVE_CHAIN_BENCHMARK_NAME.to_string(),
        metrics: BTreeMap::from([(AlgorithmMetric::RecallAt10, recall)]),
    }
}

/// Run the cognitive trace dominance benchmark.
///
/// This benchmark checks the stronger trace contract: after visible recall
/// finds seed memories, the cognitive trace report should identify the
/// expected hidden/downstream influence as the dominant candidate rather than
/// merely listing it somewhere in latent activations.
pub fn cognitive_trace_dominance_report() -> BenchmarkReport {
    let cases = cognitive_trace_fixture();
    let hits = cases
        .iter()
        .filter(|case| cognitive_trace_case_hits(case))
        .count();
    let dominance = if cases.is_empty() {
        0.0
    } else {
        hits as f64 / cases.len() as f64
    };

    BenchmarkReport {
        benchmark: COGNITIVE_TRACE_BENCHMARK_NAME.to_string(),
        metrics: BTreeMap::from([(AlgorithmMetric::CognitiveTraceDominance, dominance)]),
    }
}

/// Run the trace reinforcement benchmark.
///
/// This benchmark checks the learning half of the cognitive trace path. After
/// a trace identifies the expected hidden/downstream influence, reinforcement
/// should persist directed associative edges between the visible seed memories
/// and that hidden influence through the Hebbian -> StoreMutation -> SQLite
/// path. It reuses existing metrics rather than adding a new frozen API item:
/// `CognitiveTraceDominance` checks that the trace chose the right hidden
/// candidate, while `HebbianConsistency` checks that the expected directed
/// edges gained weight after reinforcement.
pub fn trace_reinforcement_report() -> BenchmarkReport {
    let cases = cognitive_trace_fixture();
    let outcomes = cases
        .iter()
        .map(trace_reinforcement_case_outcome)
        .collect::<Vec<_>>();
    let dominance_hits = outcomes
        .iter()
        .filter(|outcome| outcome.dominant_hit)
        .count();
    let expected_edges = outcomes
        .iter()
        .map(|outcome| outcome.expected_edges)
        .sum::<usize>();
    let reinforced_edges = outcomes
        .iter()
        .map(|outcome| outcome.reinforced_edges)
        .sum::<usize>();

    let dominance = if outcomes.is_empty() {
        0.0
    } else {
        dominance_hits as f64 / outcomes.len() as f64
    };
    let consistency = if expected_edges == 0 {
        0.0
    } else {
        reinforced_edges as f64 / expected_edges as f64
    };

    BenchmarkReport {
        benchmark: TRACE_REINFORCEMENT_BENCHMARK_NAME.to_string(),
        metrics: BTreeMap::from([
            (AlgorithmMetric::CognitiveTraceDominance, dominance),
            (AlgorithmMetric::HebbianConsistency, consistency),
        ]),
    }
}

/// Run the predictive trace benchmark.
///
/// This benchmark checks the "future pull" side of the cognitive model. A
/// trace first selects the expected hidden/downstream influence as dominant,
/// then prediction continues from that dominant candidate along outgoing
/// associative edges. `RecallAt10` measures whether the expected next hidden
/// influence appears in the continuation candidates.
pub fn predictive_trace_report() -> BenchmarkReport {
    let cases = predictive_trace_fixture();
    let hits = cases
        .iter()
        .filter(|case| predictive_trace_case_hits(case))
        .count();

    BenchmarkReport {
        benchmark: PREDICTIVE_TRACE_BENCHMARK_NAME.to_string(),
        metrics: BTreeMap::from([(AlgorithmMetric::RecallAt10, ratio(hits, cases.len()))]),
    }
}

/// Run a deterministic parameter sweep over cognitive activation settings.
///
/// This is a final-acceptance benchmark rather than a new algorithm metric. It
/// reuses existing metric IDs and reports the fraction of swept configurations
/// that preserve each cognitive-memory guarantee:
///
/// - `RecallAt10`: query -> visible seed -> latent hidden influence.
/// - `CognitiveTraceDominance`: visible + latent context -> dominant hidden
///   influence.
/// - `HebbianConsistency`: post-trace reinforcement persists the expected
///   visible <-> hidden edges.
pub fn activation_parameter_sweep_report() -> BenchmarkReport {
    let chain_configs = latent_sweep_configs();
    let trace_configs = trace_sweep_configs();
    let reinforcement_configs = trace_sweep_configs();

    let chain_hits = chain_configs
        .iter()
        .filter(|config| cognitive_chain_sweep_hits(config))
        .count();
    let trace_hits = trace_configs
        .iter()
        .filter(|config| cognitive_trace_sweep_hits(config))
        .count();
    let reinforcement_hits = reinforcement_configs
        .iter()
        .filter(|config| trace_reinforcement_sweep_hits(config))
        .count();

    BenchmarkReport {
        benchmark: ACTIVATION_PARAMETER_SWEEP_BENCHMARK_NAME.to_string(),
        metrics: BTreeMap::from([
            (
                AlgorithmMetric::RecallAt10,
                ratio(chain_hits, chain_configs.len()),
            ),
            (
                AlgorithmMetric::CognitiveTraceDominance,
                ratio(trace_hits, trace_configs.len()),
            ),
            (
                AlgorithmMetric::HebbianConsistency,
                ratio(reinforcement_hits, reinforcement_configs.len()),
            ),
        ]),
    }
}

/// Run the long-horizon cognitive-memory benchmark.
///
/// This benchmark simulates one longer memory store rather than one isolated
/// case at a time. It writes multiple day-stamped memory chains with visible
/// distractors, hidden influences, and hidden distractors, then verifies that
/// final queries still recall the correct visible seed, trace the expected
/// hidden influence, and learn the expected post-trace edges.
pub fn long_horizon_cognitive_memory_report() -> BenchmarkReport {
    let cases = long_horizon_fixture();
    let (mut store, ids) = seed_long_horizon_store(&cases);

    let mut recall_hits = 0usize;
    let mut trace_hits = 0usize;
    let mut expected_edges = 0usize;
    let mut reinforced_edges = 0usize;

    for case in &cases {
        let case_ids = ids
            .get(case.label)
            .expect("long horizon case ids should be seeded");
        let visible_recall = long_horizon_visible_recall_hits(&mut store, case, &case_ids.seed);
        if visible_recall {
            recall_hits += 1;
        }

        let report = long_horizon_trace_report(&mut store, case);
        if trace_report_dominates_hidden(&report, &case_ids.hidden) {
            trace_hits += 1;
        }

        let visible_ids = trace_visible_seed_ids(&report, 3);
        let expected = visible_hidden_edges(&visible_ids, &case_ids.hidden);
        let before = edge_weights(&mut store, &expected);
        if let Some(dominant) = report.dominant.as_ref() {
            let ids = trace_reinforcement_ids(&report, 3, &dominant.memory.id);
            reinforce_trace_ids(&mut store, ids, case.query);
        }
        let after = edge_weights(&mut store, &expected);
        expected_edges += expected.len();
        reinforced_edges += expected
            .iter()
            .filter(|edge| edge_gained_weight(*before.get(*edge).unwrap_or(&0.0), after[*edge]))
            .count();
    }

    BenchmarkReport {
        benchmark: LONG_HORIZON_COGNITIVE_BENCHMARK_NAME.to_string(),
        metrics: BTreeMap::from([
            (AlgorithmMetric::RecallAt10, ratio(recall_hits, cases.len())),
            (
                AlgorithmMetric::CognitiveTraceDominance,
                ratio(trace_hits, cases.len()),
            ),
            (
                AlgorithmMetric::HebbianConsistency,
                ratio(reinforced_edges, expected_edges),
            ),
        ]),
    }
}

/// Run the exported cognitive-session benchmark.
///
/// Unlike the inline deterministic fixtures, this benchmark loads a TOML file
/// that is shaped like a small exported long-session transcript. Each chain
/// verifies visible seed recall, dominant hidden influence, predictive future
/// continuation, and post-trace reinforcement in one shared Store.
pub fn exported_cognitive_session_report() -> BenchmarkReport {
    exported_cognitive_session_report_for(
        EXPORTED_COGNITIVE_SESSION_BENCHMARK_NAME,
        EXPORTED_COGNITIVE_SESSION_DATASET,
    )
}

/// Run the expanded Phase 6 cognitive/prediction replay benchmark.
///
/// This keeps the external-comparison fixture stable while adding a larger
/// golden replay set: 20 cognitive trace checks and 20 prediction checks.
pub fn expanded_cognitive_replay_report() -> BenchmarkReport {
    exported_cognitive_session_report_for(
        EXPANDED_COGNITIVE_REPLAY_BENCHMARK_NAME,
        EXPANDED_COGNITIVE_REPLAY_DATASET,
    )
}

fn exported_cognitive_session_report_for(benchmark_name: &str, dataset: &str) -> BenchmarkReport {
    let session = exported_cognitive_session_fixture(dataset);
    let (mut store, ids) = seed_exported_cognitive_session_store(&session.chains);

    let mut recall_hits = 0usize;
    let mut trace_hits = 0usize;
    let mut prediction_hits = 0usize;
    let mut expected_edges = 0usize;
    let mut reinforced_edges = 0usize;

    for chain in &session.chains {
        let chain_ids = ids
            .get(chain.label.as_str())
            .expect("exported cognitive session ids should be seeded");
        if exported_visible_recall_hits(&mut store, chain, &chain_ids.seed) {
            recall_hits += 1;
        }

        let report = exported_trace_report(&mut store, chain);
        if trace_report_dominates_hidden(&report, &chain_ids.hidden) {
            trace_hits += 1;
        }

        if exported_prediction_hits(&store, chain, &report, &chain_ids.future) {
            prediction_hits += 1;
        }

        let visible_ids = trace_visible_seed_ids(&report, 3);
        let expected = visible_hidden_edges(&visible_ids, &chain_ids.hidden);
        let before = edge_weights(&mut store, &expected);
        if let Some(dominant) = report.dominant.as_ref() {
            let ids = trace_reinforcement_ids(&report, 3, &dominant.memory.id);
            reinforce_trace_ids(&mut store, ids, &chain.query);
        }
        let after = edge_weights(&mut store, &expected);
        expected_edges += expected.len();
        reinforced_edges += expected
            .iter()
            .filter(|edge| edge_gained_weight(*before.get(*edge).unwrap_or(&0.0), after[*edge]))
            .count();
    }

    BenchmarkReport {
        benchmark: benchmark_name.to_string(),
        metrics: BTreeMap::from([
            (
                AlgorithmMetric::RecallAt10,
                ratio(recall_hits + prediction_hits, session.chains.len() * 2),
            ),
            (
                AlgorithmMetric::CognitiveTraceDominance,
                ratio(trace_hits, session.chains.len()),
            ),
            (
                AlgorithmMetric::HebbianConsistency,
                ratio(reinforced_edges, expected_edges),
            ),
        ]),
    }
}

/// Run the RFC-013 rule-based Merge benchmark.
///
/// `MergePrecision` is the fraction of emitted `Merge` decisions that are
/// known true positives in the deterministic fixture. `Candidate` decisions
/// are intentionally not counted as merge predictions.
pub fn merge_precision_report() -> BenchmarkReport {
    let groups = merge_fixture();
    let importance = UniformImportanceEstimator;
    let events = InMemoryMemoryEventStream::with_capacity(16);
    let now = chrono::DateTime::from_timestamp(1_700_000_000, 0)
        .expect("fixed benchmark timestamp must be valid");
    let ctx = AlgorithmContext::new(now, None, &importance, &events);
    let algorithm = RuleBasedMergeAlgorithm::default();

    let mut true_positives = 0usize;
    let mut false_positives = 0usize;

    for (target, expected_merge) in groups {
        let predicted_merge = matches!(algorithm.merge(&target, &ctx), MergeOutput::Merge { .. });
        if predicted_merge && expected_merge {
            true_positives += 1;
        } else if predicted_merge {
            false_positives += 1;
        }
    }

    let predicted_count = true_positives + false_positives;
    let precision = if predicted_count == 0 {
        0.0
    } else {
        true_positives as f64 / predicted_count as f64
    };

    BenchmarkReport {
        benchmark: MERGE_BENCHMARK_NAME.to_string(),
        metrics: BTreeMap::from([(AlgorithmMetric::MergePrecision, precision)]),
    }
}

/// Run the RFC-014 rule-based Forget benchmark.
///
/// `ForgetPrecision` is the fraction of emitted `Forget` decisions that are
/// known true positives in the deterministic fixture. `Candidate` decisions
/// are intentionally not counted as forget predictions.
pub fn forget_precision_report() -> BenchmarkReport {
    let groups = forget_fixture();
    let importance = UniformImportanceEstimator;
    let events = InMemoryMemoryEventStream::with_capacity(16);
    let now = chrono::DateTime::from_timestamp(1_700_000_000, 0)
        .expect("fixed benchmark timestamp must be valid");
    let ctx = AlgorithmContext::new(now, None, &importance, &events);
    let algorithm = RuleBasedForgetAlgorithm::default();

    let mut true_positives = 0usize;
    let mut false_positives = 0usize;

    for (target, expected_forget) in groups {
        let predicted_forget =
            matches!(algorithm.forget(&target, &ctx), ForgetOutput::Forget { .. });
        if predicted_forget && expected_forget {
            true_positives += 1;
        } else if predicted_forget {
            false_positives += 1;
        }
    }

    let predicted_count = true_positives + false_positives;
    let precision = if predicted_count == 0 {
        0.0
    } else {
        true_positives as f64 / predicted_count as f64
    };

    BenchmarkReport {
        benchmark: FORGET_BENCHMARK_NAME.to_string(),
        metrics: BTreeMap::from([(AlgorithmMetric::ForgetPrecision, precision)]),
    }
}

/// Run the RFC-015 rule-based Hebbian benchmark.
///
/// `HebbianConsistency` is the fraction of expected directed edges produced by
/// the deterministic fixture, with false-positive edges penalized.
pub fn hebbian_consistency_report() -> BenchmarkReport {
    let (target, expected_edges) = hebbian_fixture();
    let importance = UniformImportanceEstimator;
    let events = InMemoryMemoryEventStream::with_capacity(16);
    let now = chrono::DateTime::from_timestamp(1_700_000_000, 0)
        .expect("fixed benchmark timestamp must be valid");
    let ctx = AlgorithmContext::new(now, None, &importance, &events);
    let algorithm = RuleBasedHebbianAlgorithm::default();

    let produced_edges = match algorithm.reinforce(&target, &ctx) {
        HebbianOutput::Plans { plans, .. } => plans
            .into_iter()
            .map(|plan| (plan.source, plan.target))
            .collect::<std::collections::BTreeSet<_>>(),
        HebbianOutput::Skipped { .. } => std::collections::BTreeSet::new(),
        _ => std::collections::BTreeSet::new(),
    };
    let expected_edges = expected_edges
        .into_iter()
        .collect::<std::collections::BTreeSet<_>>();
    let true_positives = produced_edges.intersection(&expected_edges).count() as f64;
    let false_positives = produced_edges.difference(&expected_edges).count() as f64;
    let missed = expected_edges.difference(&produced_edges).count() as f64;
    let denominator = true_positives + false_positives + missed;
    let consistency = if denominator == 0.0 {
        0.0
    } else {
        true_positives / denominator
    };

    BenchmarkReport {
        benchmark: HEBBIAN_BENCHMARK_NAME.to_string(),
        metrics: BTreeMap::from([(AlgorithmMetric::HebbianConsistency, consistency)]),
    }
}

fn reflection_yield_report_for(
    benchmark_name: &str,
    algorithm: &dyn ReflectionAlgorithm,
) -> BenchmarkReport {
    let memories = reflection_fixture();
    let eligible_count = memories
        .iter()
        .filter(|memory| is_reflection_eligible(memory))
        .count();

    let importance = UniformImportanceEstimator;
    let events = InMemoryMemoryEventStream::with_capacity(16);
    let now = chrono::DateTime::from_timestamp(1_700_000_000, 0)
        .expect("fixed benchmark timestamp must be valid");

    for memory in &memories {
        if is_reflection_eligible(memory) {
            events.record(MemoryEvent {
                id: MemoryEventId::nil(),
                timestamp: now,
                session_id: None,
                kind: MemoryEventKind::Written,
                memory_ids: vec![memory.id.clone()],
                payload: MemoryEventPayload::Empty,
            });
        }
    }

    let ctx = AlgorithmContext::new(now, None, &importance, &events);
    let produced_count = memories
        .iter()
        .filter(|memory| {
            matches!(
                algorithm.reflect(memory, &ctx),
                ReflectionOutput::Candidate { .. } | ReflectionOutput::Produced { .. }
            )
        })
        .count();

    let yield_value = if eligible_count == 0 {
        0.0
    } else {
        produced_count as f64 / eligible_count as f64
    };

    BenchmarkReport {
        benchmark: benchmark_name.to_string(),
        metrics: BTreeMap::from([(AlgorithmMetric::ReflectionYield, yield_value)]),
    }
}

fn is_reflection_eligible(memory: &Memory) -> bool {
    !memory.content.trim().is_empty() && memory.valid_to.is_none() && memory.superseded_by.is_none()
}

fn reflection_fixture() -> Vec<Memory> {
    let mut superseded = memory("m-superseded", "Old belief superseded by a newer memory.");
    superseded.superseded_by = Some("m-newer".to_string());

    let mut expired = memory("m-expired", "Expired temporary state.");
    expired.valid_to = Some(1);

    vec![
        memory(
            "m-fact",
            "JWT refresh failures should be reflected after repeated 401 fixes.",
        ),
        memory(
            "m-preference",
            "User prefers concise Chinese summaries for project handoffs.",
        ),
        memory(
            "m-playbook",
            "When SQLite FTS misses CJK text, check tokenizer settings first.",
        ),
        memory("m-empty", "   "),
        superseded,
        expired,
    ]
}

struct CognitiveChainCase {
    query: &'static str,
    seed: &'static str,
    hidden: &'static str,
    distractor: &'static str,
}

struct CognitiveTraceCase {
    label: &'static str,
    query: &'static str,
    seed: &'static str,
    visible_distractor: &'static str,
    hidden: &'static str,
    hidden_distractor: &'static str,
    state_terms: &'static [&'static str],
    goal_terms: &'static [&'static str],
}

struct PredictiveTraceCase {
    label: &'static str,
    query: &'static str,
    seed: &'static str,
    visible_distractor: &'static str,
    hidden: &'static str,
    future: &'static str,
    future_distractor: &'static str,
    state_terms: &'static [&'static str],
    goal_terms: &'static [&'static str],
}

struct LongHorizonCase {
    label: &'static str,
    query: &'static str,
    seed: &'static str,
    visible_distractor: &'static str,
    hidden: &'static str,
    hidden_distractor: &'static str,
    state_terms: &'static [&'static str],
    goal_terms: &'static [&'static str],
}

struct LongHorizonIds {
    seed: String,
    hidden: String,
}

#[derive(Debug, Deserialize)]
struct ExportedCognitiveSession {
    chains: Vec<ExportedCognitiveChain>,
}

#[derive(Debug, Deserialize)]
struct ExportedCognitiveChain {
    label: String,
    query: String,
    seed: String,
    visible_distractor: String,
    hidden: String,
    hidden_distractor: String,
    future: String,
    future_distractor: String,
    state_terms: Vec<String>,
    goal_terms: Vec<String>,
}

impl ExportedCognitiveChain {
    fn scope(&self) -> Scope {
        Scope::Session(self.label.clone())
    }
}

struct ExportedCognitiveIds {
    seed: String,
    hidden: String,
    future: String,
}

#[derive(Clone, Copy)]
struct LatentSweepConfig {
    scale: f32,
    cap: f32,
    steps: usize,
    decay: f32,
    fanout: usize,
}

#[derive(Clone, Copy)]
struct TraceSweepConfig {
    latent_scale: f32,
    latent_cap: f32,
    latent_steps: usize,
    latent_decay: f32,
    latent_fanout: usize,
    visible_limit: usize,
    latent_limit: usize,
    seed_limit: usize,
    suppressed_limit: usize,
}

fn cognitive_chain_fixture() -> Vec<CognitiveChainCase> {
    vec![
        CognitiveChainCase {
            query: "早上忘记喝水导致心情不好，上班骑车注意力下降",
            seed: "早上忘记喝水导致心情不好",
            hidden: "上班骑车时注意力下降可能摔倒",
            distractor: "晚上整理书桌和文件夹",
        },
        CognitiveChainCase {
            query: "长期压力让人下意识回避复杂任务，工作目标受到影响",
            seed: "长期压力让人下意识回避复杂任务",
            hidden: "潜意识回避会影响工作目标和错误复盘",
            distractor: "周末可以清理临时下载目录",
        },
        CognitiveChainCase {
            query: "过去失败经验让人担心再次出错，未来注意力会被影响",
            seed: "过去失败经验让人担心再次出错",
            hidden: "记忆会影响未来决策和注意力分配",
            distractor: "午饭后备份照片到移动硬盘",
        },
        CognitiveChainCase {
            query: "object tool use affects work goal emotion decision",
            seed: "object tool use affects work goal",
            hidden: "object tool problem affects emotion decision and attention allocation",
            distractor: "afternoon monitor cable label cleanup",
        },
        CognitiveChainCase {
            query: "social evaluation worry failure complex task avoidance",
            seed: "social evaluation worry failure",
            hidden:
                "social pressure failure memory triggers subconscious avoidance for complex task",
            distractor: "meeting room air conditioner booking record",
        },
        CognitiveChainCase {
            query: "past error review future prediction risk",
            seed: "past error review insufficient",
            hidden: "memory review affects future prediction and error risk",
            distractor: "wednesday reimbursement form printing",
        },
        CognitiveChainCase {
            query: "hungry tired work attention allocation",
            seed: "hungry tired work attention dropped",
            hidden: "body state affects work goal and attention allocation",
            distractor: "evening music playlist sync",
        },
    ]
}

fn cognitive_trace_fixture() -> Vec<CognitiveTraceCase> {
    vec![
        CognitiveTraceCase {
            label: "body-state-to-commute-attention",
            query: "forgot water before commute",
            seed: "forgot morning water before commute",
            visible_distractor: "forgot water calendar note",
            hidden: "tired attention failure",
            hidden_distractor: "calendar archive cleanup",
            state_terms: &["tired"],
            goal_terms: &["attention"],
        },
        CognitiveTraceCase {
            label: "social-pressure-to-work-goal",
            query: "pressure before difficult task",
            seed: "pressure before difficult task can trigger avoidance",
            visible_distractor: "pressure report for office schedule",
            hidden: "subconscious avoidance affects goal and review quality",
            hidden_distractor: "office plant watering schedule",
            state_terms: &["subconscious"],
            goal_terms: &["goal"],
        },
        CognitiveTraceCase {
            label: "past-failure-to-future-decision",
            query: "past failure repeating mistakes",
            seed: "past failure makes a person worried about repeating mistakes",
            visible_distractor: "past failure incident index",
            hidden: "memory affects future decision attention allocation",
            hidden_distractor: "photo backup reminder",
            state_terms: &["memory"],
            goal_terms: &["future", "attention"],
        },
        CognitiveTraceCase {
            label: "object-usage-to-task-risk",
            query: "phone charger before meeting",
            seed: "phone charger was left at home before meeting",
            visible_distractor: "phone charger shopping note",
            hidden: "tool missing creates task risk and anxious planning",
            hidden_distractor: "meeting room projector inventory",
            state_terms: &["anxious"],
            goal_terms: &["task"],
        },
        CognitiveTraceCase {
            label: "renxing-social-memory-to-emotion",
            query: "renxing social trust memory",
            seed: "renxing social trust memory from last collaboration",
            visible_distractor: "social trust reading list",
            hidden: "emotion affects communication decision and work attention",
            hidden_distractor: "collaboration lunch receipt",
            state_terms: &["emotion"],
            goal_terms: &["decision", "work"],
        },
        CognitiveTraceCase {
            label: "subconscious-avoidance-to-error-review",
            query: "complex review after repeated bug",
            seed: "complex review after repeated bug can trigger avoidance",
            visible_distractor: "complex review checklist title",
            hidden: "subconscious avoidance can create error in future judgement",
            hidden_distractor: "bug label color preference",
            state_terms: &["subconscious"],
            goal_terms: &["future", "error"],
        },
    ]
}

fn predictive_trace_fixture() -> Vec<PredictiveTraceCase> {
    vec![
        PredictiveTraceCase {
            label: "hydration-to-commute-risk",
            query: "forgot water before commute",
            seed: "forgot morning water before commute",
            visible_distractor: "forgot water calendar note",
            hidden: "tired attention failure",
            future: "future commute attention risk",
            future_distractor: "calendar archive cleanup",
            state_terms: &["future"],
            goal_terms: &["commute", "attention"],
        },
        PredictiveTraceCase {
            label: "avoidance-to-review-error",
            query: "pressure before difficult task",
            seed: "pressure before difficult task can trigger avoidance",
            visible_distractor: "pressure report for office schedule",
            hidden: "subconscious avoidance affects future error review quality",
            future: "future error detection gets weaker during review",
            future_distractor: "office plant watering schedule",
            state_terms: &["future"],
            goal_terms: &["error", "review"],
        },
        PredictiveTraceCase {
            label: "past-failure-to-decision-risk",
            query: "past failure repeating mistakes",
            seed: "past failure makes repeated mistake fear salient",
            visible_distractor: "past failure incident index",
            hidden: "memory affects future decision attention allocation",
            future: "future decision risk increases when attention narrows",
            future_distractor: "photo backup reminder",
            state_terms: &["future"],
            goal_terms: &["decision", "attention"],
        },
    ]
}

fn long_horizon_fixture() -> Vec<LongHorizonCase> {
    vec![
        LongHorizonCase {
            label: "day01-hydration-commute",
            query: "day01 hydration skipped scooter commute",
            seed: "day01 hydration skipped before scooter commute caused low mood",
            visible_distractor: "day01 hydration reminder template for weekend chores",
            hidden: "tired mood reduces commute attention and raises scooter fall risk",
            hidden_distractor: "weekend chore list includes laundry and receipts",
            state_terms: &["tired", "mood"],
            goal_terms: &["commute", "attention"],
        },
        LongHorizonCase {
            label: "day02-pressure-review",
            query: "day02 pressure architecture review avoidance",
            seed: "day02 team pressure before architecture review triggered avoidance",
            visible_distractor: "day02 pressure gauge reading for office equipment",
            hidden: "subconscious avoidance reduces review quality and future error detection",
            hidden_distractor: "office equipment calibration note for facilities",
            state_terms: &["subconscious"],
            goal_terms: &["review", "future", "error"],
        },
        LongHorizonCase {
            label: "day03-charger-demo",
            query: "day03 laptop charger missing client demo",
            seed: "day03 laptop charger was missing before client demo",
            visible_distractor: "day03 laptop charger shopping comparison",
            hidden: "anxious planning from missing tool creates task failure risk",
            hidden_distractor: "client demo slide color palette archive",
            state_terms: &["anxious"],
            goal_terms: &["task", "risk"],
        },
        LongHorizonCase {
            label: "day04-past-bug",
            query: "day04 past payment bug repeating mistakes",
            seed: "day04 past payment bug made repeated mistake fear salient",
            visible_distractor: "day04 payment receipt export folder",
            hidden: "memory of failure changes future decision attention allocation",
            hidden_distractor: "receipt export naming preference",
            state_terms: &["memory"],
            goal_terms: &["future", "attention"],
        },
        LongHorizonCase {
            label: "day05-trust-message",
            query: "day05 trust message collaboration communication",
            seed: "day05 trust message from collaboration changed communication tone",
            visible_distractor: "day05 collaboration lunch receipt",
            hidden: "emotion affects communication decision and work attention",
            hidden_distractor: "lunch receipt reimbursement checklist",
            state_terms: &["emotion"],
            goal_terms: &["decision", "work"],
        },
        LongHorizonCase {
            label: "day06-hunger-incident",
            query: "day06 hunger incident deployment focus",
            seed: "day06 hunger during deployment caused impatient focus",
            visible_distractor: "day06 deployment snack inventory",
            hidden: "hungry state narrows attention and increases operational mistake risk",
            hidden_distractor: "snack inventory sorted by shelf location",
            state_terms: &["hungry"],
            goal_terms: &["attention", "risk"],
        },
        LongHorizonCase {
            label: "day07-social-feedback",
            query: "day07 social feedback concise chinese handoff",
            seed: "day07 social feedback reinforced concise chinese handoff preference",
            visible_distractor: "day07 social reading note about language history",
            hidden: "preference memory guides communication decision and reduces review friction",
            hidden_distractor: "language history bibliography for later reading",
            state_terms: &["memory"],
            goal_terms: &["communication", "review"],
        },
        LongHorizonCase {
            label: "day08-complex-review",
            query: "day08 complex review repeated bug avoidance",
            seed: "day08 complex review after repeated bug triggered avoidance",
            visible_distractor: "day08 complex review checklist title draft",
            hidden: "subconscious avoidance can create future judgement error",
            hidden_distractor: "checklist title draft typography options",
            state_terms: &["subconscious"],
            goal_terms: &["future", "error"],
        },
    ]
}

fn latent_sweep_configs() -> Vec<LatentSweepConfig> {
    vec![
        LatentSweepConfig {
            scale: 0.025,
            cap: 0.12,
            steps: 1,
            decay: 0.35,
            fanout: 4,
        },
        LatentSweepConfig {
            scale: 0.04,
            cap: 0.20,
            steps: 1,
            decay: 0.5,
            fanout: 8,
        },
        LatentSweepConfig {
            scale: 0.05,
            cap: 0.25,
            steps: 2,
            decay: 0.5,
            fanout: 10,
        },
        LatentSweepConfig {
            scale: 0.08,
            cap: 0.30,
            steps: 3,
            decay: 0.7,
            fanout: 16,
        },
        LatentSweepConfig {
            scale: 0.06,
            cap: 0.35,
            steps: 4,
            decay: 0.75,
            fanout: 20,
        },
        LatentSweepConfig {
            scale: 0.10,
            cap: 0.45,
            steps: 3,
            decay: 0.85,
            fanout: 24,
        },
    ]
}

fn trace_sweep_configs() -> Vec<TraceSweepConfig> {
    vec![
        TraceSweepConfig {
            latent_scale: 0.025,
            latent_cap: 0.12,
            latent_steps: 1,
            latent_decay: 0.35,
            latent_fanout: 4,
            visible_limit: 2,
            latent_limit: 4,
            seed_limit: 2,
            suppressed_limit: 4,
        },
        TraceSweepConfig {
            latent_scale: 0.04,
            latent_cap: 0.20,
            latent_steps: 1,
            latent_decay: 0.5,
            latent_fanout: 8,
            visible_limit: 2,
            latent_limit: 4,
            seed_limit: 2,
            suppressed_limit: 4,
        },
        TraceSweepConfig {
            latent_scale: 0.05,
            latent_cap: 0.25,
            latent_steps: 2,
            latent_decay: 0.5,
            latent_fanout: 10,
            visible_limit: 2,
            latent_limit: 4,
            seed_limit: 2,
            suppressed_limit: 4,
        },
        TraceSweepConfig {
            latent_scale: 0.08,
            latent_cap: 0.30,
            latent_steps: 3,
            latent_decay: 0.7,
            latent_fanout: 16,
            visible_limit: 2,
            latent_limit: 6,
            seed_limit: 2,
            suppressed_limit: 5,
        },
        TraceSweepConfig {
            latent_scale: 0.06,
            latent_cap: 0.35,
            latent_steps: 4,
            latent_decay: 0.75,
            latent_fanout: 20,
            visible_limit: 4,
            latent_limit: 8,
            seed_limit: 3,
            suppressed_limit: 8,
        },
        TraceSweepConfig {
            latent_scale: 0.10,
            latent_cap: 0.45,
            latent_steps: 3,
            latent_decay: 0.85,
            latent_fanout: 24,
            visible_limit: 4,
            latent_limit: 8,
            seed_limit: 3,
            suppressed_limit: 8,
        },
    ]
}

fn cognitive_chain_case_hits(case: &CognitiveChainCase) -> bool {
    cognitive_chain_case_hits_with_config(
        case,
        &LatentSweepConfig {
            scale: 0.05,
            cap: 0.25,
            steps: 2,
            decay: 0.5,
            fanout: 10,
        },
    )
}

fn cognitive_chain_sweep_hits(config: &LatentSweepConfig) -> bool {
    let cases = cognitive_chain_fixture();
    cases
        .iter()
        .all(|case| cognitive_chain_case_hits_with_config(case, config))
}

fn cognitive_chain_case_hits_with_config(
    case: &CognitiveChainCase,
    config: &LatentSweepConfig,
) -> bool {
    let mut store = Store::open_in_memory().expect("cognitive benchmark store opens");
    let seed = write_cognitive_memory(&mut store, case.seed, MemoryKind::State, 0.8);
    let hidden = write_cognitive_memory(&mut store, case.hidden, MemoryKind::Playbook, 0.8);
    let distractor = write_cognitive_memory(&mut store, case.distractor, MemoryKind::Fact, 0.5);
    store
        .update_edge(&seed, &hidden, 2.0)
        .expect("cognitive target edge is persisted");
    store
        .update_edge(&seed, &distractor, 2.0)
        .expect("cognitive distractor edge is persisted");

    let query = RecallQuery {
        query: case.query.to_string(),
        k: None,
        scope_filter: None,
        kind_filter: Some(MemoryKind::State),
    };
    let probe = QueryLatentActivationProbe::new(
        LatentActivationProbe::with_config(
            config.scale,
            config.cap,
            config.steps,
            config.decay,
            config.fanout,
        ),
        1,
    );
    let report = probe
        .probe_auto_context(&mut store, &query, 10, &LatentActivationContext::default())
        .expect("cognitive latent probe runs");

    report
        .activations
        .iter()
        .any(|hit| hit.memory.id == hidden && !hit.matched_terms.is_empty())
}

fn cognitive_trace_case_hits(case: &CognitiveTraceCase) -> bool {
    assert!(
        !case.label.trim().is_empty(),
        "cognitive trace case label must describe the chain"
    );
    let (mut store, hidden) = seed_cognitive_trace_store(case);
    let report = cognitive_trace_case_report(&mut store, case, default_trace_sweep_config());

    trace_report_dominates_hidden(&report, &hidden)
}

fn cognitive_trace_sweep_hits(config: &TraceSweepConfig) -> bool {
    let cases = cognitive_trace_fixture();
    cases.iter().all(|case| {
        let (mut store, hidden) = seed_cognitive_trace_store(case);
        let report = cognitive_trace_case_report(&mut store, case, *config);
        trace_report_dominates_hidden(&report, &hidden)
    })
}

fn predictive_trace_case_hits(case: &PredictiveTraceCase) -> bool {
    assert!(
        !case.label.trim().is_empty(),
        "predictive trace case label must describe the chain"
    );
    let (mut store, hidden, future) = seed_predictive_trace_store(case);
    let trace_case = CognitiveTraceCase {
        label: case.label,
        query: case.query,
        seed: case.seed,
        visible_distractor: case.visible_distractor,
        hidden: case.hidden,
        hidden_distractor: case.future_distractor,
        state_terms: case.state_terms,
        goal_terms: case.goal_terms,
    };
    let config = default_trace_sweep_config();
    let report = cognitive_trace_case_report(&mut store, &trace_case, config);
    if !trace_report_dominates_hidden(&report, &hidden) {
        return false;
    }

    let probe = CognitiveTraceProbe::new(CognitiveTraceConfig {
        visible_limit: config.visible_limit,
        latent_limit: config.latent_limit,
        seed_limit: config.seed_limit,
        suppressed_limit: config.suppressed_limit,
        latent_scale: config.latent_scale,
        latent_cap: config.latent_cap,
        latent_steps: config.latent_steps,
        latent_decay: config.latent_decay,
        latent_fanout: config.latent_fanout,
    });
    let prediction = probe
        .predict_continuation(&store, &report, 10)
        .expect("predictive trace continuation runs");

    prediction
        .candidates
        .iter()
        .any(|hit| hit.memory.id == future && !hit.matched_terms.is_empty())
}

struct TraceReinforcementOutcome {
    dominant_hit: bool,
    expected_edges: usize,
    reinforced_edges: usize,
}

fn trace_reinforcement_case_outcome(case: &CognitiveTraceCase) -> TraceReinforcementOutcome {
    trace_reinforcement_case_outcome_with_config(case, default_trace_sweep_config())
}

fn trace_reinforcement_sweep_hits(config: &TraceSweepConfig) -> bool {
    let cases = cognitive_trace_fixture();
    cases.iter().all(|case| {
        let outcome = trace_reinforcement_case_outcome_with_config(case, *config);
        outcome.dominant_hit && outcome.expected_edges == outcome.reinforced_edges
    })
}

fn trace_reinforcement_case_outcome_with_config(
    case: &CognitiveTraceCase,
    config: TraceSweepConfig,
) -> TraceReinforcementOutcome {
    let (mut store, hidden) = seed_cognitive_trace_store(case);
    let report = cognitive_trace_case_report(&mut store, case, config);
    let dominant_hit = trace_report_dominates_hidden(&report, &hidden);
    let visible_ids = trace_visible_seed_ids(&report, config.seed_limit);
    let expected_edges = visible_hidden_edges(&visible_ids, &hidden);
    let before = edge_weights(&mut store, &expected_edges);

    if let Some(dominant) = report.dominant.as_ref() {
        let ids = trace_reinforcement_ids(&report, config.seed_limit, &dominant.memory.id);
        reinforce_trace_ids(&mut store, ids, case.query);
    }

    let after = edge_weights(&mut store, &expected_edges);
    let reinforced_edges = expected_edges
        .iter()
        .filter(|edge| edge_gained_weight(*before.get(*edge).unwrap_or(&0.0), after[edge]))
        .count();

    TraceReinforcementOutcome {
        dominant_hit,
        expected_edges: expected_edges.len(),
        reinforced_edges,
    }
}

fn default_trace_sweep_config() -> TraceSweepConfig {
    TraceSweepConfig {
        latent_scale: 0.05,
        latent_cap: 0.25,
        latent_steps: 2,
        latent_decay: 0.5,
        latent_fanout: 10,
        visible_limit: 2,
        latent_limit: 4,
        seed_limit: 2,
        suppressed_limit: 4,
    }
}

fn seed_cognitive_trace_store(case: &CognitiveTraceCase) -> (Store, String) {
    let mut store = Store::open_in_memory().expect("cognitive trace benchmark store opens");
    let seed = write_cognitive_memory(&mut store, case.seed, MemoryKind::State, 0.8);
    write_cognitive_memory(&mut store, case.visible_distractor, MemoryKind::Fact, 0.5);
    let hidden = write_cognitive_memory(&mut store, case.hidden, MemoryKind::Playbook, 0.9);
    let hidden_distractor =
        write_cognitive_memory(&mut store, case.hidden_distractor, MemoryKind::Fact, 0.5);
    store
        .update_edge(&seed, &hidden, 2.0)
        .expect("cognitive trace target edge is persisted");
    store
        .update_edge(&seed, &hidden_distractor, 2.0)
        .expect("cognitive trace distractor edge is persisted");

    (store, hidden)
}

fn seed_predictive_trace_store(case: &PredictiveTraceCase) -> (Store, String, String) {
    let mut store = Store::open_in_memory().expect("predictive trace benchmark store opens");
    let seed = write_cognitive_memory(&mut store, case.seed, MemoryKind::State, 0.8);
    write_cognitive_memory(&mut store, case.visible_distractor, MemoryKind::Fact, 0.5);
    let hidden = write_cognitive_memory(&mut store, case.hidden, MemoryKind::Playbook, 0.9);
    let future = write_cognitive_memory(&mut store, case.future, MemoryKind::Playbook, 0.9);
    let future_distractor =
        write_cognitive_memory(&mut store, case.future_distractor, MemoryKind::Fact, 0.5);
    store
        .update_edge(&seed, &hidden, 3.0)
        .expect("predictive trace target edge is persisted");
    store
        .update_edge(&seed, &future_distractor, 0.5)
        .expect("predictive trace distractor edge is persisted");
    store
        .update_edge(&hidden, &future, 3.0)
        .expect("predictive continuation target edge is persisted");
    store
        .update_edge(&hidden, &future_distractor, 0.5)
        .expect("predictive continuation distractor edge is persisted");

    (store, hidden, future)
}

fn seed_long_horizon_store(
    cases: &[LongHorizonCase],
) -> (
    Store,
    std::collections::BTreeMap<&'static str, LongHorizonIds>,
) {
    let mut store = Store::open_in_memory().expect("long horizon benchmark store opens");
    let mut ids = std::collections::BTreeMap::new();

    for case in cases {
        let seed = write_cognitive_memory(&mut store, case.seed, MemoryKind::State, 0.8);
        write_cognitive_memory(&mut store, case.visible_distractor, MemoryKind::Fact, 0.5);
        let hidden = write_cognitive_memory(&mut store, case.hidden, MemoryKind::Playbook, 0.9);
        let hidden_distractor =
            write_cognitive_memory(&mut store, case.hidden_distractor, MemoryKind::Fact, 0.5);
        store
            .update_edge(&seed, &hidden, 2.0)
            .expect("long horizon target edge is persisted");
        store
            .update_edge(&seed, &hidden_distractor, 1.0)
            .expect("long horizon distractor edge is persisted");

        ids.insert(case.label, LongHorizonIds { seed, hidden });
    }

    (store, ids)
}

fn exported_cognitive_session_fixture(dataset: &str) -> ExportedCognitiveSession {
    toml::from_str(dataset).expect("exported cognitive session dataset parses")
}

fn seed_exported_cognitive_session_store(
    chains: &[ExportedCognitiveChain],
) -> (
    Store,
    std::collections::BTreeMap<String, ExportedCognitiveIds>,
) {
    let mut store = Store::open_in_memory().expect("exported cognitive session store opens");
    let mut ids = std::collections::BTreeMap::new();

    for chain in chains {
        let scope = chain.scope();
        let seed =
            write_scoped_cognitive_memory(&mut store, &chain.seed, MemoryKind::State, 0.8, &scope);
        write_scoped_cognitive_memory(
            &mut store,
            &chain.visible_distractor,
            MemoryKind::Fact,
            0.5,
            &scope,
        );
        let hidden = write_scoped_cognitive_memory(
            &mut store,
            &chain.hidden,
            MemoryKind::Playbook,
            0.9,
            &scope,
        );
        let hidden_distractor = write_scoped_cognitive_memory(
            &mut store,
            &chain.hidden_distractor,
            MemoryKind::Fact,
            0.5,
            &scope,
        );
        let future = write_scoped_cognitive_memory(
            &mut store,
            &chain.future,
            MemoryKind::Playbook,
            0.9,
            &scope,
        );
        let future_distractor = write_scoped_cognitive_memory(
            &mut store,
            &chain.future_distractor,
            MemoryKind::Fact,
            0.5,
            &scope,
        );

        store
            .update_edge(&seed, &hidden, 3.0)
            .expect("exported cognitive hidden edge is persisted");
        store
            .update_edge(&seed, &hidden_distractor, 0.5)
            .expect("exported cognitive hidden distractor edge is persisted");
        store
            .update_edge(&hidden, &future, 3.0)
            .expect("exported cognitive future edge is persisted");
        store
            .update_edge(&hidden, &future_distractor, 0.5)
            .expect("exported cognitive future distractor edge is persisted");

        ids.insert(
            chain.label.clone(),
            ExportedCognitiveIds {
                seed,
                hidden,
                future,
            },
        );
    }

    (store, ids)
}

fn exported_visible_recall_hits(
    store: &mut Store,
    chain: &ExportedCognitiveChain,
    seed: &str,
) -> bool {
    let query = RecallQuery {
        query: chain.query.clone(),
        k: Some(10),
        scope_filter: Some(chain.scope()),
        kind_filter: Some(MemoryKind::State),
    };
    let hits = synapse_core::RecallEngine::new(store)
        .recall(&query)
        .expect("exported cognitive visible recall runs");
    hits.iter().any(|hit| hit.memory.id == seed)
}

fn exported_trace_report(
    store: &mut Store,
    chain: &ExportedCognitiveChain,
) -> CognitiveTraceReport {
    let query = RecallQuery {
        query: chain.query.clone(),
        k: Some(2),
        scope_filter: Some(chain.scope()),
        kind_filter: Some(MemoryKind::State),
    };
    let probe = exported_trace_probe();
    let context = LatentActivationContext::new(chain.state_terms.clone(), chain.goal_terms.clone());
    probe
        .trace(store, &query, &context)
        .expect("exported cognitive trace runs")
}

fn exported_prediction_hits(
    store: &Store,
    chain: &ExportedCognitiveChain,
    report: &CognitiveTraceReport,
    future: &str,
) -> bool {
    let prediction = exported_trace_probe()
        .predict_continuation(store, report, 10)
        .expect("exported cognitive prediction runs");
    prediction.candidates.iter().any(|hit| {
        hit.memory.id == future
            && hit
                .matched_terms
                .iter()
                .any(|term| chain.state_terms.iter().any(|state| term.ends_with(state)))
    })
}

fn exported_trace_probe() -> CognitiveTraceProbe {
    CognitiveTraceProbe::new(CognitiveTraceConfig {
        visible_limit: 2,
        latent_limit: 8,
        seed_limit: 1,
        suppressed_limit: 8,
        latent_scale: 0.05,
        latent_cap: 0.25,
        latent_steps: 2,
        latent_decay: 0.5,
        latent_fanout: 16,
    })
}

fn long_horizon_visible_recall_hits(store: &mut Store, case: &LongHorizonCase, seed: &str) -> bool {
    let query = RecallQuery {
        query: case.query.to_string(),
        k: Some(10),
        scope_filter: None,
        kind_filter: None,
    };
    let hits = synapse_core::RecallEngine::new(store)
        .recall(&query)
        .expect("long horizon visible recall runs");
    hits.iter().any(|hit| hit.memory.id == seed)
}

fn long_horizon_trace_report(store: &mut Store, case: &LongHorizonCase) -> CognitiveTraceReport {
    let query = RecallQuery {
        query: case.query.to_string(),
        k: Some(2),
        scope_filter: None,
        kind_filter: Some(MemoryKind::State),
    };
    let probe = CognitiveTraceProbe::new(CognitiveTraceConfig {
        visible_limit: 2,
        latent_limit: 6,
        seed_limit: 2,
        suppressed_limit: 8,
        latent_scale: 0.05,
        latent_cap: 0.25,
        latent_steps: 2,
        latent_decay: 0.5,
        latent_fanout: 16,
    });
    let context = LatentActivationContext::new(
        case.state_terms
            .iter()
            .map(|term| (*term).to_string())
            .collect(),
        case.goal_terms
            .iter()
            .map(|term| (*term).to_string())
            .collect(),
    );
    probe
        .trace(store, &query, &context)
        .expect("long horizon cognitive trace runs")
}

fn cognitive_trace_case_report(
    store: &mut Store,
    case: &CognitiveTraceCase,
    config: TraceSweepConfig,
) -> CognitiveTraceReport {
    let query = RecallQuery {
        query: case.query.to_string(),
        k: Some(config.visible_limit),
        scope_filter: None,
        kind_filter: None,
    };
    let probe = CognitiveTraceProbe::new(CognitiveTraceConfig {
        visible_limit: config.visible_limit,
        latent_limit: config.latent_limit,
        seed_limit: config.seed_limit,
        suppressed_limit: config.suppressed_limit,
        latent_scale: config.latent_scale,
        latent_cap: config.latent_cap,
        latent_steps: config.latent_steps,
        latent_decay: config.latent_decay,
        latent_fanout: config.latent_fanout,
    });
    let context = LatentActivationContext::new(
        case.state_terms
            .iter()
            .map(|term| (*term).to_string())
            .collect(),
        case.goal_terms
            .iter()
            .map(|term| (*term).to_string())
            .collect(),
    );
    probe
        .trace(store, &query, &context)
        .expect("cognitive trace probe runs")
}

fn trace_report_dominates_hidden(report: &CognitiveTraceReport, hidden: &str) -> bool {
    report.dominant.as_ref().is_some_and(|candidate| {
        candidate.memory.id == hidden && !candidate.matched_terms.is_empty()
    })
}

fn trace_visible_seed_ids(report: &CognitiveTraceReport, reinforce_k: usize) -> Vec<String> {
    report
        .visible
        .iter()
        .take(reinforce_k)
        .map(|hit| hit.memory.id.clone())
        .collect()
}

fn trace_reinforcement_ids(
    report: &CognitiveTraceReport,
    reinforce_k: usize,
    dominant_id: &str,
) -> Vec<String> {
    let mut ids = trace_visible_seed_ids(report, reinforce_k);
    ids.push(dominant_id.to_string());
    normalize_ids(ids)
}

fn visible_hidden_edges(
    visible_ids: &[String],
    hidden: &str,
) -> std::collections::BTreeSet<(String, String)> {
    visible_ids
        .iter()
        .filter(|id| id.as_str() != hidden)
        .flat_map(|id| {
            [
                (id.clone(), hidden.to_string()),
                (hidden.to_string(), id.clone()),
            ]
        })
        .collect()
}

fn edge_weights(
    store: &mut Store,
    edges: &std::collections::BTreeSet<(String, String)>,
) -> std::collections::BTreeMap<(String, String), f32> {
    edges
        .iter()
        .map(|edge| {
            let weight = store
                .edge_weight(&edge.0, &edge.1)
                .expect("benchmark edge lookup succeeds")
                .unwrap_or(0.0);
            (edge.clone(), weight)
        })
        .collect()
}

fn edge_gained_weight(before: f32, after: f32) -> bool {
    after > before + f32::EPSILON
}

fn reinforce_trace_ids(store: &mut Store, ids: Vec<String>, query: &str) {
    if ids.len() < 2 {
        return;
    }

    let now = chrono::DateTime::from_timestamp(1_700_000_000, 0)
        .expect("fixed benchmark timestamp must be valid");
    let memory_event = MemoryEvent {
        id: MemoryEventId::nil(),
        timestamp: now,
        session_id: None,
        kind: MemoryEventKind::Recalled,
        memory_ids: ids.clone(),
        payload: MemoryEventPayload::Recalled {
            query: format!("trace:{query}"),
            hit_count: ids.len(),
        },
    };
    let importance = UniformImportanceEstimator;
    let events = InMemoryMemoryEventStream::with_capacity(1);
    events.record(memory_event.clone());
    let ctx = AlgorithmContext::new(now, None, &importance, &events);
    let output = RuleBasedHebbianAlgorithm::default()
        .reinforce(&HebbianTarget::new(vec![memory_event]), &ctx);
    let hebbian_report = PlanOnlyHebbianExecutor.execute(output.plans());
    let mutation_plan = DeterministicHebbianStoreMutationDispatcher::new(hebbian_report).dispatch();
    let mut executor = SQLitePersistentStoreExecutor::new(store);
    let store_report = executor.execute(&mutation_plan);
    assert!(
        store_report.skipped.is_empty(),
        "trace reinforcement benchmark store mutations should all apply"
    );
}

fn write_cognitive_memory(
    store: &mut Store,
    content: &str,
    kind: MemoryKind,
    importance: f32,
) -> String {
    write_scoped_cognitive_memory(store, content, kind, importance, &Scope::User)
}

fn write_scoped_cognitive_memory(
    store: &mut Store,
    content: &str,
    kind: MemoryKind,
    importance: f32,
    scope: &Scope,
) -> String {
    store
        .write(WriteInput {
            content: content.to_string(),
            kind,
            scope: scope.clone(),
            source: Source::ExplicitUser,
            confidence: Some(1.0),
            importance: Some(importance),
        })
        .expect("cognitive benchmark memory is written")
        .id
}

fn merge_fixture() -> Vec<(MergeTarget, bool)> {
    let mut superseded_duplicate = memory_with_kind(
        "merge-superseded-b",
        MemoryKind::Failure,
        Scope::Global,
        "Fix JWT refresh error by rotating token cache.",
    );
    superseded_duplicate.superseded_by = Some("merge-newer".to_string());

    vec![
        (
            MergeTarget::new(vec![
                memory_with_kind(
                    "merge-duplicate-a",
                    MemoryKind::Failure,
                    Scope::Global,
                    "Fix JWT refresh error by rotating token cache.",
                ),
                memory_with_kind(
                    "merge-duplicate-b",
                    MemoryKind::Failure,
                    Scope::Global,
                    "Fix JWT refresh error by rotating token cache.",
                ),
            ]),
            true,
        ),
        (
            MergeTarget::new(vec![
                memory_with_kind(
                    "merge-preference-a",
                    MemoryKind::Preference,
                    Scope::User,
                    "Prefer concise Chinese summaries.",
                ),
                memory_with_kind(
                    "merge-preference-b",
                    MemoryKind::Preference,
                    Scope::User,
                    "Prefer concise Chinese summaries.",
                ),
            ]),
            true,
        ),
        (
            MergeTarget::new(vec![
                memory_with_kind(
                    "merge-candidate-a",
                    MemoryKind::Failure,
                    Scope::Global,
                    "Fix JWT refresh error in auth middleware.",
                ),
                memory_with_kind(
                    "merge-candidate-b",
                    MemoryKind::Failure,
                    Scope::Global,
                    "Avoid JWT refresh failure in auth handler.",
                ),
            ]),
            false,
        ),
        (
            MergeTarget::new(vec![
                memory_with_kind(
                    "merge-unrelated-a",
                    MemoryKind::Failure,
                    Scope::Global,
                    "Fix JWT refresh error.",
                ),
                memory_with_kind(
                    "merge-unrelated-b",
                    MemoryKind::Preference,
                    Scope::User,
                    "Prefer concise Chinese summaries.",
                ),
            ]),
            false,
        ),
        (
            MergeTarget::new(vec![
                memory_with_kind(
                    "merge-superseded-a",
                    MemoryKind::Failure,
                    Scope::Global,
                    "Fix JWT refresh error by rotating token cache.",
                ),
                superseded_duplicate,
            ]),
            false,
        ),
    ]
}

fn forget_fixture() -> Vec<(ForgetTarget, bool)> {
    let mut expired = memory_with_kind(
        "forget-expired",
        MemoryKind::State,
        Scope::Global,
        "Expired temporary deploy state.",
    );
    expired.valid_to = Some(1);

    let mut superseded = memory_with_kind(
        "forget-superseded",
        MemoryKind::Fact,
        Scope::Global,
        "Old vector dimension was 384.",
    );
    superseded.superseded_by = Some("new-vector-dim".to_string());

    let mut stale_scratch = memory_with_kind(
        "forget-stale-scratch",
        MemoryKind::State,
        Scope::Global,
        "todo",
    );
    stale_scratch.confidence = 0.2;
    stale_scratch.importance = 0.1;
    stale_scratch.valid_from = 1_600_000_000;

    let mut protected = memory_with_kind(
        "forget-protected",
        MemoryKind::Playbook,
        Scope::Global,
        "Critical recovery playbook must be retained.",
    );
    protected.importance = 0.95;
    protected.valid_from = 1_600_000_000;

    let mut recent = memory_with_kind(
        "forget-recent",
        MemoryKind::Fact,
        Scope::Global,
        "Recently used deployment note.",
    );
    recent.importance = 0.1;
    recent.confidence = 0.1;
    recent.last_accessed_at = Some(1_700_000_000 - 60);

    let mut candidate = memory_with_kind(
        "forget-candidate",
        MemoryKind::Fact,
        Scope::Global,
        "Old rarely used fact.",
    );
    candidate.confidence = 0.7;
    candidate.importance = 0.4;
    candidate.valid_from = 1_600_000_000;

    vec![
        (ForgetTarget::new(expired), true),
        (ForgetTarget::new(superseded), true),
        (ForgetTarget::new(stale_scratch), true),
        (ForgetTarget::new(protected), false),
        (ForgetTarget::new(recent), false),
        (ForgetTarget::new(candidate), false),
    ]
}

fn hebbian_fixture() -> (HebbianTarget, Vec<(String, String)>) {
    let now = chrono::DateTime::from_timestamp(1_700_000_000, 0)
        .expect("fixed benchmark timestamp must be valid");
    let recall_event = MemoryEvent {
        id: MemoryEventId::nil(),
        timestamp: now,
        session_id: None,
        kind: MemoryEventKind::Recalled,
        memory_ids: vec!["a".to_string(), "b".to_string()],
        payload: MemoryEventPayload::Recalled {
            query: "auth refresh".to_string(),
            hit_count: 2,
        },
    };
    let merge_event = MemoryEvent {
        id: MemoryEventId::nil(),
        timestamp: now,
        session_id: None,
        kind: MemoryEventKind::MergeCompleted,
        memory_ids: vec!["b".to_string(), "c".to_string()],
        payload: MemoryEventPayload::MergeCompleted {
            into: "b".to_string(),
        },
    };
    let single_event = MemoryEvent {
        id: MemoryEventId::nil(),
        timestamp: now,
        session_id: None,
        kind: MemoryEventKind::Written,
        memory_ids: vec!["d".to_string()],
        payload: MemoryEventPayload::Empty,
    };
    (
        HebbianTarget::new(vec![recall_event, merge_event, single_event]),
        vec![
            ("a".to_string(), "b".to_string()),
            ("b".to_string(), "a".to_string()),
            ("b".to_string(), "c".to_string()),
            ("c".to_string(), "b".to_string()),
        ],
    )
}

fn memory(id: &str, content: &str) -> Memory {
    memory_with_kind(id, MemoryKind::Fact, Scope::Global, content)
}

fn memory_with_kind(id: &str, kind: MemoryKind, scope: Scope, content: &str) -> Memory {
    Memory {
        id: id.to_string(),
        kind,
        scope,
        content: content.to_string(),
        source: Source::ExplicitUser,
        confidence: 1.0,
        importance: 0.5,
        valid_from: 0,
        valid_to: None,
        superseded_by: None,
        access_count: 0,
        last_accessed_at: None,
    }
}

fn normalize_ids(ids: Vec<String>) -> Vec<String> {
    ids.into_iter()
        .map(|id| id.trim().to_string())
        .filter(|id| !id.is_empty())
        .collect::<std::collections::BTreeSet<_>>()
        .into_iter()
        .collect()
}

fn ratio(numerator: usize, denominator: usize) -> f64 {
    if denominator == 0 {
        0.0
    } else {
        numerator as f64 / denominator as f64
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn reflection_yield_report_is_deterministic() {
        let a = reflection_yield_report();
        let b = reflection_yield_report();

        assert_eq!(a, b);
    }

    #[test]
    fn reflection_yield_report_uses_contract_shape() {
        let report = reflection_yield_report();

        assert_eq!(report.benchmark, "reflection-yield");
        assert_eq!(report.metrics.len(), 1);
        assert_eq!(
            report.metrics.get(&AlgorithmMetric::ReflectionYield),
            Some(&1.0)
        );
    }

    #[test]
    fn deterministic_reflection_yield_report_uses_contract_shape() {
        let report = deterministic_reflection_yield_report();

        assert_eq!(report.benchmark, "reflection-yield-deterministic");
        assert_eq!(report.metrics.len(), 1);
        assert_eq!(
            report.metrics.get(&AlgorithmMetric::ReflectionYield),
            Some(&1.0)
        );
    }

    #[test]
    fn cognitive_chain_recall_report_is_deterministic() {
        let a = cognitive_chain_recall_report();
        let b = cognitive_chain_recall_report();

        assert_eq!(a, b);
    }

    #[test]
    fn cognitive_chain_recall_report_uses_contract_shape() {
        let report = cognitive_chain_recall_report();

        assert_eq!(report.benchmark, "cognitive-chain-recall");
        assert_eq!(report.metrics.len(), 1);
        assert_eq!(report.metrics.get(&AlgorithmMetric::RecallAt10), Some(&1.0));
    }

    #[test]
    fn cognitive_trace_dominance_report_is_deterministic() {
        let a = cognitive_trace_dominance_report();
        let b = cognitive_trace_dominance_report();

        assert_eq!(a, b);
    }

    #[test]
    fn cognitive_trace_dominance_report_uses_contract_shape() {
        let report = cognitive_trace_dominance_report();

        assert_eq!(report.benchmark, "cognitive-trace-dominance");
        assert_eq!(report.metrics.len(), 1);
        assert_eq!(
            report
                .metrics
                .get(&AlgorithmMetric::CognitiveTraceDominance),
            Some(&1.0)
        );
    }

    #[test]
    fn trace_reinforcement_report_is_deterministic() {
        let a = trace_reinforcement_report();
        let b = trace_reinforcement_report();

        assert_eq!(a, b);
    }

    #[test]
    fn trace_reinforcement_report_uses_contract_shape() {
        let report = trace_reinforcement_report();

        assert_eq!(report.benchmark, "trace-reinforcement");
        assert_eq!(report.metrics.len(), 2);
        assert_eq!(
            report
                .metrics
                .get(&AlgorithmMetric::CognitiveTraceDominance),
            Some(&1.0)
        );
        assert_eq!(
            report.metrics.get(&AlgorithmMetric::HebbianConsistency),
            Some(&1.0)
        );
    }

    #[test]
    fn predictive_trace_report_is_deterministic() {
        let a = predictive_trace_report();
        let b = predictive_trace_report();

        assert_eq!(a, b);
    }

    #[test]
    fn predictive_trace_report_uses_contract_shape() {
        let report = predictive_trace_report();

        assert_eq!(report.benchmark, "predictive-trace");
        assert_eq!(report.metrics.len(), 1);
        assert_eq!(report.metrics.get(&AlgorithmMetric::RecallAt10), Some(&1.0));
    }

    #[test]
    fn activation_parameter_sweep_report_is_deterministic() {
        let a = activation_parameter_sweep_report();
        let b = activation_parameter_sweep_report();

        assert_eq!(a, b);
    }

    #[test]
    fn activation_parameter_sweep_report_uses_contract_shape() {
        let report = activation_parameter_sweep_report();

        assert_eq!(report.benchmark, "activation-parameter-sweep");
        assert_eq!(report.metrics.len(), 3);
        assert_eq!(report.metrics.get(&AlgorithmMetric::RecallAt10), Some(&1.0));
        assert_eq!(
            report
                .metrics
                .get(&AlgorithmMetric::CognitiveTraceDominance),
            Some(&1.0)
        );
        assert_eq!(
            report.metrics.get(&AlgorithmMetric::HebbianConsistency),
            Some(&1.0)
        );
    }

    #[test]
    fn activation_parameter_sweep_uses_broader_final_coverage() {
        let chain_cases = cognitive_chain_fixture();
        let latent_configs = latent_sweep_configs();
        let trace_configs = trace_sweep_configs();

        assert!(
            chain_cases.len() >= 7,
            "final sweep should cover a broader cognitive-chain fixture"
        );
        assert!(
            latent_configs.len() >= 5,
            "final latent sweep should cover at least five parameter settings"
        );
        assert!(
            trace_configs.len() >= 5,
            "final trace sweep should cover at least five parameter settings"
        );
        assert!(
            latent_configs.iter().any(|config| config.steps >= 4),
            "latent sweep should include multi-step production-depth activation"
        );
        assert!(
            latent_configs.iter().any(|config| config.fanout >= 24),
            "latent sweep should include wider fanout coverage"
        );
        assert!(
            trace_configs.iter().any(|config| config.latent_steps >= 4
                && config.visible_limit >= 4
                && config.latent_limit >= 8
                && config.seed_limit >= 3
                && config.suppressed_limit >= 8),
            "trace sweep should include a wider production-range configuration"
        );
    }

    #[test]
    fn long_horizon_cognitive_memory_report_is_deterministic() {
        let a = long_horizon_cognitive_memory_report();
        let b = long_horizon_cognitive_memory_report();

        assert_eq!(a, b);
    }

    #[test]
    fn long_horizon_cognitive_memory_report_uses_contract_shape() {
        let report = long_horizon_cognitive_memory_report();

        assert_eq!(report.benchmark, "long-horizon-cognitive-memory");
        assert_eq!(report.metrics.len(), 3);
        assert_eq!(report.metrics.get(&AlgorithmMetric::RecallAt10), Some(&1.0));
        assert_eq!(
            report
                .metrics
                .get(&AlgorithmMetric::CognitiveTraceDominance),
            Some(&1.0)
        );
        assert_eq!(
            report.metrics.get(&AlgorithmMetric::HebbianConsistency),
            Some(&1.0)
        );
    }

    #[test]
    fn exported_cognitive_session_report_is_deterministic() {
        let a = exported_cognitive_session_report();
        let b = exported_cognitive_session_report();

        assert_eq!(a, b);
    }

    #[test]
    fn exported_cognitive_session_report_uses_contract_shape() {
        let report = exported_cognitive_session_report();

        assert_eq!(report.benchmark, "exported-cognitive-session");
        assert_eq!(report.metrics.len(), 3);
        assert_eq!(report.metrics.get(&AlgorithmMetric::RecallAt10), Some(&1.0));
        assert_eq!(
            report
                .metrics
                .get(&AlgorithmMetric::CognitiveTraceDominance),
            Some(&1.0)
        );
        assert_eq!(
            report.metrics.get(&AlgorithmMetric::HebbianConsistency),
            Some(&1.0)
        );
    }

    #[test]
    fn expanded_cognitive_replay_report_is_deterministic() {
        let a = expanded_cognitive_replay_report();
        let b = expanded_cognitive_replay_report();

        assert_eq!(a, b);
    }

    #[test]
    fn expanded_cognitive_replay_report_uses_contract_shape() {
        let report = expanded_cognitive_replay_report();

        assert_eq!(report.benchmark, "expanded-cognitive-replay");
        assert_eq!(report.metrics.len(), 3);
        assert_eq!(report.metrics.get(&AlgorithmMetric::RecallAt10), Some(&1.0));
        assert_eq!(
            report
                .metrics
                .get(&AlgorithmMetric::CognitiveTraceDominance),
            Some(&1.0)
        );
        assert_eq!(
            report.metrics.get(&AlgorithmMetric::HebbianConsistency),
            Some(&1.0)
        );
    }

    #[test]
    fn merge_precision_report_is_deterministic() {
        let a = merge_precision_report();
        let b = merge_precision_report();

        assert_eq!(a, b);
    }

    #[test]
    fn merge_precision_report_uses_contract_shape() {
        let report = merge_precision_report();

        assert_eq!(report.benchmark, "merge-precision");
        assert_eq!(report.metrics.len(), 1);
        assert_eq!(
            report.metrics.get(&AlgorithmMetric::MergePrecision),
            Some(&1.0)
        );
    }

    #[test]
    fn forget_precision_report_is_deterministic() {
        let a = forget_precision_report();
        let b = forget_precision_report();

        assert_eq!(a, b);
    }

    #[test]
    fn forget_precision_report_uses_contract_shape() {
        let report = forget_precision_report();

        assert_eq!(report.benchmark, "forget-precision");
        assert_eq!(report.metrics.len(), 1);
        assert_eq!(
            report.metrics.get(&AlgorithmMetric::ForgetPrecision),
            Some(&1.0)
        );
    }

    #[test]
    fn hebbian_consistency_report_is_deterministic() {
        let a = hebbian_consistency_report();
        let b = hebbian_consistency_report();

        assert_eq!(a, b);
    }

    #[test]
    fn hebbian_consistency_report_uses_contract_shape() {
        let report = hebbian_consistency_report();

        assert_eq!(report.benchmark, "hebbian-consistency");
        assert_eq!(report.metrics.len(), 1);
        assert_eq!(
            report.metrics.get(&AlgorithmMetric::HebbianConsistency),
            Some(&1.0)
        );
    }
}
