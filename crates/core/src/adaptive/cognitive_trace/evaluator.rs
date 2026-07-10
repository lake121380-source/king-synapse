use super::types::{CognitiveCompetitionTrace, CognitiveFactor, CognitiveFactorType};
use crate::{MemoryKind, RecallHit};
use std::cmp::Ordering;

const SCORE_EPSILON: f64 = 0.000_001;

#[derive(Debug, Clone, Copy, Default)]
pub struct CognitiveTraceEvaluator;

impl CognitiveTraceEvaluator {
    pub fn evaluate(query: impl AsRef<str>, hits: &[RecallHit]) -> CognitiveCompetitionTrace {
        Self::default().trace(query, hits)
    }

    pub fn trace(&self, query: impl AsRef<str>, hits: &[RecallHit]) -> CognitiveCompetitionTrace {
        let query = query.as_ref().to_string();
        if hits.is_empty() {
            return CognitiveCompetitionTrace {
                query,
                candidate_count: 0,
                dominant_candidate: None,
                suppressed_candidates: Vec::new(),
                factors: Vec::new(),
                confidence: 0.0,
                mutated: false,
            };
        }

        let max_score = hits
            .iter()
            .map(|hit| hit.score as f64)
            .filter(|score| score.is_finite())
            .fold(0.0, f64::max)
            .max(SCORE_EPSILON);
        let mut scored = hits
            .iter()
            .enumerate()
            .map(|(position, hit)| score_hit(&query, hit, max_score, position))
            .collect::<Vec<_>>();
        scored.sort_by(compare_scored_candidates);

        let dominant_candidate = scored
            .first()
            .map(|candidate| candidate.candidate_id.clone());
        let suppressed_candidates = scored
            .iter()
            .skip(1)
            .map(|candidate| candidate.candidate_id.clone())
            .collect::<Vec<_>>();
        let confidence = trace_confidence(&scored);
        let factors = scored
            .iter()
            .flat_map(|candidate| candidate.factors.clone())
            .collect::<Vec<_>>();

        CognitiveCompetitionTrace {
            query,
            candidate_count: hits.len(),
            dominant_candidate,
            suppressed_candidates,
            factors,
            confidence,
            mutated: false,
        }
    }
}

#[derive(Debug, Clone)]
struct ScoredCandidate {
    candidate_id: String,
    total: f64,
    original_position: usize,
    factors: Vec<CognitiveFactor>,
}

fn score_hit(
    query: &str,
    hit: &RecallHit,
    max_score: f64,
    original_position: usize,
) -> ScoredCandidate {
    let candidate_id = hit.memory.id.clone();
    let semantic = normalize(hit.score as f64 / max_score) * 0.35;
    let temporal = temporal_confidence(hit) * 0.15;
    let reliability = normalize(hit.memory.confidence as f64) * 0.20;
    let overlap = lexical_overlap(query, &hit.memory.content);
    let context_alignment = overlap * 0.15;
    let preference_alignment = if hit.memory.kind == MemoryKind::Preference {
        (0.50 + overlap * 0.50) * 0.10
    } else {
        0.0
    };
    let failure_evidence = if hit.memory.kind == MemoryKind::Failure {
        (0.50 + overlap * 0.50) * 0.15
    } else {
        0.0
    };

    let mut factors = vec![
        factor(&candidate_id, CognitiveFactorType::SemanticMatch, semantic),
        factor(
            &candidate_id,
            CognitiveFactorType::TemporalConfidence,
            temporal,
        ),
        factor(&candidate_id, CognitiveFactorType::Reliability, reliability),
        factor(
            &candidate_id,
            CognitiveFactorType::ContextAlignment,
            context_alignment,
        ),
    ];
    if preference_alignment > 0.0 {
        factors.push(factor(
            &candidate_id,
            CognitiveFactorType::PreferenceAlignment,
            preference_alignment,
        ));
    }
    if failure_evidence > 0.0 {
        factors.push(factor(
            &candidate_id,
            CognitiveFactorType::FailureEvidence,
            failure_evidence,
        ));
    }

    let total = factors
        .iter()
        .map(|factor| factor.contribution)
        .sum::<f64>();
    ScoredCandidate {
        candidate_id,
        total,
        original_position,
        factors,
    }
}

fn factor(
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
    let mut out = input
        .split(|ch: char| !ch.is_alphanumeric())
        .map(|term| term.trim().to_ascii_lowercase())
        .filter(|term| term.len() >= 3)
        .collect::<Vec<_>>();
    out.sort();
    out.dedup();
    out
}

fn compare_scored_candidates(left: &ScoredCandidate, right: &ScoredCandidate) -> Ordering {
    let score_order = right
        .total
        .partial_cmp(&left.total)
        .unwrap_or(Ordering::Equal);
    if (left.total - right.total).abs() > SCORE_EPSILON {
        return score_order;
    }
    left.original_position
        .cmp(&right.original_position)
        .then_with(|| left.candidate_id.cmp(&right.candidate_id))
}

fn trace_confidence(scored: &[ScoredCandidate]) -> f64 {
    let confidence = match scored {
        [] => 0.0,
        [only] => normalize(only.total),
        [first, second, ..] => {
            if first.total <= SCORE_EPSILON {
                0.0
            } else {
                normalize((first.total - second.total).max(0.0) / first.total)
            }
        }
    };
    round4(confidence)
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
