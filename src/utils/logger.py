import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler
import coloredlogs

# Import ConfigManager to read log level (adjust path if necessary)
from .config import ConfigManager

def setup_logger(name: str = None) -> logging.Logger:
    """Setup logging system with colored console output and file logging."""
    
    # Read log level from config
    config = ConfigManager()
    log_level_str = config.get("log_level", "INFO").upper()
    log_level = getattr(logging, log_level_str, logging.INFO)

    # Create main logger
    logger = logging.getLogger(name or "DanteGPU")
    logger.setLevel(log_level) # Set level for the logger itself
    logger.propagate = False # Prevent root logger from handling messages

    # Define format for both handlers
    log_format = '%(asctime)s - %(name)s:%(lineno)d - %(levelname)s - %(message)s'
    formatter = logging.Formatter(log_format)

    # Setup colored console logging
    # Remove existing handlers added by coloredlogs if any (to avoid duplicates)
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
        
    coloredlogs.install(
        level=log_level, # Set level for the coloredlogs handler
        logger=logger,
        fmt=log_format,
        level_styles=coloredlogs.DEFAULT_LEVEL_STYLES,
        field_styles=coloredlogs.DEFAULT_FIELD_STYLES
    )

    # Add file handler (keeps logging to file as before)
    log_dir = Path.home() / ".dantegpu" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    
    file_handler = RotatingFileHandler(
        log_dir / "dantegpu.log",
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    return logger
