import json
import os
import logging # Import logging
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__) # Setup logger for this module

class ConfigManager:
    def __init__(self):
        self.config_dir = Path.home() / ".dantegpu"
        self.config_file = self.config_dir / "config.json"
        self.config: Dict[str, Any] = {}
        self._load_config()
        
    def _load_config(self):
        try:
            if not self.config_dir.exists():
                logger.info(f"Creating config directory: {self.config_dir}")
                self.config_dir.mkdir(parents=True, exist_ok=True) # Added exist_ok
                
            if self.config_file.exists():
                logger.info(f"Loading config from: {self.config_file}")
                with open(self.config_file, "r") as f:
                    self.config = json.load(f)
            else:
                logger.info("Config file not found, creating default config.")
                self._create_default_config()
                
        except json.JSONDecodeError as e:
             logger.error(f"Error decoding config file {self.config_file}: {e}. Creating default config.")
             self._create_default_config()
        except Exception as e:
            logger.error(f"Error loading config: {e}. Creating default config.")
            self._create_default_config()
            
    def _create_default_config(self):
        self.config = {
            "log_level": "INFO", 
            "monitoring_interval": 5, # Default to 5 seconds
            "autostart_minimized": False,
            "marketplace_url": "https://api.example.dantegpu.market", # Placeholder URL
            "gpu_settings": {
                "power_limit": 100,
                "memory_offset": 0,
                "core_offset": 0
            }
        }
        logger.info("Saving default configuration.")
        self._save_config()
        
    def _save_config(self):
        try:
            with open(self.config_file, "w") as f:
                json.dump(self.config, f, indent=4)
            logger.debug(f"Configuration saved to {self.config_file}")
        except Exception as e:
            logger.error(f"Error saving config to {self.config_file}: {e}")
            
    def get(self, key: str, default: Any = None) -> Any:
        return self.config.get(key, default)
        
    def set(self, key: str, value: Any):
        self.config[key] = value
        self._save_config()
