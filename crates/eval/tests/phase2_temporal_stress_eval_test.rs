use std::collections::{BTreeMap, BTreeSet};
use std::path::{Path, PathBuf};
use synapse_eval::Phase2TemporalStressEvaluator;

#[test]
fn phase2_temporal_stress_eval_covers_expected_scenarios() {
    let report = Phase2TemporalStressEvaluator::evaluate("phase2-temporal-stress-eval-test")
        .expect("phase2 temporal stress evaluation should run");
    let stress_types = report
        .scenarios
        .iter()
        .map(|scenario| scenario.stress_type.as_str())
        .collect::<BTreeSet<_>>();

    assert_eq!(report.baseline_version, "phase2.7-temporal-supersession");
    assert!(!report.mechanism_changed);
    assert!(!report.dataset_changed);
    assert_eq!(report.scenario_count, 4);
    assert_eq!(report.scenario_count, report.scenarios.len());
    assert!(stress_types.contains("oscillation"));
    assert!(stress_types.contains("delayed_contradiction"));
    assert!(stress_types.contains("false_contradiction"));
    assert!(stress_types.contains("memory_recovery"));
    assert!(report.metrics.historical_preservation >= 1.0);
    assert!(report.metrics.memory_recovery_signal >= 1.0);
}

#[test]
fn phase2_temporal_stress_eval_report_schema_is_valid() {
    let report = Phase2TemporalStressEvaluator::evaluate("phase2-temporal-stress-schema-test")
        .expect("phase2 temporal stress evaluation should run");
    let value = serde_json::to_value(&report).expect("report should serialize");

    for key in [
        "baseline_version",
        "mechanism_changed",
        "dataset_changed",
        "scenario_count",
        "metrics",
        "pass",
        "status",
        "limitations",
        "scenarios",
    ] {
        assert!(value.get(key).is_some(), "missing schema field {key}");
    }

    assert!(value["metrics"].get("oscillation_resistance").is_some());
    assert!(value["metrics"]
        .get("delayed_contradiction_handling")
        .is_some());
    assert!(value["metrics"]
        .get("false_contradiction_restraint")
        .is_some());
    assert!(value["metrics"].get("memory_recovery_signal").is_some());
    assert!(value["metrics"].get("state_recovery").is_some());
    assert!(value["metrics"].get("historical_preservation").is_some());
    assert!(value["metrics"].get("stability_score").is_some());
    assert_eq!(report.status, "temporal_stress_evaluated");
}

#[test]
fn phase2_temporal_stress_eval_does_not_mutate_dataset() {
    let dataset_dir = dataset_dir();
    let before = dataset_snapshot(&dataset_dir);
    let report = Phase2TemporalStressEvaluator::evaluate("phase2-temporal-stress-mutation-test")
        .expect("phase2 temporal stress evaluation should run");
    let after = dataset_snapshot(&dataset_dir);

    assert_eq!(before, after, "stress evaluation must not mutate datasets");
    assert!(!report.dataset_changed);
}

fn dataset_dir() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR")).join("datasets/cognitive_memory")
}

fn dataset_snapshot(dataset_dir: &Path) -> BTreeMap<String, String> {
    let mut snapshot = BTreeMap::new();
    for entry in std::fs::read_dir(dataset_dir).expect("dataset dir should be readable") {
        let path = entry.expect("dataset entry should be readable").path();
        if path.extension().and_then(|ext| ext.to_str()) != Some("toml") {
            continue;
        }
        let name = path
            .file_name()
            .and_then(|name| name.to_str())
            .expect("dataset file should have UTF-8 name")
            .to_string();
        let raw = std::fs::read_to_string(&path).expect("dataset file should be readable");
        snapshot.insert(name, raw);
    }
    snapshot
}
