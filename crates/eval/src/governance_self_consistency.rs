use crate::types::{
    GovernanceRollbackReport, GovernanceSelfConsistencyCaseReport,
    GovernanceSelfConsistencyEvaluationReport, GovernanceSelfConsistencyPathReport,
    GovernanceSelfConsistencyThresholds, RegulationAction,
};
use anyhow::{Context, Result};
use serde::Deserialize;
use std::collections::BTreeMap;
use std::path::Path;

const INTERVENTION_THRESHOLD: f64 = 0.62;
const HOLD_THRESHOLD: f64 = 0.58;
const DISAGREEMENT_UNCERTAINTY_MIN: f64 = 0.55;

pub struct GovernanceSelfConsistencyEvaluator;

impl GovernanceSelfConsistencyEvaluator {
    pub fn evaluate(
        dataset_path: impl AsRef<Path>,
        tag: impl Into<String>,
    ) -> Result<GovernanceSelfConsistencyEvaluationReport> {
        let dataset_path = dataset_path.as_ref();
        let raw = std::fs::read_to_string(dataset_path).with_context(|| {
            format!(
                "reading governance self-consistency dataset {}",
                dataset_path.display()
            )
        })?;
        let dataset: GovernanceSelfConsistencyDataset =
            toml::from_str(&raw).context("parsing governance self-consistency dataset TOML")?;
        evaluate_dataset(dataset, dataset_path.display().to_string(), tag.into())
    }
}

fn evaluate_dataset(
    dataset: GovernanceSelfConsistencyDataset,
    dataset_path: String,
    tag: String,
) -> Result<GovernanceSelfConsistencyEvaluationReport> {
    if dataset.cases.is_empty() {
        anyhow::bail!("governance self-consistency dataset has no cases");
    }

    let mut cases = Vec::with_capacity(dataset.cases.len());
    let mut agreement_scores = Vec::new();
    let mut decision_path_agreements = Vec::new();
    let mut uncertainty_alignments = Vec::new();
    let mut contradictions = 0usize;
    let mut high_uncertainty_disagreements = 0usize;
    let mut disagreement_count = 0usize;
    let mut expected_action_matches = 0usize;
    let mut abstention_agreements = 0usize;
    let mut abstention_cases = 0usize;
    let mut path_correct: BTreeMap<String, (usize, usize)> = BTreeMap::new();

    for case in dataset.cases {
        let report = evaluate_case(&case);
        agreement_scores.push(report.path_agreement_score);
        decision_path_agreements.push(report.decision_path_agreement);
        uncertainty_alignments.push(report.uncertainty_alignment);
        contradictions += usize::from(report.contradiction);
        disagreement_count += usize::from(report.disagreement);
        high_uncertainty_disagreements += usize::from(
            report.disagreement && report.uncertainty_alignment >= DISAGREEMENT_UNCERTAINTY_MIN,
        );
        expected_action_matches += usize::from(report.majority_action == report.expected_action);
        if report.expected_action != RegulationAction::Intervene {
            abstention_cases += 1;
            abstention_agreements +=
                usize::from(report.majority_action != RegulationAction::Intervene);
        }
        for path in &report.paths {
            let entry = path_correct.entry(path.path.clone()).or_insert((0, 0));
            entry.0 += usize::from(path.action == report.expected_action);
            entry.1 += 1;
        }
        cases.push(report);
    }

    let governance_consistency_score = mean(&agreement_scores).unwrap_or(1.0);
    let decision_path_agreement = mean(&decision_path_agreements).unwrap_or(1.0);
    let uncertainty_alignment = mean(&uncertainty_alignments).unwrap_or(1.0);
    let contradiction_rate = safe_div(contradictions as f64, cases.len() as f64);
    let disagreement_rate = safe_div(disagreement_count as f64, cases.len() as f64);
    let high_uncertainty_disagreement_rate = safe_div(
        high_uncertainty_disagreements as f64,
        disagreement_count as f64,
    );
    let majority_expected_alignment = safe_div(expected_action_matches as f64, cases.len() as f64);
    let abstention_consistency = safe_div(abstention_agreements as f64, abstention_cases as f64);
    let path_reliability = path_correct
        .into_iter()
        .map(|(path, (correct, total))| (path, safe_div(correct as f64, total as f64)))
        .collect::<Vec<_>>();

    let thresholds = GovernanceSelfConsistencyThresholds {
        governance_consistency_min: 0.78,
        decision_path_agreement_min: 0.75,
        uncertainty_alignment_min: 0.70,
        contradiction_rate_max: 0.12,
        high_uncertainty_disagreement_min: 0.70,
        majority_expected_alignment_min: 0.80,
        abstention_consistency_min: 0.90,
    };
    let pass = governance_consistency_score >= thresholds.governance_consistency_min
        && decision_path_agreement >= thresholds.decision_path_agreement_min
        && uncertainty_alignment >= thresholds.uncertainty_alignment_min
        && contradiction_rate <= thresholds.contradiction_rate_max
        && high_uncertainty_disagreement_rate >= thresholds.high_uncertainty_disagreement_min
        && majority_expected_alignment >= thresholds.majority_expected_alignment_min
        && abstention_consistency >= thresholds.abstention_consistency_min;

    Ok(GovernanceSelfConsistencyEvaluationReport {
        tag,
        dataset: dataset_path,
        case_count: cases.len(),
        governance_consistency_score,
        decision_path_agreement,
        uncertainty_alignment,
        contradiction_rate,
        disagreement_rate,
        high_uncertainty_disagreement_rate,
        majority_expected_alignment,
        abstention_consistency,
        pass,
        thresholds,
        rollback: GovernanceRollbackReport {
            rollback_model: "governance_self_consistency_counterfactual_only".to_string(),
            persistent_edge_mutations: 0,
            default_recall_behavior_changed: false,
            edge_deletions: 0,
        },
        path_reliability,
        cases,
    })
}

fn evaluate_case(case: &GovernanceSelfConsistencyCaseSpec) -> GovernanceSelfConsistencyCaseReport {
    let paths = vec![
        path_report("direct", direct_score(case), case),
        path_report("replay", replay_score(case), case),
        path_report("pattern", pattern_score(case), case),
        path_report("boundary", boundary_score(case), case),
    ];
    let majority_action = majority_action(&paths);
    let majority_count = paths
        .iter()
        .filter(|path| path.action == majority_action)
        .count();
    let path_agreement_score = majority_count as f64 / paths.len() as f64;
    let decision_path_agreement = pairwise_agreement(&paths);
    let disagreement = majority_count < paths.len();
    let uncertainty_alignment = if disagreement {
        case.uncertainty_level
    } else {
        1.0 - case.uncertainty_level
    }
    .clamp(0.0, 1.0);
    let contradiction = has_hard_contradiction(&paths);

    GovernanceSelfConsistencyCaseReport {
        id: case.id.clone(),
        case_type: case.case_type.clone(),
        expected_action: case.expected_action,
        majority_action,
        majority_matches_expected: majority_action == case.expected_action,
        path_agreement_score,
        decision_path_agreement,
        uncertainty_alignment,
        uncertainty_level: case.uncertainty_level,
        disagreement,
        contradiction,
        risk_signal: case.risk_signal,
        replay_regret_gain: case.replay_regret_gain,
        pattern_risk: case.pattern_risk,
        boundary_margin: case.boundary_margin,
        novelty_score: case.novelty_score,
        exploration_value: case.exploration_value,
        paths,
    }
}

fn path_report(
    path: impl Into<String>,
    score: f64,
    case: &GovernanceSelfConsistencyCaseSpec,
) -> GovernanceSelfConsistencyPathReport {
    let path = path.into();
    let action = action_from_score(score, case, &path);
    GovernanceSelfConsistencyPathReport {
        path,
        action,
        confidence: confidence_from_score(score),
        score,
    }
}

fn direct_score(case: &GovernanceSelfConsistencyCaseSpec) -> f64 {
    0.58 * case.risk_signal
        + 0.24 * case.contradiction_signal
        + 0.18 * (1.0 - case.evidence_support)
}

fn replay_score(case: &GovernanceSelfConsistencyCaseSpec) -> f64 {
    0.64 * case.replay_regret_gain + 0.20 * case.risk_signal + 0.16 * case.pattern_risk
}

fn pattern_score(case: &GovernanceSelfConsistencyCaseSpec) -> f64 {
    0.62 * case.pattern_risk + 0.22 * case.risk_signal + 0.16 * case.contradiction_signal
}

fn boundary_score(case: &GovernanceSelfConsistencyCaseSpec) -> f64 {
    let restraint =
        0.34 * case.novelty_score + 0.28 * case.exploration_value + 0.22 * case.uncertainty_level;
    (0.50 * case.boundary_margin + 0.35 * case.risk_signal + 0.15 * case.pattern_risk - restraint)
        .clamp(0.0, 1.0)
}

fn action_from_score(
    score: f64,
    case: &GovernanceSelfConsistencyCaseSpec,
    path: &str,
) -> RegulationAction {
    if score >= INTERVENTION_THRESHOLD {
        RegulationAction::Intervene
    } else if should_hold(score, case, path) {
        RegulationAction::Hold
    } else {
        RegulationAction::Observe
    }
}

fn should_hold(score: f64, case: &GovernanceSelfConsistencyCaseSpec, path: &str) -> bool {
    if case.exploration_value >= 0.70 || case.novelty_score >= 0.75 {
        return true;
    }
    path == "boundary" && score <= 0.18 && case.uncertainty_level >= HOLD_THRESHOLD
}

fn confidence_from_score(score: f64) -> f64 {
    (2.0 * (score - 0.5).abs()).clamp(0.0, 1.0)
}

fn majority_action(paths: &[GovernanceSelfConsistencyPathReport]) -> RegulationAction {
    let mut counts = BTreeMap::<String, (RegulationAction, usize)>::new();
    for path in paths {
        let key = action_key(path.action).to_string();
        let entry = counts.entry(key).or_insert((path.action, 0));
        entry.1 += 1;
    }
    counts
        .into_values()
        .max_by(|left, right| {
            left.1
                .cmp(&right.1)
                .then_with(|| action_priority(left.0).cmp(&action_priority(right.0)))
        })
        .map(|(action, _)| action)
        .unwrap_or(RegulationAction::Observe)
}

fn pairwise_agreement(paths: &[GovernanceSelfConsistencyPathReport]) -> f64 {
    let mut pairs = 0usize;
    let mut agreements = 0usize;
    for left in 0..paths.len() {
        for right in left + 1..paths.len() {
            pairs += 1;
            agreements += usize::from(paths[left].action == paths[right].action);
        }
    }
    safe_div(agreements as f64, pairs as f64)
}

fn has_hard_contradiction(paths: &[GovernanceSelfConsistencyPathReport]) -> bool {
    let has_intervene = paths
        .iter()
        .any(|path| path.action == RegulationAction::Intervene && path.confidence >= 0.50);
    let has_hold = paths
        .iter()
        .any(|path| path.action == RegulationAction::Hold && path.confidence >= 0.50);
    has_intervene && has_hold
}

fn action_key(action: RegulationAction) -> &'static str {
    match action {
        RegulationAction::Intervene => "intervene",
        RegulationAction::Observe => "observe",
        RegulationAction::Hold => "hold",
    }
}

fn action_priority(action: RegulationAction) -> usize {
    match action {
        RegulationAction::Observe => 3,
        RegulationAction::Hold => 2,
        RegulationAction::Intervene => 1,
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
struct GovernanceSelfConsistencyDataset {
    cases: Vec<GovernanceSelfConsistencyCaseSpec>,
}

#[derive(Debug, Deserialize)]
struct GovernanceSelfConsistencyCaseSpec {
    id: String,
    case_type: String,
    expected_action: RegulationAction,
    risk_signal: f64,
    contradiction_signal: f64,
    evidence_support: f64,
    replay_regret_gain: f64,
    pattern_risk: f64,
    boundary_margin: f64,
    novelty_score: f64,
    exploration_value: f64,
    uncertainty_level: f64,
}

#[cfg(test)]
mod tests {
    use super::*;

    fn case_with(
        risk_signal: f64,
        replay_regret_gain: f64,
        pattern_risk: f64,
        boundary_margin: f64,
        uncertainty_level: f64,
    ) -> GovernanceSelfConsistencyCaseSpec {
        GovernanceSelfConsistencyCaseSpec {
            id: "case".to_string(),
            case_type: "test".to_string(),
            expected_action: RegulationAction::Observe,
            risk_signal,
            contradiction_signal: risk_signal,
            evidence_support: 0.3,
            replay_regret_gain,
            pattern_risk,
            boundary_margin,
            novelty_score: 0.2,
            exploration_value: 0.2,
            uncertainty_level,
        }
    }

    #[test]
    fn majority_prefers_observe_on_tie() {
        let paths = vec![
            GovernanceSelfConsistencyPathReport {
                path: "a".to_string(),
                action: RegulationAction::Observe,
                confidence: 0.1,
                score: 0.5,
            },
            GovernanceSelfConsistencyPathReport {
                path: "b".to_string(),
                action: RegulationAction::Intervene,
                confidence: 0.1,
                score: 0.7,
            },
        ];

        assert_eq!(majority_action(&paths), RegulationAction::Observe);
    }

    #[test]
    fn high_risk_paths_converge_on_intervention() {
        let case = case_with(0.9, 0.8, 0.85, 0.75, 0.2);
        let report = evaluate_case(&case);

        assert_eq!(report.majority_action, RegulationAction::Intervene);
        assert!(report.path_agreement_score >= 0.75);
    }

    #[test]
    fn disagreement_alignment_rewards_uncertain_cases() {
        let case = case_with(0.6, 0.2, 0.7, 0.1, 0.8);
        let report = evaluate_case(&case);

        if report.disagreement {
            assert!(report.uncertainty_alignment >= 0.8);
        }
    }
}
