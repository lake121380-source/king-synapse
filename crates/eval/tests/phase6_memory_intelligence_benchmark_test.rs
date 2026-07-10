use std::{collections::BTreeSet, sync::OnceLock};

use synapse_eval::{
    load_phase6_memory_intelligence_benchmark, Phase6MemoryIntelligenceBenchmarkEvaluator,
    Phase6MemoryIntelligenceReport,
};

fn report() -> &'static Phase6MemoryIntelligenceReport {
    static REPORT: OnceLock<Phase6MemoryIntelligenceReport> = OnceLock::new();
    REPORT.get_or_init(|| {
        Phase6MemoryIntelligenceBenchmarkEvaluator::evaluate("phase6-test")
            .expect("Phase 6.0 benchmark report")
    })
}

#[test]
fn benchmark_has_frozen_320_scenario_shape() {
    let scenarios = load_phase6_memory_intelligence_benchmark().expect("load benchmark");
    assert_eq!(scenarios.len(), 320);
    assert_eq!(
        scenarios
            .iter()
            .map(|scenario| scenario.memory.len())
            .sum::<usize>(),
        1920
    );
    assert_eq!(
        scenarios
            .iter()
            .map(|scenario| scenario.category.as_str())
            .collect::<BTreeSet<_>>()
            .len(),
        10
    );
    assert_eq!(
        scenarios
            .iter()
            .map(|scenario| scenario.query.as_str())
            .collect::<BTreeSet<_>>()
            .len(),
        320
    );
}

#[test]
fn every_category_has_fixed_train_validation_test_coverage() {
    let dataset = &report().dataset;
    assert_eq!(dataset.split_counts.get("train"), Some(&160));
    assert_eq!(dataset.split_counts.get("validation"), Some(&80));
    assert_eq!(dataset.split_counts.get("test"), Some(&80));
    assert_eq!(dataset.template_variants, 4);
    for counts in dataset.category_split_counts.values() {
        assert_eq!(counts.get("train"), Some(&16));
        assert_eq!(counts.get("validation"), Some(&8));
        assert_eq!(counts.get("test"), Some(&8));
    }
}

#[test]
fn timeline_ground_truth_and_conflict_labels_are_explicit() {
    let scenarios = load_phase6_memory_intelligence_benchmark().expect("load benchmark");
    for scenario in scenarios {
        assert!(scenario.conflicting_signals.len() >= 2);
        assert!(!scenario.expected_reason.trim().is_empty());
        let relevant = scenario
            .memory
            .iter()
            .filter(|memory| memory.relevant)
            .collect::<Vec<_>>();
        assert_eq!(relevant.len(), 1);
        assert_eq!(relevant[0].label, scenario.expected_top);
        assert_eq!(relevant[0].role, "ground_truth");
        assert_eq!(relevant[0].turn, scenario.timeline_length);
    }
}

#[test]
fn real_recall_engine_retrieves_every_expected_candidate() {
    let report = report();
    assert!(report.pass);
    assert_eq!(report.retrieval.expected_candidate_retrieval_rate, 1.0);
    assert_eq!(report.retrieval.recall_at_3, 1.0);
    assert_eq!(report.retrieval.recall_at_5, 1.0);
    assert_eq!(report.retrieval.determinism, 1.0);
    assert_eq!(report.retrieval.store_unchanged_rate, 1.0);
    assert_eq!(report.retrieval.label_intent_alignment, 1.0);
    assert_eq!(report.retrieval.entity_candidates, 0);
    assert_eq!(report.retrieval.entity_candidate_rate, 0.0);
}

#[test]
fn benchmark_contains_both_hard_and_no_intervention_cases() {
    let report = report();
    assert_eq!(report.dataset.intervention_required, 224);
    assert_eq!(report.dataset.no_intervention, 96);
    assert!((report.retrieval.recall_at_1 - 0.30).abs() <= 1e-12);
    assert!((report.retrieval.mrr_at_5 - 0.65).abs() <= 1e-12);
    for scenario in &report.scenarios {
        assert_eq!(
            scenario.intervention_required, !scenario.baseline_top_expected,
            "label mismatch in {}",
            scenario.id
        );
    }
}

#[test]
fn score_provenance_is_real_and_no_manual_score_field_exists() {
    let root = std::path::Path::new(env!("CARGO_MANIFEST_DIR"));
    let source = std::fs::read_to_string(
        root.join("datasets/memory_intelligence/agent_memory_benchmark.toml"),
    )
    .expect("benchmark source");
    assert!(!source.contains("baseline_score"));
    assert!(report()
        .scenarios
        .iter()
        .all(|scenario| scenario.retrieval_profile.fts_candidates == 6));
    assert!(report()
        .scenarios
        .iter()
        .all(|scenario| scenario.scores.len() == 5));
}

#[test]
fn phase6_gate_is_benchmark_only_and_never_authorizes_runtime() {
    let guards = &report().guards;
    assert!(guards.eval_only);
    assert!(guards.benchmark_only);
    assert!(guards.real_recall_engine_used);
    assert!(!guards.artificial_baseline_scores_used);
    assert!(!guards.vectors_enabled);
    assert!(!guards.reranker_enabled);
    assert!(!guards.access_recording_enabled);
    assert!(!guards.runtime_applied);
    assert!(!guards.memory_mutated_during_retrieval);
    assert!(!guards.recall_engine_modified);
    assert!(!guards.runtime_booster_registered);
    assert!(!guards.algorithm_comparison_performed);
    assert!(!guards.independent_cognitive_value_claimed);
    assert!(!guards.runtime_authorization);
    assert!(!guards.production_claim_authorized);
}

#[test]
fn fresh_run_reproduces_rankings_and_quality_metrics() {
    let fresh = Phase6MemoryIntelligenceBenchmarkEvaluator::evaluate("phase6-fresh")
        .expect("fresh Phase 6.0 report");
    let frozen = report();
    assert_eq!(fresh.retrieval.recall_at_1, frozen.retrieval.recall_at_1);
    assert_eq!(fresh.retrieval.recall_at_3, frozen.retrieval.recall_at_3);
    assert_eq!(fresh.retrieval.recall_at_5, frozen.retrieval.recall_at_5);
    assert_eq!(fresh.retrieval.mrr_at_5, frozen.retrieval.mrr_at_5);
    assert_eq!(fresh.retrieval.ndcg_at_5, frozen.retrieval.ndcg_at_5);
    for (left, right) in fresh.scenarios.iter().zip(&frozen.scenarios) {
        assert_eq!(left.id, right.id);
        assert_eq!(left.ranking, right.ranking);
        assert_eq!(left.expected_rank, right.expected_rank);
        assert_eq!(left.deterministic, right.deterministic);
        assert_eq!(left.scores.len(), right.scores.len());
        assert!(left.scores.iter().all(|score| score.is_finite()));
        assert!(right.scores.iter().all(|score| score.is_finite()));
    }
}

#[test]
fn checked_in_report_keeps_phase6_claim_boundary_explicit() {
    let path = std::path::Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("reports/phase6_memory_intelligence_benchmark.json");
    let value: serde_json::Value =
        serde_json::from_str(&std::fs::read_to_string(path).expect("checked-in Phase 6.0 report"))
            .expect("valid report JSON");
    assert_eq!(value["schema_version"], 1);
    assert_eq!(value["phase"], "Phase 6.0 Memory Intelligence Benchmark");
    assert_eq!(value["pass"], true);
    assert_eq!(value["guards"]["algorithm_comparison_performed"], false);
    assert_eq!(
        value["guards"]["independent_cognitive_value_claimed"],
        false
    );
    assert_eq!(value["guards"]["runtime_authorization"], false);
    assert_eq!(value["guards"]["production_claim_authorized"], false);
}
