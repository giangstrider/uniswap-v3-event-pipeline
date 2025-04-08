import json
import logging
from typing import Dict, List, Any

logger = logging.getLogger(__name__)

class ConfigLoader:
    """Class for loading configuration and ABI files."""
    
    def __init__(self, config_file: str, abi_dir: str) -> None:
        """
        Initialize the ConfigLoader with required paths.
        
        Args:
            config_file (str): Path to the pool configuration JSON file
            abi_dir (str): Directory containing ABI JSON files
        """               
        self.config_file = config_file
        self.abi_dir = abi_dir
        
        # Load configuration during initialization
        with open(self.config_file, 'r') as file:
            self.config: Dict[str, Any] = json.load(file)
            
        if 'pools' not in self.config:
            logger.error(f"Missing 'pools' key in configuration file: {self.config_file}")
            raise KeyError(f"Missing 'pools' key in configuration file: {self.config_file}")
            
        logger.info(f"ConfigLoader initialized with config_file={config_file}, abi_dir={abi_dir}")
    
    def load_pool_config(self) -> List[Dict[str, Any]]:
        """
        Return the pool configuration
        """
        return self.config['pools']
    
    def load_abi(self, abi_file: str) -> List[Dict[str, Any]]:
        """
        Load ABI from JSON file
        """
        abi_path = f"{self.abi_dir}/{abi_file}"
        with open(abi_path, 'r') as file:
            return json.load(file)
