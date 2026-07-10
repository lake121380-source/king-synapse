use std::path::Path;
use synapse_eval::{
    ExplanationPreference, Phase5CognitiveTraceEvaluator, Phase5TraceQualityEvaluator,
    Phase5TraceQualityReport,
};

fn evaluate(tag: &str) -> Phase5TraceQualityReport {
    Phase5TraceQualityEvaluator::evaluate(tag)
        .expect("Phase 5.2 trace quality evaluation should run")
}

#[test]
fn phase5_2_trace_quality_report_passes() {
    let report = evaluate("phase5-2-pass");

    assert!(report.pass);
    assert_eq!(report.status, "PASS_LOCAL_DETERMINISTIC_QUALITY_GATE");
    assert_eq!(report.phase, "5.2");
    assert_eq!(report.mode, "evaluation_only");
}

#[test]
fn explanation_completeness_meets_gate() {
    let report = evaluate("phase5-2-completeness");

    assert!(report.metrics.explanation_completeness >= 0.90);
    assert!(report.scenario_reports.iter().all(|scenario| {
        scenario.completeness.dominant_identified
            && scenario.completeness.suppressed_candidates_explained
            && scenario.completeness.candidate_factor_coverage
            && scenario.completeness.required_factors_present
            && scenario.completeness.confidence_reported
    }));
}

#[test]
fn factor_faithfulness_is_perfect() {
    let report = evaluate("phase5-2-faithfulness");

    assert_eq!(report.metrics.factor_faithfulness, 1.0);
    assert!(report.scenario_reports.iter().all(|scenario| {
        scenario.factor_audit.hallucinated_factor_count == 0
            && scenario.factor_audit.missing_factor_count == 0
            && scenario.factor_audit.expected_factor_count
                == scenario.factor_audit.actual_factor_count
    }));
}

#[test]
fn trace_preference_rate_meets_gate() {
    let report = evaluate("phase5-2-preference");

    assert!(report.metrics.trace_preference_rate >= 0.80);
    assert!(report.scenario_reports.iter().all(|scenario| {
        scenario.judge.preferred_explanation == ExplanationPreference::CognitiveTrace
            && scenario.judge.cognitive_score > scenario.judge.baseline_score
    }));
}

#[test]
fn trace_is_deterministic() {
    let report = evaluate("phase5-2-determinism");

    assert_eq!(report.metrics.determinism, 1.0);
    assert!(report
        .scenario_reports
        .iter()
        .all(|scenario| scenario.deterministic));
}

#[test]
fn cognitive_trace_adds_explanation_information() {
    let report = evaluate("phase5-2-information-gain");

    assert!(report.metrics.explanation_information_gain > 0.0);
    assert!(
        report.metrics.cognitive_explanation_completeness
            > report.metrics.baseline_explanation_completeness
    );
}

#[test]
fn baseline_contains_only_retrieval_metadata() {
    let report = evaluate("phase5-2-baseline-boundary");

    for scenario in &report.scenario_reports {
        assert!(scenario.baseline_explanation.selected_candidate.is_some());
        assert_eq!(
            scenario.baseline_explanation.candidates.len(),
            scenario.candidate_count
        );
        assert!(scenario
            .baseline_explanation
            .candidates
            .iter()
            .all(|candidate| candidate.rank > 0 && !candidate.sources.is_empty()));
    }
}

#[test]
fn cognitive_trace_identifies_dominant_and_suppressed_candidates() {
    let report = evaluate("phase5-2-candidate-explanation");

    for scenario in &report.scenario_reports {
        assert!(scenario.cognitive_explanation.dominant_candidate.is_some());
        assert_eq!(
            scenario.cognitive_explanation.suppressed_candidates.len() + 1,
            scenario.candidate_count
        );
        assert_eq!(
            scenario.cognitive_explanation.factors_by_candidate.len(),
            scenario.candidate_count
        );
    }
}

#[test]
fn confidence_is_bounded() {
    let report = evaluate("phase5-2-confidence");

    assert!(report
        .scenario_reports
        .iter()
        .all(|scenario| { (0.0..=1.0).contains(&scenario.cognitive_explanation.confidence) }));
}

#[test]
fn trace_quality_is_eval_only() {
    let report = evaluate("phase5-2-eval-only");

    assert!(report.guards.eval_only);
    assert!(!report.guards.core_behavior_changed);
    assert!(!report.guards.memory_written);
    assert!(!report.guards.booster_enabled);
    assert!(!report.guards.external_model_called);
}

#[test]
fn recall_candidates_are_not_mutated() {
    let report = evaluate("phase5-2-no-mutation");

    assert!(!report.guards.recall_ranking_changed);
    assert!(!report.guards.recall_scores_changed);
    assert!(!report.guards.activation_changed);
    assert!(report.scenario_reports.iter().all(|scenario| {
        scenario.ranking_unchanged
            && scenario.scores_unchanged
            && scenario.activation_unchanged
            && scenario.memory_unchanged
            && !scenario.trace.mutated
    }));
}

#[test]
fn judge_protocol_is_honest_about_external_evidence() {
    let report = evaluate("phase5-2-judge-boundary");

    assert!(report.judge_protocol.external_judge_ready);
    assert!(!report.judge_protocol.human_or_llm_judge_completed);
    assert!(report.judge_protocol.mode.contains("deterministic"));
    assert!(report.judge_protocol.caveat.contains("not a claim"));
}

#[test]
fn retrieval_trace_alignment_is_reported_as_diagnostic() {
    let report = evaluate("phase5-2-alignment");

    assert!((0.0..=1.0).contains(&report.metrics.retrieval_trace_alignment));
    let aligned = report
        .scenario_reports
        .iter()
        .filter(|scenario| scenario.retrieval_trace_aligned)
        .count();
    assert_eq!(
        report.metrics.retrieval_trace_alignment,
        aligned as f64 / report.scenarios as f64
    );
}

#[test]
fn mixed_memory_kinds_produce_specialized_factors() {
    let report = evaluate("phase5-2-specialized-factors");
    let serialized = serde_json::to_string(&report).expect("report should serialize");

    assert!(serialized.contains("PreferenceAlignment"));
    assert!(serialized.contains("FailureEvidence"));
    assert!(serialized.contains("TemporalConfidence"));
    assert!(serialized.contains("ContextAlignment"));
}

#[test]
fn phase5_2_report_schema_is_stable() {
    let report = evaluate("phase5-2-schema");
    let value = serde_json::to_value(&report).expect("report should serialize");

    for key in [
        "schema_version",
        "phase",
        "mode",
        "evaluation_version",
        "baseline_version",
        "thresholds",
        "metrics",
        "guards",
        "judge_protocol",
        "pass",
        "status",
        "scenario_reports",
    ] {
        assert!(value.get(key).is_some(), "missing schema field {key}");
    }

    for metric in [
        "explanation_completeness",
        "factor_faithfulness",
        "trace_preference_rate",
        "determinism",
        "explanation_information_gain",
        "retrieval_trace_alignment",
    ] {
        assert!(
            value["metrics"].get(metric).is_some(),
            "missing metric {metric}"
        );
    }
}

#[test]
fn committed_phase5_2_report_loads_and_passes() {
    let report_path = Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("reports")
        .join("phase5_trace_quality.json");
    let report: serde_json::Value = serde_json::from_str(
        &std::fs::read_to_string(report_path).expect("committed Phase 5.2 report should load"),
    )
    .expect("committed Phase 5.2 report should be valid JSON");

    assert_eq!(report["phase"], "5.2");
    assert_eq!(report["pass"], true);
    assert_eq!(report["metrics"]["factor_faithfulness"], 1.0);
    assert_eq!(report["metrics"]["determinism"], 1.0);
}

#[test]
fn phase5_1_trace_integration_does_not_regress() {
    let phase5_1 = Phase5CognitiveTraceEvaluator::evaluate("phase5-1-regression")
        .expect("Phase 5.1 trace integration should still run");
    let phase5_2 = evaluate("phase5-2-regression");

    assert!(phase5_1.pass);
    assert!(phase5_2.pass);
    assert_eq!(phase5_1.metrics.recall_regression, 0.0);
}
