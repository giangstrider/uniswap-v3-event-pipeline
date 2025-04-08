import logging
from typing import Optional, Any, Dict, List
from web3 import Web3
from web3.contract import Contract
from web3.types import BlockData

logger = logging.getLogger(__name__)

class Web3Client:
    """Class for interacting with Ethereum via Web3."""
    
    def __init__(self, rpc_url: str) -> None:
        """
        Initialize the Web3 client.
        
        Args:
            rpc_url (str): URL of the Ethereum RPC endpoint
        """
        self.rpc_url = rpc_url
        self.web3 = self.connect()
    
    def connect(self) -> Web3:
        """Connect to Ethereum node using Web3."""
        if not self.rpc_url:
            raise ValueError("RPC URL is not provided")
        
        logger.info(f"Connecting to Ethereum node at {self.rpc_url}")
        return Web3(Web3.HTTPProvider(self.rpc_url))
    
    def get_contract(self, address: str, abi: List[Dict[str, Any]]) -> Contract:
        """Create a contract instance."""
        return self.web3.eth.contract(address=Web3.to_checksum_address(address), abi=abi)
    
    def get_block(self, block_number: int) -> BlockData:
        """Get block information."""
        return self.web3.eth.get_block(block_number) 