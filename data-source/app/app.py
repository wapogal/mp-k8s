import json
import logging
import os
import time
import traceback
import requests
from multiprocessing import Process, Event
from typing import Dict
from kafka import KafkaConsumer, KafkaProducer
from shortuuid import ShortUUID

# Env variables
KAFKA_BROKER = os.environ.get('KAFKA_BROKER')
DATA_SOURCES_TOPIC = os.environ.get('DATA_SOURCES_TOPIC')
DATA_SOURCE_TIMEOUT_SECONDS = int(os.environ.get('DATA_SOURCE_TIMEOUT_SECONDS'))
DATA_ACCESS_SERVICE = os.environ.get('DATA_ACCESS_SERVICE')
REGISTRATION_ROUTE = os.environ.get('REGISTRATION_ROUTE')

# set variables
DATA_SOURCE_ID = "test-data-source" + "-" +ShortUUID().random(length=8) 
TEST_DATA_DIRECTORY = "test-data"

# Logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


processes: Dict[str, Process] = {}

def handle_data_request_thread(resource: str, topic: str):
    producer = KafkaProducer(bootstrap_servers=KAFKA_BROKER, value_serializer=lambda v: json.dumps(v).encode('utf-8'))

    try:
        file_path = f"{TEST_DATA_DIRECTORY}/{resource}"
        with open(file_path, 'r') as file:
            data = json.loads(file)
            for record in data:
                producer.send(topic, value=record)
    except Exception as e:
        logger.error(f"Error publishing data for resource {resource} on topic {topic}")
        logger.error(traceback.format_exc())
    
    producer.flush()
    producer.close()
        
def main_run():
    consumer = KafkaConsumer(
        bootstrap_servers=KAFKA_BROKER,
        value_deserializer=lambda v: json.loads(v.decode('utf-8')),
        auto_offset_reset='latest'
        )
    consumer.subscribe([DATA_SOURCES_TOPIC])

    # register each file in test data directory as resource at data access service
    registration_complete = False
    max_retries = 5
    while not registration_complete and max_retries > 0:
        try:
            for file in os.listdir(TEST_DATA_DIRECTORY):
                resource = file
                r = requests.post(f"http://{DATA_ACCESS_SERVICE}/{REGISTRATION_ROUTE}", json={
                    "resource": resource,
                    "data_source_id": DATA_SOURCE_ID
                })
                if r.status_code != 201:
                    logger.error(f"Error registering resource {resource} with data source id {DATA_SOURCE_ID}")
                    logger.error(f"Response: {r.text}")
                    logger.info("Retrying registration in 5 seconds, retries left: " + str(max_retries))
                    max_retries -= 1
                    time.sleep(5)
                else:
                    logger.info(f"Registered resource {resource} with data source id {DATA_SOURCE_ID}")
                    registration_complete = True
        except Exception as e:
            logger.error(f"Error registering resource: {e}")
            logger.error(traceback.format_exc())
            max_retries -= 1
            time.sleep(5)

    for message in consumer:
        try:
            message_data = json.loads(message.value)
            if message_data["event"] == "data_request":
                if message_data["handled_by"] == DATA_SOURCE_ID:
                    resource = message_data['resource']
                    topic = message_data['topic']
                    logger.info(f"Received data request for resource {resource} and topic {topic}")
                    process = Process(target=handle_data_request_thread, args=(resource, topic))
                    if resource not in processes:
                        processes[resource] = []
                    processes[resource].append(process)
                    process.start()
            elif message_data["event"] == "topics_deleted":
                topics = message_data['topics']
                for topic in topics:
                    if topic in processes:
                        logger.info(f"Terminating processes for topic {topic}")
                        processes_to_terminate = len(processes[topic])
                        for i, process in enumerate(processes[topic], start=1):
                            process.terminate()
                            logger.info(f"Terminated process for topic {topic} ({i}/{processes_to_terminate})")
                        processes.pop(topic)
                    processes[topic].terminate()
                    processes.pop(topic)
                    logger.info(f"Terminated all processes for topic {topic}")
        except json.JSONDecodeError as e:
            logger.error(f"Error decoding JSON: {e}")
            logger.error(traceback.format_exc())
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            logger.error(traceback.format_exc())

def heartbeat_run(stop_event):
    producer = KafkaProducer(bootstrap_servers=KAFKA_BROKER, value_serializer=lambda v: json.dumps(v).encode('utf-8'))
    while not stop_event.is_set():
        producer.send(DATA_SOURCES_TOPIC, value=json.dumps({
            "event": "heartbeat",
            "data_source_id": DATA_SOURCE_ID
        }))
        producer.flush()
        time.sleep((DATA_SOURCE_TIMEOUT_SECONDS/2)-1)
    producer.close()

if __name__ == "__main__":
    stop_event = Event()
    heartbeat_process = Process(target=heartbeat_run, args=(stop_event,))
    heartbeat_process.start()

    try:
        main_run()
    except Exception as e:
        logger.error(f"Error in main run: {e}")
        logger.error(traceback.format_exc())
    finally:
        stop_event.set()
        logger.info("Stopping heartbeat process")
        heartbeat_process.join()