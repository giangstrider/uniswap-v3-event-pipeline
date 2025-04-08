import logging
import json
from typing import Dict, Any, List, Optional, Tuple, Set
from database_client import DatabaseClient
from metrics import (
    MESSAGES_PROCESSED, 
    BATCH_SIZE, 
    MAX_BLOCK_NUMBER, 
    BatchProcessingTimer, 
    ERROR_COUNT
)

logger = logging.getLogger(__name__)

class MessageProcessor:
    """Process messages from Kafka and save to database."""
    
    def __init__(self, db_client: DatabaseClient) -> None:
        self.db_client = db_client
    
    def process_message_batch(self, messages_by_topic: Dict[str, List[bytes]]) -> bool:
        """
        Process a batch of messages from Kafka and save to database.
        
        Args:
            messages_by_topic: Dictionary mapping Kafka topics (str) to lists of message values (bytes)
            
        Returns:
            bool: True if successfully processed, False otherwise
        """
        if not messages_by_topic:
            return True
            
        try:
            # Group messages by event type
            event_batches = {}
            
            # Parse all messages and group by event type
            for topic, messages in messages_by_topic.items():
                # Record batch size for this topic
                BATCH_SIZE.labels(topic=topic).observe(len(messages))
                
                # Initialize the batch list for this event type
                event_batches[topic] = []
                
                with BatchProcessingTimer(topic):
                    for message in messages:
                        try:
                            # Decode and parse the message
                            message_str = message.decode('utf-8')                           
                            event_data = json.loads(message_str)

                            if event_data:
                                event_batches[topic].append(event_data)
                                
                                # Update max block number if present
                                if 'blockNumber' in event_data and 'poolAddress' in event_data:
                                    MAX_BLOCK_NUMBER.labels(
                                        pool_address=event_data['poolAddress']
                                    ).set(event_data['blockNumber'])
                            else:
                                logger.warning(f"Empty event data after parsing: {message_str}")
                            
                        except json.JSONDecodeError as e:
                            logger.error(f"Invalid JSON in message: {message}")
                            ERROR_COUNT.labels(error_type="JSONDecodeError").inc()
                            raise e
                        except Exception as e:
                            logger.error(f"Error parsing message: {e}")
                            ERROR_COUNT.labels(error_type=type(e).__name__).inc()
                            raise e
            
            # Process each event type batch
            success = True
            for event_type, batch in event_batches.items():
                if batch:
                    batch_success = self.db_client.save_event_batch(event_type, batch)
                    success = success and batch_success
                    
                    if batch_success:
                        # Count successfully processed messages
                        MESSAGES_PROCESSED.labels(topic=event_type).inc(len(batch))
            
            return success
                
        except Exception as e:
            logger.error(f"Error processing message batch: {e}")
            ERROR_COUNT.labels(error_type=type(e).__name__).inc()
            return False
