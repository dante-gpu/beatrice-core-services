#!/usr/bin/env python3

import subprocess
import json
import os
import argparse
import time
from datetime import datetime
import sys 

class MacGPUStat:
    def __init__(self):
        if sys.platform != "darwin":
            print("Error: MacGPUStat is designed to run only on macOS.", file=sys.stderr)
            sys.exit(1)
            
        self.is_apple_silicon = self._check_apple_silicon()
        
    def _check_apple_silicon(self):
        try:
            output = subprocess.check_output(['sysctl', '-n', 'hw.optional.arm64']).decode('utf-8').strip()
            return output == '1'
        except Exception:
            try:
                output = subprocess.check_output(['sysctl', 'machdep.cpu.brand_string']).decode('utf-8')
                return 'Apple' in output
            except Exception:
                print("Warning: Could not determine CPU type.", file=sys.stderr)
                return False
    
    def _run_command(self, cmd_list):
        try:
            result = subprocess.run(cmd_list, capture_output=True, text=True, check=True)
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            print(f"Error running command '{' '.join(cmd_list)}': {e}", file=sys.stderr)
            if e.stderr:
                print(f"Stderr: {e.stderr.strip()}", file=sys.stderr)
            return None
        except FileNotFoundError:
            print(f"Error: Command '{cmd_list[0]}' not found.", file=sys.stderr)
            return None
        except Exception as e:
            print(f"Unexpected error running command '{' '.join(cmd_list)}': {e}", file=sys.stderr)
            return None

    def get_system_profiler_data(self, data_type):
        cmd_list = ['system_profiler', data_type, '-json']
        output = self._run_command(cmd_list)
        if output:
            try:
                return json.loads(output)
            except json.JSONDecodeError as e:
                print(f"Error decoding JSON from system_profiler for {data_type}: {e}", file=sys.stderr)
                return None
        return None
    
    def get_gpu_info(self):
        gpu_data = self.get_system_profiler_data("SPDisplaysDataType")
        if not gpu_data:
            return []
        
        gpus = []
        display_info = gpu_data.get("SPDisplaysDataType", [])
        if not display_info:
             print("Warning: No display data found in system_profiler output.", file=sys.stderr)
             return []
             
        for card in display_info:
            name = card.get("_name") if self.is_apple_silicon else card.get("sppci_model")
            if not name:
                 name = card.get("sppci_model", "Unknown GPU") 

            gpu_info = {
                "name": name,
                "vendor": card.get("spdisplays_vendor", "Unknown"),
                "vram": card.get("spdisplays_vram", "N/A"),
                "device_id": card.get("spdisplays_device_id", card.get("sppci_device_id", "N/A")),
                "vendor_id": card.get("spdisplays_vendor_id", card.get("sppci_vendor_id", "N/A")),
                "bus": card.get("spdisplays_pcislot", card.get("sppci_bus", "N/A")),
                "metal_family": card.get("spdisplays_metal_family", "N/A") 
            }
            if gpu_info["vendor"] != "Unknown" and gpu_info["vendor_id"] in gpu_info["vendor"]:
                 gpu_info["vendor"] = gpu_info["vendor"].split('(')[0].strip()

            gpus.append(gpu_info)
        return gpus
    
    def get_gpu_usage(self):
        if self.is_apple_silicon:
            cmd_list = ["sudo", "powermetrics", "--samplers", "gpu_power", "-n", "1", "-i", "1", "--show-process-gpu", "-j"]
            print("Info: Running powermetrics with sudo to get detailed Apple Silicon GPU stats...", file=sys.stderr)
            output = self._run_command(cmd_list)
            if output:
                try:
                    last_json_line = None
                    for line in output.strip().split('\n'):
                        if line.strip().startswith('{') and line.strip().endswith('}'):
                            last_json_line = line
                    
                    if not last_json_line:
                         print("Warning: Could not find valid JSON summary in powermetrics output.", file=sys.stderr)
                         return {"gpu_utilization": "N/A", "gpu_power": "N/A", "processes": []}

                    data = json.loads(last_json_line)
                    gpu_stats = data.get("gpu_metrics", {}) 
                    if not gpu_stats:
                         gpu_stats = data.get("gpu_power", {}) 

                    processes = []
                    if "gpu_processes" in data:
                         processes = [p for p in data["gpu_processes"] if p.get("usage", 0) > 0]

                    return {
                        "gpu_utilization": gpu_stats.get("GPU Utilization (%)", gpu_stats.get("gpu_power_utilization", "N/A")),
                        "gpu_power": gpu_stats.get("GPU Power (W)", gpu_stats.get("gpu_power_wattage", "N/A")),
                        "processes": processes
                    }
                except json.JSONDecodeError as e:
                    print(f"Error decoding JSON from powermetrics: {e}", file=sys.stderr)
                    print(f"Received output: {output[:500]}...", file=sys.stderr) 
                except KeyError as e:
                    print(f"KeyError accessing powermetrics data: {e}", file=sys.stderr)
                except Exception as e:
                     print(f"Unexpected error processing powermetrics data: {e}", file=sys.stderr)

            else:
                 print("Warning: Failed to get output from powermetrics. Ensure sudo permissions are correct.", file=sys.stderr)
            return {"gpu_utilization": "N/A", "gpu_power": "N/A", "processes": []}
        else:
            print("Info: Detailed real-time GPU usage statistics (Utilization, Power) are not readily available via standard tools for non-Apple Silicon GPUs on macOS.", file=sys.stderr)
            return {"note": "Detailed usage stats not available for this GPU type"}
    
    def display_gpu_info(self, watch=False, interval=1):
        try:
            while True:
                if watch:
                    os.system('clear') 
                
                print(f"\n{'=' * 80}")
                print(f" MacGPUStat - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - Platform: {'Apple Silicon' if self.is_apple_silicon else 'Intel/AMD'}")
                print(f"{'=' * 80}")
                
                gpus = self.get_gpu_info()
                if not gpus:
                    print("\nNo GPU information available.")
                    print(f"{'=' * 80}")
                    if not watch: break
                    time.sleep(interval)
                    continue 
                
                for i, gpu in enumerate(gpus):
                    print(f"\nGPU [{i}]: {gpu['name']}")
                    print(f"  Vendor: {gpu['vendor']} (ID: {gpu['vendor_id']})")
                    print(f"  VRAM: {gpu['vram']}")
                    print(f"  Device ID: {gpu['device_id']}")
                    print(f"  Bus: {gpu['bus']}")
                    print(f"  Metal Family: {gpu['metal_family']}")
                
                print("\nGPU Usage:")
                usage = self.get_gpu_usage()
                
                if self.is_apple_silicon:
                    util = usage.get('gpu_utilization', 'N/A')
                    power = usage.get('gpu_power', 'N/A')
                    print(f"  Utilization: {util}%" if util != 'N/A' else "  Utilization: N/A")
                    print(f"  Power: {power} W" if power != 'N/A' else "  Power: N/A")
                    
                    processes = usage.get('processes', [])
                    if processes:
                        print("\n  GPU Processes:")
                        try:
                            processes.sort(key=lambda p: p.get('usage', 0), reverse=True)
                        except: pass 

                        for proc in processes[:10]: 
                            pid = proc.get('pid', 'N/A')
                            name = proc.get('command', 'Unknown')
                            p_usage = proc.get('usage', 'N/A') 
                            print(f"    - PID: {pid:<6} | Usage: {p_usage:<5}% | Command: {name}")
                    elif usage.get('gpu_utilization') != 'N/A': 
                         print("  No active GPU processes detected.")

                elif "note" in usage:
                    print(f"  {usage['note']}")
                    print("  (Consider using Activity Monitor or third-party tools like iStat Menus for general activity)")
                else:
                     print("  Could not retrieve usage information.") 
                
                print(f"\n{'=' * 80}")
                
                if not watch:
                    break
                    
                time.sleep(interval)
                
        except KeyboardInterrupt:
            print("\nExiting MacGPUStat...")
        except Exception as e:
             print(f"\nAn unexpected error occurred: {e}", file=sys.stderr)

def main():
    is_apple_silicon = False
    try:
        output = subprocess.check_output(['sysctl', '-n', 'hw.optional.arm64']).decode('utf-8').strip()
        is_apple_silicon = output == '1'
    except Exception: pass

    if is_apple_silicon and os.geteuid() != 0:
        print("Warning: Running without sudo on Apple Silicon.", file=sys.stderr)
        print("Detailed GPU usage (Utilization, Power, Processes) requires sudo privileges for powermetrics.", file=sys.stderr)
        print("Attempting to run without detailed usage stats...", file=sys.stderr)

    parser = argparse.ArgumentParser(
        description='MacGPUStat - A macOS GPU monitoring tool (like nvidia-smi)',
        formatter_class=argparse.RawTextHelpFormatter 
    )
    parser.add_argument(
        '-w', '--watch', 
        action='store_true', 
        help='Continuously monitor GPU status (similar to nvidia-smi -l).\nClears screen before each update.'
    )
    parser.add_argument(
        '-i', '--interval', 
        type=int, 
        default=2, 
        help='Refresh interval in seconds when using --watch (default: 2)'
    )
    args = parser.parse_args()
    
    if args.interval <= 0:
        print("Error: Interval must be a positive integer.", file=sys.stderr)
        sys.exit(1)

    try:
        mac_gpu = MacGPUStat()
        mac_gpu.display_gpu_info(watch=args.watch, interval=args.interval)
    except Exception as e:
         print(f"Failed to start MacGPUStat: {e}", file=sys.stderr)
         sys.exit(1)

if __name__ == "__main__":
    if sys.version_info[0] < 3:
        print("Error: MacGPUStat requires Python 3.", file=sys.stderr)
        sys.exit(1)
    main()
