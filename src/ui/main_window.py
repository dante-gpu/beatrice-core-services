import logging
from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QLabel, QTableWidget, 
                             QTableWidgetItem, QHeaderView, QGroupBox, QHBoxLayout)
from PyQt6.QtCore import Qt

# Helper function to format bytes
def format_bytes(bytes_val):
    if bytes_val is None:
        return "N/A"
    if bytes_val < 1024:
        return f"{bytes_val} B"
    elif bytes_val < 1024**2:
        return f"{bytes_val/1024:.1f} KiB"
    elif bytes_val < 1024**3:
        return f"{bytes_val/1024**2:.1f} MiB"
    else:
        return f"{bytes_val/1024**3:.1f} GiB"

class MainWindow(QMainWindow):
    def __init__(self, gpu_handler, marketplace):
        super().__init__()
        self.gpu_handler = gpu_handler
        self.marketplace = marketplace
        self.logger = logging.getLogger(__name__)
        
        self.setWindowTitle("DanteGPU Beatrice Dashboard")
        self.setMinimumSize(800, 600)
        
        # --- Main Layout ---
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        
        # --- Summary Group ---
        summary_group = QGroupBox("Overall Status")
        summary_layout = QHBoxLayout()
        summary_group.setLayout(summary_layout)
        
        self.active_gpus_label = QLabel("Active GPUs: Loading...")
        self.total_earnings_label = QLabel("Total Earnings: Loading...")
        
        summary_layout.addWidget(self.active_gpus_label)
        summary_layout.addStretch() # Add space between labels
        summary_layout.addWidget(self.total_earnings_label)
        
        main_layout.addWidget(summary_group)
        
        # --- GPU Details Table ---
        self.gpu_table = QTableWidget()
        self.gpu_table.setColumnCount(7) # ID, Model, Temp, Util, Mem, Power, Fan
        self.gpu_table.setHorizontalHeaderLabels([
            "ID", "Model", "Temp (°C)", "Util (%)", "Memory", "Power (W)", "Fan (%)"
        ])
        self.gpu_table.verticalHeader().setVisible(False) # Hide row numbers
        self.gpu_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers) # Read-only
        self.gpu_table.setAlternatingRowColors(True)
        
        # Set column widths
        header = self.gpu_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents) # ID
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)          # Model
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents) # Temp
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents) # Util
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)          # Memory
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents) # Power
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents) # Fan
        
        main_layout.addWidget(self.gpu_table)

        self.logger.info("MainWindow UI initialized.")

    def update_stats(self, stats):
        """Update dashboard with new GPU statistics"""
        if not stats or 'gpus' not in stats:
            self.active_gpus_label.setText("Active GPUs: N/A")
            self.total_earnings_label.setText("Total Earnings: N/A")
            self.gpu_table.setRowCount(0) # Clear table
            self.logger.warning("Received invalid stats data.")
            return
            
        # Update summary
        active_gpus = stats.get('active_gpus', 0)
        total_earnings = stats.get('total_earnings', 0.0) # Assuming float earnings
        self.active_gpus_label.setText(f"Active GPUs: {active_gpus}")
        self.total_earnings_label.setText(f"Total Earnings: {total_earnings:.4f} SOL") # Format earnings
        
        # Update table
        gpu_list = stats.get('gpus', [])
        self.gpu_table.setRowCount(len(gpu_list))
        
        for row, gpu_data in enumerate(gpu_list):
            gpu_id = gpu_data.get('id', 'N/A')
            model = gpu_data.get('model', 'N/A') # Get model name
            temp = gpu_data.get('temperature', 'N/A')
            # On macOS, utilization shows CPU %. Clarify this in header? Or leave as is? Leaving as is for now.
            util = gpu_data.get('utilization', 'N/A') 
            mem_used = gpu_data.get('memory_used')
            mem_total = gpu_data.get('memory_total')
            power = gpu_data.get('power_usage', 'N/A')
            fan = gpu_data.get('fan_speed', 'N/A')

            # Format memory
            mem_str = f"{format_bytes(mem_used)} / {format_bytes(mem_total)}" if mem_used is not None and mem_total is not None else "N/A"
            
            # Format optional values
            power_str = f"{power:.1f}" if power is not None else "N/A"
            fan_str = f"{fan}" if fan is not None else "N/A"
            temp_str = f"{temp}" if temp is not None else "N/A"
            util_str = f"{util}" if util is not None else "N/A"

            # Create table items
            id_item = QTableWidgetItem(str(gpu_id))
            model_item = QTableWidgetItem(model) # Create model item
            temp_item = QTableWidgetItem(temp_str)
            util_item = QTableWidgetItem(util_str)
            mem_item = QTableWidgetItem(mem_str)
            power_item = QTableWidgetItem(power_str)
            fan_item = QTableWidgetItem(fan_str)

            # Center align numeric-like columns
            temp_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            util_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            power_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            fan_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            # Populate row
            self.gpu_table.setItem(row, 0, id_item)
            self.gpu_table.setItem(row, 1, model_item) # Add model item to table
            self.gpu_table.setItem(row, 2, temp_item)
            self.gpu_table.setItem(row, 3, util_item)
            self.gpu_table.setItem(row, 4, mem_item)
            self.gpu_table.setItem(row, 5, power_item)
            self.gpu_table.setItem(row, 6, fan_item)
            
        # self.logger.debug("Dashboard UI updated with new stats.") # Use DEBUG level

    def show_gpu_status_dialog(self):
        """Show GPU status dialog (Placeholder)"""
        # TODO: Implement a more detailed status dialog if needed
        self.logger.info("GPU Status dialog requested (not implemented yet).")
        pass
        
    def show_settings_dialog(self):
        """Show settings dialog (Placeholder)"""
        # TODO: Implement settings dialog
        self.logger.info("Settings dialog requested (not implemented yet).")
        pass
