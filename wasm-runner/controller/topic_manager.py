import json
import logging
import shortuuid

from kafka import KafkaProducer
from kafka.admin import KafkaAdminClient, NewTopic


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TopicManager:
    def __init__(self, broker, producer_notify_topic, max_idle_topics=10):
        self.admin_client = KafkaAdminClient(bootstrap_servers=broker)
        self.producer_notify_topic = producer_notify_topic
        if producer_notify_topic not in self.admin_client.list_topics():
            self.admin_client.create_topics([NewTopic(producer_notify_topic, num_partitions=1, replication_factor=1)])
        self.producer = KafkaProducer(bootstrap_servers=broker, value_serializer=lambda v: json.dumps(v).encode('utf-8'))
        self.max_idle_topics = max_idle_topics
        self.idle_topics = set()
        self.active_topics = set()
    
    def request_topic(self, type: str) -> str:
        if len(self.idle_topics) > 0:
            topic_id = self.idle_topics.pop()
        else:
            topic_id = self._new_topic()
        
        self._activate_topic(topic_id, type)
        return topic_id
        
    
    def release_topic(self, topic):
        self._deactivate_topic(topic)
        if len(self.idle_topics) < self.max_idle_topics:
            self.idle_topics.add(topic)
        else:
            self._delete_topic(topic)
    
    def _new_topic(self) -> str:
        topic_id = shortuuid.uuid().lower()
        topic = NewTopic(topic_id, num_partitions=1, replication_factor=1)
        self.admin_client.create_topics([topic])
        return topic_id
    
    def _delete_topic(self, topic_id: str):
        self.admin_client.delete_topics([topic_id])
    
    def _activate_topic(self, topic_id: str, type: str):
        self.active_topics.add(topic_id)
        self.producer.send(self.producer_notify_topic, value={"topic_event": {"topic": topic_id, "type": type, "status": "active"}})
    
    def _deactivate_topic(self, topic_id: str):
        self.active_topics.remove(topic_id)
        self.producer.send(self.producer_notify_topic, value={"topic_event": {"topic": topic_id, "status": "inactive"}})
    
