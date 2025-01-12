import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler

def setup_logger(name: str = None) -> logging.Logger:
    """Setup logging system"""
    # Create main logger
    logger = logging.getLogger(name or "DanteGPU")
    logger.setLevel(logging.INFO)
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Add console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # Add file handler
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