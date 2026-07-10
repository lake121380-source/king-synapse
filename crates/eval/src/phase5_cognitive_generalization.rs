use crate::phase5_cognitive_policy::{
    build_fixture, evaluate_policy, evaluate_policy_with_included_factors, load_benchmark_from,
    CognitivePolicyBenchmarkSummary, CognitivePolicyMetrics, CognitivePolicyResult, Fixture,
    PolicySpec,
};
use anyhow::{ensure, Context, Result};
use chrono::Utc;
use serde::Serialize;
use sha2::{Digest, Sha256};
use std::{
    collections::{BTreeMap, BTreeSet},
    fs,
    path::{Path, PathBuf},
};
use synapse_core::CognitiveFactorType;

const SCHEMA_VERSION: u32 = 1;
const EVALUATION_VERSION: &str = "phase5.3.4-cognitive-generalization-validation-v1";
const POLICY_SOURCE: &str = "phase5.3.3-margin-guard-controlled-benchmark-leader";
const METADATA_ALPHA: f64 = 0.20;
const RECENCY_ALPHA: f64 = 0.20;
const MARGIN_GUARD_ALPHA: f64 = 0.20;
const MARGIN_GUARD_THRESHOLD: f64 = 0.08;
const EPSILON: f64 = 1e-12;
const REQUIRED_SPLITS: [(&str, usize); 3] = [("train", 30), ("validation", 12), ("test", 21)];
const REQUIRED_CATEGORIES: [&str; 7] = [
    "temporal_update",
    "failure_override",
    "reliability_conflict",
    "semantic_trap",
    "preference_evolution",
    "contradiction",
    "no_intervention",
];

pub struct Phase5CognitiveGeneralizationEvaluator;

impl Phase5CognitiveGeneralizationEvaluator {
    pub fn evaluate(tag: impl Into<String>) -> Result<Phase5CognitiveGeneralizationReport> {
        evaluate_generalization(tag.into())
    }
}

fn evaluate_generalization(tag: String) -> Result<Phase5CognitiveGeneralizationReport> {
    let root = dataset_root();
    let mut split_reports = Vec::new();
    let mut split_ids = BTreeMap::<String, BTreeSet<String>>::new();
    let mut all_label_mappings_stable = true;
    let mut all_hits_unchanged = true;
    let mut all_stores_unchanged = true;

    for (split, expected_count) in REQUIRED_SPLITS {
        let dir = root.join(split);
        let specs = load_benchmark_from(&dir)
            .with_context(|| format!("loading Phase 5.3.4 {split} split"))?;
        ensure!(
            specs.len() == expected_count,
            "{split} split must contain exactly {expected_count} scenarios"
        );
        ensure_categories(&specs, split)?;
        let ids = specs
            .iter()
            .map(|spec| spec.id.clone())
            .collect::<BTreeSet<_>>();
        ensure!(
            ids.len() == specs.len(),
            "duplicate scenario id in {split} split"
        );
        split_ids.insert(split.to_string(), ids);

        let fixtures = specs
            .into_iter()
            .map(build_fixture)
            .collect::<Result<Vec<_>>>()?;
        all_label_mappings_stable &= fixtures.iter().all(Fixture::label_mapping_is_bijective);
        all_hits_unchanged &= fixtures.iter().all(Fixture::hits_unchanged);
        all_stores_unchanged &= fixtures.iter().all(Fixture::store_unchanged);
        split_reports.push(evaluate_split(split, &dir, &fixtures)?);
    }

    let split_ids_disjoint = split_ids_are_disjoint(&split_ids);
    ensure!(
        split_ids_disjoint,
        "train/validation/test scenario ids must be disjoint"
    );

    let hidden = split_reports
        .iter()
        .find(|split| split.split == "test")
        .context("missing hidden test split")?;
    let decision = generalization_decision(hidden)?;
    let hidden_fixtures = load_benchmark_from(&root.join("test"))?
        .into_iter()
        .map(build_fixture)
        .collect::<Result<Vec<_>>>()?;
    all_label_mappings_stable &= hidden_fixtures
        .iter()
        .all(Fixture::label_mapping_is_bijective);
    all_hits_unchanged &= hidden_fixtures.iter().all(Fixture::hits_unchanged);
    all_stores_unchanged &= hidden_fixtures.iter().all(Fixture::store_unchanged);
    let interactions = evaluate_interactions(&hidden_fixtures)?;

    let all_deterministic = split_reports.iter().all(|split| {
        split
            .policies
            .iter()
            .all(|policy| (policy.metrics.determinism - 1.0).abs() <= EPSILON)
    }) && interactions
        .iter()
        .all(|interaction| (interaction.metrics.determinism - 1.0).abs() <= EPSILON);
    let all_bounded = split_reports.iter().all(|split| {
        split
            .policies
            .iter()
            .all(|policy| (policy.metrics.bounded_rate - 1.0).abs() <= EPSILON)
    }) && interactions
        .iter()
        .all(|interaction| (interaction.metrics.bounded_rate - 1.0).abs() <= EPSILON);

    let candidate_pool_preserved = split_reports.iter().all(|split| {
        split
            .policies
            .iter()
            .all(|policy| policy.candidate_pool_preserved)
    });
    let runtime_applied = split_reports
        .iter()
        .flat_map(|split| &split.policies)
        .any(|policy| policy.runtime_applied);

    let guards = GeneralizationSafetyGuards {
        eval_only: true,
        shadow_only: true,
        baseline_authoritative: true,
        fixed_policy_parameters: true,
        policy_locked_before_hidden_test: true,
        split_ids_disjoint,
        hidden_test_used_for_tuning: false,
        runtime_applied,
        fixture_setup_writes: true,
        policy_memory_written: false,
        memory_mutated: !all_stores_unchanged,
        ranking_mutated: !all_hits_unchanged,
        scores_mutated: !all_hits_unchanged,
        activation_changed: !all_hits_unchanged,
        candidate_pool_changed: !candidate_pool_preserved,
        recall_engine_integrated: false,
        production_claim_authorized: false,
        end_to_end_claim_authorized: false,
    };

    let pass = split_reports.len() == REQUIRED_SPLITS.len()
        && split_ids_disjoint
        && all_label_mappings_stable
        && all_deterministic
        && all_bounded
        && !guards.runtime_applied
        && !guards.policy_memory_written
        && !guards.memory_mutated
        && !guards.ranking_mutated
        && !guards.scores_mutated
        && !guards.activation_changed
        && !guards.candidate_pool_changed
        && !guards.recall_engine_integrated
        && !guards.production_claim_authorized
        && !guards.end_to_end_claim_authorized;

    Ok(Phase5CognitiveGeneralizationReport {
        schema_version: SCHEMA_VERSION,
        tag,
        phase: "Phase 5.3.4 Generalization Validation".to_string(),
        mode: "offline_shadow_locked_policy_validation".to_string(),
        evaluation_version: EVALUATION_VERSION.to_string(),
        generated_at: Utc::now().to_rfc3339(),
        policy_lock: PolicyLockReport {
            source: POLICY_SOURCE.to_string(),
            margin_guard_alpha: MARGIN_GUARD_ALPHA,
            margin_guard_threshold: MARGIN_GUARD_THRESHOLD,
            metadata_alpha: METADATA_ALPHA,
            recency_alpha: RECENCY_ALPHA,
            locked_before_hidden_test: true,
            hidden_test_parameter_search_performed: false,
        },
        splits: split_reports,
        hidden_test_decision: decision,
        factor_interactions: interactions,
        guards,
        pass,
        status: if pass { "PASS" } else { "FAIL" }.to_string(),
        conclusion: "This validates a locked conditional-authority policy on a disjoint controlled hidden fixture. It does not establish end-to-end retrieval or production improvement."
            .to_string(),
    })
}

fn evaluate_split(
    split: &str,
    dir: &Path,
    fixtures: &[Fixture],
) -> Result<GeneralizationSplitReport> {
    let policies = [
        PolicySpec::Baseline,
        PolicySpec::MetadataConfidence {
            alpha: METADATA_ALPHA,
        },
        PolicySpec::Recency {
            alpha: RECENCY_ALPHA,
        },
        PolicySpec::MarginGuard {
            alpha: MARGIN_GUARD_ALPHA,
            threshold: MARGIN_GUARD_THRESHOLD,
        },
    ]
    .iter()
    .map(|policy| evaluate_policy(policy, fixtures, None).map(policy_summary))
    .collect::<Result<Vec<_>>>()?;

    let specs = load_benchmark_from(dir)?;
    let category_counts = specs.iter().fold(BTreeMap::new(), |mut counts, spec| {
        *counts.entry(spec.category.clone()).or_insert(0) += 1;
        counts
    });
    let summary = CognitivePolicyBenchmarkSummary {
        dataset_path: relative_dataset_path(dir),
        scenarios: specs.len(),
        candidates: specs.iter().map(|scenario| scenario.memory.len()).sum(),
        categories: category_counts,
        required_categories: REQUIRED_CATEGORIES
            .iter()
            .map(|value| value.to_string())
            .collect(),
        intervention_required_scenarios: specs
            .iter()
            .filter(|scenario| scenario.intervention_required)
            .count(),
        no_intervention_scenarios: specs
            .iter()
            .filter(|scenario| !scenario.intervention_required)
            .count(),
        label_mapping_stable: fixtures.iter().all(Fixture::label_mapping_is_bijective),
    };

    Ok(GeneralizationSplitReport {
        split: split.to_string(),
        role: match split {
            "train" => "development_reference",
            "validation" => "policy_selection_audit",
            _ => "sealed_hidden_generalization_test",
        }
        .to_string(),
        dataset_sha256: hash_directory(dir)?,
        benchmark: summary,
        policies,
    })
}

fn policy_summary(result: CognitivePolicyResult) -> GeneralizationPolicySummary {
    let candidate_pool_preserved = result
        .scenario_reports
        .iter()
        .all(|scenario| scenario.candidate_pool_preserved);
    let runtime_applied = result
        .scenario_reports
        .iter()
        .any(|scenario| scenario.runtime_applied);
    GeneralizationPolicySummary {
        policy: result.policy,
        family: result.family,
        alpha: result.alpha,
        margin_threshold: result.margin_threshold,
        candidate_pool_preserved,
        runtime_applied,
        metrics: result.metrics,
    }
}

fn generalization_decision(hidden: &GeneralizationSplitReport) -> Result<GeneralizationDecision> {
    let retrieval = hidden.policy("retrieval_baseline")?;
    let metadata = hidden.policy_family("metadata_confidence")?;
    let recency = hidden.policy_family("recency_boost")?;
    let margin = hidden.policy_family("margin_guard")?;
    let beats_retrieval = margin.metrics.policy_mrr > retrieval.metrics.policy_mrr + EPSILON;
    let beats_metadata = margin.metrics.policy_mrr > metadata.metrics.policy_mrr + EPSILON;
    let beats_recency = margin.metrics.policy_mrr > recency.metrics.policy_mrr + EPSILON;
    let safety_preserved = margin.metrics.unnecessary_intervention_rate <= EPSILON
        && margin.metrics.catastrophic_regression_rate <= EPSILON;
    let intervention_quality =
        margin.metrics.intervention_precision >= 0.80 && margin.metrics.intervention_recall >= 0.80;
    Ok(GeneralizationDecision {
        hidden_margin_guard_mrr: margin.metrics.policy_mrr,
        hidden_retrieval_mrr: retrieval.metrics.policy_mrr,
        hidden_metadata_mrr: metadata.metrics.policy_mrr,
        hidden_recency_mrr: recency.metrics.policy_mrr,
        beats_retrieval,
        beats_metadata,
        beats_recency,
        safety_preserved,
        intervention_quality,
        controlled_generalization_supported: beats_retrieval
            && beats_metadata
            && beats_recency
            && safety_preserved
            && intervention_quality,
        runtime_authorization: false,
        end_to_end_generalization_proven: false,
    })
}

fn evaluate_interactions(fixtures: &[Fixture]) -> Result<Vec<FactorInteractionReport>> {
    let policy = PolicySpec::MarginGuard {
        alpha: MARGIN_GUARD_ALPHA,
        threshold: MARGIN_GUARD_THRESHOLD,
    };
    interaction_specs()
        .into_iter()
        .map(|(name, factors)| {
            let result = evaluate_policy_with_included_factors(&policy, fixtures, &factors)?;
            Ok(FactorInteractionReport {
                name: name.to_string(),
                included_factors: factors.iter().map(|factor| format!("{factor:?}")).collect(),
                metrics: result.metrics,
            })
        })
        .collect()
}

fn interaction_specs() -> Vec<(&'static str, Vec<CognitiveFactorType>)> {
    use CognitiveFactorType::{
        ContextAlignment, FailureEvidence, PreferenceAlignment, Reliability, TemporalConfidence,
    };
    vec![
        (
            "full_cognitive",
            vec![
                TemporalConfidence,
                Reliability,
                FailureEvidence,
                PreferenceAlignment,
                ContextAlignment,
            ],
        ),
        (
            "failure_plus_temporal",
            vec![FailureEvidence, TemporalConfidence],
        ),
        (
            "failure_plus_reliability",
            vec![FailureEvidence, Reliability],
        ),
        (
            "temporal_plus_preference",
            vec![TemporalConfidence, PreferenceAlignment],
        ),
        ("failure_only", vec![FailureEvidence]),
        (
            "temporal_plus_reliability",
            vec![TemporalConfidence, Reliability],
        ),
        (
            "context_plus_preference",
            vec![ContextAlignment, PreferenceAlignment],
        ),
    ]
}

fn ensure_categories(
    specs: &[crate::phase5_cognitive_policy::CognitivePolicyScenarioSpec],
    split: &str,
) -> Result<()> {
    let categories = specs
        .iter()
        .map(|scenario| scenario.category.as_str())
        .collect::<BTreeSet<_>>();
    for category in REQUIRED_CATEGORIES {
        ensure!(
            categories.contains(category),
            "{split} split is missing category {category}"
        );
    }
    Ok(())
}

fn split_ids_are_disjoint(splits: &BTreeMap<String, BTreeSet<String>>) -> bool {
    let mut observed = BTreeSet::new();
    for ids in splits.values() {
        for id in ids {
            if !observed.insert(id.clone()) {
                return false;
            }
        }
    }
    true
}

fn hash_directory(dir: &Path) -> Result<String> {
    let mut paths = fs::read_dir(dir)?
        .map(|entry| entry.map(|entry| entry.path()))
        .collect::<std::io::Result<Vec<_>>>()?;
    paths.retain(|path| path.extension().and_then(|value| value.to_str()) == Some("toml"));
    paths.sort();
    let mut hasher = Sha256::new();
    for path in paths {
        hasher.update(
            path.file_name()
                .context("dataset file name")?
                .to_string_lossy()
                .as_bytes(),
        );
        hasher.update([0]);
        hasher.update(fs::read(path)?);
        hasher.update([0]);
    }
    Ok(format!("{:x}", hasher.finalize()))
}

fn dataset_root() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("datasets")
        .join("cognitive_policy_generalization")
}

fn relative_dataset_path(dir: &Path) -> String {
    dir.strip_prefix(Path::new(env!("CARGO_MANIFEST_DIR")))
        .map(|path| format!("crates/eval/{}", path.display()).replace('\\', "/"))
        .unwrap_or_else(|_| dir.display().to_string())
}

impl GeneralizationSplitReport {
    fn policy(&self, name: &str) -> Result<&GeneralizationPolicySummary> {
        self.policies
            .iter()
            .find(|policy| policy.policy == name)
            .with_context(|| format!("missing policy {name} in {} split", self.split))
    }

    fn policy_family(&self, family: &str) -> Result<&GeneralizationPolicySummary> {
        self.policies
            .iter()
            .find(|policy| policy.family == family)
            .with_context(|| format!("missing policy family {family} in {} split", self.split))
    }
}

#[derive(Debug, Clone, Serialize)]
pub struct PolicyLockReport {
    pub source: String,
    pub margin_guard_alpha: f64,
    pub margin_guard_threshold: f64,
    pub metadata_alpha: f64,
    pub recency_alpha: f64,
    pub locked_before_hidden_test: bool,
    pub hidden_test_parameter_search_performed: bool,
}

#[derive(Debug, Clone, Serialize)]
pub struct GeneralizationPolicySummary {
    pub policy: String,
    pub family: String,
    pub alpha: Option<f64>,
    pub margin_threshold: Option<f64>,
    pub candidate_pool_preserved: bool,
    pub runtime_applied: bool,
    pub metrics: CognitivePolicyMetrics,
}

#[derive(Debug, Clone, Serialize)]
pub struct GeneralizationSplitReport {
    pub split: String,
    pub role: String,
    pub dataset_sha256: String,
    pub benchmark: CognitivePolicyBenchmarkSummary,
    pub policies: Vec<GeneralizationPolicySummary>,
}

#[derive(Debug, Clone, Serialize)]
pub struct GeneralizationDecision {
    pub hidden_margin_guard_mrr: f64,
    pub hidden_retrieval_mrr: f64,
    pub hidden_metadata_mrr: f64,
    pub hidden_recency_mrr: f64,
    pub beats_retrieval: bool,
    pub beats_metadata: bool,
    pub beats_recency: bool,
    pub safety_preserved: bool,
    pub intervention_quality: bool,
    pub controlled_generalization_supported: bool,
    pub runtime_authorization: bool,
    pub end_to_end_generalization_proven: bool,
}

#[derive(Debug, Clone, Serialize)]
pub struct FactorInteractionReport {
    pub name: String,
    pub included_factors: Vec<String>,
    pub metrics: CognitivePolicyMetrics,
}

#[derive(Debug, Clone, Serialize)]
pub struct GeneralizationSafetyGuards {
    pub eval_only: bool,
    pub shadow_only: bool,
    pub baseline_authoritative: bool,
    pub fixed_policy_parameters: bool,
    pub policy_locked_before_hidden_test: bool,
    pub split_ids_disjoint: bool,
    pub hidden_test_used_for_tuning: bool,
    pub runtime_applied: bool,
    pub fixture_setup_writes: bool,
    pub policy_memory_written: bool,
    pub memory_mutated: bool,
    pub ranking_mutated: bool,
    pub scores_mutated: bool,
    pub activation_changed: bool,
    pub candidate_pool_changed: bool,
    pub recall_engine_integrated: bool,
    pub production_claim_authorized: bool,
    pub end_to_end_claim_authorized: bool,
}

#[derive(Debug, Clone, Serialize)]
pub struct Phase5CognitiveGeneralizationReport {
    pub schema_version: u32,
    pub tag: String,
    pub phase: String,
    pub mode: String,
    pub evaluation_version: String,
    pub generated_at: String,
    pub policy_lock: PolicyLockReport,
    pub splits: Vec<GeneralizationSplitReport>,
    pub hidden_test_decision: GeneralizationDecision,
    pub factor_interactions: Vec<FactorInteractionReport>,
    pub guards: GeneralizationSafetyGuards,
    pub pass: bool,
    pub status: String,
    pub conclusion: String,
}
