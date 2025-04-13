import logging
import platform
import subprocess
import json
from typing import Dict, List, Optional, Any
import psutil # For macOS CPU/Mem stats

# Conditional import for NVIDIA
IS_MACOS = platform.system() == "Darwin"
NVIDIA_AVAILABLE = False
if not IS_MACOS:
    try:
        import nvidia_smi
        NVIDIA_AVAILABLE = True
    except ImportError:
        logging.warning("nvidia-ml-py3 library not found. NVIDIA GPU monitoring disabled.")
        NVIDIA_AVAILABLE = False
    except Exception as e:
        logging.error(f"Error importing or initializing nvidia-ml-py3: {e}")
        NVIDIA_AVAILABLE = False

class GPUHandler:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.nvidia_initialized = False
        if NVIDIA_AVAILABLE:
            self._initialize_nvidia()

    def _initialize_nvidia(self):
        """Initialize NVIDIA SMI if available"""
        if not NVIDIA_AVAILABLE:
            return
        try:
            nvidia_smi.nvmlInit()
            self.nvidia_initialized = True
            self.logger.info("NVIDIA SMI initialized successfully")
        except Exception as e:
            self.nvidia_initialized = False
            # Log specific NVML errors if possible
            if hasattr(e, 'value') and isinstance(e.value, str):
                 self.logger.error(f"Failed to initialize NVIDIA SMI: {e.value}")
            else:
                 self.logger.error(f"Failed to initialize NVIDIA SMI: {e}")


    def _get_macos_gpu_info(self) -> List[Dict[str, Any]]:
        """Get basic GPU info and system stats on macOS."""
        gpus = []
        try:
            # Get GPU model name(s) using system_profiler
            result = subprocess.run(
                ['system_profiler', 'SPDisplaysDataType', '-json'],
                capture_output=True, text=True, check=True
            )
            data = json.loads(result.stdout)
            display_info = data.get('SPDisplaysDataType', [])

            # Get overall CPU and Memory usage as proxy for activity
            cpu_percent = psutil.cpu_percent(interval=0.1)
            mem_info = psutil.virtual_memory()
            mem_percent = mem_info.percent
            mem_used = mem_info.used
            mem_total = mem_info.total

            for idx, gpu_data in enumerate(display_info):
                # Extracting model name might need adjustment based on exact output structure
                model_name = gpu_data.get('sppci_model', 'Unknown GPU')
                # Sometimes model is under _name on Apple Silicon
                if model_name == 'Unknown GPU':
                    model_name = gpu_data.get('_name', 'Unknown GPU')

                gpu_stats = {
                    "id": idx,
                    "model": model_name, # Add model name for macOS
                    "temperature": None, # Not available
                    "utilization": cpu_percent, # Use CPU % as proxy
                    "memory_used": mem_used, # Use system memory as proxy
                    "memory_total": mem_total, # Use system memory as proxy
                    "power_usage": None, # Not available
                    "fan_speed": None, # Not available
                }
                gpus.append(gpu_stats)

        except FileNotFoundError:
            self.logger.error("system_profiler command not found on macOS.")
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Error running system_profiler: {e}")
        except json.JSONDecodeError as e:
             self.logger.error(f"Error parsing system_profiler JSON output: {e}")
        except Exception as e:
            self.logger.error(f"Error getting macOS GPU/System info: {e}")

        # If system_profiler fails, return at least system stats
        if not gpus:
             cpu_percent = psutil.cpu_percent(interval=0.1)
             mem_info = psutil.virtual_memory()
             gpus.append({
                 "id": 0,
                 "model": "System",
                 "temperature": None,
                 "utilization": cpu_percent,
                 "memory_used": mem_info.used,
                 "memory_total": mem_info.total,
                 "power_usage": None,
                 "fan_speed": None,
             })

        return gpus

    def _get_nvidia_gpu_info(self) -> List[Dict[str, Any]]:
        """Get detailed GPU info using nvidia-smi."""
        gpus = []
        if not self.nvidia_initialized:
            self.logger.warning("NVIDIA SMI not initialized, cannot get stats.")
            return gpus

        try:
            device_count = nvidia_smi.nvmlDeviceGetCount()
            for i in range(device_count):
                handle = nvidia_smi.nvmlDeviceGetHandleByIndex(i)
                model_name = nvidia_smi.nvmlDeviceGetName(handle) # Get model name
                temp = nvidia_smi.nvmlDeviceGetTemperature(handle, nvidia_smi.NVML_TEMPERATURE_GPU)
                util = nvidia_smi.nvmlDeviceGetUtilizationRates(handle)
                mem = nvidia_smi.nvmlDeviceGetMemoryInfo(handle)
                power = None
                fan = None
                try:
                    power = nvidia_smi.nvmlDeviceGetPowerUsage(handle) / 1000.0 # Convert mW to W
                except nvidia_smi.NVMLError_NotSupported:
                    self.logger.debug(f"Power usage not supported for GPU {i}")
                except Exception as e_power:
                     self.logger.warning(f"Could not get power for GPU {i}: {e_power}")

                try:
                    fan = nvidia_smi.nvmlDeviceGetFanSpeed(handle)
                except nvidia_smi.NVMLError_NotSupported:
                     self.logger.debug(f"Fan speed not supported for GPU {i}")
                except Exception as e_fan:
                     self.logger.warning(f"Could not get fan speed for GPU {i}: {e_fan}")


                gpu_stats = {
                    "id": i,
                    "model": model_name,
                    "temperature": temp,
                    "utilization": util.gpu,
                    "memory_used": mem.used,
                    "memory_total": mem.total,
                    "power_usage": power,
                    "fan_speed": fan
                }
                gpus.append(gpu_stats)
        except nvidia_smi.NVMLError as e:
             self.logger.error(f"NVIDIA SMI error getting stats: {e}")
        except Exception as e:
            self.logger.error(f"Unexpected error getting NVIDIA stats: {e}")
        return gpus

    def get_current_stats(self) -> Dict:
        """Get current GPU statistics based on the operating system."""
        stats = {
            "active_gpus": 0,
            "total_earnings": 0,  # Placeholder
            "gpus": []
        }

        if IS_MACOS:
            gpu_list = self._get_macos_gpu_info()
            stats["gpus"] = gpu_list
            # On macOS, 'active_gpus' might just be the count from system_profiler
            stats["active_gpus"] = len(gpu_list) if any(g.get("model") != "System" for g in gpu_list) else 0
        elif NVIDIA_AVAILABLE and self.nvidia_initialized:
            gpu_list = self._get_nvidia_gpu_info()
            stats["gpus"] = gpu_list
            stats["active_gpus"] = len(gpu_list)
        else:
            # No compatible GPU monitoring available
            self.logger.warning("No compatible GPU monitoring available on this system.")
            # Return empty stats
            pass

        return stats

    def cleanup(self):
        """Clean up resources"""
        if self.nvidia_initialized:
            try:
                nvidia_smi.nvmlShutdown()
                self.logger.info("NVIDIA SMI shutdown complete")
                self.nvidia_initialized = False
            except Exception as e:
                self.logger.error(f"Error during NVIDIA SMI shutdown: {e}")
