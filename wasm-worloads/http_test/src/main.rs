use std::thread::sleep;
use std::time::{Duration, Instant};
use serde_json::Value;

#[tokio::main(flavor = "current_thread")]
async fn main() -> Result<(), reqwest::Error> {
    // Get env variables
    let start_time = Instant::now();
    let proxy_ip = std::env::var("PROXY_IP").unwrap();
    let proxy_port = std::env::var("PROXY_PORT").unwrap();
    let input_topic = std::env::var("INPUT_TOPIC").unwrap();

    let request_url = "http://".to_owned() + &proxy_ip + ":" + &proxy_port + "/topics/" + &input_topic + "/partitions/0/records";
    let timeout = Duration::from_secs(300);
    let mut offset = 0u64;
    let mut total_sum = 0.0;

    let client = reqwest::Client::new();

    loop {
        if Instant::now().duration_since(start_time) > timeout {
            eprintln!("Timeout reached");
            break;
        }

        eprintln!("Fetching from {}", request_url);

        let res = client
            .get(&request_url)
            .header("Accept", "application/vnd.kafka.json.v2+json")
            .query(&[
                ("timeout", "1000"),
                ("max_bytes", "100000"),
                ("offset", &offset.to_string().as_str()),
            ])
            .send()
            .await?;

        eprintln!("Response Status: {:?}", res.status());

        if !res.status().is_success() {
            eprintln!("Error fetching data, retrying in 3 seconds");
            sleep(Duration::from_secs(3));
            continue;
        }

        let body = res.text().await?;
        // eprintln!("Response Body: {:?}", body);

        let messages: Vec<Value> = serde_json::from_str(&body).unwrap_or_else(|_| vec![]);

        for message in messages {
            if let Some(value) = message.get("value") {
                if let Some(status) = value.get("status") {
                    if status == "completed" {
                        eprintln!("Received completion message.");
                        eprintln!("Total sum: {}", total_sum);
                        return Ok(());
                    }
                }

                if let Some(value_number) = value.get("value").and_then(|v| v.as_f64()) {
                    total_sum += value_number;
                    println!("Value: {}", value_number);
                }

                if let Some(message_offset) = message.get("offset") {
                    offset = message_offset.as_u64().unwrap() + 1u64;
                }
            }
        }

    }

    Ok(())
}