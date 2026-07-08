use crate::types::{
    DetectorConfidenceObservationReport, DetectorConfidenceRecord,
    GovernanceConfidenceEvaluationReport, GovernanceConfidenceThresholds, GovernanceRollbackReport,
};
use anyhow::{Context, Result};
use serde::Deserialize;
use std::collections::BTreeMap;
use std::path::Path;

const INITIAL_RELIABILITY: f64 = 0.50;
const DETECTOR_THRESHOLD: f64 = 0.65;

pub struct GovernanceConfidenceEvaluator;

impl GovernanceConfidenceEvaluator {
    pub fn evaluate(
        dataset_path: impl AsRef<Path>,
        tag: impl Into<String>,
    ) -> Result<GovernanceConfidenceEvaluationReport> {
        let dataset_path = dataset_path.as_ref();
        let raw = std::fs::read_to_string(dataset_path).with_context(|| {
            format!(
                "reading governance confidence dataset {}",
                dataset_path.display()
            )
        })?;
        let dataset: GovernanceConfidenceDataset =
            toml::from_str(&raw).context("parsing governance confidence dataset TOML")?;
        evaluate_dataset(dataset, dataset_path.display().to_string(), tag.into())
    }
}

fn evaluate_dataset(
    dataset: GovernanceConfidenceDataset,
    dataset_path: String,
    tag: String,
) -> Result<GovernanceConfidenceEvaluationReport> {
    if dataset.observations.is_empty() {
        anyhow::bail!("governance confidence dataset has no observations");
    }

    let mut by_detector: BTreeMap<String, Vec<GovernanceConfidenceObservationSpec>> =
        BTreeMap::new();
    for observation in dataset.observations {
        by_detector
            .entry(observation.detector.clone())
            .or_default()
            .push(observation);
    }

    let mut detector_reports = Vec::with_capacity(by_detector.len());
    let mut observation_reports = Vec::new();
    for (detector, observations) in by_detector {
        let (detector_report, mut reports) = evaluate_detector(&detector, &observations);
        detector_reports.push(detector_report);
        observation_reports.append(&mut reports);
    }

    let mean_initial_reliability = mean(
        detector_reports
            .iter()
            .map(|record| record.initial_reliability)
            .collect::<Vec<_>>()
            .as_slice(),
    )
    .unwrap_or(INITIAL_RELIABILITY);
    let mean_final_reliability = mean(
        detector_reports
            .iter()
            .map(|record| record.reliability_score)
            .collect::<Vec<_>>()
            .as_slice(),
    )
    .unwrap_or(INITIAL_RELIABILITY);
    let reliability_improvement = mean_final_reliability - mean_initial_reliability;
    let mean_calibration_error = mean(
        detector_reports
            .iter()
            .map(|record| record.calibrated_calibration_error)
            .collect::<Vec<_>>()
            .as_slice(),
    )
    .unwrap_or(0.5);
    let calibration_improvement = mean(
        detector_reports
            .iter()
            .map(|record| record.calibration_improvement)
            .collect::<Vec<_>>()
            .as_slice(),
    )
    .unwrap_or(0.0);
    let mean_confidence_drift = mean(
        detector_reports
            .iter()
            .map(|record| record.confidence_drift)
            .collect::<Vec<_>>()
            .as_slice(),
    )
    .unwrap_or(0.0);
    let governance_stability_score = mean(
        detector_reports
            .iter()
            .map(|record| record.stability_score)
            .collect::<Vec<_>>()
            .as_slice(),
    )
    .unwrap_or(1.0);
    let thresholds = GovernanceConfidenceThresholds {
        reliability_improvement_min: 0.25,
        calibration_improvement_min: 0.15,
        governance_stability_min: 0.60,
    };
    let pass = reliability_improvement >= thresholds.reliability_improvement_min
        && calibration_improvement >= thresholds.calibration_improvement_min
        && governance_stability_score >= thresholds.governance_stability_min;

    Ok(GovernanceConfidenceEvaluationReport {
        tag,
        dataset: dataset_path,
        detector_count: detector_reports.len(),
        observation_count: observation_reports.len(),
        mean_initial_reliability,
        mean_final_reliability,
        reliability_improvement,
        mean_calibration_error,
        calibration_improvement,
        mean_confidence_drift,
        governance_stability_score,
        pass,
        thresholds,
        rollback: GovernanceRollbackReport {
            rollback_model: "in_memory_detector_confidence_update".to_string(),
            persistent_edge_mutations: 0,
            default_recall_behavior_changed: false,
            edge_deletions: 0,
        },
        detectors: detector_reports,
        observations: observation_reports,
    })
}

fn evaluate_detector(
    detector: &str,
    observations: &[GovernanceConfidenceObservationSpec],
) -> (
    DetectorConfidenceRecord,
    Vec<DetectorConfidenceObservationReport>,
) {
    let mut tp = 0usize;
    let mut tn = 0usize;
    let mut fp = 0usize;
    let mut fn_ = 0usize;
    let mut reliability_path = vec![INITIAL_RELIABILITY];

    for (index, observation) in observations.iter().enumerate() {
        let predicted_harmful = observation.risk_score >= DETECTOR_THRESHOLD;
        match (predicted_harmful, observation.expected_harmful) {
            (true, true) => tp += 1,
            (false, false) => tn += 1,
            (true, false) => fp += 1,
            (false, true) => fn_ += 1,
        }
        reliability_path.push(posterior_reliability(correct_count(tp, tn), index + 1));
    }

    let predictions = observations.len();
    let reliability_score = posterior_reliability(correct_count(tp, tn), predictions);
    let confidence_delta = reliability_score - INITIAL_RELIABILITY;
    let raw_calibration_error = mean(
        observations
            .iter()
            .map(|observation| {
                abs_calibration_error(observation.risk_score, observation.expected_harmful)
            })
            .collect::<Vec<_>>()
            .as_slice(),
    )
    .unwrap_or(0.5);
    let mut observation_reports = Vec::with_capacity(observations.len());
    for observation in observations {
        let calibrated_score = calibrate_score(observation.risk_score, reliability_score);
        let predicted_harmful = observation.risk_score >= DETECTOR_THRESHOLD;
        observation_reports.push(DetectorConfidenceObservationReport {
            id: observation.id.clone(),
            detector: detector.to_string(),
            risk_score: observation.risk_score,
            calibrated_score,
            predicted_harmful,
            expected_harmful: observation.expected_harmful,
            correct: predicted_harmful == observation.expected_harmful,
        });
    }
    let calibrated_calibration_error = mean(
        observation_reports
            .iter()
            .map(|observation| {
                abs_calibration_error(observation.calibrated_score, observation.expected_harmful)
            })
            .collect::<Vec<_>>()
            .as_slice(),
    )
    .unwrap_or(0.5);
    let calibration_improvement = 0.5 - calibrated_calibration_error;
    let confidence_drift = reliability_path
        .windows(2)
        .map(|pair| (pair[1] - pair[0]).abs())
        .fold(0.0, f64::max);
    let stability_score = (1.0 - confidence_drift * 2.0).clamp(0.0, 1.0);

    (
        DetectorConfidenceRecord {
            detector: detector.to_string(),
            predictions,
            true_positive: tp,
            true_negative: tn,
            false_positive: fp,
            false_negative: fn_,
            initial_reliability: INITIAL_RELIABILITY,
            reliability_score,
            confidence_delta,
            raw_calibration_error,
            calibrated_calibration_error,
            calibration_improvement,
            confidence_drift,
            stability_score,
        },
        observation_reports,
    )
}

fn correct_count(tp: usize, tn: usize) -> usize {
    tp + tn
}

fn posterior_reliability(correct: usize, total: usize) -> f64 {
    (correct as f64 + 1.0) / (total as f64 + 2.0)
}

fn calibrate_score(score: f64, reliability: f64) -> f64 {
    0.5 + (score.clamp(0.0, 1.0) - 0.5) * (2.0 * reliability - 1.0)
}

fn abs_calibration_error(score: f64, expected_harmful: bool) -> f64 {
    let truth = if expected_harmful { 1.0 } else { 0.0 };
    (score.clamp(0.0, 1.0) - truth).abs()
}

fn mean(values: &[f64]) -> Option<f64> {
    if values.is_empty() {
        None
    } else {
        Some(values.iter().sum::<f64>() / values.len() as f64)
    }
}

#[derive(Debug, Deserialize)]
struct GovernanceConfidenceDataset {
    observations: Vec<GovernanceConfidenceObservationSpec>,
}

#[derive(Debug, Clone, Deserialize)]
struct GovernanceConfidenceObservationSpec {
    id: String,
    detector: String,
    risk_score: f64,
    expected_harmful: bool,
}

#[cfg(test)]
mod tests {
    use super::*;

    fn observation(
        id: &str,
        detector: &str,
        risk_score: f64,
        expected_harmful: bool,
    ) -> GovernanceConfidenceObservationSpec {
        GovernanceConfidenceObservationSpec {
            id: id.to_string(),
            detector: detector.to_string(),
            risk_score,
            expected_harmful,
        }
    }

    #[test]
    fn detector_reliability_improves_with_correct_predictions() {
        let observations = vec![
            observation("a", "scope", 0.90, true),
            observation("b", "scope", 0.20, false),
            observation("c", "scope", 0.80, true),
            observation("d", "scope", 0.30, false),
        ];
        let (record, _) = evaluate_detector("scope", &observations);

        assert_eq!(record.predictions, 4);
        assert!(record.reliability_score > INITIAL_RELIABILITY);
        assert!(record.false_positive == 0);
        assert!(record.false_negative == 0);
    }

    #[test]
    fn detector_reliability_penalizes_wrong_predictions() {
        let observations = vec![
            observation("a", "scope", 0.90, false),
            observation("b", "scope", 0.20, true),
        ];
        let (record, _) = evaluate_detector("scope", &observations);

        assert!(record.reliability_score < INITIAL_RELIABILITY);
        assert_eq!(record.false_positive, 1);
        assert_eq!(record.false_negative, 1);
    }
}
