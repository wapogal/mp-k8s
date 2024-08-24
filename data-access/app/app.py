import asyncio
import json
import os
import logging
import random
import traceback
from typing import Dict, List
from kafka import KafkaConsumer, KafkaProducer
from kafka.admin import KafkaAdminClient, NewTopic
from flask import Flask, request
from shortuuid import ShortUUID
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Env variables
KAFKA_BROKER = os.environ.get('KAFKA_BROKER')
DATA_REQUEST_ROUTE = os.environ.get('DATA_REQUEST_ROUTE')
REGISTRATION_ROUTE = os.environ.get('REGISTRATION_ROUTE')
WORKLOAD_NOTIFICATION_TOPIC = os.environ.get('WORKLOAD_NOTIFICATION_TOPIC')
DATA_SOURCES_TOPIC = os.environ.get('DATA_SOURCES_TOPIC')
DATA_SOURCE_TIMEOUT_SECONDS = int(os.environ.get('DATA_SOURCE_TIMEOUT_SECONDS'))

# Flask
app = Flask(__name__)

# Kafka
admin_client = KafkaAdminClient(bootstrap_servers=KAFKA_BROKER)
producer = KafkaProducer(bootstrap_servers=KAFKA_BROKER, value_serializer=lambda v: json.dumps(v).encode('utf-8'))
consumer = KafkaConsumer(
    bootstrap_servers=KAFKA_BROKER,
    value_deserializer=lambda v: json.loads(v.decode('utf-8')),
    auto_offset_reset='latest'
    )

active_workloads: Dict[str, Dict[str, List[str]]] = {} # This stores acctive workloads and their input/output topics

data_resources : Dict[str, List[str]] = {}
data_sources_last_seen: Dict[str, datetime] = {}

@app.route('/' + REGISTRATION_ROUTE, methods=['POST'])
def registration():
    data = request.get_json()
    resource = data['resource']
    data_source_id = data['data_source_id']

    data_sources_last_seen[data_source_id] = datetime.now()

    if resource not in data_resources:
        data_resources[resource] = []
    
    if data_source_id in data_resources[resource]:
        return {"status": "error", "message": "Data source already registered for this resource"}, 400
    
    data_resources[resource].append(data_source_id)
    return {"status": "success", "message": "Registration successful"}, 201

@app.route('/' + DATA_REQUEST_ROUTE, methods=['POST'])
def data_request():
    data = request.get_json()
    workload_id = data['workload_id']

    if workload_id not in active_workloads:
        active_workloads[workload_id] = {
            'input': [],
            'output': []
        }

    try:
        if request['type'] == 'input':
            resource = data['resource']
            if resource not in data_resources:
                logger.error(f"Resource {resource} not found in data source list")
                return {"status": "error", "message": "Resource not found"}, 400
            
            topic_id = ShortUUID().random(length=8) + "-" + resource + "-" + "input"
            ensure_topic_exists(topic_id, unique=True)

            active_workloads[workload_id]['input'].append(topic_id)
            notify_data_request(topic_id, resource)
            return {"status": "success", "topic": topic_id, "message": "Input topic created"}, 201
        elif request['type'] == 'output':
            topic_id = ShortUUID().random(length=8) + "-workload-output"
            ensure_topic_exists(topic_id, unique=True)
            active_workloads[workload_id]['output'].append(topic_id)
            return {"status": "success", "topic": topic_id, "message": "Output topic created"}, 201
    except Exception as e:
        logger.error(f"Error creating topic: {e}")
        logger.error(traceback.format_exc())
        return {"status": "error", "message": "Error creating topic: " + str(e)}, 500
      

def notify_data_request(topic: str, resource: str):
    handled_by = random.choice(data_resources[resource])
    producer.send(DATA_SOURCES_TOPIC, value=json.dumps({
        "event": "data_request",
        "handled_by": handled_by,
        "resource": resource,
        "topic": topic
    }))

def delete_topics_and_notify(topics: List[str]):
    admin_client.delete_topics(topics)
    producer.send(DATA_SOURCES_TOPIC, value=json.dumps({
        "event": "topics_deleted",
        "topics": topics
    }))


def handle_workload_event(event):
    if event['event'] == 'deleted':
        if event['workload_id'] not in active_workloads:
            logger.error(f"Trying to delete workload {event['workload_id']}, but was not found in active workloads.")
        else:
            delete_topics_and_notify(active_workloads[event['workload_id']]['input'])
            admin_client.delete_topics(active_workloads[event['workload_id']]['output'])
            active_workloads.pop(event['workload_id'])
            logger.info(f"Workload topics for {event['workload_id']} deleted")

def handle_data_source_event(event):
    if event['event'] == 'heartbeat':
        data_sources_last_seen[event['data_source_id']] = datetime.now()

def ensure_topic_exists(topic: str, unique: bool = False):
    admin_client = KafkaAdminClient(bootstrap_servers=KAFKA_BROKER)
    if topic not in admin_client.list_topics():
        admin_client.create_topics([NewTopic(topic, num_partitions=1, replication_factor=1)])
    elif unique:
        raise Exception(f"Topic {topic} should be unique but already exists")

def listener_run():
    ensure_topic_exists(WORKLOAD_NOTIFICATION_TOPIC)
    ensure_topic_exists(DATA_SOURCES_TOPIC)
    consumer.subscribe([WORKLOAD_NOTIFICATION_TOPIC, DATA_SOURCES_TOPIC])

    for message in consumer:
        try:
            event_data = json.loads(message.value)
            logger.info(f"Received message on topic {message.topic} with value: {event_data}")
            
            if message.topic == WORKLOAD_NOTIFICATION_TOPIC:
                handle_workload_event(event_data)
            elif message.topic == DATA_SOURCES_TOPIC:
                handle_data_source_event(event_data)
        except json.JSONDecodeError as e:
            logger.error(f"Error decoding JSON: {e}")
            logger.error(traceback.format_exc())
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            logger.error(traceback.format_exc())

def clean_up_run():
    while True:
        for data_source_id, last_seen in data_sources_last_seen.items():
            if last_seen + timedelta(seconds=DATA_SOURCE_TIMEOUT_SECONDS) < datetime.now():
                logger.info(f"Data source {data_source_id} timed out")
                data_sources_last_seen.pop(data_source_id)
                for resource in data_resources:
                    if data_source_id in data_resources[resource]:
                        data_resources[resource].remove(data_source_id)
                        logger.info(f"Removed data source {data_source_id} from resource {resource}")
        asyncio.sleep(5)
    

def http_api_run():
    app.run(host='0.0.0.0', port=5001)

def run():
    asyncio.gather(listener_run(), clean_up_run())

if __name__ == "__main__":
    asyncio.run(run())
    