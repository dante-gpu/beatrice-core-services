import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler
import coloredlogs

try:
    from .config import ConfigManager
except ImportError:
    from utils.config import ConfigManager # Fallback

def setup_logger(name: str = None) -> logging.Logger:
    config = ConfigManager()
    log_level_str = config.get("log_level", "INFO").upper()
    log_level = getattr(logging, log_level_str, logging.INFO)

    logger = logging.getLogger(name or "DanteGPU")
    
    # Check if handlers already exist to prevent duplication
    if logger.hasHandlers():
        logger.handlers.clear()
        
    logger.setLevel(log_level) 
    logger.propagate = False 

    log_format = '%(asctime)s - %(name)s:%(lineno)d - %(levelname)s - %(message)s'
    
    # Use coloredlogs for console output
    coloredlogs.install(
        level=log_level, 
        logger=logger,
        fmt=log_format,
        level_styles=coloredlogs.DEFAULT_LEVEL_STYLES,
        field_styles=coloredlogs.DEFAULT_FIELD_STYLES
    )

    # Setup file logging
    try:
        log_dir = Path.home() / ".dantegpu" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        
        file_handler = RotatingFileHandler(
            log_dir / "dantegpu.log",
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5,
            encoding='utf-8' # Specify encoding
        )
        file_formatter = logging.Formatter(log_format) # Use the same format
        file_handler.setFormatter(file_formatter)
        file_handler.setLevel(log_level) # Set level for file handler too
        logger.addHandler(file_handler)
    except Exception as e:
         # Log error using the console handler already set up by coloredlogs
         logger.error(f"Failed to set up file logging: {e}", exc_info=True)

    return logger
