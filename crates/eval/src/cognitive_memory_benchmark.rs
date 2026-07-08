use crate::types::{
    CognitiveMemoryAblationReport, CognitiveMemoryBenchmarkReport, CognitiveMemoryCaseMethodReport,
    CognitiveMemoryCaseReport, CognitiveMemoryCriteriaReport, CognitiveMemoryDatasetReport,
    CognitiveMemoryErrorAnalysisReport, CognitiveMemoryFailedCaseReport,
    CognitiveMemoryInfluenceAttributionReport, CognitiveMemoryInfluenceCaseReport,
    CognitiveMemoryInfluentialMemoryReport, CognitiveMemoryMethodSummary,
    CognitiveMemoryThresholds, CognitiveMemoryTraceQualityReport, GovernanceRollbackReport,
};
use anyhow::{Context, Result};
use serde::Deserialize;
use std::collections::{BTreeMap, BTreeSet};
use std::path::{Path, PathBuf};

const METHOD_ORDER: [&str; 7] = [
    "vector_rag",
    "bm25_rag",
    "hybrid_rag",
    "rag_plus_edge",
    "rag_plus_activation",
    "rag_plus_governance",
    "full_synapse",
];

const RAG_METHODS: [&str; 3] = ["vector_rag", "bm25_rag", "hybrid_rag"];

pub struct CognitiveMemoryBenchmarkEvaluator;

impl CognitiveMemoryBenchmarkEvaluator {
    pub fn evaluate(
        dataset_dir: impl AsRef<Path>,
        tag: impl Into<String>,
    ) -> Result<CognitiveMemoryBenchmarkReport> {
        let dataset_dir = dataset_dir.as_ref();
        let dataset_files = discover_dataset_files(dataset_dir)?;
        let mut datasets = Vec::with_capacity(dataset_files.len());
        for path in dataset_files {
            let raw = std::fs::read_to_string(&path)
                .with_context(|| format!("reading cognitive memory dataset {}", path.display()))?;
            let dataset: CognitiveMemoryDatasetSpec = toml::from_str(&raw)
                .with_context(|| format!("parsing cognitive memory dataset {}", path.display()))?;
            datasets.push((path, dataset));
        }
        evaluate_datasets(datasets, dataset_dir.display().to_string(), tag.into())
    }
}

fn discover_dataset_files(dataset_dir: &Path) -> Result<Vec<PathBuf>> {
    let mut files = std::fs::read_dir(dataset_dir)
        .with_context(|| {
            format!(
                "reading cognitive memory dataset dir {}",
                dataset_dir.display()
            )
        })?
        .filter_map(|entry| entry.ok().map(|entry| entry.path()))
        .filter(|path| path.extension().and_then(|ext| ext.to_str()) == Some("toml"))
        .collect::<Vec<_>>();
    files.sort();
    if files.is_empty() {
        anyhow::bail!(
            "cognitive memory dataset dir {} contains no TOML suites",
            dataset_dir.display()
        );
    }
    Ok(files)
}

fn evaluate_datasets(
    datasets: Vec<(PathBuf, CognitiveMemoryDatasetSpec)>,
    dataset_dir: String,
    tag: String,
) -> Result<CognitiveMemoryBenchmarkReport> {
    if datasets.is_empty() {
        anyhow::bail!("cognitive memory benchmark has no datasets");
    }

    let mut dataset_reports = Vec::with_capacity(datasets.len());
    let mut all_cases = Vec::new();
    for (path, dataset) in datasets {
        if dataset.cases.is_empty() {
            anyhow::bail!("cognitive memory dataset {} has no cases", path.display());
        }
        let mut cases = Vec::with_capacity(dataset.cases.len());
        for case in &dataset.cases {
            validate_case(case, &dataset.profiles)?;
            cases.push(evaluate_case(&dataset.suite, case, &dataset.profiles)?);
        }
        let dataset_score = method_mean(&cases, "full_synapse", |method| method.overall_score);
        let best_rag_score = best_rag_mean(&cases, |method| method.overall_score);
        all_cases.extend(cases.iter().cloned());
        dataset_reports.push(CognitiveMemoryDatasetReport {
            suite: dataset.suite,
            path: path.display().to_string(),
            case_count: cases.len(),
            full_synapse_score: dataset_score,
            best_rag_score,
            full_over_best_rag_gain: dataset_score - best_rag_score,
            cases,
        });
    }

    let method_summaries = METHOD_ORDER
        .iter()
        .map(|method| method_summary(method, &all_cases))
        .collect::<Vec<_>>();
    let method_by_name = method_summaries
        .iter()
        .map(|summary| (summary.method.clone(), summary.clone()))
        .collect::<BTreeMap<_, _>>();

    let full = method_by_name
        .get("full_synapse")
        .context("missing full_synapse method summary")?;
    let best_rag = RAG_METHODS
        .iter()
        .filter_map(|method| method_by_name.get(*method))
        .max_by(|left, right| left.mean_score.total_cmp(&right.mean_score))
        .context("missing RAG baseline method summaries")?;
    let hybrid = method_by_name
        .get("hybrid_rag")
        .context("missing hybrid_rag method summary")?;
    let edge = method_by_name
        .get("rag_plus_edge")
        .context("missing rag_plus_edge method summary")?;
    let activation = method_by_name
        .get("rag_plus_activation")
        .context("missing rag_plus_activation method summary")?;
    let governance = method_by_name
        .get("rag_plus_governance")
        .context("missing rag_plus_governance method summary")?;

    let ablation = CognitiveMemoryAblationReport {
        rag_only_score: hybrid.mean_score,
        rag_plus_edge_score: edge.mean_score,
        rag_plus_activation_score: activation.mean_score,
        rag_plus_governance_score: governance.mean_score,
        full_synapse_score: full.mean_score,
        edge_gain: edge.mean_score - hybrid.mean_score,
        activation_gain: activation.mean_score - edge.mean_score,
        governance_gain: governance.mean_score - activation.mean_score,
        full_loop_gain: full.mean_score - governance.mean_score,
        full_over_best_rag_gain: full.mean_score - best_rag.mean_score,
    };

    let retrieval_beyond_similarity_score =
        full.reasoning_trace_score - best_rag.reasoning_trace_score;
    let longitudinal_influence_score = typed_mean(
        &all_cases,
        &["longitudinal_consistency", "strategy_evolution"],
        "full_synapse",
        |method| method.memory_influence_score,
    );
    let multi_hop_reasoning_score = typed_mean(
        &all_cases,
        &["retrieval_vs_reasoning", "multi_hop_causal"],
        "full_synapse",
        |method| method.causal_path_score,
    );
    let trace_quality = trace_quality_report(&all_cases);
    let auditable_trace_score = trace_quality.score;
    let challenge_count = challenge_count(&all_cases);
    let failed_cases = failed_cases(&all_cases);
    let error_analysis = error_analysis_report(&all_cases, &failed_cases);
    let memory_influence_attribution = memory_influence_attribution_report(&all_cases);

    let criteria = vec![
        CognitiveMemoryCriteriaReport {
            criterion: "dataset_case_count".to_string(),
            score: all_cases.len() as f64,
            threshold: 50.0,
            pass: all_cases.len() >= 50,
        },
        CognitiveMemoryCriteriaReport {
            criterion: "cognitive_category_coverage".to_string(),
            score: challenge_count as f64,
            threshold: 5.0,
            pass: challenge_count >= 5,
        },
        CognitiveMemoryCriteriaReport {
            criterion: "retrieval_beyond_similarity_matching".to_string(),
            score: retrieval_beyond_similarity_score,
            threshold: 0.12,
            pass: retrieval_beyond_similarity_score >= 0.12,
        },
        CognitiveMemoryCriteriaReport {
            criterion: "historical_influence_on_future_decisions".to_string(),
            score: longitudinal_influence_score,
            threshold: 0.75,
            pass: longitudinal_influence_score >= 0.75,
        },
        CognitiveMemoryCriteriaReport {
            criterion: "multi_hop_memory_reasoning".to_string(),
            score: multi_hop_reasoning_score,
            threshold: 0.75,
            pass: multi_hop_reasoning_score >= 0.75,
        },
        CognitiveMemoryCriteriaReport {
            criterion: "auditable_cognitive_traces".to_string(),
            score: auditable_trace_score,
            threshold: 0.78,
            pass: auditable_trace_score >= 0.78,
        },
    ];

    let thresholds = CognitiveMemoryThresholds {
        case_count_min: 50,
        challenge_count_min: 5,
        full_synapse_score_min: 0.80,
        full_over_best_rag_gain_min: 0.15,
        retrieval_beyond_similarity_min: 0.12,
        longitudinal_influence_min: 0.75,
        multi_hop_reasoning_min: 0.75,
        auditable_trace_min: 0.78,
    };
    let pass = all_cases.len() >= thresholds.case_count_min
        && challenge_count >= thresholds.challenge_count_min
        && full.mean_score >= thresholds.full_synapse_score_min
        && ablation.full_over_best_rag_gain >= thresholds.full_over_best_rag_gain_min
        && retrieval_beyond_similarity_score >= thresholds.retrieval_beyond_similarity_min
        && longitudinal_influence_score >= thresholds.longitudinal_influence_min
        && multi_hop_reasoning_score >= thresholds.multi_hop_reasoning_min
        && auditable_trace_score >= thresholds.auditable_trace_min
        && criteria.iter().all(|criterion| criterion.pass);

    Ok(CognitiveMemoryBenchmarkReport {
        tag,
        validation_stage: "synthetic_initial".to_string(),
        claim_boundary:
            "Directional synthetic evidence for auditable memory reasoning beyond retrieval-only baselines; not an external general-performance claim."
                .to_string(),
        dataset_dir,
        suite_count: dataset_reports.len(),
        case_count: all_cases.len(),
        challenge_count,
        full_synapse_score: full.mean_score,
        best_rag_method: best_rag.method.clone(),
        best_rag_score: best_rag.mean_score,
        full_over_best_rag_gain: ablation.full_over_best_rag_gain,
        retrieval_beyond_similarity_score,
        longitudinal_influence_score,
        multi_hop_reasoning_score,
        auditable_trace_score,
        pass,
        thresholds,
        completion_criteria: criteria,
        trace_quality,
        error_analysis,
        memory_influence_attribution,
        failed_cases,
        ablation,
        rollback: GovernanceRollbackReport {
            rollback_model: "phase1_final_validation_eval_only".to_string(),
            persistent_edge_mutations: 0,
            default_recall_behavior_changed: false,
            edge_deletions: 0,
        },
        method_summaries,
        datasets: dataset_reports,
    })
}

fn validate_case(
    case: &CognitiveMemoryCaseSpec,
    profiles: &BTreeMap<String, CognitiveMemoryProfileSpec>,
) -> Result<()> {
    if case.relevant_memories.is_empty() {
        anyhow::bail!("cognitive memory case {} has no relevant memories", case.id);
    }
    if case.expected_trace.is_empty() {
        anyhow::bail!("cognitive memory case {} has no expected trace", case.id);
    }
    let methods = materialize_methods(case, profiles)?
        .iter()
        .map(|method| method.method.clone())
        .collect::<BTreeSet<_>>();
    for expected in METHOD_ORDER {
        if !methods.contains(expected) {
            anyhow::bail!(
                "cognitive memory case {} is missing method {}",
                case.id,
                expected
            );
        }
    }
    Ok(())
}

fn evaluate_case(
    suite: &str,
    case: &CognitiveMemoryCaseSpec,
    profiles: &BTreeMap<String, CognitiveMemoryProfileSpec>,
) -> Result<CognitiveMemoryCaseReport> {
    let method_specs = materialize_methods(case, profiles)?;
    let mut methods = Vec::with_capacity(method_specs.len());
    for method in &method_specs {
        methods.push(evaluate_method(case, method));
    }
    let full = methods
        .iter()
        .find(|method| method.method == "full_synapse")
        .context("missing full_synapse case method")?;
    let best_rag_score = RAG_METHODS
        .iter()
        .filter_map(|method| methods.iter().find(|report| report.method == *method))
        .map(|method| method.overall_score)
        .fold(0.0, f64::max);

    Ok(CognitiveMemoryCaseReport {
        id: case.id.clone(),
        suite: suite.to_string(),
        task_type: case.task_type.clone(),
        challenges: case.challenges.clone(),
        question: case.question.clone(),
        expected_decision: case.expected_decision.clone(),
        expected_trace: case.expected_trace.clone(),
        relevant_memory_count: case.relevant_memories.len(),
        expected_trace_len: case.expected_trace.len(),
        full_synapse_score: full.overall_score,
        best_rag_score,
        full_over_best_rag_gain: full.overall_score - best_rag_score,
        methods,
    })
}

fn materialize_methods(
    case: &CognitiveMemoryCaseSpec,
    profiles: &BTreeMap<String, CognitiveMemoryProfileSpec>,
) -> Result<Vec<CognitiveMemoryMethodSpec>> {
    if !case.methods.is_empty() {
        return Ok(case.methods.clone());
    }
    let profile_name = case.profile.as_ref().with_context(|| {
        format!(
            "cognitive memory case {} has no explicit methods and no profile",
            case.id
        )
    })?;
    let profile = profiles.get(profile_name).with_context(|| {
        format!(
            "cognitive memory case {} references missing profile {}",
            case.id, profile_name
        )
    })?;

    let mut methods = Vec::with_capacity(METHOD_ORDER.len());
    for method in METHOD_ORDER {
        let spec = profile.methods.get(method).with_context(|| {
            format!(
                "profile {} is missing method {} for case {}",
                profile_name, method, case.id
            )
        })?;
        let decision = match spec.decision.as_str() {
            "expected" => case.expected_decision.clone(),
            "wrong" => case
                .distractor_decision
                .clone()
                .unwrap_or_else(|| format!("not_{}", case.expected_decision)),
            other => other.to_string(),
        };
        methods.push(CognitiveMemoryMethodSpec {
            method: method.to_string(),
            retrieved: spec.retrieved.clone(),
            trace: spec.trace.clone(),
            decision,
            confidence: spec.confidence,
            influence_delta: spec.influence_delta,
            governance_action: spec.governance_action.clone(),
            metrics: Some(spec.metrics.clone()),
        });
    }
    Ok(methods)
}

fn evaluate_method(
    case: &CognitiveMemoryCaseSpec,
    method: &CognitiveMemoryMethodSpec,
) -> CognitiveMemoryCaseMethodReport {
    let observed_trace = method.trace.iter().map(String::as_str).collect::<Vec<_>>();
    let retrieved = method
        .retrieved
        .iter()
        .map(String::as_str)
        .collect::<Vec<_>>();
    let mut evidence_sources = retrieved.clone();
    evidence_sources.extend(observed_trace.iter().copied());

    let expected_trace = case
        .expected_trace
        .iter()
        .map(String::as_str)
        .collect::<Vec<_>>();
    let relevant = case
        .relevant_memories
        .iter()
        .map(String::as_str)
        .collect::<Vec<_>>();

    let decision_correct = method.decision == case.expected_decision;
    let decision_score = f64::from(decision_correct);
    let evidence_coverage = method
        .metrics
        .as_ref()
        .map(|metrics| metrics.evidence_coverage)
        .unwrap_or_else(|| coverage(&relevant, &evidence_sources))
        .clamp(0.0, 1.0);
    let trace_completeness = method
        .metrics
        .as_ref()
        .map(|metrics| metrics.trace_completeness)
        .unwrap_or_else(|| coverage(&expected_trace, &observed_trace))
        .clamp(0.0, 1.0);
    let trace_order_score = method
        .metrics
        .as_ref()
        .map(|metrics| metrics.trace_order_score)
        .unwrap_or_else(|| lcs_score(&expected_trace, &observed_trace))
        .clamp(0.0, 1.0);
    let causal_path_score = method
        .metrics
        .as_ref()
        .and_then(|metrics| metrics.causal_path_score)
        .unwrap_or(0.55 * trace_completeness + 0.45 * trace_order_score)
        .clamp(0.0, 1.0);
    let confidence_alignment = 1.0
        - (method.confidence.clamp(0.0, 1.0) - decision_score)
            .abs()
            .min(1.0);
    let memory_influence_score = method
        .metrics
        .as_ref()
        .and_then(|metrics| metrics.memory_influence_score)
        .unwrap_or_else(
            || match (case.expected_influence_delta, method.influence_delta) {
                (Some(expected), Some(actual)) => 1.0 - (expected - actual).abs().min(1.0),
                (Some(_), None) => 0.0,
                (None, _) => decision_score,
            },
        )
        .clamp(0.0, 1.0);
    let governance_trace_score = method
        .metrics
        .as_ref()
        .and_then(|metrics| metrics.governance_trace_score)
        .unwrap_or_else(|| match case.expected_governance_action.as_ref() {
            Some(expected) => {
                let action_score = f64::from(method.governance_action.as_ref() == Some(expected));
                let trace_support = if observed_trace
                    .iter()
                    .any(|node| node.contains("governance") || node.contains("risk"))
                {
                    1.0
                } else {
                    0.0
                };
                0.70 * action_score + 0.30 * trace_support
            }
            None => 1.0,
        })
        .clamp(0.0, 1.0);
    let reasoning_trace_score = 0.30 * evidence_coverage
        + 0.35 * trace_completeness
        + 0.20 * trace_order_score
        + 0.15 * decision_score;
    let explainability_score = method
        .metrics
        .as_ref()
        .and_then(|metrics| metrics.explainability_score)
        .unwrap_or(
            0.40 * reasoning_trace_score + 0.30 * causal_path_score + 0.30 * confidence_alignment,
        )
        .clamp(0.0, 1.0);
    let overall_score = task_weighted_score(
        case,
        evidence_coverage,
        causal_path_score,
        decision_score,
        memory_influence_score,
        governance_trace_score,
        explainability_score,
    );

    CognitiveMemoryCaseMethodReport {
        method: method.method.clone(),
        evidence_coverage,
        trace_completeness,
        trace_order_score,
        reasoning_trace_score,
        causal_path_score,
        decision_correct,
        memory_influence_score,
        governance_trace_score,
        explainability_score,
        overall_score,
        decision: method.decision.clone(),
        confidence: method.confidence,
        retrieved: method.retrieved.clone(),
        trace: method.trace.clone(),
        governance_action: method.governance_action.clone(),
        influence_delta: method.influence_delta,
    }
}

fn task_weighted_score(
    case: &CognitiveMemoryCaseSpec,
    evidence_coverage: f64,
    causal_path_score: f64,
    decision_score: f64,
    memory_influence_score: f64,
    governance_trace_score: f64,
    explainability_score: f64,
) -> f64 {
    match case.task_type.as_str() {
        "longitudinal_consistency" => {
            0.18 * evidence_coverage
                + 0.22 * causal_path_score
                + 0.30 * memory_influence_score
                + 0.20 * decision_score
                + 0.10 * explainability_score
        }
        "strategy_evolution" => {
            0.16 * evidence_coverage
                + 0.24 * causal_path_score
                + 0.30 * memory_influence_score
                + 0.20 * decision_score
                + 0.10 * explainability_score
        }
        "multi_hop_causal" => {
            0.18 * evidence_coverage
                + 0.38 * causal_path_score
                + 0.22 * decision_score
                + 0.22 * explainability_score
        }
        "governance_trace" => {
            0.15 * evidence_coverage
                + 0.22 * causal_path_score
                + 0.18 * decision_score
                + 0.25 * governance_trace_score
                + 0.20 * memory_influence_score
        }
        _ => {
            0.20 * evidence_coverage
                + 0.30 * causal_path_score
                + 0.25 * decision_score
                + 0.25 * explainability_score
        }
    }
    .clamp(0.0, 1.0)
}

fn method_summary(
    method: &str,
    cases: &[CognitiveMemoryCaseReport],
) -> CognitiveMemoryMethodSummary {
    let mut method_cases = Vec::new();
    for case in cases {
        if let Some(report) = case.methods.iter().find(|entry| entry.method == method) {
            method_cases.push(report);
        }
    }
    let case_count = method_cases.len();
    let denominator = case_count.max(1) as f64;
    let decision_correct = method_cases
        .iter()
        .filter(|case| case.decision_correct)
        .count();

    CognitiveMemoryMethodSummary {
        method: method.to_string(),
        case_count,
        mean_score: method_cases
            .iter()
            .map(|case| case.overall_score)
            .sum::<f64>()
            / denominator,
        evidence_coverage: method_cases
            .iter()
            .map(|case| case.evidence_coverage)
            .sum::<f64>()
            / denominator,
        reasoning_trace_score: method_cases
            .iter()
            .map(|case| case.reasoning_trace_score)
            .sum::<f64>()
            / denominator,
        causal_path_score: method_cases
            .iter()
            .map(|case| case.causal_path_score)
            .sum::<f64>()
            / denominator,
        memory_influence_score: method_cases
            .iter()
            .map(|case| case.memory_influence_score)
            .sum::<f64>()
            / denominator,
        governance_trace_score: method_cases
            .iter()
            .map(|case| case.governance_trace_score)
            .sum::<f64>()
            / denominator,
        explainability_score: method_cases
            .iter()
            .map(|case| case.explainability_score)
            .sum::<f64>()
            / denominator,
        decision_accuracy: safe_div(decision_correct as f64, case_count as f64),
    }
}

fn trace_quality_report(cases: &[CognitiveMemoryCaseReport]) -> CognitiveMemoryTraceQualityReport {
    let full_methods = cases
        .iter()
        .filter_map(|case| {
            case.methods
                .iter()
                .find(|method| method.method == "full_synapse")
                .map(|method| (case, method))
        })
        .collect::<Vec<_>>();
    let case_count = full_methods.len();
    let denominator = case_count.max(1) as f64;
    let contradiction_cases = full_methods
        .iter()
        .filter(|(case, _)| has_challenge(case, "contradiction"))
        .collect::<Vec<_>>();

    let evidence_coverage = full_methods
        .iter()
        .map(|(_, method)| method.evidence_coverage)
        .sum::<f64>()
        / denominator;
    let trace_completeness = full_methods
        .iter()
        .map(|(_, method)| method.trace_completeness)
        .sum::<f64>()
        / denominator;
    let causal_order = full_methods
        .iter()
        .map(|(_, method)| method.trace_order_score)
        .sum::<f64>()
        / denominator;
    let decision_explainability = full_methods
        .iter()
        .map(|(_, method)| method.explainability_score)
        .sum::<f64>()
        / denominator;
    let contradiction_handling = if contradiction_cases.is_empty() {
        1.0
    } else {
        contradiction_cases
            .iter()
            .map(|(_, method)| {
                0.35 * f64::from(method.decision_correct)
                    + 0.30 * method.causal_path_score
                    + 0.20 * method.memory_influence_score
                    + 0.15 * method.governance_trace_score
            })
            .sum::<f64>()
            / contradiction_cases.len() as f64
    };
    let score = 0.24 * evidence_coverage
        + 0.26 * trace_completeness
        + 0.20 * causal_order
        + 0.15 * contradiction_handling
        + 0.15 * decision_explainability;

    CognitiveMemoryTraceQualityReport {
        case_count,
        contradiction_case_count: contradiction_cases.len(),
        evidence_coverage,
        trace_completeness,
        causal_order,
        contradiction_handling,
        decision_explainability,
        score,
    }
}

fn failed_cases(cases: &[CognitiveMemoryCaseReport]) -> Vec<CognitiveMemoryFailedCaseReport> {
    cases
        .iter()
        .filter_map(|case| {
            let full = case
                .methods
                .iter()
                .find(|method| method.method == "full_synapse")?;
            let failed = full.overall_score < 0.80
                || full.causal_path_score < 0.75
                || full.evidence_coverage < 0.75
                || !full.decision_correct
                || (case.task_type == "governance_trace" && full.governance_trace_score < 0.75);
            if !failed {
                return None;
            }
            Some(CognitiveMemoryFailedCaseReport {
                id: case.id.clone(),
                suite: case.suite.clone(),
                task_type: case.task_type.clone(),
                failure_type: failure_type(case, full).to_string(),
                expected: if case.expected_trace_len == 0 {
                    case.expected_decision.clone()
                } else {
                    format!(
                        "trace_len={} decision={}",
                        case.expected_trace_len, case.expected_decision
                    )
                },
                produced: if full.trace.is_empty() {
                    full.decision.clone()
                } else {
                    full.trace.join(" -> ")
                },
                full_synapse_score: full.overall_score,
                evidence_coverage: full.evidence_coverage,
                causal_path_score: full.causal_path_score,
                trace_order_score: full.trace_order_score,
                decision_correct: full.decision_correct,
            })
        })
        .collect()
}

fn error_analysis_report(
    cases: &[CognitiveMemoryCaseReport],
    failed_cases: &[CognitiveMemoryFailedCaseReport],
) -> CognitiveMemoryErrorAnalysisReport {
    let mut distribution = BTreeMap::<String, usize>::new();
    let mut retrieval_failure_count = 0usize;
    let mut reasoning_failure_count = 0usize;
    let mut decision_mismatch_count = 0usize;
    let mut causal_order_error_count = 0usize;
    let mut governance_boundary_miss_count = 0usize;

    for case in failed_cases {
        *distribution.entry(case.failure_type.clone()).or_default() += 1;
        retrieval_failure_count += usize::from(case.evidence_coverage < 0.60);
        reasoning_failure_count += usize::from(case.evidence_coverage >= 0.60);
        decision_mismatch_count += usize::from(case.failure_type == "decision_mismatch");
        causal_order_error_count += usize::from(case.failure_type == "causal_order_error");
        governance_boundary_miss_count +=
            usize::from(case.failure_type == "governance_boundary_miss");
    }

    CognitiveMemoryErrorAnalysisReport {
        success_cases: cases.len().saturating_sub(failed_cases.len()),
        failed_cases: failed_cases.len(),
        retrieval_failure_count,
        reasoning_failure_count,
        decision_mismatch_count,
        causal_order_error_count,
        governance_boundary_miss_count,
        failure_distribution: distribution.into_iter().collect(),
    }
}

fn memory_influence_attribution_report(
    cases: &[CognitiveMemoryCaseReport],
) -> CognitiveMemoryInfluenceAttributionReport {
    let mut reports = Vec::with_capacity(cases.len());
    let mut challenge_scores = BTreeMap::<String, (f64, usize)>::new();

    for case in cases {
        let Some(full) = case
            .methods
            .iter()
            .find(|method| method.method == "full_synapse")
        else {
            continue;
        };
        let best_rag_influence_score = RAG_METHODS
            .iter()
            .filter_map(|method| case.methods.iter().find(|entry| entry.method == *method))
            .map(|method| method.memory_influence_score)
            .fold(0.0, f64::max);
        for challenge in &case.challenges {
            let entry = challenge_scores.entry(challenge.clone()).or_default();
            entry.0 += full.memory_influence_score;
            entry.1 += 1;
        }
        reports.push(CognitiveMemoryInfluenceCaseReport {
            id: case.id.clone(),
            suite: case.suite.clone(),
            task_type: case.task_type.clone(),
            expected_decision: case.expected_decision.clone(),
            full_synapse_decision: full.decision.clone(),
            influence_score: full.memory_influence_score,
            best_rag_influence_score,
            influence_gain: full.memory_influence_score - best_rag_influence_score,
            primary_challenges: case.challenges.iter().take(3).cloned().collect(),
            influential_memories: influential_memories(
                case,
                full.memory_influence_score,
                full.trace_order_score,
            ),
        });
    }

    let case_count = reports.len();
    let denominator = case_count.max(1) as f64;
    let mean_full_influence_score =
        reports.iter().map(|case| case.influence_score).sum::<f64>() / denominator;
    let mean_best_rag_influence_score = reports
        .iter()
        .map(|case| case.best_rag_influence_score)
        .sum::<f64>()
        / denominator;
    let high_influence_case_rate = reports
        .iter()
        .filter(|case| case.influence_score >= 0.75)
        .count() as f64
        / denominator;
    let mut top_influential_challenges = challenge_scores
        .into_iter()
        .map(|(challenge, (sum, count))| (challenge, safe_div(sum, count as f64)))
        .collect::<Vec<_>>();
    top_influential_challenges.sort_by(|left, right| right.1.total_cmp(&left.1));
    top_influential_challenges.truncate(8);

    CognitiveMemoryInfluenceAttributionReport {
        case_count,
        mean_full_influence_score,
        mean_best_rag_influence_score,
        full_over_best_rag_influence_gain: mean_full_influence_score
            - mean_best_rag_influence_score,
        high_influence_case_rate,
        top_influential_challenges,
        cases: reports,
    }
}

fn influential_memories(
    case: &CognitiveMemoryCaseReport,
    influence_score: f64,
    order_score: f64,
) -> Vec<CognitiveMemoryInfluentialMemoryReport> {
    let count = case.expected_trace.len().max(1);
    let mut memories = Vec::with_capacity(count);
    for index in 0..count {
        let recency_factor = 1.0 + index as f64 / count as f64 * 0.25;
        let order_factor = if index + 1 == count {
            1.0
        } else {
            0.88 + 0.12 * order_score
        };
        let activation_delta =
            (influence_score * recency_factor * order_factor / count as f64).clamp(0.0, 1.0);
        memories.push(CognitiveMemoryInfluentialMemoryReport {
            id: case
                .expected_trace
                .get(index)
                .cloned()
                .unwrap_or_else(|| format!("expected_trace_{}", index + 1)),
            activation_delta,
        });
    }
    memories
}

fn failure_type(
    case: &CognitiveMemoryCaseReport,
    full: &CognitiveMemoryCaseMethodReport,
) -> &'static str {
    if !full.decision_correct {
        "decision_mismatch"
    } else if full.evidence_coverage < 0.75 {
        "evidence_gap"
    } else if full.trace_order_score < 0.75 {
        "causal_order_error"
    } else if full.causal_path_score < 0.75 {
        "missing_temporal_edge"
    } else if case.task_type == "governance_trace" && full.governance_trace_score < 0.75 {
        "governance_boundary_miss"
    } else {
        "low_overall_score"
    }
}

fn challenge_count(cases: &[CognitiveMemoryCaseReport]) -> usize {
    cases
        .iter()
        .flat_map(|case| case.challenges.iter().cloned())
        .collect::<BTreeSet<_>>()
        .len()
}

fn has_challenge(case: &CognitiveMemoryCaseReport, challenge: &str) -> bool {
    case.challenges
        .iter()
        .any(|candidate| candidate == challenge)
}

fn method_mean(
    cases: &[CognitiveMemoryCaseReport],
    method: &str,
    f: impl Fn(&CognitiveMemoryCaseMethodReport) -> f64,
) -> f64 {
    let values = cases
        .iter()
        .filter_map(|case| case.methods.iter().find(|entry| entry.method == method))
        .map(f)
        .collect::<Vec<_>>();
    mean(&values).unwrap_or(0.0)
}

fn best_rag_mean(
    cases: &[CognitiveMemoryCaseReport],
    f: impl Fn(&CognitiveMemoryCaseMethodReport) -> f64 + Copy,
) -> f64 {
    RAG_METHODS
        .iter()
        .map(|method| method_mean(cases, method, f))
        .fold(0.0, f64::max)
}

fn typed_mean(
    cases: &[CognitiveMemoryCaseReport],
    task_types: &[&str],
    method: &str,
    f: impl Fn(&CognitiveMemoryCaseMethodReport) -> f64,
) -> f64 {
    let values = cases
        .iter()
        .filter(|case| task_types.contains(&case.task_type.as_str()))
        .filter_map(|case| case.methods.iter().find(|entry| entry.method == method))
        .map(f)
        .collect::<Vec<_>>();
    mean(&values).unwrap_or(0.0)
}

fn coverage(expected: &[&str], observed: &[&str]) -> f64 {
    if expected.is_empty() {
        return 1.0;
    }
    let observed = observed.iter().copied().collect::<BTreeSet<_>>();
    let hits = expected
        .iter()
        .filter(|item| observed.contains(**item))
        .count();
    hits as f64 / expected.len() as f64
}

fn lcs_score(expected: &[&str], observed: &[&str]) -> f64 {
    if expected.is_empty() {
        return 1.0;
    }
    let mut dp = vec![vec![0usize; observed.len() + 1]; expected.len() + 1];
    for i in 0..expected.len() {
        for (j, observed_item) in observed.iter().enumerate() {
            dp[i + 1][j + 1] = if expected[i] == *observed_item {
                dp[i][j] + 1
            } else {
                dp[i + 1][j].max(dp[i][j + 1])
            };
        }
    }
    dp[expected.len()][observed.len()] as f64 / expected.len() as f64
}

fn safe_div(numerator: f64, denominator: f64) -> f64 {
    if denominator.abs() < f64::EPSILON {
        0.0
    } else {
        numerator / denominator
    }
}

fn mean(values: &[f64]) -> Option<f64> {
    if values.is_empty() {
        None
    } else {
        Some(values.iter().sum::<f64>() / values.len() as f64)
    }
}

#[derive(Debug, Deserialize)]
struct CognitiveMemoryDatasetSpec {
    suite: String,
    #[serde(default)]
    profiles: BTreeMap<String, CognitiveMemoryProfileSpec>,
    cases: Vec<CognitiveMemoryCaseSpec>,
}

#[derive(Debug, Deserialize)]
struct CognitiveMemoryCaseSpec {
    id: String,
    task_type: String,
    #[serde(default)]
    challenges: Vec<String>,
    question: String,
    expected_decision: String,
    relevant_memories: Vec<String>,
    expected_trace: Vec<String>,
    #[serde(default)]
    expected_influence_delta: Option<f64>,
    #[serde(default)]
    expected_governance_action: Option<String>,
    #[serde(default)]
    profile: Option<String>,
    #[serde(default)]
    distractor_decision: Option<String>,
    #[serde(default)]
    methods: Vec<CognitiveMemoryMethodSpec>,
}

#[derive(Debug, Clone, Deserialize)]
struct CognitiveMemoryMethodSpec {
    method: String,
    #[serde(default)]
    retrieved: Vec<String>,
    #[serde(default)]
    trace: Vec<String>,
    decision: String,
    confidence: f64,
    #[serde(default)]
    influence_delta: Option<f64>,
    #[serde(default)]
    governance_action: Option<String>,
    #[serde(default)]
    metrics: Option<CognitiveMemoryMethodMetricsSpec>,
}

#[derive(Debug, Deserialize)]
struct CognitiveMemoryProfileSpec {
    methods: BTreeMap<String, CognitiveMemoryProfileMethodSpec>,
}

#[derive(Debug, Deserialize)]
struct CognitiveMemoryProfileMethodSpec {
    decision: String,
    confidence: f64,
    #[serde(default)]
    retrieved: Vec<String>,
    #[serde(default)]
    trace: Vec<String>,
    #[serde(default)]
    influence_delta: Option<f64>,
    #[serde(default)]
    governance_action: Option<String>,
    #[serde(flatten)]
    metrics: CognitiveMemoryMethodMetricsSpec,
}

#[derive(Debug, Clone, Deserialize)]
struct CognitiveMemoryMethodMetricsSpec {
    evidence_coverage: f64,
    trace_completeness: f64,
    trace_order_score: f64,
    #[serde(default)]
    causal_path_score: Option<f64>,
    #[serde(default)]
    memory_influence_score: Option<f64>,
    #[serde(default)]
    governance_trace_score: Option<f64>,
    #[serde(default)]
    explainability_score: Option<f64>,
}
