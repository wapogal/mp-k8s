mod workload_runner;
mod processing;

use processing::aggregator;
use processing::sp_trait;

use std::fs::OpenOptions;
use std::fs;
use std::env;
use std::path::Path;
use std::io::Write;

use std::rc::Rc;
use std::cell::RefCell;

static ALLOC: wee_alloc::WeeAlloc = wee_alloc::WeeAlloc::INIT;

#[tokio::main(flavor = "current_thread")]
async fn main() -> Result<(), String> {
    // Print all environment variables
    println!("Environment Variables:");
    for (key, value) in env::vars() {
        println!("{}: {}", key, value);
    }

    // Print the file tree of the root directory up to 5 levels
    println!("\nRoot Directory File Tree (up to 5 levels):");
    let root_path = Path::new("/");
    print_file_tree(root_path, 0, 5);

    let runner = Rc::new(RefCell::new(workload_runner::WorkloadRunner::new()));

    let log_event_closure = {
        let runner_clone = Rc::clone(&runner);
        Box::new(move |event: String| runner_clone.borrow_mut().log_event(event))
    };
    
    let settings = runner.borrow().settings.clone();
    let resource = settings["resource"].as_str().unwrap_or_else(|| {
        runner.borrow_mut().log_event("Using default resource: sample-data".to_string());
        "sample-data"
    });

    let mut processor: Option<Box<dyn sp_trait::StreamProcessor>> = None;

    if let Some(processor_settings) = settings["processor"].as_object() {
        let processor_type = processor_settings["type"].as_str().unwrap_or("aggregator");
        match processor_type {
            "aggregator" => {
                //runner.borrow_mut().log_event("Using aggregator processor");
                processor = Some(Box::new(aggregator::Aggregator::new(processor_settings["windowSize"].as_u64().unwrap_or(1000), log_event_closure)));
            }
            _ => {
                //runner.borrow_mut().log_event(&("Unknown processor type: ".to_owned() + processor_type));
            }
        }
    }

    if let Some(mut processor) = processor {
        loop {
            if runner.borrow_mut().timeout_reached() {
                break Err("Timeout reached".to_string());
            }
    
            let (messages, final_msg_received) = runner.borrow_mut().request_from_resource(resource).await?;
    
            for message in messages {
                if let Some(value) = message.get("value") {
                    let out = processor.process(value.clone());
                    if let Some(out) = out {
                        //runner.borrow_mut().log_event("Processor returned output");
                        write_output(&out)?;
                        //runner.borrow_mut().log_event("Output written");
                    }
            }
            }
    
            if final_msg_received {
                let out = processor.finish();
                //runner.borrow_mut().log_event("Processor returned final output");
                write_output(&out)?;
                //runner.borrow_mut().log_event("Final output written, Finished");
                return Ok(());
            }
        }
    } else {
        //runner.borrow_mut().log_event("No processor defined");
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

fn print_file_tree(path: &Path, current_level: usize, max_level: usize) {
    if current_level > max_level {
        return;
    }

    if path == Path::new("/proc") {
        return;
    }

    if path == Path::new("/sys/devices") {
        return;
    }

    // Read the directory contents
    match fs::read_dir(path) {
        Ok(entries) => {
            for entry in entries {
                match entry {
                    Ok(entry) => {
                        let path = entry.path();
                        // Print the current entry with indentation based on the level
                        println!("{}{}", "  ".repeat(current_level), path.display());

                        // If it's a directory, recursively print its contents
                        if path.is_dir() {
                            print_file_tree(&path, current_level + 1, max_level);
                        }
                    }
                    Err(e) => {
                        eprintln!("Error reading entry: {}", e);
                    }
                }
            }
        }
        Err(e) => {
            eprintln!("Error reading directory {}: {}", path.display(), e);
        }
    }
}