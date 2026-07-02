# Regression Datasets

This directory is reserved for Phase 6 replay fixtures.

The current registry is `golden-manifest.json`. It fixes the committed recall
fixtures, the 20-chain `expanded_cognitive_replay.toml` fixture, and sanitized
LongMemEval / DMR reports for third-party data that must not be committed raw.

Use this directory for future frozen replay datasets only. Synthetic stress
sets belong in `crates/eval/datasets/synthetic/`; raw external mirrors belong
outside the repository unless redistribution is explicitly allowed.
