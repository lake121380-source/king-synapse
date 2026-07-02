use anyhow::{anyhow, Context, Result};
use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::collections::{BTreeMap, BTreeSet};
use std::path::PathBuf;
use std::process::Command;
use std::time::Instant;
use synapse_core::{
    AlgorithmContext, CognitiveTraceCandidate, CognitiveTraceConfig, CognitiveTraceProbe,
    DeterministicHebbianStoreMutationDispatcher, HebbianAlgorithm, HebbianExecutor, HebbianTarget,
    InMemoryMemoryEventStream, LatentActivationContext, LatentActivationHit, MemoryEvent,
    MemoryEventId, MemoryEventKind, MemoryEventPayload, MemoryEventStream, MemoryKind,
    PersistentStoreExecutor, PlanOnlyHebbianExecutor, RecallEngine, RecallHit, RecallQuery,
    RuleBasedHebbianAlgorithm, SQLitePersistentStoreExecutor, Scope, Source, Store,
    StoreMutationDispatcher, UniformImportanceEstimator, WriteInput,
};

const EXPORTED_COGNITIVE_SESSION_DATASET: &str =
    include_str!("../datasets/exported_cognitive_session.toml");
const EXTERNAL_SCHEMA_VERSION: &str = "king-synapse.external-comparison.v1";
const EXPORTED_DATASET_NAME: &str = "exported-cognitive-session";

#[derive(Debug, Clone)]
pub struct ExternalComparisonOptions {
    pub systems: Vec<ExternalSystemKind>,
    pub graphiti_command: Option<PathBuf>,
    pub graphiti_args: Vec<String>,
    pub adapter_input_path: Option<PathBuf>,
}

impl Default for ExternalComparisonOptions {
    fn default() -> Self {
        Self {
            systems: vec![
                ExternalSystemKind::KingSynapse,
                ExternalSystemKind::Graphiti,
            ],
            graphiti_command: None,
            graphiti_args: Vec::new(),
            adapter_input_path: None,
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum ExternalSystemKind {
    KingSynapse,
    Graphiti,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ExternalComparisonReport {
    pub schema_version: String,
    pub generated_at: String,
    pub dataset: String,
    pub fixture_chains: usize,
    pub systems: Vec<ExternalSystemRun>,
    pub summary: ExternalComparisonSummary,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ExternalComparisonSummary {
    pub systems: usize,
    pub measured_systems: usize,
    pub not_configured_systems: usize,
    pub failed_systems: usize,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ExternalSystemRun {
    pub system: String,
    pub kind: ExternalSystemKind,
    pub version: String,
    pub status: ExternalRunStatus,
    pub capabilities: ExternalCapabilities,
    pub aggregate: ExternalAggregate,
    pub chains: Vec<ExternalChainRun>,
    pub notes: Vec<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub raw: Option<Value>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ExternalRunStatus {
    Measured,
    NotConfigured,
    Failed,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ExternalCapabilities {
    pub retrieval: ExternalCapabilityStatus,
    pub trace: ExternalCapabilityStatus,
    pub prediction: ExternalCapabilityStatus,
    pub reinforcement: ExternalCapabilityStatus,
    pub evidence_paths: ExternalCapabilityStatus,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ExternalCapabilityStatus {
    Supported,
    Unsupported,
    Partial,
    Unknown,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ExternalAggregate {
    pub chains: usize,
    pub mean_latency_ms: f64,
    pub metrics: BTreeMap<String, ExternalMetricAggregate>,
}

#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct ExternalMetricAggregate {
    pub hit: usize,
    pub miss: usize,
    pub unsupported: usize,
    pub not_configured: usize,
    pub failed: usize,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ExternalChainRun {
    pub label: String,
    pub query: String,
    pub expected: ExternalExpected,
    pub status: ExternalRunStatus,
    pub latency_ms: f64,
    pub returned: Vec<ExternalMemoryHit>,
    pub evidence_paths: Vec<ExternalEvidencePath>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub dominant: Option<ExternalMemoryHit>,
    pub suppressed: Vec<ExternalMemoryHit>,
    pub prediction_candidates: Vec<ExternalMemoryHit>,
    pub reinforcement: ExternalReinforcementResult,
    pub metrics: BTreeMap<String, ExternalMetricResult>,
    pub notes: Vec<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub raw: Option<Value>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ExternalExpected {
    pub visible_seed: String,
    pub hidden_influence: String,
    pub future_influence: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ExternalMemoryHit {
    pub id: String,
    pub content: String,
    pub source: String,
    pub rank: Option<usize>,
    pub score: Option<f64>,
    pub matched_terms: Vec<String>,
    pub path: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ExternalEvidencePath {
    pub source_id: String,
    pub source_content: Option<String>,
    pub target_id: String,
    pub target_content: Option<String>,
    pub path: Vec<String>,
    pub score: Option<f64>,
    pub matched_terms: Vec<String>,
}

#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct ExternalReinforcementResult {
    pub attempted: bool,
    pub supported: bool,
    pub isolated_after_report: bool,
    pub expected_edges: usize,
    pub reinforced_edges: usize,
    pub edge_weights_before: BTreeMap<String, f32>,
    pub edge_weights_after: BTreeMap<String, f32>,
    pub notes: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ExternalMetricResult {
    pub status: ExternalMetricStatus,
    pub value: Option<f64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub note: Option<String>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ExternalMetricStatus {
    Hit,
    Miss,
    Unsupported,
    NotConfigured,
    Failed,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ExternalAdapterInput {
    pub schema_version: String,
    pub dataset: String,
    pub chains: Vec<ExternalAdapterChain>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ExternalAdapterChain {
    pub label: String,
    pub query: String,
    pub seed: String,
    pub visible_distractor: String,
    pub hidden: String,
    pub hidden_distractor: String,
    pub future: String,
    pub future_distractor: String,
    pub state_terms: Vec<String>,
    pub goal_terms: Vec<String>,
}

#[derive(Debug, Deserialize)]
struct ExportedCognitiveSession {
    chains: Vec<ExportedCognitiveChain>,
}

#[derive(Debug, Clone, Deserialize)]
struct ExportedCognitiveChain {
    label: String,
    query: String,
    seed: String,
    visible_distractor: String,
    hidden: String,
    hidden_distractor: String,
    future: String,
    future_distractor: String,
    state_terms: Vec<String>,
    goal_terms: Vec<String>,
}

impl ExportedCognitiveChain {
    fn scope(&self) -> Scope {
        Scope::Session(self.label.clone())
    }
}

struct ExportedCognitiveIds {
    seed: String,
    hidden: String,
    future: String,
}

pub fn run_external_comparison(
    options: ExternalComparisonOptions,
) -> Result<ExternalComparisonReport> {
    let session = exported_cognitive_session_fixture()?;
    let systems = if options.systems.is_empty() {
        ExternalComparisonOptions::default().systems
    } else {
        options.systems.clone()
    };

    let mut runs = Vec::with_capacity(systems.len());
    for system in systems {
        let run = match system {
            ExternalSystemKind::KingSynapse => run_king_synapse(&session)?,
            ExternalSystemKind::Graphiti => run_graphiti(&session, &options)?,
        };
        runs.push(run);
    }

    let summary = comparison_summary(&runs);
    Ok(ExternalComparisonReport {
        schema_version: EXTERNAL_SCHEMA_VERSION.to_string(),
        generated_at: Utc::now().to_rfc3339(),
        dataset: EXPORTED_DATASET_NAME.to_string(),
        fixture_chains: session.chains.len(),
        systems: runs,
        summary,
    })
}

fn exported_cognitive_session_fixture() -> Result<ExportedCognitiveSession> {
    toml::from_str(EXPORTED_COGNITIVE_SESSION_DATASET)
        .context("parsing exported cognitive session fixture")
}

fn run_king_synapse(session: &ExportedCognitiveSession) -> Result<ExternalSystemRun> {
    let (mut store, ids) = seed_king_synapse_store(&session.chains)?;
    let mut chains = Vec::with_capacity(session.chains.len());

    for chain in &session.chains {
        let ids = ids
            .get(&chain.label)
            .ok_or_else(|| anyhow!("missing seeded ids for {}", chain.label))?;
        chains.push(run_king_synapse_chain(&mut store, chain, ids)?);
    }

    let aggregate = aggregate_chains(&chains);
    Ok(ExternalSystemRun {
        system: "King Synapse".to_string(),
        kind: ExternalSystemKind::KingSynapse,
        version: env!("CARGO_PKG_VERSION").to_string(),
        status: ExternalRunStatus::Measured,
        capabilities: ExternalCapabilities {
            retrieval: ExternalCapabilityStatus::Supported,
            trace: ExternalCapabilityStatus::Supported,
            prediction: ExternalCapabilityStatus::Supported,
            reinforcement: ExternalCapabilityStatus::Supported,
            evidence_paths: ExternalCapabilityStatus::Supported,
        },
        aggregate,
        chains,
        notes: vec![
            "Measured locally with an in-memory Store and the exported cognitive session fixture."
                .to_string(),
            "Trace reinforcement is applied only after each chain report is captured.".to_string(),
        ],
        raw: None,
    })
}

fn run_graphiti(
    session: &ExportedCognitiveSession,
    options: &ExternalComparisonOptions,
) -> Result<ExternalSystemRun> {
    let Some(command) = options.graphiti_command.as_ref() else {
        return Ok(not_configured_run(
            "Graphiti/Zep",
            ExternalSystemKind::Graphiti,
            "Provide --graphiti-command to run a local Graphiti adapter.",
            session,
        ));
    };

    let input_path = options
        .adapter_input_path
        .clone()
        .unwrap_or_else(|| default_adapter_input_path("graphiti"));
    if let Some(parent) = input_path.parent() {
        std::fs::create_dir_all(parent)
            .with_context(|| format!("creating adapter input dir {}", parent.display()))?;
    }
    let input = adapter_input(session);
    std::fs::write(&input_path, serde_json::to_string_pretty(&input)?)
        .with_context(|| format!("writing adapter input {}", input_path.display()))?;

    let output = Command::new(command)
        .args(&options.graphiti_args)
        .arg(&input_path)
        .output()
        .with_context(|| format!("running Graphiti adapter {}", command.display()))?;

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr).trim().to_string();
        let stdout = String::from_utf8_lossy(&output.stdout).trim().to_string();
        return Ok(failed_run(
            "Graphiti/Zep",
            ExternalSystemKind::Graphiti,
            format!(
                "Graphiti adapter exited with status {:?}. stdout={} stderr={}",
                output.status.code(),
                stdout,
                stderr
            ),
            session,
        ));
    }

    let stdout = String::from_utf8(output.stdout).context("Graphiti adapter stdout is UTF-8")?;
    let run: ExternalSystemRun =
        serde_json::from_str(&stdout).context("parsing Graphiti adapter ExternalSystemRun JSON")?;
    Ok(run)
}

fn run_king_synapse_chain(
    store: &mut Store,
    chain: &ExportedCognitiveChain,
    ids: &ExportedCognitiveIds,
) -> Result<ExternalChainRun> {
    let started = Instant::now();
    let visible_query = RecallQuery {
        query: chain.query.clone(),
        k: Some(10),
        scope_filter: Some(chain.scope()),
        kind_filter: Some(MemoryKind::State),
    };
    let visible_hits = RecallEngine::new(store)
        .recall(&visible_query)
        .context("running visible recall for external comparison")?;

    let trace_query = RecallQuery {
        query: chain.query.clone(),
        k: Some(2),
        scope_filter: Some(chain.scope()),
        kind_filter: Some(MemoryKind::State),
    };
    let context = LatentActivationContext::new(chain.state_terms.clone(), chain.goal_terms.clone());
    let probe = exported_trace_probe();
    let trace_report = probe
        .trace(store, &trace_query, &context)
        .context("running cognitive trace for external comparison")?;
    let prediction = probe
        .predict_continuation(store, &trace_report, 10)
        .context("running predictive continuation for external comparison")?;

    let reinforcement = reinforce_trace_after_report(store, &trace_report, &chain.query)?;
    let latency_ms = started.elapsed().as_secs_f64() * 1000.0;

    let returned = visible_hits
        .iter()
        .enumerate()
        .map(|(idx, hit)| memory_hit_from_recall(hit, idx + 1))
        .collect::<Vec<_>>();
    let dominant = trace_report
        .dominant
        .as_ref()
        .map(|candidate| memory_hit_from_candidate(candidate, "dominant"));
    let suppressed = trace_report
        .suppressed
        .iter()
        .enumerate()
        .map(|(idx, candidate)| {
            let mut hit = memory_hit_from_candidate(candidate, "suppressed");
            hit.rank = Some(idx + 1);
            hit
        })
        .collect::<Vec<_>>();
    let prediction_candidates = prediction
        .candidates
        .iter()
        .enumerate()
        .map(|(idx, hit)| memory_hit_from_latent(hit, "prediction", Some(idx + 1)))
        .collect::<Vec<_>>();
    let evidence_paths = trace_report
        .latent
        .iter()
        .filter(|hit| !hit.path.is_empty())
        .map(evidence_path_from_latent)
        .collect::<Vec<_>>();

    let visible_seed_found = visible_hits.iter().any(|hit| hit.memory.id == ids.seed);
    let hidden_influence_found = trace_report
        .latent
        .iter()
        .any(|hit| hit.memory.id == ids.hidden)
        || trace_report
            .dominant
            .as_ref()
            .is_some_and(|candidate| candidate.memory.id == ids.hidden)
        || trace_report
            .suppressed
            .iter()
            .any(|candidate| candidate.memory.id == ids.hidden);
    let hidden_influence_dominant = trace_report.dominant.as_ref().is_some_and(|candidate| {
        candidate.memory.id == ids.hidden && !candidate.matched_terms.is_empty()
    });
    let suppressed_alternatives_visible = !trace_report.suppressed.is_empty();
    let evidence_path_available = trace_report.dominant.as_ref().is_some_and(|candidate| {
        candidate.memory.id == ids.hidden && !candidate.latent_path.is_empty()
    });
    let future_continuation_found = prediction
        .candidates
        .iter()
        .any(|candidate| candidate.memory.id == ids.future);
    let reinforcement_isolated = reinforcement.isolated_after_report
        && reinforcement.expected_edges > 0
        && reinforcement.expected_edges == reinforcement.reinforced_edges;

    let mut metrics = BTreeMap::new();
    metrics.insert(
        "visible_seed_found".to_string(),
        hit_metric(visible_seed_found),
    );
    metrics.insert(
        "hidden_influence_found".to_string(),
        hit_metric(hidden_influence_found),
    );
    metrics.insert(
        "hidden_influence_dominant".to_string(),
        hit_metric(hidden_influence_dominant),
    );
    metrics.insert(
        "suppressed_alternatives_visible".to_string(),
        hit_metric(suppressed_alternatives_visible),
    );
    metrics.insert(
        "evidence_path_available".to_string(),
        hit_metric(evidence_path_available),
    );
    metrics.insert(
        "future_continuation_found".to_string(),
        hit_metric(future_continuation_found),
    );
    metrics.insert(
        "reinforcement_isolated".to_string(),
        hit_metric(reinforcement_isolated),
    );

    Ok(ExternalChainRun {
        label: chain.label.clone(),
        query: chain.query.clone(),
        expected: ExternalExpected {
            visible_seed: chain.seed.clone(),
            hidden_influence: chain.hidden.clone(),
            future_influence: chain.future.clone(),
        },
        status: ExternalRunStatus::Measured,
        latency_ms,
        returned,
        evidence_paths,
        dominant,
        suppressed,
        prediction_candidates,
        reinforcement,
        metrics,
        notes: Vec::new(),
        raw: None,
    })
}

fn seed_king_synapse_store(
    chains: &[ExportedCognitiveChain],
) -> Result<(Store, BTreeMap<String, ExportedCognitiveIds>)> {
    let mut store = Store::open_in_memory().context("opening external comparison store")?;
    let mut ids = BTreeMap::new();

    for chain in chains {
        let scope = chain.scope();
        let seed = write_scoped_memory(&mut store, &chain.seed, MemoryKind::State, 0.8, &scope)?;
        write_scoped_memory(
            &mut store,
            &chain.visible_distractor,
            MemoryKind::Fact,
            0.5,
            &scope,
        )?;
        let hidden =
            write_scoped_memory(&mut store, &chain.hidden, MemoryKind::Playbook, 0.9, &scope)?;
        let hidden_distractor = write_scoped_memory(
            &mut store,
            &chain.hidden_distractor,
            MemoryKind::Fact,
            0.5,
            &scope,
        )?;
        let future =
            write_scoped_memory(&mut store, &chain.future, MemoryKind::Playbook, 0.9, &scope)?;
        let future_distractor = write_scoped_memory(
            &mut store,
            &chain.future_distractor,
            MemoryKind::Fact,
            0.5,
            &scope,
        )?;

        store.update_edge(&seed, &hidden, 3.0)?;
        store.update_edge(&seed, &hidden_distractor, 0.5)?;
        store.update_edge(&hidden, &future, 3.0)?;
        store.update_edge(&hidden, &future_distractor, 0.5)?;

        ids.insert(
            chain.label.clone(),
            ExportedCognitiveIds {
                seed,
                hidden,
                future,
            },
        );
    }

    Ok((store, ids))
}

fn write_scoped_memory(
    store: &mut Store,
    content: &str,
    kind: MemoryKind,
    importance: f32,
    scope: &Scope,
) -> Result<String> {
    Ok(store
        .write(WriteInput {
            content: content.to_string(),
            kind,
            scope: scope.clone(),
            source: Source::ExplicitUser,
            confidence: Some(1.0),
            importance: Some(importance),
        })?
        .id)
}

fn reinforce_trace_after_report(
    store: &mut Store,
    report: &synapse_core::CognitiveTraceReport,
    query: &str,
) -> Result<ExternalReinforcementResult> {
    let Some(dominant) = report.dominant.as_ref() else {
        return Ok(ExternalReinforcementResult {
            attempted: true,
            supported: true,
            isolated_after_report: true,
            notes: vec!["No dominant candidate was available for reinforcement.".to_string()],
            ..ExternalReinforcementResult::default()
        });
    };

    let mut ids = report
        .visible
        .iter()
        .take(3)
        .map(|hit| hit.memory.id.clone())
        .collect::<Vec<_>>();
    ids.push(dominant.memory.id.clone());
    ids = normalize_ids(ids);

    let edges = visible_hidden_edges(&ids, &dominant.memory.id);
    let before = edge_weights(store, &edges)?;
    reinforce_ids(store, ids, query)?;
    let after = edge_weights(store, &edges)?;
    let reinforced_edges = edges
        .iter()
        .filter(|edge| {
            let before = *before.get(*edge).unwrap_or(&0.0);
            let after = *after.get(*edge).unwrap_or(&0.0);
            after > before + f32::EPSILON
        })
        .count();

    Ok(ExternalReinforcementResult {
        attempted: true,
        supported: true,
        isolated_after_report: true,
        expected_edges: edges.len(),
        reinforced_edges,
        edge_weights_before: stringify_edge_weights(before),
        edge_weights_after: stringify_edge_weights(after),
        notes: vec![
            "Reinforcement ran after recall, trace, and prediction were captured.".to_string(),
        ],
    })
}

fn reinforce_ids(store: &mut Store, ids: Vec<String>, query: &str) -> Result<()> {
    if ids.len() < 2 {
        return Ok(());
    }

    let now: DateTime<Utc> = DateTime::from_timestamp(1_700_000_000, 0)
        .ok_or_else(|| anyhow!("fixed benchmark timestamp must be valid"))?;
    let memory_event = MemoryEvent {
        id: MemoryEventId::nil(),
        timestamp: now,
        session_id: None,
        kind: MemoryEventKind::Recalled,
        memory_ids: ids.clone(),
        payload: MemoryEventPayload::Recalled {
            query: format!("trace:{query}"),
            hit_count: ids.len(),
        },
    };
    let importance = UniformImportanceEstimator;
    let events = InMemoryMemoryEventStream::with_capacity(1);
    events.record(memory_event.clone());
    let ctx = AlgorithmContext::new(now, None, &importance, &events);
    let output = RuleBasedHebbianAlgorithm::default()
        .reinforce(&HebbianTarget::new(vec![memory_event]), &ctx);
    let hebbian_report = PlanOnlyHebbianExecutor.execute(output.plans());
    let mutation_plan = DeterministicHebbianStoreMutationDispatcher::new(hebbian_report).dispatch();
    let mut executor = SQLitePersistentStoreExecutor::new(store);
    let store_report = executor.execute(&mutation_plan);
    if !store_report.skipped.is_empty() {
        return Err(anyhow!(
            "trace reinforcement skipped {} store mutations",
            store_report.skipped.len()
        ));
    }
    Ok(())
}

fn exported_trace_probe() -> CognitiveTraceProbe {
    CognitiveTraceProbe::new(CognitiveTraceConfig {
        visible_limit: 2,
        latent_limit: 8,
        seed_limit: 1,
        suppressed_limit: 8,
        latent_scale: 0.05,
        latent_cap: 0.25,
        latent_steps: 2,
        latent_decay: 0.5,
        latent_fanout: 16,
    })
}

fn adapter_input(session: &ExportedCognitiveSession) -> ExternalAdapterInput {
    ExternalAdapterInput {
        schema_version: EXTERNAL_SCHEMA_VERSION.to_string(),
        dataset: EXPORTED_DATASET_NAME.to_string(),
        chains: session
            .chains
            .iter()
            .map(|chain| ExternalAdapterChain {
                label: chain.label.clone(),
                query: chain.query.clone(),
                seed: chain.seed.clone(),
                visible_distractor: chain.visible_distractor.clone(),
                hidden: chain.hidden.clone(),
                hidden_distractor: chain.hidden_distractor.clone(),
                future: chain.future.clone(),
                future_distractor: chain.future_distractor.clone(),
                state_terms: chain.state_terms.clone(),
                goal_terms: chain.goal_terms.clone(),
            })
            .collect(),
    }
}

fn not_configured_run(
    system: &str,
    kind: ExternalSystemKind,
    note: &str,
    session: &ExportedCognitiveSession,
) -> ExternalSystemRun {
    placeholder_run(
        system,
        kind,
        ExternalRunStatus::NotConfigured,
        note,
        session,
    )
}

fn failed_run(
    system: &str,
    kind: ExternalSystemKind,
    note: String,
    session: &ExportedCognitiveSession,
) -> ExternalSystemRun {
    placeholder_run(system, kind, ExternalRunStatus::Failed, &note, session)
}

fn placeholder_run(
    system: &str,
    kind: ExternalSystemKind,
    status: ExternalRunStatus,
    note: &str,
    session: &ExportedCognitiveSession,
) -> ExternalSystemRun {
    let chains = session
        .chains
        .iter()
        .map(|chain| placeholder_chain(chain, status, note))
        .collect::<Vec<_>>();
    let aggregate = aggregate_chains(&chains);
    ExternalSystemRun {
        system: system.to_string(),
        kind,
        version: "unknown".to_string(),
        status,
        capabilities: ExternalCapabilities {
            retrieval: ExternalCapabilityStatus::Unknown,
            trace: ExternalCapabilityStatus::Unknown,
            prediction: ExternalCapabilityStatus::Unknown,
            reinforcement: ExternalCapabilityStatus::Unknown,
            evidence_paths: ExternalCapabilityStatus::Unknown,
        },
        aggregate,
        chains,
        notes: vec![note.to_string()],
        raw: None,
    }
}

fn placeholder_chain(
    chain: &ExportedCognitiveChain,
    status: ExternalRunStatus,
    note: &str,
) -> ExternalChainRun {
    let metric_status = match status {
        ExternalRunStatus::Measured => ExternalMetricStatus::Unsupported,
        ExternalRunStatus::NotConfigured => ExternalMetricStatus::NotConfigured,
        ExternalRunStatus::Failed => ExternalMetricStatus::Failed,
    };
    let metrics = [
        "visible_seed_found",
        "hidden_influence_found",
        "hidden_influence_dominant",
        "suppressed_alternatives_visible",
        "evidence_path_available",
        "future_continuation_found",
        "reinforcement_isolated",
    ]
    .into_iter()
    .map(|name| {
        (
            name.to_string(),
            ExternalMetricResult {
                status: metric_status,
                value: None,
                note: Some(note.to_string()),
            },
        )
    })
    .collect();

    ExternalChainRun {
        label: chain.label.clone(),
        query: chain.query.clone(),
        expected: ExternalExpected {
            visible_seed: chain.seed.clone(),
            hidden_influence: chain.hidden.clone(),
            future_influence: chain.future.clone(),
        },
        status,
        latency_ms: 0.0,
        returned: Vec::new(),
        evidence_paths: Vec::new(),
        dominant: None,
        suppressed: Vec::new(),
        prediction_candidates: Vec::new(),
        reinforcement: ExternalReinforcementResult {
            notes: vec![note.to_string()],
            ..ExternalReinforcementResult::default()
        },
        metrics,
        notes: vec![note.to_string()],
        raw: None,
    }
}

fn aggregate_chains(chains: &[ExternalChainRun]) -> ExternalAggregate {
    let mut metrics = BTreeMap::<String, ExternalMetricAggregate>::new();
    for chain in chains {
        for (name, result) in &chain.metrics {
            let aggregate = metrics.entry(name.clone()).or_default();
            match result.status {
                ExternalMetricStatus::Hit => aggregate.hit += 1,
                ExternalMetricStatus::Miss => aggregate.miss += 1,
                ExternalMetricStatus::Unsupported => aggregate.unsupported += 1,
                ExternalMetricStatus::NotConfigured => aggregate.not_configured += 1,
                ExternalMetricStatus::Failed => aggregate.failed += 1,
            }
        }
    }
    let measured_latencies = chains
        .iter()
        .filter(|chain| chain.status == ExternalRunStatus::Measured)
        .map(|chain| chain.latency_ms)
        .collect::<Vec<_>>();
    let mean_latency_ms = if measured_latencies.is_empty() {
        0.0
    } else {
        measured_latencies.iter().sum::<f64>() / measured_latencies.len() as f64
    };

    ExternalAggregate {
        chains: chains.len(),
        mean_latency_ms,
        metrics,
    }
}

fn comparison_summary(runs: &[ExternalSystemRun]) -> ExternalComparisonSummary {
    ExternalComparisonSummary {
        systems: runs.len(),
        measured_systems: runs
            .iter()
            .filter(|run| run.status == ExternalRunStatus::Measured)
            .count(),
        not_configured_systems: runs
            .iter()
            .filter(|run| run.status == ExternalRunStatus::NotConfigured)
            .count(),
        failed_systems: runs
            .iter()
            .filter(|run| run.status == ExternalRunStatus::Failed)
            .count(),
    }
}

fn hit_metric(hit: bool) -> ExternalMetricResult {
    ExternalMetricResult {
        status: if hit {
            ExternalMetricStatus::Hit
        } else {
            ExternalMetricStatus::Miss
        },
        value: Some(if hit { 1.0 } else { 0.0 }),
        note: None,
    }
}

fn memory_hit_from_recall(hit: &RecallHit, rank: usize) -> ExternalMemoryHit {
    ExternalMemoryHit {
        id: hit.memory.id.clone(),
        content: hit.memory.content.clone(),
        source: "visible_recall".to_string(),
        rank: Some(rank),
        score: Some(hit.score as f64),
        matched_terms: hit.sources.iter().map(ToString::to_string).collect(),
        path: Vec::new(),
    }
}

fn memory_hit_from_candidate(
    candidate: &CognitiveTraceCandidate,
    source: &str,
) -> ExternalMemoryHit {
    ExternalMemoryHit {
        id: candidate.memory.id.clone(),
        content: candidate.memory.content.clone(),
        source: source.to_string(),
        rank: candidate.visible_rank,
        score: Some(candidate.combined_score as f64),
        matched_terms: candidate.matched_terms.clone(),
        path: candidate.latent_path.clone(),
    }
}

fn memory_hit_from_latent(
    hit: &LatentActivationHit,
    source: &str,
    rank: Option<usize>,
) -> ExternalMemoryHit {
    ExternalMemoryHit {
        id: hit.memory.id.clone(),
        content: hit.memory.content.clone(),
        source: source.to_string(),
        rank,
        score: Some(hit.activation as f64),
        matched_terms: hit.matched_terms.clone(),
        path: hit.path.clone(),
    }
}

fn evidence_path_from_latent(hit: &LatentActivationHit) -> ExternalEvidencePath {
    ExternalEvidencePath {
        source_id: hit.path.first().cloned().unwrap_or_default(),
        source_content: None,
        target_id: hit.memory.id.clone(),
        target_content: Some(hit.memory.content.clone()),
        path: hit.path.clone(),
        score: Some(hit.activation as f64),
        matched_terms: hit.matched_terms.clone(),
    }
}

fn normalize_ids(ids: Vec<String>) -> Vec<String> {
    ids.into_iter()
        .filter_map(|id| {
            let id = id.trim();
            if id.is_empty() {
                None
            } else {
                Some(id.to_string())
            }
        })
        .collect::<BTreeSet<_>>()
        .into_iter()
        .collect()
}

fn visible_hidden_edges(visible_ids: &[String], hidden: &str) -> BTreeSet<(String, String)> {
    visible_ids
        .iter()
        .filter(|id| id.as_str() != hidden)
        .flat_map(|id| {
            [
                (id.clone(), hidden.to_string()),
                (hidden.to_string(), id.clone()),
            ]
        })
        .collect()
}

fn edge_weights(
    store: &mut Store,
    edges: &BTreeSet<(String, String)>,
) -> Result<BTreeMap<(String, String), f32>> {
    edges
        .iter()
        .map(|edge| {
            let weight = store.edge_weight(&edge.0, &edge.1)?.unwrap_or(0.0);
            Ok((edge.clone(), weight))
        })
        .collect()
}

fn stringify_edge_weights(weights: BTreeMap<(String, String), f32>) -> BTreeMap<String, f32> {
    weights
        .into_iter()
        .map(|((source, target), weight)| (format!("{source}->{target}"), weight))
        .collect()
}

fn default_adapter_input_path(name: &str) -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("reports")
        .join(format!("{name}-external-adapter-input.json"))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn king_synapse_external_comparison_hits_exported_fixture() {
        let report = run_external_comparison(ExternalComparisonOptions {
            systems: vec![ExternalSystemKind::KingSynapse],
            graphiti_command: None,
            graphiti_args: Vec::new(),
            adapter_input_path: None,
        })
        .expect("external comparison runs");

        assert_eq!(report.systems.len(), 1);
        let run = &report.systems[0];
        assert_eq!(run.status, ExternalRunStatus::Measured);
        assert_eq!(run.chains.len(), 8);

        for metric in [
            "visible_seed_found",
            "hidden_influence_found",
            "hidden_influence_dominant",
            "suppressed_alternatives_visible",
            "evidence_path_available",
            "future_continuation_found",
            "reinforcement_isolated",
        ] {
            let aggregate = run.aggregate.metrics.get(metric).expect("metric exists");
            assert_eq!(aggregate.hit, 8, "{metric}");
            assert_eq!(aggregate.miss, 0, "{metric}");
        }
    }

    #[test]
    fn graphiti_without_command_is_not_configured() {
        let report = run_external_comparison(ExternalComparisonOptions {
            systems: vec![ExternalSystemKind::Graphiti],
            graphiti_command: None,
            graphiti_args: Vec::new(),
            adapter_input_path: None,
        })
        .expect("external comparison runs");

        let run = &report.systems[0];
        assert_eq!(run.status, ExternalRunStatus::NotConfigured);
        assert_eq!(run.chains.len(), 8);
        let aggregate = run
            .aggregate
            .metrics
            .get("visible_seed_found")
            .expect("metric exists");
        assert_eq!(aggregate.not_configured, 8);
    }
}
