use crate::error::{Error, Result};
use directories::ProjectDirs;
use serde::{Deserialize, Serialize};
use std::path::PathBuf;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Config {
    #[serde(default = "default_db_path")]
    pub db_path: PathBuf,

    #[serde(default = "default_recall_k")]
    pub default_recall_k: usize,

    #[serde(default)]
    pub require_confirm_writes: bool,
}

fn default_recall_k() -> usize {
    8
}

fn default_db_path() -> PathBuf {
    data_dir().join("synapse.sqlite")
}

impl Default for Config {
    fn default() -> Self {
        Config {
            db_path: default_db_path(),
            default_recall_k: default_recall_k(),
            require_confirm_writes: false,
        }
    }
}

pub fn data_dir() -> PathBuf {
    if let Some(pd) = ProjectDirs::from("ai", "kingsynapse", "king-synapse") {
        return pd.data_dir().to_path_buf();
    }
    // fallback: cwd-relative hidden dir (keeps Phase 0 robust on weird hosts)
    std::env::current_dir()
        .unwrap_or_else(|_| PathBuf::from("."))
        .join(".king_synapse")
}

pub fn config_path() -> PathBuf {
    if let Some(pd) = ProjectDirs::from("ai", "kingsynapse", "king-synapse") {
        return pd.config_dir().join("config.toml");
    }
    data_dir().join("config.toml")
}

impl Config {
    pub fn load_or_default() -> Result<Self> {
        let path = config_path();
        if path.exists() {
            let bytes = std::fs::read_to_string(&path)?;
            let cfg: Config = toml::from_str(&bytes)?;
            Ok(cfg)
        } else {
            Ok(Config::default())
        }
    }

    pub fn save(&self) -> Result<()> {
        let path = config_path();
        if let Some(parent) = path.parent() {
            std::fs::create_dir_all(parent)?;
        }
        let s = toml::to_string_pretty(self)?;
        std::fs::write(path, s)?;
        Ok(())
    }

    pub fn ensure_db_dir(&self) -> Result<()> {
        if let Some(parent) = self.db_path.parent() {
            std::fs::create_dir_all(parent)?;
        }
        Ok(())
    }
}

// silence unused import on platforms where Error isn't referenced
#[allow(dead_code)]
fn _ensure_error_in_scope() -> Error {
    Error::Invalid(String::new())
}
