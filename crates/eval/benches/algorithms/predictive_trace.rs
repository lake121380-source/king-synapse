use synapse_eval::predictive_trace_report;

fn main() {
    let report = predictive_trace_report();
    println!(
        "{}",
        serde_json::to_string_pretty(&report)
            .expect("predictive trace benchmark report serializes")
    );
}
