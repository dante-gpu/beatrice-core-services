import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

class ConfigManager:
    def __init__(self):
        self.config_dir = Path.home() / ".dantegpu"
        self.config_file = self.config_dir / "config.json"
        self.config: Dict[str, Any] = {}
        self._load_config()
        
    def _load_config(self):
        """Load configuration file"""
        try:
            if not self.config_dir.exists():
                self.config_dir.mkdir(parents=True)
                
            if self.config_file.exists():
                with open(self.config_file, "r") as f:
                    self.config = json.load(f)
            else:
                self._create_default_config()
                
        except Exception as e:
            print(f"Error loading config: {e}")
            self._create_default_config()
            
    def _create_default_config(self):
        """Create default configuration"""
        self.config = {
            "autostart_minimized": False,
            "monitoring_interval": 1,
            "marketplace_url": "https://api.dantegpu.market", # TODO: Change to actual marketplace url this is mock url :////
            "gpu_settings": {
                "power_limit": 100,
                "memory_offset": 0,
                "core_offset": 0
            }
        }
        self._save_config()
        
    def _save_config(self):
        """Save configuration to file"""
        try:
            with open(self.config_file, "w") as f:
                json.dump(self.config, f, indent=4)
        except Exception as e:
            print(f"Error saving config: {e}")
            
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value"""
        return self.config.get(key, default)
        
    def set(self, key: str, value: Any):
        """Set configuration value"""
        self.config[key] = value
        self._save_config() 