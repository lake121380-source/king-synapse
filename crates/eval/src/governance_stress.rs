use crate::types::{
    GovernanceRollbackReport, GovernanceStressCaseReport, GovernanceStressEdgeReport,
    GovernanceStressEvaluationReport, GovernanceStressThresholds,
};
use anyhow::{Context, Result};
use serde::Deserialize;
use std::path::Path;

pub(crate) const DEFAULT_HARMFUL_THRESHOLD: f64 = 0.65;
const AMBIGUOUS_UNCERTAINTY_THRESHOLD: f64 = 0.45;
pub(crate) const SUPPRESSION_EPSILON: f64 = 0.05;

#[derive(Debug, Clone, Copy)]
pub(crate) struct GovernanceRiskConfig {
    pub harmful_threshold: f64,
    pub scope_weight: f64,
    pub evidence_gap_weight: f64,
    pub emotion_weight: f64,
    pub severity_weight: f64,
    pub base_rate_weight: f64,
    pub sample_support_weight: f64,
    pub relation_pressure: f64,
}

impl Default for GovernanceRiskConfig {
    fn default() -> Self {
        Self {
            harmful_threshold: DEFAULT_HARMFUL_THRESHOLD,
            scope_weight: 0.32,
            evidence_gap_weight: 0.28,
            emotion_weight: 0.18,
            severity_weight: 0.10,
            base_rate_weight: 0.20,
            sample_support_weight: 0.14,
            relation_pressure: 0.05,
        }
    }
}

pub struct GovernanceStressEvaluator;

impl GovernanceStressEvaluator {
    pub fn evaluate(
        dataset_path: impl AsRef<Path>,
        tag: impl Into<String>,
    ) -> Result<GovernanceStressEvaluationReport> {
        let dataset_path = dataset_path.as_ref();
        let raw = std::fs::read_to_string(dataset_path).with_context(|| {
            format!(
                "reading governance stress dataset {}",
                dataset_path.display()
            )
        })?;
        let dataset: GovernanceStressDataset =
            toml::from_str(&raw).context("parsing governance stress dataset TOML")?;
        evaluate_dataset(dataset, dataset_path.display().to_string(), tag.into())
    }
}

fn evaluate_dataset(
    dataset: GovernanceStressDataset,
    dataset_path: String,
    tag: String,
) -> Result<GovernanceStressEvaluationReport> {
    if dataset.cases.is_empty() {
        anyhow::bail!("governance stress dataset has no cases");
    }

    let mut cases = Vec::with_capacity(dataset.cases.len());
    for case in dataset.cases {
        cases.push(evaluate_case(case, GovernanceRiskConfig::default())?);
    }

    let edges: Vec<&GovernanceStressEdgeReport> =
        cases.iter().flat_map(|case| case.edges.iter()).collect();
    let edge_count = edges.len();
    let harmful_edge_count = edges.iter().filter(|edge| edge.label == "harmful").count();
    let valid_edge_count = edges.iter().filter(|edge| edge.label == "valid").count();
    let ambiguous_edge_count = edges
        .iter()
        .filter(|edge| edge.label == "ambiguous")
        .count();
    let longitudinal_edge_count = edges
        .iter()
        .filter(|edge| edge.longitudinal_recovery_score.is_some())
        .count();
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
    let normal_recall_preservation = mean(
        edges
            .iter()
            .filter_map(|edge| edge.normal_preservation)
            .collect::<Vec<_>>()
            .as_slice(),
    )
    .unwrap_or(1.0);
    let harmful_detection_rate = rate(detected_harmful, harmful_edge_count);
    let false_positive_rate = rate(false_positives, valid_edge_count);
    let over_suppression_rate = rate(false_suppressed_valid, suppressed_edges);
    let thresholds = GovernanceStressThresholds {
        harmful_detection_min: 0.70,
        false_positive_max: 0.10,
        ambiguous_calibration_min: 0.60,
        longitudinal_recovery_min: 0.50,
        normal_recall_preservation_min: 0.95,
        over_suppression_max: 0.10,
    };
    let pass = harmful_detection_rate >= thresholds.harmful_detection_min
        && false_positive_rate <= thresholds.false_positive_max
        && ambiguous_calibration_score >= thresholds.ambiguous_calibration_min
        && longitudinal_recovery_score >= thresholds.longitudinal_recovery_min
        && normal_recall_preservation >= thresholds.normal_recall_preservation_min
        && over_suppression_rate <= thresholds.over_suppression_max;

    Ok(GovernanceStressEvaluationReport {
        tag,
        dataset: dataset_path,
        case_count: cases.len(),
        edge_count,
        harmful_edge_count,
        valid_edge_count,
        ambiguous_edge_count,
        longitudinal_edge_count,
        harmful_detection_rate,
        false_positive_rate,
        ambiguous_calibration_score,
        longitudinal_recovery_score,
        normal_recall_preservation,
        over_suppression_rate,
        pass,
        thresholds,
        rollback: GovernanceRollbackReport {
            rollback_model: "in_memory_mixed_reality_stress_simulation".to_string(),
            persistent_edge_mutations: 0,
            default_recall_behavior_changed: false,
            edge_deletions: 0,
        },
        cases,
    })
}

pub(crate) fn evaluate_case(
    case: GovernanceStressCaseSpec,
    config: GovernanceRiskConfig,
) -> Result<GovernanceStressCaseReport> {
    if case.edges.is_empty() {
        anyhow::bail!("governance stress case {} has no edges", case.id);
    }

    let case_type = case.case_type.clone();
    let issue = case.issue.clone();
    let severity = case.severity;
    let edges = case
        .edges
        .into_iter()
        .map(|edge| evaluate_edge(severity, edge, config))
        .collect();

    Ok(GovernanceStressCaseReport {
        id: case.id,
        case_type,
        issue,
        edges,
    })
}

pub(crate) fn evaluate_edge(
    severity: f64,
    edge: GovernanceStressEdgeSpec,
    config: GovernanceRiskConfig,
) -> GovernanceStressEdgeReport {
    let risk_score = cognitive_risk_score(severity, &edge, config);
    let uncertainty_score = uncertainty_score(&edge);
    let detected_harmful = risk_score >= config.harmful_threshold;
    let baseline_influence = bounded(edge.weight) * bounded(edge.confidence);
    let governance_action = governance_action(detected_harmful, uncertainty_score);
    let governed_influence = governed_influence(
        baseline_influence,
        risk_score,
        uncertainty_score,
        config.harmful_threshold,
    );
    let suppression_gain = baseline_influence - governed_influence;
    let false_positive = edge.label == "valid" && detected_harmful;
    let normal_preservation = if edge.label == "valid" && baseline_influence > 0.0 {
        Some(governed_influence / baseline_influence)
    } else {
        None
    };
    let calibration_score = if edge.label == "ambiguous" {
        edge.target_calibrated_influence.map(|target| {
            let denom = baseline_influence.max(bounded(target)).max(0.01);
            (1.0 - (governed_influence - bounded(target)).abs() / denom).clamp(0.0, 1.0)
        })
    } else {
        None
    };
    let (confidence_path, longitudinal_recovery_score) = longitudinal_recovery(&edge);

    GovernanceStressEdgeReport {
        id: edge.id,
        source: edge.source,
        target: edge.target,
        label: edge.label,
        expected_action: governance_action.to_string(),
        risk_score,
        uncertainty_score,
        detected_harmful,
        false_positive,
        baseline_influence,
        governed_influence,
        suppression_gain,
        normal_preservation,
        calibration_score,
        longitudinal_recovery_score,
        confidence_path,
    }
}

fn governance_action(detected_harmful: bool, uncertainty_score: f64) -> &'static str {
    if detected_harmful {
        "suppress"
    } else if uncertainty_score >= AMBIGUOUS_UNCERTAINTY_THRESHOLD {
        "calibrate"
    } else {
        "preserve"
    }
}

fn governed_influence(
    baseline_influence: f64,
    risk_score: f64,
    uncertainty_score: f64,
    harmful_threshold: f64,
) -> f64 {
    if risk_score >= harmful_threshold {
        let suppression_fraction = (0.15 + risk_score * 0.65).clamp(0.0, 0.80);
        baseline_influence * (1.0 - suppression_fraction)
    } else if uncertainty_score >= AMBIGUOUS_UNCERTAINTY_THRESHOLD {
        let calibration_fraction = (0.08 + uncertainty_score * 0.24).clamp(0.0, 0.28);
        baseline_influence * (1.0 - calibration_fraction)
    } else {
        baseline_influence
    }
}

pub(crate) fn cognitive_risk_score(
    severity: f64,
    edge: &GovernanceStressEdgeSpec,
    config: GovernanceRiskConfig,
) -> f64 {
    let confidence = bounded(edge.confidence);
    let evidence_strength = bounded(edge.evidence_strength);
    let evidence_gap = (confidence - evidence_strength).max(0.0);
    let scope_pressure = bounded(edge.scope_shift)
        .max(bounded(edge.event_specificity) * bounded(edge.prediction_scope));
    let emotion_pressure = (bounded(edge.emotion_weight) - evidence_strength).max(0.0);
    let sample_support = sample_support(edge.sample_size);
    let relation_pressure = if edge.relation == "predicts" || edge.relation == "explains" {
        config.relation_pressure
    } else {
        0.0
    };

    (config.scope_weight * scope_pressure * (1.0 - sample_support)
        + config.evidence_gap_weight * evidence_gap
        + config.emotion_weight * emotion_pressure
        + config.severity_weight * bounded(severity)
        + relation_pressure
        - config.base_rate_weight * bounded(edge.base_rate_support)
        - config.sample_support_weight * sample_support)
        .clamp(0.0, 1.0)
}

fn uncertainty_score(edge: &GovernanceStressEdgeSpec) -> f64 {
    let evidence_midpoint = 1.0 - (bounded(edge.evidence_strength) - 0.5).abs() * 2.0;
    (0.55 * bounded(edge.uncertainty)
        + 0.30 * evidence_midpoint
        + 0.15 * (1.0 - sample_support(edge.sample_size)))
    .clamp(0.0, 1.0)
}

fn longitudinal_recovery(edge: &GovernanceStressEdgeSpec) -> (Vec<f64>, Option<f64>) {
    let Some(target) = edge.expected_final_confidence else {
        return (Vec::new(), None);
    };
    if edge.evidence_sequence.is_empty() {
        return (vec![bounded(edge.confidence)], Some(0.0));
    }

    let target = bounded(target);
    let mut confidence = bounded(edge.confidence);
    let mut path = vec![confidence];
    for evidence in &edge.evidence_sequence {
        let evidence = bounded(*evidence);
        let learning_rate = 0.12 + evidence * 0.26;
        confidence += (target - confidence) * learning_rate;
        path.push(confidence);
    }

    let initial_error = (bounded(edge.confidence) - target).abs();
    let final_error = (confidence - target).abs();
    let score = if initial_error <= f64::EPSILON {
        1.0
    } else {
        (1.0 - final_error / initial_error).clamp(0.0, 1.0)
    };
    (path, Some(score))
}

pub(crate) fn sample_support(sample_size: usize) -> f64 {
    if sample_size == 0 {
        0.0
    } else {
        ((sample_size as f64).ln() / 3.0).clamp(0.0, 1.0)
    }
}

pub(crate) fn bounded(value: f64) -> f64 {
    if value.is_finite() {
        value.clamp(0.0, 1.0)
    } else {
        0.0
    }
}

pub(crate) fn mean(values: &[f64]) -> Option<f64> {
    if values.is_empty() {
        None
    } else {
        Some(values.iter().sum::<f64>() / values.len() as f64)
    }
}

pub(crate) fn rate(numerator: usize, denominator: usize) -> f64 {
    if denominator == 0 {
        0.0
    } else {
        numerator as f64 / denominator as f64
    }
}

#[derive(Debug, Clone, Deserialize)]
pub(crate) struct GovernanceStressDataset {
    pub cases: Vec<GovernanceStressCaseSpec>,
}

#[derive(Debug, Clone, Deserialize)]
pub(crate) struct GovernanceStressCaseSpec {
    pub id: String,
    pub case_type: String,
    pub issue: String,
    pub severity: f64,
    pub edges: Vec<GovernanceStressEdgeSpec>,
}

#[derive(Debug, Clone, Deserialize)]
pub(crate) struct GovernanceStressEdgeSpec {
    pub id: String,
    pub source: String,
    pub target: String,
    pub relation: String,
    pub label: String,
    pub weight: f64,
    pub confidence: f64,
    pub evidence_strength: f64,
    pub event_specificity: f64,
    pub prediction_scope: f64,
    pub scope_shift: f64,
    pub emotion_weight: f64,
    pub base_rate_support: f64,
    pub uncertainty: f64,
    pub sample_size: usize,
    #[serde(default)]
    pub target_calibrated_influence: Option<f64>,
    #[serde(default)]
    pub expected_final_confidence: Option<f64>,
    #[serde(default)]
    pub evidence_sequence: Vec<f64>,
}

#[cfg(test)]
mod tests {
    use super::*;

    fn valid_repeated_failure_edge() -> GovernanceStressEdgeSpec {
        GovernanceStressEdgeSpec {
            id: "valid".to_string(),
            source: "many_failures".to_string(),
            target: "strategy_problem".to_string(),
            relation: "supports".to_string(),
            label: "valid".to_string(),
            weight: 0.80,
            confidence: 0.84,
            evidence_strength: 0.86,
            event_specificity: 0.60,
            prediction_scope: 0.62,
            scope_shift: 0.28,
            emotion_weight: 0.18,
            base_rate_support: 0.82,
            uncertainty: 0.12,
            sample_size: 20,
            target_calibrated_influence: None,
            expected_final_confidence: None,
            evidence_sequence: vec![],
        }
    }

    fn harmful_single_event_edge() -> GovernanceStressEdgeSpec {
        GovernanceStressEdgeSpec {
            id: "harmful".to_string(),
            source: "one_failure".to_string(),
            target: "always_fail".to_string(),
            relation: "predicts".to_string(),
            label: "harmful".to_string(),
            weight: 0.90,
            confidence: 0.92,
            evidence_strength: 0.15,
            event_specificity: 0.96,
            prediction_scope: 1.0,
            scope_shift: 0.94,
            emotion_weight: 0.74,
            base_rate_support: 0.05,
            uncertainty: 0.20,
            sample_size: 1,
            target_calibrated_influence: None,
            expected_final_confidence: Some(0.45),
            evidence_sequence: vec![0.12, 0.18, 0.80, 0.75],
        }
    }

    fn ambiguous_trend_edge() -> GovernanceStressEdgeSpec {
        GovernanceStressEdgeSpec {
            id: "ambiguous".to_string(),
            source: "ai_coding".to_string(),
            target: "job_reduction".to_string(),
            relation: "predicts".to_string(),
            label: "ambiguous".to_string(),
            weight: 0.78,
            confidence: 0.70,
            evidence_strength: 0.50,
            event_specificity: 0.36,
            prediction_scope: 0.78,
            scope_shift: 0.52,
            emotion_weight: 0.20,
            base_rate_support: 0.45,
            uncertainty: 0.70,
            sample_size: 6,
            target_calibrated_influence: Some(0.42),
            expected_final_confidence: None,
            evidence_sequence: vec![],
        }
    }

    #[test]
    fn repeated_failures_do_not_become_false_positive() {
        let report = evaluate_edge(
            0.8,
            valid_repeated_failure_edge(),
            GovernanceRiskConfig::default(),
        );

        assert!(!report.detected_harmful);
        assert!(!report.false_positive);
        assert!(report.normal_preservation.unwrap() >= 0.99);
    }

    #[test]
    fn single_event_global_claim_is_detected_and_recovers_over_time() {
        let report = evaluate_edge(
            0.9,
            harmful_single_event_edge(),
            GovernanceRiskConfig::default(),
        );

        assert!(report.detected_harmful);
        assert!(report.suppression_gain > 0.40);
        assert!(report.longitudinal_recovery_score.unwrap() > 0.50);
        assert!(report.confidence_path.len() > 1);
    }

    #[test]
    fn ambiguous_trend_is_calibrated_without_harmful_detection() {
        let report = evaluate_edge(0.7, ambiguous_trend_edge(), GovernanceRiskConfig::default());

        assert!(!report.detected_harmful);
        assert_eq!(report.expected_action, "calibrate");
        assert!(report.calibration_score.unwrap() > 0.60);
    }
}
