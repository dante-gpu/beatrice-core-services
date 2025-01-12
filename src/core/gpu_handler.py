import logging
from typing import Dict, Optional
import nvidia_smi

class GPUHandler:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._initialize_nvidia()
        
    def _initialize_nvidia(self):
        """Initialize NVIDIA GPUs"""
        try:
            nvidia_smi.nvmlInit()
            self.nvidia_available = True
            self.logger.info("NVIDIA SMI initialized successfully")
        except Exception as e:
            self.nvidia_available = False
            self.logger.error(f"Failed to initialize NVIDIA SMI: {e}")
            
    def get_current_stats(self) -> Dict:
        """Get current GPU statistics"""
        if not self.nvidia_available:
            return {"active_gpus": 0, "total_earnings": 0}
            
        try:
            device_count = nvidia_smi.nvmlDeviceGetCount()
            stats = {
                "active_gpus": device_count,
                "total_earnings": 0,  # Will be fetched from our dante ai-marketplace
                "gpus": []
            }
            
            for i in range(device_count):
                handle = nvidia_smi.nvmlDeviceGetHandleByIndex(i)
                info = nvidia_smi.nvmlDeviceGetMemoryInfo(handle)
                util = nvidia_smi.nvmlDeviceGetUtilizationRates(handle)
                
                gpu_stats = {
                    "id": i,
                    "memory_used": info.used,
                    "memory_total": info.total,
                    "utilization": util.gpu
                }
                stats["gpus"].append(gpu_stats)
                
            return stats
            
        except Exception as e:
            self.logger.error(f"Failed to get GPU stats: {e}")
            return {"active_gpus": 0, "total_earnings": 0}
            
    def cleanup(self):
        """Clean up resources"""
        if self.nvidia_available:
            try:
                nvidia_smi.nvmlShutdown()
                self.logger.info("NVIDIA SMI shutdown complete")
            except Exception as e:
                self.logger.error(f"Error during NVIDIA SMI shutdown: {e}") 