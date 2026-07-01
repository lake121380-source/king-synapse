use synapse_eval::trace_reinforcement_report;

fn main() {
    let report = trace_reinforcement_report();
    println!(
        "{}",
        serde_json::to_string_pretty(&report)
            .expect("trace reinforcement benchmark report serializes")
    );
}
