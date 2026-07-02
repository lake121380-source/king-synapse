use synapse_eval::expanded_cognitive_replay_report;

fn main() {
    let report = expanded_cognitive_replay_report();
    println!(
        "{}",
        serde_json::to_string_pretty(&report)
            .expect("expanded cognitive replay benchmark report serializes")
    );
}
