use crate::types::{
    GovernanceRegulationBoundaryCaseReport, GovernanceRegulationBoundaryEvaluationReport,
    GovernanceRegulationBoundaryThresholds, GovernanceRollbackReport, RegulationAction,
};
use anyhow::{Context, Result};
use serde::Deserialize;
use std::path::Path;

const INTERVENTION_MARGIN: f64 = 0.22;
const INTERVENTION_PRESSURE_MIN: f64 = 0.62;
const RESTRAINT_MARGIN: f64 = -0.10;
const RESTRAINT_PRESSURE_MIN: f64 = 0.58;
const MAX_REGULATION: f64 = 0.55;

pub struct GovernanceRegulationBoundaryEvaluator;

impl GovernanceRegulationBoundaryEvaluator {
    pub fn evaluate(
        dataset_path: impl AsRef<Path>,
        tag: impl Into<String>,
    ) -> Result<GovernanceRegulationBoundaryEvaluationReport> {
        let dataset_path = dataset_path.as_ref();
        let raw = std::fs::read_to_string(dataset_path).with_context(|| {
            format!(
                "reading governance regulation boundary dataset {}",
                dataset_path.display()
            )
        })?;
        let dataset: GovernanceRegulationBoundaryDataset =
            toml::from_str(&raw).context("parsing governance regulation boundary dataset TOML")?;
        evaluate_dataset(dataset, dataset_path.display().to_string(), tag.into())
    }
}

fn evaluate_dataset(
    dataset: GovernanceRegulationBoundaryDataset,
    dataset_path: String,
    tag: String,
) -> Result<GovernanceRegulationBoundaryEvaluationReport> {
    if dataset.cases.is_empty() {
        anyhow::bail!("governance regulation boundary dataset has no cases");
    }

    let mut case_reports = Vec::with_capacity(dataset.cases.len());
    let mut expected_interventions = 0usize;
    let mut predicted_interventions = 0usize;
    let mut correct_interventions = 0usize;
    let mut expected_non_interventions = 0usize;
    let mut correct_non_interventions = 0usize;
    let mut unnecessary_interventions = 0usize;
    let mut exploration_cases = 0usize;
    let mut preserved_exploration_cases = 0usize;
    let mut ambiguous_cases = 0usize;
    let mut ambiguous_restrained_cases = 0usize;
    let mut exact_correct = 0usize;
    let mut boundary_misses = 0usize;
    let mut outcome_gain_total = 0.0;

    for case in dataset.cases {
        let report = evaluate_case(&case);
        let expected_intervene = report.expected_action == RegulationAction::Intervene;
        let predicted_intervene = report.predicted_action == RegulationAction::Intervene;
        expected_interventions += usize::from(expected_intervene);
        predicted_interventions += usize::from(predicted_intervene);
        correct_interventions += usize::from(expected_intervene && predicted_intervene);
        expected_non_interventions += usize::from(!expected_intervene);
        correct_non_interventions += usize::from(!expected_intervene && !predicted_intervene);
        unnecessary_interventions += usize::from(!expected_intervene && predicted_intervene);

        if report.exploration_case {
            exploration_cases += 1;
            preserved_exploration_cases += usize::from(!predicted_intervene);
        }
        if report.ambiguous_case {
            ambiguous_cases += 1;
            ambiguous_restrained_cases += usize::from(!predicted_intervene);
        }
        exact_correct += usize::from(report.correct_action);
        boundary_misses += usize::from(!report.correct_action);
        outcome_gain_total += report.regret_reduction;
        case_reports.push(report);
    }

    let intervention_precision =
        safe_div(correct_interventions as f64, predicted_interventions as f64).max(
            if predicted_interventions == 0 {
                1.0
            } else {
                0.0
            },
        );
    let intervention_recall = safe_div(correct_interventions as f64, expected_interventions as f64);
    let intervention_restraint = safe_div(
        correct_non_interventions as f64,
        expected_non_interventions as f64,
    );
    let unnecessary_intervention_rate = safe_div(
        unnecessary_interventions as f64,
        expected_non_interventions as f64,
    );
    let exploration_preservation = if exploration_cases == 0 {
        1.0
    } else {
        preserved_exploration_cases as f64 / exploration_cases as f64
    };
    let ambiguous_restraint_rate = if ambiguous_cases == 0 {
        1.0
    } else {
        ambiguous_restrained_cases as f64 / ambiguous_cases as f64
    };
    let regulation_boundary_score = safe_div(exact_correct as f64, case_reports.len() as f64);
    let boundary_miss_rate = safe_div(boundary_misses as f64, case_reports.len() as f64);
    let mean_outcome_gain = safe_div(outcome_gain_total, case_reports.len() as f64);
    let thresholds = GovernanceRegulationBoundaryThresholds {
        intervention_precision_min: 0.85,
        intervention_recall_min: 0.70,
        intervention_restraint_min: 0.85,
        unnecessary_intervention_max: 0.10,
        exploration_preservation_min: 0.90,
        ambiguous_restraint_min: 0.85,
        regulation_boundary_score_min: 0.80,
        mean_outcome_gain_min: 0.04,
    };
    let pass = intervention_precision >= thresholds.intervention_precision_min
        && intervention_recall >= thresholds.intervention_recall_min
        && intervention_restraint >= thresholds.intervention_restraint_min
        && unnecessary_intervention_rate <= thresholds.unnecessary_intervention_max
        && exploration_preservation >= thresholds.exploration_preservation_min
        && ambiguous_restraint_rate >= thresholds.ambiguous_restraint_min
        && regulation_boundary_score >= thresholds.regulation_boundary_score_min
        && mean_outcome_gain >= thresholds.mean_outcome_gain_min;

    Ok(GovernanceRegulationBoundaryEvaluationReport {
        tag,
        dataset: dataset_path,
        case_count: case_reports.len(),
        intervention_case_count: expected_interventions,
        non_intervention_case_count: expected_non_interventions,
        exploration_case_count: exploration_cases,
        ambiguous_case_count: ambiguous_cases,
        predicted_interventions,
        correct_interventions,
        unnecessary_interventions,
        intervention_precision,
        intervention_recall,
        intervention_restraint,
        unnecessary_intervention_rate,
        exploration_preservation,
        ambiguous_restraint_rate,
        regulation_boundary_score,
        boundary_miss_rate,
        mean_outcome_gain,
        pass,
        thresholds,
        rollback: GovernanceRollbackReport {
            rollback_model: "influence_regulation_boundary_counterfactual_only".to_string(),
            persistent_edge_mutations: 0,
            default_recall_behavior_changed: false,
            edge_deletions: 0,
        },
        cases: case_reports,
    })
}

fn evaluate_case(
    case: &GovernanceRegulationBoundaryCaseSpec,
) -> GovernanceRegulationBoundaryCaseReport {
    let harm_pressure = harm_pressure(case);
    let restraint_pressure = restraint_pressure(case);
    let boundary_margin = harm_pressure - restraint_pressure;
    let predicted_action = decide_action(harm_pressure, restraint_pressure, boundary_margin);
    let regulation_strength = regulation_strength(predicted_action, harm_pressure, boundary_margin);
    let regulated_influence =
        (case.current_influence * (1.0 - regulation_strength)).clamp(0.0, 1.0);
    let baseline_regret = (case.current_influence - case.desired_influence).abs();
    let regulated_regret = (regulated_influence - case.desired_influence).abs();
    let regret_reduction = baseline_regret - regulated_regret;
    let expected_action = case.expected_action;
    let correct_action = predicted_action == expected_action;
    let exploration_case = case.exploration_value >= 0.55 || case.case_type.contains("exploration");
    let ambiguous_case = case.case_type.contains("ambiguous")
        || (boundary_margin.abs() <= 0.14 && expected_action != RegulationAction::Intervene);

    GovernanceRegulationBoundaryCaseReport {
        id: case.id.clone(),
        case_type: case.case_type.clone(),
        expected_action,
        predicted_action,
        correct_action,
        harm_pressure,
        restraint_pressure,
        boundary_margin,
        risk_signal: case.risk_signal,
        pattern_risk: case.pattern_risk,
        contradiction_signal: case.contradiction_signal,
        evidence_support: case.evidence_support,
        novelty_score: case.novelty_score,
        uncertainty_score: case.uncertainty_score,
        context_volatility: case.context_volatility,
        exploration_value: case.exploration_value,
        current_influence: case.current_influence,
        desired_influence: case.desired_influence,
        regulated_influence,
        regulation_strength,
        baseline_regret,
        regulated_regret,
        regret_reduction,
        exploration_case,
        ambiguous_case,
    }
}

fn harm_pressure(case: &GovernanceRegulationBoundaryCaseSpec) -> f64 {
    (0.38 * case.risk_signal
        + 0.24 * case.pattern_risk
        + 0.22 * case.contradiction_signal
        + 0.16 * (1.0 - case.evidence_support))
        .clamp(0.0, 1.0)
}

fn restraint_pressure(case: &GovernanceRegulationBoundaryCaseSpec) -> f64 {
    (0.30 * case.novelty_score
        + 0.25 * case.uncertainty_score
        + 0.20 * case.context_volatility
        + 0.25 * case.exploration_value)
        .clamp(0.0, 1.0)
}

fn decide_action(
    harm_pressure: f64,
    restraint_pressure: f64,
    boundary_margin: f64,
) -> RegulationAction {
    if boundary_margin >= INTERVENTION_MARGIN && harm_pressure >= INTERVENTION_PRESSURE_MIN {
        RegulationAction::Intervene
    } else if boundary_margin <= RESTRAINT_MARGIN || restraint_pressure >= RESTRAINT_PRESSURE_MIN {
        RegulationAction::Hold
    } else {
        RegulationAction::Observe
    }
}

fn regulation_strength(action: RegulationAction, harm_pressure: f64, boundary_margin: f64) -> f64 {
    if action != RegulationAction::Intervene {
        return 0.0;
    }
    ((0.35 * harm_pressure + 0.65 * boundary_margin.max(0.0)) * MAX_REGULATION)
        .clamp(0.0, MAX_REGULATION)
}

fn safe_div(numerator: f64, denominator: f64) -> f64 {
    if denominator.abs() <= f64::EPSILON {
        0.0
    } else {
        numerator / denominator
    }
}

#[derive(Debug, Deserialize)]
struct GovernanceRegulationBoundaryDataset {
    cases: Vec<GovernanceRegulationBoundaryCaseSpec>,
}

#[derive(Debug, Deserialize)]
struct GovernanceRegulationBoundaryCaseSpec {
    id: String,
    case_type: String,
    expected_action: RegulationAction,
    risk_signal: f64,
    pattern_risk: f64,
    contradiction_signal: f64,
    evidence_support: f64,
    novelty_score: f64,
    uncertainty_score: f64,
    context_volatility: f64,
    exploration_value: f64,
    current_influence: f64,
    desired_influence: f64,
}

#[cfg(test)]
mod tests {
    use super::*;

    fn case_with(
        risk_signal: f64,
        pattern_risk: f64,
        contradiction_signal: f64,
        evidence_support: f64,
        novelty_score: f64,
        uncertainty_score: f64,
        exploration_value: f64,
    ) -> GovernanceRegulationBoundaryCaseSpec {
        GovernanceRegulationBoundaryCaseSpec {
            id: "case".to_string(),
            case_type: "test".to_string(),
            expected_action: RegulationAction::Observe,
            risk_signal,
            pattern_risk,
            contradiction_signal,
            evidence_support,
            novelty_score,
            uncertainty_score,
            context_volatility: 0.2,
            exploration_value,
            current_influence: 0.7,
            desired_influence: 0.4,
        }
    }

    #[test]
    fn high_harm_low_restraint_justifies_intervention() {
        let case = case_with(0.9, 0.8, 0.8, 0.1, 0.1, 0.1, 0.1);
        let harm = harm_pressure(&case);
        let restraint = restraint_pressure(&case);

        assert_eq!(
            decide_action(harm, restraint, harm - restraint),
            RegulationAction::Intervene
        );
    }

    #[test]
    fn high_exploration_pressure_holds_even_with_medium_risk() {
        let case = case_with(0.55, 0.35, 0.3, 0.5, 0.85, 0.8, 0.9);
        let harm = harm_pressure(&case);
        let restraint = restraint_pressure(&case);

        assert_eq!(
            decide_action(harm, restraint, harm - restraint),
            RegulationAction::Hold
        );
    }

    #[test]
    fn observe_zone_keeps_ambiguous_cases_out_of_intervention() {
        let case = case_with(0.60, 0.55, 0.45, 0.45, 0.35, 0.35, 0.35);
        let harm = harm_pressure(&case);
        let restraint = restraint_pressure(&case);

        assert_eq!(
            decide_action(harm, restraint, harm - restraint),
            RegulationAction::Observe
        );
    }
}
