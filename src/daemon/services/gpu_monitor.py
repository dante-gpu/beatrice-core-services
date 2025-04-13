import asyncio
import logging
import platform
import subprocess
import json
import queue 
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone 
import psutil

IS_MACOS = platform.system() == "Darwin"
NVIDIA_AVAILABLE = False
if not IS_MACOS:
    try:
        import nvidia_smi
        NVIDIA_AVAILABLE = True
    except ImportError:
        logging.getLogger(__name__).warning("nvidia-ml-py3 library not found. NVIDIA GPU monitoring disabled.")
        NVIDIA_AVAILABLE = False
    except Exception as e:
        logging.getLogger(__name__).error(f"Error importing or initializing nvidia-ml-py3: {e}")
        NVIDIA_AVAILABLE = False

try:
    from ..service import BaseService, ServiceHealth, ServiceState 
    from ...utils.helpers import format_bytes 
except ImportError:
    from daemon.service import BaseService, ServiceHealth, ServiceState
    from utils.helpers import format_bytes

class GPUMonitorService(BaseService):
    def __init__(
        self,
        name: str = "gpu_monitor",
        monitoring_interval: int = 5, 
        logger: Optional[logging.Logger] = None
    ):
        super().__init__(name, logger)
        self.monitoring_interval = monitoring_interval
        self._last_collection_time: Optional[datetime] = None
        self._collection_lock = asyncio.Lock() 
        self.update_queue: Optional[queue.Queue] = None 
        
        self.nvidia_initialized = False
        if NVIDIA_AVAILABLE:
             self._initialize_nvidia_smi()

    def set_update_queue(self, queue: queue.Queue): 
        self.update_queue = queue
        self.logger.info("Update queue set for GPUMonitorService.")

    def _initialize_nvidia_smi(self):
        if not NVIDIA_AVAILABLE: return
        try:
            nvidia_smi.nvmlInit()
            self.nvidia_initialized = True
            self.logger.info("NVIDIA SMI initialized successfully by GPUMonitorService.")
        except Exception as e:
            self.nvidia_initialized = False
            if hasattr(e, 'value') and isinstance(e.value, str):
                 self.logger.error(f"GPUMonitorService failed to initialize NVIDIA SMI: {e.value}")
            else:
                 self.logger.error(f"GPUMonitorService failed to initialize NVIDIA SMI: {e}")

    def _run_command(self, cmd_list):
        try:
            result = subprocess.run(cmd_list, capture_output=True, text=True, check=True, timeout=5) 
            return result.stdout.strip()
        except subprocess.TimeoutExpired:
             self.logger.warning(f"Timeout running command: {' '.join(cmd_list)}")
             return None
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Error running command '{' '.join(cmd_list)}': {e.stderr or e}")
            return None
        except FileNotFoundError:
            self.logger.error(f"Error: Command '{cmd_list[0]}' not found.")
            return None
        except Exception as e:
            self.logger.error(f"Unexpected error running command '{' '.join(cmd_list)}': {e}")
            return None

    def _get_macos_gpu_info(self) -> List[Dict[str, Any]]:
        gpus = []
        try:
            cmd_list = ['system_profiler', 'SPDisplaysDataType', '-json']
            output = self._run_command(cmd_list)
            if not output: return [] 

            data = json.loads(output)
            display_info = data.get('SPDisplaysDataType', [])
            if not display_info: return [] 

            cpu_percent = psutil.cpu_percent(interval=None) 
            mem_info = psutil.virtual_memory()

            for idx, gpu_data in enumerate(display_info):
                name = gpu_data.get("_name") if IS_MACOS else gpu_data.get("sppci_model") # Use IS_MACOS flag
                if not name: name = gpu_data.get("sppci_model", "Unknown GPU")

                gpu_stats = {
                    "id": idx, "model": name,
                    "vendor": gpu_data.get("spdisplays_vendor", "Unknown").split('(')[0].strip(),
                    "vram": gpu_data.get("spdisplays_vram", "N/A"),
                    "device_id": gpu_data.get("spdisplays_device_id", gpu_data.get("sppci_device_id", "N/A")),
                    "vendor_id": gpu_data.get("spdisplays_vendor_id", gpu_data.get("sppci_vendor_id", "N/A")),
                    "bus": gpu_data.get("spdisplays_pcislot", gpu_data.get("sppci_bus", "N/A")),
                    "metal_family": gpu_data.get("spdisplays_metal_family", "N/A"),
                    "temperature": None, "utilization": cpu_percent, 
                    "memory_used": mem_info.used, "memory_total": mem_info.total, 
                    "power_usage": None, "fan_speed": None,
                }
                gpus.append(gpu_stats)
        except json.JSONDecodeError as e:
             self.logger.error(f"Error parsing system_profiler JSON output: {e}")
        except Exception as e:
            self.logger.error(f"Error getting macOS GPU/System info: {e}", exc_info=True)
        
        if not gpus:
             try:
                  cpu_percent = psutil.cpu_percent(interval=None)
                  mem_info = psutil.virtual_memory()
                  gpus.append({
                      "id": 0, "model": "System Stats", "vendor": "N/A", "vram": "N/A", 
                      "device_id": "N/A", "vendor_id": "N/A", "bus": "N/A", "metal_family": "N/A",
                      "temperature": None, "utilization": cpu_percent, 
                      "memory_used": mem_info.used, "memory_total": mem_info.total, 
                      "power_usage": None, "fan_speed": None,
                  })
             except Exception as ps_e:
                  self.logger.error(f"Failed to get even basic system stats: {ps_e}")

        return gpus

    def _get_nvidia_gpu_info(self) -> List[Dict[str, Any]]:
        gpus = []
        if not self.nvidia_initialized: return gpus
        try:
            device_count = nvidia_smi.nvmlDeviceGetCount()
            for i in range(device_count):
                handle = nvidia_smi.nvmlDeviceGetHandleByIndex(i)
                model_name = nvidia_smi.nvmlDeviceGetName(handle)
                temp = nvidia_smi.nvmlDeviceGetTemperature(handle, nvidia_smi.NVML_TEMPERATURE_GPU)
                util = nvidia_smi.nvmlDeviceGetUtilizationRates(handle)
                mem = nvidia_smi.nvmlDeviceGetMemoryInfo(handle)
                power, fan = None, None
                try: power = nvidia_smi.nvmlDeviceGetPowerUsage(handle) / 1000.0
                except nvidia_smi.NVMLError_NotSupported: pass
                except Exception as e_p: self.logger.debug(f"Power query failed GPU {i}: {e_p}")
                try: fan = nvidia_smi.nvmlDeviceGetFanSpeed(handle)
                except nvidia_smi.NVMLError_NotSupported: pass
                except Exception as e_f: self.logger.debug(f"Fan query failed GPU {i}: {e_f}")

                vendor = "NVIDIA" 
                vram_str = format_bytes(mem.total) 
                try: device_id = nvidia_smi.nvmlDeviceGetPciInfo(handle).pciDeviceId
                except Exception: device_id = "N/A"
                try: vendor_id = nvidia_smi.nvmlDeviceGetPciInfo(handle).pciVendorId
                except Exception: vendor_id = "N/A"
                try: bus = nvidia_smi.nvmlDeviceGetPciInfo(handle).busId 
                except Exception: bus = "N/A"
                
                gpu_stats = {
                    "id": i, "model": model_name, "vendor": vendor, "vram": vram_str,
                    "device_id": hex(device_id) if isinstance(device_id, int) else device_id, 
                    "vendor_id": hex(vendor_id) if isinstance(vendor_id, int) else vendor_id, 
                    "bus": bus, "metal_family": "N/A", 
                    "temperature": temp, "utilization": util.gpu,
                    "memory_used": mem.used, "memory_total": mem.total,
                    "power_usage": power, "fan_speed": fan
                }
                gpus.append(gpu_stats)
        except nvidia_smi.NVMLError as e:
             self.logger.error(f"NVIDIA SMI error getting stats: {e}")
        except Exception as e:
            self.logger.error(f"Unexpected error getting NVIDIA stats: {e}", exc_info=True)
        return gpus

    async def _collect_and_send_stats(self):
        async with self._collection_lock: 
            stats_data = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "active_gpus": 0,
                "total_earnings": 0, 
                "gpus": []
            }
            
            if IS_MACOS:
                gpu_list = self._get_macos_gpu_info()
                stats_data["gpus"] = gpu_list
                stats_data["active_gpus"] = len(gpu_list) if any(g.get("model") != "System Stats" for g in gpu_list) else 0
            elif NVIDIA_AVAILABLE and self.nvidia_initialized:
                gpu_list = self._get_nvidia_gpu_info()
                stats_data["gpus"] = gpu_list
                stats_data["active_gpus"] = len(gpu_list)
            else:
                self.logger.warning("No compatible GPU monitoring available for stat collection.")
                pass 

            self._last_collection_time = datetime.now(timezone.utc)
            
            if self.update_queue:
                try:
                    self.update_queue.put_nowait(stats_data) 
                except queue.Full: 
                     self.logger.warning("Update queue is full. Discarding latest stats.")
                except Exception as qe:
                     self.logger.error(f"Error putting stats into queue: {qe}")
            else:
                self.logger.warning("Update queue not set. Cannot send stats to GUI.")

    async def start(self) -> bool:
        if self.state == ServiceState.RUNNING:
            self.logger.warning(f"Service {self.name} already running.")
            return True
            
        await super().start() 
        
        self.logger.info(f"Starting monitoring loop for {self.name}")
        self._start_time = datetime.now(timezone.utc) 

        try:
            await self._collect_and_send_stats() 
            
            self.state = ServiceState.RUNNING 

            while self._is_running: 
                try:
                    await asyncio.sleep(self.monitoring_interval)
                    if not self._is_running: 
                        self.logger.info(f"Stop requested during sleep for {self.name}. Exiting loop.")
                        break 
                    await self._collect_and_send_stats()
                except asyncio.CancelledError:
                     self.logger.info(f"Monitoring loop cancelled for {self.name}.")
                     break 
                except Exception as loop_e:
                     self.logger.error(f"Error during monitoring interval for {self.name}: {loop_e}", exc_info=True)
                     if not self._is_running: break 
                     await asyncio.sleep(self.monitoring_interval * 2) 

            self.logger.info(f"Service {self.name} monitoring loop finished.")

        except asyncio.CancelledError:
            self.state = ServiceState.STOPPED
            self.logger.info(f"Service {self.name} monitoring task cancelled.")
            return True 
        except Exception as e:
            self.logger.error(f"Fatal error in service {self.name} monitoring loop: {e}", exc_info=True)
            self.state = ServiceState.ERROR
            return False 
        finally:
             await self.stop() 


    async def stop(self) -> bool:
        if self.state == ServiceState.STOPPED or self.state == ServiceState.STOPPING:
             return True 

        await super().stop() 
        
        self.logger.info(f"Performing cleanup for {self.name}")
        
        if self.nvidia_initialized:
            try:
                nvidia_smi.nvmlShutdown()
                self.nvidia_initialized = False
                self.logger.info("NVIDIA SMI shutdown complete by GPUMonitorService.")
            except Exception as e:
                self.logger.error(f"Error during NVIDIA SMI shutdown in GPUMonitorService: {e}")
                
        self.state = ServiceState.STOPPED
        self.logger.info(f"Service {self.name} stopped.")
        return True

    async def check_health(self) -> ServiceHealth:
        health = ServiceHealth()
        health.status = self.state == ServiceState.RUNNING
        health.last_check = datetime.now(timezone.utc)
        
        if not health.status:
            health.last_error = f"Service not in RUNNING state (current: {self.state})"
        elif self._last_collection_time:
            time_since_last = (datetime.now(timezone.utc) - self._last_collection_time).total_seconds()
            if time_since_last > self.monitoring_interval * 3: 
                health.status = False
                health.last_error = f"Data collection seems stalled (last update: {time_since_last:.1f}s ago)"
                self.logger.warning(health.last_error)
        elif self.state == ServiceState.RUNNING:
             pass 

        health.metrics = {
            "state": self.state.value,
            "last_collection": self._last_collection_time.isoformat() if self._last_collection_time else None,
            "monitoring_interval": self.monitoring_interval,
            "nvidia_available": NVIDIA_AVAILABLE,
            "nvidia_initialized": self.nvidia_initialized,
            "is_macos": IS_MACOS
        }
        
        return health
