use std::collections::BTreeSet;
use std::path::{Path, PathBuf};
use synapse_eval::CognitiveMemoryBenchmarkEvaluator;
use toml::Value;

#[test]
fn phase1_dataset_scaling_loads_two_hundred_cases() {
    let dataset_dir = dataset_dir();
    let report = CognitiveMemoryBenchmarkEvaluator::evaluate(
        &dataset_dir,
        "phase1-dataset-scaling-test",
    )
    .expect("phase1.2 cognitive memory benchmark dataset should load");

    assert!(report.case_count >= 200, "expected at least 200 cases");
    assert!(report.suite_count >= 15, "expected at least 15 suites");
    assert!(report.pass, "scaled dataset should pass the frozen scorer");

    let suites = report
        .datasets
        .iter()
        .map(|dataset| dataset.suite.as_str())
        .collect::<BTreeSet<_>>();
    for suite in [
        "adversarial_expanded",
        "longitudinal_memory",
        "memory_conflict",
        "multi_entity_reasoning",
        "temporal_complex",
        "uncertainty_boundary",
    ] {
        assert!(suites.contains(suite), "missing suite {suite}");
    }
}

#[test]
fn phase1_dataset_scaling_has_unique_ids_and_required_fields() {
    let mut ids = BTreeSet::new();
    let mut case_count = 0usize;

    for path in dataset_files() {
        let raw = std::fs::read_to_string(&path)
            .unwrap_or_else(|error| panic!("failed to read {}: {error}", path.display()));
        let value = raw
            .parse::<Value>()
            .unwrap_or_else(|error| panic!("failed to parse {}: {error}", path.display()));
        let suite = value
            .get("suite")
            .and_then(Value::as_str)
            .unwrap_or_else(|| panic!("{} missing suite", path.display()));
        let cases = value
            .get("cases")
            .and_then(Value::as_array)
            .unwrap_or_else(|| panic!("{suite} missing cases array"));

        assert!(!cases.is_empty(), "{suite} has no cases");
        for case in cases {
            case_count += 1;
            let id = required_str(case, "id", suite);
            assert!(ids.insert(id.to_string()), "duplicated case id {id}");
            required_str(case, "question", suite);
            required_str(case, "expected_decision", suite);
            required_array(case, "relevant_memories", suite);
            required_array(case, "expected_trace", suite);
            assert!(
                case.get("profile").is_some() || case.get("methods").is_some(),
                "{suite}/{id} missing scoring profile or explicit methods"
            );
        }
    }

    assert!(case_count >= 200, "expected at least 200 cases");
}

fn dataset_dir() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR")).join("datasets/cognitive_memory")
}

fn dataset_files() -> Vec<PathBuf> {
    let mut files = std::fs::read_dir(dataset_dir())
        .expect("dataset directory should be readable")
        .map(|entry| entry.expect("dataset entry should be readable").path())
        .filter(|path| path.extension().and_then(|ext| ext.to_str()) == Some("toml"))
        .collect::<Vec<_>>();
    files.sort();
    files
}

fn required_str<'a>(case: &'a Value, field: &str, suite: &str) -> &'a str {
    case.get(field)
        .and_then(Value::as_str)
        .filter(|value| !value.trim().is_empty())
        .unwrap_or_else(|| panic!("{suite} case missing non-empty {field}"))
}

fn required_array<'a>(case: &'a Value, field: &str, suite: &str) -> &'a Vec<Value> {
    case.get(field)
        .and_then(Value::as_array)
        .filter(|value| !value.is_empty())
        .unwrap_or_else(|| panic!("{suite} case missing non-empty {field}"))
}
