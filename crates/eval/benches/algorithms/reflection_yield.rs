use synapse_eval::{deterministic_reflection_yield_report, reflection_yield_report};

fn main() {
    let report = vec![
        reflection_yield_report(),
        deterministic_reflection_yield_report(),
    ];
    println!(
        "{}",
        serde_json::to_string_pretty(&report).expect("reflection benchmark report serializes")
    );
}
