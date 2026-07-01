use crate::working_memory::HebbianExecutionReport;

pub trait HebbianSink {
    fn consume(&mut self, report: &HebbianExecutionReport);
}

#[derive(Debug, Default)]
pub struct NoOpHebbianSink;

impl HebbianSink for NoOpHebbianSink {
    fn consume(&mut self, _report: &HebbianExecutionReport) {}
}
