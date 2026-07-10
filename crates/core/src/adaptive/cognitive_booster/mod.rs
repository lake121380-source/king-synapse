//! Phase 5.3.1 bounded cognitive booster interface.
//!
//! This module defines a shadow-only proposal contract. It is deliberately
//! separate from `recall::RecallBooster`: candidates are borrowed immutably,
//! no `RecallHit` field can be changed, and outputs are never applied by the
//! recall runtime in Phase 5.3.1.

mod interface;
mod types;

pub use interface::{CognitiveBooster, NoOpCognitiveBooster};
pub use types::{
    CognitiveAdjustedScore, CognitiveBoosterConfig, CognitiveBoosterConfigError,
    CognitiveBoosterInput, CognitiveBoosterMode, CognitiveBoosterOutput,
    MAX_COGNITIVE_BOOSTER_BONUS,
};
