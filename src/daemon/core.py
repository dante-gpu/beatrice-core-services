import asyncio
import logging
import signal
import sys
from typing import Dict, Optional
from datetime import datetime

class BeatriceDaemon:
    """
    Beatrice daemon services. All services are managed here.
    """

    def __init__(self):
        self._is_running: bool = False
        self._start_time: Optional[datetime] = None
        self.services: Dict = {}
        self.logger = self._setup_logging()

         def _setup_logging(self) -> logging.Logger:
        """Creates basic logging configuration."""
        logger = logging.getLogger("BeatriceDaemon")
        logger.setLevel(logging.INFO)
        
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        
        return logger

 async def start(self):
        """Starts the daemon and initializes required services."""
        if self._is_running:
            self.logger.warning("Daemon already running")
            return
            
        try:
            self._start_time = datetime.utcnow()
            self._is_running = True
            self.logger.info("Beatrice Daemon starting...")


self._register_signal_handlers()
 # Main loop
  while self._is_running:
                await self._run_service_checks()
                await asyncio.sleep(1)  # 1 second delay for main loop


              except Exception as e:
            self.logger.error(f"Fatal error in daemon: {str(e)}")
            await self.stop()
            raise
            
    async def stop(self):
        """Stops the daemon and cleans up resources."""
        if not self._is_running:
            return

            self.logger.info("Beatrice Daemon stopping...")
        self._is_running = False

         for service_name, service in self.services.items():
            try:
                await service.stop()
                self.logger.info(f"Service {service_name} stopped")
            except Exception as e:
                self.logger.error(f"Error stopping service {service_name}: {str(e)}")
                
        self.logger.info("Beatrice Daemon stopped")