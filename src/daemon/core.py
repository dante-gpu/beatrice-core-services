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

    def _register_signal_handlers(self):
        """SIGTERM and SIGINT signal handlers."""
        loop = asyncio.get_event_loop()
        
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(
                sig,
                lambda s=sig: asyncio.create_task(self._signal_handler(s))
            )

    async def _signal_handler(self, sig: signal.Signals):
        """Catches shutdown signals and stops the daemon."""
        self.logger.info(f"Received shutdown signal {sig.name}")
        await self.stop()
        
    async def _run_service_checks(self):
        """Checks the health of all services."""
        for service_name, service in self.services.items():
            try:
                health_status = await service.check_health()
                if not health_status:
                    self.logger.warning(f"Service {service_name} health check failed")
            except Exception as e:
                self.logger.error(f"Error checking service {service_name}: {str(e)}")
                
    @property
    def uptime(self) -> Optional[float]:
        """Returns the uptime of the daemon in seconds."""
        if self._start_time is None:
            return None
        return (datetime.utcnow() - self._start_time).total_seconds()