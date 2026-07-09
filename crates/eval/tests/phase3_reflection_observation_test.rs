use synapse_eval::Phase3ReflectionObservationEvaluator;

#[test]
fn phase3_reflection_observation_generates_expected_trace_actions() {
    let report =
        Phase3ReflectionObservationEvaluator::evaluate("phase3-reflection-observation-test")
            .expect("phase3 reflection observation should run");

    assert_eq!(report.evaluation_version, "phase3.1-reflection-observation");
    assert_eq!(report.baseline_version, "phase2.10-memory-lifecycle-freeze");
    assert_eq!(report.implementation_status, "observation_only");
    assert_eq!(report.trace_count, report.traces.len());
    assert_eq!(report.trace_count, 6);
    assert!(report.reflected > 0);
    assert!(report.observed > 0);
    assert!(report.ignored > 0);
    assert!(report.pass);
}

#[test]
fn phase3_reflection_observation_is_side_effect_safe() {
    let report =
        Phase3ReflectionObservationEvaluator::evaluate("phase3-reflection-observation-safety-test")
            .expect("phase3 reflection observation should run");

    assert!(!report.mechanism_changed);
    assert!(!report.schema_changed);
    assert!(!report.retrieval_changed);
    assert!(!report.activation_changed);
    assert!(!report.temporal_lifecycle_changed);
    assert!(!report.governance_changed);
    assert!(!report.playbook_created);
    assert!(!report.future_influence_changed);
    assert_eq!(report.metrics.observation_safety, 1.0);
    assert!(report.traces.iter().all(|trace| {
        !trace.lesson_persisted && !trace.playbook_created && !trace.future_influence_changed
    }));
}

#[test]
fn phase3_reflection_observation_report_schema_is_valid() {
    let report =
        Phase3ReflectionObservationEvaluator::evaluate("phase3-reflection-observation-schema-test")
            .expect("phase3 reflection observation should run");
    let value = serde_json::to_value(&report).expect("report should serialize");

    for key in [
        "evaluation_version",
        "baseline_version",
        "trace_count",
        "metrics",
        "playbook_created",
        "future_influence_changed",
        "implementation_status",
        "status",
        "traces",
    ] {
        assert!(value.get(key).is_some(), "missing schema field {key}");
    }

    assert!(value["metrics"]
        .get("reflection_trigger_precision")
        .is_some());
    assert!(value["metrics"].get("reflection_trigger_recall").is_some());
    assert!(value["metrics"].get("lesson_grounding_readiness").is_some());
    assert!(value["metrics"].get("lesson_scope_readiness").is_some());
    assert!(value["metrics"].get("observation_safety").is_some());
    assert_eq!(report.status, "reflection_observation_traced");
}
