use crate::working_memory::ReflectionReport;

pub trait ReflectionSink {
    fn consume(&mut self, report: &ReflectionReport);
}

#[derive(Debug, Default)]
pub struct NoOpReflectionSink;

impl ReflectionSink for NoOpReflectionSink {
    fn consume(&mut self, _report: &ReflectionReport) {}
}
