import json
import logging
from typing import Dict, Any, Optional, List
from kafka import KafkaProducer

logger = logging.getLogger(__name__)

class EventProducer:
    """Class for producing events to Kafka."""
    
    def __init__(self, brokers: str) -> None:
        """
        Initialize the Event Producer.
        
        Args:
            brokers (str): Kafka broker addresses, comma-separated
        """
        self.brokers = brokers
        self.producer = self.create_producer()
    
    def create_producer(self) -> KafkaProducer:
        """Create and return a Kafka producer."""
        logger.info(f"Connecting to Kafka at {self.brokers}")
        return KafkaProducer(
            bootstrap_servers=self.brokers,
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )
    
    def send_message(self, topic: str, message: Dict[str, Any], headers: Optional[List[tuple]] = None) -> None:
        """
        Send a message to a Kafka topic.
        """
        self.producer.send(topic, message, headers=headers)
        self.producer.flush()