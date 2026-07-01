use crate::working_memory::PolicyReport;

pub trait PolicySink {
    fn consume(&self, report: &PolicyReport);
}

#[derive(Debug, Default)]
pub struct NoOpPolicySink;

impl PolicySink for NoOpPolicySink {
    fn consume(&self, _report: &PolicyReport) {}
}
