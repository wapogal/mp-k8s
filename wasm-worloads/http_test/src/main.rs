use std::thread::sleep;
use std::time::Duration;

#[tokio::main(flavor = "current_thread")]
async fn main() -> Result<(), reqwest::Error> {
    // Get env variables
    let proxy_ip = std::env::var("PROXY_IP").unwrap();
    let proxy_port = std::env::var("PROXY_PORT").unwrap();
    let input_topic = std::env::var("INPUT_TOPIC").unwrap();

    let request_url = "http://".to_owned() + &proxy_ip + ":" + &proxy_port + "/topics/" + &input_topic + "/partitions/0/records";


    sleep(Duration::from_secs(10));

    eprintln!("Fetching from {}", request_url);

    let client = reqwest::Client::new();

    let res = client
        .get(&request_url)
        .header("Accept", "application/vnd.kafka.json.v2+json")
        .query(&[
            ("offset", "0"),
            ("timeout", "1000"),
            ("max_bytes", "100000"),
        ])
        .send()
        .await?;

    eprintln!("Response Status: {:?}", res.status());

    let body = res.text().await?;
    eprintln!("Response Body: {:?}", body);

    Ok(())
}