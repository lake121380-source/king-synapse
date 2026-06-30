use crate::error::{Error, Result};
use serde::{Deserialize, Serialize};
use std::fmt;
use std::str::FromStr;

/// The five first-class kinds of memory King Synapse treats as primitives.
///
/// These are not arbitrary tags — each kind has its own decay rate,
/// extractor pipeline, and importance heuristic (mostly defined in later phases).
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "lowercase")]
pub enum MemoryKind {
    Fact,
    Preference,
    Failure,
    Playbook,
    State,
}

impl fmt::Display for MemoryKind {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        let s = match self {
            MemoryKind::Fact => "fact",
            MemoryKind::Preference => "preference",
            MemoryKind::Failure => "failure",
            MemoryKind::Playbook => "playbook",
            MemoryKind::State => "state",
        };
        f.write_str(s)
    }
}

impl FromStr for MemoryKind {
    type Err = Error;
    fn from_str(s: &str) -> Result<Self> {
        match s.to_ascii_lowercase().as_str() {
            "fact" => Ok(MemoryKind::Fact),
            "preference" | "pref" => Ok(MemoryKind::Preference),
            "failure" | "fail" => Ok(MemoryKind::Failure),
            "playbook" | "play" => Ok(MemoryKind::Playbook),
            "state" => Ok(MemoryKind::State),
            other => Err(Error::Invalid(format!("unknown memory kind: {other}"))),
        }
    }
}

/// Where the memory applies. Phase 0 uses textual scope strings,
/// later phases will resolve project paths to stable hashes.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "lowercase")]
pub enum Scope {
    Global,
    User,
    Org(String),
    Project(String),
    File(String),
    Session(String),
}

impl fmt::Display for Scope {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Scope::Global => f.write_str("global"),
            Scope::User => f.write_str("user"),
            Scope::Org(o) => write!(f, "org:{o}"),
            Scope::Project(p) => write!(f, "project:{p}"),
            Scope::File(p) => write!(f, "file:{p}"),
            Scope::Session(s) => write!(f, "session:{s}"),
        }
    }
}

impl FromStr for Scope {
    type Err = Error;
    fn from_str(s: &str) -> Result<Self> {
        if s == "global" {
            return Ok(Scope::Global);
        }
        if s == "user" {
            return Ok(Scope::User);
        }
        if let Some(v) = s.strip_prefix("org:") {
            return Ok(Scope::Org(v.to_string()));
        }
        if let Some(v) = s.strip_prefix("project:") {
            return Ok(Scope::Project(v.to_string()));
        }
        if let Some(v) = s.strip_prefix("file:") {
            return Ok(Scope::File(v.to_string()));
        }
        if let Some(v) = s.strip_prefix("session:") {
            return Ok(Scope::Session(v.to_string()));
        }
        Err(Error::Invalid(format!("bad scope: {s}")))
    }
}

/// Who/what wrote this memory. Provenance is a first-class column,
/// not metadata — King Synapse's transparency promise depends on it.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum Source {
    ExplicitUser,
    AgentSelf,
    ExtractedFromTurn,
    Imported,
}

impl fmt::Display for Source {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        let s = match self {
            Source::ExplicitUser => "explicit_user",
            Source::AgentSelf => "agent_self",
            Source::ExtractedFromTurn => "extracted_from_turn",
            Source::Imported => "imported",
        };
        f.write_str(s)
    }
}

impl FromStr for Source {
    type Err = Error;
    fn from_str(s: &str) -> Result<Self> {
        match s {
            "explicit_user" => Ok(Source::ExplicitUser),
            "agent_self" => Ok(Source::AgentSelf),
            "extracted_from_turn" => Ok(Source::ExtractedFromTurn),
            "imported" => Ok(Source::Imported),
            other => Err(Error::Invalid(format!("bad source: {other}"))),
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Memory {
    pub id: String,
    pub kind: MemoryKind,
    pub scope: Scope,
    pub content: String,
    pub source: Source,
    pub confidence: f32,
    pub importance: f32,
    pub valid_from: i64,
    pub valid_to: Option<i64>,
    pub superseded_by: Option<String>,
    pub access_count: i64,
    pub last_accessed_at: Option<i64>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WriteInput {
    pub content: String,
    pub kind: MemoryKind,
    pub scope: Scope,
    pub source: Source,
    pub confidence: Option<f32>,
    pub importance: Option<f32>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RecallQuery {
    pub query: String,
    pub k: Option<usize>,
    pub scope_filter: Option<Scope>,
    pub kind_filter: Option<MemoryKind>,
}
