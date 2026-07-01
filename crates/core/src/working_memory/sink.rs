use crate::error::Result;
use crate::working_memory::ExecutionReport;

pub trait ConsolidationSink {
    fn apply(&mut self, report: &ExecutionReport) -> Result<()>;
}

#[derive(Debug, Default)]
pub struct NoOpSink;

impl ConsolidationSink for NoOpSink {
    fn apply(&mut self, _report: &ExecutionReport) -> Result<()> {
        Ok(())
    }
}
