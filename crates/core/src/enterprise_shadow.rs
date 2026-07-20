//! Read-only enterprise knowledge execution over a frozen Canonical Packet.
//!
//! This module deliberately owns no persistence, learning, admission, or
//! network mutation. It turns one natural-language question into an auditable
//! candidate/selection/guard trace and a conservative shadow draft.

use crate::{Error, Result};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use sha2::{Digest, Sha256};
use std::collections::{BTreeSet, HashMap};
use std::path::Path;

const SUSPENDED_GUARD: &str = "do_not_use_82_percent_market_statistic";
const UNKNOWN_GUARD: &str = "do_not_publish_specific_28_script_batch_duration";
const AVAILABILITY_GUARD: &str = "do_not_describe_7x24_as_default_or_unconditional";
const DEPARTMENT_GUARD: &str = "do_not_claim_all_nine_departments_are_fully_running";
const QUOTE_GUARD: &str = "binding_customer_quote_requires_human_confirmation";

const COMPANY_INTRO_IDS: &[&str] = &[
    "canonical-company-001",
    "canonical-company-002",
    "canonical-company-003",
    "canonical-company-005",
    "canonical-company-008",
    "canonical-company-009",
    "canonical-company-010",
    "canonical-company-011",
    "canonical-company-012",
    "canonical-company-013",
];

const TERM_RULES: &[(&str, &[&str])] = &[
    (
        "canonical-company-001",
        &["服务多久", "服务了多久", "服务关系", "一年"],
    ),
    (
        "canonical-company-002",
        &["7x24", "7×24", "7＊24", "全天", "在线"],
    ),
    ("canonical-company-003", &["九个部门", "9个部门", "部门"]),
    ("canonical-company-004", &["试用", "首周", "免费", "内容"]),
    ("canonical-company-005", &["案例", "客户授权", "公开案例"]),
    (
        "canonical-company-007",
        &["套餐", "价格", "多少钱", "报价", "1980", "2980", "3980"],
    ),
    (
        "canonical-company-008",
        &["叫什么", "品牌和主体", "公司名称", "法定主体"],
    ),
    (
        "canonical-company-009",
        &["定位", "服务什么", "中小企业", "落地服务", "业务定位"],
    ),
    (
        "canonical-company-010",
        &["ai员工", "员工角色", "角色", "调度", "文案", "剪辑"],
    ),
    (
        "canonical-company-011",
        &["能力", "能做什么", "可以做什么", "交付", "api", "脚本"],
    ),
    (
        "canonical-company-012",
        &["飞书", "企业微信", "接入", "集成"],
    ),
    (
        "canonical-company-013",
        &["原则", "理念", "风格", "不卖焦虑", "务实"],
    ),
];

const SUSPENDED_TERMS: &[&str] = &["82%", "82％", "采用率", "市场统计"];
const UNKNOWN_TERMS: &[&str] = &[
    "28条",
    "脚本批次",
    "批次",
    "交付多久",
    "交付周期",
    "具体时长",
];
const COMPANY_INTRO_TERMS: &[&str] = &["公司介绍", "介绍一下公司", "写一段公司介绍"];

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct EnterpriseCandidateEntry {
    pub entry_id: String,
    pub score: u32,
    pub rank: usize,
    pub eligibility: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub exclusion_reason: Option<String>,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct EnterpriseExcludedEntry {
    pub entry_id: String,
    pub reason: String,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct EnterpriseEvidenceBasis {
    pub entry_id: String,
    pub basis: String,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct EnterpriseLineage {
    pub output_line: usize,
    pub entry_ids: Vec<String>,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct EnterpriseRuntimeTrace {
    pub schema_version: u32,
    pub task_id: String,
    pub packet_sha256: String,
    pub candidate_entries: Vec<EnterpriseCandidateEntry>,
    pub selected_entries: Vec<String>,
    pub excluded_entries: Vec<EnterpriseExcludedEntry>,
    pub applied_guards: Vec<String>,
    pub evidence_basis: Vec<EnterpriseEvidenceBasis>,
    pub answer_mode: String,
    pub lineage: Vec<EnterpriseLineage>,
    pub runtime_write: bool,
    pub source_document_filesystem_read_during_generation: bool,
    pub external_provider_called: bool,
    pub candidate_or_network_modified: bool,
    pub learning_or_reflection: bool,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct EnterpriseShadowResponse {
    pub answer: String,
    pub trace: EnterpriseRuntimeTrace,
}

#[derive(Clone, Debug, Deserialize)]
struct EnterprisePacket {
    packet_id: String,
    selected_confirmed_entry_ids: Vec<String>,
    selected_confirmed_entries: Vec<CanonicalEntry>,
    suspended_blockers: Vec<BlockerEntry>,
    unknown_blockers: Vec<BlockerEntry>,
    mandatory_output_guards: Vec<String>,
    #[serde(default)]
    source_documents_in_packet: Vec<Value>,
    #[serde(default)]
    unadjudicated_assertions_in_packet: Vec<Value>,
}

#[derive(Clone, Debug, Deserialize)]
struct CanonicalEntry {
    entry_id: String,
    key: String,
    value: Value,
    #[serde(default)]
    display_value_zh: Option<String>,
    authority: String,
    #[serde(default)]
    retrieval_eligible_after_runtime_authorization: bool,
}

#[derive(Clone, Debug, Deserialize)]
struct BlockerEntry {
    entry_id: String,
}

#[derive(Clone, Debug)]
pub struct EnterpriseShadowEngine {
    packet: EnterprisePacket,
    packet_sha256: String,
}

impl EnterpriseShadowEngine {
    pub fn from_path(path: impl AsRef<Path>) -> Result<Self> {
        let body = std::fs::read(path)?;
        Self::from_slice(&body)
    }

    pub fn from_slice(body: &[u8]) -> Result<Self> {
        let packet: EnterprisePacket = serde_json::from_slice(body)?;
        validate_packet(&packet)?;
        Ok(Self {
            packet,
            packet_sha256: sha256_hex(body),
        })
    }

    pub fn packet_id(&self) -> &str {
        &self.packet.packet_id
    }

    pub fn packet_sha256(&self) -> &str {
        &self.packet_sha256
    }

    pub fn execute(&self, question: &str) -> Result<EnterpriseShadowResponse> {
        let question = question.trim();
        if question.is_empty() {
            return Err(Error::Invalid(
                "enterprise question must not be empty".into(),
            ));
        }

        let (candidate_entries, selected_entries, excluded_entries) = self.retrieve(question);
        let applied_guards = self.guard_decisions(&selected_entries, &excluded_entries);
        let answer_mode = if selected_entries.is_empty() {
            "withheld"
        } else {
            "shadow_draft"
        };
        let answer = self.compose_answer(&selected_entries, &excluded_entries, &applied_guards);
        let evidence_basis = selected_entries
            .iter()
            .filter_map(|entry_id| self.entry(entry_id))
            .map(|entry| EnterpriseEvidenceBasis {
                entry_id: entry.entry_id.clone(),
                basis: authority_to_basis(&entry.authority).to_string(),
            })
            .collect::<Vec<_>>();
        let lineage = if selected_entries.is_empty() {
            Vec::new()
        } else {
            vec![EnterpriseLineage {
                output_line: 1,
                entry_ids: selected_entries.clone(),
            }]
        };

        Ok(EnterpriseShadowResponse {
            answer,
            trace: EnterpriseRuntimeTrace {
                schema_version: 1,
                task_id: format!(
                    "enterprise-shadow-{}",
                    &sha256_hex(question.as_bytes())[..16]
                ),
                packet_sha256: self.packet_sha256.clone(),
                candidate_entries,
                selected_entries,
                excluded_entries,
                applied_guards,
                evidence_basis,
                answer_mode: answer_mode.to_string(),
                lineage,
                runtime_write: false,
                source_document_filesystem_read_during_generation: false,
                external_provider_called: false,
                candidate_or_network_modified: false,
                learning_or_reflection: false,
            },
        })
    }

    fn entry(&self, entry_id: &str) -> Option<&CanonicalEntry> {
        self.packet
            .selected_confirmed_entries
            .iter()
            .find(|entry| entry.entry_id == entry_id)
    }

    fn retrieve(
        &self,
        question: &str,
    ) -> (
        Vec<EnterpriseCandidateEntry>,
        Vec<String>,
        Vec<EnterpriseExcludedEntry>,
    ) {
        let normalized = question.to_lowercase();
        let suspended_score = match_count(&normalized, SUSPENDED_TERMS);
        let unknown_score = match_count(&normalized, UNKNOWN_TERMS);
        let mut scored: HashMap<String, (u32, Option<&'static str>)> = HashMap::new();

        if suspended_score == 0 && unknown_score == 0 {
            if match_count(&normalized, COMPANY_INTRO_TERMS) > 0 {
                for entry_id in COMPANY_INTRO_IDS {
                    scored.insert((*entry_id).to_string(), (1, None));
                }
            } else {
                for (entry_id, terms) in TERM_RULES {
                    let score = match_count(&normalized, terms);
                    if score > 0 && self.entry(entry_id).is_some() {
                        scored.insert((*entry_id).to_string(), (score, None));
                    }
                }
            }
        }

        if suspended_score > 0 {
            if let Some(blocker) = self.packet.suspended_blockers.first() {
                scored.insert(
                    blocker.entry_id.clone(),
                    (suspended_score, Some("status_suspended")),
                );
            }
        }
        if unknown_score > 0 {
            if let Some(blocker) = self.packet.unknown_blockers.first() {
                scored.insert(
                    blocker.entry_id.clone(),
                    (unknown_score, Some("status_unknown")),
                );
            }
        }

        let mut candidates = scored
            .into_iter()
            .map(|(entry_id, (score, reason))| (entry_id, score, reason))
            .collect::<Vec<_>>();
        candidates.sort_by(|a, b| b.1.cmp(&a.1).then_with(|| a.0.cmp(&b.0)));

        let candidate_entries = candidates
            .iter()
            .enumerate()
            .map(
                |(index, (entry_id, score, reason))| EnterpriseCandidateEntry {
                    entry_id: entry_id.clone(),
                    score: *score,
                    rank: index + 1,
                    eligibility: if reason.is_some() {
                        "excluded".to_string()
                    } else {
                        "eligible".to_string()
                    },
                    exclusion_reason: reason.map(str::to_string),
                },
            )
            .collect::<Vec<_>>();
        let selected_entries = candidates
            .iter()
            .filter(|(_, _, reason)| reason.is_none())
            .map(|(entry_id, _, _)| entry_id.clone())
            .collect::<Vec<_>>();
        let excluded_entries = candidates
            .iter()
            .filter_map(|(entry_id, _, reason)| {
                reason.map(|reason| EnterpriseExcludedEntry {
                    entry_id: entry_id.clone(),
                    reason: reason.to_string(),
                })
            })
            .collect::<Vec<_>>();

        (candidate_entries, selected_entries, excluded_entries)
    }

    fn guard_decisions(
        &self,
        selected: &[String],
        excluded: &[EnterpriseExcludedEntry],
    ) -> Vec<String> {
        let mut guards = Vec::new();
        if contains_id(selected, "canonical-company-002") {
            guards.push(AVAILABILITY_GUARD.to_string());
        }
        if contains_id(selected, "canonical-company-003") {
            guards.push(DEPARTMENT_GUARD.to_string());
        }
        if contains_id(selected, "canonical-company-007") {
            guards.push(QUOTE_GUARD.to_string());
        }
        for item in excluded {
            if item.reason == "status_suspended" {
                guards.push(SUSPENDED_GUARD.to_string());
            }
            if item.reason == "status_unknown" {
                guards.push(UNKNOWN_GUARD.to_string());
            }
        }
        guards
    }

    fn compose_answer(
        &self,
        selected: &[String],
        excluded: &[EnterpriseExcludedEntry],
        guards: &[String],
    ) -> String {
        if selected.is_empty() {
            if excluded.is_empty() {
                return "当前知识包没有与该问题匹配的可用条目，Runtime 保持不回答。".into();
            }
            return "当前问题触及知识包中的受限或未知信息，Runtime 不会给出未经确认的具体回答。"
                .into();
        }

        let mut parts = selected
            .iter()
            .filter_map(|entry_id| self.entry(entry_id))
            .map(render_entry)
            .filter(|text| !text.is_empty())
            .collect::<Vec<_>>();
        if guards.iter().any(|guard| guard == QUOTE_GUARD) {
            parts.push("正式报价、合同范围和交付边界仍需人工确认。".into());
        }
        parts.join("")
    }
}

fn validate_packet(packet: &EnterprisePacket) -> Result<()> {
    if packet.packet_id.trim().is_empty() {
        return Err(Error::Invalid(
            "enterprise packet_id must not be empty".into(),
        ));
    }
    if !packet.source_documents_in_packet.is_empty() {
        return Err(Error::Invalid(
            "enterprise packet must not contain source documents".into(),
        ));
    }
    if !packet.unadjudicated_assertions_in_packet.is_empty() {
        return Err(Error::Invalid(
            "enterprise packet must not contain unadjudicated assertions".into(),
        ));
    }
    let entry_ids = packet
        .selected_confirmed_entries
        .iter()
        .map(|entry| entry.entry_id.as_str())
        .collect::<BTreeSet<_>>();
    if entry_ids.len() != packet.selected_confirmed_entries.len() {
        return Err(Error::Invalid("enterprise entry ids must be unique".into()));
    }
    let declared_ids = packet
        .selected_confirmed_entry_ids
        .iter()
        .map(String::as_str)
        .collect::<BTreeSet<_>>();
    if entry_ids != declared_ids {
        return Err(Error::Invalid(
            "enterprise selected entry ids do not match entries".into(),
        ));
    }
    if packet
        .selected_confirmed_entries
        .iter()
        .any(|entry| !entry.retrieval_eligible_after_runtime_authorization)
    {
        return Err(Error::Invalid(
            "enterprise packet contains an ineligible selected entry".into(),
        ));
    }
    for required in [
        UNKNOWN_GUARD,
        AVAILABILITY_GUARD,
        SUSPENDED_GUARD,
        DEPARTMENT_GUARD,
        QUOTE_GUARD,
    ] {
        if !packet
            .mandatory_output_guards
            .iter()
            .any(|guard| guard == required)
        {
            return Err(Error::Invalid(format!(
                "enterprise packet missing mandatory guard: {required}"
            )));
        }
    }
    Ok(())
}

fn render_entry(entry: &CanonicalEntry) -> String {
    match entry.entry_id.as_str() {
        "canonical-company-002" => {
            "7×24在线能力需要单独评估和部署，不是套餐默认或无条件提供。".into()
        }
        "canonical-company-003" => {
            "资料确认的是覆盖9个部门的应用场景，不代表每个部门都处于同一上线状态。".into()
        }
        "canonical-company-004" => format!(
            "当前试用条件为首周免费，交付{}条内容。",
            entry.value["content_count"].as_u64().unwrap_or(0)
        ),
        "canonical-company-005" => {
            "案例对外使用仍需负责人确认和客户授权，Runtime 不据此扩大公开范围。".into()
        }
        "canonical-company-007" => format!(
            "当前参考套餐为起步{}元/月、成长{}元/月、全能{}元/月。",
            format_number(entry.value["starter"].as_u64()),
            format_number(entry.value["growth"].as_u64()),
            format_number(entry.value["full"].as_u64())
        ),
        "canonical-company-008" => format!(
            "品牌为{}，运营主体为{}。",
            entry.value["brand"].as_str().unwrap_or("未确认"),
            entry.value["legal_or_operating_entity"]
                .as_str()
                .unwrap_or("未确认")
        ),
        "canonical-company-009" => format!(
            "{}，同时{}。",
            entry.value["primary"].as_str().unwrap_or(""),
            entry.value["secondary"].as_str().unwrap_or("")
        ),
        "canonical-company-010" => {
            format!("AI员工角色包括{}。", value_strings(&entry.value).join("、"))
        }
        "canonical-company-011" => format!(
            "当前可交付能力包括{}。",
            value_strings(&entry.value).join("、")
        ),
        "canonical-company-012" => entry.value["wording"]
            .as_str()
            .map(|text| format!("{text}。"))
            .unwrap_or_default(),
        "canonical-company-013" => entry
            .value
            .as_str()
            .map(|text| format!("品牌原则是：{text}。"))
            .unwrap_or_default(),
        _ => entry
            .display_value_zh
            .clone()
            .unwrap_or_else(|| entry.key.clone()),
    }
}

fn match_count(question: &str, terms: &[&str]) -> u32 {
    terms
        .iter()
        .filter(|term| question.contains(&term.to_lowercase()))
        .count() as u32
}

fn contains_id(ids: &[String], expected: &str) -> bool {
    ids.iter().any(|entry_id| entry_id == expected)
}

fn authority_to_basis(authority: &str) -> &'static str {
    if authority == "owner_attestation" {
        "owner_attestation"
    } else if authority.starts_with("owner_confirmed") {
        "owner_confirmation"
    } else if authority == "external_reference" {
        "external_reference"
    } else if authority == "multiple_sources" {
        "multiple_sources"
    } else if authority == "source_assertion" {
        "source_assertion"
    } else {
        "unknown"
    }
}

fn value_strings(value: &Value) -> Vec<&str> {
    value
        .as_array()
        .map(|items| items.iter().filter_map(Value::as_str).collect())
        .unwrap_or_default()
}

fn format_number(value: Option<u64>) -> String {
    let value = value.unwrap_or(0);
    if value < 1_000 {
        return value.to_string();
    }
    let high = value / 1_000;
    let low = value % 1_000;
    format!("{high},{low:03}")
}

fn sha256_hex(body: &[u8]) -> String {
    format!("{:x}", Sha256::digest(body))
}
