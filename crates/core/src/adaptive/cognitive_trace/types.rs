use serde::{Deserialize, Serialize};

/// Inspection-only cognitive competition trace over already-retrieved recall hits.
///
/// This report is explanatory. Its scores must not be fed back into recall
/// ranking, activation, storage, or mutation paths.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct CognitiveCompetitionTrace {
    pub query: String,
    pub candidate_count: usize,
    pub dominant_candidate: Option<String>,
    pub suppressed_candidates: Vec<String>,
    pub factors: Vec<CognitiveFactor>,
    pub confidence: f64,
    pub mutated: bool,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct CognitiveFactor {
    #[serde(rename = "candidate")]
    pub candidate_id: String,
    #[serde(rename = "factor")]
    pub factor_type: CognitiveFactorType,
    pub contribution: f64,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "PascalCase")]
pub enum CognitiveFactorType {
    SemanticMatch,
    TemporalConfidence,
    Reliability,
    PreferenceAlignment,
    FailureEvidence,
    ContextAlignment,
}
