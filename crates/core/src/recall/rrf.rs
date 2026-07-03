//! Reciprocal Rank Fusion: the simplest, most reliable hybrid-search fusion.
//!
//! For each input ranking the contribution of a document is `1 / (k + rank)`,
//! where rank is 1-indexed. Per-branch raw scores never cross-pollute; only
//! ranks matter, which makes RRF robust to score-scale differences between
//! BM25, cosine distance, and entity hit counts.
//!
//! Reference: Cormack, Clarke, Buettcher 2009.

use serde::{Deserialize, Serialize};
use std::cmp::Ordering;
use std::collections::HashMap;

/// k=60 is the standard from the original RRF paper; small k overweights
/// the very top, large k flattens too much.
pub const DEFAULT_RRF_K: f64 = 60.0;

#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
pub struct RrfBranchWeights {
    pub fts: f64,
    pub entity: f64,
    pub vector: f64,
}

impl Default for RrfBranchWeights {
    fn default() -> Self {
        Self {
            fts: 1.0,
            entity: 1.0,
            vector: 1.0,
        }
    }
}

impl RrfBranchWeights {
    pub const fn new(fts: f64, entity: f64, vector: f64) -> Self {
        Self {
            fts,
            entity,
            vector,
        }
    }

    pub fn sanitized(self) -> Self {
        Self {
            fts: sanitize_weight(self.fts),
            entity: sanitize_weight(self.entity),
            vector: sanitize_weight(self.vector),
        }
    }
}

pub struct RrfInput<'a> {
    pub name: &'a str,
    /// IDs in descending order of relevance for this branch.
    pub ids: &'a [String],
    /// Branch weight applied to every rank contribution.
    pub weight: f64,
}

/// Returns `(id, fused_score, source_branches)` sorted by fused_score desc.
/// Each id appears at most once even if multiple branches return it.
pub fn rrf_fuse(branches: &[RrfInput<'_>], k: f64) -> Vec<(String, f64, Vec<&'static str>)> {
    let k = sanitize_k(k);
    let mut scores: HashMap<String, f64> = HashMap::new();
    let mut sources: HashMap<String, Vec<&'static str>> = HashMap::new();

    for branch in branches {
        // Re-borrow the &'static branch name. We expect callers to pass
        // string literals (handled by accepting &'a str + coercion below).
        let name: &'static str = static_name(branch.name);
        let weight = sanitize_weight(branch.weight);
        for (i, id) in branch.ids.iter().enumerate() {
            let rank = (i + 1) as f64;
            let contribution = weight / (k + rank);
            *scores.entry(id.clone()).or_insert(0.0) += contribution;
            sources.entry(id.clone()).or_default().push(name);
        }
    }

    let mut out: Vec<(String, f64, Vec<&'static str>)> = scores
        .into_iter()
        .map(|(id, s)| {
            let src = sources.remove(&id).unwrap_or_default();
            (id, s, src)
        })
        .collect();
    out.sort_by(
        |a, b| match b.1.partial_cmp(&a.1).unwrap_or(Ordering::Equal) {
            Ordering::Equal => a.0.cmp(&b.0),
            other => other,
        },
    );
    out
}

pub fn sanitize_k(k: f64) -> f64 {
    if k.is_finite() && k >= 0.0 {
        k
    } else {
        DEFAULT_RRF_K
    }
}

pub fn sanitize_weight(weight: f64) -> f64 {
    if weight.is_finite() && weight >= 0.0 {
        weight
    } else {
        1.0
    }
}

/// Map well-known branch names to their `'static` form so callers don't
/// have to fiddle with lifetimes. Unknown names fall back to "other".
fn static_name(name: &str) -> &'static str {
    match name {
        "fts" => "fts",
        "entity" => "entity",
        "vector" => "vector",
        _ => "other",
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn ids(items: &[&str]) -> Vec<String> {
        items.iter().map(|s| s.to_string()).collect()
    }

    #[test]
    fn single_branch_preserves_order() {
        let a = ids(&["x", "y", "z"]);
        let fused = rrf_fuse(
            &[RrfInput {
                name: "fts",
                ids: &a,
                weight: 1.0,
            }],
            DEFAULT_RRF_K,
        );
        let order: Vec<&str> = fused.iter().map(|(id, _, _)| id.as_str()).collect();
        assert_eq!(order, vec!["x", "y", "z"]);
    }

    #[test]
    fn three_branches_promote_shared_doc() {
        // "shared" is rank 3 in fts, rank 2 in entity, rank 1 in vector ->
        // should beat any doc that only appears in one branch.
        let fts = ids(&["a", "b", "shared", "c"]);
        let entity = ids(&["d", "shared"]);
        let vector = ids(&["shared", "e"]);
        let fused = rrf_fuse(
            &[
                RrfInput {
                    name: "fts",
                    ids: &fts,
                    weight: 1.0,
                },
                RrfInput {
                    name: "entity",
                    ids: &entity,
                    weight: 1.0,
                },
                RrfInput {
                    name: "vector",
                    ids: &vector,
                    weight: 1.0,
                },
            ],
            DEFAULT_RRF_K,
        );
        let top = &fused[0];
        assert_eq!(top.0, "shared");
        let mut srcs = top.2.clone();
        srcs.sort();
        assert_eq!(srcs, vec!["entity", "fts", "vector"]);
    }

    #[test]
    fn empty_branches_yield_empty() {
        let fused = rrf_fuse(&[], DEFAULT_RRF_K);
        assert!(fused.is_empty());
    }

    #[test]
    fn vector_only_doc_still_makes_topk() {
        // Doc appears only in vector but at rank 1 -- must still surface.
        let fts: Vec<String> = ids(&["a", "b"]);
        let entity: Vec<String> = ids(&["c"]);
        let vector: Vec<String> = ids(&["only-vec"]);
        let fused = rrf_fuse(
            &[
                RrfInput {
                    name: "fts",
                    ids: &fts,
                    weight: 1.0,
                },
                RrfInput {
                    name: "entity",
                    ids: &entity,
                    weight: 1.0,
                },
                RrfInput {
                    name: "vector",
                    ids: &vector,
                    weight: 1.0,
                },
            ],
            DEFAULT_RRF_K,
        );
        assert!(fused.iter().any(|(id, _, _)| id == "only-vec"));
    }

    #[test]
    fn vector_weight_changes_ranking() {
        let fts = ids(&["a", "fts-only"]);
        let entity = ids(&["entity-only"]);
        let vector = ids(&["vector-top", "vector-follower"]);

        let balanced = rrf_fuse(
            &[
                RrfInput {
                    name: "fts",
                    ids: &fts,
                    weight: 1.0,
                },
                RrfInput {
                    name: "entity",
                    ids: &entity,
                    weight: 1.0,
                },
                RrfInput {
                    name: "vector",
                    ids: &vector,
                    weight: 1.0,
                },
            ],
            DEFAULT_RRF_K,
        );
        assert_eq!(balanced.first().map(|(id, _, _)| id.as_str()), Some("a"));

        let weighted = rrf_fuse(
            &[
                RrfInput {
                    name: "fts",
                    ids: &fts,
                    weight: 1.0,
                },
                RrfInput {
                    name: "entity",
                    ids: &entity,
                    weight: 1.0,
                },
                RrfInput {
                    name: "vector",
                    ids: &vector,
                    weight: 3.0,
                },
            ],
            DEFAULT_RRF_K,
        );
        assert_eq!(
            weighted.first().map(|(id, _, _)| id.as_str()),
            Some("vector-top")
        );
    }
}
