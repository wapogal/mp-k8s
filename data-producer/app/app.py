import threading
import json
import os
import logging
from kafka import KafkaConsumer, KafkaProducer
from kafka.admin import KafkaAdminClient, NewTopic
from queue import Queue

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

data_topic = 'test-data'
request_topic = 'data-request'

class DataProducer:
    def __init__(self, broker, producer_notify_topic):
        self.broker = broker
        self.producer_notify_topic = producer_notify_topic
        admin_client = KafkaAdminClient(bootstrap_servers=broker)
        if self.producer_notify_topic not in admin_client.list_topics():
                admin_client.create_topics([NewTopic(self.producer_notify_topic, num_partitions=1, replication_factor=1)])
        self.producer = KafkaProducer(bootstrap_servers=broker, value_serializer=lambda v: json.dumps(v).encode('utf-8'))
        self.consumer = KafkaConsumer(
            producer_notify_topic,
            bootstrap_servers=broker,
            value_deserializer=lambda v: json.loads(v.decode('utf-8')),
            auto_offset_reset='latest'
            )
        self.consumer.subscribe([producer_notify_topic])
        self.task_queue = Queue()
        self.active_topics = set()

    def produce_data(self, topic):
        logger.info(f"Starting data production for topic: {topic}")
        try:
            with open(f"test-data/sample_data.json", 'r') as file:
                data = json.load(file)
                for record in data:
                    self.producer.send(topic, value=record)
                    logger.info(f"Data sent to topic {topic}: {record}")
        except Exception as e:
            logger.error(f"Error producing data: {e}")

        self.producer.send(topic, value={"status": "completed"})
        logger.info(f"Finished sending data to topic {topic}")

    def handle_topic_event(self):
        while True:
            event = self.task_queue.get()
            if event is None:
                break
            logger.info(f"Handling topic event: {event}")
            topic_event = event['topic_event']
            topic_id = topic_event['topic']
            status = topic_event['status']

            if status == "created":
                type = topic_event['type']
                if type == "input":
                    self.active_topics.add(topic_id)
                    self.produce_data(topic_id)
            elif status == "deleted" and topic_id in self.active_topics:
                self.active_topics.remove(topic_id)

    def consume_events(self):
        for event in self.consumer:
            self.task_queue.put(event.value)

    def run(self):
        logger.info("Starting DataProducer...")

        consumer_thread = threading.Thread(target=self.consume_events)
        worker_thread = threading.Thread(target=self.handle_topic_event)

        consumer_thread.start()
        worker_thread.start()

        consumer_thread.join()
        worker_thread.join()

if __name__ == "__main__":
    broker = os.getenv('KAFKA_BROKER')
    notifications_topic = os.getenv('KAFKA_NOTIFY_TOPIC')
    data_producer = DataProducer(broker, notifications_topic)
    data_producer.run()