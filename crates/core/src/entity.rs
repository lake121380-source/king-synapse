use crate::error::{Error, Result};
use serde::{Deserialize, Serialize};
use std::fmt;
use std::str::FromStr;

/// Eight node kinds King Synapse builds the associative network from.
/// Phase 1 implements the five most extractable from text; the rest
/// arrive with richer extractors in later phases.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq, Hash)]
#[serde(rename_all = "snake_case")]
pub enum EntityType {
    Symbol,
    Command,
    Error,
    File,
    Library,
    Concept,
    Session,
    Frustration,
}

impl fmt::Display for EntityType {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        let s = match self {
            EntityType::Symbol => "symbol",
            EntityType::Command => "command",
            EntityType::Error => "error",
            EntityType::File => "file",
            EntityType::Library => "library",
            EntityType::Concept => "concept",
            EntityType::Session => "session",
            EntityType::Frustration => "frustration",
        };
        f.write_str(s)
    }
}

impl FromStr for EntityType {
    type Err = Error;
    fn from_str(s: &str) -> Result<Self> {
        match s {
            "symbol" => Ok(EntityType::Symbol),
            "command" => Ok(EntityType::Command),
            "error" => Ok(EntityType::Error),
            "file" => Ok(EntityType::File),
            "library" => Ok(EntityType::Library),
            "concept" => Ok(EntityType::Concept),
            "session" => Ok(EntityType::Session),
            "frustration" => Ok(EntityType::Frustration),
            other => Err(Error::Invalid(format!("bad entity type: {other}"))),
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Entity {
    pub id: String,
    pub kind: EntityType,
    pub name: String,
    pub normalized: String,
    pub created_at: i64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EntityRef {
    pub kind: EntityType,
    pub name: String,
}

impl EntityRef {
    pub fn new(kind: EntityType, name: impl Into<String>) -> Self {
        Self {
            kind,
            name: name.into(),
        }
    }

    pub fn normalized(&self) -> String {
        normalize(&self.name)
    }
}

pub fn normalize(s: &str) -> String {
    s.trim().to_lowercase()
}
