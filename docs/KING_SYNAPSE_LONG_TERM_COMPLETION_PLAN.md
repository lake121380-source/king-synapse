# King Synapse Long-Term Completion Plan

Status: M0 governance baseline pending freeze

Canonical product name: **King Synapse**

Historical/local alias: **King Recall**

Primary product surfaces: the local-first Rust core, the `kr` CLI, and the
stdio MCP server.

## 1. Completion definition

The project is complete when King Synapse is a releasable, upgradeable,
recoverable, rollback-safe, cross-platform validated local memory system.
Atomic Evidence is governed as a conditional capability: a positive Phase 7.4
result may authorize a Phase 7.5 design review, while a neutral or negative
result permanently retains Atomic Evidence as a diagnostic-only layer. Runtime
activation of Atomic Evidence is not required for the project itself to be
complete.

The mandatory product scope is:

- the local memory engine;
- SQLite-backed storage with migration, backup, restore, and recovery evidence;
- deterministic recall, trace, prediction, and reinforcement boundaries;
- the `kr` command-line interface;
- the stdio MCP server;
- reproducible evaluation and audit tooling;
- release, upgrade, rollback, security, and compatibility documentation.

The following are not mandatory for the first complete release and remain
closed unless a later Productization Gate explicitly authorizes them:

- a Web user interface;
- a hosted HTTP API;
- Docker as a supported product surface;
- hosted SaaS operation;
- autonomous memory or lesson writes;
- a default-on Atomic or Cognitive ranking policy.

## 2. Non-negotiable governance

Every stage follows these rules:

1. Frozen artifacts are write-once. A semantic change requires a successor
   version that retains the previous artifact and result.
2. Every decision-bearing artifact has exact-file SHA-256 lineage.
3. Replay outputs use deterministic canonical serialization.
4. Audit logs are append-only and retain failed attempts and negative results.
5. Effect data remains sealed until its protocol, sampling frame, environment,
   metrics, statistics, costs, and failure rules are frozen.
6. Phase 7.3.3-D Confirmatory data is never Phase 7.4 effect data.
7. Provider credentials, raw responses, private data, and local absolute paths
   are never committed.
8. Runtime, persistence, promotion, learning, and autonomous-write authority
   are separate and default to false.
9. A Gate pass authorizes only the exact next stage named by that Gate.
10. Neutral, negative, invalid, and unidentifiable results are authoritative
    outcomes, not invitations to tune the same version.

## 3. Current baseline

The Phase 7.3.3-D predecessor is frozen at:

```text
confirmatory_success_frozen_runtime_integration_not_authorized
```

Phase 7.4.1 has completed an eval-only Atomic Evidence shadow prototype and its
Prototype Gate. Its current next authorized stage is:

```text
freeze_phase7_4_offline_retrieval_evaluation_protocol_v1
```

The Phase 7.4 effect dataset is closed, no Phase 7.4 Provider has been called,
and Runtime Integration is not authorized.

The broader project Productization Gate remains a validation-only no-go. Phase
7.4 completion does not by itself close productization.

## 4. M0 — Governance baseline and version checkpoint

### Objective

Create a durable project completion contract and make Phase 7.4.1 replayable
from descendant Git commits.

### Required work

- freeze this plan and its machine-readable Completion Contract;
- freeze a replay-portability policy for Phase 7.4.1;
- preserve the original Phase 7.4.1 manifest and recorded execution HEAD;
- create a dedicated Phase 7.4.1 Git checkpoint;
- prove that the recorded execution HEAD is an ancestor of the checkpoint;
- prove that every frozen Phase 7.4.1 implementation byte in the checkpoint
  matches its original implementation manifest;
- allow future verification only when the checkpoint is an ancestor of the
  verifier HEAD and frozen bytes remain exact;
- freeze M0 state, readiness, audit, and receipt artifacts;
- push the Phase 7.4.1 checkpoint and M0 governance checkpoint to `origin/main`.

### Naming and version decision

`King Synapse` is the canonical product name. `King Recall` remains a local and
historical alias. The eventual completion release target is `1.0.0`, but no
Cargo version change or 1.0 claim is authorized until the Productization Gate
and release audit pass. Historical research milestone labels do not silently
change the current workspace package version.

### Exit Gate

- a fresh clone can verify all Phase 7.4.1 lineage;
- descendant commits do not invalidate replay merely because HEAD changed;
- Phase 7.4.1 and M0 have isolated Git checkpoints;
- effect data, Provider access, Runtime, storage writes, and schema changes
  remain unauthorized.

## 5. M1 — Phase 7.4.2 Offline Retrieval Protocol Freeze

### Objective

Preregister RQ1 and RQ2 before effect content is opened.

### Required protocol contents

- RQ1 Evidence Localization;
- RQ2 Unsupported or Contradictory Activation;
- Arm A Chunk Retrieval;
- Arm B Atomic Retrieval plus Evidence Reconstruction;
- Recall@K, Precision@K, MRR, and evidence-localization F1;
- unsupported activation, contradiction exposure, and supported-evidence
  recall non-inferiority;
- K, span matching, sample size, MDE, confidence intervals, and missing-data
  handling;
- a one-sided family-wise alpha of 0.05 with a frozen multiplicity procedure;
- equal-resource execution and timeout rules;
- latency, CPU, memory, storage, reconstruction-failure, and optional Provider
  cost thresholds;
- structural and realized identifiability rules;
- failure taxonomy, negative-result policy, and Final Audit protocol;
- exact environment, dependency, model, and hardware manifests.

### Exit Gate

The protocol, schemas, environment, statistical plan, leakage rules, manifests,
state, readiness, audit, and receipt are frozen while effect data remains
closed.

## 6. M2 — Dataset, Reference, and pre-effect Gates

### Objective

Create a genuinely independent Phase 7.4 evaluation substrate.

### Required sequence

1. Freeze the independent source inventory and sampling frame.
2. Select cases without viewing effect labels or arm outcomes.
3. Construct blind reviewer packets.
4. Complete independent reviews, agreement, disagreement adjudication, and
   Gold Freeze.
5. Audit case IDs, source hashes, Candidate hashes, Evidence hashes, and labels
   against Phase 7.3.3-D.
6. Run Representation, Evidence Coverage, Structural Identifiability, Leakage,
   and Dataset Opening Gates.

### Failure disposition

Any structural, leakage, or coverage failure freezes an authoritative negative
or invalid result. Effect scoring remains closed and same-version semantic
repair is not permitted.

## 7. M3 — Formal RQ1/RQ2 paired execution

### Objective

Measure whether Atomic Evidence improves retrieval localization or prevents
unsupported activation under equal resources.

### Execution requirements

- identical queries, candidate pools, cutoffs, resources, and timeouts;
- deterministic Arm A and Arm B outputs;
- canonical per-case records;
- attempt logs, failure taxonomy, and resource accounting;
- deterministic replay before analysis;
- Realized Identifiability Gate before effect scoring;
- paired analysis, power audit, multiplicity correction, non-inferiority, and
  cost/regression Gates.

No post-result change to K, matching, thresholds, inclusion, or failure rules is
allowed. RecallEngine and Runtime ranking remain unchanged.

## 8. M4 — RQ3 Competition and Reflection Evaluation

### Objective

Determine whether Atomic Evidence improves cognitive competition or reflection
without acquiring Runtime authority.

### Arms

- Arm C Existing Memory Competition;
- Arm D Memory plus Atomic Evidence shadow competition.

### Metrics

- winner correctness;
- conflict-resolution accuracy;
- harmful suppression;
- contradiction handling;
- lesson grounding;
- failure avoidance;
- future influence accuracy;
- explanation completeness.

RQ3 cannot compensate for failure of both RQ1 and RQ2 and cannot independently
authorize Runtime Integration.

## 9. M5 — Phase 7.4 Final Audit

The audit requires:

- Gate A: at least one of RQ1 or RQ2 passes under the frozen family-wise rule;
- Gate B: no severe recall, suppression, stability, or safety regression;
- Gate C: costs and operational complexity stay within preregistered bounds;
- Gate D: lineage, replay, failures, negative results, and audit all pass.

The only valid terminal dispositions are:

```text
positive_capability_transfer_phase7_5_design_review_authorized
diagnostic_value_only_runtime_integration_not_authorized
authoritative_negative_result_runtime_integration_not_authorized
```

A positive disposition authorizes only a Phase 7.5 design review.

## 10. M6 — Phase 7.5 Runtime Integration Design

This stage exists only after a positive Phase 7.4 Final Audit.

The design must be default-off, preserve the existing MemoryKind set, avoid an
initial storage migration, construct overlays on the read path, preserve a
reconstructable baseline ranking, provide a kill switch and deterministic
fallback, and separate Runtime authority from persistence authority.

Required artifacts include an RFC/ADR, compatibility audit, rollout and
rollback contracts, latency and failure budgets, and an incident taxonomy.

## 11. M7 — Runtime shadow, dogfood, and canary

The authorized progression is:

1. Runtime shadow: calculate Atomic outputs but never change user-visible
   results.
2. Explicit opt-in: expose baseline and Atomic outcomes together with a direct
   disable path.
3. Bounded canary: activate only for frozen scenarios under strict error
   budgets and automatic rollback.

Default-on behavior requires a new independent Gate.

## 12. M8 — Productization Gate closure

The existing no-go blockers must be closed or explicitly removed from public
claims:

- clear supported-task boundaries;
- documented weaknesses relative to competitors;
- prospective CPU/GPU/latency acceptance thresholds;
- published-comparable DMR evidence or narrower DMR claims;
- a stable public local demo;
- an explicit safe Runtime default policy.

The project may ship with Atomic, Cognitive ranking, reranking, and hosted
integrations experimental and default-off. Product completion does not require
a global ranking policy.

## 13. M9 — Engineering and operations hardening

Required work includes:

- Linux and Windows CI, with macOS when dependencies support it;
- workspace tests, release builds, clippy, replay, CLI smoke, and MCP smoke;
- elimination or explicitly scoped suppression of all release-blocking clippy
  warnings;
- SQLite schema versioning, migration dry-runs, backup, restore, WAL recovery,
  corruption handling, and interrupted-write tests;
- dependency and secret audits, MCP input bounds, path/permission review, a
  threat model, and `SECURITY.md`;
- empty, large, Unicode/CJK, concurrent, Provider-unavailable, disk-full,
  timeout, and interrupted-process tests;
- p50/p95/p99, CPU, RAM, GPU, cold/warm start, scale, and long-session drift
  measurements.

## 14. M10 — Release Candidate and 1.0

Before 1.0:

- product name, crate versions, tags, and release notes agree;
- `CHANGELOG.md`, `CONTRIBUTING.md`, and `SECURITY.md` exist;
- installation, upgrade, backup, restore, uninstall, and rollback are tested and
  documented;
- CLI and MCP contract snapshots pass;
- the clean-machine demo passes;
- no credentials, local paths, or prohibited raw evaluation data are present;
- release binaries have checksums;
- at least two RC cycles pass;
- README claims have exact supporting evidence;
- the Productization Gate is `go`;
- the release tag and release receipt are reproducible.

## 15. Completion matrix

| Area | Completion evidence |
| --- | --- |
| Atomic Research | Immutable positive, neutral, or negative Phase 7.4 terminal result |
| Runtime | Only Gate-authorized behavior is active; every experimental path is disableable and rollback-safe |
| Core | Store, Recall, Trace, Prediction, and Reinforcement contracts are stable |
| CLI/MCP | Parity, stable error semantics, and compatibility tests pass |
| Data | Migration, backup, restore, and corruption recovery pass |
| Quality | Workspace tests, clippy, release build, and replay pass |
| Performance | Preregistered latency and resource budgets pass |
| Security | Threat model, dependency/secret audits, and security documentation pass |
| Claims | Every README claim has evidence and an explicit boundary |
| Release | Productization Gate is `go`; RC, installation, upgrade, and rollback pass |

## 16. Scheduling rule

Estimated duration is planning information, never authority. With one primary
developer plus AI assistance, the diagnostic-only path is expected to require
approximately 18–26 weeks and the positive Runtime path approximately 26–38
weeks. Independent review, Provider access, hardware, and public-data licensing
may extend those estimates. No schedule permits a Gate to be skipped.
