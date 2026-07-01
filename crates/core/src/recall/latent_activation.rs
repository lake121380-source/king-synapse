use crate::error::Result;
use crate::model::Memory;
use crate::store::Store;
use serde::{Deserialize, Serialize};
use std::cmp::Ordering;
use std::collections::{HashMap, HashSet};

const DEFAULT_SCALE: f32 = 0.05;
const DEFAULT_CAP: f32 = 0.25;
const DEFAULT_DECAY: f32 = 0.5;
const DEFAULT_STEPS: usize = 2;
const DEFAULT_FANOUT: usize = 16;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LatentActivationHit {
    pub memory: Memory,
    pub activation: f32,
    pub depth: usize,
    pub path: Vec<String>,
}

pub struct LatentActivationProbe {
    scale: f32,
    cap: f32,
    decay: f32,
    steps: usize,
    fanout: usize,
}

impl LatentActivationProbe {
    pub fn new(scale: f32, cap: f32) -> Self {
        Self::with_config(scale, cap, DEFAULT_STEPS, DEFAULT_DECAY, DEFAULT_FANOUT)
    }

    pub fn with_config(scale: f32, cap: f32, steps: usize, decay: f32, fanout: usize) -> Self {
        Self {
            scale: sanitize_non_negative(scale, DEFAULT_SCALE),
            cap: sanitize_non_negative(cap, DEFAULT_CAP),
            decay: sanitize_unit(decay, DEFAULT_DECAY),
            steps: steps.max(1),
            fanout: fanout.max(1),
        }
    }

    pub fn scale(&self) -> f32 {
        self.scale
    }

    pub fn cap(&self) -> f32 {
        self.cap
    }

    pub fn decay(&self) -> f32 {
        self.decay
    }

    pub fn steps(&self) -> usize {
        self.steps
    }

    pub fn fanout(&self) -> usize {
        self.fanout
    }

    pub fn activate(
        &self,
        store: &Store,
        seed_ids: &[&str],
        limit: usize,
    ) -> Result<Vec<LatentActivationHit>> {
        if seed_ids.is_empty()
            || limit == 0
            || self.scale == 0.0
            || self.cap == 0.0
            || self.decay == 0.0
        {
            return Ok(Vec::new());
        }

        let seeds = normalized_seed_set(seed_ids);
        if seeds.is_empty() {
            return Ok(Vec::new());
        }

        let mut frontier = seeds
            .iter()
            .map(|id| FrontierNode {
                id: id.clone(),
                activation: 1.0,
                path_activation: 1.0,
                path: vec![id.clone()],
            })
            .collect::<Vec<_>>();
        let mut accumulated: HashMap<String, AccumulatedActivation> = HashMap::new();

        for depth in 1..=self.steps {
            let mut next_frontier: HashMap<String, FrontierNode> = HashMap::new();
            let step_decay = if depth == 1 { 1.0 } else { self.decay };

            for source in &frontier {
                if source.activation <= 0.0 || !source.activation.is_finite() {
                    continue;
                }

                let edges = store.outgoing_edges(&source.id, self.fanout)?;
                for edge in edges {
                    if edge.weight <= 0.0 || !edge.weight.is_finite() {
                        continue;
                    }
                    if seeds.contains(&edge.target) || source.path.contains(&edge.target) {
                        continue;
                    }

                    let propagated = source.activation * edge.weight * self.scale * step_decay;
                    if propagated <= 0.0 || !propagated.is_finite() {
                        continue;
                    }

                    let mut path = source.path.clone();
                    path.push(edge.target.clone());
                    update_accumulated(
                        &mut accumulated,
                        &edge.target,
                        propagated,
                        depth,
                        &path,
                        self.cap,
                    );
                    update_frontier(
                        &mut next_frontier,
                        &edge.target,
                        propagated,
                        &path,
                        self.cap,
                    );
                }
            }

            if next_frontier.is_empty() {
                break;
            }
            frontier = next_frontier.into_values().collect();
        }

        let mut hits = Vec::new();
        for (id, activation) in accumulated {
            if let Some(memory) = store.get(&id)? {
                if memory.valid_to.is_none() {
                    hits.push(LatentActivationHit {
                        memory,
                        activation: activation.activation,
                        depth: activation.depth,
                        path: activation.path,
                    });
                }
            }
        }

        hits.sort_by(compare_latent_hits);
        hits.truncate(limit);
        Ok(hits)
    }
}

impl Default for LatentActivationProbe {
    fn default() -> Self {
        Self::new(DEFAULT_SCALE, DEFAULT_CAP)
    }
}

#[derive(Debug, Clone)]
struct FrontierNode {
    id: String,
    activation: f32,
    path_activation: f32,
    path: Vec<String>,
}

#[derive(Debug, Clone)]
struct AccumulatedActivation {
    activation: f32,
    depth: usize,
    path_activation: f32,
    path: Vec<String>,
}

fn update_accumulated(
    accumulated: &mut HashMap<String, AccumulatedActivation>,
    target: &str,
    propagated: f32,
    depth: usize,
    path: &[String],
    cap: f32,
) {
    let entry = accumulated
        .entry(target.to_string())
        .or_insert_with(|| AccumulatedActivation {
            activation: 0.0,
            depth,
            path_activation: propagated,
            path: path.to_vec(),
        });
    entry.activation = (entry.activation + propagated).min(cap);
    if is_better_path(
        propagated,
        depth,
        path,
        entry.path_activation,
        entry.depth,
        &entry.path,
    ) {
        entry.depth = depth;
        entry.path_activation = propagated;
        entry.path = path.to_vec();
    }
}

fn update_frontier(
    frontier: &mut HashMap<String, FrontierNode>,
    target: &str,
    propagated: f32,
    path: &[String],
    cap: f32,
) {
    let entry = frontier
        .entry(target.to_string())
        .or_insert_with(|| FrontierNode {
            id: target.to_string(),
            activation: 0.0,
            path_activation: propagated,
            path: path.to_vec(),
        });
    entry.activation = (entry.activation + propagated).min(cap);
    if is_better_path(
        propagated,
        path.len().saturating_sub(1),
        path,
        entry.path_activation,
        entry.path.len().saturating_sub(1),
        &entry.path,
    ) {
        entry.path_activation = propagated;
        entry.path = path.to_vec();
    }
}

fn normalized_seed_set(seed_ids: &[&str]) -> HashSet<String> {
    seed_ids
        .iter()
        .map(|id| id.trim())
        .filter(|id| !id.is_empty())
        .map(str::to_string)
        .collect()
}

fn compare_latent_hits(a: &LatentActivationHit, b: &LatentActivationHit) -> Ordering {
    b.activation
        .partial_cmp(&a.activation)
        .unwrap_or(Ordering::Equal)
        .then_with(|| a.depth.cmp(&b.depth))
        .then_with(|| a.memory.id.cmp(&b.memory.id))
}

fn is_better_path(
    candidate_activation: f32,
    candidate_depth: usize,
    candidate_path: &[String],
    current_activation: f32,
    current_depth: usize,
    current_path: &[String],
) -> bool {
    candidate_activation
        .partial_cmp(&current_activation)
        .unwrap_or(Ordering::Equal)
        .then_with(|| current_depth.cmp(&candidate_depth))
        .then_with(|| current_path.cmp(candidate_path))
        == Ordering::Greater
}

fn sanitize_non_negative(value: f32, fallback: f32) -> f32 {
    if value.is_finite() {
        value.max(0.0)
    } else {
        fallback
    }
}

fn sanitize_unit(value: f32, fallback: f32) -> f32 {
    if value.is_finite() {
        value.clamp(0.0, 1.0)
    } else {
        fallback
    }
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

    fn assert_close(actual: f32, expected: f32) {
        assert!(
            (actual - expected).abs() < 1e-6,
            "expected {expected}, got {actual}"
        );
    }

    #[test]
    fn latent_probe_returns_direct_hidden_targets() {
        let mut store = Store::open_in_memory().unwrap();
        let seed = add(&mut store, "forgot morning water");
        let target = add(&mut store, "mood affects commute attention");
        store.update_edge(&seed, &target, 2.0).unwrap();

        let probe = LatentActivationProbe::new(0.05, 0.25);
        let hits = probe.activate(&store, &[&seed], 10).unwrap();

        assert_eq!(hits.len(), 1);
        assert_eq!(hits[0].memory.id, target);
        assert_close(hits[0].activation, 0.1);
        assert_eq!(hits[0].depth, 1);
        assert_eq!(hits[0].path, vec![seed, target]);
    }

    #[test]
    fn latent_probe_spreads_activation_across_decayed_steps() {
        let mut store = Store::open_in_memory().unwrap();
        let seed = add(&mut store, "forgot morning water");
        let mood = add(&mut store, "bad mood before work");
        let commute = add(&mut store, "inattention while riding");
        store.update_edge(&seed, &mood, 2.0).unwrap();
        store.update_edge(&mood, &commute, 2.0).unwrap();

        let probe = LatentActivationProbe::with_config(0.05, 0.25, 2, 0.5, 10);
        let hits = probe.activate(&store, &[&seed], 10).unwrap();

        let mood_hit = hits.iter().find(|hit| hit.memory.id == mood).unwrap();
        let commute_hit = hits.iter().find(|hit| hit.memory.id == commute).unwrap();
        assert_close(mood_hit.activation, 0.1);
        assert_eq!(mood_hit.depth, 1);
        assert_close(commute_hit.activation, 0.005);
        assert_eq!(commute_hit.depth, 2);
        assert_eq!(
            commute_hit.path,
            vec![seed.clone(), mood.clone(), commute.clone()]
        );
    }

    #[test]
    fn latent_probe_excludes_seed_cycles_and_inactive_targets() {
        let mut store = Store::open_in_memory().unwrap();
        let seed = add(&mut store, "seed");
        let target = add(&mut store, "target");
        let inactive = add(&mut store, "inactive");
        store.update_edge(&seed, &target, 2.0).unwrap();
        store.update_edge(&target, &seed, 2.0).unwrap();
        store.update_edge(&target, &inactive, 2.0).unwrap();
        store.invalidate(&inactive, "test").unwrap();

        let probe = LatentActivationProbe::with_config(0.05, 0.25, 3, 0.5, 10);
        let hits = probe.activate(&store, &[&seed], 10).unwrap();

        assert_eq!(hits.len(), 1);
        assert_eq!(hits[0].memory.id, target);
        assert!(!hits.iter().any(|hit| hit.memory.id == seed));
        assert!(!hits.iter().any(|hit| hit.memory.id == inactive));
    }
}
