# Phase 7.4.2 Source Inventory and Sampling Frame

Status: construction contract frozen before source-content authoring

## Purpose

This stage creates a content-blind inventory of Phase 7.4 case slots and freezes
the deterministic selection of formal and reserve slots before any query,
Memory text, Atomic unit, or Gold label is authored.

The entry Gate is:

```text
construct_phase7_4_independent_source_inventory_and_sampling_frame_v1
```

## Inventory

The inventory contains `240` new Phase 7.4 slots:

- eight preregistered strata;
- 30 slots per stratum;
- Phase 7.4-only case IDs;
- no query content;
- no Memory content;
- no evidence content;
- no Atomic overlay;
- no Gold or review label;
- no Provider output;
- no Phase 7.3.3-D lineage.

The case-ID format is:

```text
p74-<stratum-code>-<three-digit ordinal>
```

Stratum codes are:

| Stratum | Code |
| --- | --- |
| temporal update | `tu` |
| contradiction | `co` |
| preference evolution | `pe` |
| failure learning | `fl` |
| causal reasoning | `cr` |
| multi-entity reasoning | `me` |
| uncertainty boundary | `ub` |
| adversarial lexical overlap | `al` |

## Deterministic selection

For every slot, compute:

```text
sha256("phase7.4|7402101|" + stratum + "|" + case_id)
```

Within each stratum, sort by the hexadecimal digest ascending, then by case ID.
The first 21 slots are formal selected slots. The remaining nine are reserve
slots.

This produces:

- 168 formal selected slots;
- 72 reserve slots;
- exactly 21 selected and nine reserve slots per stratum.

Reserve slots cannot replace formal slots after any selected content is
authored or opened. They are retained only for a prospectively authorized
successor, replication, or a mechanical pre-authoring failure documented before
content creation.

## Content blindness

Selection is complete before content authoring. At this stage:

- `query_authored = false`;
- `memory_content_authored = false`;
- `evidence_content_authored = false`;
- `atomic_overlay_constructed = false`;
- `reference_review_started = false`;
- `gold_frozen = false`;
- `selected_effect_content_opened = false`.

The inventory is therefore not an effect dataset. It is a frozen namespace and
sampling decision.

## Independence

No Phase 7.3.3-D dataset, worklist, Gold, arm result, analysis, or Confirmatory
content may be loaded during construction. The `p74-` namespace and
`phase7_4_independent_v1` source namespace are new. Full text/hash leakage
analysis occurs only after new Phase 7.4 source content has been authored and
before any Reference or arm execution.

## Authoring constraints for the next stage

Each selected slot must later receive:

- one independently authored query;
- exactly ten new Memory snapshots;
- at least one support-bearing Memory;
- at least one hard distractor;
- source evidence and event identities;
- query-blind Atomic segmentation;
- no copied or paraphrased Phase 7.3.3-D effect content.

Content authoring must follow a separately frozen authoring contract. It cannot
start merely because a slot was selected.

## Failure policy

This stage fails authoritatively if:

- slot IDs are duplicated;
- any stratum count differs from 30;
- the selected count differs from 21 in any stratum;
- the reserve count differs from nine in any stratum;
- the sampling digest or ordering fails deterministic replay;
- any content or label field is populated;
- Phase 7.3.3-D lineage is used;
- Provider, Runtime, Store, RecallEngine, or write authority is claimed.

Same-version semantic repair is not allowed after freeze.

## Disposition

Successful freeze authorizes only:

```text
freeze_phase7_4_selected_source_authoring_contract_v1
```

It does not authorize source-content authoring until that successor contract is
frozen. It does not authorize Gold review, dataset opening, arm execution,
effect scoring, Provider access, Runtime Integration, productization, or
release.
