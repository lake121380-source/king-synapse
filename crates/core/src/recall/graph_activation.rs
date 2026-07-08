use crate::error::Result;
use crate::recall::{BoosterContext, RecallBooster, RecallHit};
use std::collections::HashMap;

const DEFAULT_SCALE: f32 = 0.02; // Small: activation is a tie-breaker, not ranking override
const DEFAULT_CAP: f32 = 0.05; // Max bonus ~5% of score range, preserves reranker dominance
const DEFAULT_DECAY: f32 = 0.5;
const DEFAULT_STEPS: usize = 1;

pub struct GraphActivationBooster {
    scale: f32,
    cap: f32,
    decay: f32,
    steps: usize,
}

impl GraphActivationBooster {
    pub fn new(scale: f32, cap: f32) -> Self {
        Self::with_spreading(scale, cap, DEFAULT_STEPS, DEFAULT_DECAY)
    }

    pub fn with_spreading(scale: f32, cap: f32, steps: usize, decay: f32) -> Self {
        Self {
            scale: sanitize_non_negative(scale, DEFAULT_SCALE),
            cap: sanitize_non_negative(cap, DEFAULT_CAP),
            decay: sanitize_unit(decay, DEFAULT_DECAY),
            steps: steps.max(1),
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
}

impl Default for GraphActivationBooster {
    fn default() -> Self {
        Self::new(DEFAULT_SCALE, DEFAULT_CAP)
    }
}

impl RecallBooster for GraphActivationBooster {
    fn name(&self) -> &'static str {
        "graph_activation"
    }

    fn apply(&self, ctx: &BoosterContext<'_>, hits: &mut [RecallHit]) -> Result<()> {
        if hits.len() < 2 || self.scale == 0.0 || self.cap == 0.0 || self.decay == 0.0 {
            return Ok(());
        }

        let ids: Vec<&str> = hits.iter().map(|hit| hit.memory.id.as_str()).collect();
        let edges = ctx.store.edge_weights_between(&ids, &ids)?;
        if edges.is_empty() {
            return Ok(());
        }

        let adjacency = adjacency_map(edges);
        let mut frontier = initial_activation(hits);
        let mut bonuses = HashMap::new();

        for step in 0..self.steps {
            let attenuation = self.decay.powi(step as i32);
            let mut next_frontier = HashMap::new();

            for (source, source_activation) in &frontier {
                let Some(targets) = adjacency.get(source) else {
                    continue;
                };
                for (target, weight) in targets {
                    let propagated = source_activation * weight * self.scale * attenuation;
                    if propagated <= 0.0 || !propagated.is_finite() {
                        continue;
                    }
                    *bonuses.entry(target.clone()).or_insert(0.0) += propagated;
                    *next_frontier.entry(target.clone()).or_insert(0.0) += propagated;
                }
            }

            if next_frontier.is_empty() {
                break;
            }
            frontier = next_frontier;
        }

        for hit in hits {
            if let Some(bonus) = bonuses.get(&hit.memory.id) {
                // Soft clamping via sigmoid: allows wider spread than hard cap.
                // bonus maps to [0, cap) asymptotically, preserving ordering.
                let raw = hit.activation_bonus + bonus;
                let sigmoid_factor = 1.0 / (1.0 + (-raw * 4.0 / self.cap).exp());
                hit.activation_bonus = self.cap * sigmoid_factor;
            }
        }
        Ok(())
    }
}

fn adjacency_map(edges: Vec<(String, String, f32)>) -> HashMap<String, Vec<(String, f32)>> {
    let mut adjacency: HashMap<String, Vec<(String, f32)>> = HashMap::new();
    for (source, target, weight) in edges {
        if weight <= 0.0 || !weight.is_finite() {
            continue;
        }
        adjacency.entry(source).or_default().push((target, weight));
    }
    adjacency
}

fn initial_activation(hits: &[RecallHit]) -> HashMap<String, f32> {
    hits.iter()
        .map(|hit| (hit.memory.id.clone(), 1.0))
        .collect()
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
