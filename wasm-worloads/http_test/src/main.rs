#[tokio::main(flavor = "current_thread")]
async fn main() -> Result<(), reqwest::Error> {
    // Get env variables
    let proxy_address = std::env::var("PROXY_ADDRESS").unwrap();
    let input_topic = std::env::var("INPUT_TOPIC").unwrap();
    // output_topic = std::env::var("OUTPUT_TOPIC").unwrap();

    let request_url = proxy_address + "/topics/" + &input_topic + "/consumer";

    eprintln!("Fetching {} ...", request_url);

    let res = reqwest::get(request_url).await?;

    eprintln!("Response: {:?} {}", res.version(), res.status());
    eprintln!("Headers: {:#?}", res.headers());
    eprintln!("Body: {:#?}", res.text().await?);

    Ok(())
}