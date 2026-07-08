use crate::types::{
    GovernanceAggregationDetectorReport, GovernanceAggregationEvaluationReport,
    GovernanceAggregationMethodReport, GovernanceAggregationThresholds, GovernanceRollbackReport,
};
use anyhow::{Context, Result};
use serde::Deserialize;
use std::collections::BTreeMap;
use std::path::Path;

const DETECTOR_THRESHOLD: f64 = 0.65;

pub struct GovernanceAggregationEvaluator;

impl GovernanceAggregationEvaluator {
    pub fn evaluate(
        dataset_path: impl AsRef<Path>,
        tag: impl Into<String>,
    ) -> Result<GovernanceAggregationEvaluationReport> {
        let dataset_path = dataset_path.as_ref();
        let raw = std::fs::read_to_string(dataset_path).with_context(|| {
            format!(
                "reading governance aggregation dataset {}",
                dataset_path.display()
            )
        })?;
        let dataset: GovernanceAggregationDataset =
            toml::from_str(&raw).context("parsing governance aggregation dataset TOML")?;
        evaluate_dataset(dataset, dataset_path.display().to_string(), tag.into())
    }
}

fn evaluate_dataset(
    dataset: GovernanceAggregationDataset,
    dataset_path: String,
    tag: String,
) -> Result<GovernanceAggregationEvaluationReport> {
    if dataset.observations.is_empty() {
        anyhow::bail!("governance aggregation dataset has no observations");
    }

    let mut by_detector: BTreeMap<String, Vec<GovernanceAggregationObservationSpec>> =
        BTreeMap::new();
    for observation in &dataset.observations {
        by_detector
            .entry(observation.detector.clone())
            .or_default()
            .push(observation.clone());
    }
    let detector_profiles: BTreeMap<String, DetectorAggregationProfile> = by_detector
        .iter()
        .map(|(detector, observations)| (detector.clone(), detector_profile(observations)))
        .collect();
    let detectors: Vec<GovernanceAggregationDetectorReport> = detector_profiles
        .iter()
        .map(|(detector, profile)| GovernanceAggregationDetectorReport {
            detector: detector.clone(),
            reliability: profile.reliability,
            raw_calibration_error: profile.raw_error,
            reliability_scaled_error: profile.reliability_scaled_error,
            empirical_calibrated_error: profile.empirical_error,
            empirical_positive_rate: profile.positive_rate,
            observations: profile.observations,
        })
        .collect();

    let raw_scores: Vec<ScoredTruth> = dataset
        .observations
        .iter()
        .map(|observation| ScoredTruth {
            score: observation.risk_score,
            expected_harmful: observation.expected_harmful,
        })
        .collect();
    let reliability_scores: Vec<ScoredTruth> = dataset
        .observations
        .iter()
        .map(|observation| {
            let reliability = detector_profiles
                .get(&observation.detector)
                .map(|profile| profile.reliability)
                .unwrap_or(0.5);
            ScoredTruth {
                score: reliability_scaled_score(observation.risk_score, reliability),
                expected_harmful: observation.expected_harmful,
            }
        })
        .collect();
    let empirical_scores: Vec<ScoredTruth> = dataset
        .observations
        .iter()
        .map(|observation| {
            let profile = detector_profiles.get(&observation.detector);
            ScoredTruth {
                score: empirical_score(observation.risk_score, profile),
                expected_harmful: observation.expected_harmful,
            }
        })
        .collect();

    let raw = method_report("raw", &raw_scores, None, None);
    let reliability_scaled = method_report(
        "reliability_scaled",
        &reliability_scores,
        Some(&raw_scores),
        Some(&raw),
    );
    let empirical_calibrated = method_report(
        "empirical_calibrated",
        &empirical_scores,
        Some(&raw_scores),
        Some(&raw),
    );
    let best_method = [&raw, &reliability_scaled, &empirical_calibrated]
        .into_iter()
        .min_by(|a, b| {
            a.calibration_error
                .partial_cmp(&b.calibration_error)
                .unwrap_or(std::cmp::Ordering::Equal)
        })
        .map(|report| report.method.clone())
        .unwrap_or_else(|| "raw".to_string());
    let thresholds = GovernanceAggregationThresholds {
        calibration_error_max: 0.25,
        ranking_auc_min: 0.85,
        stability_min: 0.85,
    };
    let pass = empirical_calibrated.calibration_error <= thresholds.calibration_error_max
        && empirical_calibrated.ranking_auc >= thresholds.ranking_auc_min
        && empirical_calibrated.stability_score >= thresholds.stability_min
        && empirical_calibrated.calibration_error < raw.calibration_error;

    Ok(GovernanceAggregationEvaluationReport {
        tag,
        dataset: dataset_path,
        detector_count: detectors.len(),
        observation_count: dataset.observations.len(),
        best_method,
        raw,
        reliability_scaled,
        empirical_calibrated,
        pass,
        thresholds,
        rollback: GovernanceRollbackReport {
            rollback_model: "in_memory_reliability_calibrated_aggregation".to_string(),
            persistent_edge_mutations: 0,
            default_recall_behavior_changed: false,
            edge_deletions: 0,
        },
        detectors,
    })
}

fn detector_profile(
    observations: &[GovernanceAggregationObservationSpec],
) -> DetectorAggregationProfile {
    let total = observations.len();
    let mut true_positive = 0usize;
    let mut true_negative = 0usize;
    let mut false_positive = 0usize;
    let mut false_negative = 0usize;
    for observation in observations {
        match (
            observation.risk_score >= DETECTOR_THRESHOLD,
            observation.expected_harmful,
        ) {
            (true, true) => true_positive += 1,
            (true, false) => false_positive += 1,
            (false, false) => true_negative += 1,
            (false, true) => false_negative += 1,
        }
    }
    let correct = true_positive + true_negative;
    let reliability = (correct as f64 + 1.0) / (total as f64 + 2.0);
    let positives = observations
        .iter()
        .filter(|observation| observation.expected_harmful)
        .count();
    let positive_rate = positives as f64 / total.max(1) as f64;
    let precision = (true_positive as f64 + 1.0) / ((true_positive + false_positive) as f64 + 2.0);
    let negative_harmful_rate =
        (false_negative as f64 + 1.0) / ((true_negative + false_negative) as f64 + 2.0);
    let raw_error = mean_abs_error(
        observations
            .iter()
            .map(|observation| (observation.risk_score, observation.expected_harmful)),
    );
    let reliability_scaled_error = mean_abs_error(observations.iter().map(|observation| {
        (
            reliability_scaled_score(observation.risk_score, reliability),
            observation.expected_harmful,
        )
    }));
    let empirical_error = mean_abs_error(observations.iter().map(|observation| {
        (
            empirical_score(
                observation.risk_score,
                Some(&DetectorAggregationProfile {
                    reliability,
                    positive_rate,
                    precision,
                    negative_harmful_rate,
                    observations: total,
                    raw_error: 0.0,
                    reliability_scaled_error: 0.0,
                    empirical_error: 0.0,
                }),
            ),
            observation.expected_harmful,
        )
    }));
    DetectorAggregationProfile {
        reliability,
        positive_rate,
        precision,
        negative_harmful_rate,
        observations: total,
        raw_error,
        reliability_scaled_error,
        empirical_error,
    }
}

fn reliability_scaled_score(score: f64, reliability: f64) -> f64 {
    0.5 + (score.clamp(0.0, 1.0) - 0.5) * (2.0 * reliability.clamp(0.0, 1.0) - 1.0)
}

fn empirical_score(score: f64, profile: Option<&DetectorAggregationProfile>) -> f64 {
    let Some(profile) = profile else {
        return score.clamp(0.0, 1.0);
    };
    let class_probability = if score >= DETECTOR_THRESHOLD {
        profile.precision
    } else {
        profile.negative_harmful_rate
    };
    let margin = (score - DETECTOR_THRESHOLD).abs().min(0.35) / 0.35;
    let prior_weight = 0.20 * (1.0 - margin);
    ((1.0 - prior_weight) * class_probability + prior_weight * profile.positive_rate)
        .clamp(0.0, 1.0)
}

fn method_report(
    method: &str,
    scores: &[ScoredTruth],
    raw_scores: Option<&[ScoredTruth]>,
    raw: Option<&GovernanceAggregationMethodReport>,
) -> GovernanceAggregationMethodReport {
    let calibration_error = mean_abs_error(
        scores
            .iter()
            .map(|score| (score.score, score.expected_harmful)),
    );
    let calibration_error_delta_vs_raw = raw
        .map(|raw| raw.calibration_error - calibration_error)
        .unwrap_or(0.0);
    GovernanceAggregationMethodReport {
        method: method.to_string(),
        calibration_error,
        calibration_error_delta_vs_raw,
        ranking_auc: ranking_auc(scores),
        stability_score: stability_score(scores, raw_scores),
    }
}

fn mean_abs_error(values: impl Iterator<Item = (f64, bool)>) -> f64 {
    let mut total = 0.0;
    let mut count = 0usize;
    for (score, expected_harmful) in values {
        let truth = if expected_harmful { 1.0 } else { 0.0 };
        total += (score.clamp(0.0, 1.0) - truth).abs();
        count += 1;
    }
    if count == 0 {
        0.0
    } else {
        total / count as f64
    }
}

fn ranking_auc(scores: &[ScoredTruth]) -> f64 {
    let positives: Vec<&ScoredTruth> = scores
        .iter()
        .filter(|score| score.expected_harmful)
        .collect();
    let negatives: Vec<&ScoredTruth> = scores
        .iter()
        .filter(|score| !score.expected_harmful)
        .collect();
    if positives.is_empty() || negatives.is_empty() {
        return 1.0;
    }
    let mut wins = 0.0;
    for positive in &positives {
        for negative in &negatives {
            if positive.score > negative.score {
                wins += 1.0;
            } else if (positive.score - negative.score).abs() <= f64::EPSILON {
                wins += 0.5;
            }
        }
    }
    wins / (positives.len() * negatives.len()) as f64
}

fn stability_score(scores: &[ScoredTruth], raw_scores: Option<&[ScoredTruth]>) -> f64 {
    let Some(raw_scores) = raw_scores else {
        return 1.0;
    };
    if scores.is_empty() || scores.len() != raw_scores.len() {
        return 0.0;
    }
    let mean_shift = scores
        .iter()
        .zip(raw_scores.iter())
        .map(|(score, raw_score)| (score.score - raw_score.score).abs())
        .sum::<f64>()
        / scores.len() as f64;
    (1.0 - mean_shift).clamp(0.0, 1.0)
}

#[derive(Debug, Clone, Copy)]
struct ScoredTruth {
    score: f64,
    expected_harmful: bool,
}

#[derive(Debug, Clone)]
struct DetectorAggregationProfile {
    reliability: f64,
    positive_rate: f64,
    precision: f64,
    negative_harmful_rate: f64,
    observations: usize,
    raw_error: f64,
    reliability_scaled_error: f64,
    empirical_error: f64,
}

#[derive(Debug, Deserialize)]
struct GovernanceAggregationDataset {
    observations: Vec<GovernanceAggregationObservationSpec>,
}

#[derive(Debug, Clone, Deserialize)]
struct GovernanceAggregationObservationSpec {
    detector: String,
    risk_score: f64,
    expected_harmful: bool,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn ranking_auc_rewards_positive_scores_above_negative_scores() {
        let scores = vec![
            ScoredTruth {
                score: 0.9,
                expected_harmful: true,
            },
            ScoredTruth {
                score: 0.1,
                expected_harmful: false,
            },
        ];

        assert!((ranking_auc(&scores) - 1.0).abs() < f64::EPSILON);
    }

    #[test]
    fn stability_score_rewards_small_movement_from_raw_scores() {
        let raw_scores = vec![
            ScoredTruth {
                score: 0.8,
                expected_harmful: true,
            },
            ScoredTruth {
                score: 0.2,
                expected_harmful: false,
            },
        ];
        let calibrated_scores = vec![
            ScoredTruth {
                score: 0.75,
                expected_harmful: true,
            },
            ScoredTruth {
                score: 0.25,
                expected_harmful: false,
            },
        ];

        assert!((stability_score(&calibrated_scores, Some(&raw_scores)) - 0.95).abs() < 1e-9);
    }
}
