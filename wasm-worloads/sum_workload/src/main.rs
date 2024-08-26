mod workload_runner;

use std::time::Duration;

#[tokio::main(flavor = "current_thread")]
async fn main() -> Result<(), String> {
    let mut runner = workload_runner::WorkloadRunner::new();

    let resource = "generated_records";

    let mut sum = 0.0;
    loop {
        if runner.timeout_reached(Duration::from_secs(300)) {
            runner.log_error("Timeout reached");
            break Err("Timeout reached".to_string());
        }
        let (messages, final_msg_received) = runner.request_from_resource(resource).await?;
        if final_msg_received {
            println!("Received completion message.");
            println!("Total sum: {}", sum);
            return Ok(());
        }
        for message in messages {
            if let Some(value) = message.get("value") {
                if let Some(value_number) = value.get("value").and_then(|v| v.as_f64()) {
                    sum += value_number;
                    println!("Value: {}", value_number);
                }
            }
        }
    }
}