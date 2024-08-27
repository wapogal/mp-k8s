use serde_json::Value;

pub trait StreamProcessor {
    fn process(&mut self, value: Value) -> Option<Vec<String>>;
    fn finish(&mut self) -> Vec<String>;
}