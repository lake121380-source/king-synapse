use thiserror::Error;

#[derive(Debug, Error)]
pub enum Error {
    #[error("sqlite error: {0}")]
    Sqlite(#[from] rusqlite::Error),

    #[error("io error: {0}")]
    Io(#[from] std::io::Error),

    #[error("json error: {0}")]
    Json(#[from] serde_json::Error),

    #[error("toml parse: {0}")]
    TomlDe(#[from] toml::de::Error),

    #[error("toml serialize: {0}")]
    TomlSer(#[from] toml::ser::Error),

    #[error("invalid input: {0}")]
    Invalid(String),

    #[error("not found: {0}")]
    NotFound(String),

    #[allow(dead_code)]
    #[error("embedder error: {0}")]
    Embedder(String),
}

pub type Result<T> = std::result::Result<T, Error>;

impl From<&str> for Error {
    fn from(s: &str) -> Self {
        Error::Invalid(s.to_string())
    }
}
