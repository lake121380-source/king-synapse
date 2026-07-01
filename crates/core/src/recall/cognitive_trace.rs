use crate::error::Result;
use crate::model::{Memory, RecallQuery};
use crate::recall::{LatentActivationContext, LatentActivationHit, LatentActivationProbe};
use crate::{RecallEngine, RecallHit, Store};
use serde::{Deserialize, Serialize};
use std::cmp::Ordering;
use std::collections::HashMap;

const DEFAULT_VISIBLE_LIMIT: usize = 8;
const DEFAULT_LATENT_LIMIT: usize = 10;
const DEFAULT_SEED_LIMIT: usize = 3;
const DEFAULT_SUPPRESSED_LIMIT: usize = 7;
const DEFAULT_LATENT_SCALE: f32 = 0.05;
const DEFAULT_LATENT_CAP: f32 = 0.25;
const DEFAULT_LATENT_STEPS: usize = 2;
const DEFAULT_LATENT_DECAY: f32 = 0.5;
const DEFAULT_LATENT_FANOUT: usize = 16;
const VISIBLE_COMPETITION_WEIGHT: f32 = 0.7;
const LATENT_COMPETITION_WEIGHT: f32 = 1.0;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CognitiveTraceConfig {
    pub visible_limit: usize,
    pub latent_limit: usize,
    pub seed_limit: usize,
    pub suppressed_limit: usize,
    pub latent_scale: f32,
    pub latent_cap: f32,
    pub latent_steps: usize,
    pub latent_decay: f32,
    pub latent_fanout: usize,
}

impl Default for CognitiveTraceConfig {
    fn default() -> Self {
        Self {
            visible_limit: DEFAULT_VISIBLE_LIMIT,
            latent_limit: DEFAULT_LATENT_LIMIT,
            seed_limit: DEFAULT_SEED_LIMIT,
            suppressed_limit: DEFAULT_SUPPRESSED_LIMIT,
            latent_scale: DEFAULT_LATENT_SCALE,
            latent_cap: DEFAULT_LATENT_CAP,
            latent_steps: DEFAULT_LATENT_STEPS,
            latent_decay: DEFAULT_LATENT_DECAY,
            latent_fanout: DEFAULT_LATENT_FANOUT,
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum CognitiveTraceSource {
    Visible,
    Latent,
    VisibleAndLatent,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CognitiveTraceCandidate {
    pub memory: Memory,
    pub source: CognitiveTraceSource,
    pub combined_score: f32,
    pub visible_score: Option<f32>,
    pub visible_rank: Option<usize>,
    pub latent_activation: Option<f32>,
    pub latent_depth: Option<usize>,
    pub latent_path: Vec<String>,
    pub latent_modulation: Option<f32>,
    pub matched_terms: Vec<String>,
    pub inhibition: f32,
}

#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct CognitiveTraceStatistics {
    pub visible_candidates: usize,
    pub latent_candidates: usize,
    pub combined_candidates: usize,
    pub suppressed_candidates: usize,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CognitiveTraceReport {
    pub query: String,
    pub context: LatentActivationContext,
    pub dominant: Option<CognitiveTraceCandidate>,
    pub suppressed: Vec<CognitiveTraceCandidate>,
    pub visible: Vec<RecallHit>,
    pub latent: Vec<LatentActivationHit>,
    pub statistics: CognitiveTraceStatistics,
}

pub struct CognitiveTraceProbe {
    config: CognitiveTraceConfig,
}

impl CognitiveTraceProbe {
    pub fn new(config: CognitiveTraceConfig) -> Self {
        Self { config }
    }

    pub fn config(&self) -> &CognitiveTraceConfig {
        &self.config
    }

    pub fn trace(
        &self,
        store: &mut Store,
        query: &RecallQuery,
        context: &LatentActivationContext,
    ) -> Result<CognitiveTraceReport> {
        let visible_limit = query.k.unwrap_or(self.config.visible_limit).max(1);
        let visible_query = RecallQuery {
            query: query.query.clone(),
            k: Some(visible_limit),
            scope_filter: query.scope_filter.clone(),
            kind_filter: query.kind_filter,
        };
        let visible = RecallEngine::new(store).recall(&visible_query)?;
        let seed_ids = visible
            .iter()
            .take(self.config.seed_limit.max(1))
            .map(|hit| hit.memory.id.as_str())
            .collect::<Vec<_>>();
        let latent_probe = LatentActivationProbe::with_config(
            self.config.latent_scale,
            self.config.latent_cap,
            self.config.latent_steps,
            self.config.latent_decay,
            self.config.latent_fanout,
        );
        let latent = latent_probe.activate_with_context(
            store,
            &seed_ids,
            self.config.latent_limit.max(1),
            context,
        )?;
        let (dominant, suppressed) =
            merge_candidates(&visible, &latent, self.config.suppressed_limit);
        let statistics = CognitiveTraceStatistics {
            visible_candidates: visible.len(),
            latent_candidates: latent.len(),
            combined_candidates: usize::from(dominant.is_some()) + suppressed.len(),
            suppressed_candidates: suppressed.len(),
        };

        Ok(CognitiveTraceReport {
            query: query.query.clone(),
            context: context.clone(),
            dominant,
            suppressed,
            visible,
            latent,
            statistics,
        })
    }

    pub fn trace_auto_context(
        &self,
        store: &mut Store,
        query: &RecallQuery,
        explicit_context: &LatentActivationContext,
    ) -> Result<CognitiveTraceReport> {
        let context =
            LatentActivationContext::from_text(&query.query).merge(explicit_context.clone());
        self.trace(store, query, &context)
    }
}

impl Default for CognitiveTraceProbe {
    fn default() -> Self {
        Self::new(CognitiveTraceConfig::default())
    }
}

#[derive(Debug, Clone)]
struct CandidateBuilder {
    memory: Memory,
    visible_score: Option<f32>,
    visible_rank: Option<usize>,
    latent_activation: Option<f32>,
    latent_depth: Option<usize>,
    latent_path: Vec<String>,
    latent_modulation: Option<f32>,
    matched_terms: Vec<String>,
}

impl CandidateBuilder {
    fn from_visible(hit: &RecallHit, rank: usize) -> Self {
        Self {
            memory: hit.memory.clone(),
            visible_score: Some(hit.score),
            visible_rank: Some(rank),
            latent_activation: None,
            latent_depth: None,
            latent_path: Vec::new(),
            latent_modulation: None,
            matched_terms: Vec::new(),
        }
    }

    fn from_latent(hit: &LatentActivationHit) -> Self {
        Self {
            memory: hit.memory.clone(),
            visible_score: None,
            visible_rank: None,
            latent_activation: Some(hit.activation),
            latent_depth: Some(hit.depth),
            latent_path: hit.path.clone(),
            latent_modulation: Some(hit.modulation),
            matched_terms: hit.matched_terms.clone(),
        }
    }

    fn apply_latent(&mut self, hit: &LatentActivationHit) {
        self.latent_activation = Some(hit.activation);
        self.latent_depth = Some(hit.depth);
        self.latent_path = hit.path.clone();
        self.latent_modulation = Some(hit.modulation);
        self.matched_terms = hit.matched_terms.clone();
    }

    fn into_candidate(
        self,
        dominant_score: f32,
        max_visible_score: f32,
        max_latent_activation: f32,
    ) -> CognitiveTraceCandidate {
        let combined_score = competition_score(&self, max_visible_score, max_latent_activation);
        let source = match (
            self.visible_score.is_some(),
            self.latent_activation.is_some(),
        ) {
            (true, true) => CognitiveTraceSource::VisibleAndLatent,
            (true, false) => CognitiveTraceSource::Visible,
            (false, true) => CognitiveTraceSource::Latent,
            (false, false) => CognitiveTraceSource::Visible,
        };

        CognitiveTraceCandidate {
            memory: self.memory,
            source,
            combined_score,
            visible_score: self.visible_score,
            visible_rank: self.visible_rank,
            latent_activation: self.latent_activation,
            latent_depth: self.latent_depth,
            latent_path: self.latent_path,
            latent_modulation: self.latent_modulation,
            matched_terms: self.matched_terms,
            inhibition: (dominant_score - combined_score).max(0.0),
        }
    }
}

fn merge_candidates(
    visible: &[RecallHit],
    latent: &[LatentActivationHit],
    suppressed_limit: usize,
) -> (
    Option<CognitiveTraceCandidate>,
    Vec<CognitiveTraceCandidate>,
) {
    let mut builders: HashMap<String, CandidateBuilder> = HashMap::new();
    for (idx, hit) in visible.iter().enumerate() {
        builders.insert(
            hit.memory.id.clone(),
            CandidateBuilder::from_visible(hit, idx + 1),
        );
    }
    for hit in latent {
        builders
            .entry(hit.memory.id.clone())
            .and_modify(|candidate| candidate.apply_latent(hit))
            .or_insert_with(|| CandidateBuilder::from_latent(hit));
    }

    let mut builders = builders.into_values().collect::<Vec<_>>();
    let max_visible_score = builders
        .iter()
        .filter_map(|candidate| candidate.visible_score)
        .filter(|score| *score > 0.0 && score.is_finite())
        .fold(0.0, f32::max);
    let max_latent_activation = builders
        .iter()
        .filter_map(|candidate| candidate.latent_activation)
        .filter(|activation| *activation > 0.0 && activation.is_finite())
        .fold(0.0, f32::max);
    builders.sort_by(|a, b| compare_builders(a, b, max_visible_score, max_latent_activation));
    let dominant_score = builders
        .first()
        .map(|candidate| competition_score(candidate, max_visible_score, max_latent_activation))
        .unwrap_or(0.0);
    let mut candidates = builders
        .into_iter()
        .map(|candidate| {
            candidate.into_candidate(dominant_score, max_visible_score, max_latent_activation)
        })
        .collect::<Vec<_>>();
    let dominant = candidates.first().cloned();
    let suppressed = if candidates.len() > 1 {
        candidates
            .drain(1..)
            .take(suppressed_limit)
            .collect::<Vec<_>>()
    } else {
        Vec::new()
    };

    (dominant, suppressed)
}

fn compare_builders(
    a: &CandidateBuilder,
    b: &CandidateBuilder,
    max_visible_score: f32,
    max_latent_activation: f32,
) -> Ordering {
    competition_score(b, max_visible_score, max_latent_activation)
        .partial_cmp(&competition_score(
            a,
            max_visible_score,
            max_latent_activation,
        ))
        .unwrap_or(Ordering::Equal)
        .then_with(|| {
            a.visible_rank
                .unwrap_or(usize::MAX)
                .cmp(&b.visible_rank.unwrap_or(usize::MAX))
        })
        .then_with(|| a.memory.id.cmp(&b.memory.id))
}

fn competition_score(
    candidate: &CandidateBuilder,
    max_visible_score: f32,
    max_latent_activation: f32,
) -> f32 {
    let visible = normalized_component(candidate.visible_score, max_visible_score);
    let latent = normalized_component(candidate.latent_activation, max_latent_activation);
    visible * VISIBLE_COMPETITION_WEIGHT + latent * LATENT_COMPETITION_WEIGHT
}

fn normalized_component(value: Option<f32>, max_value: f32) -> f32 {
    if max_value <= 0.0 || !max_value.is_finite() {
        return 0.0;
    }
    value
        .filter(|value| *value > 0.0 && value.is_finite())
        .map(|value| (value / max_value).clamp(0.0, 1.0))
        .unwrap_or(0.0)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::model::{MemoryKind, Scope, Source, WriteInput};

    fn add(store: &mut Store, content: &str) -> String {
        store
            .write(WriteInput {
                content: content.to_string(),
                kind: MemoryKind::Fact,
                scope: Scope::User,
                source: Source::ExplicitUser,
                confidence: Some(1.0),
                importance: Some(0.7),
            })
            .unwrap()
            .id
    }

    fn config() -> CognitiveTraceConfig {
        CognitiveTraceConfig {
            visible_limit: 4,
            latent_limit: 4,
            seed_limit: 2,
            suppressed_limit: 4,
            latent_scale: 0.05,
            latent_cap: 0.25,
            latent_steps: 2,
            latent_decay: 0.5,
            latent_fanout: 10,
        }
    }

    #[test]
    fn cognitive_trace_can_surface_latent_dominant_candidate() {
        let mut store = Store::open_in_memory().unwrap();
        let seed = add(&mut store, "forgot morning water before commute");
        let visible = add(&mut store, "forgot water calendar note");
        let hidden = add(&mut store, "tired attention failure");
        store.update_edge(&seed, &hidden, 2.0).unwrap();

        let query = RecallQuery {
            query: "forgot water".to_string(),
            k: Some(2),
            scope_filter: None,
            kind_filter: None,
        };
        let context =
            LatentActivationContext::new(vec!["tired".to_string()], vec!["attention".to_string()]);
        let report = CognitiveTraceProbe::new(config())
            .trace(&mut store, &query, &context)
            .unwrap();

        let dominant = report.dominant.expect("dominant candidate");
        assert_eq!(dominant.memory.id, hidden);
        assert_eq!(dominant.source, CognitiveTraceSource::Latent);
        assert!(dominant.combined_score > 0.0);
        assert!(dominant.matched_terms.contains(&"state:tired".to_string()));
        assert!(dominant
            .matched_terms
            .contains(&"goal:attention".to_string()));
        assert!(report
            .suppressed
            .iter()
            .any(|candidate| candidate.memory.id == seed));
        assert!(report
            .suppressed
            .iter()
            .any(|candidate| candidate.memory.id == visible));
    }

    #[test]
    fn cognitive_trace_auto_context_derives_query_terms() {
        let mut store = Store::open_in_memory().unwrap();
        let seed = add(&mut store, "forgot water before commute");
        let hidden = add(&mut store, "attention failure risk");
        store.update_edge(&seed, &hidden, 2.0).unwrap();

        let query = RecallQuery {
            query: "forgot water while tired before commute".to_string(),
            k: Some(1),
            scope_filter: None,
            kind_filter: None,
        };
        let report = CognitiveTraceProbe::new(config())
            .trace_auto_context(&mut store, &query, &LatentActivationContext::default())
            .unwrap();

        let dominant = report.dominant.expect("dominant candidate");
        assert_eq!(dominant.memory.id, hidden);
        assert!(report.context.state_terms.contains(&"tired".to_string()));
        assert!(report.context.goal_terms.contains(&"commute".to_string()));
    }
}
