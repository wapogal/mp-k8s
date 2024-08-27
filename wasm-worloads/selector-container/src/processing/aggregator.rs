use crate::processing::sp_trait::StreamProcessor; // Updated import path
use std::collections::HashMap;
use serde_json::Value;

struct AggregatedMetrics {
    count: u64,
    sum: f64,
    min: f64,
    max: f64,
    mean: f64,
    variance: f64,
    sum_squares: f64,
    m2: f64,
}

impl AggregatedMetrics {
    pub fn new() -> Self {
        Self {
            count: 0,
            sum: 0.0,
            min: f64::MAX,
            max: f64::MIN,
            mean: 0.0,
            variance: 0.0,
            sum_squares: 0.0,
            m2: 0.0,
        }
    }
}

pub struct Aggregator {
    // Time scale aggregation
    window_start: HashMap<(String, Vec<String>), u64>,
    window_size: u64,
    window_metrics: HashMap<(String, Vec<String>), AggregatedMetrics>,
    result_buffer: Vec<(u64, String, Vec<String>, AggregatedMetrics)>,
}

impl Aggregator {
    pub fn new(window_size: u64) -> Self {
        Self {
            window_start: HashMap::new(),
            window_size,
            window_metrics: HashMap::new(),
            result_buffer: Vec::new(),
        }
    }
}

impl StreamProcessor for Aggregator {
    fn process(&mut self, msg_value: Value) -> Option<Vec<String>> {
        let mut return_value = None;
        let timestamp = msg_value["timestamp"].as_u64()?;
        let metric = msg_value["metric"].as_str()?;
        let value = msg_value["value"].as_f64()?;
        let _source = msg_value["source"].as_str()?; // Prefixed with underscore to suppress unused variable warning
        let tags = msg_value["tags"].as_array()?;

        let group = (
            metric.to_string(),
            tags.iter()
                .map(|v| v.as_str().unwrap_or_default().to_string())
                .collect(),
        );

        let group_clone = group.clone();
        self.window_start.entry(group_clone.clone()).or_insert(timestamp);
        self.window_metrics
            .entry(group_clone.clone())
            .or_insert(AggregatedMetrics::new());

        let start = self.window_start.get(&group).unwrap();
        if timestamp - start > self.window_size {
            if let Some((_, agg_metrics)) = self.window_metrics.remove_entry(&group) {
                self.result_buffer
                    .push((*start, group_clone.0.clone(), group_clone.1.clone(), agg_metrics));
            }

            if self.result_buffer.len() > 1000 {
                let mut out = Vec::new();
                for (timestamp, metric, tags, agg_metrics) in
                    std::mem::replace(&mut self.result_buffer, Vec::new())
                {
                    out.push(format!(
                        "{},{},{},{},{},{},{},{};",
                        timestamp,
                        metric,
                        tags.join("-"),
                        agg_metrics.count,
                        agg_metrics.sum,
                        agg_metrics.min,
                        agg_metrics.max,
                        agg_metrics.mean
                    ));
                }
                return_value = Some(out);
            }

            self.window_start.insert(group.clone(), timestamp);
            self.window_metrics.insert(group, AggregatedMetrics::new());
        }

        if let Some(metrics) = self.window_metrics.get_mut(&group_clone) {
            metrics.count += 1;
            metrics.sum += value;
            metrics.sum_squares += value * value;

            if value < metrics.min {
                metrics.min = value;
            }
            if value > metrics.max {
                metrics.max = value;
            }

            let delta = value - metrics.mean;
            metrics.mean += delta / metrics.count as f64;
            let delta2 = value - metrics.mean;
            metrics.m2 += delta * delta2;
            metrics.variance = metrics.m2 / (metrics.count as f64 - 1.0);
        }
        return_value
    }

    fn finish(&mut self) -> Vec<String> {
        for (group, agg_metrics) in self.window_metrics.drain() {
            self.result_buffer.push((
                *self.window_start.get(&group).unwrap(),
                group.0,
                group.1,
                agg_metrics,
            ));
        }
        let mut out = Vec::new();
        for (timestamp, metric, tags, agg_metrics) in
            std::mem::replace(&mut self.result_buffer, Vec::new())
        {
            out.push(format!(
                "{},{},{},{},{},{},{},{};",
                timestamp,
                metric,
                tags.join("-"),
                agg_metrics.count,
                agg_metrics.sum,
                agg_metrics.min,
                agg_metrics.max,
                agg_metrics.mean
            ));
        }
        out
    }
}