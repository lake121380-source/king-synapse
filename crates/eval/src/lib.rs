pub mod algorithms;
pub mod cognitive_competition_stability;
pub mod cognitive_memory_benchmark;
pub mod contextual_competition_integration;
pub mod contract;
pub mod external;
pub mod governance_aggregation;
pub mod governance_bias;
pub mod governance_calibration;
pub mod governance_competition;
pub mod governance_confidence;
pub mod governance_drift;
pub mod governance_eval;
pub mod governance_recovery;
pub mod governance_regulation_boundary;
pub mod governance_replay;
pub mod governance_self_consistency;
pub mod governance_soft_dominance;
pub mod governance_stress;
pub mod harness;
pub mod metrics;
pub mod phase2_competition_eval;
pub mod phase2_temporal_influence_eval;
pub mod phase2_temporal_stress_eval;
pub mod phase3_future_influence;
pub mod phase3_lesson_candidate_eval;
pub mod phase3_lesson_lifecycle;
pub mod phase3_lesson_promotion;
pub mod phase3_reflection_observation;
pub mod phase4_cognitive_competition;
pub mod phase4_cognitive_influence;
pub mod phase4_contextual_weighting;
pub mod phase5_cognitive_generalization;
pub mod phase5_cognitive_policy;
pub mod phase5_cognitive_trace;
pub mod phase5_end_to_end_cognitive;
pub mod phase5_shadow_ranking;
pub mod phase5_trace_quality;
pub mod phase6_cognitive_baseline_comparison;
pub mod phase6_memory_intelligence_benchmark;
pub mod phase6_recall_score_distribution;
pub mod phase7_bounded_pattern_extraction_provider;
pub mod phase7_cognitive_architecture_contract;
pub mod phase7_pattern_extraction_protocol;
pub mod phase7_transfer_evaluation_protocol;
pub mod reporter;
pub mod types;

pub use algorithms::{
    activation_parameter_sweep_report, cognitive_chain_recall_report,
    cognitive_trace_dominance_report, deterministic_reflection_yield_report,
    expanded_cognitive_replay_report, exported_cognitive_session_report, forget_precision_report,
    hebbian_consistency_report, long_horizon_cognitive_memory_report,
    long_horizon_stability_audit_report, merge_precision_report, predictive_trace_report,
    reflection_yield_report, trace_reinforcement_report,
};
pub use cognitive_competition_stability::{
    CognitiveCompetitionStabilityMetrics, DeterministicStabilityReport,
    EvidenceStepReport as StabilityEvidenceStepReport,
    EvidenceTransitionReport as StabilityEvidenceTransitionReport,
    NoiseCaseReport as StabilityNoiseCaseReport, NoiseResistanceReport as StabilityNoiseReport,
    Phase4CognitiveCompetitionStabilityEvaluator, Phase4CognitiveCompetitionStabilityReport,
    StabilityCandidate, StabilityContext, StabilityExperimentStatus, StabilityResult,
    StabilityScoreBreakdown,
};
pub use cognitive_memory_benchmark::CognitiveMemoryBenchmarkEvaluator;
pub use contextual_competition_integration::{
    CandidateScoreBreakdown as ContextualCompetitionScoreBreakdown,
    CognitiveCandidate as ContextualCompetitionCandidate,
    CompetitionResult as ContextualCompetitionResult,
    ContextFlipSummary as ContextualCompetitionFlipSummary, ContextualCompetitionMetric,
    EvaluationContext as ContextualCompetitionEvaluationContext, FlipPairReport,
    Phase4ContextualCompetitionIntegrationEvaluator, Phase4ContextualCompetitionIntegrationReport,
    ScenarioReport as ContextualCompetitionScenarioReport,
};
pub use contract::{AlgorithmMetric, BenchmarkReport};
pub use external::{
    run_external_comparison, ExternalComparisonOptions, ExternalComparisonReport,
    ExternalSystemKind,
};
pub use governance_aggregation::GovernanceAggregationEvaluator;
pub use governance_bias::GovernanceBiasEvaluator;
pub use governance_calibration::GovernanceCalibrationEvaluator;
pub use governance_competition::GovernanceCompetitionEvaluator;
pub use governance_confidence::GovernanceConfidenceEvaluator;
pub use governance_drift::GovernanceDriftEvaluator;
pub use governance_eval::GovernanceEvaluator;
pub use governance_recovery::GovernanceRecoveryEvaluator;
pub use governance_regulation_boundary::GovernanceRegulationBoundaryEvaluator;
pub use governance_replay::GovernanceReplayEvaluator;
pub use governance_self_consistency::GovernanceSelfConsistencyEvaluator;
pub use governance_soft_dominance::GovernanceSoftDominanceEvaluator;
pub use governance_stress::GovernanceStressEvaluator;
pub use harness::{default_dataset_path, run};
pub use phase2_competition_eval::{
    Phase2CompetitionCaseReport, Phase2CompetitionDeltaReport, Phase2CompetitionEvaluationReport,
    Phase2CompetitionEvaluator, Phase2CompetitionModeReport, Phase2CompetitionTraceStepReport,
};
pub use phase2_temporal_influence_eval::{
    BeforeAfterImprovement, Phase2TemporalCaseReport, Phase2TemporalErrorsReport,
    Phase2TemporalInfluenceEvaluationReport, Phase2TemporalInfluenceEvaluator,
    Phase2TemporalMetricsReport, Phase2TemporalModeReport, Phase2TemporalTransitionStepReport,
};
pub use phase2_temporal_stress_eval::{
    Phase2TemporalStressEvaluationReport, Phase2TemporalStressEvaluator,
    Phase2TemporalStressMetricsReport, Phase2TemporalStressScenarioReport,
    Phase2TemporalStressStepReport,
};
pub use phase3_future_influence::{
    FutureInfluenceResultsReport, FutureInfluenceSafetyReport, FutureInfluenceTrace,
    Phase3FutureInfluenceEvaluator, Phase3FutureInfluenceMetrics, Phase3FutureInfluenceReport,
};
pub use phase3_lesson_candidate_eval::{
    LessonCandidateReport, Phase3LessonCandidateEvaluationReport, Phase3LessonCandidateEvaluator,
    Phase3LessonCandidateMetrics,
};
pub use phase3_lesson_lifecycle::{
    LessonLifecycleSafetyReport, LessonLifecycleState, LessonLifecycleStateCounts,
    LessonLifecycleTrace, LessonTransition, Phase3LessonLifecycleEvaluator,
    Phase3LessonLifecycleMetrics, Phase3LessonLifecycleReport,
};
pub use phase3_lesson_promotion::{
    LessonPromotionTrace, Phase3LessonPromotionEvaluator, Phase3LessonPromotionMetrics,
    Phase3LessonPromotionReport, PromotionSafetyReport, PromotionSummaryReport,
};
pub use phase3_reflection_observation::{
    Phase3ReflectionObservationEvaluator, Phase3ReflectionObservationMetrics,
    Phase3ReflectionObservationReport, ReflectionTraceReport,
};
pub use phase4_cognitive_competition::{
    ActivationPathReport, CognitiveCompetitionSafetyReport, CompetitionCandidate,
    CompetitionCandidateState, CompetitionParameters, CompetitionRound, CompetitionTrace,
    Phase4CognitiveCompetitionEvaluator, Phase4CognitiveCompetitionMetrics,
    Phase4CognitiveCompetitionReport, SuppressedCompetitionCandidate,
};
pub use phase4_cognitive_influence::{
    CandidateType, CognitiveCandidate, CognitiveInfluenceRanking, CognitiveInfluenceSafetyReport,
    CognitiveInfluenceTrace, CognitiveScoreBreakdown, InfluenceWeights,
    Phase4CognitiveInfluenceEvaluator, Phase4CognitiveInfluenceMetrics,
    Phase4CognitiveInfluenceReport, SuppressedCandidateReport,
};
pub use phase4_contextual_weighting::{
    CognitiveContext, ContextVariantReport, ContextualCandidate, ContextualInfluenceRanking,
    ContextualWeightBreakdown, ContextualWeightParameters, ContextualWeightingSafetyReport,
    ContextualWeightingTrace, Phase4ContextualWeightingEvaluator, Phase4ContextualWeightingMetrics,
    Phase4ContextualWeightingReport,
};
pub use phase5_cognitive_generalization::{
    FactorInteractionReport, GeneralizationDecision, GeneralizationPolicySummary,
    GeneralizationSafetyGuards, GeneralizationSplitReport, Phase5CognitiveGeneralizationEvaluator,
    Phase5CognitiveGeneralizationReport, PolicyLockReport,
};
pub use phase5_cognitive_policy::{
    load_cognitive_policy_benchmark, CognitiveFactorContributionReport,
    CognitivePolicyAblationReport, CognitivePolicyBenchmarkSummary, CognitivePolicyCandidateReport,
    CognitivePolicyMemorySpec, CognitivePolicyMetrics, CognitivePolicyResult,
    CognitivePolicySafetyGuards, CognitivePolicyScenarioReport, CognitivePolicyScenarioSpec,
    Phase5CognitivePolicyEvaluator, Phase5CognitivePolicyReport, PolicyNormalizationReport,
};
pub use phase5_cognitive_trace::{
    LatencySummary as Phase5CognitiveTraceLatencySummary, Phase5CognitiveTraceEvaluator,
    Phase5CognitiveTraceGuards, Phase5CognitiveTraceLatency, Phase5CognitiveTraceMetrics,
    Phase5CognitiveTraceReport, Phase5CognitiveTraceScenarioReport,
};
pub use phase5_end_to_end_cognitive::{
    load_phase5_end_to_end_workload, EndToEndCandidateReport, EndToEndDatasetSummary,
    EndToEndDecision, EndToEndMemorySpec, EndToEndMetrics, EndToEndPolicyResult, EndToEndProtocol,
    EndToEndSafetyGuards, EndToEndScenarioReport, EndToEndScenarioSpec,
    Phase5EndToEndCognitiveEvaluator, Phase5EndToEndReport,
};
pub use phase5_shadow_ranking::{
    Phase5ShadowRankingEvaluator, Phase5ShadowRankingGuards, Phase5ShadowRankingLatency,
    Phase5ShadowRankingMetrics, Phase5ShadowRankingReport, Phase5ShadowRankingScenarioReport,
    ShadowCandidateReport,
};
pub use phase5_trace_quality::{
    BaselineCandidateMetadata, BaselineExplanation, CognitiveExplanation,
    ExplanationCompletenessAudit, ExplanationCriteria, ExplanationPreference,
    FactorFaithfulnessAudit, PairwiseExplanationJudgeReport, Phase5TraceQualityEvaluator,
    Phase5TraceQualityGuards, Phase5TraceQualityJudgeProtocol, Phase5TraceQualityMetrics,
    Phase5TraceQualityReport, Phase5TraceQualityScenarioReport, Phase5TraceQualityThresholds,
};
pub use phase6_cognitive_baseline_comparison::{
    AblationResult, CandidatePolicyReport, CognitiveBaselineComparisonGuards,
    CognitiveBaselineComparisonProtocol, CognitiveBaselineDatasetSummary,
    CognitiveBaselineDecision, ComparisonMetrics, FactorContribution,
    Phase6CognitiveBaselineComparisonEvaluator, Phase6CognitiveBaselineComparisonReport,
    PolicyResult, ScenarioPolicyReport,
};
pub use phase6_memory_intelligence_benchmark::{
    load_phase6_memory_intelligence_benchmark, MemoryIntelligenceDatasetSummary,
    MemoryIntelligenceGroupMetrics, MemoryIntelligenceGuards, MemoryIntelligenceMemorySpec,
    MemoryIntelligenceProtocol, MemoryIntelligenceRetrievalMetrics,
    MemoryIntelligenceScenarioReport, MemoryIntelligenceScenarioSpec,
    Phase6MemoryIntelligenceBenchmarkEvaluator, Phase6MemoryIntelligenceReport,
};
pub use phase6_recall_score_distribution::{
    AdjacentGapDistribution, CandidateCountDistribution, DistributionSummary, GroupMarginCoverage,
    MarginCoverage, Phase6RecallScoreDistributionEvaluator, Phase6RecallScoreDistributionReport,
    RankScoreDistribution, RecallScoreDistributionDecision, RecallScoreDistributionGuards,
    RecallScoreDistributionProtocol, RecallScoreScenarioReport, ScoreDistributionReport,
};
pub use phase7_bounded_pattern_extraction_provider::{
    evaluate_provider, BoundedPatternExtractionGuards, BoundedPatternExtractionProviderConfig,
    DeterministicBoundedPatternExtractionProvider, PatternExtractionProviderCaseReport,
    PatternExtractionProviderSummary, PatternExtractionQualityMetrics,
    Phase7BoundedPatternExtractionDecision, Phase7BoundedPatternExtractionEvaluator,
    Phase7BoundedPatternExtractionReport, ProviderFaultInjectionReport, ProviderOutputDisposition,
};
pub use phase7_cognitive_architecture_contract::{
    validate_pattern_candidate, CognitiveArtifactContract, ConfidenceUpdatePolicy,
    EvidenceReference, FalsificationCondition, NorthStarContract, PatternCandidate,
    PatternCondition, PatternContractCase, PatternContractValidation, PatternLifecycleTransition,
    PatternPrediction, PatternStatus, Phase7ArchitectureDecision, Phase7ArchitectureGuards,
    Phase7CognitiveArchitectureContractEvaluator, Phase7CognitiveArchitectureContractReport,
};
pub use phase7_pattern_extraction_protocol::{
    load_phase7_pattern_extraction_design, validate_pattern_extraction_batch,
    validate_pattern_extraction_submission, ExtractionExperience, PatternExtractionBatchValidation,
    PatternExtractionCase, PatternExtractionDataset, PatternExtractionDatasetSummary,
    PatternExtractionInput, PatternExtractionMetricDefinition, PatternExtractionNegativeCase,
    PatternExtractionProtocolGuards, PatternExtractionProvider,
    PatternExtractionSubmissionValidation, Phase7PatternExtractionDecision,
    Phase7PatternExtractionProtocolEvaluator, Phase7PatternExtractionReport,
};
pub use phase7_transfer_evaluation_protocol::{
    load_phase7_transfer_benchmark, validate_transfer_scenario, DangerousTransfer,
    EvidenceGraphEdge, ExpectedTransfer, Phase7TransferDecision,
    Phase7TransferEvaluationProtocolEvaluator, Phase7TransferEvaluationReport, TransferArmContract,
    TransferBenchmarkDataset, TransferCategory, TransferDatasetSummary, TransferEvidence,
    TransferExperimentArm, TransferFailureTaxonomyEntry, TransferMetricDefinition,
    TransferPatternCandidate, TransferProtocolGuards, TransferScenario, TransferScenarioValidation,
    TransferSplit,
};
pub use reporter::print_table;
pub use types::{
    BenchOptions, CognitiveMemoryAblationReport, CognitiveMemoryBenchmarkReport,
    CognitiveMemoryCaseMethodReport, CognitiveMemoryCaseReport, CognitiveMemoryCriteriaReport,
    CognitiveMemoryDatasetReport, CognitiveMemoryErrorAnalysisReport,
    CognitiveMemoryFailedCaseReport, CognitiveMemoryInfluenceAttributionReport,
    CognitiveMemoryInfluenceCaseReport, CognitiveMemoryInfluentialMemoryReport,
    CognitiveMemoryMethodSummary, CognitiveMemoryThresholds, CognitiveMemoryTraceQualityReport,
    Dataset, DetectorConfidenceObservationReport, DetectorConfidenceRecord,
    GovernanceAggregationDetectorReport, GovernanceAggregationEvaluationReport,
    GovernanceAggregationMethodReport, GovernanceAggregationThresholds, GovernanceBiasCaseReport,
    GovernanceBiasEdgeReport, GovernanceBiasEvaluationReport, GovernanceBiasThresholds,
    GovernanceCalibrationCandidateReport, GovernanceCalibrationSweepReport,
    GovernanceCalibrationThresholds, GovernanceCompetitionEvaluationReport,
    GovernanceCompetitionInfluenceReport, GovernanceCompetitionScenarioReport,
    GovernanceCompetitionStepReport, GovernanceCompetitionSuppressionReport,
    GovernanceCompetitionThresholds, GovernanceConfidenceEvaluationReport,
    GovernanceConfidenceThresholds, GovernanceDetectionReport, GovernanceDriftEvaluationReport,
    GovernanceDriftPatternReport, GovernanceDriftScenarioReport, GovernanceDriftStepReport,
    GovernanceDriftThresholds, GovernanceEvaluationReport, GovernanceInterventionSafetyReport,
    GovernanceRecoveryEvaluationReport, GovernanceRecoveryScenarioReport,
    GovernanceRecoveryStepReport, GovernanceRecoveryThresholds,
    GovernanceRegulationBoundaryCaseReport, GovernanceRegulationBoundaryEvaluationReport,
    GovernanceRegulationBoundaryThresholds, GovernanceReplayCaseReport,
    GovernanceReplayDetectorReport, GovernanceReplayEvaluationReport, GovernanceReplayEventReport,
    GovernanceReplayThresholds, GovernanceRollbackReport, GovernanceSelfConsistencyCaseReport,
    GovernanceSelfConsistencyEvaluationReport, GovernanceSelfConsistencyPathReport,
    GovernanceSelfConsistencyThresholds, GovernanceSoftDominanceAdjustmentReport,
    GovernanceSoftDominanceEvaluationReport, GovernanceSoftDominanceInfluenceReport,
    GovernanceSoftDominanceScenarioReport, GovernanceSoftDominanceStepReport,
    GovernanceSoftDominanceThresholds, GovernanceSourceTraceReport, GovernanceStressCaseReport,
    GovernanceStressEdgeReport, GovernanceStressEvaluationReport, GovernanceStressThresholds,
    GovernanceTemporalStabilityReport, MemorySpec, QueryResult, QuerySpec, RegulationAction,
    Report, SemanticConfidenceBucket, SemanticEdgeLifecycleRecord, SemanticGovernanceReport,
    SemanticJudgeKind, SemanticPolicyEvaluation, SemanticPolicySearchReport,
    SemanticSurvivalReport, SemanticUtilityReport,
};
