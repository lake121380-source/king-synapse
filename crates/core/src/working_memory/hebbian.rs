use crate::working_memory::ReflectionEvent;

#[derive(Debug, Clone, PartialEq)]
pub struct EdgeUpdatePlan {
    pub source: String,
    pub target: String,
    pub weight_delta: f32,
}

pub trait HebbianReinforcementEngine {
    fn reinforce(&self, event: &ReflectionEvent) -> Vec<EdgeUpdatePlan>;
}

pub struct NoOpHebbianReinforcementEngine;

impl HebbianReinforcementEngine for NoOpHebbianReinforcementEngine {
    fn reinforce(&self, _event: &ReflectionEvent) -> Vec<EdgeUpdatePlan> {
        Vec::new()
    }
}
