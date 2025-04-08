import os
import logging
from typing import Dict

from config_loader import ConfigLoader
from web3_client import Web3Client
from event_producer import EventProducer
from event_handler import EventHandler
from event_listener import EventListener
from metrics import start_metrics_server

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def main() -> None:
    # Get environment variables
    eth_rpc_url: str = os.environ.get('ETH_RPC_URL', '')
    kafka_brokers: str = os.environ.get('KAFKA_BROKERS', 'kafka:9092')
    config_file: str = os.environ.get('CONFIG_FILE', 'config/pool_config.json')
    abi_dir: str = 'abi'
    metrics_port: int = int(os.environ.get('METRICS_PORT', '8001'))
    
    # Start metrics server
    start_metrics_server(metrics_port)
    
    # Create clients
    config_loader = ConfigLoader(config_file=config_file, abi_dir=abi_dir)
    web3_client = Web3Client(rpc_url=eth_rpc_url)
    kafka_client = EventProducer(brokers=kafka_brokers)
    
    
    # Create and start the event listener
    listener = EventListener(
        config_loader=config_loader,
        web3_client=web3_client,
        event_handler=EventHandler(event_producer=kafka_client)
    )
    
    # Start listening for events
    listener.listen()

if __name__ == "__main__":
    main() 