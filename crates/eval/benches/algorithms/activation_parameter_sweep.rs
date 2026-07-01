use synapse_eval::activation_parameter_sweep_report;

fn main() {
    let report = activation_parameter_sweep_report();
    println!(
        "{}",
        serde_json::to_string_pretty(&report)
            .expect("activation parameter sweep benchmark report serializes")
    );
}
