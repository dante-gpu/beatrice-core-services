import asyncio
import logging
import signal
import sys
import asyncio 
import queue 
from typing import Dict, Optional, List, TYPE_CHECKING 
from datetime import datetime, timezone 

if TYPE_CHECKING:
    from .service import BaseService

class BeatriceDaemon:
    def __init__(self):
        self._is_running: bool = False
        self._start_time: Optional[datetime] = None
        self.services: Dict[str, 'BaseService'] = {} 
        self._service_tasks: List[asyncio.Task] = [] 
        self.logger = self._setup_logging()
        self.update_queue = queue.Queue() 

    def _setup_logging(self) -> logging.Logger:
        logger = logging.getLogger("BeatriceDaemon")
        # Prevent duplicate handlers if logger already exists
        if logger.hasHandlers():
             logger.handlers.clear()
             
        logger.setLevel(logging.INFO) 
        
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.propagate = False # Avoid propagating to root logger if setup elsewhere
        
        return logger

    def register_service(self, service: 'BaseService'):
        if service.name in self.services:
            self.logger.warning(f"Service '{service.name}' already registered. Skipping.")
            return
        self.services[service.name] = service
        if hasattr(service, 'set_update_queue'):
             service.set_update_queue(self.update_queue)
        self.logger.info(f"Service '{service.name}' registered.")

    async def _start_services(self):
        self.logger.info("Starting registered services...")
        for service_name, service in self.services.items():
            try:
                task = asyncio.create_task(service.start(), name=f"Service_{service_name}")
                self._service_tasks.append(task)
                self.logger.info(f"Service '{service_name}' task created.")
            except Exception as e:
                self.logger.error(f"Failed to create task for service '{service_name}': {e}")

    async def start(self):
        if self._is_running:
            self.logger.warning("Daemon already running")
            return
            
        try:
            self._start_time = datetime.now(timezone.utc) # Use timezone aware
            self._is_running = True
            self.logger.info("Beatrice Daemon starting...")
            
            await self._start_services()
            
            self._register_signal_handlers()
            
            while self._is_running:
                all_tasks_done = True
                for task in self._service_tasks[:]: 
                     if task.done():
                         try:
                             task.result() 
                         except asyncio.CancelledError:
                              self.logger.info(f"Service task {task.get_name()} cancelled.")
                         except Exception as e:
                              self.logger.error(f"Service task {task.get_name()} failed: {e}", exc_info=True)
                         self._service_tasks.remove(task)
                     else:
                          all_tasks_done = False 
                
                if all_tasks_done and self._is_running and self.services:
                     self.logger.warning("All service tasks finished unexpectedly. Stopping daemon.")
                     await self.stop() 
                     break 
                elif not self.services and self._is_running:
                     self.logger.info("No services registered. Daemon running idle.")
                     await asyncio.sleep(5) 
                     continue 

                await asyncio.sleep(5)  
        except Exception as e:
            self.logger.error(f"Fatal error in daemon: {str(e)}")
            await self.stop()
            raise

    async def stop(self):
        if not self._is_running:
            return

        self.logger.info("Beatrice Daemon stopping...")
        self._is_running = False 

        self.logger.info(f"Cancelling {len(self._service_tasks)} service tasks...")
        for task in self._service_tasks:
            if not task.done():
                task.cancel()
        
        if self._service_tasks:
             gathered_tasks = asyncio.gather(*self._service_tasks, return_exceptions=True)
             try:
                  results = await asyncio.wait_for(gathered_tasks, timeout=5.0)
                  self.logger.debug(f"Service task cancellation results: {results}")
                  self.logger.info("All service tasks cancelled or finished.")
             except asyncio.TimeoutError:
                  self.logger.warning("Timeout waiting for service tasks to cancel.")
                  pending = [t for t in self._service_tasks if not t.done()]
                  if pending:
                       self.logger.warning(f"Pending tasks after timeout: {[t.get_name() for t in pending]}")
             except Exception as e:
                  self.logger.error(f"Error gathering cancelled service tasks: {e}")
        self._service_tasks = [] 

        self.logger.info("Calling stop() on registered services...")
        for service_name, service in self.services.items():
            try:
                stop_result = service.stop()
                if asyncio.iscoroutine(stop_result):
                    await stop_result
                self.logger.info(f"Service '{service_name}' stop method called.")
            except Exception as e:
                self.logger.error(f"Error calling stop on service '{service_name}': {str(e)}")
                
        self.logger.info("Beatrice Daemon stopped.")

    def _register_signal_handlers(self):
        try:
             loop = asyncio.get_running_loop()
        except RuntimeError:
             self.logger.error("No running event loop to register signal handlers.")
             return

        for sig in (signal.SIGTERM, signal.SIGINT):
            try:
                 loop.add_signal_handler(
                     sig,
                     lambda s=sig: asyncio.create_task(self._signal_handler(s))
                 )
            except NotImplementedError:
                 self.logger.warning(f"Signal handling for {sig.name} not supported on this platform (e.g., Windows).")
            except Exception as e:
                 self.logger.error(f"Failed to register signal handler for {sig.name}: {e}")


    async def _signal_handler(self, sig: signal.Signals):
        self.logger.info(f"Received shutdown signal {sig.name}. Initiating stop...")
        if self._is_running: 
             try:
                  await self.stop()
             except Exception as e:
                  self.logger.critical(f"Error during daemon stop initiated by signal {sig.name}: {e}", exc_info=True)
        else:
             self.logger.info("Daemon already stopping/stopped.")
        
    async def _run_service_checks(self):
        # This method seems less useful now that services run their own loops
        # Kept for potential future use or can be removed.
        pass
        # for service_name, service in self.services.items():
        #     try:
        #         health_status = await service.check_health()
        #         if not health_status:
        #             self.logger.warning(f"Service {service_name} health check failed")
        #     except Exception as e:
        #         self.logger.error(f"Error checking service {service_name}: {str(e)}")
                
    @property
    def uptime(self) -> Optional[float]:
        if self._start_time is None:
            return None
        return (datetime.now(timezone.utc) - self._start_time).total_seconds()
