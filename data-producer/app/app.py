import logging
import os
from typing import List
from kafka import KafkaConsumer, KafkaProducer
from kafka.admin import KafkaAdminClient, NewTopic
import json

# Kafka configuration
broker = os.getenv('KAFKA_BROKER')
data_topic = 'test-data'
request_topic = 'data-request'

# Set up logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_topics(topic_names: List[str]):
    try:
        admin_client = KafkaAdminClient(bootstrap_servers=broker)
        new_topics = []
        for topic_name in topic_names:
            if topic_name not in admin_client.list_topics():
                new_topics.append(NewTopic(topic_name, num_partitions=1, replication_factor=1))
                logger.info(f"Topic {topic_name} to be created")
            else:
                logger.info(f"Topic {topic_name} already exists")
        if len(new_topics) > 0:
            logger.info(f"Creating new topics: {new_topics}")
            admin_client.create_topics(new_topics)
    except Exception as e:
        logger.error(f"Error creating topics {topic_names}: {e}")

def load_data_from_json(file_path: str):
    try:
        with open(file_path, 'r') as file:
            data = json.load(file)
        return data
    except Exception as e:
        logger.error(f"Error loading data from JSON file: {e}")
        return [{"error": "Error loading data from JSON file"}]

def handle_data_request():
    consumer = KafkaConsumer(
        request_topic,
        bootstrap_servers=broker,
        group_id='data-request-handler'
        )
    consumer.subscribe([request_topic])
    
    producer = KafkaProducer(
        bootstrap_servers=broker,
        value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )
    
    for message in consumer:
        try:
            request = json.loads(message.value.decode('utf-8'))
            logger.info(f"Received request: {request}")

            data = load_data_from_json("test-data/" + request['file_name'])
            for record in data:
                producer.send(data_topic, value=record)
                logger.info(f"Data sent to topic {data_topic}: {record}")
        except Exception as e:
            logger.error(f"Error processing message: {e}")
    
if __name__ == "__main__":
    create_topics([data_topic, request_topic])
    handle_data_request()
