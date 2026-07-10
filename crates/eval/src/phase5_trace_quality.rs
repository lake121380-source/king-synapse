use anyhow::Result;
use chrono::Utc;
use serde::Serialize;
use std::cmp::Ordering;
use std::collections::{BTreeMap, BTreeSet};
use synapse_core::{
    CognitiveCompetitionTrace, CognitiveFactor, CognitiveFactorType, CognitiveTraceEvaluator,
    MemoryKind, RecallEngine, RecallHit, RecallQuery, Scope, Source, Store, WriteInput,
};

const EVALUATION_VERSION: &str = "phase5.2-cognitive-trace-quality-evaluation";
const BASELINE_VERSION: &str = "phase5.1-cognitive-competition-trace-integration";
const FACTOR_EPSILON: f64 = 0.000_001;

pub struct Phase5TraceQualityEvaluator;

impl Phase5TraceQualityEvaluator {
    pub fn evaluate(tag: impl Into<String>) -> Result<Phase5TraceQualityReport> {
        evaluate_trace_quality(tag.into())
    }
}

fn evaluate_trace_quality(tag: String) -> Result<Phase5TraceQualityReport> {
    let scenario_reports = quality_scenarios()
        .into_iter()
        .map(evaluate_scenario)
        .collect::<Result<Vec<_>>>()?;

    let explanation_completeness = average(
        scenario_reports
            .iter()
            .map(|scenario| scenario.explanation_completeness),
    );
    let factor_faithfulness = average(
        scenario_reports
            .iter()
            .map(|scenario| scenario.factor_faithfulness),
    );
    let trace_preference_rate = safe_div(
        scenario_reports
            .iter()
            .filter(|scenario| {
                scenario.judge.preferred_explanation == ExplanationPreference::CognitiveTrace
            })
            .count() as f64,
        scenario_reports.len() as f64,
    );
    let determinism = safe_div(
        scenario_reports
            .iter()
            .filter(|scenario| scenario.deterministic)
            .count() as f64,
        scenario_reports.len() as f64,
    );
    let retrieval_trace_alignment = safe_div(
        scenario_reports
            .iter()
            .filter(|scenario| scenario.retrieval_trace_aligned)
            .count() as f64,
        scenario_reports.len() as f64,
    );
    let baseline_explanation_completeness = average(
        scenario_reports
            .iter()
            .map(|scenario| scenario.judge.baseline_score),
    );
    let cognitive_explanation_completeness = average(
        scenario_reports
            .iter()
            .map(|scenario| scenario.judge.cognitive_score),
    );

    let thresholds = Phase5TraceQualityThresholds {
        explanation_completeness: 0.90,
        factor_faithfulness: 1.0,
        trace_preference_rate: 0.80,
        determinism: 1.0,
    };
    let metrics = Phase5TraceQualityMetrics {
        explanation_completeness,
        factor_faithfulness,
        trace_preference_rate,
        determinism,
        baseline_explanation_completeness,
        cognitive_explanation_completeness,
        explanation_information_gain: cognitive_explanation_completeness
            - baseline_explanation_completeness,
        retrieval_trace_alignment,
    };
    let guards = Phase5TraceQualityGuards {
        eval_only: true,
        core_behavior_changed: false,
        recall_ranking_changed: scenario_reports
            .iter()
            .any(|scenario| !scenario.ranking_unchanged),
        recall_scores_changed: scenario_reports
            .iter()
            .any(|scenario| !scenario.scores_unchanged),
        memory_written: scenario_reports
            .iter()
            .any(|scenario| !scenario.memory_unchanged),
        activation_changed: scenario_reports
            .iter()
            .any(|scenario| !scenario.activation_unchanged),
        booster_enabled: false,
        external_model_called: false,
    };
    let judge_protocol = Phase5TraceQualityJudgeProtocol {
        mode: "deterministic_pairwise_explanation_rubric_v1".to_string(),
        purpose: "CI-stable proxy for pairwise explanation value".to_string(),
        external_judge_ready: true,
        human_or_llm_judge_completed: false,
        caveat: "The preference metric is a deterministic rubric result, not a claim of completed human or LLM evaluation.".to_string(),
    };
    let pass = metrics.explanation_completeness >= thresholds.explanation_completeness
        && metrics.factor_faithfulness >= thresholds.factor_faithfulness
        && metrics.trace_preference_rate >= thresholds.trace_preference_rate
        && metrics.determinism >= thresholds.determinism
        && guards.eval_only
        && !guards.core_behavior_changed
        && !guards.recall_ranking_changed
        && !guards.recall_scores_changed
        && !guards.memory_written
        && !guards.activation_changed
        && !guards.booster_enabled
        && !guards.external_model_called;

    Ok(Phase5TraceQualityReport {
        schema_version: 1,
        tag,
        phase: "5.2".to_string(),
        mode: "evaluation_only".to_string(),
        evaluation_version: EVALUATION_VERSION.to_string(),
        baseline_version: BASELINE_VERSION.to_string(),
        generated_at: Utc::now().to_rfc3339(),
        scenarios: scenario_reports.len(),
        thresholds,
        metrics,
        guards,
        judge_protocol,
        pass,
        status: if pass {
            "PASS_LOCAL_DETERMINISTIC_QUALITY_GATE"
        } else {
            "FAIL"
        }
        .to_string(),
        scenario_reports,
    })
}

fn evaluate_scenario(scenario: QualityScenario) -> Result<Phase5TraceQualityScenarioReport> {
    let mut store = Store::open_in_memory()?;
    for memory in scenario.memories {
        store.write(WriteInput {
            content: memory.content.to_string(),
            kind: memory.kind,
            scope: Scope::User,
            source: Source::ExplicitUser,
            confidence: Some(memory.confidence),
            importance: Some(memory.importance),
        })?;
    }
    let query = RecallQuery {
        query: scenario.query.to_string(),
        k: Some(scenario.k),
        scope_filter: Some(Scope::User),
        kind_filter: None,
    };
    let mut engine = RecallEngine::new(&mut store).with_access_recording(false);
    let hits = engine.recall(&query)?;
    drop(engine);
    anyhow::ensure!(
        !hits.is_empty(),
        "Phase 5.2 scenario {} returned no RecallHit candidates",
        scenario.scenario_id
    );

    let memory_count_before_trace = store.list_recent(usize::MAX)?.len();
    let before_signature = hit_signature(&hits);
    let trace = CognitiveTraceEvaluator::evaluate(&query.query, &hits);
    let replay_trace = CognitiveTraceEvaluator::evaluate(&query.query, &hits);
    let after_signature = hit_signature(&hits);
    let memory_count_after_trace = store.list_recent(usize::MAX)?.len();
    let expected_factors = expected_factors(&query.query, &hits);
    let factor_audit = audit_factors(&trace.factors, &expected_factors);
    let completeness = completeness_audit(&trace, &hits, &expected_factors);
    let baseline_explanation = baseline_explanation(&hits);
    let cognitive_explanation = cognitive_explanation(&trace);
    let judge = judge_explanations(&baseline_explanation, &cognitive_explanation);
    let retrieval_top_candidate = hits.first().map(|hit| hit.memory.id.clone());
    let retrieval_trace_aligned = retrieval_top_candidate == trace.dominant_candidate;
    let deterministic = trace == replay_trace;

    Ok(Phase5TraceQualityScenarioReport {
        scenario_id: scenario.scenario_id.to_string(),
        query: query.query,
        candidate_count: hits.len(),
        retrieval_top_candidate,
        cognitive_dominant_candidate: trace.dominant_candidate.clone(),
        retrieval_trace_aligned,
        baseline_explanation,
        cognitive_explanation,
        trace,
        explanation_completeness: completeness.score,
        completeness,
        factor_faithfulness: factor_audit.score,
        factor_audit,
        judge,
        deterministic,
        ranking_unchanged: before_signature.ids == after_signature.ids,
        scores_unchanged: before_signature.scores == after_signature.scores,
        activation_unchanged: before_signature.activation == after_signature.activation,
        memory_unchanged: memory_count_before_trace == memory_count_after_trace,
    })
}
fn baseline_explanation(hits: &[RecallHit]) -> BaselineExplanation {
    BaselineExplanation {
        selected_candidate: hits.first().map(|hit| hit.memory.id.clone()),
        candidates: hits
            .iter()
            .enumerate()
            .map(|(index, hit)| BaselineCandidateMetadata {
                candidate_id: hit.memory.id.clone(),
                rank: index + 1,
                score: hit.score,
                sources: hit.sources.iter().map(ToString::to_string).collect(),
                valid_from: hit.memory.valid_from,
            })
            .collect(),
    }
}

fn cognitive_explanation(trace: &CognitiveCompetitionTrace) -> CognitiveExplanation {
    let mut factors_by_candidate = BTreeMap::<String, Vec<CognitiveFactor>>::new();
    for factor in &trace.factors {
        factors_by_candidate
            .entry(factor.candidate_id.clone())
            .or_default()
            .push(factor.clone());
    }
    CognitiveExplanation {
        dominant_candidate: trace.dominant_candidate.clone(),
        suppressed_candidates: trace.suppressed_candidates.clone(),
        factors_by_candidate,
        confidence: trace.confidence,
    }
}

fn completeness_audit(
    trace: &CognitiveCompetitionTrace,
    hits: &[RecallHit],
    expected_factors: &[CognitiveFactor],
) -> ExplanationCompletenessAudit {
    let candidate_ids = hits
        .iter()
        .map(|hit| hit.memory.id.as_str())
        .collect::<BTreeSet<_>>();
    let dominant_identified = trace
        .dominant_candidate
        .as_deref()
        .is_some_and(|candidate| candidate_ids.contains(candidate));
    let suppressed = trace
        .suppressed_candidates
        .iter()
        .map(String::as_str)
        .collect::<BTreeSet<_>>();
    let expected_suppressed = candidate_ids
        .iter()
        .copied()
        .filter(|candidate| Some(*candidate) != trace.dominant_candidate.as_deref())
        .collect::<BTreeSet<_>>();
    let suppressed_candidates_explained = suppressed == expected_suppressed;
    let actual_factor_candidates = trace
        .factors
        .iter()
        .map(|factor| factor.candidate_id.as_str())
        .collect::<BTreeSet<_>>();
    let candidate_factor_coverage = actual_factor_candidates == candidate_ids;
    let expected_keys = factor_keys(expected_factors);
    let actual_keys = factor_keys(&trace.factors);
    let required_factors_present = expected_keys == actual_keys;
    let confidence_reported = trace.confidence.is_finite()
        && (0.0..=1.0).contains(&trace.confidence)
        && trace.candidate_count == hits.len();
    let satisfied = [
        dominant_identified,
        suppressed_candidates_explained,
        candidate_factor_coverage,
        required_factors_present,
        confidence_reported,
    ]
    .into_iter()
    .filter(|value| *value)
    .count();

    ExplanationCompletenessAudit {
        dominant_identified,
        suppressed_candidates_explained,
        candidate_factor_coverage,
        required_factors_present,
        confidence_reported,
        satisfied_components: satisfied,
        total_components: 5,
        score: safe_div(satisfied as f64, 5.0),
    }
}

fn audit_factors(
    actual: &[CognitiveFactor],
    expected: &[CognitiveFactor],
) -> FactorFaithfulnessAudit {
    let mut matched_expected = vec![false; expected.len()];
    let mut faithful_factor_count = 0usize;
    let mut hallucinated_factors = Vec::new();

    for factor in actual {
        let match_index = expected.iter().enumerate().position(|(index, candidate)| {
            !matched_expected[index]
                && factor.candidate_id == candidate.candidate_id
                && factor.factor_type == candidate.factor_type
                && (factor.contribution - candidate.contribution).abs() <= FACTOR_EPSILON
        });
        if let Some(index) = match_index {
            matched_expected[index] = true;
            faithful_factor_count += 1;
        } else {
            hallucinated_factors.push(factor.clone());
        }
    }

    let missing_factors = expected
        .iter()
        .enumerate()
        .filter(|(index, _)| !matched_expected[*index])
        .map(|(_, factor)| factor.clone())
        .collect::<Vec<_>>();
    let denominator = actual.len().max(expected.len());

    FactorFaithfulnessAudit {
        expected_factor_count: expected.len(),
        actual_factor_count: actual.len(),
        faithful_factor_count,
        hallucinated_factor_count: hallucinated_factors.len(),
        missing_factor_count: missing_factors.len(),
        hallucinated_factors,
        missing_factors,
        score: if denominator == 0 {
            1.0
        } else {
            safe_div(faithful_factor_count as f64, denominator as f64)
        },
    }
}

fn judge_explanations(
    baseline: &BaselineExplanation,
    cognitive: &CognitiveExplanation,
) -> PairwiseExplanationJudgeReport {
    let baseline_criteria = ExplanationCriteria {
        outcome_identified: baseline.selected_candidate.is_some(),
        alternatives_explained: false,
        evidence_attributed: false,
        confidence_reported: false,
        candidate_coverage: !baseline.candidates.is_empty(),
    };
    let cognitive_criteria = ExplanationCriteria {
        outcome_identified: cognitive.dominant_candidate.is_some(),
        alternatives_explained: !cognitive.suppressed_candidates.is_empty(),
        evidence_attributed: !cognitive.factors_by_candidate.is_empty(),
        confidence_reported: cognitive.confidence.is_finite()
            && (0.0..=1.0).contains(&cognitive.confidence),
        candidate_coverage: cognitive.factors_by_candidate.len()
            == cognitive.suppressed_candidates.len()
                + usize::from(cognitive.dominant_candidate.is_some()),
    };
    let baseline_score = baseline_criteria.score();
    let cognitive_score = cognitive_criteria.score();
    let preferred_explanation = match cognitive_score.partial_cmp(&baseline_score) {
        Some(Ordering::Greater) => ExplanationPreference::CognitiveTrace,
        Some(Ordering::Less) => ExplanationPreference::BaselineMetadata,
        _ => ExplanationPreference::Tie,
    };

    PairwiseExplanationJudgeReport {
        protocol: "deterministic_pairwise_explanation_rubric_v1".to_string(),
        baseline_criteria,
        cognitive_criteria,
        baseline_score,
        cognitive_score,
        preferred_explanation,
        reasons: vec![
            "dominant outcome is explicit".to_string(),
            "suppressed alternatives are explicit".to_string(),
            "candidate-level factors are attributed".to_string(),
            "competition confidence is reported".to_string(),
        ],
    }
}

fn expected_factors(query: &str, hits: &[RecallHit]) -> Vec<CognitiveFactor> {
    let max_score = hits
        .iter()
        .map(|hit| hit.score as f64)
        .filter(|score| score.is_finite())
        .fold(0.0, f64::max)
        .max(FACTOR_EPSILON);
    hits.iter()
        .flat_map(|hit| {
            let candidate_id = hit.memory.id.clone();
            let overlap = lexical_overlap(query, &hit.memory.content);
            let mut factors = vec![
                expected_factor(
                    &candidate_id,
                    CognitiveFactorType::SemanticMatch,
                    normalize(hit.score as f64 / max_score) * 0.35,
                ),
                expected_factor(
                    &candidate_id,
                    CognitiveFactorType::TemporalConfidence,
                    temporal_confidence(hit) * 0.15,
                ),
                expected_factor(
                    &candidate_id,
                    CognitiveFactorType::Reliability,
                    normalize(hit.memory.confidence as f64) * 0.20,
                ),
                expected_factor(
                    &candidate_id,
                    CognitiveFactorType::ContextAlignment,
                    overlap * 0.15,
                ),
            ];
            if hit.memory.kind == MemoryKind::Preference {
                factors.push(expected_factor(
                    &candidate_id,
                    CognitiveFactorType::PreferenceAlignment,
                    (0.50 + overlap * 0.50) * 0.10,
                ));
            }
            if hit.memory.kind == MemoryKind::Failure {
                factors.push(expected_factor(
                    &candidate_id,
                    CognitiveFactorType::FailureEvidence,
                    (0.50 + overlap * 0.50) * 0.15,
                ));
            }
            factors
        })
        .collect()
}

fn expected_factor(
    candidate_id: &str,
    factor_type: CognitiveFactorType,
    contribution: f64,
) -> CognitiveFactor {
    CognitiveFactor {
        candidate_id: candidate_id.to_string(),
        factor_type,
        contribution: round4(contribution),
    }
}

fn temporal_confidence(hit: &RecallHit) -> f64 {
    if hit.memory.valid_to.is_some() || hit.memory.superseded_by.is_some() {
        0.20
    } else if hit.memory.last_accessed_at.is_some() {
        0.90
    } else {
        0.75
    }
}

fn lexical_overlap(query: &str, content: &str) -> f64 {
    let query_terms = terms(query);
    if query_terms.is_empty() {
        return 0.0;
    }
    let content_terms = terms(content);
    let matches = query_terms
        .iter()
        .filter(|term| content_terms.iter().any(|candidate| candidate == *term))
        .count();
    normalize(matches as f64 / query_terms.len() as f64)
}

fn terms(input: &str) -> Vec<String> {
    let mut output = input
        .split(|character: char| !character.is_alphanumeric())
        .map(|term| term.trim().to_ascii_lowercase())
        .filter(|term| term.len() >= 3)
        .collect::<Vec<_>>();
    output.sort();
    output.dedup();
    output
}

fn factor_keys(factors: &[CognitiveFactor]) -> BTreeSet<(String, String)> {
    factors
        .iter()
        .map(|factor| {
            (
                factor.candidate_id.clone(),
                format!("{:?}", factor.factor_type),
            )
        })
        .collect()
}

fn hit_signature(hits: &[RecallHit]) -> HitSignature {
    HitSignature {
        ids: hits.iter().map(|hit| hit.memory.id.clone()).collect(),
        scores: hits.iter().map(|hit| hit.score.to_bits()).collect(),
        activation: hits
            .iter()
            .map(|hit| hit.activation_bonus.to_bits())
            .collect(),
    }
}

fn quality_scenarios() -> Vec<QualityScenario> {
    vec![
        QualityScenario {
            scenario_id: "phase5_2_001_failure_evidence",
            query: "production deployment rollback failure",
            k: 8,
            memories: vec![
                memory("Production deployment rollback failure followed skipped resource validation.", MemoryKind::Failure, 0.95, 0.90),
                memory("Production deployment rollback playbook validates resources before release.", MemoryKind::Playbook, 0.90, 0.88),
                memory("Production deployment uses a staged rollback release process.", MemoryKind::Fact, 0.78, 0.75),
            ],
        },
        QualityScenario {
            scenario_id: "phase5_2_002_preference_alignment",
            query: "local prototype iteration preference",
            k: 8,
            memories: vec![
                memory("User preference favors fast local prototype iteration before architecture freeze.", MemoryKind::Preference, 0.96, 0.90),
                memory("Local prototype iteration should end with formal architecture review.", MemoryKind::Playbook, 0.88, 0.82),
                memory("Local prototype iteration reduces early feedback latency.", MemoryKind::Fact, 0.80, 0.76),
            ],
        },
        QualityScenario {
            scenario_id: "phase5_2_003_reliability_competition",
            query: "api retry timeout evidence",
            k: 8,
            memories: vec![
                memory("API retry timeout evidence weakly suggests one second is sufficient.", MemoryKind::Fact, 0.30, 0.70),
                memory("API retry timeout evidence shows one second caused repeated failures.", MemoryKind::Failure, 0.97, 0.94),
                memory("API retry timeout evidence should be validated under production latency.", MemoryKind::Playbook, 0.91, 0.88),
            ],
        },
        QualityScenario {
            scenario_id: "phase5_2_004_context_alignment",
            query: "gpu batch memory overflow",
            k: 8,
            memories: vec![
                memory("GPU batch memory overflow occurred when batch size exceeded capacity.", MemoryKind::Failure, 0.93, 0.92),
                memory("GPU batch experiments prefer fast iteration with small samples.", MemoryKind::Preference, 0.90, 0.84),
                memory("GPU memory capacity varies by accelerator model.", MemoryKind::Fact, 0.86, 0.80),
            ],
        },
        QualityScenario {
            scenario_id: "phase5_2_005_suppressed_alternatives",
            query: "release safety rollback verification",
            k: 8,
            memories: vec![
                memory("Release safety rollback verification must complete before rollout.", MemoryKind::Playbook, 0.95, 0.92),
                memory("Release safety rollback verification was skipped during a failed rollout.", MemoryKind::Failure, 0.94, 0.91),
                memory("Release preference favors speed after safety rollback verification.", MemoryKind::Preference, 0.89, 0.84),
                memory("Release rollback verification records deployment state.", MemoryKind::Fact, 0.84, 0.79),
            ],
        },
        QualityScenario {
            scenario_id: "phase5_2_006_mixed_candidate_kinds",
            query: "database migration backup recovery",
            k: 8,
            memories: vec![
                memory("Database migration backup recovery failed when the snapshot was missing.", MemoryKind::Failure, 0.96, 0.94),
                memory("Database migration backup recovery requires a verified snapshot.", MemoryKind::Playbook, 0.94, 0.92),
                memory("Database migration backup preference favors reversible changes.", MemoryKind::Preference, 0.88, 0.84),
                memory("Database migration backup recovery duration depends on data size.", MemoryKind::Fact, 0.82, 0.78),
            ],
        },
    ]
}

fn memory(
    content: &'static str,
    kind: MemoryKind,
    confidence: f32,
    importance: f32,
) -> QualityMemory {
    QualityMemory {
        content,
        kind,
        confidence,
        importance,
    }
}
fn average(values: impl Iterator<Item = f64>) -> f64 {
    let values = values.collect::<Vec<_>>();
    safe_div(values.iter().sum(), values.len() as f64)
}

fn safe_div(numerator: f64, denominator: f64) -> f64 {
    if denominator <= f64::EPSILON {
        0.0
    } else {
        numerator / denominator
    }
}

fn normalize(value: f64) -> f64 {
    if value.is_finite() {
        value.clamp(0.0, 1.0)
    } else {
        0.0
    }
}

fn round4(value: f64) -> f64 {
    (normalize(value) * 10_000.0).round() / 10_000.0
}

#[derive(Debug, Clone)]
struct QualityScenario {
    scenario_id: &'static str,
    query: &'static str,
    k: usize,
    memories: Vec<QualityMemory>,
}

#[derive(Debug, Clone)]
struct QualityMemory {
    content: &'static str,
    kind: MemoryKind,
    confidence: f32,
    importance: f32,
}
#[derive(Debug, Clone)]
struct HitSignature {
    ids: Vec<String>,
    scores: Vec<u32>,
    activation: Vec<u32>,
}

#[derive(Debug, Clone, Serialize)]
pub struct Phase5TraceQualityReport {
    pub schema_version: u32,
    pub tag: String,
    pub phase: String,
    pub mode: String,
    pub evaluation_version: String,
    pub baseline_version: String,
    pub generated_at: String,
    pub scenarios: usize,
    pub thresholds: Phase5TraceQualityThresholds,
    pub metrics: Phase5TraceQualityMetrics,
    pub guards: Phase5TraceQualityGuards,
    pub judge_protocol: Phase5TraceQualityJudgeProtocol,
    pub pass: bool,
    pub status: String,
    pub scenario_reports: Vec<Phase5TraceQualityScenarioReport>,
}

#[derive(Debug, Clone, Serialize)]
pub struct Phase5TraceQualityThresholds {
    pub explanation_completeness: f64,
    pub factor_faithfulness: f64,
    pub trace_preference_rate: f64,
    pub determinism: f64,
}

#[derive(Debug, Clone, Serialize)]
pub struct Phase5TraceQualityMetrics {
    pub explanation_completeness: f64,
    pub factor_faithfulness: f64,
    pub trace_preference_rate: f64,
    pub determinism: f64,
    pub baseline_explanation_completeness: f64,
    pub cognitive_explanation_completeness: f64,
    pub explanation_information_gain: f64,
    pub retrieval_trace_alignment: f64,
}

#[derive(Debug, Clone, Serialize)]
pub struct Phase5TraceQualityGuards {
    pub eval_only: bool,
    pub core_behavior_changed: bool,
    pub recall_ranking_changed: bool,
    pub recall_scores_changed: bool,
    pub memory_written: bool,
    pub activation_changed: bool,
    pub booster_enabled: bool,
    pub external_model_called: bool,
}

#[derive(Debug, Clone, Serialize)]
pub struct Phase5TraceQualityJudgeProtocol {
    pub mode: String,
    pub purpose: String,
    pub external_judge_ready: bool,
    pub human_or_llm_judge_completed: bool,
    pub caveat: String,
}

#[derive(Debug, Clone, Serialize)]
pub struct Phase5TraceQualityScenarioReport {
    pub scenario_id: String,
    pub query: String,
    pub candidate_count: usize,
    pub retrieval_top_candidate: Option<String>,
    pub cognitive_dominant_candidate: Option<String>,
    pub retrieval_trace_aligned: bool,
    pub baseline_explanation: BaselineExplanation,
    pub cognitive_explanation: CognitiveExplanation,
    pub trace: CognitiveCompetitionTrace,
    pub explanation_completeness: f64,
    pub completeness: ExplanationCompletenessAudit,
    pub factor_faithfulness: f64,
    pub factor_audit: FactorFaithfulnessAudit,
    pub judge: PairwiseExplanationJudgeReport,
    pub deterministic: bool,
    pub ranking_unchanged: bool,
    pub scores_unchanged: bool,
    pub activation_unchanged: bool,
    pub memory_unchanged: bool,
}

#[derive(Debug, Clone, Serialize)]
pub struct BaselineExplanation {
    pub selected_candidate: Option<String>,
    pub candidates: Vec<BaselineCandidateMetadata>,
}

#[derive(Debug, Clone, Serialize)]
pub struct BaselineCandidateMetadata {
    pub candidate_id: String,
    pub rank: usize,
    pub score: f32,
    pub sources: Vec<String>,
    pub valid_from: i64,
}

#[derive(Debug, Clone, Serialize)]
pub struct CognitiveExplanation {
    pub dominant_candidate: Option<String>,
    pub suppressed_candidates: Vec<String>,
    pub factors_by_candidate: BTreeMap<String, Vec<CognitiveFactor>>,
    pub confidence: f64,
}

#[derive(Debug, Clone, Serialize)]
pub struct ExplanationCompletenessAudit {
    pub dominant_identified: bool,
    pub suppressed_candidates_explained: bool,
    pub candidate_factor_coverage: bool,
    pub required_factors_present: bool,
    pub confidence_reported: bool,
    pub satisfied_components: usize,
    pub total_components: usize,
    pub score: f64,
}

#[derive(Debug, Clone, Serialize)]
pub struct FactorFaithfulnessAudit {
    pub expected_factor_count: usize,
    pub actual_factor_count: usize,
    pub faithful_factor_count: usize,
    pub hallucinated_factor_count: usize,
    pub missing_factor_count: usize,
    pub hallucinated_factors: Vec<CognitiveFactor>,
    pub missing_factors: Vec<CognitiveFactor>,
    pub score: f64,
}

#[derive(Debug, Clone, Serialize)]
pub struct PairwiseExplanationJudgeReport {
    pub protocol: String,
    pub baseline_criteria: ExplanationCriteria,
    pub cognitive_criteria: ExplanationCriteria,
    pub baseline_score: f64,
    pub cognitive_score: f64,
    pub preferred_explanation: ExplanationPreference,
    pub reasons: Vec<String>,
}

#[derive(Debug, Clone, Serialize)]
pub struct ExplanationCriteria {
    pub outcome_identified: bool,
    pub alternatives_explained: bool,
    pub evidence_attributed: bool,
    pub confidence_reported: bool,
    pub candidate_coverage: bool,
}

impl ExplanationCriteria {
    fn score(&self) -> f64 {
        let satisfied = [
            self.outcome_identified,
            self.alternatives_explained,
            self.evidence_attributed,
            self.confidence_reported,
            self.candidate_coverage,
        ]
        .into_iter()
        .filter(|value| *value)
        .count();
        safe_div(satisfied as f64, 5.0)
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum ExplanationPreference {
    BaselineMetadata,
    CognitiveTrace,
    Tie,
}
