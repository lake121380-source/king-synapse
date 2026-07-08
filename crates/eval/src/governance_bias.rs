use crate::types::{
    GovernanceBiasCaseReport, GovernanceBiasEdgeReport, GovernanceBiasEvaluationReport,
    GovernanceBiasThresholds, GovernanceRollbackReport,
};
use anyhow::{Context, Result};
use serde::Deserialize;
use std::path::Path;

const DETECTION_THRESHOLD: f64 = 0.65;
const SUPPRESSION_EPSILON: f64 = 0.05;

pub struct GovernanceBiasEvaluator;

impl GovernanceBiasEvaluator {
    pub fn evaluate(
        dataset_path: impl AsRef<Path>,
        tag: impl Into<String>,
    ) -> Result<GovernanceBiasEvaluationReport> {
        let dataset_path = dataset_path.as_ref();
        let raw = std::fs::read_to_string(dataset_path).with_context(|| {
            format!("reading governance bias dataset {}", dataset_path.display())
        })?;
        let dataset: GovernanceBiasDataset =
            toml::from_str(&raw).context("parsing governance bias dataset TOML")?;
        evaluate_dataset(dataset, dataset_path.display().to_string(), tag.into())
    }
}

fn evaluate_dataset(
    dataset: GovernanceBiasDataset,
    dataset_path: String,
    tag: String,
) -> Result<GovernanceBiasEvaluationReport> {
    if dataset.cases.is_empty() {
        anyhow::bail!("governance bias dataset has no cases");
    }

    let mut case_reports = Vec::with_capacity(dataset.cases.len());
    for case in dataset.cases {
        case_reports.push(evaluate_case(case)?);
    }

    let edge_count: usize = case_reports.iter().map(|case| case.edges.len()).sum();
    let harmful_edge_count: usize = case_reports.iter().map(|case| case.harmful_edges).sum();
    let detected_harmful_edges: usize = case_reports
        .iter()
        .map(|case| case.detected_harmful_edges)
        .sum();
    let normal_edge_count = edge_count.saturating_sub(harmful_edge_count);
    let false_suppressed_normal_edges: usize = case_reports
        .iter()
        .map(|case| case.false_suppressed_normal_edges)
        .sum();
    let suppressed_edges = case_reports
        .iter()
        .flat_map(|case| case.edges.iter())
        .filter(|edge| edge.suppression_gain > SUPPRESSION_EPSILON)
        .count();
    let harmful_suppression_gain = weighted_mean(
        case_reports
            .iter()
            .flat_map(|case| case.edges.iter())
            .filter(|edge| edge.label == "harmful")
            .map(|edge| (edge.suppression_gain, 1usize)),
    );
    let normal_recall_preservation = weighted_mean(
        case_reports
            .iter()
            .flat_map(|case| case.edges.iter())
            .filter(|edge| edge.label == "normal")
            .map(|edge| {
                let preservation = if edge.baseline_influence > 0.0 {
                    edge.governed_influence / edge.baseline_influence
                } else {
                    1.0
                };
                (preservation, 1usize)
            }),
    )
    .unwrap_or(1.0);
    let recovery_score = weighted_mean(
        case_reports
            .iter()
            .flat_map(|case| case.edges.iter())
            .filter_map(|edge| edge.recovery_score.map(|score| (score, 1usize))),
    )
    .unwrap_or(1.0);
    let thresholds = GovernanceBiasThresholds {
        detection_min: 0.70,
        normal_recall_preservation_min: 0.95,
        over_suppression_max: 0.05,
        recovery_min: 0.50,
    };
    let harmful_edge_detection_rate = rate(detected_harmful_edges, harmful_edge_count);
    let over_suppression_rate = rate(false_suppressed_normal_edges, suppressed_edges);
    let suppression_gain = harmful_suppression_gain.unwrap_or(0.0);
    let pass = harmful_edge_detection_rate >= thresholds.detection_min
        && normal_recall_preservation >= thresholds.normal_recall_preservation_min
        && over_suppression_rate <= thresholds.over_suppression_max
        && recovery_score >= thresholds.recovery_min;

    Ok(GovernanceBiasEvaluationReport {
        tag,
        dataset: dataset_path,
        case_count: case_reports.len(),
        edge_count,
        harmful_edge_count,
        normal_edge_count,
        harmful_edge_detection_rate,
        suppression_gain,
        over_suppression_rate,
        normal_recall_preservation,
        recovery_score,
        pass,
        thresholds,
        rollback: GovernanceRollbackReport {
            rollback_model: "in_memory_positive_control_simulation".to_string(),
            persistent_edge_mutations: 0,
            default_recall_behavior_changed: false,
            edge_deletions: 0,
        },
        cases: case_reports,
    })
}

fn evaluate_case(case: GovernanceBiasCaseSpec) -> Result<GovernanceBiasCaseReport> {
    if case.edges.is_empty() {
        anyhow::bail!("governance bias case {} has no edges", case.id);
    }

    let case_issue = case.issue.clone();
    let case_severity = case.severity;
    let mut edge_reports = Vec::with_capacity(case.edges.len());
    for edge in case.edges {
        edge_reports.push(evaluate_edge(&case_issue, case_severity, edge));
    }

    let harmful_edges = edge_reports
        .iter()
        .filter(|edge| edge.label == "harmful")
        .count();
    let detected_harmful_edges = edge_reports
        .iter()
        .filter(|edge| edge.label == "harmful" && edge.detected_harmful)
        .count();
    let false_suppressed_normal_edges = edge_reports
        .iter()
        .filter(|edge| edge.label == "normal" && edge.suppression_gain > SUPPRESSION_EPSILON)
        .count();
    let suppression_gain = weighted_mean(
        edge_reports
            .iter()
            .filter(|edge| edge.label == "harmful")
            .map(|edge| (edge.suppression_gain, 1usize)),
    )
    .unwrap_or(0.0);
    let recovery_score = weighted_mean(
        edge_reports
            .iter()
            .filter_map(|edge| edge.recovery_score.map(|score| (score, 1usize))),
    )
    .unwrap_or(1.0);
    let normal_recall_preservation = weighted_mean(
        edge_reports
            .iter()
            .filter(|edge| edge.label == "normal")
            .map(|edge| {
                let preservation = if edge.baseline_influence > 0.0 {
                    edge.governed_influence / edge.baseline_influence
                } else {
                    1.0
                };
                (preservation, 1usize)
            }),
    )
    .unwrap_or(1.0);

    Ok(GovernanceBiasCaseReport {
        id: case.id,
        issue: case.issue,
        severity: case.severity,
        harmful_edges,
        detected_harmful_edges,
        false_suppressed_normal_edges,
        suppression_gain,
        recovery_score,
        normal_recall_preservation,
        edges: edge_reports,
    })
}

fn evaluate_edge(
    case_issue: &str,
    case_severity: f64,
    edge: GovernanceBiasEdgeSpec,
) -> GovernanceBiasEdgeReport {
    let risk_score = cognitive_risk_score(case_severity, &edge);
    let detected_harmful = risk_score >= DETECTION_THRESHOLD;
    let baseline_influence = bounded(edge.weight) * bounded(edge.confidence);
    let suppression_fraction = if detected_harmful {
        (0.15 + risk_score * 0.65).clamp(0.0, 0.80)
    } else {
        0.0
    };
    let governed_influence = baseline_influence * (1.0 - suppression_fraction);
    let suppression_gain = baseline_influence - governed_influence;
    let (recovered_confidence, recovery_score) =
        recovery_metrics(edge.confidence, suppression_fraction, &edge);

    GovernanceBiasEdgeReport {
        id: edge.id,
        source: edge.source,
        target: edge.target,
        label: edge.label,
        expected_issue: edge
            .expected_issue
            .unwrap_or_else(|| case_issue.to_string()),
        risk_score,
        detected_harmful,
        baseline_influence,
        governed_influence,
        suppression_gain,
        recovered_confidence,
        recovery_score,
    }
}

fn cognitive_risk_score(case_severity: f64, edge: &GovernanceBiasEdgeSpec) -> f64 {
    let confidence = bounded(edge.confidence);
    let evidence_strength = bounded(edge.evidence_strength);
    let evidence_gap = (confidence - evidence_strength).max(0.0);
    let scope_pressure = bounded(edge.scope_shift)
        .max(bounded(edge.event_specificity) * bounded(edge.prediction_scope));
    let emotion_pressure = (bounded(edge.emotion_weight) - evidence_strength).max(0.0);
    let causal_pressure = if edge.relation == "predicts" || edge.relation == "explains" {
        0.05
    } else {
        0.0
    };

    (0.34 * scope_pressure
        + 0.31 * evidence_gap
        + 0.20 * emotion_pressure
        + 0.10 * bounded(case_severity)
        + causal_pressure)
        .clamp(0.0, 1.0)
}

fn recovery_metrics(
    confidence: f64,
    suppression_fraction: f64,
    edge: &GovernanceBiasEdgeSpec,
) -> (Option<f64>, Option<f64>) {
    let Some(target) = edge.expected_recovered_confidence else {
        return (None, None);
    };
    let recovery_evidence = bounded(edge.recovery_evidence_strength);
    let regulated_confidence = bounded(confidence) * (1.0 - suppression_fraction);
    let recovered_confidence =
        regulated_confidence + (bounded(target) - regulated_confidence) * recovery_evidence;
    let initial_error = (bounded(confidence) - bounded(target)).abs();
    let final_error = (recovered_confidence - bounded(target)).abs();
    let score = if initial_error <= f64::EPSILON {
        1.0
    } else {
        (1.0 - final_error / initial_error).clamp(0.0, 1.0)
    };
    (Some(recovered_confidence), Some(score))
}

fn bounded(value: f64) -> f64 {
    if value.is_finite() {
        value.clamp(0.0, 1.0)
    } else {
        0.0
    }
}

fn rate(numerator: usize, denominator: usize) -> f64 {
    if denominator == 0 {
        0.0
    } else {
        numerator as f64 / denominator as f64
    }
}

fn weighted_mean(values: impl Iterator<Item = (f64, usize)>) -> Option<f64> {
    let mut total = 0.0;
    let mut weight = 0usize;
    for (value, value_weight) in values {
        total += value * value_weight as f64;
        weight += value_weight;
    }
    if weight == 0 {
        None
    } else {
        Some(total / weight as f64)
    }
}

#[derive(Debug, Deserialize)]
struct GovernanceBiasDataset {
    cases: Vec<GovernanceBiasCaseSpec>,
}

#[derive(Debug, Deserialize)]
struct GovernanceBiasCaseSpec {
    id: String,
    issue: String,
    severity: f64,
    #[allow(dead_code)]
    memories: Vec<GovernanceBiasMemorySpec>,
    edges: Vec<GovernanceBiasEdgeSpec>,
}

#[derive(Debug, Deserialize)]
struct GovernanceBiasMemorySpec {
    #[allow(dead_code)]
    id: String,
    #[allow(dead_code)]
    content: String,
    #[allow(dead_code)]
    role: String,
}

#[derive(Debug, Deserialize)]
struct GovernanceBiasEdgeSpec {
    id: String,
    source: String,
    target: String,
    relation: String,
    label: String,
    weight: f64,
    confidence: f64,
    evidence_strength: f64,
    event_specificity: f64,
    prediction_scope: f64,
    scope_shift: f64,
    emotion_weight: f64,
    recovery_evidence_strength: f64,
    expected_recovered_confidence: Option<f64>,
    expected_issue: Option<String>,
}

#[cfg(test)]
mod tests {
    use super::*;

    fn harmful_edge() -> GovernanceBiasEdgeSpec {
        GovernanceBiasEdgeSpec {
            id: "bad".to_string(),
            source: "one_failure".to_string(),
            target: "identity_claim".to_string(),
            relation: "predicts".to_string(),
            label: "harmful".to_string(),
            weight: 0.9,
            confidence: 0.92,
            evidence_strength: 0.15,
            event_specificity: 0.95,
            prediction_scope: 1.0,
            scope_shift: 0.9,
            emotion_weight: 0.7,
            recovery_evidence_strength: 0.8,
            expected_recovered_confidence: Some(0.45),
            expected_issue: Some("over_generalization".to_string()),
        }
    }

    fn normal_edge() -> GovernanceBiasEdgeSpec {
        GovernanceBiasEdgeSpec {
            id: "good".to_string(),
            source: "one_failure".to_string(),
            target: "prepare_next_time".to_string(),
            relation: "supports".to_string(),
            label: "normal".to_string(),
            weight: 0.7,
            confidence: 0.75,
            evidence_strength: 0.70,
            event_specificity: 0.75,
            prediction_scope: 0.35,
            scope_shift: 0.15,
            emotion_weight: 0.20,
            recovery_evidence_strength: 0.0,
            expected_recovered_confidence: None,
            expected_issue: Some("none".to_string()),
        }
    }

    fn test_case(edges: Vec<GovernanceBiasEdgeSpec>) -> GovernanceBiasCaseSpec {
        GovernanceBiasCaseSpec {
            id: "case".to_string(),
            issue: "over_generalization".to_string(),
            severity: 0.90,
            memories: vec![],
            edges,
        }
    }

    #[test]
    fn detects_and_suppresses_positive_control_harmful_edge() {
        let report = evaluate_case(test_case(vec![harmful_edge()])).unwrap();

        assert_eq!(report.harmful_edges, 1);
        assert_eq!(report.detected_harmful_edges, 1);
        assert!(report.suppression_gain > 0.40);
        assert!(report.edges[0].risk_score >= DETECTION_THRESHOLD);
    }

    #[test]
    fn preserves_normal_control_edges() {
        let report = evaluate_case(test_case(vec![normal_edge()])).unwrap();

        assert_eq!(report.false_suppressed_normal_edges, 0);
        assert!(report.normal_recall_preservation >= 0.99);
        assert!(!report.edges[0].detected_harmful);
    }

    #[test]
    fn recovery_moves_confidence_toward_counterevidence_target() {
        let report = evaluate_case(test_case(vec![harmful_edge()])).unwrap();
        let edge = &report.edges[0];

        assert!(edge.recovered_confidence.is_some());
        assert!(edge.recovery_score.unwrap() > 0.50);
    }
}
