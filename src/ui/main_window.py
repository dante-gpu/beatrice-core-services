import logging
from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QLabel, QTableWidget, 
                             QTableWidgetItem, QHeaderView, QGroupBox, QHBoxLayout,
                             QProgressBar, QApplication) # Import QProgressBar and QApplication
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

# Custom QProgressBar for table cells
class TableProgressBar(QProgressBar):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # Ensure text is visible even with low progress values
        self.setStyleSheet("""
            QProgressBar {
                text-align: center;
                padding: 1px;
                border-radius: 5px;
                background-color: #45494c; /* Match theme */
                color: #f0f0f0; /* Match theme */
            }
            QProgressBar::chunk {
                background-color: #007bff; /* Blue progress */
                border-radius: 4px;
                margin: 0.5px;
            }
        """)

    # Override text method to always show percentage
    def text(self) -> str:
        if self.maximum() == 0:
            return "N/A"
        return f"{self.value()}%"


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
        self.gpu_table.setFocusPolicy(Qt.FocusPolicy.NoFocus) # Prevent cell selection outline
        self.gpu_table.setSelectionMode(QTableWidget.SelectionMode.NoSelection) # Disable selection
        
        # Set column widths
        header = self.gpu_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents) # ID
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)          # Model
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents) # Temp
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)          # Util (Progress Bar)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)          # Memory (Progress Bar)
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
            temp = gpu_data.get('temperature') # Keep as number or None
            util = gpu_data.get('utilization') # Keep as number or None
            mem_used = gpu_data.get('memory_used') # Keep as number or None
            mem_total = gpu_data.get('memory_total') # Keep as number or None
            power = gpu_data.get('power_usage') # Keep as number or None
            fan = gpu_data.get('fan_speed') # Keep as number or None

            # --- Create Table Items/Widgets ---
            id_item = QTableWidgetItem(str(gpu_id))
            model_item = QTableWidgetItem(model) 
            
            # Temperature Item
            temp_str = f"{temp}" if temp is not None else "N/A"
            temp_item = QTableWidgetItem(temp_str)
            temp_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            # Power Item
            power_str = f"{power:.1f}" if power is not None else "N/A"
            power_item = QTableWidgetItem(power_str)
            power_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            # Fan Item
            fan_str = f"{fan}" if fan is not None else "N/A"
            fan_item = QTableWidgetItem(fan_str)
            fan_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            # --- Create Progress Bars ---
            # Utilization Progress Bar
            util_progress = TableProgressBar()
            if util is not None:
                util_progress.setRange(0, 100)
                util_progress.setValue(int(util))
            else:
                util_progress.setRange(0, 0) # Makes it show N/A via text() override
                util_progress.setValue(0)

            # Memory Progress Bar
            mem_progress = TableProgressBar()
            if mem_used is not None and mem_total is not None and mem_total > 0:
                mem_progress.setRange(0, 100)
                mem_percent = int((mem_used / mem_total) * 100)
                mem_progress.setValue(mem_percent)
                # Override text to show usage details
                mem_progress.text = lambda mu=mem_used, mt=mem_total: f"{format_bytes(mu)} / {format_bytes(mt)}"
            else:
                mem_progress.setRange(0, 0)
                mem_progress.setValue(0)
                mem_progress.text = lambda: "N/A"


            # --- Populate Row ---
            self.gpu_table.setItem(row, 0, id_item)
            self.gpu_table.setItem(row, 1, model_item) 
            self.gpu_table.setItem(row, 2, temp_item)
            self.gpu_table.setCellWidget(row, 3, util_progress) # Use setCellWidget for progress bar
            self.gpu_table.setCellWidget(row, 4, mem_progress) # Use setCellWidget for progress bar
            self.gpu_table.setItem(row, 5, power_item)
            self.gpu_table.setItem(row, 6, fan_item)
            
        # Adjust row heights to fit progress bars if needed
        self.gpu_table.resizeRowsToContents() 
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

# Example usage for testing the UI standalone (optional)
# if __name__ == '__main__':
#     import sys
#     # Mock handlers for testing
#     class MockGPUHandler:
#         def get_current_stats(self):
#             # Return some sample data
#             return {
#                 "active_gpus": 2,
#                 "total_earnings": 1.2345,
#                 "gpus": [
#                     {"id": 0, "model": "NVIDIA GeForce RTX 3080", "temperature": 65, "utilization": 85, "memory_used": 6*1024**3, "memory_total": 10*1024**3, "power_usage": 250.5, "fan_speed": 70},
#                     {"id": 1, "model": "NVIDIA GeForce RTX 3070", "temperature": 58, "utilization": 60, "memory_used": 4*1024**3, "memory_total": 8*1024**3, "power_usage": 180.0, "fan_speed": 65},
#                     {"id": 2, "model": "Apple M2 Max GPU", "temperature": None, "utilization": 45, "memory_used": 12*1024**3, "memory_total": 32*1024**3, "power_usage": None, "fan_speed": None}, # macOS example
#                 ]
#             }
#     class MockMarketplace: pass

#     app = QApplication(sys.argv)
    
#     # Apply stylesheet directly for testing
#     stylesheet = """ ... [Paste Stylesheet Here] ... """
#     app.setStyleSheet(stylesheet)

#     window = MainWindow(MockGPUHandler(), MockMarketplace())
#     window.show()
#     window.update_stats(window.gpu_handler.get_current_stats()) # Initial update
#     sys.exit(app.exec())
