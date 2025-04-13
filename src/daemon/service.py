import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Dict, Optional, Any
from enum import Enum
from datetime import datetime, timezone # Use timezone

class ServiceState(Enum):
    INIT = "initialized"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"
    RECOVERING = "recovering"

class ServiceHealth:
    def __init__(self):
        self.status: bool = False
        self.last_check: datetime = datetime.now(timezone.utc) # Use timezone aware
        self.error_count: int = 0
        self.last_error: Optional[str] = None
        self.metrics: Dict[str, Any] = {}
        self.recovery_attempts: int = 0
        self.last_recovery: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "last_check": self.last_check.isoformat(),
            "error_count": self.error_count,
            "last_error": self.last_error,
            "metrics": self.metrics,
            "recovery_attempts": self.recovery_attempts,
            "last_recovery": self.last_recovery.isoformat() if self.last_recovery else None
        }

class BaseService(ABC):
    def __init__(self, name: str, logger: Optional[logging.Logger] = None):
        self.name = name
        self.state = ServiceState.INIT
        self.health = ServiceHealth()
        self.logger = logger or logging.getLogger(name)
        self._start_time: Optional[datetime] = None
        self._is_running: bool = False 
        self._dependencies: Dict[str, 'BaseService'] = {}
        self._is_critical = False
        self._max_recovery_attempts: int = 3
        self._recovery_delay: float = 5.0  

    @abstractmethod
    async def start(self):
        self._is_running = True 
        self.state = ServiceState.STARTING
        pass

    @abstractmethod
    async def stop(self):
        self._is_running = False 
        self.state = ServiceState.STOPPING
        pass

    @abstractmethod
    async def check_health(self) -> ServiceHealth:
        pass

    async def add_dependency(self, service: 'BaseService'):
        if service.name in self._dependencies:
            self.logger.warning(f"Dependency {service.name} already exists")
            return
        self._dependencies[service.name] = service
        self.logger.info(f"Added dependency: {service.name}")

    async def remove_dependency(self, service_name: str):
        if service_name in self._dependencies:
            del self._dependencies[service_name]
            self.logger.info(f"Removed dependency: {service_name}")
        else:
            self.logger.warning(f"Dependency {service_name} not found")

    async def check_dependencies(self) -> bool:
        if not self._dependencies:
            return True
            
        failed_deps = []
        for dep_name, dep_service in self._dependencies.items():
            try:
                 health = await dep_service.check_health()
                 if not health.status:
                     failed_deps.append(dep_name)
                     self.logger.error(f"Dependency {dep_name} health check failed")
            except Exception as e:
                 self.logger.error(f"Error checking health of dependency {dep_name}: {e}")
                 failed_deps.append(f"{dep_name} (error)")

        if failed_deps:
            self.health.last_error = f"Failed dependencies: {', '.join(failed_deps)}"
            return False
            
        return True
    
    async def recover(self) -> bool:
        if self.health.recovery_attempts >= self._max_recovery_attempts:
             self.logger.error(f"Max recovery attempts ({self._max_recovery_attempts}) reached for service {self.name}. Giving up.")
             self.state = ServiceState.ERROR
             return False
             
        self.health.recovery_attempts += 1
        self.health.last_recovery = datetime.now(timezone.utc)
        self.logger.info(f"Attempting recovery for service {self.name} (Attempt {self.health.recovery_attempts}/{self._max_recovery_attempts})")
        
        try:
            self.state = ServiceState.RECOVERING
            await self.stop()
            await asyncio.sleep(self._recovery_delay)
            
            # Re-create and start the task (assuming start() is the main loop)
            # This logic might need adjustment depending on how daemon manages tasks
            self.logger.info(f"Restarting service task for {self.name}...")
            # The daemon should ideally handle task recreation upon failure detection
            # This basic recover might just try to call start again if it exited
            await self.start() # This might not work as expected if start() is long-running
            
            # Check health after attempting restart
            await asyncio.sleep(1) # Give it a moment
            health_check = await self.check_health()
            if health_check.status:
                self.state = ServiceState.RUNNING
                self.logger.info(f"Service {self.name} recovered successfully")
                self.health.error_count = 0 # Reset error count on successful recovery
                self.health.recovery_attempts = 0 # Reset attempts
                return True
            else:
                self.state = ServiceState.ERROR
                self.logger.error(f"Service {self.name} recovery failed. Health check status: {health_check.status}, Error: {health_check.last_error}")
                return False
                
        except Exception as e:
            self.state = ServiceState.ERROR
            self.logger.error(f"Recovery failed for service {self.name}: {str(e)}", exc_info=True)
            return False

    @property
    def uptime(self) -> Optional[float]:
        if self._start_time is None:
            return None
        return (datetime.now(timezone.utc) - self._start_time).total_seconds()

    @property
    def is_healthy(self) -> bool:
        return self.state == ServiceState.RUNNING and self.health.status

    @property
    def is_critical(self) -> bool:
        return self._is_critical

    def set_critical(self, value: bool = True):
        self._is_critical = value
        self.logger.info(f"Service {self.name} critical status set to {value}")
