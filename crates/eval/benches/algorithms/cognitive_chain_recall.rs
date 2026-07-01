use synapse_eval::cognitive_chain_recall_report;

fn main() {
    let report = cognitive_chain_recall_report();
    println!(
        "{}",
        serde_json::to_string_pretty(&report).expect("cognitive chain benchmark report serializes")
    );
}
