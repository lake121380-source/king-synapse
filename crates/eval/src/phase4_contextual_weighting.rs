use crate::phase4_cognitive_influence::CandidateType;
use anyhow::Result;
use chrono::Utc;
use serde::Serialize;
use std::cmp::Ordering;
use std::collections::BTreeSet;

const EVALUATION_VERSION: &str = "phase4.3-contextual-cognitive-weighting";
const BASELINE_VERSION: &str = "phase4.2-cognitive-competition-model";
const SCORE_EPSILON: f32 = 0.0001;

pub struct Phase4ContextualWeightingEvaluator;

impl Phase4ContextualWeightingEvaluator {
    pub fn evaluate(tag: impl Into<String>) -> Result<Phase4ContextualWeightingReport> {
        Self::evaluate_with_parameters(tag, ContextualWeightParameters::default())
    }

    pub fn evaluate_with_parameters(
        tag: impl Into<String>,
        parameters: ContextualWeightParameters,
    ) -> Result<Phase4ContextualWeightingReport> {
        Ok(evaluate_contextual_weighting(tag.into(), parameters))
    }

    pub fn score_candidate_for_context(
        candidate: &ContextualCandidate,
        context: &CognitiveContext,
        parameters: ContextualWeightParameters,
    ) -> ContextualWeightBreakdown {
        score_candidate(candidate, context, parameters)
    }
}

fn evaluate_contextual_weighting(
    tag: String,
    parameters: ContextualWeightParameters,
) -> Phase4ContextualWeightingReport {
    let scenarios = contextual_weighting_scenarios();
    let traces = scenarios
        .iter()
        .map(|scenario| evaluate_scenario(scenario, parameters))
        .collect::<Vec<_>>();
    let safety = ContextualWeightingSafetyReport {
        core_changed: false,
        memory_written: false,
        runtime_weight_changed: false,
    };

    let metrics = Phase4ContextualWeightingMetrics {
        context_weight_accuracy: safe_div(
            traces
                .iter()
                .filter(|trace| trace.context_weight_correct)
                .count() as f32,
            traces.len() as f32,
        ),
        adaptive_weight_shift: safe_div(
            traces
                .iter()
                .filter(|trace| trace.adaptive_weight_shift)
                .count() as f32,
            traces.len() as f32,
        ),
        cross_context_consistency: safe_div(
            traces
                .iter()
                .filter(|trace| trace.cross_context_consistent)
                .count() as f32,
            traces.len() as f32,
        ),
        importance_explanation: safe_div(
            traces
                .iter()
                .filter(|trace| trace.explanation_complete)
                .count() as f32,
            traces.len() as f32,
        ),
        conflict_resolution: safe_div(
            traces
                .iter()
                .filter(|trace| trace.conflict_resolved)
                .count() as f32,
            traces.len() as f32,
        ),
    };

    let pass = traces.len() == scenarios.len()
        && metrics.context_weight_accuracy >= 1.0
        && metrics.adaptive_weight_shift >= 1.0
        && metrics.cross_context_consistency >= 1.0
        && metrics.importance_explanation >= 1.0
        && metrics.conflict_resolution >= 1.0
        && !safety.core_changed
        && !safety.memory_written
        && !safety.runtime_weight_changed
        && traces.iter().all(|trace| trace.contextual_weighting_safe);

    Phase4ContextualWeightingReport {
        tag,
        phase: "4.3".to_string(),
        mode: "evaluation_only".to_string(),
        evaluation_version: EVALUATION_VERSION.to_string(),
        baseline_version: BASELINE_VERSION.to_string(),
        generated_at: Utc::now().to_rfc3339(),
        scenarios: traces.len(),
        parameters,
        metrics,
        safety,
        pass,
        status: "contextual_cognitive_weighting_evaluated".to_string(),
        traces,
    }
}

fn evaluate_scenario(
    scenario: &ContextualWeightingScenario,
    parameters: ContextualWeightParameters,
) -> ContextualWeightingTrace {
    let mut candidate_weights = scenario
        .candidates
        .iter()
        .map(|candidate| score_candidate(candidate, &scenario.context, parameters))
        .collect::<Vec<_>>();
    candidate_weights.sort_by(compare_breakdown);

    let ranking = candidate_weights
        .iter()
        .map(|candidate| ContextualInfluenceRanking {
            candidate_id: candidate.candidate_id.clone(),
            candidate_type: candidate.candidate_type,
            contextual_weight: candidate.contextual_weight,
            final_influence: candidate.final_influence,
        })
        .collect::<Vec<_>>();

    let dominant = candidate_weights
        .first()
        .expect("contextual weighting scenarios always include candidates");
    let expected_dominant_candidate = scenario.expected_dominant_id.to_string();
    let conflict_resolved = dominant.candidate_id == expected_dominant_candidate;
    let context_variants = scenario
        .context_variants
        .iter()
        .flat_map(|variant| {
            scenario.candidates.iter().map(|candidate| {
                let breakdown = score_candidate(candidate, &variant.context, parameters);
                ContextVariantReport {
                    label: variant.label.to_string(),
                    context: variant.context.clone(),
                    candidate_id: candidate.id.clone(),
                    contextual_weight: breakdown.contextual_weight,
                    final_influence: breakdown.final_influence,
                }
            })
        })
        .collect::<Vec<_>>();
    let context_weight_correct = validate_context_weight(scenario, &context_variants);
    let adaptive_weight_shift = validate_adaptive_shift(scenario, &context_variants);
    let cross_context_consistent = validate_cross_context_consistency(scenario, &context_variants);
    let explanation = explanation_for_trace(
        scenario,
        dominant,
        &candidate_weights,
        &context_variants,
        conflict_resolved,
    );
    let explanation_complete = explanation.iter().any(|line| line.contains("candidate"))
        && explanation.iter().any(|line| line.contains("context"))
        && explanation
            .iter()
            .any(|line| line.contains("weight_breakdown"))
        && explanation
            .iter()
            .any(|line| line.contains("final influence"))
        && explanation.iter().any(|line| line.contains("reason"));

    ContextualWeightingTrace {
        scenario_id: scenario.id.to_string(),
        context: scenario.context.clone(),
        expected_dominant_candidate,
        dominant_candidate: dominant.candidate_id.clone(),
        dominant_candidate_type: dominant.candidate_type,
        candidate_weights,
        ranking,
        context_variants,
        context_weight_correct,
        adaptive_weight_shift,
        cross_context_consistent,
        explanation_complete,
        conflict_resolved,
        explanation,
        contextual_weighting_safe: true,
        core_changed: false,
        memory_written: false,
        runtime_weight_changed: false,
    }
}

fn score_candidate(
    candidate: &ContextualCandidate,
    context: &CognitiveContext,
    parameters: ContextualWeightParameters,
) -> ContextualWeightBreakdown {
    let context_match = context_match_score(candidate, context);
    let constraint_match = constraint_match_score(candidate, context);
    let temporal_confidence = candidate.temporal_confidence.clamp(0.0, 1.0);
    let reliability = candidate.reliability.clamp(0.0, 1.0);
    let context_component = parameters.context_match_weight * context_match;
    let constraint_component = parameters.constraint_match_weight * constraint_match;
    let temporal_component = parameters.temporal_confidence_weight * temporal_confidence;
    let reliability_component = parameters.reliability_weight * reliability;
    let contextual_weight =
        context_component + constraint_component + temporal_component + reliability_component;
    let final_influence = candidate.base_strength.clamp(0.0, 1.0) * contextual_weight;

    ContextualWeightBreakdown {
        candidate_id: candidate.id.clone(),
        candidate_type: candidate.candidate_type,
        base_strength: candidate.base_strength,
        historical_confidence: candidate.historical_confidence,
        context_match,
        constraint_match,
        temporal_confidence,
        reliability,
        context_component,
        constraint_component,
        temporal_component,
        reliability_component,
        contextual_weight,
        final_influence,
        reason: reason_for_weight(candidate, context, context_match, constraint_match),
    }
}

fn context_match_score(candidate: &ContextualCandidate, context: &CognitiveContext) -> f32 {
    let candidate_terms = feature_terms(&candidate.context_features);
    let task_terms = tokenize(&context.task_type);
    let environment_terms = tokenize(&context.environment);
    let task_score = overlap_score(&candidate_terms, &task_terms);
    let environment_score = overlap_score(&candidate_terms, &environment_terms);

    (0.70 * task_score + 0.30 * environment_score).clamp(0.0, 1.0)
}

fn constraint_match_score(candidate: &ContextualCandidate, context: &CognitiveContext) -> f32 {
    if context.constraints.is_empty() {
        return 0.5;
    }

    let candidate_terms = feature_terms(&candidate.context_features);
    let matched = context
        .constraints
        .iter()
        .filter(|constraint| {
            let terms = tokenize(constraint);
            !terms.is_empty() && terms.iter().all(|term| candidate_terms.contains(term))
        })
        .count();
    safe_div(matched as f32, context.constraints.len() as f32).clamp(0.0, 1.0)
}

fn feature_terms(features: &[String]) -> BTreeSet<String> {
    features
        .iter()
        .flat_map(|feature| tokenize(feature))
        .collect::<BTreeSet<_>>()
}

fn tokenize(text: &str) -> Vec<String> {
    text.to_lowercase()
        .split(|character: char| !character.is_ascii_alphanumeric())
        .filter(|token| token.len() > 2)
        .map(str::to_string)
        .collect()
}

fn overlap_score(candidate_terms: &BTreeSet<String>, context_terms: &[String]) -> f32 {
    if context_terms.is_empty() {
        return 0.0;
    }

    let matched = context_terms
        .iter()
        .filter(|term| candidate_terms.contains(*term))
        .count();
    safe_div(matched as f32, context_terms.len() as f32)
}

fn compare_breakdown(
    left: &ContextualWeightBreakdown,
    right: &ContextualWeightBreakdown,
) -> Ordering {
    let score_order = right
        .final_influence
        .partial_cmp(&left.final_influence)
        .unwrap_or(Ordering::Equal);
    if (left.final_influence - right.final_influence).abs() > SCORE_EPSILON {
        return score_order;
    }

    candidate_priority(right.candidate_type)
        .cmp(&candidate_priority(left.candidate_type))
        .then_with(|| left.candidate_id.cmp(&right.candidate_id))
}

fn candidate_priority(candidate_type: CandidateType) -> u8 {
    match candidate_type {
        CandidateType::Memory => 1,
        CandidateType::Lesson => 2,
        CandidateType::PlaybookCandidate => 3,
    }
}

fn reason_for_weight(
    candidate: &ContextualCandidate,
    context: &CognitiveContext,
    context_match: f32,
    constraint_match: f32,
) -> String {
    if constraint_match >= 0.90 {
        format!(
            "reason: {} matches current constraints for {} in {}",
            candidate.id, context.task_type, context.environment
        )
    } else if context_match >= 0.70 {
        format!(
            "reason: {} aligns with the current {} context",
            candidate.id, context.task_type
        )
    } else if candidate.temporal_confidence >= 0.85 {
        format!(
            "reason: {} remains relevant because temporal confidence is high",
            candidate.id
        )
    } else {
        format!(
            "reason: {} receives limited contextual support in this scenario",
            candidate.id
        )
    }
}

fn validate_context_weight(
    scenario: &ContextualWeightingScenario,
    variants: &[ContextVariantReport],
) -> bool {
    if let Some(order) = scenario.expected_variant_order {
        let weights = order
            .iter()
            .filter_map(|label| variant_for_label(variants, label))
            .map(|variant| variant.contextual_weight)
            .collect::<Vec<_>>();
        return weights
            .windows(2)
            .all(|window| window[0] > window[1] + SCORE_EPSILON);
    }

    true
}

fn validate_adaptive_shift(
    scenario: &ContextualWeightingScenario,
    variants: &[ContextVariantReport],
) -> bool {
    let Some(order) = scenario.expected_variant_order else {
        return true;
    };
    let weights = order
        .iter()
        .filter_map(|label| variant_for_label(variants, label))
        .map(|variant| variant.contextual_weight)
        .collect::<Vec<_>>();
    let (Some(max), Some(min)) = (
        weights.iter().copied().reduce(f32::max),
        weights.iter().copied().reduce(f32::min),
    ) else {
        return false;
    };

    max - min >= scenario.minimum_shift
}

fn validate_cross_context_consistency(
    scenario: &ContextualWeightingScenario,
    variants: &[ContextVariantReport],
) -> bool {
    if !scenario.requires_cross_context_consistency {
        return true;
    }

    validate_context_weight(scenario, variants)
        && variants
            .iter()
            .all(|variant| (0.0..=1.0).contains(&variant.contextual_weight))
}

fn variant_for_label<'a>(
    variants: &'a [ContextVariantReport],
    label: &&'static str,
) -> Option<&'a ContextVariantReport> {
    variants.iter().find(|variant| variant.label == *label)
}

fn explanation_for_trace(
    scenario: &ContextualWeightingScenario,
    dominant: &ContextualWeightBreakdown,
    candidate_weights: &[ContextualWeightBreakdown],
    variants: &[ContextVariantReport],
    conflict_resolved: bool,
) -> Vec<String> {
    vec![
        format!(
            "candidate {} selected as dominant under contextual weighting",
            dominant.candidate_id
        ),
        format!(
            "context task={} environment={} urgency={:.2}",
            scenario.context.task_type, scenario.context.environment, scenario.context.urgency
        ),
        format!(
            "weight_breakdown context={:.4} constraint={:.4} temporal={:.4} reliability={:.4}",
            dominant.context_component,
            dominant.constraint_component,
            dominant.temporal_component,
            dominant.reliability_component
        ),
        format!(
            "final influence {:.4} = base_strength {:.4} * contextual_weight {:.4}",
            dominant.final_influence, dominant.base_strength, dominant.contextual_weight
        ),
        format!("reason: {}", scenario.reason),
        format!(
            "conflict_resolved={} ranked_candidates={}",
            conflict_resolved,
            candidate_weights
                .iter()
                .map(|candidate| candidate.candidate_id.as_str())
                .collect::<Vec<_>>()
                .join(", ")
        ),
        format!(
            "context_variants={}",
            variants
                .iter()
                .map(|variant| format!(
                    "{}:{}:{:.4}",
                    variant.label, variant.candidate_id, variant.contextual_weight
                ))
                .collect::<Vec<_>>()
                .join(", ")
        ),
    ]
}

fn contextual_weighting_scenarios() -> Vec<ContextualWeightingScenario> {
    vec![
        ContextualWeightingScenario {
            id: "contextual_weighting_001_same_memory_different_context",
            reason: "the same deployment resource lesson should matter more in production than in a local experiment",
            context: context(
                "production deployment",
                "production",
                vec!["resource constraints", "rollback path"],
                0.90,
            ),
            expected_dominant_id: "lesson_check_resources",
            expected_variant_order: Some(&["production", "local"]),
            minimum_shift: 0.20,
            requires_cross_context_consistency: false,
            context_variants: vec![
                variant(
                    "production",
                    context(
                        "production deployment",
                        "production",
                        vec!["resource constraints", "rollback path"],
                        0.90,
                    ),
                ),
                variant(
                    "local",
                    context("local experiment", "local", vec!["resource constraints"], 0.20),
                ),
            ],
            candidates: vec![candidate(
                "lesson_check_resources",
                CandidateType::Lesson,
                0.78,
                0.82,
                0.86,
                0.90,
                vec![
                    "production",
                    "deployment",
                    "resource",
                    "constraints",
                    "rollback",
                    "path",
                ],
            )],
        },
        ContextualWeightingScenario {
            id: "contextual_weighting_002_context_overrides_history",
            reason: "a weaker-history lesson can win when it fits the immediate incident context",
            context: context(
                "database incident response",
                "production",
                vec!["database connectivity", "incident mitigation"],
                0.95,
            ),
            expected_dominant_id: "lesson_database_incident_context",
            expected_variant_order: None,
            minimum_shift: 0.0,
            requires_cross_context_consistency: false,
            context_variants: vec![],
            candidates: vec![
                candidate(
                    "memory_high_history_low_context",
                    CandidateType::Memory,
                    0.95,
                    0.95,
                    0.70,
                    0.75,
                    vec!["legacy", "stable", "archive", "batch"],
                ),
                candidate(
                    "lesson_database_incident_context",
                    CandidateType::Lesson,
                    0.56,
                    0.50,
                    0.92,
                    0.88,
                    vec![
                        "database",
                        "connectivity",
                        "incident",
                        "mitigation",
                        "production",
                        "response",
                    ],
                ),
            ],
        },
        ContextualWeightingScenario {
            id: "contextual_weighting_003_temporal_context_interaction",
            reason: "newer context-fit evidence should beat an old high-history strategy after environment change",
            context: context(
                "current deployment strategy",
                "new runtime",
                vec!["changed environment"],
                0.70,
            ),
            expected_dominant_id: "lesson_new_runtime_strategy",
            expected_variant_order: None,
            minimum_shift: 0.0,
            requires_cross_context_consistency: false,
            context_variants: vec![],
            candidates: vec![
                candidate(
                    "lesson_old_runtime_strategy",
                    CandidateType::Lesson,
                    0.90,
                    0.92,
                    0.12,
                    0.72,
                    vec!["old", "previous", "runtime", "deployment"],
                ),
                candidate(
                    "lesson_new_runtime_strategy",
                    CandidateType::Lesson,
                    0.68,
                    0.64,
                    0.94,
                    0.90,
                    vec![
                        "current",
                        "deployment",
                        "strategy",
                        "new",
                        "runtime",
                        "changed",
                        "environment",
                    ],
                ),
            ],
        },
        ContextualWeightingScenario {
            id: "contextual_weighting_004_constraint_aware_weighting",
            reason: "limited-memory constraints should raise the memory-efficient strategy above high-resource alternatives",
            context: context(
                "model deployment",
                "limited memory",
                vec!["limited memory", "low resource"],
                0.80,
            ),
            expected_dominant_id: "lesson_memory_efficient_strategy",
            expected_variant_order: None,
            minimum_shift: 0.0,
            requires_cross_context_consistency: false,
            context_variants: vec![],
            candidates: vec![
                candidate(
                    "lesson_memory_efficient_strategy",
                    CandidateType::Lesson,
                    0.68,
                    0.62,
                    0.88,
                    0.88,
                    vec![
                        "model",
                        "deployment",
                        "limited",
                        "memory",
                        "low",
                        "resource",
                        "efficient",
                    ],
                ),
                candidate(
                    "playbook_high_resource_strategy",
                    CandidateType::PlaybookCandidate,
                    0.82,
                    0.80,
                    0.72,
                    0.78,
                    vec!["model", "deployment", "high", "resource", "large", "batch"],
                ),
            ],
        },
        ContextualWeightingScenario {
            id: "contextual_weighting_005_cross_context_consistency",
            reason: "the same readiness lesson should change monotonically as context moves away from production deployment",
            context: context(
                "production deployment",
                "production",
                vec!["rollback path"],
                0.80,
            ),
            expected_dominant_id: "lesson_deployment_readiness",
            expected_variant_order: Some(&["production", "staging", "local"]),
            minimum_shift: 0.15,
            requires_cross_context_consistency: true,
            context_variants: vec![
                variant(
                    "production",
                    context(
                        "production deployment",
                        "production",
                        vec!["rollback path"],
                        0.80,
                    ),
                ),
                variant(
                    "staging",
                    context(
                        "staging deployment",
                        "staging",
                        vec!["rollback path"],
                        0.55,
                    ),
                ),
                variant(
                    "local",
                    context("local experiment", "local", vec!["fast iteration"], 0.15),
                ),
            ],
            candidates: vec![candidate(
                "lesson_deployment_readiness",
                CandidateType::Lesson,
                0.76,
                0.78,
                0.84,
                0.86,
                vec![
                    "production",
                    "deployment",
                    "rollback",
                    "path",
                    "resource",
                    "readiness",
                ],
            )],
        },
        ContextualWeightingScenario {
            id: "contextual_weighting_006_explanation_trace",
            reason: "the trace must explain candidate, context, weight breakdown, final influence, and suppression reason",
            context: context(
                "auditable production rollout",
                "production",
                vec!["rollback path", "permission check"],
                0.90,
            ),
            expected_dominant_id: "playbook_auditable_rollout",
            expected_variant_order: None,
            minimum_shift: 0.0,
            requires_cross_context_consistency: false,
            context_variants: vec![],
            candidates: vec![
                candidate(
                    "memory_generic_rollout",
                    CandidateType::Memory,
                    0.86,
                    0.86,
                    0.76,
                    0.76,
                    vec!["production", "rollout", "generic"],
                ),
                candidate(
                    "playbook_auditable_rollout",
                    CandidateType::PlaybookCandidate,
                    0.74,
                    0.74,
                    0.88,
                    0.92,
                    vec![
                        "auditable",
                        "production",
                        "rollout",
                        "rollback",
                        "path",
                        "permission",
                        "check",
                        "checklist",
                    ],
                ),
            ],
        },
    ]
}

fn context(
    task_type: &'static str,
    environment: &'static str,
    constraints: Vec<&'static str>,
    urgency: f32,
) -> CognitiveContext {
    CognitiveContext {
        task_type: task_type.to_string(),
        environment: environment.to_string(),
        constraints: constraints.into_iter().map(str::to_string).collect(),
        urgency,
    }
}

fn variant(label: &'static str, context: CognitiveContext) -> ContextVariant {
    ContextVariant { label, context }
}

fn candidate(
    id: &'static str,
    candidate_type: CandidateType,
    base_strength: f32,
    historical_confidence: f32,
    temporal_confidence: f32,
    reliability: f32,
    context_features: Vec<&'static str>,
) -> ContextualCandidate {
    ContextualCandidate {
        id: id.to_string(),
        candidate_type,
        base_strength,
        historical_confidence,
        temporal_confidence,
        reliability,
        context_features: context_features.into_iter().map(str::to_string).collect(),
        contextual_weight: 0.0,
        final_influence: 0.0,
    }
}

fn safe_div(numerator: f32, denominator: f32) -> f32 {
    if denominator.abs() < f32::EPSILON {
        0.0
    } else {
        numerator / denominator
    }
}

#[derive(Debug, Clone, Copy, Serialize)]
pub struct ContextualWeightParameters {
    pub context_match_weight: f32,
    pub constraint_match_weight: f32,
    pub temporal_confidence_weight: f32,
    pub reliability_weight: f32,
}

impl Default for ContextualWeightParameters {
    fn default() -> Self {
        Self {
            context_match_weight: 0.35,
            constraint_match_weight: 0.25,
            temporal_confidence_weight: 0.20,
            reliability_weight: 0.20,
        }
    }
}

#[derive(Debug, Clone, Serialize)]
pub struct ContextualCandidate {
    pub id: String,
    pub candidate_type: CandidateType,
    pub base_strength: f32,
    pub historical_confidence: f32,
    pub temporal_confidence: f32,
    pub reliability: f32,
    pub context_features: Vec<String>,
    pub contextual_weight: f32,
    pub final_influence: f32,
}

#[derive(Debug, Clone, Serialize)]
pub struct CognitiveContext {
    pub task_type: String,
    pub environment: String,
    pub constraints: Vec<String>,
    pub urgency: f32,
}

#[derive(Debug, Clone)]
struct ContextualWeightingScenario {
    id: &'static str,
    reason: &'static str,
    context: CognitiveContext,
    expected_dominant_id: &'static str,
    expected_variant_order: Option<&'static [&'static str]>,
    minimum_shift: f32,
    requires_cross_context_consistency: bool,
    context_variants: Vec<ContextVariant>,
    candidates: Vec<ContextualCandidate>,
}

#[derive(Debug, Clone)]
struct ContextVariant {
    label: &'static str,
    context: CognitiveContext,
}

#[derive(Debug, Clone, Serialize)]
pub struct Phase4ContextualWeightingReport {
    pub tag: String,
    pub phase: String,
    pub mode: String,
    pub evaluation_version: String,
    pub baseline_version: String,
    pub generated_at: String,
    pub scenarios: usize,
    pub parameters: ContextualWeightParameters,
    pub metrics: Phase4ContextualWeightingMetrics,
    pub safety: ContextualWeightingSafetyReport,
    pub pass: bool,
    pub status: String,
    pub traces: Vec<ContextualWeightingTrace>,
}

#[derive(Debug, Clone, Serialize)]
pub struct Phase4ContextualWeightingMetrics {
    pub context_weight_accuracy: f32,
    pub adaptive_weight_shift: f32,
    pub cross_context_consistency: f32,
    pub importance_explanation: f32,
    pub conflict_resolution: f32,
}

#[derive(Debug, Clone, Serialize)]
pub struct ContextualWeightingSafetyReport {
    pub core_changed: bool,
    pub memory_written: bool,
    pub runtime_weight_changed: bool,
}

#[derive(Debug, Clone, Serialize)]
pub struct ContextualWeightingTrace {
    pub scenario_id: String,
    pub context: CognitiveContext,
    pub expected_dominant_candidate: String,
    pub dominant_candidate: String,
    pub dominant_candidate_type: CandidateType,
    pub candidate_weights: Vec<ContextualWeightBreakdown>,
    pub ranking: Vec<ContextualInfluenceRanking>,
    pub context_variants: Vec<ContextVariantReport>,
    pub context_weight_correct: bool,
    pub adaptive_weight_shift: bool,
    pub cross_context_consistent: bool,
    pub explanation_complete: bool,
    pub conflict_resolved: bool,
    pub explanation: Vec<String>,
    pub contextual_weighting_safe: bool,
    pub core_changed: bool,
    pub memory_written: bool,
    pub runtime_weight_changed: bool,
}

#[derive(Debug, Clone, Serialize)]
pub struct ContextualWeightBreakdown {
    pub candidate_id: String,
    pub candidate_type: CandidateType,
    pub base_strength: f32,
    pub historical_confidence: f32,
    pub context_match: f32,
    pub constraint_match: f32,
    pub temporal_confidence: f32,
    pub reliability: f32,
    pub context_component: f32,
    pub constraint_component: f32,
    pub temporal_component: f32,
    pub reliability_component: f32,
    pub contextual_weight: f32,
    pub final_influence: f32,
    pub reason: String,
}

#[derive(Debug, Clone, Serialize)]
pub struct ContextualInfluenceRanking {
    pub candidate_id: String,
    pub candidate_type: CandidateType,
    pub contextual_weight: f32,
    pub final_influence: f32,
}

#[derive(Debug, Clone, Serialize)]
pub struct ContextVariantReport {
    pub label: String,
    pub context: CognitiveContext,
    pub candidate_id: String,
    pub contextual_weight: f32,
    pub final_influence: f32,
}
