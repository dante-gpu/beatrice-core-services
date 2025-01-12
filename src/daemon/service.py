import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Dict, Optional, Any
from enum import Enum
from datetime import datetime

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
        self.last_check: datetime = datetime.utcnow()
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
    """
    abstract methods are implemented in the subclasses. -@virjilakrum
    """
    def __init__(self, name: str, logger: Optional[logging.Logger] = None):
        self.name = name
        self.state = ServiceState.INIT
        self.health = ServiceHealth()
        self.logger = logger or logging.getLogger(name)
        self._start_time: Optional[datetime] = None
        self._dependencies: Dict[str, 'BaseService'] = {}
        self._is_critical = False
        self._max_recovery_attempts: int = 3
        self._recovery_delay: float = 5.0  # seconds

    @abstractmethod
    async def start(self) -> bool:
        """service is started"""
        pass

    @abstractmethod
    async def stop(self) -> bool:
        """service is stopped"""
        pass

    @abstractmethod
    async def check_health(self) -> ServiceHealth:
        """service health is checked"""
        pass

    async def add_dependency(self, service: 'BaseService'):
        """service dependency is added"""
        if service.name in self._dependencies:
            self.logger.warning(f"Dependency {service.name} already exists")
            return
        self._dependencies[service.name] = service
        self.logger.info(f"Added dependency: {service.name}")

    async def remove_dependency(self, service_name: str):
        """service dependency is removed"""
        if service_name in self._dependencies:
            del self._dependencies[service_name]
            self.logger.info(f"Removed dependency: {service_name}")
        else:
            self.logger.warning(f"Dependency {service_name} not found")

    async def check_dependencies(self) -> bool:
        """all dependencies are checked"""
        if not self._dependencies:
            return True
            
        failed_deps = []
        for dep_name, dep_service in self._dependencies.items():
            health = await dep_service.check_health()
            if not health.status:
                failed_deps.append(dep_name)
                self.logger.error(f"Dependency {dep_name} health check failed")
        
        if failed_deps:
            self.health.last_error = f"Failed dependencies: {', '.join(failed_deps)}"
            return False
            
        return True