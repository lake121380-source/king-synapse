use crate::error::{Error, Result};
use fastembed::ExecutionProviderDispatch;

const ACCELERATOR_ENV: &str = "KING_SYNAPSE_ACCELERATOR";
const CUDA_DEVICE_ENV: &str = "KING_SYNAPSE_CUDA_DEVICE_ID";
const CUDA_LOW_MEMORY_ENV: &str = "KING_SYNAPSE_CUDA_LOW_MEMORY";
const CUDA_MEMORY_LIMIT_MB_ENV: &str = "KING_SYNAPSE_CUDA_MEMORY_LIMIT_MB";
const DIRECTML_DEVICE_ENV: &str = "KING_SYNAPSE_DIRECTML_DEVICE_ID";

pub(crate) fn execution_providers_from_env() -> Result<Vec<ExecutionProviderDispatch>> {
    let raw = std::env::var(ACCELERATOR_ENV).unwrap_or_default();
    match raw.trim().to_ascii_lowercase().as_str() {
        "" | "cpu" | "none" | "off" => Ok(Vec::new()),
        "cuda" => cuda_execution_provider(),
        "gpu" | "directml" | "dml" => directml_execution_provider(),
        other => Err(Error::Invalid(format!(
            "unsupported accelerator `{other}`; use cpu, directml, or cuda"
        ))),
    }
}

#[cfg(target_os = "windows")]
fn cuda_execution_provider() -> Result<Vec<ExecutionProviderDispatch>> {
    let mut cuda = ort::ep::CUDA::default();
    if env_flag(CUDA_LOW_MEMORY_ENV) {
        cuda = cuda
            .with_arena_extend_strategy(ort::ep::ArenaExtendStrategy::SameAsRequested)
            .with_conv_algorithm_search(ort::ep::cuda::ConvAlgorithmSearch::Default)
            .with_conv_max_workspace(false);
    }
    if let Ok(raw) = std::env::var(CUDA_DEVICE_ENV) {
        let trimmed = raw.trim();
        if !trimmed.is_empty() {
            let id = trimmed.parse::<i32>().map_err(|_| {
                Error::Invalid(format!("{CUDA_DEVICE_ENV} must be an integer device id"))
            })?;
            cuda = cuda.with_device_id(id);
        }
    }
    if let Ok(raw) = std::env::var(CUDA_MEMORY_LIMIT_MB_ENV) {
        let trimmed = raw.trim();
        if !trimmed.is_empty() {
            let mb = trimmed.parse::<usize>().map_err(|_| {
                Error::Invalid(format!(
                    "{CUDA_MEMORY_LIMIT_MB_ENV} must be a positive integer megabyte value"
                ))
            })?;
            if mb == 0 {
                return Err(Error::Invalid(format!(
                    "{CUDA_MEMORY_LIMIT_MB_ENV} must be greater than 0"
                )));
            }
            cuda = cuda.with_memory_limit(mb * 1024 * 1024);
        }
    }
    Ok(vec![cuda.build().error_on_failure()])
}

fn env_flag(name: &str) -> bool {
    matches!(
        std::env::var(name)
            .unwrap_or_default()
            .trim()
            .to_ascii_lowercase()
            .as_str(),
        "1" | "true" | "yes" | "on"
    )
}

#[cfg(not(target_os = "windows"))]
fn cuda_execution_provider() -> Result<Vec<ExecutionProviderDispatch>> {
    Err(Error::Invalid(
        "CUDA accelerator is currently configured for Windows validation builds".to_string(),
    ))
}

#[cfg(target_os = "windows")]
fn directml_execution_provider() -> Result<Vec<ExecutionProviderDispatch>> {
    let mut directml = ort::ep::DirectML::default()
        .with_performance_preference(ort::ep::directml::PerformancePreference::HighPerformance);
    if let Ok(raw) = std::env::var(DIRECTML_DEVICE_ENV) {
        let trimmed = raw.trim();
        if !trimmed.is_empty() {
            let id = trimmed.parse::<i32>().map_err(|_| {
                Error::Invalid(format!(
                    "{DIRECTML_DEVICE_ENV} must be an integer device id"
                ))
            })?;
            directml = directml.with_device_id(id);
        }
    }
    Ok(vec![directml.build().error_on_failure()])
}

#[cfg(not(target_os = "windows"))]
fn directml_execution_provider() -> Result<Vec<ExecutionProviderDispatch>> {
    Err(Error::Invalid(
        "DirectML accelerator is only supported on Windows".to_string(),
    ))
}
