use std::collections::BTreeMap;
use std::path::{Path, PathBuf};
use synapse_eval::Phase2TemporalInfluenceEvaluator;

#[test]
fn phase2_temporal_influence_eval_loads_same_dataset_without_mutation() {
    let dataset_dir = dataset_dir();
    let before = dataset_snapshot(&dataset_dir);
    let report = Phase2TemporalInfluenceEvaluator::evaluate(
        &dataset_dir,
        "phase2-temporal-influence-eval-test",
    )
    .expect("phase2 temporal influence evaluation should load");
    let after = dataset_snapshot(&dataset_dir);

    assert_eq!(before, after, "evaluation must not mutate datasets");
    assert_eq!(report.baseline.name, "synapse+competition");
    assert_eq!(report.temporal.name, "synapse+temporal+competition");
    assert_eq!(report.baseline.case_count, report.temporal.case_count);
    assert_eq!(report.case_count, report.baseline.case_count);
    assert_eq!(report.case_count, 200);
    assert_eq!(report.dataset_version, "v1.2");
    assert!(report.temporal_opportunities > 0);
}

#[test]
fn phase2_temporal_influence_eval_report_schema_is_valid() {
    let report = Phase2TemporalInfluenceEvaluator::evaluate(
        dataset_dir(),
        "phase2-temporal-influence-schema-test",
    )
    .expect("phase2 temporal influence evaluation should load");
    let value = serde_json::to_value(&report).expect("report should serialize");

    for key in [
        "baseline",
        "temporal",
        "temporal_errors",
        "metrics",
        "temporal_opportunities",
        "obsolete_opportunities",
        "causal_transition_opportunities",
        "cases",
        "status",
    ] {
        assert!(value.get(key).is_some(), "missing schema field {key}");
    }

    assert!(value["temporal_errors"].get("causal_order_error").is_some());
    assert!(value["temporal_errors"]
        .get("obsolete_memory_error")
        .is_some());
    assert!(value["metrics"].get("temporal_update_accuracy").is_some());
    assert!(value["metrics"].get("obsolete_memory_detection").is_some());
    assert!(value["metrics"].get("historical_preservation").is_some());
    assert!(value["metrics"].get("causal_transition_accuracy").is_some());
    assert!(report.metrics.temporal_update_accuracy >= 0.0);
    assert!(report.metrics.historical_preservation >= 0.0);
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
