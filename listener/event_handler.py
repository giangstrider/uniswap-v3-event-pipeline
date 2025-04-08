import logging
from typing import Dict, Any, List, Tuple

from event_producer import EventProducer
from metrics import MESSAGES_BY_TOPIC, MESSAGES_PRODUCED, EventProcessingTimer

logger = logging.getLogger(__name__)

class EventHandler:
    """Base class for handling Uniswap V3 events."""
    
    def __init__(self, event_producer: EventProducer) -> None:
        self.event_producer = event_producer

    
    def handle_event(self, event: Dict[str, Any], pool_address: str, pool_name: str) -> None:
        """Process/Parse an event and send it to Kafka."""
        event_type = event.get('event', 'Unknown')
        
        with EventProcessingTimer(event_type):
            event_data = self._get_base_event_data(event, pool_address, pool_name)
            
            specific_data = self._extract_event_specific_data(event)
            event_data.update(specific_data)
            
            # Log the event
            logger.info(f"{event_type} event detected on pool {pool_name} ({pool_address}): {event_data['transactionHash']}")

            headers = self._create_message_headers(event, pool_address)
            
            logger.info(f"Sending event to Kafka:[Topic: {event_type}][Headers: {headers}] {event_data}")
            # Send to Kafka with headers
            self.event_producer.send_message(event_type, event_data, headers=headers)
            
            # Increment metrics
            MESSAGES_PRODUCED.labels(pool_address=pool_address, pool_name=pool_name).inc()
            MESSAGES_BY_TOPIC.labels(topic=event_type, pool_address=pool_address, pool_name=pool_name).inc()
    
    def _extract_event_specific_data(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Extract event-specific data by dynamically getting all args."""
        # Dynamically extract all keys from the args dictionary
        if 'args' in event:
            return dict(event['args'])
        return {}
    
    def _get_base_event_data(self, event: Dict[str, Any], pool_address: str, pool_name: str) -> Dict[str, Any]:
        """Get common event data fields."""
        return {
            'poolAddress': pool_address,
            'poolName': pool_name,
            'blockNumber': event['blockNumber'],
            'transactionHash': event['transactionHash'],
            'timestamp': event['timestamp'],
            'event': event.get('event', 'Unknown')
        }
    
    def _create_message_headers(self, event: Dict[str, Any], pool_address: str) -> List[Tuple[str, bytes]]:
        """Create Kafka message headers with metadata."""
        # Convert values to bytes as required by Kafka headers
        return [
            ('blockNumber', str(event['blockNumber']).encode('utf-8')),
            ('poolAddress', pool_address.encode('utf-8')),
            ('blockTimestamp', str(event['timestamp']).encode('utf-8'))
        ]
