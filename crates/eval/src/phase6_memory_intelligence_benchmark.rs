use anyhow::{ensure, Context, Result};
use chrono::Utc;
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::{
    collections::{BTreeMap, BTreeSet, HashMap},
    fs,
    path::{Path, PathBuf},
    str::FromStr,
};
use synapse_core::{
    MemoryKind, RecallEngine, RecallProfile, RecallQuery, Scope, Source, Store, WriteInput,
};

use crate::metrics::{ndcg_at_k, percentile, recall_at_k, reciprocal_rank};

const SCHEMA_VERSION: u32 = 1;
const BENCHMARK_VERSION: &str = "phase6.0-memory-intelligence-benchmark-v1";
const EVALUATION_VERSION: &str = "phase6.0-memory-intelligence-benchmark-gate-v1";
const DEFAULT_K: usize = 5;
const EXPECTED_SCENARIOS: usize = 320;
const EXPECTED_MEMORIES_PER_SCENARIO: usize = 6;
const EXPECTED_CATEGORIES: usize = 10;
const EXPECTED_TEMPLATE_VARIANTS: usize = 4;
const EPSILON: f64 = 1e-12;
// RecallEngine applies second-resolution temporal decay using the wall clock. Two
// otherwise identical recalls can straddle a one-second boundary, so score
// determinism uses a tolerance while ranking determinism remains exact.
const SCORE_DETERMINISM_EPSILON: f64 = 1e-6;

pub struct Phase6MemoryIntelligenceBenchmarkEvaluator;

impl Phase6MemoryIntelligenceBenchmarkEvaluator {
    pub fn evaluate(tag: impl Into<String>) -> Result<Phase6MemoryIntelligenceReport> {
        evaluate(tag.into())
    }
}

pub fn load_phase6_memory_intelligence_benchmark() -> Result<Vec<MemoryIntelligenceScenarioSpec>> {
    let path = dataset_path();
    let source = fs::read_to_string(&path)
        .with_context(|| format!("reading Phase 6.0 benchmark {}", path.display()))?;
    ensure!(
        !source.contains("baseline_score"),
        "Phase 6.0 benchmark must not contain artificial baseline_score fields"
    );
    let dataset: MemoryIntelligenceDatasetFile = toml::from_str(&source)
        .with_context(|| format!("parsing Phase 6.0 benchmark {}", path.display()))?;
    ensure!(dataset.schema_version == SCHEMA_VERSION);
    ensure!(dataset.benchmark_version == BENCHMARK_VERSION);
    ensure!(dataset.generator_seed == 600_320);
    validate_scenarios(&dataset.scenario)?;
    Ok(dataset.scenario)
}

fn evaluate(tag: String) -> Result<Phase6MemoryIntelligenceReport> {
    let scenarios = load_phase6_memory_intelligence_benchmark()?;
    let mut reports = Vec::with_capacity(scenarios.len());
    let mut all_store_unchanged = true;

    for scenario in &scenarios {
        let outcome = evaluate_scenario(scenario)?;
        all_store_unchanged &= outcome.store_unchanged;
        reports.push(outcome.report);
    }

    let dataset = summarize_dataset(&scenarios)?;
    let retrieval = aggregate_metrics(&reports);
    let category_metrics = grouped_metrics(&reports, |scenario| scenario.category.clone());
    let split_metrics = grouped_metrics(&reports, |scenario| scenario.split.clone());
    let all_deterministic = reports.iter().all(|scenario| scenario.deterministic);
    let all_entity_neutral = reports
        .iter()
        .all(|scenario| scenario.retrieval_profile.entity_candidates == 0);
    let all_expected_retrieved = reports.iter().all(|scenario| scenario.expected_retrieved);
    let all_label_intent_aligned = reports
        .iter()
        .all(|scenario| scenario.intervention_required != scenario.baseline_top_expected);

    let guards = MemoryIntelligenceGuards {
        eval_only: true,
        benchmark_only: true,
        real_recall_engine_used: true,
        artificial_baseline_scores_used: false,
        vectors_enabled: false,
        reranker_enabled: false,
        access_recording_enabled: false,
        runtime_applied: false,
        memory_mutated_during_retrieval: !all_store_unchanged,
        recall_engine_modified: false,
        runtime_booster_registered: false,
        algorithm_comparison_performed: false,
        independent_cognitive_value_claimed: false,
        runtime_authorization: false,
        production_claim_authorized: false,
    };

    let split_shape_valid = dataset.split_counts.get("train") == Some(&160)
        && dataset.split_counts.get("validation") == Some(&80)
        && dataset.split_counts.get("test") == Some(&80);
    let category_shape_valid = dataset.category_split_counts.values().all(|counts| {
        counts.get("train") == Some(&16)
            && counts.get("validation") == Some(&8)
            && counts.get("test") == Some(&8)
    });

    let pass = dataset.scenarios == EXPECTED_SCENARIOS
        && dataset.memories == EXPECTED_SCENARIOS * EXPECTED_MEMORIES_PER_SCENARIO
        && dataset.categories == EXPECTED_CATEGORIES
        && dataset.template_variants == EXPECTED_TEMPLATE_VARIANTS
        && dataset.unique_queries == EXPECTED_SCENARIOS
        && split_shape_valid
        && category_shape_valid
        && all_expected_retrieved
        && all_deterministic
        && all_entity_neutral
        && all_label_intent_aligned
        && (retrieval.expected_candidate_retrieval_rate - 1.0).abs() <= EPSILON
        && (retrieval.determinism - 1.0).abs() <= EPSILON
        && (retrieval.label_intent_alignment - 1.0).abs() <= EPSILON
        && !guards.artificial_baseline_scores_used
        && !guards.runtime_applied
        && !guards.memory_mutated_during_retrieval
        && !guards.recall_engine_modified
        && !guards.runtime_booster_registered
        && !guards.algorithm_comparison_performed
        && !guards.independent_cognitive_value_claimed
        && !guards.runtime_authorization
        && !guards.production_claim_authorized;

    Ok(Phase6MemoryIntelligenceReport {
        schema_version: SCHEMA_VERSION,
        tag,
        phase: "Phase 6.0 Memory Intelligence Benchmark".to_string(),
        mode: "offline_real_recall_benchmark_foundation".to_string(),
        evaluation_version: EVALUATION_VERSION.to_string(),
        generated_at: Utc::now().to_rfc3339(),
        protocol: MemoryIntelligenceProtocol {
            dataset_path: relative_dataset_path(),
            dataset_sha256: hash_file(&dataset_path())?,
            generator_path: relative_generator_path(),
            generator_sha256: hash_file(&generator_path())?,
            generator_seed: 600_320,
            candidate_limit: DEFAULT_K,
            retrieval_mode: "real_recall_engine_fts_entity_no_vectors_no_reranker".to_string(),
            score_provenance: "RecallEngine::recall_profiled RecallHit.score".to_string(),
            split_policy: "per-category fixed 16 train / 8 validation / 8 test".to_string(),
            quality_gate_semantics: "PASS validates benchmark integrity, retrieval provenance, deterministic reachability, and safety only".to_string(),
        },
        dataset,
        retrieval,
        category_metrics,
        split_metrics,
        scenarios: reports,
        guards,
        pass,
        status: if pass { "PASS" } else { "FAIL" }.to_string(),
        conclusion: "Phase 6.0 freezes a 320-scenario real-RecallEngine benchmark foundation. PASS does not compare cognitive algorithms, prove independent cognitive value, or authorize runtime.".to_string(),
    })
}

fn dataset_path() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("datasets")
        .join("memory_intelligence")
        .join("agent_memory_benchmark.toml")
}

fn generator_path() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("..")
        .join("..")
        .join("scripts")
        .join("eval")
        .join("generate_phase6_memory_intelligence_benchmark.py")
}

fn relative_dataset_path() -> String {
    "crates/eval/datasets/memory_intelligence/agent_memory_benchmark.toml".to_string()
}

fn relative_generator_path() -> String {
    "scripts/eval/generate_phase6_memory_intelligence_benchmark.py".to_string()
}

fn hash_file(path: &Path) -> Result<String> {
    let mut hasher = Sha256::new();
    hasher.update(fs::read(path)?);
    Ok(format!("{:x}", hasher.finalize()))
}

fn validate_scenarios(scenarios: &[MemoryIntelligenceScenarioSpec]) -> Result<()> {
    ensure!(scenarios.len() == EXPECTED_SCENARIOS);
    let mut ids = BTreeSet::new();
    let mut queries = BTreeSet::new();
    let mut category_counts = BTreeMap::<String, usize>::new();
    let mut category_split_counts = BTreeMap::<String, BTreeMap<String, usize>>::new();

    for scenario in scenarios {
        ensure!(
            ids.insert(scenario.id.clone()),
            "duplicate id {}",
            scenario.id
        );
        ensure!(
            queries.insert(scenario.query.clone()),
            "duplicate query {}",
            scenario.query
        );
        ensure!(matches!(
            scenario.split.as_str(),
            "train" | "validation" | "test"
        ));
        ensure!(!scenario.category.trim().is_empty());
        ensure!(!scenario.expected_reason.trim().is_empty());
        ensure!(scenario.conflicting_signals.len() >= 2);
        ensure!(scenario.memory.len() == EXPECTED_MEMORIES_PER_SCENARIO);
        ensure!((0..EXPECTED_TEMPLATE_VARIANTS).contains(&scenario.template_variant));
        *category_counts
            .entry(scenario.category.clone())
            .or_default() += 1;
        *category_split_counts
            .entry(scenario.category.clone())
            .or_default()
            .entry(scenario.split.clone())
            .or_default() += 1;

        let mut labels = BTreeSet::new();
        let mut turns = BTreeSet::new();
        let relevant = scenario
            .memory
            .iter()
            .filter(|memory| memory.relevant)
            .collect::<Vec<_>>();
        ensure!(
            relevant.len() == 1,
            "{} needs one relevant memory",
            scenario.id
        );
        ensure!(relevant[0].label == scenario.expected_top);
        ensure!(relevant[0].role == "ground_truth");
        ensure!(relevant[0].turn == scenario.timeline_length);

        for memory in &scenario.memory {
            ensure!(labels.insert(memory.label.clone()));
            ensure!(turns.insert(memory.turn));
            ensure!(!memory.content.trim().is_empty());
            ensure!(!memory.role.trim().is_empty());
            ensure!((0.0..=1.0).contains(&memory.confidence));
            ensure!((0.0..=1.0).contains(&memory.importance));
            MemoryKind::from_str(&memory.kind)
                .with_context(|| format!("invalid memory kind in {}", scenario.id))?;
        }
    }

    ensure!(category_counts.len() == EXPECTED_CATEGORIES);
    ensure!(category_counts.values().all(|count| *count == 32));
    ensure!(category_split_counts.values().all(|counts| {
        counts.get("train") == Some(&16)
            && counts.get("validation") == Some(&8)
            && counts.get("test") == Some(&8)
    }));
    Ok(())
}

fn evaluate_scenario(spec: &MemoryIntelligenceScenarioSpec) -> Result<ScenarioOutcome> {
    let mut store = Store::open_in_memory()?;
    let mut label_to_id = BTreeMap::new();
    let mut id_to_label = HashMap::new();
    let mut recently_accessed = Vec::new();
    let mut access_timestamp = 0_i64;

    let mut ordered_memories = spec.memory.iter().collect::<Vec<_>>();
    ordered_memories.sort_by_key(|memory| memory.turn);
    for memory in ordered_memories {
        let stored = store.write(WriteInput {
            content: memory.content.clone(),
            kind: MemoryKind::from_str(&memory.kind)?,
            scope: Scope::User,
            source: Source::ExplicitUser,
            confidence: Some(memory.confidence as f32),
            importance: Some(memory.importance as f32),
        })?;
        access_timestamp = access_timestamp.max(stored.valid_from + 1);
        if memory.recently_accessed {
            recently_accessed.push(stored.id.clone());
        }
        label_to_id.insert(memory.label.clone(), stored.id.clone());
        id_to_label.insert(stored.id, memory.label.clone());
    }
    if !recently_accessed.is_empty() {
        let ids = recently_accessed
            .iter()
            .map(String::as_str)
            .collect::<Vec<_>>();
        store.record_access(&ids, access_timestamp)?;
    }

    let before = snapshot_store(&store, label_to_id.values())?;
    let query = RecallQuery {
        query: spec.query.clone(),
        k: Some(DEFAULT_K),
        scope_filter: Some(Scope::User),
        kind_filter: None,
    };
    let first = RecallEngine::new(&mut store)
        .with_access_recording(false)
        .recall_profiled(&query)?;
    let after_first = snapshot_store(&store, label_to_id.values())?;
    let second = RecallEngine::new(&mut store)
        .with_access_recording(false)
        .recall_profiled(&query)?;
    let after_second = snapshot_store(&store, label_to_id.values())?;
    ensure!(!first.hits.is_empty(), "{} returned no RecallHit", spec.id);

    let ranking = hit_labels(&first.hits, &id_to_label)?;
    let second_ranking = hit_labels(&second.hits, &id_to_label)?;
    let scores = first
        .hits
        .iter()
        .map(|hit| hit.score as f64)
        .collect::<Vec<_>>();
    let second_scores = second
        .hits
        .iter()
        .map(|hit| hit.score as f64)
        .collect::<Vec<_>>();
    let deterministic = ranking == second_ranking
        && scores
            .iter()
            .zip(&second_scores)
            .all(|(left, right)| (left - right).abs() <= SCORE_DETERMINISM_EPSILON);
    let expected_rank = ranking
        .iter()
        .position(|label| label == &spec.expected_top)
        .map(|index| index + 1);
    let relevant = vec![spec.expected_top.clone()];

    Ok(ScenarioOutcome {
        store_unchanged: before == after_first && after_first == after_second,
        report: MemoryIntelligenceScenarioReport {
            id: spec.id.clone(),
            split: spec.split.clone(),
            category: spec.category.clone(),
            template_variant: spec.template_variant,
            intervention_required: spec.intervention_required,
            expected_top: spec.expected_top.clone(),
            expected_reason: spec.expected_reason.clone(),
            conflicting_signals: spec.conflicting_signals.clone(),
            ranking: ranking.clone(),
            scores,
            expected_retrieved: expected_rank.is_some(),
            expected_rank,
            baseline_top_expected: ranking.first() == Some(&spec.expected_top),
            recall_at_1: recall_at_k(&ranking, &relevant, 1),
            recall_at_3: recall_at_k(&ranking, &relevant, 3),
            recall_at_5: recall_at_k(&ranking, &relevant, 5),
            reciprocal_rank_at_5: reciprocal_rank(&ranking, &relevant),
            ndcg_at_5: ndcg_at_k(&ranking, &relevant, 5),
            deterministic,
            store_unchanged: before == after_first && after_first == after_second,
            retrieval_profile: first.profile,
        },
    })
}

fn hit_labels(
    hits: &[synapse_core::RecallHit],
    id_to_label: &HashMap<String, String>,
) -> Result<Vec<String>> {
    hits.iter()
        .map(|hit| {
            id_to_label
                .get(&hit.memory.id)
                .cloned()
                .with_context(|| format!("unknown RecallHit id {}", hit.memory.id))
        })
        .collect()
}

fn snapshot_store<'a>(store: &Store, ids: impl Iterator<Item = &'a String>) -> Result<String> {
    let mut memories = ids
        .map(|id| store.get(id))
        .collect::<std::result::Result<Vec<_>, _>>()?;
    memories.sort_by(|left, right| {
        left.as_ref()
            .map(|memory| &memory.id)
            .cmp(&right.as_ref().map(|memory| &memory.id))
    });
    Ok(serde_json::to_string(&memories)?)
}

fn summarize_dataset(
    scenarios: &[MemoryIntelligenceScenarioSpec],
) -> Result<MemoryIntelligenceDatasetSummary> {
    let mut split_counts = BTreeMap::new();
    let mut category_counts = BTreeMap::new();
    let mut category_split_counts = BTreeMap::<String, BTreeMap<String, usize>>::new();
    let mut memory_kind_counts = BTreeMap::new();
    let mut queries = BTreeSet::new();
    let mut variants = BTreeSet::new();
    let mut intervention_required = 0;

    for scenario in scenarios {
        *split_counts.entry(scenario.split.clone()).or_default() += 1;
        *category_counts
            .entry(scenario.category.clone())
            .or_default() += 1;
        *category_split_counts
            .entry(scenario.category.clone())
            .or_default()
            .entry(scenario.split.clone())
            .or_default() += 1;
        queries.insert(scenario.query.clone());
        variants.insert(scenario.template_variant);
        if scenario.intervention_required {
            intervention_required += 1;
        }
        for memory in &scenario.memory {
            *memory_kind_counts.entry(memory.kind.clone()).or_default() += 1;
        }
    }

    Ok(MemoryIntelligenceDatasetSummary {
        scenarios: scenarios.len(),
        memories: scenarios.iter().map(|scenario| scenario.memory.len()).sum(),
        categories: category_counts.len(),
        template_variants: variants.len(),
        unique_queries: queries.len(),
        intervention_required,
        no_intervention: scenarios.len() - intervention_required,
        split_counts,
        category_counts,
        category_split_counts,
        memory_kind_counts,
    })
}

fn grouped_metrics(
    reports: &[MemoryIntelligenceScenarioReport],
    key: impl Fn(&MemoryIntelligenceScenarioReport) -> String,
) -> Vec<MemoryIntelligenceGroupMetrics> {
    let mut groups = BTreeMap::<String, Vec<&MemoryIntelligenceScenarioReport>>::new();
    for report in reports {
        groups.entry(key(report)).or_default().push(report);
    }
    groups
        .into_iter()
        .map(|(group, scenarios)| MemoryIntelligenceGroupMetrics {
            group,
            metrics: aggregate_borrowed_metrics(&scenarios),
        })
        .collect()
}

fn aggregate_metrics(
    reports: &[MemoryIntelligenceScenarioReport],
) -> MemoryIntelligenceRetrievalMetrics {
    let borrowed = reports.iter().collect::<Vec<_>>();
    aggregate_borrowed_metrics(&borrowed)
}

fn aggregate_borrowed_metrics(
    reports: &[&MemoryIntelligenceScenarioReport],
) -> MemoryIntelligenceRetrievalMetrics {
    let count = reports.len() as f64;
    let mean = |value: fn(&MemoryIntelligenceScenarioReport) -> f64| {
        reports.iter().map(|report| value(report)).sum::<f64>() / count
    };
    let mut latencies = reports
        .iter()
        .map(|report| report.retrieval_profile.total_ms)
        .collect::<Vec<_>>();
    let expected_rank_distribution =
        reports
            .iter()
            .fold(BTreeMap::<usize, usize>::new(), |mut counts, report| {
                if let Some(rank) = report.expected_rank {
                    *counts.entry(rank).or_default() += 1;
                }
                counts
            });
    let entity_candidates = reports
        .iter()
        .map(|report| report.retrieval_profile.entity_candidates)
        .sum();

    MemoryIntelligenceRetrievalMetrics {
        scenarios: reports.len(),
        expected_candidate_retrieval_rate: mean(
            |report| {
                if report.expected_retrieved {
                    1.0
                } else {
                    0.0
                }
            },
        ),
        recall_at_1: mean(|report| report.recall_at_1),
        recall_at_3: mean(|report| report.recall_at_3),
        recall_at_5: mean(|report| report.recall_at_5),
        mrr_at_5: mean(|report| report.reciprocal_rank_at_5),
        ndcg_at_5: mean(|report| report.ndcg_at_5),
        determinism: mean(|report| if report.deterministic { 1.0 } else { 0.0 }),
        store_unchanged_rate: mean(|report| if report.store_unchanged { 1.0 } else { 0.0 }),
        label_intent_alignment: mean(|report| {
            if report.intervention_required != report.baseline_top_expected {
                1.0
            } else {
                0.0
            }
        }),
        entity_candidates,
        entity_candidate_rate: entity_candidates as f64 / count,
        retrieval_latency_p50_ms: percentile(&mut latencies.clone(), 50.0),
        retrieval_latency_p95_ms: percentile(&mut latencies, 95.0),
        expected_rank_distribution,
    }
}

#[derive(Debug, Deserialize)]
struct MemoryIntelligenceDatasetFile {
    schema_version: u32,
    benchmark_version: String,
    generator_seed: u64,
    scenario: Vec<MemoryIntelligenceScenarioSpec>,
}

#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct MemoryIntelligenceScenarioSpec {
    pub id: String,
    pub split: String,
    pub category: String,
    pub query: String,
    pub expected_top: String,
    pub intervention_required: bool,
    pub timeline_length: usize,
    pub template_variant: usize,
    pub expected_reason: String,
    pub conflicting_signals: Vec<String>,
    pub memory: Vec<MemoryIntelligenceMemorySpec>,
}

#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct MemoryIntelligenceMemorySpec {
    pub label: String,
    pub content: String,
    pub kind: String,
    pub confidence: f64,
    pub importance: f64,
    pub recently_accessed: bool,
    pub relevant: bool,
    pub turn: usize,
    pub role: String,
}

struct ScenarioOutcome {
    store_unchanged: bool,
    report: MemoryIntelligenceScenarioReport,
}

#[derive(Debug, Clone, Serialize)]
pub struct Phase6MemoryIntelligenceReport {
    pub schema_version: u32,
    pub tag: String,
    pub phase: String,
    pub mode: String,
    pub evaluation_version: String,
    pub generated_at: String,
    pub protocol: MemoryIntelligenceProtocol,
    pub dataset: MemoryIntelligenceDatasetSummary,
    pub retrieval: MemoryIntelligenceRetrievalMetrics,
    pub category_metrics: Vec<MemoryIntelligenceGroupMetrics>,
    pub split_metrics: Vec<MemoryIntelligenceGroupMetrics>,
    pub scenarios: Vec<MemoryIntelligenceScenarioReport>,
    pub guards: MemoryIntelligenceGuards,
    pub pass: bool,
    pub status: String,
    pub conclusion: String,
}

#[derive(Debug, Clone, Serialize)]
pub struct MemoryIntelligenceProtocol {
    pub dataset_path: String,
    pub dataset_sha256: String,
    pub generator_path: String,
    pub generator_sha256: String,
    pub generator_seed: u64,
    pub candidate_limit: usize,
    pub retrieval_mode: String,
    pub score_provenance: String,
    pub split_policy: String,
    pub quality_gate_semantics: String,
}

#[derive(Debug, Clone, Serialize)]
pub struct MemoryIntelligenceDatasetSummary {
    pub scenarios: usize,
    pub memories: usize,
    pub categories: usize,
    pub template_variants: usize,
    pub unique_queries: usize,
    pub intervention_required: usize,
    pub no_intervention: usize,
    pub split_counts: BTreeMap<String, usize>,
    pub category_counts: BTreeMap<String, usize>,
    pub category_split_counts: BTreeMap<String, BTreeMap<String, usize>>,
    pub memory_kind_counts: BTreeMap<String, usize>,
}

#[derive(Debug, Clone, Serialize)]
pub struct MemoryIntelligenceGroupMetrics {
    pub group: String,
    pub metrics: MemoryIntelligenceRetrievalMetrics,
}

#[derive(Debug, Clone, Serialize)]
pub struct MemoryIntelligenceRetrievalMetrics {
    pub scenarios: usize,
    pub expected_candidate_retrieval_rate: f64,
    pub recall_at_1: f64,
    pub recall_at_3: f64,
    pub recall_at_5: f64,
    pub mrr_at_5: f64,
    pub ndcg_at_5: f64,
    pub determinism: f64,
    pub store_unchanged_rate: f64,
    pub label_intent_alignment: f64,
    pub entity_candidates: usize,
    pub entity_candidate_rate: f64,
    pub retrieval_latency_p50_ms: f64,
    pub retrieval_latency_p95_ms: f64,
    pub expected_rank_distribution: BTreeMap<usize, usize>,
}

#[derive(Debug, Clone, Serialize)]
pub struct MemoryIntelligenceScenarioReport {
    pub id: String,
    pub split: String,
    pub category: String,
    pub template_variant: usize,
    pub intervention_required: bool,
    pub expected_top: String,
    pub expected_reason: String,
    pub conflicting_signals: Vec<String>,
    pub ranking: Vec<String>,
    pub scores: Vec<f64>,
    pub expected_retrieved: bool,
    pub expected_rank: Option<usize>,
    pub baseline_top_expected: bool,
    pub recall_at_1: f64,
    pub recall_at_3: f64,
    pub recall_at_5: f64,
    pub reciprocal_rank_at_5: f64,
    pub ndcg_at_5: f64,
    pub deterministic: bool,
    pub store_unchanged: bool,
    pub retrieval_profile: RecallProfile,
}

#[derive(Debug, Clone, Serialize)]
pub struct MemoryIntelligenceGuards {
    pub eval_only: bool,
    pub benchmark_only: bool,
    pub real_recall_engine_used: bool,
    pub artificial_baseline_scores_used: bool,
    pub vectors_enabled: bool,
    pub reranker_enabled: bool,
    pub access_recording_enabled: bool,
    pub runtime_applied: bool,
    pub memory_mutated_during_retrieval: bool,
    pub recall_engine_modified: bool,
    pub runtime_booster_registered: bool,
    pub algorithm_comparison_performed: bool,
    pub independent_cognitive_value_claimed: bool,
    pub runtime_authorization: bool,
    pub production_claim_authorized: bool,
}
