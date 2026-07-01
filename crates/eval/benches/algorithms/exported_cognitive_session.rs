use synapse_eval::exported_cognitive_session_report;

fn main() {
    let report = exported_cognitive_session_report();
    println!(
        "{}",
        serde_json::to_string_pretty(&report)
            .expect("exported cognitive session benchmark report serializes")
    );
}
