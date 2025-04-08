import logging
import time
import signal
import threading
from typing import Dict, Any, List, Tuple
from kafka import KafkaConsumer
from kafka.structs import TopicPartition, OffsetAndMetadata
from message_processor import MessageProcessor
from metrics import MESSAGES_CONSUMED, ERROR_COUNT

logger = logging.getLogger(__name__)

class MessageConsumer:
    """Consume messages from Kafka and process them."""
    
    def __init__(
        self, 
        brokers: str, 
        topics: List[str], 
        group_id: str, 
        processor: MessageProcessor,
        batch_size: int = 100,
        batch_timeout: float = 5.0
    ) -> None:
        """
        Initialize the Kafka consumer.
        
        Args:
            brokers (str): Kafka broker addresses, comma-separated
            topics (list): Kafka topics to consume from
            group_id (str): Consumer group ID
            processor (MessageProcessor): Processor for handling messages
            batch_size (int): Maximum number of messages to process in a batch
            batch_timeout (float): Maximum time to wait for a batch to fill up (seconds)
        """
        self.brokers = brokers
        self.topics = topics
        self.group_id = group_id
        self.processor = processor
        self.batch_size = batch_size
        self.batch_timeout = batch_timeout
        self.consumer = None
        self.running = False
        self.shutdown_event = threading.Event()
    
    def _create_consumer(self) -> KafkaConsumer:
        """Create and return a Kafka consumer."""
        logger.info(f"Connecting to Kafka at {self.brokers}, topics: {self.topics}, group: {self.group_id}")
        
        # Create consumer without retry logic
        consumer = KafkaConsumer(
            *self.topics,
            bootstrap_servers=self.brokers,
            group_id=self.group_id,
            # Disable auto-commit to implement manual acknowledgment
            enable_auto_commit=False,
            auto_offset_reset='earliest',
            value_deserializer=lambda x: x,
            # Add reasonable consumer timeout to check for shutdown
            consumer_timeout_ms=1000
        )
        return consumer
    
    def consume(self) -> None:
        """
        Continuously consume messages from Kafka in batches.
        
        This method will block until shutdown is requested, processing messages in batches.
        """
        self.running = True
        self.consumer = self._create_consumer()
        
        logger.info(f"Starting to consume from topics: {self.topics}")
        
        try:
            while self.running and not self.shutdown_event.is_set():
                try:
                    # Collect a batch of messages
                    message_batch = {}  # Topic: value
                    offsets_to_commit = {}  # {TopicPartition: OffsetAndMetadata}
                    
                    batch_start_time = time.time()
                    
                    # Keep pulling messages until we reach batch size or timeout
                    while (len(message_batch) < self.batch_size and 
                           time.time() - batch_start_time < self.batch_timeout and
                           self.running and not self.shutdown_event.is_set()):
                        
                        # Poll with a short timeout to check shutdown frequently
                        message_poll = self.consumer.poll(timeout_ms=100, max_records=self.batch_size - len(message_batch))
                        
                        if not message_poll:
                            if message_batch:
                                break
                            # No messages yet, keep waiting until timeout
                            continue
                        
                        # Process the polled messages
                        for tp, messages in message_poll.items():
                            for message in messages:
                                topic = tp.topic
                                
                                # Track message consumption metrics
                                MESSAGES_CONSUMED.labels(topic=topic).inc()
                                
                                if topic not in message_batch:
                                    message_batch[topic] = []
                                message_batch[topic].append(message.value)
                                # Track latest offset for each partition
                                offsets_to_commit[tp] = OffsetAndMetadata(message.offset + 1, metadata=None, leader_epoch=-1)
                    
                    # Process the batch if we have any messages
                    if message_batch:
                        logger.info(f"Processing batch of {sum(len(msgs) for msgs in message_batch.values())} messages across {len(message_batch)} topics")
                        success = self.processor.process_message_batch(message_batch)
                        
                        if success:
                            # Commit the offsets if processing was successful
                            if offsets_to_commit:
                                self.consumer.commit(offsets_to_commit)
                                logger.info(f"Committed offsets for {len(offsets_to_commit)} partitions")
                        else:
                            logger.error("Failed to process message batch, not committing offsets")
                    
                except Exception as e:
                    logger.error(f"Error in batch processing: {e}")
                    ERROR_COUNT.labels(error_type=type(e).__name__).inc()
                    raise e
        
        finally:
            self.close()
    
    def close(self) -> None:
        """
        Close the consumer and clean up resources.
        """
        self.running = False
        
        if self.consumer:
            try:
                # Make sure to commit any pending offsets before closing
                self.consumer.close()
                logger.info("Kafka consumer closed")
            except Exception as e:
                logger.error(f"Error closing Kafka consumer: {e}")
                ERROR_COUNT.labels(error_type=type(e).__name__).inc()
    
    def request_shutdown(self) -> None:
        """
        Signal the consumer to shut down gracefully.
        """
        logger.info("Shutdown requested")
        self.running = False
        self.shutdown_event.set() 