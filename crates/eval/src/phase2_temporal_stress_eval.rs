use anyhow::Result;
use serde::Serialize;
use synapse_core::adaptive::{
    MemoryInfluenceState, RuleBasedTemporalTransitionEngine, TemporalEvent, TemporalMemoryProfile,
    TemporalTransitionEngine, TemporalTransitionStep,
};

const BASELINE_VERSION: &str = "phase2.7-temporal-supersession";

pub struct Phase2TemporalStressEvaluator;

impl Phase2TemporalStressEvaluator {
    pub fn evaluate(tag: impl Into<String>) -> Result<Phase2TemporalStressEvaluationReport> {
        Ok(evaluate_stress_scenarios(tag.into()))
    }
}

fn evaluate_stress_scenarios(tag: String) -> Phase2TemporalStressEvaluationReport {
    let engine = RuleBasedTemporalTransitionEngine::default();
    let threshold = engine.supersession_policy().pressure_threshold() as f64;

    let scenarios = vec![
        oscillation_scenario(&engine, threshold),
        delayed_contradiction_scenario(&engine, threshold),
        false_contradiction_scenario(&engine),
        memory_recovery_signal_scenario(&engine),
    ];

    let metrics = Phase2TemporalStressMetricsReport {
        oscillation_resistance: scenario_score(&scenarios, "oscillation"),
        delayed_contradiction_handling: scenario_score(&scenarios, "delayed_contradiction"),
        false_contradiction_restraint: scenario_score(&scenarios, "false_contradiction"),
        memory_recovery_signal: scenario_score(&scenarios, "memory_recovery"),
        state_recovery: state_recovery_score(&scenarios),
        historical_preservation: safe_div(
            scenarios.iter().filter(|scenario| scenario.stored).count() as f64,
            scenarios.len() as f64,
        ),
        stability_score: safe_div(
            scenarios.iter().filter(|scenario| scenario.success).count() as f64,
            scenarios.len() as f64,
        ),
    };

    let limitations = if metrics.state_recovery < 1.0 {
        vec![
            "The Phase 2.8 weak-recovery stress scenario emits a recovery signal but does not cross the Phase 2.9 reactivation threshold.".to_string(),
        ]
    } else {
        Vec::new()
    };

    let pass = scenarios.len() == 4
        && metrics.oscillation_resistance >= 1.0
        && metrics.delayed_contradiction_handling >= 1.0
        && metrics.false_contradiction_restraint >= 1.0
        && metrics.memory_recovery_signal >= 1.0
        && metrics.historical_preservation >= 1.0
        && metrics.stability_score >= 1.0;

    Phase2TemporalStressEvaluationReport {
        tag,
        baseline_version: BASELINE_VERSION.to_string(),
        mechanism_changed: false,
        dataset_changed: false,
        scenario_count: scenarios.len(),
        metrics,
        pass,
        status: "temporal_stress_evaluated".to_string(),
        limitations,
        scenarios,
    }
}

fn oscillation_scenario(
    engine: &RuleBasedTemporalTransitionEngine,
    threshold: f64,
) -> Phase2TemporalStressScenarioReport {
    let events = vec![
        TemporalEvent::Contradiction,
        TemporalEvent::SupportingEvidence,
        TemporalEvent::Contradiction,
        TemporalEvent::SupportingEvidence,
        TemporalEvent::Contradiction,
        TemporalEvent::SupportingEvidence,
    ];
    let memory = TemporalMemoryProfile::new("oscillating_preference", 0.90);
    let report = engine.apply_many(memory, &events);
    let success = report.memory.state == MemoryInfluenceState::Challenged
        && f64::from(report.memory.supersession_pressure) < threshold
        && report.memory.current_influence > report.memory.base_influence * 0.25
        && report.memory.stored;

    scenario_report(
        "temporal_stress_001_oscillation",
        "oscillation",
        "Oscillation Test",
        "Alternating contradiction and support should not wildly supersede a memory.",
        "Memory remains challenged, not superseded, while pressure stays below the supersession threshold.",
        events,
        report.memory,
        success,
        vec![
            "Alternating evidence produced bounded displacement pressure.".to_string(),
            "The memory stayed stored and influence was reduced rather than erased.".to_string(),
        ],
    )
}

fn delayed_contradiction_scenario(
    engine: &RuleBasedTemporalTransitionEngine,
    threshold: f64,
) -> Phase2TemporalStressScenarioReport {
    let events = vec![
        TemporalEvent::SupportingEvidence,
        TemporalEvent::SupportingEvidence,
        TemporalEvent::SupportingEvidence,
        TemporalEvent::Contradiction,
        TemporalEvent::FailureOutcome,
    ];
    let memory = TemporalMemoryProfile::new("long_lived_architecture_preference", 0.88);
    let report = engine.apply_many(memory, &events);
    let success = report.memory.state == MemoryInfluenceState::Superseded
        && f64::from(report.memory.supersession_pressure) >= threshold
        && report.memory.current_influence <= report.memory.base_influence * 0.25
        && report.memory.stored;

    scenario_report(
        "temporal_stress_002_delayed_contradiction",
        "delayed_contradiction",
        "Delayed Contradiction Test",
        "A long-valid memory should become superseded when later contradiction and failure accumulate enough pressure.",
        "Delayed counterevidence crosses the supersession threshold while preserving the historical memory.",
        events,
        report.memory,
        success,
        vec![
            "Early support did not block later displacement evidence.".to_string(),
            "The memory remained stored while future influence dropped to the superseded band.".to_string(),
        ],
    )
}

fn false_contradiction_scenario(
    engine: &RuleBasedTemporalTransitionEngine,
) -> Phase2TemporalStressScenarioReport {
    let events = vec![
        TemporalEvent::SupportingEvidence,
        TemporalEvent::SupportingEvidence,
        TemporalEvent::SupportingEvidence,
    ];
    let memory = TemporalMemoryProfile::new("coffee_preference", 0.82);
    let report = engine.apply_many(memory, &events);
    let success = report.memory.state == MemoryInfluenceState::Active
        && report.memory.supersession_pressure <= f32::EPSILON
        && (report.memory.current_influence - report.memory.base_influence).abs() <= f32::EPSILON
        && report.memory.stored;

    scenario_report(
        "temporal_stress_003_false_contradiction",
        "false_contradiction",
        "False Contradiction Test",
        "Compatible later evidence should not be treated as a contradiction just because it is semantically nearby.",
        "No displacement pressure is added and the memory stays active.",
        events,
        report.memory,
        success,
        vec![
            "The stress harness encodes compatible evidence as support, not contradiction.".to_string(),
            "No premature supersession occurred.".to_string(),
        ],
    )
}

fn memory_recovery_signal_scenario(
    engine: &RuleBasedTemporalTransitionEngine,
) -> Phase2TemporalStressScenarioReport {
    let events = vec![
        TemporalEvent::Contradiction,
        TemporalEvent::FailureOutcome,
        TemporalEvent::SupportingEvidence,
        TemporalEvent::SupportingEvidence,
        TemporalEvent::SupportingEvidence,
        TemporalEvent::SupportingEvidence,
    ];
    let memory = TemporalMemoryProfile::new("superseded_strategy_memory", 0.86);
    let report = engine.apply_many(memory, &events);
    let pressure_at_supersession = report
        .memory
        .transition_history
        .iter()
        .find(|step| step.to == MemoryInfluenceState::Superseded)
        .map(|step| step.supersession_pressure_after)
        .unwrap_or(report.memory.supersession_pressure);
    let recovery_signal_detected = report.memory.stored
        && report.memory.state == MemoryInfluenceState::Superseded
        && report.memory.supersession_pressure < pressure_at_supersession;

    scenario_report(
        "temporal_stress_004_memory_recovery_signal",
        "memory_recovery",
        "Memory Recovery Signal Test",
        "Later supporting evidence should show that a superseded memory can be reconsidered without being deleted.",
        "Recovery appears as reduced displacement pressure; actual state recovery is intentionally not implemented yet.",
        events,
        report.memory,
        recovery_signal_detected,
        vec![
            "Supporting evidence reduced displacement pressure after supersession.".to_string(),
            "State recovery remains unsupported: Superseded stayed Superseded.".to_string(),
        ],
    )
}

fn scenario_report(
    id: &str,
    stress_type: &str,
    name: &str,
    description: &str,
    expected: &str,
    events: Vec<TemporalEvent>,
    memory: TemporalMemoryProfile,
    success: bool,
    observations: Vec<String>,
) -> Phase2TemporalStressScenarioReport {
    let pressure_peak = memory
        .transition_history
        .iter()
        .map(|step| step.supersession_pressure_after)
        .fold(memory.supersession_pressure, f32::max);
    let state_recovered = memory
        .transition_history
        .iter()
        .any(|step| step.from == MemoryInfluenceState::Superseded && step.to != step.from);

    Phase2TemporalStressScenarioReport {
        id: id.to_string(),
        stress_type: stress_type.to_string(),
        name: name.to_string(),
        description: description.to_string(),
        expected: expected.to_string(),
        events: events.iter().map(event_name).collect(),
        final_state: format!("{:?}", memory.state),
        stored: memory.stored,
        base_influence: memory.base_influence as f64,
        current_influence: memory.current_influence as f64,
        influence_delta: (memory.base_influence - memory.current_influence) as f64,
        pressure_peak: pressure_peak as f64,
        pressure_final: memory.supersession_pressure as f64,
        state_recovered,
        success,
        observations,
        transition_history: memory
            .transition_history
            .iter()
            .map(transition_step_report)
            .collect(),
    }
}

fn transition_step_report(step: &TemporalTransitionStep) -> Phase2TemporalStressStepReport {
    Phase2TemporalStressStepReport {
        memory_id: step.memory_id.clone(),
        event: event_name(&step.event),
        from: format!("{:?}", step.from),
        to: format!("{:?}", step.to),
        influence_before: step.influence_before as f64,
        influence_after: step.influence_after as f64,
        supersession_pressure_before: step.supersession_pressure_before as f64,
        supersession_pressure_after: step.supersession_pressure_after as f64,
        reactivation_pressure_before: step.reactivation_pressure_before as f64,
        reactivation_pressure_after: step.reactivation_pressure_after as f64,
        reason: step.reason.clone(),
    }
}

fn event_name(event: &TemporalEvent) -> String {
    format!("{event:?}")
}

fn scenario_score(scenarios: &[Phase2TemporalStressScenarioReport], stress_type: &str) -> f64 {
    let matching = scenarios
        .iter()
        .filter(|scenario| scenario.stress_type == stress_type)
        .collect::<Vec<_>>();
    safe_div(
        matching.iter().filter(|scenario| scenario.success).count() as f64,
        matching.len() as f64,
    )
}

fn state_recovery_score(scenarios: &[Phase2TemporalStressScenarioReport]) -> f64 {
    let matching = scenarios
        .iter()
        .filter(|scenario| scenario.stress_type == "memory_recovery")
        .collect::<Vec<_>>();
    safe_div(
        matching
            .iter()
            .filter(|scenario| scenario.state_recovered)
            .count() as f64,
        matching.len() as f64,
    )
}

fn safe_div(numerator: f64, denominator: f64) -> f64 {
    if denominator.abs() < f64::EPSILON {
        0.0
    } else {
        numerator / denominator
    }
}

#[derive(Debug, Clone, Serialize)]
pub struct Phase2TemporalStressEvaluationReport {
    pub tag: String,
    pub baseline_version: String,
    pub mechanism_changed: bool,
    pub dataset_changed: bool,
    pub scenario_count: usize,
    pub metrics: Phase2TemporalStressMetricsReport,
    pub pass: bool,
    pub status: String,
    pub limitations: Vec<String>,
    pub scenarios: Vec<Phase2TemporalStressScenarioReport>,
}

#[derive(Debug, Clone, Serialize)]
pub struct Phase2TemporalStressMetricsReport {
    pub oscillation_resistance: f64,
    pub delayed_contradiction_handling: f64,
    pub false_contradiction_restraint: f64,
    pub memory_recovery_signal: f64,
    pub state_recovery: f64,
    pub historical_preservation: f64,
    pub stability_score: f64,
}

#[derive(Debug, Clone, Serialize)]
pub struct Phase2TemporalStressScenarioReport {
    pub id: String,
    pub stress_type: String,
    pub name: String,
    pub description: String,
    pub expected: String,
    pub events: Vec<String>,
    pub final_state: String,
    pub stored: bool,
    pub base_influence: f64,
    pub current_influence: f64,
    pub influence_delta: f64,
    pub pressure_peak: f64,
    pub pressure_final: f64,
    pub state_recovered: bool,
    pub success: bool,
    pub observations: Vec<String>,
    pub transition_history: Vec<Phase2TemporalStressStepReport>,
}

#[derive(Debug, Clone, Serialize)]
pub struct Phase2TemporalStressStepReport {
    pub memory_id: String,
    pub event: String,
    pub from: String,
    pub to: String,
    pub influence_before: f64,
    pub influence_after: f64,
    pub supersession_pressure_before: f64,
    pub supersession_pressure_after: f64,
    pub reactivation_pressure_before: f64,
    pub reactivation_pressure_after: f64,
    pub reason: String,
}
