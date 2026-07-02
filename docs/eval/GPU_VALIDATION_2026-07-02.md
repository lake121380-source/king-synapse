# GPU Validation 2026-07-02

Status: blocked by local CUDA runtime.

This note records the GPU setup attempt for Phase 6 validation. It is not a
long-memory benchmark result.

## What Changed

- `KING_SYNAPSE_ACCELERATOR=cuda` now routes fastembed model inference through
  the ONNX Runtime CUDA execution provider on Windows validation builds.
- `KING_SYNAPSE_ACCELERATOR=directml` remains available for DirectML attempts.
- `KING_SYNAPSE_ACCELERATOR=cpu`, `none`, `off`, or an empty value keeps the
  previous CPU behavior.
- `scripts/eval/longmem_dmr_smoke.py` now accepts `--accelerator`, so future
  LongMemEval / DMR runs can request GPU mode directly.

## Verified

```powershell
cargo fmt --all
cargo check -p synapse-core
```

Result: passed.

CUDA smoke command:

```powershell
$env:HF_ENDPOINT='https://hf-mirror.com'
$env:FASTEMBED_CACHE_DIR="$env:LOCALAPPDATA\king-synapse\fastembed-cache"
$env:KING_SYNAPSE_ACCELERATOR='cuda'
$env:KING_SYNAPSE_CUDA_DEVICE_ID='0'
cargo run -p synapse-eval --bin kr-eval -- `
  --dataset crates/eval/datasets/basic.toml `
  --k 3 `
  --tag cuda-check `
  --json crates/eval/reports/_tmp-cuda-check.json `
  --vectors `
  --rerank `
  --rerank-pool 5
```

Observed result after enabling `copy-dylibs` for ONNX Runtime:

```text
Error loading "D:\lake\jiaoben\king_recall\target\debug\onnxruntime_providers_cuda.dll"
which depends on "cublasLt64_12.dll" which is missing.
```

No `_tmp-cuda-check.json` report was written.

## Local Machine State

- GPU detected by Windows: `NVIDIA GeForce RTX 2060`
- Driver version reported by WMI: `32.0.15.9597`
- `nvidia-smi` was not found in PATH or the checked NVIDIA program directory.
- `CUDA_PATH` was not set.
- CUDA 12 runtime DLLs such as `cublasLt64_12.dll`, `cublas64_12.dll`,
  `cudart64_12.dll`, and `cudnn64_9.dll` were not found in the checked common
  installation paths.
- DirectML had already failed on this machine with ONNX Runtime adapter errors,
  so CUDA is the intended GPU path for the next validation attempt.

## Conclusion

This is not a Synapse architecture failure and not a DMR/LongMemEval result.
The project can request CUDA now, but the local machine cannot run the CUDA
provider until CUDA 12 runtime dependencies are installed and visible on PATH.

Do not start the 50-sample vector/reranker validation on CPU. Resume with GPU
only after the CUDA runtime check passes.

## Next GPU Command

After CUDA 12 runtime DLLs are installed and visible on PATH:

```powershell
python scripts/eval/longmem_dmr_smoke.py `
  --endpoint https://hf-mirror.com `
  --datasets dmr `
  --modes all `
  --dmr-sample-size 50 `
  --k 50 `
  --accelerator cuda `
  --cuda-device-id 0 `
  --output crates/eval/reports/dmr-50-validation.json `
  --cleanup-cache
```

