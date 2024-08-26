use std::thread::sleep;
use std::process;
use std::time::{Duration, Instant};
use serde_json::Value;
use serde_json::json;

#[tokio::main(flavor = "current_thread")]
async fn main() -> Result<(), reqwest::Error> {
    let start_time = Instant::now();

    // Get env variables
    println!("Fetching env variables");
    let kafka_proxy_adress = std::env::var("KAFKA_PROXY_ADDRESS").unwrap();
    let data_access_adress = std::env::var("DATA_ACCESS_ADDRESS").unwrap();
    let data_request_route = std::env::var("DATA_REQUEST_ROUTE").unwrap();
    let workload_id = std::env::var("WORKLOAD_ID").unwrap();

    // Set up client
    let client = reqwest::Client::new();
    let topic_request_url = "http://".to_owned() + &data_access_adress + "/" + &data_request_route;

    // Get input topic from data access service
    println!("Fetching input topic from data access service");
    let res = client.post(&topic_request_url)
        .header("Content-Type", "application/json")
        .json(&json!({
            "type": "input",
            "resource": "generated_records",
            "workload_id": &workload_id.to_string().as_str(),
        }))
        .send()
        .await?;

    if !res.status().is_success(){
        eprintln!("Error fetching input topic from data access service");
        eprintln!("Response Status: {:?}", res.status());
        eprintln!("Response Body: {:?}", res.text().await?);
        process::exit(1);
    }

    let body = res.text().await?;
    let json: Value = serde_json::from_str(&body).unwrap_or_else(|_| {
        eprintln!("Error parsing response from data access service");
        process::exit(1);
    });
    let input_topic = json.get("topic")
        .and_then(|v: &Value| v.as_str())
        .ok_or_else(|| {
            eprintln!("Did not find input topic in response from data access service");
            process::exit(1);
        })
        .unwrap_or_else(|_| {
            eprintln!("Couldn't unwrap input topic");
            process::exit(1);
        });

    // Get output topic from data access service
    println!("Fetching output topic from data access service");
    let res = client.post(&topic_request_url)
        .header("Content-Type", "application/json")
        .json(&json!({
            "type": "output",
            "workload_id": &workload_id.to_string().as_str(),
    }))
        .send()
        .await?;

    if !res.status().is_success(){
        eprintln!("Error fetching output topic from data access service");
        eprintln!("Response Status: {:?}", res.status());
        eprintln!("Response Body: {:?}", res.text().await?);
        process::exit(1);
    }

    let body = res.text().await?;
    let json: Value = serde_json::from_str(&body).unwrap_or_else(|_| {
        eprintln!("Error parsing response from data access service");
        process::exit(1);
    });
    let _output_topic = json.get("topic") // TODO use output topic
        .and_then(|v: &Value| v.as_str())
        .ok_or_else(|| {
            eprintln!("Did not find output topic in response from data access service");
            process::exit(1);
        })
        .unwrap_or_else(|_| {
            eprintln!("Couldn't unwrap output topic");
            process::exit(1);
        });
    

    let input_topic_url = "http://".to_owned() + &kafka_proxy_adress + "/topics/" + &input_topic + "/partitions/0/records";
    let timeout = Duration::from_secs(300);
    let mut offset = 0u64;
    let mut total_sum = 0.0;

    loop {
        if Instant::now().duration_since(start_time) > timeout {
            eprintln!("Timeout reached");
            break;
        }

        println!("Fetching from {}, offset {}", input_topic_url, offset);

        let res = client
            .get(&input_topic_url)
            .header("Accept", "application/vnd.kafka.json.v2+json")
            .query(&[
                ("timeout", "1000"),
                ("max_bytes", "100000"),
                ("offset", &offset.to_string().as_str()),
            ])
            .send()
            .await?;

        println!("Response Status: {:?}", res.status());

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
                    eprintln!("Status message received: {:?}", status);
                    if status == "completed" {
                        println!("Received completion message.");
                        println!("Total sum: {}", total_sum);
                        process::exit(0);
                    }
                    if status == "error" {
                        eprintln!("Received error message.");
                        eprintln!("Error: {}", value.get("error").unwrap_or(&Value::Null));
                        process::exit(1);
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
    eprintln!("No completion message received within timeout");
    process::exit(1);
}