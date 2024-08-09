#[tokio::main(flavor = "current_thread")]
async fn main() -> Result<(), reqwest::Error> {
    // Get env variables
    let proxy_ip = std::env::var("PROXY_IP").unwrap();
    let proxy_port = std::env::var("PROXY_PORT").unwrap();
    let input_topic = std::env::var("INPUT_TOPIC").unwrap();
    let workload_id = std::env::var("WORKLOAD_ID").unwrap();
    // let output_topic = std::env::var("OUTPUT_TOPIC").unwrap();

    let client = reqwest::Client::new();

    // Create consumer
    let consumer_url = "http://".to_owned() + &proxy_ip + ":" + &proxy_port + "/consumers/my-group"; // TODO manage consumer groups better than this so they also get deleted
    eprintln!("Creating consumer group on {}", consumer_url.clone());
    let create_consumer_body = r#"{
        "name": ""#.to_owned() + &workload_id + r#"",
        "format": "json",
        "auto.offset.reset": "earliest"
    }"#;

    let res = client.post(&consumer_url)
        .header("Content-Type", "application/vnd.kafka.v2+json")
        .body(create_consumer_body)
        .send()
        .await?;

    eprintln!("Got response: {:?}", res);
    
    let subscribe_url = consumer_url.clone() + "/instances/" + &workload_id + "/subscription";
    eprintln!("Subscribing on {}", subscribe_url.clone());
    let subscribe_body = r#"{"topics":[""#.to_owned() + &input_topic + r#""]}"#;
    let res = client.post(&subscribe_url)
        .header("Content-Type", "application/vnd.kafka.v2+json")
        .body(subscribe_body)
        .send()
        .await?;

    eprintln!("Got response: {:?}", res);

    let fetch_url = consumer_url.clone() + "/instances/" + &workload_id + "/records";


    let mut last_message_received = false;

    while !last_message_received {
        eprintln!("Fetching from {}", fetch_url.clone());
        let res = client.get(&fetch_url)
            .header("Accept", "application/vnd.kafka.json.v2+json")
            .send()
            .await?;

        eprintln!("Response: {:?}", res);

        let body = res.text().await?;
        eprintln!("Response Body: {:?}", body);

        last_message_received = true;
    }

    Ok(())
}