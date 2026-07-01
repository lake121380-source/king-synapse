use synapse_eval::long_horizon_cognitive_memory_report;

fn main() {
    let report = long_horizon_cognitive_memory_report();
    println!(
        "{}",
        serde_json::to_string_pretty(&report)
            .expect("long horizon cognitive memory benchmark report serializes")
    );
}
