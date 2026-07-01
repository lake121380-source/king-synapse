use synapse_eval::merge_precision_report;

fn main() {
    let report = merge_precision_report();
    println!(
        "{}",
        serde_json::to_string_pretty(&report).expect("merge benchmark report serializes")
    );
}
