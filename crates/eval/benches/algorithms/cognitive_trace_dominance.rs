use synapse_eval::cognitive_trace_dominance_report;

fn main() {
    let report = cognitive_trace_dominance_report();
    println!(
        "{}",
        serde_json::to_string_pretty(&report).expect("cognitive trace benchmark report serializes")
    );
}
