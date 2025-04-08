import os
import logging
import signal
import sys
import threading
import json
from database_client import DatabaseClient
from message_processor import MessageProcessor
from message_consumer import MessageConsumer
from typing import Dict, List

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

# Global reference to resources that need cleanup
consumer = None
db_client = None


def signal_handler(sig, frame):
    """Handle shutdown signals gracefully."""
    logger.info(f"Received signal {sig}, shutting down...")
    
    ACTIVE.set(0)
    
    if consumer:
        consumer.request_shutdown()
    
    # Exit after 30 seconds at most
    def force_exit():
        logger.warning("Forcing exit after timeout")
        sys.exit(1)
    
    # Schedule force exit after timeout
    exit_timer = threading.Timer(30.0, force_exit)
    exit_timer.daemon = True
    exit_timer.start()

def load_event_type_config() -> List[str]:
    """
    Load event type configuration from ABI file.
    """
    # Load ABI for event type configuration
    abi_dir = os.environ.get('ABI_DIR', 'abi')
    abi_file = os.environ.get('ABI_FILE', 'uniswap_v3_pool.json')
    
    event_type_config = []
    with open(f"{abi_dir}/{abi_file}", 'r') as file:
        abi = json.load(file)
        # Extract event types from ABI
        for item in abi:
            if item.get('type') == 'event':
                event_name = item.get('name')
                if event_name:
                    event_type_config.append(event_name)

    logger.info(f"Loaded event type configuration: {event_type_config}")
    return event_type_config

def main() -> None:
    """Main entry point for the consumer service."""
    global consumer, db_client

    
    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    # Get environment variables
    database_url = os.environ.get('DATABASE_URL')
    kafka_brokers = os.environ.get('KAFKA_BROKERS', 'kafka:9092')
    kafka_topics = load_event_type_config()
    consumer_group = os.environ.get('KAFKA_CONSUMER_GROUP', 'uniswap-event-consumer')
    
    # Batch configuration
    batch_size = int(os.environ.get('BATCH_SIZE', '100'))
    batch_timeout = float(os.environ.get('BATCH_TIMEOUT', '5.0'))

    # Load ABI for table creation
    abi_dir = os.environ.get('ABI_DIR', 'abi')
    abi_file = os.environ.get('ABI_FILE', 'uniswap_v3_pool.json')
    abi_path = f"{abi_dir}/{abi_file}"
    
    with open(abi_path, 'r') as file:
        abi_data = json.load(file)
    
    try:
        # Set active gauge to 1
        ACTIVE.set(1)
        
        # Create clients
        db_client = DatabaseClient(database_url)
        
        # Create tables based on ABI before processing any data
        logger.info("Creating tables from ABI definitions")
        db_client.create_tables_from_abi(abi_data)
        
        processor = MessageProcessor(db_client)
        
        # Create and start the consumer
        consumer = MessageConsumer(
            brokers=kafka_brokers,
            topics=kafka_topics,
            group_id=consumer_group,
            processor=processor,
            batch_size=batch_size,
            batch_timeout=batch_timeout
        )
        
        # Start consuming messages (blocking)
        logger.info("Starting consumer service")
        consumer.consume()
        
    except KeyboardInterrupt:
        logger.info("Consumer service stopped via keyboard interrupt")
    except Exception as e:
        logger.error(f"Error in consumer service: {e}")
    finally:
        # Clean up resources
        if consumer:
            consumer.close()
        
        if db_client:
            db_client.close()
        
        logger.info("Consumer service shutdown complete")

if __name__ == "__main__":
    main() 