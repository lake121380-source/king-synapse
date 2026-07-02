# GPU Validation 2026-07-02

Status: passed for Phase 6 local validation.

This note records the local GPU setup used for the 50-sample LongMemEval and
DMR validation runs. It is infrastructure evidence, not a benchmark result by
itself.

## What Changed

- `KING_SYNAPSE_ACCELERATOR=cuda` routes fastembed model inference through the
  ONNX Runtime CUDA execution provider on Windows validation builds.
- The LongMemEval / DMR runner accepts `--accelerator cuda` and automatically
  prepends local NVIDIA CUDA runtime wheel DLL directories when they exist under
  the user cache.
- The runner now records model inference parameters:
  `embed-batch-size`, `embed-max-length`, `rerank-batch-size`, and
  `rerank-max-length`.
- `KING_SYNAPSE_ACCELERATOR=cpu`, `none`, `off`, or an empty value keeps the
  previous CPU behavior.

## Local Runtime

CUDA Toolkit was not installed system-wide. Instead, the required CUDA 12
runtime DLLs were installed into a user cache outside the repository through
NVIDIA Python wheels:

```text
%LOCALAPPDATA%\king-synapse\cuda-runtime-py313
```

Installed wheel families:

- `nvidia-cuda-runtime-cu12`
- `nvidia-cuda-nvrtc-cu12`
- `nvidia-cublas-cu12`
- `nvidia-cudnn-cu12`
- `nvidia-cufft-cu12`
- `nvidia-curand-cu12`
- `nvidia-cusolver-cu12`
- `nvidia-cusparse-cu12`
- `nvidia-nvjitlink-cu12`

The committed reports do not record the absolute local runtime path.

## Verified

```powershell
cargo fmt --all
cargo check -p synapse-core
```

Result: passed.

CUDA smoke result:

```text
dataset:        crates/eval/datasets/basic.toml
vectors:        true
rerank:         true
Recall@10:      1.000
MRR@10:         1.000
```

Temporary smoke reports were deleted.

## 50-Sample Runs

The completed CUDA validation reports are:

- `crates/eval/reports/longmem-50-validation.json`
- `crates/eval/reports/dmr-50-validation.json`

Fixed GPU inference configuration:

| Parameter | Value |
| --- | ---: |
| CUDA device | 0 |
| Embed batch size | 32 |
| Embed max length | 256 |
| Rerank batch size | 32 |
| Rerank max length | 256 |
| Rerank pool | 50 |

## Local Machine State

- GPU detected by Windows: `NVIDIA GeForce RTX 2060`
- Driver version reported by WMI: `32.0.15.9597`
- `nvidia-smi` was not found in PATH or the checked NVIDIA program directory.
- `CUDA_PATH` was not set.
- DirectML had failed on this machine with ONNX Runtime adapter errors, so CUDA
  is the validated GPU path.

## Conclusion

The local GPU path is usable for Phase 6 validation after adding CUDA 12 runtime
DLLs from NVIDIA wheels. The 4GB GPU requires explicit embedding/reranker batch
and max-length limits; without them, LongMemEval embedding can create excessive
host memory pressure and DMR reranking can hit CUDA OOM.

