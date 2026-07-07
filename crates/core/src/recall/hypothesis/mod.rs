//! Edge Hypothesis Pool — memory ecology edge lifecycle.
//!
//! Design: docs/EDGE_HYPOTHESIS_POOL.md (v0.3 FROZEN)
//!
//! Core principle: "reasoning proposes, experience disposes."
//! Edges are not created by a single observation. They are proposed as
//! hypotheses, validated across diverse contexts, and only graduate to
//! confirmed edges when experience proves them.

pub mod generator;
pub mod model;
pub mod store_ext;

pub use generator::{EdgeHypothesisGenerator, RuleBasedEdgeGenerator};
pub use model::{
    EdgeEvidence, EdgeHypothesis, EdgeHypothesisStatus, EdgeRelation, EdgeUtilityObservation,
    RetrievalContext,
};
pub use store_ext::HypothesisStore;

#[cfg(test)]
mod lifecycle_tests;
