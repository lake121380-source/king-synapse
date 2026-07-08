use crate::types::{
    GovernanceDriftEvaluationReport, GovernanceDriftPatternReport, GovernanceDriftScenarioReport,
    GovernanceDriftStepReport, GovernanceDriftThresholds, GovernanceRollbackReport,
};
use anyhow::{Context, Result};
use serde::Deserialize;
use std::collections::BTreeMap;
use std::path::Path;

const DOMINANCE_THRESHOLD: f64 = 0.65;
const PRESSURE_THRESHOLD: f64 = 0.38;
const MAX_SUPPRESSION: f64 = 0.55;

pub struct GovernanceDriftEvaluator;

impl GovernanceDriftEvaluator {
    pub fn evaluate(
        dataset_path: impl AsRef<Path>,
        tag: impl Into<String>,
    ) -> Result<GovernanceDriftEvaluationReport> {
        let dataset_path = dataset_path.as_ref();
        let raw = std::fs::read_to_string(dataset_path).with_context(|| {
            format!(
                "reading governance drift dataset {}",
                dataset_path.display()
            )
        })?;
        let dataset: GovernanceDriftDataset =
            toml::from_str(&raw).context("parsing governance drift dataset TOML")?;
        evaluate_dataset(dataset, dataset_path.display().to_string(), tag.into())
    }
}

fn evaluate_dataset(
    dataset: GovernanceDriftDataset,
    dataset_path: String,
    tag: String,
) -> Result<GovernanceDriftEvaluationReport> {
    if dataset.scenarios.is_empty() {
        anyhow::bail!("governance drift dataset has no scenarios");
    }

    let mut pattern_memory: BTreeMap<String, PatternMemory> = BTreeMap::new();
    let mut scenario_reports = Vec::with_capacity(dataset.scenarios.len());
    let mut total_steps = 0usize;
    let mut harmful_scenarios = 0usize;
    let mut weak_bias_scenarios = 0usize;
    let mut detected_weak_bias_scenarios = 0usize;
    let mut governed_regret_total = 0.0;
    let mut no_pattern_regret_total = 0.0;
    let mut impact_total = 0.0;
    let mut harmful_baseline_regret_total = 0.0;
    let mut harmful_governed_regret_total = 0.0;
    let mut harmful_impact_total = 0.0;
    let mut recovery_scores = Vec::new();
    let mut normal_steps = 0usize;
    let mut normal_preserved_steps = 0usize;
    let mut normal_influence_steps = 0usize;
    let mut over_correction_steps = 0usize;
    let mut normal_shift_total = 0.0;
    let mut normal_shift_count = 0usize;

    for scenario in dataset.scenarios {
        let pattern_prior = pattern_memory
            .get(&scenario.pattern)
            .map(|memory| memory.pattern_risk)
            .unwrap_or(0.0);
        let scenario_report = evaluate_scenario(&scenario, pattern_prior)?;
        total_steps += scenario_report.steps.len();

        let scenario_impact = scenario
            .steps
            .iter()
            .map(|step| step.impact_weight.unwrap_or(1.0).max(0.0))
            .sum::<f64>();
        governed_regret_total += scenario_report.governed_regret * scenario_impact;
        no_pattern_regret_total += scenario_report.no_pattern_regret * scenario_impact;
        impact_total += scenario_impact;

        if scenario.expected_harmful {
            harmful_scenarios += 1;
            harmful_baseline_regret_total += scenario_report.baseline_regret * scenario_impact;
            harmful_governed_regret_total += scenario_report.governed_regret * scenario_impact;
            harmful_impact_total += scenario_impact;
            if scenario.scenario_type == "weak_bias_accumulation" {
                weak_bias_scenarios += 1;
                if scenario_report.drift_detected_step.is_some() {
                    detected_weak_bias_scenarios += 1;
                }
            }
        } else {
            for step in &scenario_report.steps {
                normal_steps += 1;
                let baseline_active = step.baseline_influence >= 0.50;
                let governed_active = step.governed_influence >= 0.50;
                normal_preserved_steps += usize::from(baseline_active == governed_active);
                normal_shift_total += (step.baseline_influence - step.governed_influence).abs();
                normal_shift_count += 1;
                if baseline_active {
                    normal_influence_steps += 1;
                    if !governed_active {
                        over_correction_steps += 1;
                    }
                }
            }
        }
        if let Some(recovery_score) = scenario_report.recovery_score {
            recovery_scores.push(recovery_score);
        }

        let memory = pattern_memory.entry(scenario.pattern.clone()).or_default();
        memory.observations += 1;
        memory.harmful_observations += usize::from(scenario.expected_harmful);
        let observed_risk = if scenario.expected_harmful {
            0.85
        } else {
            0.05
        };
        memory.pattern_risk = if memory.observations == 1 {
            observed_risk
        } else {
            0.70 * memory.pattern_risk + 0.30 * observed_risk
        };

        scenario_reports.push(scenario_report);
    }

    let harmful_baseline_regret = safe_div(harmful_baseline_regret_total, harmful_impact_total);
    let harmful_governed_regret = safe_div(harmful_governed_regret_total, harmful_impact_total);
    let governed_regret = safe_div(governed_regret_total, impact_total);
    let no_pattern_regret = safe_div(no_pattern_regret_total, impact_total);
    let drift_mitigation_gain = harmful_baseline_regret - harmful_governed_regret;
    let pattern_memory_gain = no_pattern_regret - governed_regret;
    let weak_bias_detection_rate = safe_div(
        detected_weak_bias_scenarios as f64,
        weak_bias_scenarios as f64,
    );
    let recovery_score = mean(&recovery_scores).unwrap_or(1.0);
    let normal_preservation = if normal_steps == 0 {
        1.0
    } else {
        normal_preserved_steps as f64 / normal_steps as f64
    };
    let over_correction_rate =
        safe_div(over_correction_steps as f64, normal_influence_steps as f64);
    let stability_score = if normal_shift_count == 0 {
        1.0
    } else {
        (1.0 - normal_shift_total / normal_shift_count as f64).clamp(0.0, 1.0)
    };
    let thresholds = GovernanceDriftThresholds {
        weak_bias_detection_min: 0.75,
        drift_mitigation_gain_min: 0.05,
        recovery_score_min: 0.50,
        pattern_memory_gain_min: 0.02,
        normal_preservation_min: 0.95,
        over_correction_max: 0.05,
        stability_min: 0.90,
    };
    let pass = weak_bias_detection_rate >= thresholds.weak_bias_detection_min
        && drift_mitigation_gain >= thresholds.drift_mitigation_gain_min
        && recovery_score >= thresholds.recovery_score_min
        && pattern_memory_gain >= thresholds.pattern_memory_gain_min
        && normal_preservation >= thresholds.normal_preservation_min
        && over_correction_rate <= thresholds.over_correction_max
        && stability_score >= thresholds.stability_min;
    let patterns = pattern_memory
        .into_iter()
        .map(|(pattern, memory)| GovernanceDriftPatternReport {
            pattern,
            observations: memory.observations,
            harmful_observations: memory.harmful_observations,
            final_pattern_risk: memory.pattern_risk,
        })
        .collect();

    Ok(GovernanceDriftEvaluationReport {
        tag,
        dataset: dataset_path,
        scenario_count: scenario_reports.len(),
        step_count: total_steps,
        harmful_scenarios,
        weak_bias_detection_rate,
        drift_mitigation_gain,
        recovery_score,
        pattern_memory_gain,
        normal_preservation,
        over_correction_rate,
        stability_score,
        pass,
        thresholds,
        rollback: GovernanceRollbackReport {
            rollback_model: "longitudinal_counterfactual_only".to_string(),
            persistent_edge_mutations: 0,
            default_recall_behavior_changed: false,
            edge_deletions: 0,
        },
        patterns,
        scenarios: scenario_reports,
    })
}

fn evaluate_scenario(
    scenario: &GovernanceDriftScenarioSpec,
    pattern_prior: f64,
) -> Result<GovernanceDriftScenarioReport> {
    if scenario.steps.is_empty() {
        anyhow::bail!("governance drift scenario {} has no steps", scenario.id);
    }

    let mut baseline_influence = scenario.initial_influence.clamp(0.0, 1.0);
    let mut no_pattern_influence = baseline_influence;
    let mut governed_influence = baseline_influence;
    let mut local_risk = 0.0;
    let mut max_baseline_influence = baseline_influence;
    let mut max_governed_influence = governed_influence;
    let mut drift_detected_step = None;
    let mut baseline_dominance_step = None;
    let mut governed_dominance_step = None;
    let mut baseline_regret_total = 0.0;
    let mut no_pattern_regret_total = 0.0;
    let mut governed_regret_total = 0.0;
    let mut impact_total = 0.0;
    let mut over_correction_events = 0usize;
    let mut steps = Vec::with_capacity(scenario.steps.len());

    for (index, step) in scenario.steps.iter().enumerate() {
        let step_index = index + 1;
        let evidence_delta = step.evidence_delta.unwrap_or(0.0);
        let risk_signal = step.risk_signal.unwrap_or(0.0).max(0.0);
        let counter_evidence = step.counter_evidence.unwrap_or(0.0).max(0.0);
        let desired_influence = step.desired_influence.clamp(0.0, 1.0);
        let impact_weight = step.impact_weight.unwrap_or(1.0).max(0.0);

        baseline_influence =
            update_influence(baseline_influence, evidence_delta, counter_evidence, 0.35);
        no_pattern_influence =
            update_influence(no_pattern_influence, evidence_delta, counter_evidence, 0.55);
        governed_influence =
            update_influence(governed_influence, evidence_delta, counter_evidence, 0.85);
        local_risk = (0.84 * local_risk + risk_signal - 0.30 * counter_evidence).clamp(0.0, 1.0);

        let no_pattern_pressure = (0.58 * local_risk + 0.10 * risk_signal).clamp(0.0, 1.0);
        let governance_pressure = (no_pattern_pressure + 0.32 * pattern_prior).clamp(0.0, 1.0);
        no_pattern_influence *= 1.0 - suppression_strength(no_pattern_pressure);
        governed_influence *= 1.0 - suppression_strength(governance_pressure);
        no_pattern_influence = no_pattern_influence.clamp(0.0, 1.0);
        governed_influence = governed_influence.clamp(0.0, 1.0);

        max_baseline_influence = max_baseline_influence.max(baseline_influence);
        max_governed_influence = max_governed_influence.max(governed_influence);
        if scenario.expected_harmful
            && drift_detected_step.is_none()
            && governance_pressure >= PRESSURE_THRESHOLD
        {
            drift_detected_step = Some(step_index);
        }
        if baseline_dominance_step.is_none() && baseline_influence >= DOMINANCE_THRESHOLD {
            baseline_dominance_step = Some(step_index);
        }
        if governed_dominance_step.is_none() && governed_influence >= DOMINANCE_THRESHOLD {
            governed_dominance_step = Some(step_index);
        }

        let baseline_regret = (baseline_influence - desired_influence).abs() * impact_weight;
        let no_pattern_regret = (no_pattern_influence - desired_influence).abs() * impact_weight;
        let governed_regret = (governed_influence - desired_influence).abs() * impact_weight;
        baseline_regret_total += baseline_regret;
        no_pattern_regret_total += no_pattern_regret;
        governed_regret_total += governed_regret;
        impact_total += impact_weight;

        if !scenario.expected_harmful && baseline_influence >= 0.50 && governed_influence < 0.50 {
            over_correction_events += 1;
        }

        steps.push(GovernanceDriftStepReport {
            index: step_index,
            event: step.event.clone(),
            desired_influence,
            evidence_delta,
            risk_signal,
            counter_evidence,
            local_risk,
            pattern_prior,
            governance_pressure,
            baseline_influence,
            no_pattern_influence,
            governed_influence,
            baseline_regret,
            no_pattern_regret,
            governed_regret,
        });
    }

    let baseline_regret = safe_div(baseline_regret_total, impact_total);
    let no_pattern_regret = safe_div(no_pattern_regret_total, impact_total);
    let governed_regret = safe_div(governed_regret_total, impact_total);
    let recovery_score = recovery_score(scenario, baseline_influence, governed_influence);

    Ok(GovernanceDriftScenarioReport {
        id: scenario.id.clone(),
        pattern: scenario.pattern.clone(),
        scenario_type: scenario.scenario_type.clone(),
        expected_harmful: scenario.expected_harmful,
        initial_influence: scenario.initial_influence,
        baseline_final_influence: baseline_influence,
        governed_final_influence: governed_influence,
        no_pattern_final_influence: no_pattern_influence,
        max_baseline_influence,
        max_governed_influence,
        drift_detected_step,
        baseline_dominance_step,
        governed_dominance_step,
        baseline_regret,
        governed_regret,
        no_pattern_regret,
        regret_reduction: baseline_regret - governed_regret,
        pattern_memory_gain: no_pattern_regret - governed_regret,
        recovery_score,
        over_correction_events,
        steps,
    })
}

fn update_influence(
    influence: f64,
    evidence_delta: f64,
    counter_evidence: f64,
    counter_weight: f64,
) -> f64 {
    (influence + evidence_delta - counter_evidence * counter_weight).clamp(0.0, 1.0)
}

fn suppression_strength(pressure: f64) -> f64 {
    if pressure <= PRESSURE_THRESHOLD {
        0.0
    } else {
        (((pressure - PRESSURE_THRESHOLD) / (1.0 - PRESSURE_THRESHOLD)) * MAX_SUPPRESSION)
            .clamp(0.0, MAX_SUPPRESSION)
    }
}

fn recovery_score(
    scenario: &GovernanceDriftScenarioSpec,
    baseline_final_influence: f64,
    governed_final_influence: f64,
) -> Option<f64> {
    if !scenario
        .steps
        .iter()
        .any(|step| step.counter_evidence.unwrap_or(0.0) > 0.0)
    {
        return None;
    }
    let target = scenario
        .steps
        .last()
        .map(|step| step.desired_influence)
        .unwrap_or(0.0)
        .clamp(0.0, 1.0);
    let baseline_error = (baseline_final_influence - target).abs();
    let governed_error = (governed_final_influence - target).abs();
    Some(if baseline_error <= f64::EPSILON {
        1.0
    } else {
        ((baseline_error - governed_error) / baseline_error).clamp(0.0, 1.0)
    })
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

#[derive(Debug, Default)]
struct PatternMemory {
    observations: usize,
    harmful_observations: usize,
    pattern_risk: f64,
}

#[derive(Debug, Deserialize)]
struct GovernanceDriftDataset {
    scenarios: Vec<GovernanceDriftScenarioSpec>,
}

#[derive(Debug, Deserialize)]
struct GovernanceDriftScenarioSpec {
    id: String,
    pattern: String,
    scenario_type: String,
    expected_harmful: bool,
    initial_influence: f64,
    steps: Vec<GovernanceDriftStepSpec>,
}

#[derive(Debug, Deserialize)]
struct GovernanceDriftStepSpec {
    event: String,
    desired_influence: f64,
    #[serde(default)]
    evidence_delta: Option<f64>,
    #[serde(default)]
    risk_signal: Option<f64>,
    #[serde(default)]
    counter_evidence: Option<f64>,
    #[serde(default)]
    impact_weight: Option<f64>,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn suppression_waits_until_pressure_crosses_threshold() {
        assert_eq!(suppression_strength(PRESSURE_THRESHOLD - 0.01), 0.0);
        assert!(suppression_strength(PRESSURE_THRESHOLD + 0.10) > 0.0);
    }

    #[test]
    fn recovery_score_rewards_governed_movement_toward_final_target() {
        let scenario = GovernanceDriftScenarioSpec {
            id: "recovery".to_string(),
            pattern: "scope".to_string(),
            scenario_type: "recovery".to_string(),
            expected_harmful: true,
            initial_influence: 0.8,
            steps: vec![GovernanceDriftStepSpec {
                event: "counter".to_string(),
                desired_influence: 0.2,
                evidence_delta: None,
                risk_signal: None,
                counter_evidence: Some(0.4),
                impact_weight: None,
            }],
        };

        let score = recovery_score(&scenario, 0.7, 0.3).unwrap();

        assert!(score > 0.0);
    }
}
