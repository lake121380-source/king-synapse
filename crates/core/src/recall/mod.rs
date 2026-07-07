//! Recall layer: turns a `RecallQuery` into a ranked list of memories.
//!
//! Pipeline (frozen at Phase 2 step 5.5; see `docs/RECALL_PIPELINE.md`):
//!
//! ```text
//! retriever -> RRF -> [reranker] -> base_score (decay, importance)
//!                                -> [boosters] -> final_score -> top-k
//! ```
//!
//! Store stays query-agnostic; this module owns query understanding,
//! optional embedding, fusion, reranking, decay, boosters, and resorting.

mod booster;
mod cognitive_trace;
mod engine;
mod graph_activation;
mod hit;
mod latent_activation;
mod latent_booster;
mod hypothesis;
mod query_latent;
mod rrf;

use crate::error::Result;

pub use booster::{BoosterContext, NoOpBooster, RecallBooster};
pub use cognitive_trace::{
    CognitiveTraceCandidate, CognitiveTraceConfig, CognitiveTracePredictionReport,
    CognitiveTracePredictionStatistics, CognitiveTraceProbe, CognitiveTraceReport,
    CognitiveTraceSource, CognitiveTraceStatistics,
};
pub use engine::{ProfiledRecall, RecallEngine, RecallProfile};
pub use graph_activation::GraphActivationBooster;
pub use hit::{RecallHit, RecallSource};
pub use latent_activation::{LatentActivationContext, LatentActivationHit, LatentActivationProbe};
pub use latent_booster::LatentActivationBooster;
pub use query_latent::{QueryLatentActivationProbe, QueryLatentActivationReport};
pub use rrf::{RrfBranchWeights, DEFAULT_RRF_K};

pub use hypothesis::generator::{EdgeHypothesisGenerator, RuleBasedEdgeGenerator};
pub use hypothesis::model::{
    EdgeEvidence, EdgeHypothesis, EdgeHypothesisStatus, EdgeRelation,
    EdgeUtilityObservation, RetrievalContext,
    CONFIRM_THRESHOLD, MIN_OBSERVATIONS, MIN_DIVERSITY_CONTEXTS,
    W_FREQUENCY, W_DIVERSITY, W_UTILITY,
    INITIAL_CONFIDENCE, REOBSERVATION_BOOST, DECAY_PER_TURN, CONFIDENCE_FLOOR,
};
pub use hypothesis::store_ext::HypothesisStore;

/// Default candidate pool size handed to the reranker before top-k truncation.
pub const DEFAULT_RERANK_POOL: usize = 50;

/// Anything that can turn a natural-language query into a dense vector.
///
/// `Embedder` from `crate::embed` implements this; tests can supply a stub.
pub trait QueryEmbedder {
    fn embed_query(&mut self, query: &str) -> Result<Vec<f32>>;
}

impl QueryEmbedder for crate::embed::Embedder {
    fn embed_query(&mut self, query: &str) -> Result<Vec<f32>> {
        crate::embed::Embedder::embed_query(self, query)
    }
}
