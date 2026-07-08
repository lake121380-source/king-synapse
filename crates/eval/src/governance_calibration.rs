use crate::governance_stress::{
    bounded, evaluate_edge, mean, rate, GovernanceRiskConfig, GovernanceStressDataset,
    DEFAULT_HARMFUL_THRESHOLD, SUPPRESSION_EPSILON,
};
use crate::types::{
    GovernanceCalibrationCandidateReport, GovernanceCalibrationSweepReport,
    GovernanceCalibrationThresholds, GovernanceRollbackReport, GovernanceStressEdgeReport,
};
use anyhow::{Context, Result};
use std::path::Path;

pub struct GovernanceCalibrationEvaluator;

impl GovernanceCalibrationEvaluator {
    pub fn evaluate(
        dataset_path: impl AsRef<Path>,
        tag: impl Into<String>,
    ) -> Result<GovernanceCalibrationSweepReport> {
        let dataset_path = dataset_path.as_ref();
        let raw = std::fs::read_to_string(dataset_path).with_context(|| {
            format!(
                "reading governance calibration dataset {}",
                dataset_path.display()
            )
        })?;
        let dataset: GovernanceStressDataset =
            toml::from_str(&raw).context("parsing governance calibration dataset TOML")?;
        evaluate_dataset(dataset, dataset_path.display().to_string(), tag.into())
    }
}

fn evaluate_dataset(
    dataset: GovernanceStressDataset,
    dataset_path: String,
    tag: String,
) -> Result<GovernanceCalibrationSweepReport> {
    if dataset.cases.is_empty() {
        anyhow::bail!("governance calibration dataset has no cases");
    }

    let thresholds = GovernanceCalibrationThresholds {
        harmful_detection_min: 0.85,
        false_positive_max: 0.05,
        normal_recall_preservation_min: 0.95,
        over_suppression_max: 0.05,
    };
    let baseline = evaluate_candidate("baseline", GovernanceRiskConfig::default(), &dataset);
    let mut candidates = Vec::new();
    for config in candidate_configs() {
        candidates.push(evaluate_candidate(config.0, config.1, &dataset));
    }
    candidates.sort_by(|a, b| {
        b.objective_score
            .partial_cmp(&a.objective_score)
            .unwrap_or(std::cmp::Ordering::Equal)
            .then_with(|| a.name.cmp(&b.name))
    });
    let best_candidate = candidates
        .iter()
        .filter(|candidate| candidate.pass)
        .max_by(|a, b| {
            a.objective_score
                .partial_cmp(&b.objective_score)
                .unwrap_or(std::cmp::Ordering::Equal)
        })
        .cloned();
    let pareto_frontier = pareto_frontier(&candidates);

    Ok(GovernanceCalibrationSweepReport {
        tag,
        dataset: dataset_path,
        candidate_count: candidates.len(),
        baseline,
        best_candidate,
        pareto_frontier,
        thresholds,
        rollback: GovernanceRollbackReport {
            rollback_model: "in_memory_risk_calibration_sweep".to_string(),
            persistent_edge_mutations: 0,
            default_recall_behavior_changed: false,
            edge_deletions: 0,
        },
    })
}

fn candidate_configs() -> Vec<(&'static str, GovernanceRiskConfig)> {
    let mut configs = Vec::new();
    let thresholds = [DEFAULT_HARMFUL_THRESHOLD, 0.62, 0.60, 0.58, 0.55];
    let scope_weights = [0.32, 0.36, 0.40, 0.44];
    let evidence_weights = [0.28, 0.30];
    let sample_weights = [0.14, 0.12];
    for threshold in thresholds {
        for scope_weight in scope_weights {
            for evidence_gap_weight in evidence_weights {
                for sample_support_weight in sample_weights {
                    let mut config = GovernanceRiskConfig::default();
                    config.harmful_threshold = threshold;
                    config.scope_weight = scope_weight;
                    config.evidence_gap_weight = evidence_gap_weight;
                    config.sample_support_weight = sample_support_weight;
                    let name = Box::leak(
                        format!(
                            "t{threshold:.2}_scope{scope_weight:.2}_evidence{evidence_gap_weight:.2}_sample{sample_support_weight:.2}"
                        )
                        .into_boxed_str(),
                    );
                    configs.push((name as &'static str, config));
                }
            }
        }
    }
    configs
}

fn evaluate_candidate(
    name: impl Into<String>,
    config: GovernanceRiskConfig,
    dataset: &GovernanceStressDataset,
) -> GovernanceCalibrationCandidateReport {
    let mut edges = Vec::new();
    for case in &dataset.cases {
        for edge in &case.edges {
            edges.push(evaluate_edge(case.severity, edge.clone(), config));
        }
    }
    candidate_report(name.into(), config, &edges)
}

fn candidate_report(
    name: String,
    config: GovernanceRiskConfig,
    edges: &[GovernanceStressEdgeReport],
) -> GovernanceCalibrationCandidateReport {
    let harmful_edges = edges.iter().filter(|edge| edge.label == "harmful").count();
    let valid_edges = edges.iter().filter(|edge| edge.label == "valid").count();
    let detected_harmful = edges
        .iter()
        .filter(|edge| edge.label == "harmful" && edge.detected_harmful)
        .count();
    let false_positives = edges
        .iter()
        .filter(|edge| edge.label == "valid" && edge.false_positive)
        .count();
    let suppressed_edges = edges
        .iter()
        .filter(|edge| edge.suppression_gain > SUPPRESSION_EPSILON)
        .count();
    let false_suppressed_valid = edges
        .iter()
        .filter(|edge| edge.label == "valid" && edge.suppression_gain > SUPPRESSION_EPSILON)
        .count();
    let normal_recall_preservation = mean(
        edges
            .iter()
            .filter_map(|edge| edge.normal_preservation)
            .collect::<Vec<_>>()
            .as_slice(),
    )
    .unwrap_or(1.0);
    let ambiguous_calibration_score = mean(
        edges
            .iter()
            .filter_map(|edge| edge.calibration_score)
            .collect::<Vec<_>>()
            .as_slice(),
    )
    .unwrap_or(1.0);
    let longitudinal_recovery_score = mean(
        edges
            .iter()
            .filter_map(|edge| edge.longitudinal_recovery_score)
            .collect::<Vec<_>>()
            .as_slice(),
    )
    .unwrap_or(1.0);
    let harmful_detection_rate = rate(detected_harmful, harmful_edges);
    let false_positive_rate = rate(false_positives, valid_edges);
    let over_suppression_rate = rate(false_suppressed_valid, suppressed_edges);
    let pass = harmful_detection_rate >= 0.85
        && false_positive_rate <= 0.05
        && normal_recall_preservation >= 0.95
        && over_suppression_rate <= 0.05;
    let objective_score = harmful_detection_rate
        - 1.2 * false_positive_rate
        - 0.8 * (1.0 - normal_recall_preservation).max(0.0)
        - 0.8 * over_suppression_rate
        + 0.08 * bounded(ambiguous_calibration_score)
        + 0.08 * bounded(longitudinal_recovery_score);
    let missed_harmful_edges = edges
        .iter()
        .filter(|edge| edge.label == "harmful" && !edge.detected_harmful)
        .map(|edge| edge.id.clone())
        .collect();
    let false_positive_edges = edges
        .iter()
        .filter(|edge| edge.label == "valid" && edge.false_positive)
        .map(|edge| edge.id.clone())
        .collect();

    GovernanceCalibrationCandidateReport {
        name,
        harmful_threshold: config.harmful_threshold,
        scope_weight: config.scope_weight,
        evidence_gap_weight: config.evidence_gap_weight,
        sample_support_weight: config.sample_support_weight,
        harmful_detection_rate,
        false_positive_rate,
        normal_recall_preservation,
        over_suppression_rate,
        ambiguous_calibration_score,
        longitudinal_recovery_score,
        pass,
        objective_score,
        missed_harmful_edges,
        false_positive_edges,
    }
}

fn pareto_frontier(
    candidates: &[GovernanceCalibrationCandidateReport],
) -> Vec<GovernanceCalibrationCandidateReport> {
    let mut frontier: Vec<GovernanceCalibrationCandidateReport> = candidates
        .iter()
        .filter(|candidate| {
            !candidates.iter().any(|other| {
                other.name != candidate.name
                    && other.harmful_detection_rate >= candidate.harmful_detection_rate
                    && other.false_positive_rate <= candidate.false_positive_rate
                    && other.normal_recall_preservation >= candidate.normal_recall_preservation
                    && other.over_suppression_rate <= candidate.over_suppression_rate
                    && (other.harmful_detection_rate > candidate.harmful_detection_rate
                        || other.false_positive_rate < candidate.false_positive_rate
                        || other.normal_recall_preservation > candidate.normal_recall_preservation
                        || other.over_suppression_rate < candidate.over_suppression_rate)
            })
        })
        .cloned()
        .collect();
    frontier.sort_by(|a, b| {
        b.harmful_detection_rate
            .partial_cmp(&a.harmful_detection_rate)
            .unwrap_or(std::cmp::Ordering::Equal)
            .then_with(|| {
                a.false_positive_rate
                    .partial_cmp(&b.false_positive_rate)
                    .unwrap_or(std::cmp::Ordering::Equal)
            })
            .then_with(|| b.objective_score.partial_cmp(&a.objective_score).unwrap())
    });
    frontier.truncate(12);
    frontier
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn pareto_frontier_removes_dominated_candidates() {
        let mk = |name: &str, detection: f64, fp: f64| GovernanceCalibrationCandidateReport {
            name: name.to_string(),
            harmful_threshold: 0.0,
            scope_weight: 0.0,
            evidence_gap_weight: 0.0,
            sample_support_weight: 0.0,
            harmful_detection_rate: detection,
            false_positive_rate: fp,
            normal_recall_preservation: 1.0,
            over_suppression_rate: 0.0,
            ambiguous_calibration_score: 1.0,
            longitudinal_recovery_score: 1.0,
            pass: true,
            objective_score: detection - fp,
            missed_harmful_edges: Vec::new(),
            false_positive_edges: Vec::new(),
        };
        let frontier = pareto_frontier(&[mk("dominated", 0.75, 0.1), mk("best", 0.85, 0.0)]);

        assert_eq!(frontier.len(), 1);
        assert_eq!(frontier[0].name, "best");
    }
}
