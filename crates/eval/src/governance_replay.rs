use crate::types::{
    GovernanceReplayCaseReport, GovernanceReplayDetectorReport, GovernanceReplayEvaluationReport,
    GovernanceReplayEventReport, GovernanceReplayThresholds, GovernanceRollbackReport,
};
use anyhow::{Context, Result};
use serde::Deserialize;
use std::collections::BTreeMap;
use std::path::Path;

const DETECTOR_THRESHOLD: f64 = 0.65;
const DECISION_THRESHOLD: f64 = 0.50;
const MAX_SUPPRESSION: f64 = 0.85;

pub struct GovernanceReplayEvaluator;

impl GovernanceReplayEvaluator {
    pub fn evaluate(
        replay_dataset_path: impl AsRef<Path>,
        feedback_dataset_path: impl AsRef<Path>,
        tag: impl Into<String>,
    ) -> Result<GovernanceReplayEvaluationReport> {
        let replay_dataset_path = replay_dataset_path.as_ref();
        let feedback_dataset_path = feedback_dataset_path.as_ref();
        let replay_raw = std::fs::read_to_string(replay_dataset_path).with_context(|| {
            format!(
                "reading governance replay dataset {}",
                replay_dataset_path.display()
            )
        })?;
        let feedback_raw = std::fs::read_to_string(feedback_dataset_path).with_context(|| {
            format!(
                "reading governance feedback dataset {}",
                feedback_dataset_path.display()
            )
        })?;
        let replay_dataset: GovernanceReplayDataset =
            toml::from_str(&replay_raw).context("parsing governance replay dataset TOML")?;
        let feedback_dataset: GovernanceFeedbackDataset =
            toml::from_str(&feedback_raw).context("parsing governance feedback dataset TOML")?;
        evaluate_dataset(
            replay_dataset,
            feedback_dataset,
            replay_dataset_path.display().to_string(),
            feedback_dataset_path.display().to_string(),
            tag.into(),
        )
    }
}

fn evaluate_dataset(
    replay_dataset: GovernanceReplayDataset,
    feedback_dataset: GovernanceFeedbackDataset,
    dataset_path: String,
    feedback_dataset_path: String,
    tag: String,
) -> Result<GovernanceReplayEvaluationReport> {
    if replay_dataset.cases.is_empty() {
        anyhow::bail!("governance replay dataset has no cases");
    }
    if feedback_dataset.observations.is_empty() {
        anyhow::bail!("governance replay feedback dataset has no observations");
    }

    let detector_profiles = detector_profiles(&feedback_dataset.observations);
    let detectors = detector_profiles
        .iter()
        .map(|(detector, profile)| GovernanceReplayDetectorReport {
            detector: detector.clone(),
            reliability: profile.reliability,
            precision_when_flagged: profile.precision,
            harmful_rate_when_safe: profile.negative_harmful_rate,
            positive_rate: profile.positive_rate,
            observations: profile.observations,
        })
        .collect::<Vec<_>>();

    let mut case_reports = Vec::with_capacity(replay_dataset.cases.len());
    let mut baseline_correct = 0usize;
    let mut governed_correct = 0usize;
    let mut event_count = 0usize;
    let mut baseline_regret_total = 0.0;
    let mut governed_regret_total = 0.0;
    let mut impact_total = 0.0;
    let mut normal_event_count = 0usize;
    let mut normal_governed_correct = 0usize;
    let mut normal_influence_events = 0usize;
    let mut over_conservative_events = 0usize;
    let mut normal_shift_total = 0.0;
    let mut normal_case_count = 0usize;

    for case in replay_dataset.cases {
        let profile = detector_profiles.get(&case.detector);
        let calibrated_risk = calibrated_risk(case.raw_risk, profile);
        let suppression_strength = suppression_strength(calibrated_risk);
        let baseline_influence = case.baseline_influence.clamp(0.0, 1.0);
        let governed_influence =
            (baseline_influence * (1.0 - suppression_strength)).clamp(0.0, 1.0);
        let mut case_baseline_correct = 0usize;
        let mut case_governed_correct = 0usize;
        let mut case_baseline_regret = 0.0;
        let mut case_governed_regret = 0.0;
        let mut case_impact_total = 0.0;
        let mut case_over_conservative_events = 0usize;
        let mut event_reports = Vec::with_capacity(case.events.len());

        if !case.expected_harmful {
            normal_case_count += 1;
            normal_shift_total += (baseline_influence - governed_influence).abs();
        }

        for event in case.events {
            let desired_influence = event.desired_influence.clamp(0.0, 1.0);
            let impact_weight = event.impact_weight.unwrap_or(1.0).max(0.0);
            let expected_prediction = desired_influence >= DECISION_THRESHOLD;
            let baseline_prediction = baseline_influence >= DECISION_THRESHOLD;
            let governed_prediction = governed_influence >= DECISION_THRESHOLD;
            let baseline_event_correct = baseline_prediction == expected_prediction;
            let governed_event_correct = governed_prediction == expected_prediction;
            let baseline_regret = (baseline_influence - desired_influence).abs() * impact_weight;
            let governed_regret = (governed_influence - desired_influence).abs() * impact_weight;

            baseline_correct += usize::from(baseline_event_correct);
            governed_correct += usize::from(governed_event_correct);
            event_count += 1;
            baseline_regret_total += baseline_regret;
            governed_regret_total += governed_regret;
            impact_total += impact_weight;

            case_baseline_correct += usize::from(baseline_event_correct);
            case_governed_correct += usize::from(governed_event_correct);
            case_baseline_regret += baseline_regret;
            case_governed_regret += governed_regret;
            case_impact_total += impact_weight;

            if !case.expected_harmful {
                normal_event_count += 1;
                normal_governed_correct += usize::from(governed_event_correct);
                if expected_prediction {
                    normal_influence_events += 1;
                    if !governed_prediction {
                        over_conservative_events += 1;
                        case_over_conservative_events += 1;
                    }
                }
            }

            event_reports.push(GovernanceReplayEventReport {
                id: event.id,
                desired_influence,
                impact_weight,
                baseline_prediction,
                governed_prediction,
                expected_prediction,
                baseline_correct: baseline_event_correct,
                governed_correct: governed_event_correct,
                baseline_regret,
                governed_regret,
                regret_delta: baseline_regret - governed_regret,
            });
        }

        let case_event_count = event_reports.len().max(1) as f64;
        let case_baseline_accuracy = case_baseline_correct as f64 / case_event_count;
        let case_governed_accuracy = case_governed_correct as f64 / case_event_count;
        let case_baseline_regret_mean = safe_div(case_baseline_regret, case_impact_total);
        let case_governed_regret_mean = safe_div(case_governed_regret, case_impact_total);

        case_reports.push(GovernanceReplayCaseReport {
            id: case.id,
            detector: case.detector,
            expected_harmful: case.expected_harmful,
            raw_risk: case.raw_risk,
            calibrated_risk,
            baseline_influence,
            governed_influence,
            suppression_strength,
            baseline_accuracy: case_baseline_accuracy,
            governed_accuracy: case_governed_accuracy,
            counterfactual_gain: case_governed_accuracy - case_baseline_accuracy,
            baseline_regret: case_baseline_regret_mean,
            governed_regret: case_governed_regret_mean,
            regret_reduction: case_baseline_regret_mean - case_governed_regret_mean,
            over_conservative_events: case_over_conservative_events,
            events: event_reports,
        });
    }

    let baseline_accuracy = safe_div(baseline_correct as f64, event_count as f64);
    let governed_accuracy = safe_div(governed_correct as f64, event_count as f64);
    let baseline_regret = safe_div(baseline_regret_total, impact_total);
    let governed_regret = safe_div(governed_regret_total, impact_total);
    let regret_reduction = baseline_regret - governed_regret;
    let regret_reduction_rate = safe_div(regret_reduction, baseline_regret.max(f64::EPSILON));
    let normal_preservation = if normal_event_count == 0 {
        1.0
    } else {
        normal_governed_correct as f64 / normal_event_count as f64
    };
    let over_conservatism_rate = if normal_influence_events == 0 {
        0.0
    } else {
        over_conservative_events as f64 / normal_influence_events as f64
    };
    let stability_score = if normal_case_count == 0 {
        1.0
    } else {
        (1.0 - normal_shift_total / normal_case_count as f64).clamp(0.0, 1.0)
    };
    let thresholds = GovernanceReplayThresholds {
        counterfactual_gain_min: 0.15,
        regret_reduction_min: 0.15,
        normal_preservation_min: 0.95,
        over_conservatism_max: 0.05,
        stability_min: 0.90,
    };
    let pass = governed_accuracy - baseline_accuracy >= thresholds.counterfactual_gain_min
        && regret_reduction >= thresholds.regret_reduction_min
        && normal_preservation >= thresholds.normal_preservation_min
        && over_conservatism_rate <= thresholds.over_conservatism_max
        && stability_score >= thresholds.stability_min;

    Ok(GovernanceReplayEvaluationReport {
        tag,
        dataset: dataset_path,
        feedback_dataset: feedback_dataset_path,
        detector_count: detectors.len(),
        case_count: case_reports.len(),
        event_count,
        baseline_accuracy,
        governed_accuracy,
        counterfactual_gain: governed_accuracy - baseline_accuracy,
        baseline_regret,
        governed_regret,
        regret_reduction,
        regret_reduction_rate,
        normal_preservation,
        over_conservatism_rate,
        stability_score,
        pass,
        thresholds,
        rollback: GovernanceRollbackReport {
            rollback_model: "counterfactual_replay_only".to_string(),
            persistent_edge_mutations: 0,
            default_recall_behavior_changed: false,
            edge_deletions: 0,
        },
        detectors,
        cases: case_reports,
    })
}

fn detector_profiles(
    observations: &[GovernanceFeedbackObservationSpec],
) -> BTreeMap<String, DetectorReplayProfile> {
    let mut by_detector: BTreeMap<String, Vec<&GovernanceFeedbackObservationSpec>> =
        BTreeMap::new();
    for observation in observations {
        by_detector
            .entry(observation.detector.clone())
            .or_default()
            .push(observation);
    }
    by_detector
        .into_iter()
        .map(|(detector, observations)| (detector, detector_profile(&observations)))
        .collect()
}

fn detector_profile(observations: &[&GovernanceFeedbackObservationSpec]) -> DetectorReplayProfile {
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
    let positives = observations
        .iter()
        .filter(|observation| observation.expected_harmful)
        .count();
    DetectorReplayProfile {
        reliability: (correct as f64 + 1.0) / (total as f64 + 2.0),
        positive_rate: positives as f64 / total.max(1) as f64,
        precision: (true_positive as f64 + 1.0) / ((true_positive + false_positive) as f64 + 2.0),
        negative_harmful_rate: (false_negative as f64 + 1.0)
            / ((true_negative + false_negative) as f64 + 2.0),
        observations: total,
    }
}

fn calibrated_risk(score: f64, profile: Option<&DetectorReplayProfile>) -> f64 {
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

fn suppression_strength(calibrated_risk: f64) -> f64 {
    if calibrated_risk <= DECISION_THRESHOLD {
        0.0
    } else {
        (((calibrated_risk - DECISION_THRESHOLD) / (1.0 - DECISION_THRESHOLD)) * MAX_SUPPRESSION)
            .clamp(0.0, MAX_SUPPRESSION)
    }
}

fn safe_div(numerator: f64, denominator: f64) -> f64 {
    if denominator.abs() <= f64::EPSILON {
        0.0
    } else {
        numerator / denominator
    }
}

#[derive(Debug, Clone)]
struct DetectorReplayProfile {
    reliability: f64,
    positive_rate: f64,
    precision: f64,
    negative_harmful_rate: f64,
    observations: usize,
}

#[derive(Debug, Deserialize)]
struct GovernanceFeedbackDataset {
    observations: Vec<GovernanceFeedbackObservationSpec>,
}

#[derive(Debug, Deserialize)]
struct GovernanceFeedbackObservationSpec {
    detector: String,
    risk_score: f64,
    expected_harmful: bool,
}

#[derive(Debug, Deserialize)]
struct GovernanceReplayDataset {
    cases: Vec<GovernanceReplayCaseSpec>,
}

#[derive(Debug, Deserialize)]
struct GovernanceReplayCaseSpec {
    id: String,
    detector: String,
    raw_risk: f64,
    expected_harmful: bool,
    baseline_influence: f64,
    events: Vec<GovernanceReplayEventSpec>,
}

#[derive(Debug, Deserialize)]
struct GovernanceReplayEventSpec {
    id: String,
    desired_influence: f64,
    #[serde(default)]
    impact_weight: Option<f64>,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn calibrated_risk_uses_negative_harmful_rate_below_threshold() {
        let profile = DetectorReplayProfile {
            reliability: 0.8,
            positive_rate: 0.5,
            precision: 0.8,
            negative_harmful_rate: 0.2,
            observations: 8,
        };

        let score = calibrated_risk(0.20, Some(&profile));

        assert!(score < 0.30);
    }

    #[test]
    fn suppression_only_starts_after_calibrated_risk_crosses_decision_threshold() {
        assert_eq!(suppression_strength(0.49), 0.0);
        assert!(suppression_strength(0.80) > 0.0);
    }
}
