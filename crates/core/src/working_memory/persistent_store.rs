use crate::working_memory::{
    SkippedStoreMutation, StoreExecutionReport, StoreExecutionStatistics, StoreExecutionWarning,
    StoreMutation, StoreMutationPlan,
};
use crate::{MemoryKind, Scope, Source, Store, WriteInput};

pub trait PersistentStoreExecutor {
    fn execute(&mut self, plan: &StoreMutationPlan) -> StoreExecutionReport;
}

pub struct NoOpPersistentStoreExecutor;

impl PersistentStoreExecutor for NoOpPersistentStoreExecutor {
    fn execute(&mut self, _plan: &StoreMutationPlan) -> StoreExecutionReport {
        StoreExecutionReport::default()
    }
}

pub struct SQLitePersistentStoreExecutor<'a> {
    store: &'a mut Store,
}

impl<'a> SQLitePersistentStoreExecutor<'a> {
    pub fn new(store: &'a mut Store) -> Self {
        Self { store }
    }
}

impl PersistentStoreExecutor for SQLitePersistentStoreExecutor<'_> {
    fn execute(&mut self, plan: &StoreMutationPlan) -> StoreExecutionReport {
        let mut report = StoreExecutionReport {
            executed: Vec::with_capacity(plan.mutations.len()),
            skipped: Vec::new(),
            warnings: Vec::new(),
            statistics: StoreExecutionStatistics::default(),
        };

        for mutation in &plan.mutations {
            execute_mutation(self.store, mutation, &mut report);
        }

        report
    }
}

pub struct KuzuPersistentStoreExecutor;

impl PersistentStoreExecutor for KuzuPersistentStoreExecutor {
    fn execute(&mut self, plan: &StoreMutationPlan) -> StoreExecutionReport {
        let mut report = StoreExecutionReport::default();
        for mutation in &plan.mutations {
            report
                .skipped
                .push(SkippedStoreMutation::Unsupported(mutation.clone()));
            report.warnings.push(StoreExecutionWarning {
                message: "kuzu persistent executor is not implemented".to_string(),
            });
            report.statistics.skipped += 1;
        }
        report
    }
}

fn execute_mutation(
    store: &mut Store,
    mutation: &StoreMutation,
    report: &mut StoreExecutionReport,
) {
    match mutation {
        StoreMutation::InsertMemory { content, .. } => {
            let result = store.write(WriteInput {
                content: content.clone(),
                kind: MemoryKind::Fact,
                scope: Scope::Global,
                source: Source::AgentSelf,
                confidence: None,
                importance: None,
            });
            record_result(result.map(|_| ()), mutation, report);
        }
        StoreMutation::ArchiveMemory { id } | StoreMutation::DeleteMemory { id } => {
            record_result(store.invalidate(id, "store_adapter"), mutation, report);
        }
        StoreMutation::UpdateMemory { id, content } => {
            record_result(
                store.update_content(id, content, "store_adapter"),
                mutation,
                report,
            );
        }
        StoreMutation::UpdateEdge { .. } => {
            report
                .skipped
                .push(SkippedStoreMutation::Unsupported(mutation.clone()));
            report.warnings.push(StoreExecutionWarning {
                message: "store mutation is not supported by SQLitePersistentStoreExecutor"
                    .to_string(),
            });
            report.statistics.skipped += 1;
        }
    }
}

fn record_result(
    result: crate::Result<()>,
    mutation: &StoreMutation,
    report: &mut StoreExecutionReport,
) {
    match result {
        Ok(()) => {
            report.executed.push(mutation.clone());
            report.statistics.executed += 1;
        }
        Err(error) => {
            report
                .skipped
                .push(SkippedStoreMutation::Failed(mutation.clone()));
            report.warnings.push(StoreExecutionWarning {
                message: error.to_string(),
            });
            report.statistics.skipped += 1;
        }
    }
}
