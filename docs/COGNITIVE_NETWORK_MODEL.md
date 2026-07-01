# Cognitive Network Algorithm Model

Status: **Design Model**

This document translates the product idea behind King Synapse into an
algorithmic model. The core claim is simple: a thought is not selected from a
flat list. It emerges from a network of memories, body state, emotion, social
context, tools, objects, goals, and hidden associations.

## Human Model

A person can be modeled as an active graph:

- every memory, event, object, feeling, goal, and learned rule is a node;
- every association is a weighted directed edge;
- the current query or situation activates a few visible seed nodes;
- activation spreads through hidden edges;
- body state and goals modulate the hidden activation;
- many thought candidates compete at once;
- the strongest candidate becomes dominant;
- weaker candidates are still present as suppressed alternatives;
- explicit replay or use strengthens the path for future activation.

Example:

```text
forgot morning water
  -> worse mood
  -> lower commute attention
  -> riding mistake risk
```

The system does not need to pretend this chain is certain. It only needs to
make the chain inspectable, scoreable, and learnable.

## Current Implementation Mapping

| Human concept | King Synapse surface |
| --- | --- |
| Visible thought or spoken sentence | `RecallQuery` and `RecallHit` |
| Prior learned memory | `Memory` node in Store |
| Association between memories | persisted `memory_edges` |
| Hidden/subconscious influence | `LatentActivationProbe` |
| Body/emotional state | `LatentActivationContext.state_terms` |
| Goal or task pressure | `LatentActivationContext.goal_terms` |
| Many possible thoughts | cognitive trace candidate pool |
| Dominant thought | `CognitiveTraceReport.dominant` |
| Suppressed thoughts | `CognitiveTraceReport.suppressed` |
| Learning from repeated co-occurrence | Hebbian reinforcement |

This keeps the Store simple. Store persists memories and edges. Recall and
trace layers decide how activation is interpreted.

## Algorithm Shape

The cognitive trace algorithm can be described as:

```text
input:
  query text
  optional state terms
  optional goal terms

1. visible = RecallEngine(query)
2. seeds = top visible memory ids
3. context = explicit context + auto-derived query context
4. latent = spread activation from seeds through memory_edges
5. candidates = merge visible and latent memories
6. score each candidate:
     visible_component = normalized visible score
     latent_component = normalized hidden activation
     context_modulation = state/goal matches on latent path
     competition_score =
       visible_component * visible_weight
       + latent_component * latent_weight
7. dominant = highest competition_score
8. suppressed = next candidates, each with inhibition = dominant - candidate
9. optional reinforcement:
     after the report is produced, reinforce visible seeds <-> dominant
```

The important boundary is step 9. Learning happens after the trace report is
computed, so reinforcement cannot affect the current ranking. It only changes
future activation.

## Subconscious Influence

In this project, "subconscious" means:

- the memory was not directly recalled by visible query text;
- it was reached through hidden weighted edges;
- it was strengthened or weakened by state and goal context;
- it can become dominant even when visible recall found something else;
- it remains explainable through an activation path.

That is why `LatentActivationProbe` is deliberately separate from
`RecallEngine`. Recall answers "what directly matches this query?" Trace asks
"what hidden influence might be steering this moment?"

## Prediction

Human prediction should be implemented as probabilistic trace continuation, not
as deterministic mind reading.

Near-term prediction model:

```text
current trace
  -> dominant candidate
  -> outgoing weighted edges
  -> state/goal modulation
  -> next likely candidates
```

The output should be ranked possible continuations with paths and scores. It
should not claim certainty. A good prediction report says:

- which memory or state triggered the prediction;
- which edges carried the activation;
- which candidate won;
- which candidates were suppressed;
- what evidence would strengthen or weaken the prediction next time.

## Design Rules

1. Do not make Store interpret psychology. Store remains persistence.
2. Do not change frozen `RecallHit` fields to add cognitive data.
3. Do not let boosters create new recall candidates.
4. Keep latent/subconscious influence inspectable as a separate report.
5. Run reinforcement only after the report that caused it.
6. Treat prediction as ranked uncertainty, not truth.
7. Every new cognitive claim needs a benchmark or manual transcript.

## Next Algorithm Extension

The next production-grade extension should be a predictive trace report:

```text
CognitiveTraceReport
  -> dominant candidate
  -> continuation activation
  -> ranked next-candidate report
```

Suggested acceptance metric:

```text
CognitivePredictionPrecision
```

It should measure whether the expected next hidden influence appears in the
top-k continuation candidates across long-horizon sessions.

Implemented baseline: `CognitiveTraceProbe::predict_continuation()` starts from
the dominant trace candidate and returns ranked continuation candidates. The
`predictive_trace` benchmark uses `RecallAt10` to verify that the expected next
hidden influence appears in the continuation set.
