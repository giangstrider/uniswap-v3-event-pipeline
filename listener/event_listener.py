import time
import logging
import traceback
from typing import Dict, List, Any, Optional, Mapping
from web3.contract import Contract
from web3.types import FilterParams

from config_loader import ConfigLoader
from web3_client import Web3Client
from event_handler import EventHandler

logger = logging.getLogger(__name__)

class EventListener:
    """Main class for listening to Uniswap V3 Pool events."""
    
    def __init__(
        self, 
        config_loader: ConfigLoader, 
        web3_client: Web3Client, 
        event_handler: EventHandler,
    ) -> None:
        """
        Initialize the event listener.
        """
        self.config_loader = config_loader
        self.web3_client = web3_client
        self.event_handler = event_handler
    
    def create_event_filters(self, pool_configs: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """Create event filters for all pools and event types."""
        filters: Dict[str, Dict[str, Any]] = {}
        for pool in pool_configs:
            pool_address = pool['address']
            pool_name = pool['name']
            abi = pool['abi']
            
            contract: Contract = self.web3_client.get_contract(pool_address, abi)
            pool_filters: Dict[str, FilterParams] = {}
            
            # Create filters based on configured event types
            for event_type in contract.events:
                event_type_name = event_type.name
                event_type_lower = event_type_name.lower()

                pool_filters[event_type_lower] = getattr(
                    contract.events, event_type_name.capitalize()
                ).create_filter(from_block='latest')
            
            filters[pool_address] = {
                'filters': pool_filters,
                'name': pool_name
            }
            logger.info(f"Created filters for pool: {pool_name} ({pool_address}) with events: {list(pool_filters.keys())}")
        return filters
    
    def listen(self) -> None:
        """
        Main function to listen for Uniswap V3 Pool events across multiple pools.
        
        This method continuously polls for new events from configured Uniswap pools:
        - Creates event filters for each pool and event type
        - Enters a continuous loop to check for new events
        - For each new event, retrieves block timestamp and passes to appropriate handler
        - Uses get_new_entries() to only process events that haven't been seen before
        - Includes error handling and rate limiting to prevent excessive resource usage
        """
        pool_configs = self.config_loader.load_pool_config()
        
        # Load ABIs for each pool
        for pool in pool_configs:
            abi_file = pool.get('abi_file')
            pool['abi'] = self.config_loader.load_abi(abi_file)
        
        # Create event filters for all pools
        filters = self.create_event_filters(pool_configs)
        
        logger.info(f"Listening for events on {len(pool_configs)} pools")
        
        # Event loop
        while True:
            try:
                for pool_address, pool_data in filters.items():
                    pool_filters = pool_data['filters']
                    pool_name = pool_data['name']
                    
                    # Process events for each event type
                    for event_filter in pool_filters.values():
                        for event in event_filter.get_new_entries():
                            event_data = dict(event)
                            block_number = event_data['blockNumber']
                            block = self.web3_client.get_block(block_number)
                            
                            event_data['timestamp'] = block['timestamp']
                            event_data['transactionHash'] = event_data['transactionHash'].hex()

                            self.event_handler.handle_event(event_data, pool_address, pool_name)
                
                # Small delay to prevent excessive polling
                time.sleep(1)
            except Exception as e:
                logger.error(f"Error processing events: {e}")
                logger.error(traceback.format_exc())
                time.sleep(1) 