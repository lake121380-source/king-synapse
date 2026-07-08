use crate::types::{
    GovernanceCompetitionEvaluationReport, GovernanceCompetitionInfluenceReport,
    GovernanceCompetitionScenarioReport, GovernanceCompetitionStepReport,
    GovernanceCompetitionSuppressionReport, GovernanceCompetitionThresholds,
    GovernanceRollbackReport,
};
use anyhow::{Context, Result};
use serde::Deserialize;
use std::collections::{BTreeMap, BTreeSet};
use std::path::Path;

const RISK_THRESHOLD: f64 = 0.30;
const MAX_SUPPRESSION: f64 = 0.60;

pub struct GovernanceCompetitionEvaluator;

impl GovernanceCompetitionEvaluator {
    pub fn evaluate(
        dataset_path: impl AsRef<Path>,
        tag: impl Into<String>,
    ) -> Result<GovernanceCompetitionEvaluationReport> {
        let dataset_path = dataset_path.as_ref();
        let raw = std::fs::read_to_string(dataset_path).with_context(|| {
            format!(
                "reading governance competition dataset {}",
                dataset_path.display()
            )
        })?;
        let dataset: GovernanceCompetitionDataset =
            toml::from_str(&raw).context("parsing governance competition dataset TOML")?;
        evaluate_dataset(dataset, dataset_path.display().to_string(), tag.into())
    }
}

fn evaluate_dataset(
    dataset: GovernanceCompetitionDataset,
    dataset_path: String,
    tag: String,
) -> Result<GovernanceCompetitionEvaluationReport> {
    if dataset.scenarios.is_empty() {
        anyhow::bail!("governance competition dataset has no scenarios");
    }

    let mut scenarios = Vec::with_capacity(dataset.scenarios.len());
    let mut step_count = 0usize;
    let mut baseline_correct_steps = 0usize;
    let mut governed_correct_steps = 0usize;
    let mut transition_correct = 0usize;
    let mut transition_count = 0usize;
    let mut evidence_response_gain_total = 0.0;
    let mut stability_scores = Vec::new();
    let mut appropriate_suppressions = 0usize;
    let mut total_suppressions = 0usize;
    let mut over_suppressions = 0usize;
    let mut normal_preserved_steps = 0usize;
    let mut normal_preservation_steps = 0usize;

    for scenario in dataset.scenarios {
        let report = evaluate_scenario(&scenario)?;
        step_count += report.step_count;
        baseline_correct_steps += report.baseline_correct_steps;
        governed_correct_steps += report.governed_correct_steps;
        evidence_response_gain_total += report.evidence_response_gain * report.step_count as f64;
        stability_scores.push(report.influence_balance_stability);
        for (index, step) in report.steps.iter().enumerate() {
            if index > 0 && step.expected_dominant != report.steps[index - 1].expected_dominant {
                transition_count += 1;
                transition_correct += usize::from(step.governed_correct);
            }
            for suppression in &step.suppressions {
                total_suppressions += 1;
                appropriate_suppressions += usize::from(suppression.appropriate);
                over_suppressions += usize::from(!suppression.appropriate);
            }
            if expected_influence_is_non_harmful(step) && step.baseline_correct {
                normal_preservation_steps += 1;
                normal_preserved_steps += usize::from(step.governed_correct);
            }
        }
        scenarios.push(report);
    }

    let baseline_competition_score = safe_div(baseline_correct_steps as f64, step_count as f64);
    let governed_competition_score = safe_div(governed_correct_steps as f64, step_count as f64);
    let competition_gain = governed_competition_score - baseline_competition_score;
    let dominant_transition_accuracy = if transition_count == 0 {
        1.0
    } else {
        transition_correct as f64 / transition_count as f64
    };
    let evidence_response_gain = safe_div(evidence_response_gain_total, step_count as f64);
    let influence_balance_stability = mean(&stability_scores).unwrap_or(1.0);
    let suppression_precision = if total_suppressions == 0 {
        1.0
    } else {
        appropriate_suppressions as f64 / total_suppressions as f64
    };
    let over_suppression_rate = safe_div(over_suppressions as f64, total_suppressions as f64);
    let normal_preservation = if normal_preservation_steps == 0 {
        1.0
    } else {
        normal_preserved_steps as f64 / normal_preservation_steps as f64
    };
    let thresholds = GovernanceCompetitionThresholds {
        governed_competition_score_min: 0.80,
        competition_gain_min: 0.20,
        dominant_transition_accuracy_min: 0.75,
        evidence_response_gain_min: 0.08,
        influence_balance_stability_min: 0.80,
        suppression_precision_min: 0.85,
        over_suppression_max: 0.10,
        normal_preservation_min: 0.95,
    };
    let pass = governed_competition_score >= thresholds.governed_competition_score_min
        && competition_gain >= thresholds.competition_gain_min
        && dominant_transition_accuracy >= thresholds.dominant_transition_accuracy_min
        && evidence_response_gain >= thresholds.evidence_response_gain_min
        && influence_balance_stability >= thresholds.influence_balance_stability_min
        && suppression_precision >= thresholds.suppression_precision_min
        && over_suppression_rate <= thresholds.over_suppression_max
        && normal_preservation >= thresholds.normal_preservation_min;

    Ok(GovernanceCompetitionEvaluationReport {
        tag,
        dataset: dataset_path,
        scenario_count: scenarios.len(),
        step_count,
        baseline_competition_score,
        governed_competition_score,
        competition_gain,
        dominant_transition_accuracy,
        evidence_response_gain,
        influence_balance_stability,
        suppression_precision,
        over_suppression_rate,
        normal_preservation,
        pass,
        thresholds,
        rollback: GovernanceRollbackReport {
            rollback_model: "competing_influence_counterfactual_only".to_string(),
            persistent_edge_mutations: 0,
            default_recall_behavior_changed: false,
            edge_deletions: 0,
        },
        scenarios,
    })
}

fn evaluate_scenario(
    scenario: &GovernanceCompetitionScenarioSpec,
) -> Result<GovernanceCompetitionScenarioReport> {
    if scenario.influences.is_empty() {
        anyhow::bail!(
            "governance competition scenario {} has no influences",
            scenario.id
        );
    }
    if scenario.steps.is_empty() {
        anyhow::bail!(
            "governance competition scenario {} has no steps",
            scenario.id
        );
    }

    let influence_meta = scenario
        .influences
        .iter()
        .map(|influence| (influence.id.clone(), influence.clone()))
        .collect::<BTreeMap<_, _>>();
    let mut baseline = scenario
        .influences
        .iter()
        .map(|influence| {
            (
                influence.id.clone(),
                influence.initial_strength.clamp(0.0, 1.0),
            )
        })
        .collect::<BTreeMap<_, _>>();
    let mut governed = baseline.clone();
    let mut step_reports: Vec<GovernanceCompetitionStepReport> =
        Vec::with_capacity(scenario.steps.len());
    let mut baseline_correct_steps = 0usize;
    let mut governed_correct_steps = 0usize;
    let mut evidence_response_gain_total = 0.0;
    let mut stability_violations = 0usize;
    let mut transition_slots = 0usize;
    let mut appropriate_suppressions = 0usize;
    let mut total_suppressions = 0usize;
    let mut over_suppressions = 0usize;
    let mut normal_preserved_steps = 0usize;
    let mut normal_preservation_steps = 0usize;

    for (index, step) in scenario.steps.iter().enumerate() {
        let step_index = index + 1;
        apply_evidence(&mut baseline, step);
        apply_evidence(&mut governed, step);
        let suppressions = apply_governance(&mut governed, step, &influence_meta);
        for suppression in &suppressions {
            total_suppressions += 1;
            appropriate_suppressions += usize::from(suppression.appropriate);
            over_suppressions += usize::from(!suppression.appropriate);
        }

        let baseline_dominant = dominant(&baseline);
        let governed_dominant = dominant(&governed);
        let baseline_correct = baseline_dominant == step.expected_dominant;
        let governed_correct = governed_dominant == step.expected_dominant;
        baseline_correct_steps += usize::from(baseline_correct);
        governed_correct_steps += usize::from(governed_correct);
        let baseline_expected_margin = expected_margin(&baseline, &step.expected_dominant);
        let governed_expected_margin = expected_margin(&governed, &step.expected_dominant);
        let evidence_response_gain = governed_expected_margin - baseline_expected_margin;
        evidence_response_gain_total += evidence_response_gain;

        let influences = influence_reports(&baseline, &governed, &influence_meta);
        let report = GovernanceCompetitionStepReport {
            index: step_index,
            event: step.event.clone(),
            expected_dominant: step.expected_dominant.clone(),
            baseline_dominant,
            governed_dominant,
            baseline_correct,
            governed_correct,
            baseline_expected_margin,
            governed_expected_margin,
            evidence_response_gain,
            influences,
            suppressions,
        };
        if index > 0 {
            transition_slots += 1;
            let previous = &step_reports[index - 1];
            let expected_changed = previous.expected_dominant != report.expected_dominant;
            let governed_changed = previous.governed_dominant != report.governed_dominant;
            if (!expected_changed && governed_changed)
                || (expected_changed && !report.governed_correct)
            {
                stability_violations += 1;
            }
        }
        if expected_influence_is_non_harmful(&report) && report.baseline_correct {
            normal_preservation_steps += 1;
            normal_preserved_steps += usize::from(report.governed_correct);
        }
        step_reports.push(report);
    }

    let baseline_competition_score =
        safe_div(baseline_correct_steps as f64, step_reports.len() as f64);
    let governed_competition_score =
        safe_div(governed_correct_steps as f64, step_reports.len() as f64);
    let dominant_transition_accuracy = transition_accuracy(&step_reports);
    let evidence_response_gain = safe_div(evidence_response_gain_total, step_reports.len() as f64);
    let influence_balance_stability = if transition_slots == 0 {
        1.0
    } else {
        (1.0 - stability_violations as f64 / transition_slots as f64).clamp(0.0, 1.0)
    };
    let suppression_precision = if total_suppressions == 0 {
        1.0
    } else {
        appropriate_suppressions as f64 / total_suppressions as f64
    };
    let over_suppression_rate = safe_div(over_suppressions as f64, total_suppressions as f64);
    let normal_preservation = if normal_preservation_steps == 0 {
        1.0
    } else {
        normal_preserved_steps as f64 / normal_preservation_steps as f64
    };

    Ok(GovernanceCompetitionScenarioReport {
        id: scenario.id.clone(),
        scenario_type: scenario.scenario_type.clone(),
        influence_count: scenario.influences.len(),
        step_count: step_reports.len(),
        baseline_correct_steps,
        governed_correct_steps,
        baseline_competition_score,
        governed_competition_score,
        dominant_transition_accuracy,
        evidence_response_gain,
        influence_balance_stability,
        suppression_precision,
        over_suppression_rate,
        normal_preservation,
        steps: step_reports,
    })
}

fn apply_evidence(strengths: &mut BTreeMap<String, f64>, step: &GovernanceCompetitionStepSpec) {
    for signal in &step.signals {
        let entry = strengths.entry(signal.influence.clone()).or_insert(0.0);
        *entry = (*entry + signal.evidence_delta.unwrap_or(0.0)).clamp(0.0, 1.0);
    }
}

fn apply_governance(
    strengths: &mut BTreeMap<String, f64>,
    step: &GovernanceCompetitionStepSpec,
    influence_meta: &BTreeMap<String, GovernanceCompetitionInfluenceSpec>,
) -> Vec<GovernanceCompetitionSuppressionReport> {
    let mut suppressions = Vec::new();
    for signal in &step.signals {
        let risk_signal = signal.risk_signal.unwrap_or(0.0).clamp(0.0, 1.0);
        let suppression_strength = suppression_strength(risk_signal);
        if suppression_strength <= 0.0 {
            continue;
        }
        let Some(strength) = strengths.get_mut(&signal.influence) else {
            continue;
        };
        *strength = (*strength * (1.0 - suppression_strength)).clamp(0.0, 1.0);
        let harmful = influence_meta
            .get(&signal.influence)
            .map(|influence| influence.harmful)
            .unwrap_or(false);
        let appropriate = harmful && signal.influence != step.expected_dominant;
        suppressions.push(GovernanceCompetitionSuppressionReport {
            influence: signal.influence.clone(),
            harmful,
            risk_signal,
            suppression_strength,
            appropriate,
        });
    }
    suppressions
}

fn suppression_strength(risk_signal: f64) -> f64 {
    if risk_signal <= RISK_THRESHOLD {
        0.0
    } else {
        (((risk_signal - RISK_THRESHOLD) / (1.0 - RISK_THRESHOLD)) * MAX_SUPPRESSION)
            .clamp(0.0, MAX_SUPPRESSION)
    }
}

fn dominant(strengths: &BTreeMap<String, f64>) -> String {
    strengths
        .iter()
        .max_by(|left, right| {
            left.1
                .partial_cmp(right.1)
                .unwrap_or(std::cmp::Ordering::Equal)
                .then_with(|| right.0.cmp(left.0))
        })
        .map(|(id, _)| id.clone())
        .unwrap_or_default()
}

fn expected_margin(strengths: &BTreeMap<String, f64>, expected: &str) -> f64 {
    let expected_strength = strengths.get(expected).copied().unwrap_or(0.0);
    let strongest_other = strengths
        .iter()
        .filter(|(id, _)| id.as_str() != expected)
        .map(|(_, strength)| *strength)
        .fold(0.0, f64::max);
    expected_strength - strongest_other
}

fn influence_reports(
    baseline: &BTreeMap<String, f64>,
    governed: &BTreeMap<String, f64>,
    influence_meta: &BTreeMap<String, GovernanceCompetitionInfluenceSpec>,
) -> Vec<GovernanceCompetitionInfluenceReport> {
    let mut ids = BTreeSet::new();
    ids.extend(baseline.keys().cloned());
    ids.extend(governed.keys().cloned());
    ids.into_iter()
        .map(|id| {
            let meta = influence_meta.get(&id);
            GovernanceCompetitionInfluenceReport {
                id: id.clone(),
                label: meta
                    .map(|influence| influence.label.clone())
                    .unwrap_or_else(|| id.clone()),
                harmful: meta.map(|influence| influence.harmful).unwrap_or(false),
                baseline_strength: baseline.get(&id).copied().unwrap_or(0.0),
                governed_strength: governed.get(&id).copied().unwrap_or(0.0),
            }
        })
        .collect()
}

fn transition_accuracy(steps: &[GovernanceCompetitionStepReport]) -> f64 {
    if steps.len() < 2 {
        return 1.0;
    }
    let mut transitions = 0usize;
    let mut correct = 0usize;
    for pair in steps.windows(2) {
        if pair[0].expected_dominant != pair[1].expected_dominant {
            transitions += 1;
            correct += usize::from(pair[1].governed_correct);
        }
    }
    if transitions == 0 {
        1.0
    } else {
        correct as f64 / transitions as f64
    }
}

fn expected_influence_is_non_harmful(step: &GovernanceCompetitionStepReport) -> bool {
    step.influences
        .iter()
        .find(|influence| influence.id == step.expected_dominant)
        .map(|influence| !influence.harmful)
        .unwrap_or(true)
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
struct GovernanceCompetitionDataset {
    scenarios: Vec<GovernanceCompetitionScenarioSpec>,
}

#[derive(Debug, Deserialize)]
struct GovernanceCompetitionScenarioSpec {
    id: String,
    scenario_type: String,
    influences: Vec<GovernanceCompetitionInfluenceSpec>,
    steps: Vec<GovernanceCompetitionStepSpec>,
}

#[derive(Debug, Clone, Deserialize)]
struct GovernanceCompetitionInfluenceSpec {
    id: String,
    label: String,
    initial_strength: f64,
    #[serde(default)]
    harmful: bool,
}

#[derive(Debug, Deserialize)]
struct GovernanceCompetitionStepSpec {
    event: String,
    expected_dominant: String,
    signals: Vec<GovernanceCompetitionSignalSpec>,
}

#[derive(Debug, Deserialize)]
struct GovernanceCompetitionSignalSpec {
    influence: String,
    #[serde(default)]
    evidence_delta: Option<f64>,
    #[serde(default)]
    risk_signal: Option<f64>,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn suppression_waits_until_risk_crosses_threshold() {
        assert_eq!(suppression_strength(RISK_THRESHOLD - 0.01), 0.0);
        assert!(suppression_strength(RISK_THRESHOLD + 0.10) > 0.0);
    }

    #[test]
    fn expected_margin_compares_expected_against_strongest_competitor() {
        let strengths = BTreeMap::from([
            ("adaptive".to_string(), 0.7),
            ("misbelief".to_string(), 0.4),
            ("context".to_string(), 0.2),
        ]);

        assert!((expected_margin(&strengths, "adaptive") - 0.3).abs() < 1e-9);
    }
}
