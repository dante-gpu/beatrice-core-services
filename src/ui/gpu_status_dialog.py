import logging
import platform
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QScrollArea, QWidget, QGridLayout, 
                             QLabel, QDialogButtonBox, QGroupBox, QSizePolicy)
from PyQt6.QtCore import Qt

try:
    from ..utils.helpers import format_bytes
except ImportError:
    from utils.helpers import format_bytes

class GPUStatusDialog(QDialog):
    def __init__(self, current_stats: dict | None, parent=None):
        super().__init__(parent)
        self.current_stats = current_stats if current_stats else {}
        self.logger = logging.getLogger(__name__)

        self.setWindowTitle("Detailed GPU Status")
        self.setMinimumSize(500, 400)

        main_layout = QVBoxLayout(self)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        main_layout.addWidget(scroll_area)

        content_widget = QWidget()
        scroll_area.setWidget(content_widget)
        self.content_layout = QVBoxLayout(content_widget)
        self.content_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        button_box.accepted.connect(self.accept)
        main_layout.addWidget(button_box)

        self.populate_gpu_details()
        self.logger.debug("GPUStatusDialog initialized.")

    def populate_gpu_details(self):
        try:
            gpu_list = self.current_stats.get('gpus', [])

            if not gpu_list:
                self.content_layout.addWidget(QLabel("No GPU information available."))
                return

            for gpu_data in gpu_list:
                gpu_group = self._create_gpu_group(gpu_data)
                self.content_layout.addWidget(gpu_group)
                
            self.content_layout.addStretch(1) 

        except Exception as e:
            self.logger.error(f"Error populating GPU status dialog: {e}")
            self.content_layout.addWidget(QLabel(f"Error loading GPU details: {e}"))

    def _create_gpu_group(self, gpu_data: dict) -> QGroupBox:
        gpu_id = gpu_data.get('id', 'N/A')
        model = gpu_data.get('model', 'N/A')
        
        group_box = QGroupBox(f"GPU [{gpu_id}]: {model}")
        group_layout = QGridLayout(group_box)

        temp = gpu_data.get('temperature')
        util = gpu_data.get('utilization')
        mem_used = gpu_data.get('memory_used')
        mem_total = gpu_data.get('memory_total')
        power = gpu_data.get('power_usage')
        fan = gpu_data.get('fan_speed')
        
        vendor = gpu_data.get('vendor', 'N/A')
        vram_str = gpu_data.get('vram', 'N/A') 
        device_id = gpu_data.get('device_id', 'N/A')
        vendor_id = gpu_data.get('vendor_id', 'N/A')
        bus = gpu_data.get('bus', 'N/A')
        metal = gpu_data.get('metal_family', 'N/A')

        temp_str = f"{temp}°C" if temp is not None else "N/A"
        util_str = f"{util}%" if util is not None else "N/A" 
        mem_str = f"{format_bytes(mem_used)} / {format_bytes(mem_total)}" if mem_used is not None and mem_total is not None else "N/A"
        power_str = f"{power:.1f} W" if power is not None else "N/A"
        fan_str = f"{fan}%" if fan is not None else "N/A"

        row = 0
        group_layout.addWidget(QLabel("Model:"), row, 0)
        group_layout.addWidget(QLabel(model), row, 1)
        row += 1
        group_layout.addWidget(QLabel("Vendor:"), row, 0)
        group_layout.addWidget(QLabel(f"{vendor} (ID: {vendor_id})"), row, 1)
        row += 1
        group_layout.addWidget(QLabel("VRAM:"), row, 0)
        group_layout.addWidget(QLabel(vram_str), row, 1)
        row += 1
        group_layout.addWidget(QLabel("Device ID:"), row, 0)
        group_layout.addWidget(QLabel(device_id), row, 1)
        row += 1
        group_layout.addWidget(QLabel("Bus Info:"), row, 0)
        group_layout.addWidget(QLabel(bus), row, 1)
        row += 1
        group_layout.addWidget(QLabel("Metal Family:"), row, 0)
        group_layout.addWidget(QLabel(metal), row, 1) # Relevant for macOS
        row += 1
        
        # Add WMI specific fields if present
        wmi_driver = gpu_data.get('wmi_driver_version')
        wmi_processor = gpu_data.get('wmi_video_processor')
        wmi_ram_bytes = gpu_data.get('wmi_adapter_ram')
        wmi_resolution = gpu_data.get('wmi_resolution')
        wmi_refresh = gpu_data.get('wmi_refresh_rate')
        
        if wmi_driver:
             group_layout.addWidget(QLabel("Driver (WMI):"), row, 0)
             group_layout.addWidget(QLabel(wmi_driver), row, 1)
             row += 1
        if wmi_processor:
             group_layout.addWidget(QLabel("Processor (WMI):"), row, 0)
             group_layout.addWidget(QLabel(wmi_processor), row, 1)
             row += 1
        if wmi_ram_bytes:
             group_layout.addWidget(QLabel("Adapter RAM (WMI):"), row, 0)
             group_layout.addWidget(QLabel(format_bytes(wmi_ram_bytes)), row, 1)
             row += 1
        if wmi_resolution and wmi_resolution != '?x?':
             group_layout.addWidget(QLabel("Resolution (WMI):"), row, 0)
             group_layout.addWidget(QLabel(wmi_resolution), row, 1)
             row += 1
        if wmi_refresh:
             group_layout.addWidget(QLabel("Refresh Rate (WMI):"), row, 0)
             group_layout.addWidget(QLabel(f"{wmi_refresh} Hz"), row, 1)
             row += 1
             
        # Standard metrics
        group_layout.addWidget(QLabel("Temperature:"), row, 0)
        group_layout.addWidget(QLabel(temp_str), row, 1)
        row += 1
        
        is_macos = platform.system() == "Darwin"
        util_label_text = "Overall CPU Usage:" if is_macos else "GPU Utilization:"
        mem_label_text = "System Memory Usage:" if is_macos else "GPU Memory Usage:"
        
        group_layout.addWidget(QLabel(util_label_text), row, 0)
        group_layout.addWidget(QLabel(util_str), row, 1)
        row += 1
        group_layout.addWidget(QLabel(mem_label_text), row, 0)
        group_layout.addWidget(QLabel(mem_str), row, 1)
        row += 1
        group_layout.addWidget(QLabel("Power Draw:"), row, 0)
        group_layout.addWidget(QLabel(power_str), row, 1)
        row += 1
        group_layout.addWidget(QLabel("Fan Speed:"), row, 0)
        group_layout.addWidget(QLabel(fan_str), row, 1)
        row += 1

        if is_macos:
            note_label = QLabel("Note: Detailed GPU Util/Power requires running\n`sudo python3 src/cli/macgpustat.py` in terminal.")
            note_label.setStyleSheet("font-style: italic; color: #aaa;")
            note_label.setWordWrap(True)
            group_layout.addWidget(note_label, row, 0, 1, 2)
            row += 1

        group_layout.setColumnStretch(1, 1) 

        return group_box
