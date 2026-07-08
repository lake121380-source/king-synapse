use crate::types::{
    GovernanceRollbackReport, GovernanceSoftDominanceAdjustmentReport,
    GovernanceSoftDominanceEvaluationReport, GovernanceSoftDominanceInfluenceReport,
    GovernanceSoftDominanceScenarioReport, GovernanceSoftDominanceStepReport,
    GovernanceSoftDominanceThresholds,
};
use anyhow::{Context, Result};
use serde::Deserialize;
use std::collections::{BTreeMap, BTreeSet};
use std::path::Path;

const RISK_THRESHOLD: f64 = 0.30;
const MAX_SUPPRESSION: f64 = 0.55;
const BASELINE_INERTIA_WEIGHT: f64 = 0.22;
const BASELINE_CONTEXT_WEIGHT: f64 = 0.08;
const GOVERNED_INERTIA_WEIGHT: f64 = 0.12;
const GOVERNED_CONTEXT_WEIGHT: f64 = 0.30;

pub struct GovernanceSoftDominanceEvaluator;

impl GovernanceSoftDominanceEvaluator {
    pub fn evaluate(
        dataset_path: impl AsRef<Path>,
        tag: impl Into<String>,
    ) -> Result<GovernanceSoftDominanceEvaluationReport> {
        let dataset_path = dataset_path.as_ref();
        let raw = std::fs::read_to_string(dataset_path).with_context(|| {
            format!(
                "reading governance soft dominance dataset {}",
                dataset_path.display()
            )
        })?;
        let dataset: GovernanceSoftDominanceDataset =
            toml::from_str(&raw).context("parsing governance soft dominance dataset TOML")?;
        evaluate_dataset(dataset, dataset_path.display().to_string(), tag.into())
    }
}

fn evaluate_dataset(
    dataset: GovernanceSoftDominanceDataset,
    dataset_path: String,
    tag: String,
) -> Result<GovernanceSoftDominanceEvaluationReport> {
    if dataset.scenarios.is_empty() {
        anyhow::bail!("governance soft dominance dataset has no scenarios");
    }

    let mut scenarios = Vec::with_capacity(dataset.scenarios.len());
    let mut step_count = 0usize;
    let mut baseline_correct_steps = 0usize;
    let mut governed_correct_steps = 0usize;
    let mut flexible_steps = 0usize;
    let mut flexible_correct_steps = 0usize;
    let mut context_switch_steps = 0usize;
    let mut context_switch_correct_steps = 0usize;
    let mut near_threshold_steps = 0usize;
    let mut near_threshold_correct_steps = 0usize;
    let mut boundary_misses = 0usize;
    let mut normal_preservation_steps = 0usize;
    let mut normal_preserved_steps = 0usize;
    let mut over_corrections = 0usize;
    let mut total_adjustments = 0usize;
    let mut inertia_drag_reductions = Vec::new();
    let mut transition_latency_gains = Vec::new();

    for scenario in dataset.scenarios {
        let report = evaluate_scenario(&scenario)?;
        step_count += report.step_count;
        baseline_correct_steps += report.baseline_correct_steps;
        governed_correct_steps += report.governed_correct_steps;
        flexible_steps += report.flexible_steps;
        flexible_correct_steps += report.flexible_correct_steps;
        context_switch_steps += report.context_switch_steps;
        context_switch_correct_steps += report.context_switch_correct_steps;
        near_threshold_steps += report.near_threshold_steps;
        near_threshold_correct_steps += report.near_threshold_correct_steps;
        boundary_misses += report.boundary_misses;
        normal_preservation_steps += report.normal_preservation_steps;
        normal_preserved_steps += report.normal_preserved_steps;
        over_corrections += report.over_corrections;
        total_adjustments += report.total_adjustments;
        inertia_drag_reductions.push(report.inertia_drag_reduction);
        transition_latency_gains.push(report.transition_latency_gain);
        scenarios.push(report);
    }

    let baseline_dominance_score = safe_div(baseline_correct_steps as f64, step_count as f64);
    let governed_dominance_score = safe_div(governed_correct_steps as f64, step_count as f64);
    let dominance_gain = governed_dominance_score - baseline_dominance_score;
    let dominance_flexibility = safe_div(flexible_correct_steps as f64, flexible_steps as f64);
    let context_switch_accuracy = safe_div(
        context_switch_correct_steps as f64,
        context_switch_steps as f64,
    );
    let inertia_drag_reduction = mean(&inertia_drag_reductions).unwrap_or(0.0);
    let transition_latency_improvement = mean(&transition_latency_gains).unwrap_or(0.0);
    let near_threshold_accuracy = safe_div(
        near_threshold_correct_steps as f64,
        near_threshold_steps as f64,
    );
    let boundary_miss_rate = safe_div(boundary_misses as f64, near_threshold_steps as f64);
    let over_correction_rate = safe_div(over_corrections as f64, total_adjustments as f64);
    let normal_preservation = if normal_preservation_steps == 0 {
        1.0
    } else {
        normal_preserved_steps as f64 / normal_preservation_steps as f64
    };
    let thresholds = GovernanceSoftDominanceThresholds {
        governed_dominance_score_min: 0.82,
        dominance_gain_min: 0.16,
        dominance_flexibility_min: 0.78,
        context_switch_accuracy_min: 0.75,
        inertia_drag_reduction_min: 0.04,
        transition_latency_improvement_min: 0.08,
        near_threshold_accuracy_min: 0.60,
        over_correction_max: 0.08,
        normal_preservation_min: 0.95,
    };
    let pass = governed_dominance_score >= thresholds.governed_dominance_score_min
        && dominance_gain >= thresholds.dominance_gain_min
        && dominance_flexibility >= thresholds.dominance_flexibility_min
        && context_switch_accuracy >= thresholds.context_switch_accuracy_min
        && inertia_drag_reduction >= thresholds.inertia_drag_reduction_min
        && transition_latency_improvement >= thresholds.transition_latency_improvement_min
        && near_threshold_accuracy >= thresholds.near_threshold_accuracy_min
        && over_correction_rate <= thresholds.over_correction_max
        && normal_preservation >= thresholds.normal_preservation_min;

    Ok(GovernanceSoftDominanceEvaluationReport {
        tag,
        dataset: dataset_path,
        scenario_count: scenarios.len(),
        step_count,
        baseline_dominance_score,
        governed_dominance_score,
        dominance_gain,
        dominance_flexibility,
        context_switch_accuracy,
        inertia_drag_reduction,
        transition_latency_improvement,
        near_threshold_accuracy,
        boundary_miss_rate,
        over_correction_rate,
        normal_preservation,
        pass,
        thresholds,
        rollback: GovernanceRollbackReport {
            rollback_model: "soft_dominance_counterfactual_only".to_string(),
            persistent_edge_mutations: 0,
            default_recall_behavior_changed: false,
            edge_deletions: 0,
        },
        scenarios,
    })
}

fn evaluate_scenario(
    scenario: &GovernanceSoftDominanceScenarioSpec,
) -> Result<GovernanceSoftDominanceScenarioReport> {
    if scenario.influences.is_empty() {
        anyhow::bail!(
            "governance soft dominance scenario {} has no influences",
            scenario.id
        );
    }
    if scenario.steps.is_empty() {
        anyhow::bail!(
            "governance soft dominance scenario {} has no steps",
            scenario.id
        );
    }

    let influence_meta = scenario
        .influences
        .iter()
        .map(|influence| (influence.id.clone(), influence.clone()))
        .collect::<BTreeMap<_, _>>();
    let mut baseline = initial_states(scenario);
    let mut governed = baseline.clone();
    let mut steps = Vec::with_capacity(scenario.steps.len());
    let mut baseline_correct_steps = 0usize;
    let mut governed_correct_steps = 0usize;
    let mut flexible_steps = 0usize;
    let mut flexible_correct_steps = 0usize;
    let mut context_switch_steps = 0usize;
    let mut context_switch_correct_steps = 0usize;
    let mut near_threshold_steps = 0usize;
    let mut near_threshold_correct_steps = 0usize;
    let mut boundary_misses = 0usize;
    let mut normal_preservation_steps = 0usize;
    let mut normal_preserved_steps = 0usize;
    let mut over_corrections = 0usize;
    let mut total_adjustments = 0usize;
    let mut inertia_drag_reduction_total = 0.0;
    let mut inertia_drag_steps = 0usize;

    for (index, step) in scenario.steps.iter().enumerate() {
        let step_index = index + 1;
        apply_step_signals(&mut baseline, step);
        apply_step_signals(&mut governed, step);
        let adjustments = apply_governance(&mut governed, step, &influence_meta);
        total_adjustments += adjustments.len();
        over_corrections += adjustments
            .iter()
            .filter(|adjustment| !adjustment.appropriate)
            .count();

        let baseline_scores = score_map(&baseline, ScoreMode::Baseline);
        let governed_scores = score_map(&governed, ScoreMode::Governed);
        let baseline_dominant = dominant(&baseline_scores);
        let governed_dominant = dominant(&governed_scores);
        let baseline_correct = baseline_dominant == step.expected_dominant;
        let governed_correct = governed_dominant == step.expected_dominant;
        baseline_correct_steps += usize::from(baseline_correct);
        governed_correct_steps += usize::from(governed_correct);

        let expected_changed = steps
            .last()
            .map(|previous: &GovernanceSoftDominanceStepReport| {
                previous.expected_dominant != step.expected_dominant
            })
            .unwrap_or(false);
        if expected_changed {
            context_switch_steps += 1;
            context_switch_correct_steps += usize::from(governed_correct);
        }
        if expected_changed || !baseline_correct {
            flexible_steps += 1;
            flexible_correct_steps += usize::from(governed_correct);
        }

        let near_threshold = step
            .signals
            .iter()
            .any(|signal| is_near_threshold(signal.risk_signal.unwrap_or(0.0)));
        if near_threshold {
            near_threshold_steps += 1;
            near_threshold_correct_steps += usize::from(governed_correct);
            boundary_misses += usize::from(!governed_correct);
        }

        let expected_non_harmful = influence_meta
            .get(&step.expected_dominant)
            .map(|influence| !influence.harmful)
            .unwrap_or(true);
        if expected_non_harmful && baseline_correct {
            normal_preservation_steps += 1;
            normal_preserved_steps += usize::from(governed_correct);
        }

        let baseline_expected_margin = expected_margin(&baseline_scores, &step.expected_dominant);
        let governed_expected_margin = expected_margin(&governed_scores, &step.expected_dominant);
        let (baseline_inertia_drag, governed_inertia_drag) = inertia_drag(
            &baseline,
            &governed,
            &baseline_scores,
            &governed_scores,
            step,
        );
        if baseline_inertia_drag > 0.0 || governed_inertia_drag > 0.0 {
            inertia_drag_steps += 1;
            inertia_drag_reduction_total += baseline_inertia_drag - governed_inertia_drag;
        }

        let influences = influence_reports(&baseline, &governed, &influence_meta);
        steps.push(GovernanceSoftDominanceStepReport {
            index: step_index,
            event: step.event.clone(),
            expected_dominant: step.expected_dominant.clone(),
            baseline_dominant,
            governed_dominant,
            baseline_correct,
            governed_correct,
            baseline_expected_margin,
            governed_expected_margin,
            baseline_inertia_drag,
            governed_inertia_drag,
            near_threshold,
            context_switch: expected_changed,
            influences,
            adjustments,
        });
    }

    let baseline_dominance_score = safe_div(baseline_correct_steps as f64, steps.len() as f64);
    let governed_dominance_score = safe_div(governed_correct_steps as f64, steps.len() as f64);
    let dominance_flexibility = safe_div(flexible_correct_steps as f64, flexible_steps as f64);
    let context_switch_accuracy = safe_div(
        context_switch_correct_steps as f64,
        context_switch_steps as f64,
    );
    let inertia_drag_reduction =
        safe_div(inertia_drag_reduction_total, inertia_drag_steps as f64).max(0.0);
    let first_baseline_correct_step =
        first_challenged_correct_step(&steps, DominanceTrack::Baseline);
    let first_governed_correct_step =
        first_challenged_correct_step(&steps, DominanceTrack::Governed);
    let transition_latency_gain = latency_gain(
        first_baseline_correct_step,
        first_governed_correct_step,
        steps.len(),
    );
    let near_threshold_accuracy = safe_div(
        near_threshold_correct_steps as f64,
        near_threshold_steps as f64,
    );
    let boundary_miss_rate = safe_div(boundary_misses as f64, near_threshold_steps as f64);
    let over_correction_rate = safe_div(over_corrections as f64, total_adjustments as f64);
    let normal_preservation = if normal_preservation_steps == 0 {
        1.0
    } else {
        normal_preserved_steps as f64 / normal_preservation_steps as f64
    };

    Ok(GovernanceSoftDominanceScenarioReport {
        id: scenario.id.clone(),
        scenario_type: scenario.scenario_type.clone(),
        influence_count: scenario.influences.len(),
        step_count: steps.len(),
        baseline_correct_steps,
        governed_correct_steps,
        baseline_dominance_score,
        governed_dominance_score,
        flexible_steps,
        flexible_correct_steps,
        dominance_flexibility,
        context_switch_steps,
        context_switch_correct_steps,
        context_switch_accuracy,
        inertia_drag_reduction,
        transition_latency_gain,
        near_threshold_steps,
        near_threshold_correct_steps,
        near_threshold_accuracy,
        boundary_misses,
        boundary_miss_rate,
        normal_preservation_steps,
        normal_preserved_steps,
        over_corrections,
        total_adjustments,
        over_correction_rate,
        normal_preservation,
        steps,
    })
}

fn initial_states(
    scenario: &GovernanceSoftDominanceScenarioSpec,
) -> BTreeMap<String, InfluenceState> {
    scenario
        .influences
        .iter()
        .map(|influence| {
            (
                influence.id.clone(),
                InfluenceState {
                    strength: influence.initial_strength.clamp(0.0, 1.0),
                    inertia: influence.initial_inertia.clamp(0.0, 1.0),
                    context_fit: influence.initial_context_fit.clamp(0.0, 1.0),
                },
            )
        })
        .collect()
}

fn apply_step_signals(
    states: &mut BTreeMap<String, InfluenceState>,
    step: &GovernanceSoftDominanceStepSpec,
) {
    for signal in &step.signals {
        let state = states
            .entry(signal.influence.clone())
            .or_insert_with(InfluenceState::default);
        state.strength = (state.strength + signal.evidence_delta.unwrap_or(0.0)).clamp(0.0, 1.0);
        state.context_fit =
            (state.context_fit + signal.context_fit_delta.unwrap_or(0.0)).clamp(0.0, 1.0);
        state.inertia = (state.inertia + signal.inertia_delta.unwrap_or(0.0)).clamp(0.0, 1.0);
    }
}

fn apply_governance(
    states: &mut BTreeMap<String, InfluenceState>,
    step: &GovernanceSoftDominanceStepSpec,
    influence_meta: &BTreeMap<String, GovernanceSoftDominanceInfluenceSpec>,
) -> Vec<GovernanceSoftDominanceAdjustmentReport> {
    let mut adjustments = Vec::new();
    for signal in &step.signals {
        let risk_signal = signal.risk_signal.unwrap_or(0.0).clamp(0.0, 1.0);
        let suppression_strength = risk_suppression(risk_signal);
        if suppression_strength <= 0.0 {
            continue;
        }
        let Some(state) = states.get_mut(&signal.influence) else {
            continue;
        };
        let strength_before = state.strength;
        let inertia_before = state.inertia;
        state.strength = (state.strength * (1.0 - 0.42 * suppression_strength)).clamp(0.0, 1.0);
        state.inertia = (state.inertia * (1.0 - 0.65 * suppression_strength)).clamp(0.0, 1.0);

        let harmful = influence_meta
            .get(&signal.influence)
            .map(|influence| influence.harmful)
            .unwrap_or(false);
        let appropriate = harmful && signal.influence != step.expected_dominant;
        adjustments.push(GovernanceSoftDominanceAdjustmentReport {
            influence: signal.influence.clone(),
            harmful,
            risk_signal,
            suppression_strength,
            strength_delta: state.strength - strength_before,
            inertia_delta: state.inertia - inertia_before,
            appropriate,
        });
    }
    adjustments
}

fn risk_suppression(risk_signal: f64) -> f64 {
    if risk_signal <= RISK_THRESHOLD {
        0.0
    } else {
        (((risk_signal - RISK_THRESHOLD) / (1.0 - RISK_THRESHOLD)) * MAX_SUPPRESSION)
            .clamp(0.0, MAX_SUPPRESSION)
    }
}

fn score_map(states: &BTreeMap<String, InfluenceState>, mode: ScoreMode) -> BTreeMap<String, f64> {
    states
        .iter()
        .map(|(id, state)| (id.clone(), effective_score(state, mode)))
        .collect()
}

fn effective_score(state: &InfluenceState, mode: ScoreMode) -> f64 {
    match mode {
        ScoreMode::Baseline => {
            state.strength
                + BASELINE_INERTIA_WEIGHT * state.inertia
                + BASELINE_CONTEXT_WEIGHT * state.context_fit
        }
        ScoreMode::Governed => {
            state.strength
                + GOVERNED_INERTIA_WEIGHT * state.inertia
                + GOVERNED_CONTEXT_WEIGHT * state.context_fit
        }
    }
}

fn dominant(scores: &BTreeMap<String, f64>) -> String {
    scores
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

fn expected_margin(scores: &BTreeMap<String, f64>, expected: &str) -> f64 {
    let expected_score = scores.get(expected).copied().unwrap_or(0.0);
    let strongest_other = scores
        .iter()
        .filter(|(id, _)| id.as_str() != expected)
        .map(|(_, score)| *score)
        .fold(0.0, f64::max);
    expected_score - strongest_other
}

fn inertia_drag(
    baseline: &BTreeMap<String, InfluenceState>,
    governed: &BTreeMap<String, InfluenceState>,
    baseline_scores: &BTreeMap<String, f64>,
    governed_scores: &BTreeMap<String, f64>,
    step: &GovernanceSoftDominanceStepSpec,
) -> (f64, f64) {
    let Some(high_inertia_id) = baseline
        .iter()
        .max_by(|left, right| {
            left.1
                .inertia
                .partial_cmp(&right.1.inertia)
                .unwrap_or(std::cmp::Ordering::Equal)
        })
        .map(|(id, _)| id.as_str())
    else {
        return (0.0, 0.0);
    };
    if high_inertia_id == step.expected_dominant {
        return (0.0, 0.0);
    }

    let baseline_drag = drag_margin(baseline_scores, high_inertia_id, &step.expected_dominant);
    let governed_drag = drag_margin(governed_scores, high_inertia_id, &step.expected_dominant);
    let governed_drag = if governed.contains_key(high_inertia_id) {
        governed_drag
    } else {
        0.0
    };
    (baseline_drag, governed_drag)
}

fn drag_margin(scores: &BTreeMap<String, f64>, inertia_id: &str, expected_id: &str) -> f64 {
    let inertia_score = scores.get(inertia_id).copied().unwrap_or(0.0);
    let expected_score = scores.get(expected_id).copied().unwrap_or(0.0);
    (inertia_score - expected_score).max(0.0)
}

fn influence_reports(
    baseline: &BTreeMap<String, InfluenceState>,
    governed: &BTreeMap<String, InfluenceState>,
    influence_meta: &BTreeMap<String, GovernanceSoftDominanceInfluenceSpec>,
) -> Vec<GovernanceSoftDominanceInfluenceReport> {
    let mut ids = BTreeSet::new();
    ids.extend(baseline.keys().cloned());
    ids.extend(governed.keys().cloned());
    ids.into_iter()
        .map(|id| {
            let meta = influence_meta.get(&id);
            let baseline_state = baseline.get(&id).copied().unwrap_or_default();
            let governed_state = governed.get(&id).copied().unwrap_or_default();
            GovernanceSoftDominanceInfluenceReport {
                id: id.clone(),
                label: meta
                    .map(|influence| influence.label.clone())
                    .unwrap_or_else(|| id.clone()),
                harmful: meta.map(|influence| influence.harmful).unwrap_or(false),
                baseline_strength: baseline_state.strength,
                governed_strength: governed_state.strength,
                baseline_inertia: baseline_state.inertia,
                governed_inertia: governed_state.inertia,
                baseline_context_fit: baseline_state.context_fit,
                governed_context_fit: governed_state.context_fit,
                baseline_effective_score: effective_score(&baseline_state, ScoreMode::Baseline),
                governed_effective_score: effective_score(&governed_state, ScoreMode::Governed),
            }
        })
        .collect()
}

fn first_challenged_correct_step(
    steps: &[GovernanceSoftDominanceStepReport],
    track: DominanceTrack,
) -> Option<usize> {
    let first_challenge = steps
        .iter()
        .position(|step| step.context_switch || !step.baseline_correct)?;
    steps
        .iter()
        .skip(first_challenge)
        .find(|step| match track {
            DominanceTrack::Baseline => step.baseline_correct,
            DominanceTrack::Governed => step.governed_correct,
        })
        .map(|step| step.index)
}

fn latency_gain(
    baseline_step: Option<usize>,
    governed_step: Option<usize>,
    step_count: usize,
) -> f64 {
    let fallback = step_count + 1;
    let baseline_step = baseline_step.unwrap_or(fallback);
    let governed_step = governed_step.unwrap_or(fallback);
    safe_div(
        (baseline_step as isize - governed_step as isize).max(0) as f64,
        fallback as f64,
    )
}

fn is_near_threshold(risk_signal: f64) -> bool {
    (RISK_THRESHOLD - 0.05..=RISK_THRESHOLD + 0.05).contains(&risk_signal)
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

#[derive(Debug, Clone, Copy)]
enum ScoreMode {
    Baseline,
    Governed,
}

#[derive(Debug, Clone, Copy)]
enum DominanceTrack {
    Baseline,
    Governed,
}

#[derive(Debug, Clone, Copy, Default)]
struct InfluenceState {
    strength: f64,
    inertia: f64,
    context_fit: f64,
}

#[derive(Debug, Deserialize)]
struct GovernanceSoftDominanceDataset {
    scenarios: Vec<GovernanceSoftDominanceScenarioSpec>,
}

#[derive(Debug, Deserialize)]
struct GovernanceSoftDominanceScenarioSpec {
    id: String,
    scenario_type: String,
    influences: Vec<GovernanceSoftDominanceInfluenceSpec>,
    steps: Vec<GovernanceSoftDominanceStepSpec>,
}

#[derive(Debug, Clone, Deserialize)]
struct GovernanceSoftDominanceInfluenceSpec {
    id: String,
    label: String,
    initial_strength: f64,
    initial_inertia: f64,
    initial_context_fit: f64,
    #[serde(default)]
    harmful: bool,
}

#[derive(Debug, Deserialize)]
struct GovernanceSoftDominanceStepSpec {
    event: String,
    expected_dominant: String,
    signals: Vec<GovernanceSoftDominanceSignalSpec>,
}

#[derive(Debug, Deserialize)]
struct GovernanceSoftDominanceSignalSpec {
    influence: String,
    #[serde(default)]
    evidence_delta: Option<f64>,
    #[serde(default)]
    context_fit_delta: Option<f64>,
    #[serde(default)]
    inertia_delta: Option<f64>,
    #[serde(default)]
    risk_signal: Option<f64>,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn risk_suppression_waits_until_threshold() {
        assert_eq!(risk_suppression(RISK_THRESHOLD - 0.01), 0.0);
        assert!(risk_suppression(RISK_THRESHOLD + 0.05) > 0.0);
    }

    #[test]
    fn governed_score_rewards_context_more_than_baseline() {
        let state = InfluenceState {
            strength: 0.45,
            inertia: 0.20,
            context_fit: 0.80,
        };

        assert!(
            effective_score(&state, ScoreMode::Governed)
                > effective_score(&state, ScoreMode::Baseline)
        );
    }

    #[test]
    fn inertia_drag_counts_only_when_high_inertia_competes_with_expected() {
        let baseline = BTreeMap::from([
            (
                "old".to_string(),
                InfluenceState {
                    strength: 0.50,
                    inertia: 0.90,
                    context_fit: 0.30,
                },
            ),
            (
                "new".to_string(),
                InfluenceState {
                    strength: 0.45,
                    inertia: 0.10,
                    context_fit: 0.80,
                },
            ),
        ]);
        let governed = baseline.clone();
        let baseline_scores = score_map(&baseline, ScoreMode::Baseline);
        let governed_scores = score_map(&governed, ScoreMode::Governed);
        let step = GovernanceSoftDominanceStepSpec {
            event: "new context arrives".to_string(),
            expected_dominant: "new".to_string(),
            signals: Vec::new(),
        };

        let (baseline_drag, governed_drag) = inertia_drag(
            &baseline,
            &governed,
            &baseline_scores,
            &governed_scores,
            &step,
        );

        assert!(baseline_drag > governed_drag);
    }
}
