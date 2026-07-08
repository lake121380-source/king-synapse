use crate::harness::run;
use crate::types::{
    BenchOptions, GovernanceDetectionReport, GovernanceEvaluationReport,
    GovernanceInterventionSafetyReport, GovernanceRollbackReport, GovernanceSourceTraceReport,
    GovernanceTemporalStabilityReport, SemanticEdgeLifecycleRecord, SemanticPolicyEvaluation,
};
use anyhow::{Context, Result};

pub struct GovernanceEvaluator;

impl GovernanceEvaluator {
    pub fn evaluate(opts: BenchOptions) -> Result<GovernanceEvaluationReport> {
        let report = run(opts).context("collecting governance validation trace")?;
        let Some(survival) = report.semantic_survival.as_ref() else {
            anyhow::bail!(
                "governance evaluation requires semantic_edge_mode != off and hypothesis_generation enabled"
            );
        };

        let detection = build_detection_report(&survival.records);
        let intervention = build_intervention_report(&survival.policy_search.policies);
        let stability = build_stability_report(&survival.records);
        let rollback = GovernanceRollbackReport {
            rollback_model: "in_memory_counterfactual_only".to_string(),
            persistent_edge_mutations: 0,
            default_recall_behavior_changed: false,
            edge_deletions: 0,
        };
        let source_trace = GovernanceSourceTraceReport {
            recall_at_10: report.recall_at_10,
            mrr_at_10: report.mrr_at_10,
            candidate_edges: survival.governance.candidate_edges,
            graduated_edges: survival.graduated_count,
            activated_edges: survival.activated_count,
            suspect_edges: survival.governance.suspect_edges,
            trusted_edges: survival.governance.trusted_edges,
            dormant_edges: survival.governance.dormant_edges,
            attribution_evaluated_edges: survival.utility.attribution_evaluated_edges,
            policy_count: survival.policy_search.policies.len(),
        };

        Ok(GovernanceEvaluationReport {
            tag: report.tag,
            dataset: report.dataset,
            n_memories: report.n_memories,
            n_queries: report.n_queries,
            semantic_judge: report.semantic_judge,
            semantic_edge_mode: report.semantic_edge_mode,
            detection_score: detection.f1,
            intervention_gain: intervention.intervention_gain,
            regression_rate: intervention.regression_rate,
            stability_score: stability.stability_score,
            suspect_detection: detection,
            intervention_safety: intervention,
            temporal_stability: stability,
            policy_search: survival.policy_search.clone(),
            rollback,
            source_trace,
        })
    }
}

fn build_detection_report(records: &[SemanticEdgeLifecycleRecord]) -> GovernanceDetectionReport {
    let evaluated: Vec<&SemanticEdgeLifecycleRecord> = records
        .iter()
        .filter(|record| record.attribution_queries > 0)
        .collect();
    let mut tp = 0usize;
    let mut fp = 0usize;
    let mut tn = 0usize;
    let mut fn_ = 0usize;

    for record in &evaluated {
        let predicted_suspect =
            record.governance_state == "suspect" || record.governance_state == "dormant";
        let harmful = is_harmful_edge(record);
        match (predicted_suspect, harmful) {
            (true, true) => tp += 1,
            (true, false) => fp += 1,
            (false, true) => fn_ += 1,
            (false, false) => tn += 1,
        }
    }

    let precision = rate(tp, tp + fp);
    let recall = rate(tp, tp + fn_);
    let f1 = if precision + recall > 0.0 {
        2.0 * precision * recall / (precision + recall)
    } else {
        0.0
    };
    let accuracy = rate(tp + tn, evaluated.len());

    GovernanceDetectionReport {
        evaluated_edges: evaluated.len(),
        predicted_suspect_edges: tp + fp,
        ground_truth_harmful_edges: tp + fn_,
        true_positive: tp,
        false_positive: fp,
        true_negative: tn,
        false_negative: fn_,
        precision,
        recall,
        f1,
        accuracy,
        method: "predicted suspect/dormant vs negative causal attribution".to_string(),
    }
}

fn build_intervention_report(
    policies: &[SemanticPolicyEvaluation],
) -> GovernanceInterventionSafetyReport {
    let best = best_policy(policies);
    let Some(best) = best else {
        return GovernanceInterventionSafetyReport {
            evaluated_queries: 0,
            changed_queries: 0,
            improved_queries: 0,
            harmed_queries: 0,
            neutral_queries: 0,
            intervention_gain: 0.0,
            regression_rate: 0.0,
            safety_passed: true,
            method: "best counterfactual governance policy vs full graph".to_string(),
        };
    };
    let regression_rate = rate(best.harmed_queries, best.evaluated_queries);
    GovernanceInterventionSafetyReport {
        evaluated_queries: best.evaluated_queries,
        changed_queries: best.changed_queries,
        improved_queries: best.improved_queries,
        harmed_queries: best.harmed_queries,
        neutral_queries: best.neutral_queries,
        intervention_gain: best.mean_mrr_delta_vs_full_graph,
        regression_rate,
        safety_passed: best.mean_mrr_delta_vs_full_graph >= 0.0 && regression_rate <= 0.05,
        method: format!("best policy by MRR: {}", best.name),
    }
}

fn build_stability_report(
    records: &[SemanticEdgeLifecycleRecord],
) -> GovernanceTemporalStabilityReport {
    let evaluated: Vec<&SemanticEdgeLifecycleRecord> = records
        .iter()
        .filter(|record| record.attribution_queries > 0)
        .collect();
    let stable_edges = evaluated
        .iter()
        .filter(|record| is_stable_edge(record))
        .count();
    let unstable_edges = evaluated.len().saturating_sub(stable_edges);
    let mean_consistency = if evaluated.is_empty() {
        0.0
    } else {
        evaluated
            .iter()
            .map(|record| record.causal_consistency)
            .sum::<f64>()
            / evaluated.len() as f64
    };
    let mean_variance = if evaluated.is_empty() {
        0.0
    } else {
        evaluated
            .iter()
            .map(|record| record.causal_mrr_delta_variance)
            .sum::<f64>()
            / evaluated.len() as f64
    };
    GovernanceTemporalStabilityReport {
        evaluated_edges: evaluated.len(),
        stable_edges,
        unstable_edges,
        mean_causal_consistency: mean_consistency,
        mean_causal_mrr_delta_variance: mean_variance,
        stability_score: rate(stable_edges, evaluated.len()),
        method: "stable when attribution has enough samples and low causal MRR variance"
            .to_string(),
    }
}

fn best_policy(policies: &[SemanticPolicyEvaluation]) -> Option<&SemanticPolicyEvaluation> {
    policies.iter().max_by(|a, b| {
        a.mean_mrr_delta_vs_full_graph
            .partial_cmp(&b.mean_mrr_delta_vs_full_graph)
            .unwrap_or(std::cmp::Ordering::Equal)
    })
}

fn is_harmful_edge(record: &SemanticEdgeLifecycleRecord) -> bool {
    record.mean_causal_mrr_delta < -0.005
        || record.causal_harmful_queries > record.causal_useful_queries
}

fn is_stable_edge(record: &SemanticEdgeLifecycleRecord) -> bool {
    record.attribution_queries >= 3 && record.causal_mrr_delta_variance <= 0.005
}

fn rate(numerator: usize, denominator: usize) -> f64 {
    if denominator == 0 {
        0.0
    } else {
        numerator as f64 / denominator as f64
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn record(
        state: &str,
        mean_causal_mrr_delta: f64,
        useful_queries: usize,
        harmful_queries: usize,
        attribution_queries: usize,
        variance: f64,
    ) -> SemanticEdgeLifecycleRecord {
        SemanticEdgeLifecycleRecord {
            edge_id: "edge".to_string(),
            source_id: "a".to_string(),
            target_id: "b".to_string(),
            source_key: "a".to_string(),
            target_key: "b".to_string(),
            relation: "supports".to_string(),
            judge_confidence: 0.8,
            reason_category: "semantic".to_string(),
            reason: "test".to_string(),
            created_at: 0,
            accepted_at_query: 0,
            accepted_context: "test".to_string(),
            observation_count: 0,
            distinct_context_count: 0,
            hypothesis_confidence: 0.0,
            hypothesis_status: "confirmed".to_string(),
            confirmed: true,
            graduated: true,
            graduation_step: Some(1),
            activation_hits: 0,
            activation_bonus_mean: 0.0,
            utility_queries: 0,
            useful_queries: 0,
            harmful_queries: 0,
            neutral_queries: 0,
            mean_rank_delta: 0.0,
            mean_mrr_delta: 0.0,
            correct_rank_improvements: 0,
            wrong_rank_promotions: 0,
            attribution_queries,
            causal_useful_queries: useful_queries,
            causal_harmful_queries: harmful_queries,
            causal_neutral_queries: attribution_queries
                .saturating_sub(useful_queries + harmful_queries),
            mean_causal_rank_delta: 0.0,
            mean_causal_mrr_delta,
            causal_mrr_delta_variance: variance,
            causal_consistency: 0.0,
            useful_ratio: 0.0,
            harmful_ratio: 0.0,
            governance_state: state.to_string(),
            governance_weight: 1.0,
            rank_delta: None,
        }
    }

    #[test]
    fn detection_scores_suspect_edges_against_negative_attribution() {
        let records = vec![
            record("suspect", -0.02, 0, 3, 3, 0.0),
            record("graduated", 0.01, 2, 0, 3, 0.0),
            record("graduated", -0.02, 0, 2, 3, 0.0),
        ];

        let report = build_detection_report(&records);

        assert_eq!(report.true_positive, 1);
        assert_eq!(report.false_negative, 1);
        assert_eq!(report.true_negative, 1);
        assert!((report.precision - 1.0).abs() < f64::EPSILON);
        assert!((report.recall - 0.5).abs() < f64::EPSILON);
    }

    #[test]
    fn intervention_safety_uses_best_policy_and_tracks_regressions() {
        let policies = vec![
            SemanticPolicyEvaluation {
                name: "regressive".to_string(),
                description: "test".to_string(),
                evaluated_queries: 10,
                changed_queries: 3,
                improved_queries: 1,
                harmed_queries: 2,
                neutral_queries: 7,
                mean_rank_delta_vs_full_graph: -0.1,
                mean_mrr_delta_vs_full_graph: -0.02,
                mean_edge_weight: 0.8,
            },
            SemanticPolicyEvaluation {
                name: "safe".to_string(),
                description: "test".to_string(),
                evaluated_queries: 10,
                changed_queries: 1,
                improved_queries: 1,
                harmed_queries: 0,
                neutral_queries: 9,
                mean_rank_delta_vs_full_graph: 0.0,
                mean_mrr_delta_vs_full_graph: 0.01,
                mean_edge_weight: 1.0,
            },
        ];

        let report = build_intervention_report(&policies);

        assert_eq!(report.method, "best policy by MRR: safe");
        assert_eq!(report.harmed_queries, 0);
        assert!(report.safety_passed);
        assert!((report.intervention_gain - 0.01).abs() < f64::EPSILON);
    }

    #[test]
    fn stability_requires_enough_samples_and_low_variance() {
        let records = vec![
            record("graduated", 0.0, 0, 0, 3, 0.001),
            record("graduated", 0.0, 0, 0, 2, 0.001),
            record("graduated", 0.0, 0, 0, 3, 0.010),
        ];

        let report = build_stability_report(&records);

        assert_eq!(report.evaluated_edges, 3);
        assert_eq!(report.stable_edges, 1);
        assert_eq!(report.unstable_edges, 2);
        assert!((report.stability_score - (1.0 / 3.0)).abs() < f64::EPSILON);
    }
}
