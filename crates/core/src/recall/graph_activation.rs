use crate::error::Result;
use crate::recall::{BoosterContext, RecallBooster, RecallHit};
use std::collections::HashMap;

const DEFAULT_SCALE: f32 = 0.05;
const DEFAULT_CAP: f32 = 0.15;

pub struct GraphActivationBooster {
    scale: f32,
    cap: f32,
}

impl GraphActivationBooster {
    pub fn new(scale: f32, cap: f32) -> Self {
        Self {
            scale: sanitize_non_negative(scale, DEFAULT_SCALE),
            cap: sanitize_non_negative(cap, DEFAULT_CAP),
        }
    }

    pub fn scale(&self) -> f32 {
        self.scale
    }

    pub fn cap(&self) -> f32 {
        self.cap
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
        if hits.len() < 2 || self.scale == 0.0 || self.cap == 0.0 {
            return Ok(());
        }

        let ids: Vec<&str> = hits.iter().map(|hit| hit.memory.id.as_str()).collect();
        let edges = ctx.store.edge_weights_between(&ids, &ids)?;
        if edges.is_empty() {
            return Ok(());
        }

        let mut bonuses = HashMap::new();
        for (_source, target, weight) in edges {
            if weight <= 0.0 || !weight.is_finite() {
                continue;
            }
            let bonus = (weight * self.scale).min(self.cap);
            *bonuses.entry(target).or_insert(0.0) += bonus;
        }

        for hit in hits {
            if let Some(bonus) = bonuses.get(&hit.memory.id) {
                hit.activation_bonus = (hit.activation_bonus + bonus).min(self.cap);
            }
        }
        Ok(())
    }
}

fn sanitize_non_negative(value: f32, fallback: f32) -> f32 {
    if value.is_finite() {
        value.max(0.0)
    } else {
        fallback
    }
}
