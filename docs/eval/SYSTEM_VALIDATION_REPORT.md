# System Validation Report

Date: 2026-07-02

Status: scoped validation passed.

This report answers only the three system-validation questions. It includes a
small LongMemEval / DMR smoke run, but does not claim that full LongMemEval,
official DMR, hosted Graphiti, hosted Mem0, or a live Letta endpoint have been
fully measured.

## 1. Is The System Stable?

Answer: yes for the exported cognitive-session fixture and internal evaluation
surface.

Evidence:

- `cargo fmt --all -- --check` passed.
- `cargo test -p synapse-eval` passed with `40 passed; 0 failed`.
- `cargo bench -p synapse-eval --bench exported_cognitive_session` reported:

```json
{
  "RecallAt10": 1.0,
  "HebbianConsistency": 1.0,
  "CognitiveTraceDominance": 1.0
}
```

The King Synapse external harness was then run five times against the same
fixture. Every run produced the same scored behavior:

| Metric | Result |
| --- | ---: |
| Visible seed recall | 8/8 in every run |
| Hidden influence retrieval | 8/8 in every run |
| Dominant trace selection | 8/8 in every run |
| Suppressed alternatives visible | 8/8 in every run |
| Evidence path availability | 8/8 in every run |
| Future continuation | 8/8 in every run |
| Reinforcement isolation | 8/8 in every run |

Observed mean-latency range for the five repeatability runs:

```text
4.52 ms .. 4.70 ms
```

Stability conclusion: stable on the current deterministic cognitive fixture.
The LongMemEval / DMR smoke path can run and report aggregate metrics, but
full long-memory stability is not yet proven.

## 2. Is The System Internally Consistent?

Answer: yes for the validated fixture.

The current validation did not observe contradiction between recall, latent
trace evidence, prediction, or reinforcement isolation:

- visible recall found the visible seed in every chain;
- hidden influence retrieval found the intended hidden memory in every chain;
- dominant trace selection matched the intended hidden influence in every
  chain;
- suppressed alternatives remained visible instead of disappearing from the
  report;
- evidence paths were available for every chain;
- future continuation was found for every chain;
- reinforcement stayed isolated after the report and did not mutate the
  already-scored result.

Consistency conclusion: the system's main cognitive-memory layers agree with
each other under the exported cognitive-session fixture. This is enough to say
the core design is coherent in the validated scope, but not enough to claim
long-horizon real-world consistency yet.

## 3. Does King Synapse Expose More Cognitive-Trace Ability?

Answer: yes in the checked external-comparison fixture.

The latest external comparison measured King Synapse, Graphiti/Zep local Kuzu
mode, and Mem0 OSS with DeepSeek plus local Qdrant. Letta remained
`not_configured`: `letta-client 1.12.1` is installed, but no
`LETTA_API_KEY`, `LETTA_BASE_URL`, or local endpoint is configured.

| System | Visible | Hidden | Dominant trace | Suppressed alternatives | Evidence paths | Future continuation | Reinforcement isolation |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| King Synapse | 8/8 | 8/8 | 8/8 | 8/8 | 8/8 | 8/8 | 8/8 |
| Graphiti/Zep local | 8/8 | 8/8 | unsupported | unsupported | 8/8 | unsupported | unsupported |
| Mem0 OSS + DeepSeek | 7/8 | 8/8 | unsupported | unsupported | unsupported | unsupported | unsupported |
| Letta | not configured | not configured | not configured | not configured | not configured | not configured | not configured |

Comparative conclusion: King Synapse currently exposes the richest
cognitive-trace surface in this fixture. Graphiti/Zep can surface graph-style
evidence paths in local deterministic mode, but the adapter does not expose
dominant/suppressed trace competition, future continuation, or reinforcement
isolation. Mem0 retrieves every hidden influence and seven of eight visible
seeds in this run, but does not expose path evidence, trace competition,
prediction, or reinforcement isolation through the measured adapter.

This is not a claim that King Synapse is better at every long-memory task. It
is a narrower claim: for the cognitive-trace behavior this project is designed
to validate, King Synapse exposes more inspectable structure than the measured
competitor adapters.

## Final Judgment

King Synapse is valid enough to leave feature-building mode and remain in
system validation mode.

The project has crossed the basic bar for:

1. stable deterministic fixture behavior;
2. internally consistent recall, trace, prediction, and reinforcement reports;
3. visible comparative value on cognitive-trace introspection.
4. fixed benchmark and golden replay baselines for the current Phase 6 scope.

Long-memory 50-sample evidence now exists across three retrieval modes:

| Dataset | Sample | Baseline Recall@10 | Vector Recall@10 | Vector + reranker Recall@10 |
| --- | ---: | ---: | ---: | ---: |
| LongMemEval cleaned | 50/50 | 0.503 | 0.663 | 0.590 |
| DMR candidate MSC-Self-Instruct | 50/50 | 0.188 | 0.438 | 0.584 |

The 50-sample reports are:

- `crates/eval/reports/longmem-50-validation.json`
- `crates/eval/reports/dmr-50-validation.json`
- `docs/eval/VALIDATION_LONGMEM_50.md`
- `docs/eval/VALIDATION_DMR_50.md`
- `docs/eval/FAILURE_ANALYSIS.md`

They exclude raw third-party records from the committed reports. The current
read is: vector search improves both LongMemEval and DMR. Reranking improves
DMR substantially and improves LongMemEval top-1 / MRR, but it can reduce
LongMemEval top-10 recall versus vector-only.

Failure analysis now shows:

| Dataset | Final-mode top 1 | Ranking failures | Retrieval misses | Pre-eval missing/chunk rows |
| --- | ---: | ---: | ---: | ---: |
| LongMemEval 50 | 18 | 26 | 6 | 0 |
| DMR 50 | 16 | 29 | 5 | 278 |

The dominant evaluated failure mode is ranking. The dominant DMR data issue is
mapping/chunking: 278 candidate rows were skipped before evaluation because the
expected answer text was not found in generated memory chunks.

DMR mapping audit status:

- `docs/eval/DMR_MAPPING_AUDIT.md` and
  `crates/eval/reports/dmr-mapping-audit.json` audit all 500 candidate rows.
- Every audited row generated five memory chunks.
- The current strict answer-string rule accepted 82 rows and skipped 418 rows.
- Among skipped rows, 241 matched after punctuation-insensitive exact matching
  and 362 had all significant answer tokens in one chunk.
- The DMR skip is now localized to mapping/scoring strictness, not empty chunk
  generation or a broad architecture failure.
- A punctuation-normalized candidate rerun is recorded in
  `docs/eval/VALIDATION_DMR_50_PUNCTUATION.md` and
  `crates/eval/reports/dmr-50-punctuation-validation.json`; it reduced
  pre-evaluation skips before 50 valid examples from `278` to `31`.

Benchmark baseline status:

- `docs/eval/BENCHMARK_BASELINE.md` fixes the recall, algorithm, and
  long-memory baseline numbers.
- `docs/eval/GOLDEN_DATASET.md` fixes the current replay registry, including
  20 cognitive trace replays and 20 prediction replays.
- `crates/eval/reports/phase6-benchmark-baseline.json` stores the
  machine-readable baseline gates.
- `crates/eval/datasets/regression/golden-manifest.json` records dataset
  paths, source revisions, hashes, sample sizes, and raw-data policy.

Performance analysis status:

- `docs/eval/PERFORMANCE_ANALYSIS.md` records the current Phase 6 latency
  evidence.
- Lightweight replay baselines stay below `4.2 ms` P95.
- In the 50-sample long-memory reports, vector mode adds much less P50 latency
  than reranking. Reranking adds about `698 ms` P50 on LongMemEval and about
  `541 ms` P50 on DMR over vector mode.
- Memory, CPU, embedding sub-stage, vector-search sub-stage, and reranker
  sub-stage timing are not independently instrumented yet.

The project has not yet crossed the bar for:

1. official DMR benchmark results;
2. hosted Graphiti or hosted Mem0 comparison;
3. live Letta endpoint measurement;
4. sub-stage performance instrumentation;
5. final DMR scoring-policy adoption beyond candidate punctuation matching;
6. production-readiness claims.

GPU validation status:

- CUDA execution-provider selection is wired through
  `KING_SYNAPSE_ACCELERATOR=cuda` and the LongMemEval / DMR runner now exposes
  `--accelerator cuda`.
- The local CUDA smoke check passed after installing CUDA 12 runtime DLLs into
  a user cache outside the repository.
- The 50-sample LongMemEval and DMR validation runs completed on CUDA with
  embedding batch `32`, embedding max length `256`, reranker batch `32`, and
  reranker max length `256`.
- Details are recorded in `docs/eval/GPU_VALIDATION_2026-07-02.md`.

Next required action: keep feature growth frozen and investigate the remaining
validation boundaries: DMR mapping/chunk skips, final candidate ranking, and
live/hosted external runs.
