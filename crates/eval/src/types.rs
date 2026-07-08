use serde::{Deserialize, Serialize};
use std::path::PathBuf;
use synapse_core::{RecallProfile, RrfBranchWeights, SemanticEdgeMode};

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum SemanticJudgeKind {
    Heuristic,
    #[serde(rename = "deepseek")]
    DeepSeek,
}

impl Default for SemanticJudgeKind {
    fn default() -> Self {
        Self::Heuristic
    }
}

#[derive(Debug, Deserialize)]
pub struct Dataset {
    pub memories: Vec<MemorySpec>,
    #[serde(default)]
    pub queries: Vec<QuerySpec>,
}

#[derive(Debug, Deserialize)]
pub struct MemorySpec {
    pub key: String,
    pub kind: String,
    pub scope: String,
    pub content: String,
    #[serde(default)]
    pub importance: Option<f32>,
    #[serde(default)]
    pub confidence: Option<f32>,
}

#[derive(Debug, Deserialize)]
pub struct QuerySpec {
    pub query: String,
    pub relevant: Vec<String>,
}

#[derive(Debug, Serialize)]
pub struct QueryResult {
    pub query: String,
    pub relevant: Vec<String>,
    pub returned: Vec<String>,
    pub returned_hit_diagnostics: Vec<ReturnedHitDiagnostic>,
    pub recall_at_5: f64,
    pub recall_at_10: f64,
    pub rr: f64,
    pub ndcg_at_10: f64,
    pub latency_ms: f64,
    pub profile: RecallProfile,
}

#[derive(Debug, Serialize)]
pub struct ReturnedHitDiagnostic {
    pub key: String,
    pub rank: usize,
    pub score: f32,
    pub rrf_score: f32,
    pub rerank_score: Option<f32>,
    pub activation_bonus: f32,
    pub fts_rank: Option<u32>,
    pub entity_rank: Option<u32>,
    pub vector_rank: Option<u32>,
    pub entity_hits: u32,
    pub sources: Vec<String>,
}

#[derive(Debug, Serialize)]
pub struct SemanticAuditSample {
    pub decision: String,
    pub query: String,
    pub source_key: String,
    pub target_key: String,
    pub source_content: String,
    pub target_content: String,
    pub edge_relation: String,
    pub judged_relation: Option<String>,
    pub confidence: f32,
    pub reason_category: String,
    pub reason: String,
}

#[derive(Debug, Serialize)]
pub struct Report {
    pub tag: String,
    pub dataset: String,
    pub vectors_enabled: bool,
    pub rerank_enabled: bool,
    pub rerank_pool: usize,
    pub rrf_k: f64,
    pub rrf_weights: RrfBranchWeights,
    pub graph_activation: bool,
    pub edge_count: usize,
    pub hypothesis_generation: bool,
    pub hypothesis_graduation: bool,
    pub semantic_edge_mode: SemanticEdgeMode,
    pub semantic_judge: SemanticJudgeKind,
    pub semantic_judge_cache_path: Option<String>,
    pub semantic_cache_hits: usize,
    pub semantic_cache_misses: usize,
    pub semantic_cache_writes: usize,
    pub semantic_audit_samples: Vec<SemanticAuditSample>,
    pub semantic_survival: Option<SemanticSurvivalReport>,
    pub hypothesis_metrics: Option<HypothesisMetrics>,
    pub k: usize,
    pub n_memories: usize,
    pub n_queries: usize,
    pub recall_at_5: f64,
    pub recall_at_10: f64,
    pub mrr_at_10: f64,
    pub ndcg_at_10: f64,
    pub p50_latency_ms: f64,
    pub p95_latency_ms: f64,
    pub total_ms: f64,
    pub timing: TimingReport,
    pub per_query: Vec<QueryResult>,
}

#[derive(Debug, Default, Serialize)]
pub struct TimingReport {
    pub dataset_load_ms: f64,
    pub store_write_ms: f64,
    pub embedder_load_ms: Option<f64>,
    pub corpus_embedding_ms: Option<f64>,
    pub embedding_write_ms: Option<f64>,
    pub reranker_load_ms: Option<f64>,
    pub query_wall_ms: f64,
    pub recall_profile_totals: RecallProfile,
    pub recall_profile_mean_ms: RecallProfileMeanMs,
}

#[derive(Debug, Default, Serialize)]
pub struct RecallProfileMeanMs {
    pub total_ms: f64,
    pub fts_ms: f64,
    pub entity_ms: f64,
    pub query_embedding_ms: f64,
    pub vector_search_ms: f64,
    pub memory_hydration_ms: f64,
    pub rrf_fusion_ms: f64,
    pub hit_build_ms: f64,
    pub reranker_ms: f64,
    pub booster_ms: f64,
    pub final_score_ms: f64,
    pub record_access_ms: f64,
}

pub struct BenchOptions {
    pub dataset_path: PathBuf,
    pub k: usize,
    pub vectors: bool,
    pub rerank: bool,
    pub rerank_pool: usize,
    pub rrf_k: f64,
    pub rrf_weights: RrfBranchWeights,
    pub tag: String,
    pub graph_activation: bool,
    /// Enable edge hypothesis generation after each retrieval.
    pub hypothesis_generation: bool,
    /// Graduate confirmed hypotheses to memory_edges periodically.
    pub hypothesis_graduation: bool,
    /// Optional Phase 1c semantic judge mode over rule-generated candidates.
    pub semantic_edge_mode: SemanticEdgeMode,
    /// Judge implementation used when semantic_edge_mode is not off.
    pub semantic_judge: SemanticJudgeKind,
    /// Optional persistent semantic judge cache path. Only used by model-backed judges.
    pub semantic_judge_cache_path: Option<PathBuf>,
}

#[derive(Debug, Clone, Serialize)]
pub struct SemanticEdgeLifecycleRecord {
    pub edge_id: String,
    pub source_id: String,
    pub target_id: String,
    pub source_key: String,
    pub target_key: String,
    pub relation: String,
    pub judge_confidence: f32,
    pub reason_category: String,
    pub reason: String,
    pub created_at: i64,
    pub accepted_at_query: usize,
    pub accepted_context: String,
    pub observation_count: usize,
    pub distinct_context_count: usize,
    pub hypothesis_confidence: f32,
    pub hypothesis_status: String,
    pub confirmed: bool,
    pub graduated: bool,
    pub graduation_step: Option<usize>,
    pub activation_hits: usize,
    pub activation_bonus_mean: f32,
    pub utility_queries: usize,
    pub useful_queries: usize,
    pub harmful_queries: usize,
    pub neutral_queries: usize,
    pub mean_rank_delta: f64,
    pub mean_mrr_delta: f64,
    pub correct_rank_improvements: usize,
    pub wrong_rank_promotions: usize,
    pub attribution_queries: usize,
    pub causal_useful_queries: usize,
    pub causal_harmful_queries: usize,
    pub causal_neutral_queries: usize,
    pub mean_causal_rank_delta: f64,
    pub mean_causal_mrr_delta: f64,
    pub causal_mrr_delta_variance: f64,
    pub causal_consistency: f64,
    pub useful_ratio: f64,
    pub harmful_ratio: f64,
    pub governance_state: String,
    pub governance_weight: f32,
    pub rank_delta: Option<f64>,
}

#[derive(Debug, Clone, Serialize)]
pub struct SemanticConfidenceBucket {
    pub bucket: String,
    pub accepted_edges: usize,
    pub confirmed_edges: usize,
    pub graduated_edges: usize,
    pub activated_edges: usize,
    pub confirmation_rate: f64,
    pub graduation_rate: f64,
    pub activation_rate: f64,
}

#[derive(Debug, Clone, Serialize)]
pub struct SemanticSurvivalReport {
    pub candidate_count: usize,
    pub semantic_accepted_count: usize,
    pub semantic_rejected_count: usize,
    pub unique_accepted_edges: usize,
    pub confirmed_count: usize,
    pub graduated_count: usize,
    pub activated_count: usize,
    pub utility: SemanticUtilityReport,
    pub governance: SemanticGovernanceReport,
    pub policy_search: SemanticPolicySearchReport,
    pub confidence_buckets: Vec<SemanticConfidenceBucket>,
    pub records: Vec<SemanticEdgeLifecycleRecord>,
}

#[derive(Debug, Clone, Serialize)]
pub struct SemanticPolicySearchReport {
    pub evaluated_queries: usize,
    pub best_policy_by_mrr: Option<String>,
    pub policies: Vec<SemanticPolicyEvaluation>,
}

#[derive(Debug, Clone, Serialize)]
pub struct SemanticPolicyEvaluation {
    pub name: String,
    pub description: String,
    pub evaluated_queries: usize,
    pub changed_queries: usize,
    pub improved_queries: usize,
    pub harmed_queries: usize,
    pub neutral_queries: usize,
    pub mean_rank_delta_vs_full_graph: f64,
    pub mean_mrr_delta_vs_full_graph: f64,
    pub mean_edge_weight: f64,
}

#[derive(Debug, Clone, Serialize)]
pub struct SemanticGovernanceReport {
    pub candidate_edges: usize,
    pub graduated_edges: usize,
    pub trusted_edges: usize,
    pub suspect_edges: usize,
    pub dormant_edges: usize,
    pub mean_governance_weight: f64,
    pub evaluated_queries: usize,
    pub changed_queries: usize,
    pub mean_rank_delta_vs_full_graph: f64,
    pub mean_mrr_delta_vs_full_graph: f64,
}

#[derive(Debug, Clone, Serialize)]
pub struct SemanticUtilityReport {
    pub evaluated_queries: usize,
    pub affected_queries: usize,
    pub utility_events: usize,
    pub affected_edges: usize,
    pub useful_edges: usize,
    pub harmful_edges: usize,
    pub neutral_edges: usize,
    pub mean_rank_delta: f64,
    pub mean_mrr_delta: f64,
    pub correct_rank_improvements: usize,
    pub wrong_rank_promotions: usize,
    pub attribution_evaluated_edges: usize,
    pub attribution_affected_edges: usize,
    pub causal_useful_edges: usize,
    pub causal_harmful_edges: usize,
    pub causal_neutral_edges: usize,
    pub mean_causal_rank_delta: f64,
    pub mean_causal_mrr_delta: f64,
}

#[derive(Debug, Clone, Serialize)]
pub struct GovernanceEvaluationReport {
    pub tag: String,
    pub dataset: String,
    pub n_memories: usize,
    pub n_queries: usize,
    pub semantic_judge: SemanticJudgeKind,
    pub semantic_edge_mode: SemanticEdgeMode,
    pub detection_score: f64,
    pub intervention_gain: f64,
    pub regression_rate: f64,
    pub stability_score: f64,
    pub suspect_detection: GovernanceDetectionReport,
    pub intervention_safety: GovernanceInterventionSafetyReport,
    pub temporal_stability: GovernanceTemporalStabilityReport,
    pub policy_search: SemanticPolicySearchReport,
    pub rollback: GovernanceRollbackReport,
    pub source_trace: GovernanceSourceTraceReport,
}

#[derive(Debug, Clone, Serialize)]
pub struct GovernanceDetectionReport {
    pub evaluated_edges: usize,
    pub predicted_suspect_edges: usize,
    pub ground_truth_harmful_edges: usize,
    pub true_positive: usize,
    pub false_positive: usize,
    pub true_negative: usize,
    pub false_negative: usize,
    pub precision: f64,
    pub recall: f64,
    pub f1: f64,
    pub accuracy: f64,
    pub method: String,
}

#[derive(Debug, Clone, Serialize)]
pub struct GovernanceInterventionSafetyReport {
    pub evaluated_queries: usize,
    pub changed_queries: usize,
    pub improved_queries: usize,
    pub harmed_queries: usize,
    pub neutral_queries: usize,
    pub intervention_gain: f64,
    pub regression_rate: f64,
    pub safety_passed: bool,
    pub method: String,
}

#[derive(Debug, Clone, Serialize)]
pub struct GovernanceTemporalStabilityReport {
    pub evaluated_edges: usize,
    pub stable_edges: usize,
    pub unstable_edges: usize,
    pub mean_causal_consistency: f64,
    pub mean_causal_mrr_delta_variance: f64,
    pub stability_score: f64,
    pub method: String,
}

#[derive(Debug, Clone, Serialize)]
pub struct GovernanceRollbackReport {
    pub rollback_model: String,
    pub persistent_edge_mutations: usize,
    pub default_recall_behavior_changed: bool,
    pub edge_deletions: usize,
}

#[derive(Debug, Clone, Serialize)]
pub struct GovernanceSourceTraceReport {
    pub recall_at_10: f64,
    pub mrr_at_10: f64,
    pub candidate_edges: usize,
    pub graduated_edges: usize,
    pub activated_edges: usize,
    pub suspect_edges: usize,
    pub trusted_edges: usize,
    pub dormant_edges: usize,
    pub attribution_evaluated_edges: usize,
    pub policy_count: usize,
}

#[derive(Debug, Clone, Serialize)]
pub struct GovernanceBiasEvaluationReport {
    pub tag: String,
    pub dataset: String,
    pub case_count: usize,
    pub edge_count: usize,
    pub harmful_edge_count: usize,
    pub normal_edge_count: usize,
    pub harmful_edge_detection_rate: f64,
    pub suppression_gain: f64,
    pub over_suppression_rate: f64,
    pub normal_recall_preservation: f64,
    pub recovery_score: f64,
    pub pass: bool,
    pub thresholds: GovernanceBiasThresholds,
    pub rollback: GovernanceRollbackReport,
    pub cases: Vec<GovernanceBiasCaseReport>,
}

#[derive(Debug, Clone, Serialize)]
pub struct GovernanceBiasThresholds {
    pub detection_min: f64,
    pub normal_recall_preservation_min: f64,
    pub over_suppression_max: f64,
    pub recovery_min: f64,
}

#[derive(Debug, Clone, Serialize)]
pub struct GovernanceBiasCaseReport {
    pub id: String,
    pub issue: String,
    pub severity: f64,
    pub harmful_edges: usize,
    pub detected_harmful_edges: usize,
    pub false_suppressed_normal_edges: usize,
    pub suppression_gain: f64,
    pub recovery_score: f64,
    pub normal_recall_preservation: f64,
    pub edges: Vec<GovernanceBiasEdgeReport>,
}

#[derive(Debug, Clone, Serialize)]
pub struct GovernanceBiasEdgeReport {
    pub id: String,
    pub source: String,
    pub target: String,
    pub label: String,
    pub expected_issue: String,
    pub risk_score: f64,
    pub detected_harmful: bool,
    pub baseline_influence: f64,
    pub governed_influence: f64,
    pub suppression_gain: f64,
    pub recovered_confidence: Option<f64>,
    pub recovery_score: Option<f64>,
}

#[derive(Debug, Clone, Serialize)]
pub struct GovernanceStressEvaluationReport {
    pub tag: String,
    pub dataset: String,
    pub case_count: usize,
    pub edge_count: usize,
    pub harmful_edge_count: usize,
    pub valid_edge_count: usize,
    pub ambiguous_edge_count: usize,
    pub longitudinal_edge_count: usize,
    pub harmful_detection_rate: f64,
    pub false_positive_rate: f64,
    pub ambiguous_calibration_score: f64,
    pub longitudinal_recovery_score: f64,
    pub normal_recall_preservation: f64,
    pub over_suppression_rate: f64,
    pub pass: bool,
    pub thresholds: GovernanceStressThresholds,
    pub rollback: GovernanceRollbackReport,
    pub cases: Vec<GovernanceStressCaseReport>,
}

#[derive(Debug, Clone, Serialize)]
pub struct GovernanceStressThresholds {
    pub harmful_detection_min: f64,
    pub false_positive_max: f64,
    pub ambiguous_calibration_min: f64,
    pub longitudinal_recovery_min: f64,
    pub normal_recall_preservation_min: f64,
    pub over_suppression_max: f64,
}

#[derive(Debug, Clone, Serialize)]
pub struct GovernanceStressCaseReport {
    pub id: String,
    pub case_type: String,
    pub issue: String,
    pub edges: Vec<GovernanceStressEdgeReport>,
}

#[derive(Debug, Clone, Serialize)]
pub struct GovernanceStressEdgeReport {
    pub id: String,
    pub source: String,
    pub target: String,
    pub label: String,
    pub expected_action: String,
    pub risk_score: f64,
    pub uncertainty_score: f64,
    pub detected_harmful: bool,
    pub false_positive: bool,
    pub baseline_influence: f64,
    pub governed_influence: f64,
    pub suppression_gain: f64,
    pub normal_preservation: Option<f64>,
    pub calibration_score: Option<f64>,
    pub longitudinal_recovery_score: Option<f64>,
    pub confidence_path: Vec<f64>,
}

#[derive(Debug, Clone, Serialize)]
pub struct GovernanceCalibrationSweepReport {
    pub tag: String,
    pub dataset: String,
    pub candidate_count: usize,
    pub baseline: GovernanceCalibrationCandidateReport,
    pub best_candidate: Option<GovernanceCalibrationCandidateReport>,
    pub pareto_frontier: Vec<GovernanceCalibrationCandidateReport>,
    pub thresholds: GovernanceCalibrationThresholds,
    pub rollback: GovernanceRollbackReport,
}

#[derive(Debug, Clone, Serialize)]
pub struct GovernanceCalibrationThresholds {
    pub harmful_detection_min: f64,
    pub false_positive_max: f64,
    pub normal_recall_preservation_min: f64,
    pub over_suppression_max: f64,
}

#[derive(Debug, Clone, Serialize)]
pub struct GovernanceCalibrationCandidateReport {
    pub name: String,
    pub harmful_threshold: f64,
    pub scope_weight: f64,
    pub evidence_gap_weight: f64,
    pub sample_support_weight: f64,
    pub harmful_detection_rate: f64,
    pub false_positive_rate: f64,
    pub normal_recall_preservation: f64,
    pub over_suppression_rate: f64,
    pub ambiguous_calibration_score: f64,
    pub longitudinal_recovery_score: f64,
    pub pass: bool,
    pub objective_score: f64,
    pub missed_harmful_edges: Vec<String>,
    pub false_positive_edges: Vec<String>,
}

#[derive(Debug, Clone, Serialize)]
pub struct GovernanceConfidenceEvaluationReport {
    pub tag: String,
    pub dataset: String,
    pub detector_count: usize,
    pub observation_count: usize,
    pub mean_initial_reliability: f64,
    pub mean_final_reliability: f64,
    pub reliability_improvement: f64,
    pub mean_calibration_error: f64,
    pub calibration_improvement: f64,
    pub mean_confidence_drift: f64,
    pub governance_stability_score: f64,
    pub pass: bool,
    pub thresholds: GovernanceConfidenceThresholds,
    pub rollback: GovernanceRollbackReport,
    pub detectors: Vec<DetectorConfidenceRecord>,
    pub observations: Vec<DetectorConfidenceObservationReport>,
}

#[derive(Debug, Clone, Serialize)]
pub struct GovernanceConfidenceThresholds {
    pub reliability_improvement_min: f64,
    pub calibration_improvement_min: f64,
    pub governance_stability_min: f64,
}

#[derive(Debug, Clone, Serialize)]
pub struct DetectorConfidenceRecord {
    pub detector: String,
    pub predictions: usize,
    pub true_positive: usize,
    pub true_negative: usize,
    pub false_positive: usize,
    pub false_negative: usize,
    pub initial_reliability: f64,
    pub reliability_score: f64,
    pub confidence_delta: f64,
    pub raw_calibration_error: f64,
    pub calibrated_calibration_error: f64,
    pub calibration_improvement: f64,
    pub confidence_drift: f64,
    pub stability_score: f64,
}

#[derive(Debug, Clone, Serialize)]
pub struct DetectorConfidenceObservationReport {
    pub id: String,
    pub detector: String,
    pub risk_score: f64,
    pub calibrated_score: f64,
    pub predicted_harmful: bool,
    pub expected_harmful: bool,
    pub correct: bool,
}

#[derive(Debug, Clone, Serialize)]
pub struct GovernanceAggregationEvaluationReport {
    pub tag: String,
    pub dataset: String,
    pub detector_count: usize,
    pub observation_count: usize,
    pub best_method: String,
    pub raw: GovernanceAggregationMethodReport,
    pub reliability_scaled: GovernanceAggregationMethodReport,
    pub empirical_calibrated: GovernanceAggregationMethodReport,
    pub pass: bool,
    pub thresholds: GovernanceAggregationThresholds,
    pub rollback: GovernanceRollbackReport,
    pub detectors: Vec<GovernanceAggregationDetectorReport>,
}

#[derive(Debug, Clone, Serialize)]
pub struct GovernanceAggregationThresholds {
    pub calibration_error_max: f64,
    pub ranking_auc_min: f64,
    pub stability_min: f64,
}

#[derive(Debug, Clone, Serialize)]
pub struct GovernanceAggregationMethodReport {
    pub method: String,
    pub calibration_error: f64,
    pub calibration_error_delta_vs_raw: f64,
    pub ranking_auc: f64,
    pub stability_score: f64,
}

#[derive(Debug, Clone, Serialize)]
pub struct GovernanceAggregationDetectorReport {
    pub detector: String,
    pub reliability: f64,
    pub raw_calibration_error: f64,
    pub reliability_scaled_error: f64,
    pub empirical_calibrated_error: f64,
    pub empirical_positive_rate: f64,
    pub observations: usize,
}

#[derive(Debug, Clone, Serialize)]
pub struct GovernanceReplayEvaluationReport {
    pub tag: String,
    pub dataset: String,
    pub feedback_dataset: String,
    pub detector_count: usize,
    pub case_count: usize,
    pub event_count: usize,
    pub baseline_accuracy: f64,
    pub governed_accuracy: f64,
    pub counterfactual_gain: f64,
    pub baseline_regret: f64,
    pub governed_regret: f64,
    pub regret_reduction: f64,
    pub regret_reduction_rate: f64,
    pub normal_preservation: f64,
    pub over_conservatism_rate: f64,
    pub stability_score: f64,
    pub pass: bool,
    pub thresholds: GovernanceReplayThresholds,
    pub rollback: GovernanceRollbackReport,
    pub detectors: Vec<GovernanceReplayDetectorReport>,
    pub cases: Vec<GovernanceReplayCaseReport>,
}

#[derive(Debug, Clone, Serialize)]
pub struct GovernanceReplayThresholds {
    pub counterfactual_gain_min: f64,
    pub regret_reduction_min: f64,
    pub normal_preservation_min: f64,
    pub over_conservatism_max: f64,
    pub stability_min: f64,
}

#[derive(Debug, Clone, Serialize)]
pub struct GovernanceReplayDetectorReport {
    pub detector: String,
    pub reliability: f64,
    pub precision_when_flagged: f64,
    pub harmful_rate_when_safe: f64,
    pub positive_rate: f64,
    pub observations: usize,
}

#[derive(Debug, Clone, Serialize)]
pub struct GovernanceReplayCaseReport {
    pub id: String,
    pub detector: String,
    pub expected_harmful: bool,
    pub raw_risk: f64,
    pub calibrated_risk: f64,
    pub baseline_influence: f64,
    pub governed_influence: f64,
    pub suppression_strength: f64,
    pub baseline_accuracy: f64,
    pub governed_accuracy: f64,
    pub counterfactual_gain: f64,
    pub baseline_regret: f64,
    pub governed_regret: f64,
    pub regret_reduction: f64,
    pub over_conservative_events: usize,
    pub events: Vec<GovernanceReplayEventReport>,
}

#[derive(Debug, Clone, Serialize)]
pub struct GovernanceReplayEventReport {
    pub id: String,
    pub desired_influence: f64,
    pub impact_weight: f64,
    pub baseline_prediction: bool,
    pub governed_prediction: bool,
    pub expected_prediction: bool,
    pub baseline_correct: bool,
    pub governed_correct: bool,
    pub baseline_regret: f64,
    pub governed_regret: f64,
    pub regret_delta: f64,
}

#[derive(Debug, Clone, Serialize)]
pub struct GovernanceDriftEvaluationReport {
    pub tag: String,
    pub dataset: String,
    pub scenario_count: usize,
    pub step_count: usize,
    pub harmful_scenarios: usize,
    pub weak_bias_detection_rate: f64,
    pub drift_mitigation_gain: f64,
    pub recovery_score: f64,
    pub pattern_memory_gain: f64,
    pub normal_preservation: f64,
    pub over_correction_rate: f64,
    pub stability_score: f64,
    pub pass: bool,
    pub thresholds: GovernanceDriftThresholds,
    pub rollback: GovernanceRollbackReport,
    pub patterns: Vec<GovernanceDriftPatternReport>,
    pub scenarios: Vec<GovernanceDriftScenarioReport>,
}

#[derive(Debug, Clone, Serialize)]
pub struct GovernanceDriftThresholds {
    pub weak_bias_detection_min: f64,
    pub drift_mitigation_gain_min: f64,
    pub recovery_score_min: f64,
    pub pattern_memory_gain_min: f64,
    pub normal_preservation_min: f64,
    pub over_correction_max: f64,
    pub stability_min: f64,
}

#[derive(Debug, Clone, Serialize)]
pub struct GovernanceDriftPatternReport {
    pub pattern: String,
    pub observations: usize,
    pub harmful_observations: usize,
    pub final_pattern_risk: f64,
}

#[derive(Debug, Clone, Serialize)]
pub struct GovernanceDriftScenarioReport {
    pub id: String,
    pub pattern: String,
    pub scenario_type: String,
    pub expected_harmful: bool,
    pub initial_influence: f64,
    pub baseline_final_influence: f64,
    pub governed_final_influence: f64,
    pub no_pattern_final_influence: f64,
    pub max_baseline_influence: f64,
    pub max_governed_influence: f64,
    pub drift_detected_step: Option<usize>,
    pub baseline_dominance_step: Option<usize>,
    pub governed_dominance_step: Option<usize>,
    pub baseline_regret: f64,
    pub governed_regret: f64,
    pub no_pattern_regret: f64,
    pub regret_reduction: f64,
    pub pattern_memory_gain: f64,
    pub recovery_score: Option<f64>,
    pub over_correction_events: usize,
    pub steps: Vec<GovernanceDriftStepReport>,
}

#[derive(Debug, Clone, Serialize)]
pub struct GovernanceDriftStepReport {
    pub index: usize,
    pub event: String,
    pub desired_influence: f64,
    pub evidence_delta: f64,
    pub risk_signal: f64,
    pub counter_evidence: f64,
    pub local_risk: f64,
    pub pattern_prior: f64,
    pub governance_pressure: f64,
    pub baseline_influence: f64,
    pub no_pattern_influence: f64,
    pub governed_influence: f64,
    pub baseline_regret: f64,
    pub no_pattern_regret: f64,
    pub governed_regret: f64,
}

#[derive(Debug, Clone, Serialize)]
pub struct GovernanceRecoveryEvaluationReport {
    pub tag: String,
    pub dataset: String,
    pub scenario_count: usize,
    pub step_count: usize,
    pub recovery_scenarios: usize,
    pub recovery_success_rate: f64,
    pub target_recovery_rate: f64,
    pub recovery_score: f64,
    pub recovery_gain: f64,
    pub latency_improvement: f64,
    pub dominant_shift_rate: f64,
    pub relapse_rate: f64,
    pub normal_preservation: f64,
    pub over_correction_rate: f64,
    pub stability_score: f64,
    pub pass: bool,
    pub thresholds: GovernanceRecoveryThresholds,
    pub rollback: GovernanceRollbackReport,
    pub scenarios: Vec<GovernanceRecoveryScenarioReport>,
}

#[derive(Debug, Clone, Serialize)]
pub struct GovernanceRecoveryThresholds {
    pub recovery_success_min: f64,
    pub recovery_score_min: f64,
    pub recovery_gain_min: f64,
    pub latency_improvement_min: f64,
    pub dominant_shift_min: f64,
    pub relapse_max: f64,
    pub normal_preservation_min: f64,
    pub over_correction_max: f64,
    pub stability_min: f64,
}

#[derive(Debug, Clone, Serialize)]
pub struct GovernanceRecoveryScenarioReport {
    pub id: String,
    pub pattern: String,
    pub scenario_type: String,
    pub expected_recovery: bool,
    pub initial_misbelief_influence: f64,
    pub initial_adaptive_influence: f64,
    pub target_misbelief_influence: f64,
    pub target_adaptive_influence: f64,
    pub baseline_final_misbelief: f64,
    pub governed_final_misbelief: f64,
    pub baseline_final_adaptive: f64,
    pub governed_final_adaptive: f64,
    pub baseline_recovery_step: Option<usize>,
    pub governed_recovery_step: Option<usize>,
    pub baseline_dominant_shift_step: Option<usize>,
    pub governed_dominant_shift_step: Option<usize>,
    pub recovery_success: bool,
    pub relapsed: bool,
    pub baseline_regret: f64,
    pub governed_regret: f64,
    pub recovery_gain: f64,
    pub recovery_score: f64,
    pub latency_gain: f64,
    pub over_correction_events: usize,
    pub steps: Vec<GovernanceRecoveryStepReport>,
}

#[derive(Debug, Clone, Serialize)]
pub struct GovernanceRecoveryStepReport {
    pub index: usize,
    pub event: String,
    pub counter_evidence: f64,
    pub adaptive_evidence: f64,
    pub relapse_pressure: f64,
    pub recovery_signal: f64,
    pub recovery_pressure: f64,
    pub desired_misbelief_influence: f64,
    pub desired_adaptive_influence: f64,
    pub baseline_misbelief_influence: f64,
    pub governed_misbelief_influence: f64,
    pub baseline_adaptive_influence: f64,
    pub governed_adaptive_influence: f64,
    pub baseline_dominant: String,
    pub governed_dominant: String,
    pub baseline_regret: f64,
    pub governed_regret: f64,
}

#[derive(Debug, Clone, Serialize)]
pub struct GovernanceCompetitionEvaluationReport {
    pub tag: String,
    pub dataset: String,
    pub scenario_count: usize,
    pub step_count: usize,
    pub baseline_competition_score: f64,
    pub governed_competition_score: f64,
    pub competition_gain: f64,
    pub dominant_transition_accuracy: f64,
    pub evidence_response_gain: f64,
    pub influence_balance_stability: f64,
    pub suppression_precision: f64,
    pub over_suppression_rate: f64,
    pub normal_preservation: f64,
    pub pass: bool,
    pub thresholds: GovernanceCompetitionThresholds,
    pub rollback: GovernanceRollbackReport,
    pub scenarios: Vec<GovernanceCompetitionScenarioReport>,
}

#[derive(Debug, Clone, Serialize)]
pub struct GovernanceCompetitionThresholds {
    pub governed_competition_score_min: f64,
    pub competition_gain_min: f64,
    pub dominant_transition_accuracy_min: f64,
    pub evidence_response_gain_min: f64,
    pub influence_balance_stability_min: f64,
    pub suppression_precision_min: f64,
    pub over_suppression_max: f64,
    pub normal_preservation_min: f64,
}

#[derive(Debug, Clone, Serialize)]
pub struct GovernanceCompetitionScenarioReport {
    pub id: String,
    pub scenario_type: String,
    pub influence_count: usize,
    pub step_count: usize,
    pub baseline_correct_steps: usize,
    pub governed_correct_steps: usize,
    pub baseline_competition_score: f64,
    pub governed_competition_score: f64,
    pub dominant_transition_accuracy: f64,
    pub evidence_response_gain: f64,
    pub influence_balance_stability: f64,
    pub suppression_precision: f64,
    pub over_suppression_rate: f64,
    pub normal_preservation: f64,
    pub steps: Vec<GovernanceCompetitionStepReport>,
}

#[derive(Debug, Clone, Serialize)]
pub struct GovernanceCompetitionStepReport {
    pub index: usize,
    pub event: String,
    pub expected_dominant: String,
    pub baseline_dominant: String,
    pub governed_dominant: String,
    pub baseline_correct: bool,
    pub governed_correct: bool,
    pub baseline_expected_margin: f64,
    pub governed_expected_margin: f64,
    pub evidence_response_gain: f64,
    pub influences: Vec<GovernanceCompetitionInfluenceReport>,
    pub suppressions: Vec<GovernanceCompetitionSuppressionReport>,
}

#[derive(Debug, Clone, Serialize)]
pub struct GovernanceCompetitionInfluenceReport {
    pub id: String,
    pub label: String,
    pub harmful: bool,
    pub baseline_strength: f64,
    pub governed_strength: f64,
}

#[derive(Debug, Clone, Serialize)]
pub struct GovernanceCompetitionSuppressionReport {
    pub influence: String,
    pub harmful: bool,
    pub risk_signal: f64,
    pub suppression_strength: f64,
    pub appropriate: bool,
}

#[derive(Debug, Clone, Serialize)]
pub struct GovernanceSoftDominanceEvaluationReport {
    pub tag: String,
    pub dataset: String,
    pub scenario_count: usize,
    pub step_count: usize,
    pub baseline_dominance_score: f64,
    pub governed_dominance_score: f64,
    pub dominance_gain: f64,
    pub dominance_flexibility: f64,
    pub context_switch_accuracy: f64,
    pub inertia_drag_reduction: f64,
    pub transition_latency_improvement: f64,
    pub near_threshold_accuracy: f64,
    pub boundary_miss_rate: f64,
    pub over_correction_rate: f64,
    pub normal_preservation: f64,
    pub pass: bool,
    pub thresholds: GovernanceSoftDominanceThresholds,
    pub rollback: GovernanceRollbackReport,
    pub scenarios: Vec<GovernanceSoftDominanceScenarioReport>,
}

#[derive(Debug, Clone, Serialize)]
pub struct GovernanceSoftDominanceThresholds {
    pub governed_dominance_score_min: f64,
    pub dominance_gain_min: f64,
    pub dominance_flexibility_min: f64,
    pub context_switch_accuracy_min: f64,
    pub inertia_drag_reduction_min: f64,
    pub transition_latency_improvement_min: f64,
    pub near_threshold_accuracy_min: f64,
    pub over_correction_max: f64,
    pub normal_preservation_min: f64,
}

#[derive(Debug, Clone, Serialize)]
pub struct GovernanceSoftDominanceScenarioReport {
    pub id: String,
    pub scenario_type: String,
    pub influence_count: usize,
    pub step_count: usize,
    pub baseline_correct_steps: usize,
    pub governed_correct_steps: usize,
    pub baseline_dominance_score: f64,
    pub governed_dominance_score: f64,
    pub flexible_steps: usize,
    pub flexible_correct_steps: usize,
    pub dominance_flexibility: f64,
    pub context_switch_steps: usize,
    pub context_switch_correct_steps: usize,
    pub context_switch_accuracy: f64,
    pub inertia_drag_reduction: f64,
    pub transition_latency_gain: f64,
    pub near_threshold_steps: usize,
    pub near_threshold_correct_steps: usize,
    pub near_threshold_accuracy: f64,
    pub boundary_misses: usize,
    pub boundary_miss_rate: f64,
    pub normal_preservation_steps: usize,
    pub normal_preserved_steps: usize,
    pub over_corrections: usize,
    pub total_adjustments: usize,
    pub over_correction_rate: f64,
    pub normal_preservation: f64,
    pub steps: Vec<GovernanceSoftDominanceStepReport>,
}

#[derive(Debug, Clone, Serialize)]
pub struct GovernanceSoftDominanceStepReport {
    pub index: usize,
    pub event: String,
    pub expected_dominant: String,
    pub baseline_dominant: String,
    pub governed_dominant: String,
    pub baseline_correct: bool,
    pub governed_correct: bool,
    pub baseline_expected_margin: f64,
    pub governed_expected_margin: f64,
    pub baseline_inertia_drag: f64,
    pub governed_inertia_drag: f64,
    pub near_threshold: bool,
    pub context_switch: bool,
    pub influences: Vec<GovernanceSoftDominanceInfluenceReport>,
    pub adjustments: Vec<GovernanceSoftDominanceAdjustmentReport>,
}

#[derive(Debug, Clone, Serialize)]
pub struct GovernanceSoftDominanceInfluenceReport {
    pub id: String,
    pub label: String,
    pub harmful: bool,
    pub baseline_strength: f64,
    pub governed_strength: f64,
    pub baseline_inertia: f64,
    pub governed_inertia: f64,
    pub baseline_context_fit: f64,
    pub governed_context_fit: f64,
    pub baseline_effective_score: f64,
    pub governed_effective_score: f64,
}

#[derive(Debug, Clone, Serialize)]
pub struct GovernanceSoftDominanceAdjustmentReport {
    pub influence: String,
    pub harmful: bool,
    pub risk_signal: f64,
    pub suppression_strength: f64,
    pub strength_delta: f64,
    pub inertia_delta: f64,
    pub appropriate: bool,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum RegulationAction {
    Intervene,
    Observe,
    Hold,
}

#[derive(Debug, Clone, Serialize)]
pub struct GovernanceRegulationBoundaryEvaluationReport {
    pub tag: String,
    pub dataset: String,
    pub case_count: usize,
    pub intervention_case_count: usize,
    pub non_intervention_case_count: usize,
    pub exploration_case_count: usize,
    pub ambiguous_case_count: usize,
    pub predicted_interventions: usize,
    pub correct_interventions: usize,
    pub unnecessary_interventions: usize,
    pub intervention_precision: f64,
    pub intervention_recall: f64,
    pub intervention_restraint: f64,
    pub unnecessary_intervention_rate: f64,
    pub exploration_preservation: f64,
    pub ambiguous_restraint_rate: f64,
    pub regulation_boundary_score: f64,
    pub boundary_miss_rate: f64,
    pub mean_outcome_gain: f64,
    pub pass: bool,
    pub thresholds: GovernanceRegulationBoundaryThresholds,
    pub rollback: GovernanceRollbackReport,
    pub cases: Vec<GovernanceRegulationBoundaryCaseReport>,
}

#[derive(Debug, Clone, Serialize)]
pub struct GovernanceRegulationBoundaryThresholds {
    pub intervention_precision_min: f64,
    pub intervention_recall_min: f64,
    pub intervention_restraint_min: f64,
    pub unnecessary_intervention_max: f64,
    pub exploration_preservation_min: f64,
    pub ambiguous_restraint_min: f64,
    pub regulation_boundary_score_min: f64,
    pub mean_outcome_gain_min: f64,
}

#[derive(Debug, Clone, Serialize)]
pub struct GovernanceRegulationBoundaryCaseReport {
    pub id: String,
    pub case_type: String,
    pub expected_action: RegulationAction,
    pub predicted_action: RegulationAction,
    pub correct_action: bool,
    pub harm_pressure: f64,
    pub restraint_pressure: f64,
    pub boundary_margin: f64,
    pub risk_signal: f64,
    pub pattern_risk: f64,
    pub contradiction_signal: f64,
    pub evidence_support: f64,
    pub novelty_score: f64,
    pub uncertainty_score: f64,
    pub context_volatility: f64,
    pub exploration_value: f64,
    pub current_influence: f64,
    pub desired_influence: f64,
    pub regulated_influence: f64,
    pub regulation_strength: f64,
    pub baseline_regret: f64,
    pub regulated_regret: f64,
    pub regret_reduction: f64,
    pub exploration_case: bool,
    pub ambiguous_case: bool,
}

#[derive(Debug, Clone, Serialize)]
pub struct GovernanceSelfConsistencyEvaluationReport {
    pub tag: String,
    pub dataset: String,
    pub case_count: usize,
    pub governance_consistency_score: f64,
    pub decision_path_agreement: f64,
    pub uncertainty_alignment: f64,
    pub contradiction_rate: f64,
    pub disagreement_rate: f64,
    pub high_uncertainty_disagreement_rate: f64,
    pub majority_expected_alignment: f64,
    pub abstention_consistency: f64,
    pub pass: bool,
    pub thresholds: GovernanceSelfConsistencyThresholds,
    pub rollback: GovernanceRollbackReport,
    pub path_reliability: Vec<(String, f64)>,
    pub cases: Vec<GovernanceSelfConsistencyCaseReport>,
}

#[derive(Debug, Clone, Serialize)]
pub struct GovernanceSelfConsistencyThresholds {
    pub governance_consistency_min: f64,
    pub decision_path_agreement_min: f64,
    pub uncertainty_alignment_min: f64,
    pub contradiction_rate_max: f64,
    pub high_uncertainty_disagreement_min: f64,
    pub majority_expected_alignment_min: f64,
    pub abstention_consistency_min: f64,
}

#[derive(Debug, Clone, Serialize)]
pub struct GovernanceSelfConsistencyCaseReport {
    pub id: String,
    pub case_type: String,
    pub expected_action: RegulationAction,
    pub majority_action: RegulationAction,
    pub majority_matches_expected: bool,
    pub path_agreement_score: f64,
    pub decision_path_agreement: f64,
    pub uncertainty_alignment: f64,
    pub uncertainty_level: f64,
    pub disagreement: bool,
    pub contradiction: bool,
    pub risk_signal: f64,
    pub replay_regret_gain: f64,
    pub pattern_risk: f64,
    pub boundary_margin: f64,
    pub novelty_score: f64,
    pub exploration_value: f64,
    pub paths: Vec<GovernanceSelfConsistencyPathReport>,
}

#[derive(Debug, Clone, Serialize)]
pub struct GovernanceSelfConsistencyPathReport {
    pub path: String,
    pub action: RegulationAction,
    pub confidence: f64,
    pub score: f64,
}

#[derive(Debug, Clone, serde::Serialize, serde::Deserialize, Default)]
pub struct HypothesisMetrics {
    pub total_hypotheses: usize,
    pub candidates: usize,
    pub observed: usize,
    pub confirmed: usize,
    pub strengthened: usize,
    pub disputed: usize,
    pub forgotten: usize,
    pub graduated_edges: usize,
    pub edge_density_pct: f64,
    pub max_edge_out_degree: usize,
    pub edge_types: Vec<(String, usize)>,
    pub mean_confidence: f64,
    pub mean_observations: f64,
    pub mean_distinct_contexts: f64,
    pub semantic_judged: usize,
    pub semantic_accepted: usize,
    pub semantic_rejected: usize,
    pub semantic_acceptance_rate: f64,
}
