//! Dense text embedder used to fill `embedding_state` and `memory_vecs`.
//!
//! Phase 2 step 3: wrap `fastembed` with a 768-dimensional multilingual model
//! so embeddings line up with the `memory_vecs vec0(embedding float[768])`
//! virtual table created in `schema::vec_schema_sql()`.
//!
//! Synchronous and lazy: callers build one Embedder, batch-embed pending
//! memories, then drop it. First load downloads ONNX + tokenizer files into
//! `FASTEMBED_CACHE_DIR` (or `./.fastembed_cache` if unset).

use crate::accelerator::execution_providers_from_env;
use crate::error::{Error, Result};
use fastembed::{EmbeddingModel, TextEmbedding, TextInitOptions};

/// Multilingual E5 base: 768-d, ~470MB ONNX, covers CJK + EN well.
/// Matches `schema::VEC_DIM`.
pub(crate) const DEFAULT_MODEL: EmbeddingModel = EmbeddingModel::MultilingualE5Base;
pub(crate) const DEFAULT_MODEL_NAME: &str = "multilingual-e5-base";
pub const DEFAULT_DIM: usize = 768;

/// E5 family expects "passage: " / "query: " prefixes for best recall.
pub(crate) const PASSAGE_PREFIX: &str = "passage: ";
pub(crate) const QUERY_PREFIX: &str = "query: ";
const EMBED_BATCH_SIZE_ENV: &str = "KING_SYNAPSE_EMBED_BATCH_SIZE";
const EMBED_MAX_LENGTH_ENV: &str = "KING_SYNAPSE_EMBED_MAX_LENGTH";

pub struct Embedder {
    inner: TextEmbedding,
    model_name: String,
    dim: usize,
    batch_size: Option<usize>,
}

impl Embedder {
    /// Load the default 768-d multilingual model. Downloads on first call.
    pub fn new() -> Result<Self> {
        Self::with_model(DEFAULT_MODEL, DEFAULT_MODEL_NAME.to_string(), DEFAULT_DIM)
    }

    fn with_model(model: EmbeddingModel, name: String, dim: usize) -> Result<Self> {
        let mut opts = TextInitOptions::new(model).with_show_download_progress(true);
        if let Some(max_length) = positive_usize_from_env(EMBED_MAX_LENGTH_ENV, "token length")? {
            opts = opts.with_max_length(max_length);
        }
        let execution_providers = execution_providers_from_env()?;
        if !execution_providers.is_empty() {
            opts = opts.with_execution_providers(execution_providers);
        }
        let inner = TextEmbedding::try_new(opts)
            .map_err(|e| Error::Embedder(format!("init {name}: {e}")))?;
        Ok(Self {
            inner,
            model_name: name,
            dim,
            batch_size: positive_usize_from_env(EMBED_BATCH_SIZE_ENV, "batch size")?,
        })
    }

    pub fn model_name(&self) -> &str {
        &self.model_name
    }

    pub fn dim(&self) -> usize {
        self.dim
    }

    /// Embed memory contents (documents). Prepends the E5 passage prefix.
    pub fn embed_documents(&mut self, texts: &[&str]) -> Result<Vec<Vec<f32>>> {
        if texts.is_empty() {
            return Ok(Vec::new());
        }
        let prefixed: Vec<String> = texts
            .iter()
            .map(|t| format!("{PASSAGE_PREFIX}{t}"))
            .collect();
        let out = self
            .inner
            .embed(&prefixed, self.batch_size)
            .map_err(|e| Error::Embedder(format!("embed docs: {e}")))?;
        self.validate_dims(&out)?;
        Ok(out)
    }

    /// Embed a single user query. Prepends the E5 query prefix.
    pub fn embed_query(&mut self, query: &str) -> Result<Vec<f32>> {
        let prefixed = format!("{QUERY_PREFIX}{query}");
        let mut out = self
            .inner
            .embed(&[prefixed], self.batch_size)
            .map_err(|e| Error::Embedder(format!("embed query: {e}")))?;
        self.validate_dims(&out)?;
        out.pop()
            .ok_or_else(|| Error::Embedder("embed query: empty output".into()))
    }

    fn validate_dims(&self, vecs: &[Vec<f32>]) -> Result<()> {
        for v in vecs {
            if v.len() != self.dim {
                return Err(Error::Embedder(format!(
                    "model returned dim {} but expected {}",
                    v.len(),
                    self.dim
                )));
            }
        }
        Ok(())
    }
}

fn positive_usize_from_env(name: &str, label: &str) -> Result<Option<usize>> {
    let raw = std::env::var(name).unwrap_or_default();
    let trimmed = raw.trim();
    if trimmed.is_empty() {
        return Ok(None);
    }
    let value = trimmed
        .parse::<usize>()
        .map_err(|_| Error::Invalid(format!("{name} must be a positive integer {label}")))?;
    if value == 0 {
        return Err(Error::Invalid(format!("{name} must be greater than 0")));
    }
    Ok(Some(value))
}
