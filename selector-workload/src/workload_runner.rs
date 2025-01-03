use std::collections::HashMap;
use std::fs::File;
use std::io::Write;
use std::time::{Duration, Instant};

use reqwest::Client;
use serde_json::{json, Value};

pub struct WorkloadRunner {
    // Event times for logging
    event_times: Vec<(Instant, String)>,

    // Environment variables
    kafka_proxy_address: String,
    topic_request_url: String,
    workload_id: String,
    pub settings: Value,

    // HTTP client
    client: Client,

    // Topic URLs
    input_topic_urls: HashMap<String, (bool, String, u64)>,
    output_topic_urls: HashMap<String, String>,
}

impl WorkloadRunner {
    pub fn new() -> Self {
        // Initialize event times with start time
        let mut event_times = vec![(Instant::now(), "start".to_string())];

        // Fetch environment variables
        event_times.push((Instant::now(), "fetching env variables".to_string()));
        let kafka_proxy_address = std::env::var("KAFKA_PROXY_ADDRESS").unwrap();
        let data_access_address = std::env::var("DATA_ACCESS_ADDRESS").unwrap();
        let data_request_route = std::env::var("DATA_REQUEST_ROUTE").unwrap();
        let workload_id = std::env::var("WORKLOAD_ID").unwrap();
        let settings_string = std::env::var("SETTINGS").unwrap();
        event_times.push((Instant::now(), format!("got env variables:: workload_id: {}, kafka_proxy_address: {}, data_access_address: {}, data_request_route: {}", workload_id, kafka_proxy_address, data_access_address, data_request_route)));
        
        let settings: Value = serde_json::from_str(&settings_string).unwrap();

        let topic_request_url = "http://".to_owned() + &data_access_address + "/" + &data_request_route;

        // Set up the HTTP client
        event_times.push((Instant::now(), "setting up client".to_string()));
        let client = Client::new();
        event_times.push((Instant::now(), "client set up".to_string()));

        // Return the initialized struct
        Self {
            event_times,
            kafka_proxy_address,
            topic_request_url,
            workload_id,
            settings,
            client,
            input_topic_urls: HashMap::new(),
            output_topic_urls: HashMap::new(),
        }
    }

    pub fn timeout_reached(&mut self) -> bool {
        let timeout_duration : Duration = Duration::from_secs(self.settings["timeout"].as_u64().unwrap());
        if Instant::now().duration_since(self.event_times.first().unwrap().0) > timeout_duration {
            self.log_error("Timeout reached".to_string());
            true
        }
        else {
            false
        }
    }

    fn output_before_exit(&mut self) {
        let start_time = self.event_times.first().map(|(instant, _)| *instant);
        self.log_event("end (drop)".to_string());
        if let Some(start_time) = start_time {
            println!("Event times:");
            for (instant, event) in &self.event_times {
                println!("{}: {}", instant.duration_since(start_time).as_millis(), event);
            }
            println!("Printed {} events", self.event_times.len());

            // Write to file
            let file_name = "/logs/event_times_".to_owned() + &self.workload_id + ".csv";
            let mut file = File::create(file_name).unwrap();
            for (instant, event) in &self.event_times {
                writeln!(file, "{}, {};", instant.duration_since(start_time).as_millis(), event).unwrap();
            }
            println!("Event times written to file");
        }
    }

    async fn send_topic_request(&mut self, request_type: &str, resource: &str) -> Result<String, String> {
        self.log_event(format!("sending topic request:: type: {}, resource: {}", request_type, resource));

        let res = self.client.post(&self.topic_request_url)
            .header("Content-Type", "application/json")
            .json(&json!({
                "type": request_type,
                "resource": resource,
                "workload_id": &self.workload_id,
            }))
            .send()
            .await
            .map_err(|e| {
                self.log_error(format!("topic request failed:: type: {}, resource: {}", request_type, resource));
                e.to_string()
            })?;

        if !res.status().is_success() {
            self.log_error(format!("topic response status was not success:: type: {}, resource: {}, status: {}", request_type, resource, res.status()));
            return Err("Topic response failed".to_string());
        }

        let body = res.text().await.map_err(|e| e.to_string())?;
        let json: Value = serde_json::from_str(&body).map_err(|_| {
            self.log_error(format!("Error parsing response from data access service:: type: {}, resource: {}", request_type, resource));
            "Failed to parse JSON".to_string()
        })?;

        let topic = json.get("topic")
            .and_then(|v| v.as_str())
            .ok_or_else(|| {
                self.log_error(format!("Did not find topic in response:: type: {}, resource: {}", request_type, resource));
                "Topic not found".to_string()
            })?;
        
        self.log_event(format!("Got topic:: type: {}, resource: {}, topic: {}", request_type, resource, topic));
        Ok(topic.to_string())
    }

    pub fn log_error(&mut self, error: String) {
        self.event_times.push((Instant::now(), error));
        // eprintln!("{}", error);
    }

    pub fn log_event(&mut self, event: String) {
        self.event_times.push((Instant::now(), event));
        // println!("{}", event);
    }

    async fn get_input_topic(&mut self, resource: &str) -> Result<(), String> {
        let topic = self.send_topic_request("input", resource).await?;
        let topic_url = format!("http://{}/topics/{}/partitions/0/records", self.kafka_proxy_address, topic);
        self.input_topic_urls.insert(resource.to_string(), (false, topic_url, 0u64));
        Ok(())
    }

    async fn get_output_topic(&mut self) -> Result<(), String> {
        let topic = self.send_topic_request("output", "").await?;
        let topic_url = format!("http://{}/topics/{}/partitions/0/records", self.kafka_proxy_address, topic);
        self.output_topic_urls.insert(topic.clone(), topic_url);
        Ok(())
    }

    pub async fn request_from_resource(&mut self, resource: &str) -> Result<(Vec<Value>, bool), String> {
        self.log_event(format!("requesting:: resource: {}", resource));
        if !self.input_topic_urls.contains_key(resource) {
            self.get_input_topic(resource).await?;
        }
        
        let (final_msg_received, topic_url, offset) = {
            let entry = self.input_topic_urls.get_mut(resource).unwrap();
            (entry.0, entry.1.clone(), entry.2)
        };
        
        if final_msg_received {
            self.log_error(format!("final message already received:: resource: {}", resource));
            return Err("final message already received".to_string());
        }

        self.log_event(format!("requesting from:: resource: {}, url: {}, offset: {}", resource, topic_url, offset));
        let res = self.client
            .get(&topic_url)
            .header("Accept", "application/vnd.kafka.json.v2+json")
            .query(&[
                ("timeout", self.settings["request"]["timeout"].as_u64().unwrap_or_else(|| {
                    self.log_event(format!("Using default timeout: {}", 1000));
                    1000
                }).to_string().as_str()),
                ("max_bytes", self.settings["request"]["max_bytes"].as_u64().unwrap_or_else(|| {
                    self.log_event(format!("Using default max_bytes: {}", 1000000));
                    1000000
                }).to_string().as_str()),
                ("offset", &offset.to_string()),
            ])
            .send()
            .await
            .map_err(|e| {
                self.log_error(format!("topic request failed:: resource: {}", resource));
                e.to_string()
            })?;
        self.log_event(format!("topic request finished:: resource: {}", resource));
        
        if !res.status().is_success() {
            self.log_error(format!("topic response status was not success:: resource: {}, status: {}", resource, res.status()));
            return Err("topic response status was not success".to_string());
        }

        let body = res.text().await.map_err(|e| e.to_string())?;
        
        let messages: Vec<Value> = serde_json::from_str(&body).unwrap_or_else(|_| vec![]);

        let (mut final_msg_received, mut offset) = {
            let entry = self.input_topic_urls.get_mut(resource).unwrap();
            (entry.0, entry.2)
        };

        if let Some(last_message) = messages.last() {
            if let Some(offset_val) = last_message.get("offset").and_then(|v| v.as_u64()) {
                offset = offset_val + 1;
            }
            if let Some(value) = last_message.get("value") {
                if let Some(status) = value.get("status") {
                    if status == "error" {
                        self.log_error(format!("Received error message:: resource: {}, offset: {}", resource, offset));
                        return Err("Received error message".to_string());
                    }
                    if status == "completed" {
                        self.log_event(format!("Received completion message:: resource: {}, offset: {}", resource, offset));
                        final_msg_received = true;
                        self.input_topic_urls.get_mut(resource).unwrap().0 = final_msg_received;
                    }
                }
            }
        }
        self.input_topic_urls.get_mut(resource).unwrap().2 = offset;
        Ok((messages, final_msg_received))
    }
}

impl Drop for WorkloadRunner {
    fn drop(&mut self) {
        self.output_before_exit();
    }
}