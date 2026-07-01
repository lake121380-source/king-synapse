use synapse_eval::reflection_yield_report;

fn main() {
    let report = reflection_yield_report();
    println!(
        "{}",
        serde_json::to_string_pretty(&report).expect("reflection benchmark report serializes")
    );
}
