use anyhow::Result;
use chrono::Utc;
use serde::Serialize;

const BASELINE_VERSION: &str = "phase2.10-memory-lifecycle-freeze";
const EVALUATION_VERSION: &str = "phase3.1-reflection-observation";

pub struct Phase3ReflectionObservationEvaluator;

impl Phase3ReflectionObservationEvaluator {
    pub fn evaluate(tag: impl Into<String>) -> Result<Phase3ReflectionObservationReport> {
        Ok(evaluate_observation_cases(tag.into()))
    }
}

fn evaluate_observation_cases(tag: String) -> Phase3ReflectionObservationReport {
    let cases = observation_cases();
    let traces = cases
        .iter()
        .map(evaluate_case)
        .collect::<Vec<ReflectionTraceReport>>();
    let reflected = traces
        .iter()
        .filter(|trace| trace.observed_action == "Reflect")
        .count();
    let observed = traces
        .iter()
        .filter(|trace| trace.observed_action == "Observe")
        .count();
    let ignored = traces
        .iter()
        .filter(|trace| trace.observed_action == "Ignore")
        .count();
    let correct_actions = traces
        .iter()
        .filter(|trace| trace.observed_action == trace.expected_action)
        .count();
    let expected_reflect = traces
        .iter()
        .filter(|trace| trace.expected_action == "Reflect")
        .count();
    let correct_reflect = traces
        .iter()
        .filter(|trace| trace.expected_action == "Reflect" && trace.observed_action == "Reflect")
        .count();
    let false_reflect = traces
        .iter()
        .filter(|trace| trace.expected_action != "Reflect" && trace.observed_action == "Reflect")
        .count();
    let grounded_reflections = traces
        .iter()
        .filter(|trace| {
            trace.observed_action == "Reflect"
                && !trace.supporting_events.is_empty()
                && trace.lesson_candidate.is_some()
                && trace.grounding_status == "grounded"
        })
        .count();
    let scoped_reflections = traces
        .iter()
        .filter(|trace| {
            trace.observed_action != "Reflect"
                || (trace.lesson_scope != "global" && trace.overgeneralization_guard)
        })
        .count();
    let persistence_safe = traces.iter().all(|trace| {
        !trace.lesson_persisted && !trace.playbook_created && !trace.future_influence_changed
    });

    let metrics = Phase3ReflectionObservationMetrics {
        reflection_trigger_precision: safe_div(
            correct_reflect as f64,
            (correct_reflect + false_reflect) as f64,
        ),
        reflection_trigger_recall: safe_div(correct_reflect as f64, expected_reflect as f64),
        action_agreement: safe_div(correct_actions as f64, traces.len() as f64),
        lesson_grounding_readiness: safe_div(grounded_reflections as f64, reflected as f64),
        lesson_scope_readiness: safe_div(scoped_reflections as f64, traces.len() as f64),
        observation_safety: f64::from(persistence_safe),
    };

    let pass = traces.len() == cases.len()
        && metrics.reflection_trigger_precision >= 0.80
        && metrics.reflection_trigger_recall >= 0.80
        && metrics.action_agreement >= 0.80
        && metrics.lesson_grounding_readiness >= 0.80
        && metrics.lesson_scope_readiness >= 0.80
        && metrics.observation_safety >= 1.0;

    Phase3ReflectionObservationReport {
        tag,
        evaluation_version: EVALUATION_VERSION.to_string(),
        baseline_version: BASELINE_VERSION.to_string(),
        generated_at: Utc::now().to_rfc3339(),
        trace_count: traces.len(),
        reflected,
        observed,
        ignored,
        mechanism_changed: false,
        schema_changed: false,
        retrieval_changed: false,
        activation_changed: false,
        temporal_lifecycle_changed: false,
        governance_changed: false,
        playbook_created: false,
        future_influence_changed: false,
        implementation_status: "observation_only".to_string(),
        metrics,
        pass,
        status: "reflection_observation_traced".to_string(),
        traces,
    }
}

fn evaluate_case(case: &ObservationCase) -> ReflectionTraceReport {
    let observed_action = observed_action(case);
    let supporting_events = case
        .events
        .iter()
        .filter(|event| event.supports_reflection)
        .map(|event| event.id.to_string())
        .collect::<Vec<_>>();
    let contradicting_events = case
        .events
        .iter()
        .filter(|event| event.contradicts_reflection)
        .map(|event| event.id.to_string())
        .collect::<Vec<_>>();
    let lesson_candidate = if observed_action == "Reflect" {
        case.lesson_candidate.map(str::to_string)
    } else {
        None
    };

    ReflectionTraceReport {
        experience_id: case.id.to_string(),
        expected_action: case.expected_action.to_string(),
        observed_action: observed_action.to_string(),
        outcome: case.outcome.to_string(),
        impact: case.impact,
        failure_pattern: case.failure_pattern.map(str::to_string),
        successful_pattern: case.successful_pattern.map(str::to_string),
        lesson_candidate,
        lesson_scope: case.lesson_scope.to_string(),
        confidence: confidence_for_case(case, observed_action),
        supporting_events,
        contradicting_events,
        grounding_status: grounding_status(case, observed_action).to_string(),
        overgeneralization_guard: case.lesson_scope != "global",
        lesson_persisted: false,
        playbook_created: false,
        future_influence_changed: false,
        trace_notes: trace_notes(case, observed_action),
    }
}

fn observed_action(case: &ObservationCase) -> &'static str {
    let support_count = case
        .events
        .iter()
        .filter(|event| event.supports_reflection)
        .count();
    let contradiction_count = case
        .events
        .iter()
        .filter(|event| event.contradicts_reflection)
        .count();

    if case.impact >= 0.80 && support_count >= 2 && contradiction_count == 0 {
        "Reflect"
    } else if support_count > 0 || contradiction_count > 0 || case.impact >= 0.45 {
        "Observe"
    } else {
        "Ignore"
    }
}

fn confidence_for_case(case: &ObservationCase, observed_action: &str) -> f64 {
    let support_count = case
        .events
        .iter()
        .filter(|event| event.supports_reflection)
        .count() as f64;
    let contradiction_count = case
        .events
        .iter()
        .filter(|event| event.contradicts_reflection)
        .count() as f64;
    let raw = match observed_action {
        "Reflect" => 0.45 + case.impact * 0.35 + support_count * 0.08 - contradiction_count * 0.12,
        "Observe" => 0.35 + case.impact * 0.25 + support_count * 0.05,
        _ => 0.15 + case.impact * 0.10,
    };
    raw.clamp(0.0, 1.0)
}

fn grounding_status(case: &ObservationCase, observed_action: &str) -> &'static str {
    if observed_action == "Reflect" && case.lesson_candidate.is_some() {
        "grounded"
    } else if observed_action == "Observe" {
        "pending_evidence"
    } else {
        "not_applicable"
    }
}

fn trace_notes(case: &ObservationCase, observed_action: &str) -> Vec<String> {
    let mut notes = vec![
        "observation only: no lesson persisted".to_string(),
        "observation only: no playbook created".to_string(),
        "observation only: no future influence changed".to_string(),
    ];
    match observed_action {
        "Reflect" => notes.push(format!(
            "reflection candidate is grounded in {} supporting events",
            case.events
                .iter()
                .filter(|event| event.supports_reflection)
                .count()
        )),
        "Observe" => notes.push("insufficient evidence for lesson formation".to_string()),
        _ => notes.push("low-value event ignored by reflection observation".to_string()),
    }
    notes
}

fn observation_cases() -> Vec<ObservationCase> {
    vec![
        ObservationCase {
            id: "reflection_obs_001_gpu_deployment_failure",
            outcome: "large model deployment failed under GPU memory pressure",
            impact: 0.92,
            expected_action: "Reflect",
            failure_pattern: Some("resource validation missing before rollout"),
            successful_pattern: None,
            lesson_candidate: Some(
                "For GPU-limited model deployment, validate memory footprint before rollout.",
            ),
            lesson_scope: "gpu_limited_model_deployment",
            events: vec![
                ObservationEvent {
                    id: "gpu_failure_log",
                    supports_reflection: true,
                    contradicts_reflection: false,
                },
                ObservationEvent {
                    id: "oom_runtime_error",
                    supports_reflection: true,
                    contradicts_reflection: false,
                },
                ObservationEvent {
                    id: "user_correction_reduce_batch",
                    supports_reflection: true,
                    contradicts_reflection: false,
                },
            ],
        },
        ObservationCase {
            id: "reflection_obs_002_routine_success",
            outcome: "routine documentation update completed",
            impact: 0.12,
            expected_action: "Ignore",
            failure_pattern: None,
            successful_pattern: Some("routine success with no reusable strategy signal"),
            lesson_candidate: None,
            lesson_scope: "none",
            events: vec![ObservationEvent {
                id: "doc_update_success",
                supports_reflection: false,
                contradicts_reflection: false,
            }],
        },
        ObservationCase {
            id: "reflection_obs_003_ambiguous_one_off_error",
            outcome: "single transient network error without root cause",
            impact: 0.48,
            expected_action: "Observe",
            failure_pattern: Some("transient error without confirmed cause"),
            successful_pattern: None,
            lesson_candidate: None,
            lesson_scope: "network_diagnostics_pending",
            events: vec![ObservationEvent {
                id: "one_off_network_timeout",
                supports_reflection: true,
                contradicts_reflection: false,
            }],
        },
        ObservationCase {
            id: "reflection_obs_004_repeated_permission_failure",
            outcome: "deployment failed twice because database write permission was missing",
            impact: 0.88,
            expected_action: "Reflect",
            failure_pattern: Some("permission verification skipped before deployment"),
            successful_pattern: None,
            lesson_candidate: Some(
                "Before deployment, verify database write permissions for the runtime user.",
            ),
            lesson_scope: "database_backed_deployment",
            events: vec![
                ObservationEvent {
                    id: "first_permission_failure",
                    supports_reflection: true,
                    contradicts_reflection: false,
                },
                ObservationEvent {
                    id: "second_permission_failure",
                    supports_reflection: true,
                    contradicts_reflection: false,
                },
                ObservationEvent {
                    id: "operator_manual_fix",
                    supports_reflection: true,
                    contradicts_reflection: false,
                },
            ],
        },
        ObservationCase {
            id: "reflection_obs_005_local_docker_disk_scope",
            outcome: "local Docker image build failed because the workstation disk was full",
            impact: 0.83,
            expected_action: "Reflect",
            failure_pattern: Some("local environment capacity check missing"),
            successful_pattern: None,
            lesson_candidate: Some(
                "For local Docker builds, check available disk space before image build.",
            ),
            lesson_scope: "local_docker_build",
            events: vec![
                ObservationEvent {
                    id: "docker_build_failure",
                    supports_reflection: true,
                    contradicts_reflection: false,
                },
                ObservationEvent {
                    id: "disk_full_error",
                    supports_reflection: true,
                    contradicts_reflection: false,
                },
            ],
        },
        ObservationCase {
            id: "reflection_obs_006_mixed_docker_evidence",
            outcome: "one Docker failure followed by successful CI Docker builds",
            impact: 0.60,
            expected_action: "Observe",
            failure_pattern: Some("local Docker failure may not generalize"),
            successful_pattern: Some("CI Docker builds succeeded after cleanup"),
            lesson_candidate: None,
            lesson_scope: "docker_evidence_mixed",
            events: vec![
                ObservationEvent {
                    id: "local_docker_failure",
                    supports_reflection: true,
                    contradicts_reflection: false,
                },
                ObservationEvent {
                    id: "ci_docker_success",
                    supports_reflection: false,
                    contradicts_reflection: true,
                },
            ],
        },
    ]
}

fn safe_div(numerator: f64, denominator: f64) -> f64 {
    if denominator.abs() < f64::EPSILON {
        0.0
    } else {
        numerator / denominator
    }
}

#[derive(Debug, Clone)]
struct ObservationCase {
    id: &'static str,
    outcome: &'static str,
    impact: f64,
    expected_action: &'static str,
    failure_pattern: Option<&'static str>,
    successful_pattern: Option<&'static str>,
    lesson_candidate: Option<&'static str>,
    lesson_scope: &'static str,
    events: Vec<ObservationEvent>,
}

#[derive(Debug, Clone)]
struct ObservationEvent {
    id: &'static str,
    supports_reflection: bool,
    contradicts_reflection: bool,
}

#[derive(Debug, Clone, Serialize)]
pub struct Phase3ReflectionObservationReport {
    pub tag: String,
    pub evaluation_version: String,
    pub baseline_version: String,
    pub generated_at: String,
    pub trace_count: usize,
    pub reflected: usize,
    pub observed: usize,
    pub ignored: usize,
    pub mechanism_changed: bool,
    pub schema_changed: bool,
    pub retrieval_changed: bool,
    pub activation_changed: bool,
    pub temporal_lifecycle_changed: bool,
    pub governance_changed: bool,
    pub playbook_created: bool,
    pub future_influence_changed: bool,
    pub implementation_status: String,
    pub metrics: Phase3ReflectionObservationMetrics,
    pub pass: bool,
    pub status: String,
    pub traces: Vec<ReflectionTraceReport>,
}

#[derive(Debug, Clone, Serialize)]
pub struct Phase3ReflectionObservationMetrics {
    pub reflection_trigger_precision: f64,
    pub reflection_trigger_recall: f64,
    pub action_agreement: f64,
    pub lesson_grounding_readiness: f64,
    pub lesson_scope_readiness: f64,
    pub observation_safety: f64,
}

#[derive(Debug, Clone, Serialize)]
pub struct ReflectionTraceReport {
    pub experience_id: String,
    pub expected_action: String,
    pub observed_action: String,
    pub outcome: String,
    pub impact: f64,
    pub failure_pattern: Option<String>,
    pub successful_pattern: Option<String>,
    pub lesson_candidate: Option<String>,
    pub lesson_scope: String,
    pub confidence: f64,
    pub supporting_events: Vec<String>,
    pub contradicting_events: Vec<String>,
    pub grounding_status: String,
    pub overgeneralization_guard: bool,
    pub lesson_persisted: bool,
    pub playbook_created: bool,
    pub future_influence_changed: bool,
    pub trace_notes: Vec<String>,
}
