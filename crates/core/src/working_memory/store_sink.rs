use crate::working_memory::StoreExecutionReport;

pub trait StoreSink {
    fn consume(&self, report: &StoreExecutionReport);
}

#[derive(Debug, Default)]
pub struct NoOpStoreSink;

impl StoreSink for NoOpStoreSink {
    fn consume(&self, _report: &StoreExecutionReport) {}
}
