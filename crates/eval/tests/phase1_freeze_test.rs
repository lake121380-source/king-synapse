use std::collections::BTreeSet;
use std::path::Path;
use synapse_eval::CognitiveMemoryBenchmarkEvaluator;

#[test]
fn phase1_cognitive_memory_freeze_report_is_stable() {
    let dataset_dir = Path::new(env!("CARGO_MANIFEST_DIR")).join("datasets/cognitive_memory");
    let report = CognitiveMemoryBenchmarkEvaluator::evaluate(
        dataset_dir,
        "phase1-freeze-test",
    )
    .expect("phase1 cognitive memory benchmark dataset should load");

    assert_eq!(report.case_count, 50);
    assert_eq!(report.challenge_count, 16);
    assert_eq!(report.suite_count, 9);
    assert!(report.pass);
    assert_eq!(report.validation_stage, "synthetic_initial");
    assert!(report
        .claim_boundary
        .contains("Directional synthetic evidence"));

    assert!(report.full_synapse_score > 0.0);
    assert!(report.best_rag_score > 0.0);
    assert!(report.full_over_best_rag_gain > 0.0);
    assert!(report.trace_quality.score > 0.0);
    assert!(
        report
            .memory_influence_attribution
            .mean_full_influence_score
            > 0.0
    );
    assert_eq!(report.error_analysis.success_cases, 46);
    assert_eq!(report.error_analysis.failed_cases, 4);
    assert_eq!(report.error_analysis.retrieval_failure_count, 0);
    assert_eq!(report.error_analysis.reasoning_failure_count, 4);

    let value = serde_json::to_value(&report).expect("report schema should serialize");
    for key in [
        "validation_stage",
        "claim_boundary",
        "trace_quality",
        "error_analysis",
        "memory_influence_attribution",
        "failed_cases",
        "ablation",
    ] {
        assert!(value.get(key).is_some(), "missing schema field {key}");
    }

    let expected_suites = BTreeSet::from([
        "adversarial",
        "causal",
        "consistency",
        "contradiction",
        "evolution",
        "failure_learning",
        "governance",
        "preference",
        "temporal",
    ]);
    let actual_suites = report
        .datasets
        .iter()
        .map(|dataset| dataset.suite.as_str())
        .collect::<BTreeSet<_>>();
    assert_eq!(actual_suites, expected_suites);
}
