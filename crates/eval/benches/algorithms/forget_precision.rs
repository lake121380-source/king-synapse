use synapse_eval::forget_precision_report;

fn main() {
    let report = forget_precision_report();
    println!(
        "{}",
        serde_json::to_string_pretty(&report).expect("forget benchmark report serializes")
    );
}
