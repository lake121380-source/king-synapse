use std::collections::BTreeMap;
use std::path::{Path, PathBuf};
use synapse_eval::Phase2CompetitionEvaluator;

#[test]
fn phase2_competition_eval_loads_baseline_and_competition_modes() {
    let dataset_dir = dataset_dir();
    let before = dataset_snapshot(&dataset_dir);
    let report = Phase2CompetitionEvaluator::evaluate(&dataset_dir, "phase2-competition-eval-test")
        .expect("phase2 competition evaluation should load");
    let after = dataset_snapshot(&dataset_dir);

    assert_eq!(before, after, "evaluation must not mutate datasets");
    assert_eq!(report.baseline.name, "synapse");
    assert_eq!(report.competition.name, "synapse+competition");
    assert_eq!(report.baseline.case_count, report.competition.case_count);
    assert_eq!(report.case_count, report.baseline.case_count);
    assert_eq!(report.case_count, 200);
    assert_eq!(report.dataset_version, "v1.2");
}

#[test]
fn phase2_competition_eval_report_schema_is_valid() {
    let report =
        Phase2CompetitionEvaluator::evaluate(dataset_dir(), "phase2-competition-schema-test")
            .expect("phase2 competition evaluation should load");
    let value = serde_json::to_value(&report).expect("report should serialize");

    for key in [
        "baseline",
        "competition",
        "delta",
        "suppression_opportunities",
        "correct_suppressions",
        "cases",
        "status",
    ] {
        assert!(value.get(key).is_some(), "missing schema field {key}");
    }
    assert!(value["delta"].get("decision_mismatch").is_some());
    assert!(value["delta"].get("causal_order_error").is_some());
    assert!(value["delta"].get("suppression_correctness").is_some());
    assert!(value["delta"].get("influence_shift").is_some());
    assert!(report.suppression_opportunities > 0);
    assert!(report.delta.suppression_correctness >= 0.0);
    assert!(report.delta.influence_shift >= 0.0);
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
