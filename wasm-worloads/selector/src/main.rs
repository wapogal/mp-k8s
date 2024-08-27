mod workload_runner;
mod processing;

use processing::aggregator;
use processing::sp_trait;

use std::fs::OpenOptions;
use std::io::Write;

#[tokio::main(flavor = "current_thread")]
async fn main() -> Result<(), String> {
    let mut runner = workload_runner::WorkloadRunner::new();

    let settings = runner.settings.clone();
    let resource = settings["resource"].as_str().unwrap_or_else(|| {
        runner.log_event("Using default resource: sample-data");
        "sample-data"
    });

    let mut processor: Option<Box<dyn sp_trait::StreamProcessor>> = None;

    if let Some(processor_settings) = settings["processor"].as_object() {
        let processor_type = processor_settings["type"].as_str().unwrap_or("aggregator");
        match processor_type {
            "aggregator" => {
                runner.log_event("Using aggregator processor");
                processor = Some(Box::new(aggregator::Aggregator::new(processor_settings["windowSize"].as_u64().unwrap_or(1000))));
            }
            _ => {
                runner.log_event(&("Unknown processor type: ".to_owned() + processor_type));
            }
        }
    }

    if let Some(mut processor) = processor {
        loop {
            if runner.timeout_reached() {
                break Err("Timeout reached".to_string());
            }
    
            let (messages, final_msg_received) = runner.request_from_resource(resource).await?;
    
            for message in messages {
                if let Some(value) = message.get("value") {
                    let out = processor.process(value.clone());
                    if let Some(out) = out {
                        runner.log_event("Processor returned output");
                        write_output(&out)?;
                        runner.log_event("Output written");
                    }
            }
            }
    
            if final_msg_received {
                let out = processor.finish();
                runner.log_event("Processor returned final output");
                write_output(&out)?;
                runner.log_event("Final output written, Finished");
                return Ok(());
            }
        }
    } else {
        runner.log_event("No processor defined");
        return Err("No processor defined".to_string());
    }
}

fn write_output(out: &Vec<String>) -> Result<(), String> {
    let mut file = OpenOptions::new()
        .write(true)
        .create(true)
        .append(true)
        .open("/logs/output.csv").map_err(|e| e.to_string())?;

    for line in out {
        writeln!(file, "{}", line).map_err(|e| e.to_string())?;
    }

    Ok(())
}