use crate::types::{
    GovernanceRecoveryEvaluationReport, GovernanceRecoveryScenarioReport,
    GovernanceRecoveryStepReport, GovernanceRecoveryThresholds, GovernanceRollbackReport,
};
use anyhow::{Context, Result};
use serde::Deserialize;
use std::path::Path;

const RECOVERY_THRESHOLD: f64 = 0.10;
const DOMINANCE_MARGIN: f64 = 0.05;
const PRESSURE_THRESHOLD: f64 = 0.30;
const MAX_SUPPRESSION: f64 = 0.50;

pub struct GovernanceRecoveryEvaluator;

impl GovernanceRecoveryEvaluator {
    pub fn evaluate(
        dataset_path: impl AsRef<Path>,
        tag: impl Into<String>,
    ) -> Result<GovernanceRecoveryEvaluationReport> {
        let dataset_path = dataset_path.as_ref();
        let raw = std::fs::read_to_string(dataset_path).with_context(|| {
            format!(
                "reading governance recovery dataset {}",
                dataset_path.display()
            )
        })?;
        let dataset: GovernanceRecoveryDataset =
            toml::from_str(&raw).context("parsing governance recovery dataset TOML")?;
        evaluate_dataset(dataset, dataset_path.display().to_string(), tag.into())
    }
}

fn evaluate_dataset(
    dataset: GovernanceRecoveryDataset,
    dataset_path: String,
    tag: String,
) -> Result<GovernanceRecoveryEvaluationReport> {
    if dataset.scenarios.is_empty() {
        anyhow::bail!("governance recovery dataset has no scenarios");
    }

    let mut scenario_reports = Vec::with_capacity(dataset.scenarios.len());
    let mut step_count = 0usize;
    let mut recovery_scenarios = 0usize;
    let mut recovery_successes = 0usize;
    let mut target_recoveries = 0usize;
    let mut dominant_shifts = 0usize;
    let mut relapses = 0usize;
    let mut recovery_scores = Vec::new();
    let mut recovery_gain_total = 0.0;
    let mut latency_gains = Vec::new();
    let mut normal_steps = 0usize;
    let mut normal_preserved_steps = 0usize;
    let mut normal_active_steps = 0usize;
    let mut over_correction_steps = 0usize;
    let mut normal_shift_total = 0.0;

    for scenario in dataset.scenarios {
        let report = evaluate_scenario(&scenario)?;
        step_count += report.steps.len();
        if report.expected_recovery {
            recovery_scenarios += 1;
            recovery_successes += usize::from(report.recovery_success);
            target_recoveries += usize::from(report.governed_recovery_step.is_some());
            dominant_shifts += usize::from(report.governed_dominant_shift_step.is_some());
            relapses += usize::from(report.relapsed);
            recovery_scores.push(report.recovery_score);
            recovery_gain_total += report.recovery_gain;
            latency_gains.push(report.latency_gain);
        } else {
            for step in &report.steps {
                normal_steps += 1;
                let baseline_active = step.baseline_misbelief_influence >= 0.50;
                let governed_active = step.governed_misbelief_influence >= 0.50;
                normal_preserved_steps += usize::from(baseline_active == governed_active);
                normal_shift_total +=
                    (step.baseline_misbelief_influence - step.governed_misbelief_influence).abs();
                if baseline_active {
                    normal_active_steps += 1;
                    if !governed_active {
                        over_correction_steps += 1;
                    }
                }
            }
        }
        scenario_reports.push(report);
    }

    let recovery_success_rate = safe_div(recovery_successes as f64, recovery_scenarios as f64);
    let target_recovery_rate = safe_div(target_recoveries as f64, recovery_scenarios as f64);
    let recovery_score = mean(&recovery_scores).unwrap_or(1.0);
    let recovery_gain = safe_div(recovery_gain_total, recovery_scenarios as f64);
    let latency_improvement = mean(&latency_gains).unwrap_or(1.0);
    let dominant_shift_rate = safe_div(dominant_shifts as f64, recovery_scenarios as f64);
    let relapse_rate = safe_div(relapses as f64, recovery_scenarios as f64);
    let normal_preservation = if normal_steps == 0 {
        1.0
    } else {
        normal_preserved_steps as f64 / normal_steps as f64
    };
    let over_correction_rate = safe_div(over_correction_steps as f64, normal_active_steps as f64);
    let stability_score = if normal_steps == 0 {
        1.0
    } else {
        (1.0 - normal_shift_total / normal_steps as f64).clamp(0.0, 1.0)
    };
    let thresholds = GovernanceRecoveryThresholds {
        recovery_success_min: 0.75,
        recovery_score_min: 0.60,
        recovery_gain_min: 0.16,
        latency_improvement_min: 0.20,
        dominant_shift_min: 0.75,
        relapse_max: 0.20,
        normal_preservation_min: 0.95,
        over_correction_max: 0.05,
        stability_min: 0.90,
    };
    let pass = recovery_success_rate >= thresholds.recovery_success_min
        && recovery_score >= thresholds.recovery_score_min
        && recovery_gain >= thresholds.recovery_gain_min
        && latency_improvement >= thresholds.latency_improvement_min
        && dominant_shift_rate >= thresholds.dominant_shift_min
        && relapse_rate <= thresholds.relapse_max
        && normal_preservation >= thresholds.normal_preservation_min
        && over_correction_rate <= thresholds.over_correction_max
        && stability_score >= thresholds.stability_min;

    Ok(GovernanceRecoveryEvaluationReport {
        tag,
        dataset: dataset_path,
        scenario_count: scenario_reports.len(),
        step_count,
        recovery_scenarios,
        recovery_success_rate,
        target_recovery_rate,
        recovery_score,
        recovery_gain,
        latency_improvement,
        dominant_shift_rate,
        relapse_rate,
        normal_preservation,
        over_correction_rate,
        stability_score,
        pass,
        thresholds,
        rollback: GovernanceRollbackReport {
            rollback_model: "belief_recovery_counterfactual_only".to_string(),
            persistent_edge_mutations: 0,
            default_recall_behavior_changed: false,
            edge_deletions: 0,
        },
        scenarios: scenario_reports,
    })
}

fn evaluate_scenario(
    scenario: &GovernanceRecoveryScenarioSpec,
) -> Result<GovernanceRecoveryScenarioReport> {
    if scenario.steps.is_empty() {
        anyhow::bail!("governance recovery scenario {} has no steps", scenario.id);
    }

    let mut baseline_misbelief = scenario.initial_misbelief_influence.clamp(0.0, 1.0);
    let mut governed_misbelief = baseline_misbelief;
    let mut baseline_adaptive = scenario.initial_adaptive_influence.clamp(0.0, 1.0);
    let mut governed_adaptive = baseline_adaptive;
    let target_misbelief = scenario.target_misbelief_influence.clamp(0.0, 1.0);
    let target_adaptive = scenario.target_adaptive_influence.clamp(0.0, 1.0);
    let mut recovery_signal = 0.0;
    let mut baseline_recovery_step = None;
    let mut governed_recovery_step = None;
    let mut baseline_dominant_shift_step = None;
    let mut governed_dominant_shift_step = None;
    let mut baseline_regret_total = 0.0;
    let mut governed_regret_total = 0.0;
    let mut impact_total = 0.0;
    let mut steps = Vec::with_capacity(scenario.steps.len());

    for (index, step) in scenario.steps.iter().enumerate() {
        let step_index = index + 1;
        let counter_evidence = step.counter_evidence.unwrap_or(0.0).max(0.0);
        let adaptive_evidence = step.adaptive_evidence.unwrap_or(0.0).max(0.0);
        let relapse_pressure = step.relapse_pressure.unwrap_or(0.0).max(0.0);
        let desired_misbelief = step.desired_misbelief_influence.clamp(0.0, 1.0);
        let desired_adaptive = step.desired_adaptive_influence.clamp(0.0, 1.0);
        let impact_weight = step.impact_weight.unwrap_or(1.0).max(0.0);

        baseline_misbelief = (baseline_misbelief + relapse_pressure
            - 0.18 * counter_evidence
            - 0.08 * adaptive_evidence)
            .clamp(0.0, 1.0);
        baseline_adaptive =
            (baseline_adaptive + 0.35 * adaptive_evidence + 0.10 * counter_evidence
                - 0.05 * relapse_pressure)
                .clamp(0.0, 1.0);

        recovery_signal = (0.72 * recovery_signal + counter_evidence + 0.55 * adaptive_evidence
            - 0.25 * relapse_pressure)
            .clamp(0.0, 1.0);
        let recovery_pressure = recovery_pressure(recovery_signal);
        governed_misbelief = (governed_misbelief + 0.55 * relapse_pressure
            - 0.40 * counter_evidence
            - 0.20 * adaptive_evidence)
            .clamp(0.0, 1.0);
        governed_misbelief *= 1.0 - recovery_pressure;
        governed_misbelief = governed_misbelief.clamp(0.0, 1.0);
        governed_adaptive =
            (governed_adaptive + 0.72 * adaptive_evidence + 0.24 * counter_evidence
                - 0.03 * relapse_pressure)
                .clamp(0.0, 1.0);

        if baseline_recovery_step.is_none() && recovered(baseline_misbelief, target_misbelief) {
            baseline_recovery_step = Some(step_index);
        }
        if governed_recovery_step.is_none() && recovered(governed_misbelief, target_misbelief) {
            governed_recovery_step = Some(step_index);
        }
        if baseline_dominant_shift_step.is_none()
            && baseline_adaptive >= baseline_misbelief + DOMINANCE_MARGIN
        {
            baseline_dominant_shift_step = Some(step_index);
        }
        if governed_dominant_shift_step.is_none()
            && governed_adaptive >= governed_misbelief + DOMINANCE_MARGIN
        {
            governed_dominant_shift_step = Some(step_index);
        }

        let baseline_regret = influence_regret(
            baseline_misbelief,
            baseline_adaptive,
            desired_misbelief,
            desired_adaptive,
        ) * impact_weight;
        let governed_regret = influence_regret(
            governed_misbelief,
            governed_adaptive,
            desired_misbelief,
            desired_adaptive,
        ) * impact_weight;
        baseline_regret_total += baseline_regret;
        governed_regret_total += governed_regret;
        impact_total += impact_weight;

        steps.push(GovernanceRecoveryStepReport {
            index: step_index,
            event: step.event.clone(),
            counter_evidence,
            adaptive_evidence,
            relapse_pressure,
            recovery_signal,
            recovery_pressure,
            desired_misbelief_influence: desired_misbelief,
            desired_adaptive_influence: desired_adaptive,
            baseline_misbelief_influence: baseline_misbelief,
            governed_misbelief_influence: governed_misbelief,
            baseline_adaptive_influence: baseline_adaptive,
            governed_adaptive_influence: governed_adaptive,
            baseline_dominant: dominant_label(baseline_misbelief, baseline_adaptive),
            governed_dominant: dominant_label(governed_misbelief, governed_adaptive),
            baseline_regret,
            governed_regret,
        });
    }

    let baseline_regret = safe_div(baseline_regret_total, impact_total);
    let governed_regret = safe_div(governed_regret_total, impact_total);
    let recovery_gain = baseline_regret - governed_regret;
    let total_steps = scenario.steps.len() + 1;
    let baseline_latency = baseline_dominant_shift_step
        .or(baseline_recovery_step)
        .unwrap_or(total_steps);
    let governed_latency = governed_dominant_shift_step
        .or(governed_recovery_step)
        .unwrap_or(total_steps);
    let latency_gain = safe_div(
        (baseline_latency as isize - governed_latency as isize).max(0) as f64,
        total_steps as f64,
    );
    let functional_recovery_score = recovery_score(
        baseline_misbelief,
        governed_misbelief,
        baseline_adaptive,
        governed_adaptive,
        target_misbelief,
        target_adaptive,
    );
    let recovery_success = scenario.expected_recovery
        && functional_recovery_score >= 0.60
        && governed_dominant_shift_step.is_some();
    let relapsed = if let Some(recovery_step) = governed_recovery_step {
        steps
            .iter()
            .skip(recovery_step)
            .any(|step| step.governed_misbelief_influence > target_misbelief + 0.18)
    } else {
        false
    };
    let over_correction_events = if scenario.expected_recovery {
        0
    } else {
        steps
            .iter()
            .filter(|step| {
                step.baseline_misbelief_influence >= 0.50
                    && step.governed_misbelief_influence < 0.50
            })
            .count()
    };

    Ok(GovernanceRecoveryScenarioReport {
        id: scenario.id.clone(),
        pattern: scenario.pattern.clone(),
        scenario_type: scenario.scenario_type.clone(),
        expected_recovery: scenario.expected_recovery,
        initial_misbelief_influence: scenario.initial_misbelief_influence,
        initial_adaptive_influence: scenario.initial_adaptive_influence,
        target_misbelief_influence: target_misbelief,
        target_adaptive_influence: target_adaptive,
        baseline_final_misbelief: baseline_misbelief,
        governed_final_misbelief: governed_misbelief,
        baseline_final_adaptive: baseline_adaptive,
        governed_final_adaptive: governed_adaptive,
        baseline_recovery_step,
        governed_recovery_step,
        baseline_dominant_shift_step,
        governed_dominant_shift_step,
        recovery_success,
        relapsed,
        baseline_regret,
        governed_regret,
        recovery_gain,
        recovery_score: functional_recovery_score,
        latency_gain,
        over_correction_events,
        steps,
    })
}

fn recovery_pressure(recovery_signal: f64) -> f64 {
    if recovery_signal <= PRESSURE_THRESHOLD {
        0.0
    } else {
        (((recovery_signal - PRESSURE_THRESHOLD) / (1.0 - PRESSURE_THRESHOLD)) * MAX_SUPPRESSION)
            .clamp(0.0, MAX_SUPPRESSION)
    }
}

fn recovered(misbelief: f64, target_misbelief: f64) -> bool {
    misbelief <= target_misbelief + RECOVERY_THRESHOLD
}

fn influence_regret(
    misbelief: f64,
    adaptive: f64,
    desired_misbelief: f64,
    desired_adaptive: f64,
) -> f64 {
    ((misbelief - desired_misbelief).abs() + (adaptive - desired_adaptive).abs()) / 2.0
}

fn recovery_score(
    baseline_misbelief: f64,
    governed_misbelief: f64,
    baseline_adaptive: f64,
    governed_adaptive: f64,
    target_misbelief: f64,
    target_adaptive: f64,
) -> f64 {
    let baseline_error = influence_regret(
        baseline_misbelief,
        baseline_adaptive,
        target_misbelief,
        target_adaptive,
    );
    let governed_error = influence_regret(
        governed_misbelief,
        governed_adaptive,
        target_misbelief,
        target_adaptive,
    );
    if baseline_error <= f64::EPSILON {
        1.0
    } else {
        ((baseline_error - governed_error) / baseline_error).clamp(0.0, 1.0)
    }
}

fn dominant_label(misbelief: f64, adaptive: f64) -> String {
    if adaptive >= misbelief + DOMINANCE_MARGIN {
        "adaptive".to_string()
    } else if misbelief >= adaptive + DOMINANCE_MARGIN {
        "misbelief".to_string()
    } else {
        "balanced".to_string()
    }
}

fn safe_div(numerator: f64, denominator: f64) -> f64 {
    if denominator.abs() <= f64::EPSILON {
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
struct GovernanceRecoveryDataset {
    scenarios: Vec<GovernanceRecoveryScenarioSpec>,
}

#[derive(Debug, Deserialize)]
struct GovernanceRecoveryScenarioSpec {
    id: String,
    pattern: String,
    scenario_type: String,
    expected_recovery: bool,
    initial_misbelief_influence: f64,
    initial_adaptive_influence: f64,
    target_misbelief_influence: f64,
    target_adaptive_influence: f64,
    steps: Vec<GovernanceRecoveryStepSpec>,
}

#[derive(Debug, Deserialize)]
struct GovernanceRecoveryStepSpec {
    event: String,
    desired_misbelief_influence: f64,
    desired_adaptive_influence: f64,
    #[serde(default)]
    counter_evidence: Option<f64>,
    #[serde(default)]
    adaptive_evidence: Option<f64>,
    #[serde(default)]
    relapse_pressure: Option<f64>,
    #[serde(default)]
    impact_weight: Option<f64>,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn recovery_pressure_waits_for_accumulated_signal() {
        assert_eq!(recovery_pressure(PRESSURE_THRESHOLD - 0.01), 0.0);
        assert!(recovery_pressure(PRESSURE_THRESHOLD + 0.20) > 0.0);
    }

    #[test]
    fn recovery_score_rewards_movement_toward_target() {
        let score = recovery_score(0.8, 0.3, 0.2, 0.7, 0.2, 0.75);

        assert!(score > 0.5);
    }
}
