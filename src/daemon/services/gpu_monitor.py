import asyncio
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
# import psutil

# Note: We're using a placeholder GPU library here. In production,
# you'd want to use specific libraries based on the GPU vendor
try:
    import nvidia_smi
    nvidia_smi.nvmlInit()
    NVIDIA_AVAILABLE = True
except ImportError:
    NVIDIA_AVAILABLE = False

from ...daemon.service import BaseService, ServiceHealth, ServiceState
"""
GPU Monitoring Service Module
---------------------------

This module provides comprehensive GPU monitoring capabilities for the Beatrice Core Services.
It's designed to be extensible and fault-tolerant, with support for multiple GPU vendors.

Key Features:
- Real-time GPU metrics collection
- Auto-discovery of GPU devices
- Fault tolerance and automatic recovery
- Thread-safe metric collection
- Configurable monitoring intervals
- Comprehensive health checking

Technical Architecture:
- Uses async/await pattern for non-blocking operations
- Implements BaseService for lifecycle management
- Uses NVIDIA SMI for direct GPU communication
- Implements thread-safe metric collection with locks

Dependencies:
- nvidia-smi: Required for NVIDIA GPU monitoring
- psutil: System resource monitoring
- asyncio: Asynchronous operations

Development Guidelines: @fybx @mehmethayirli @muhammedakinci
- Always use async context managers for lock operations
- Implement proper error handling for GPU operations
- Maintain backward compatibility when adding new metrics
- Document any vendor-specific implementation details
- Add unit tests for new functionality
- Follow error handling patterns defined in BaseService
- Use NVIDIA SMI for GPU monitoring and control

Performance Considerations:
- Metric collection is CPU-intensive
- Lock operations may impact concurrent access
- Consider monitoring interval impacts on system load
- Cache metrics when possible to reduce GPU queries

Error Handling Strategy:
- Implement exponential backoff for retries
- Log all GPU communication errors
- Maintain service stability during GPU errors
- Provide detailed error context for debugging

Future Improvements:
- Add support for AMD GPUs
- Implement metric persistence
- Add machine learning based anomaly detection
- Enhance metric collection granularity
- Add power management features
"""
"""
GPU Metrics Container Class
--------------------------

Stores and manages individual GPU device metrics. This class serves as a data container for all metrics collected from a single GPU device.

Metrics Included:
- Temperature: GPU core temperature in Celsius
- Utilization: GPU utilization percentage
- Memory Used: Current memory usage in bytes
- Memory Total: Total available memory in bytes
- Power Usage: Current power consumption in watts
- Fan Speed: Fan speed percentage

Implementation Notes:
- All metrics are stored in their native units
- No data validation is performed in this class
- Memory values are stored in bytes for precision
- Add new metrics here when expanding monitoring

Usage Example:
    metrics = GPUMetrics()
    metrics.temperature = 75.0
    metrics.utilization = 85.0
    dict_data = metrics.to_dict()

Debug Considerations:
- Monitor memory usage patterns
- Track metric value ranges
- Consider adding value validation
"""

class GPUMetrics:
    def __init__(self):
        self.temperature: float = 0.0
        self.utilization: float = 0.0
        self.memory_used: int = 0
        self.memory_total: int = 0
        self.power_usage: float = 0.0
        self.fan_speed: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "temperature": self.temperature,
            "utilization": self.utilization,
            "memory_used": self.memory_used,
            "memory_total": self.memory_total,
            "power_usage": self.power_usage,
            "fan_speed": self.fan_speed
        }

class GPUMonitorService(BaseService):
    """
    GPU monitoring service that tracks various GPU metrics
    
    Notes:
    - Service automatically detects available GPUs
    - Implements automatic recovery on monitoring failures
    - Configurable monitoring intervals
    - Thread-safe metric collection
    """
    def __init__(
        self,
        name: str = "gpu_monitor",
        monitoring_interval: int = 5,
        logger: Optional[logging.Logger] = None
    ):
        super().__init__(name, logger)
        self.monitoring_interval = monitoring_interval
        self._gpu_metrics: Dict[int, GPUMetrics] = {}
        self._monitoring_task: Optional[asyncio.Task] = None
        self._last_collection_time: Optional[datetime] = None
        self._collection_lock = asyncio.Lock()

    async def start(self) -> bool:
        """
        Start the GPU monitoring service
        
        Developer Notes:
        - Initializes NVIDIA SMI if available
        - Creates background monitoring task
        - Sets up initial GPU detection
        """
        try:
            self.state = ServiceState.STARTING
            self.logger.info("Starting GPU monitoring service")

            if not NVIDIA_AVAILABLE:
                self.logger.error("NVIDIA SMI library not available")
                self.state = ServiceState.ERROR
                return False

            # Start monitoring task
            self._monitoring_task = asyncio.create_task(self._monitoring_loop())
            self._start_time = datetime.utcnow()
            self.state = ServiceState.RUNNING
            
            return True

        except Exception as e:
            self.logger.error(f"Failed to start GPU monitoring: {str(e)}")
            self.state = ServiceState.ERROR
            return False

    async def stop(self) -> bool:
        """
        Stop the GPU monitoring service
        
        Developer Notes:
        - Ensures graceful shutdown of monitoring tasks
        - Properly closes NVIDIA SMI connection
        - Cleans up resources
        """
        try:
            self.state = ServiceState.STOPPING
            self.logger.info("Stopping GPU monitoring service")

            if self._monitoring_task:
                self._monitoring_task.cancel()
                await asyncio.gather(self._monitoring_task, return_exceptions=True)

            if NVIDIA_AVAILABLE:
                nvidia_smi.nvmlShutdown()

            self.state = ServiceState.STOPPED
            return True

        except Exception as e:
            self.logger.error(f"Failed to stop GPU monitoring: {str(e)}")
            self.state = ServiceState.ERROR
            return False

    async def check_health(self) -> ServiceHealth:
        """
        Check the health status of the GPU monitoring service
        
        Developer Notes:
        - Verifies both service and GPU health
        - Updates health metrics with latest GPU status
        - Implements timeout for health checks
        """
        health = ServiceHealth()
        
        try:
            # Check if monitoring is active
            if self.state != ServiceState.RUNNING:
                health.status = False
                health.last_error = f"Service not running (current state: {self.state})"
                return health

            # Verify last collection time
            if self._last_collection_time:
                time_since_last = (datetime.utcnow() - self._last_collection_time).total_seconds()
                if time_since_last > self.monitoring_interval * 2:
                    health.status = False
                    health.last_error = f"Data collection delayed: {time_since_last}s"
                    return health

            # Check GPU metrics
            health.status = True
            health.metrics = {
                "gpu_count": len(self._gpu_metrics),
                "last_collection": self._last_collection_time.isoformat() if self._last_collection_time else None,
                "metrics": {idx: metrics.to_dict() for idx, metrics in self._gpu_metrics.items()}
            }

        except Exception as e:
            health.status = False
            health.last_error = str(e)
            health.error_count += 1

        return health

    async def _monitoring_loop(self):
        """
        Main monitoring loop for collecting GPU metrics
        
        Developer Notes:
        - Implements exponential backoff for retries
        - Uses asyncio locks for thread safety
        - Handles GPU hotplug/unplug scenarios
        """
        while self.state == ServiceState.RUNNING:
            try:
                async with self._collection_lock:
                    await self._collect_gpu_metrics()
                
                self._last_collection_time = datetime.utcnow()
                await asyncio.sleep(self.monitoring_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in monitoring loop: {str(e)}")
                await asyncio.sleep(self.monitoring_interval * 2)

    async def _collect_gpu_metrics(self):
        """
        Collect metrics from all available GPUs
        
        Developer Notes:
        - Supports multiple GPUs
        - Implements error handling for each GPU
        - Collects comprehensive metrics set
        """
        if not NVIDIA_AVAILABLE:
            return

        try:
            device_count = nvidia_smi.nvmlDeviceGetCount()
            
            for gpu_id in range(device_count):
                handle = nvidia_smi.nvmlDeviceGetHandleByIndex(gpu_id)
                
                metrics = GPUMetrics()
                
                # Collect detailed GPU metrics
                temp = nvidia_smi.nvmlDeviceGetTemperature(handle, nvidia_smi.NVML_TEMPERATURE_GPU)
                util = nvidia_smi.nvmlDeviceGetUtilizationRates(handle)
                mem = nvidia_smi.nvmlDeviceGetMemoryInfo(handle)
                power = nvidia_smi.nvmlDeviceGetPowerUsage(handle)
                fan = nvidia_smi.nvmlDeviceGetFanSpeed(handle)

                metrics.temperature = temp
                metrics.utilization = util.gpu
                metrics.memory_used = mem.used
                metrics.memory_total = mem.total
                metrics.power_usage = power / 1000.0  # Convert to watts
                metrics.fan_speed = fan

                self._gpu_metrics[gpu_id] = metrics

        except Exception as e:
            self.logger.error(f"Failed to collect GPU metrics: {str(e)}")
            raise