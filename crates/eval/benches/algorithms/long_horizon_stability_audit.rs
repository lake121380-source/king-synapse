use synapse_eval::long_horizon_stability_audit_report;

fn main() {
    let report = long_horizon_stability_audit_report();
    println!(
        "{}",
        serde_json::to_string_pretty(&report)
            .expect("long horizon stability audit report serializes")
    );
}
