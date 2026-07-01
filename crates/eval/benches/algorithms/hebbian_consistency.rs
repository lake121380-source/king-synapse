use synapse_eval::hebbian_consistency_report;

fn main() {
    let report = hebbian_consistency_report();
    println!(
        "{}",
        serde_json::to_string_pretty(&report).expect("hebbian benchmark report serializes")
    );
}
