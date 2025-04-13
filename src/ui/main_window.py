import logging
import platform 
import webbrowser 
import urllib.parse 
from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QLabel, QTableWidget, 
                             QTableWidgetItem, QHeaderView, QGroupBox, QHBoxLayout,
                             QProgressBar, QApplication, QPushButton) # Add QPushButton
from PyQt6.QtCore import Qt

try:
    from ..utils.helpers import format_bytes
except ImportError:
    from utils.helpers import format_bytes 

class TableProgressBar(QProgressBar):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet("""
            QProgressBar {
                text-align: center;
                padding: 1px;
                border-radius: 5px;
                background-color: #45494c; 
                color: #f0f0f0; 
            }
            QProgressBar::chunk {
                background-color: #007bff; 
                border-radius: 4px;
                margin: 0.5px;
            }
        """)

    def text(self) -> str:
        if self.maximum() == 0:
            return "N/A"
        return f"{self.value()}%"


class MainWindow(QMainWindow):
    def __init__(self, gpu_handler, marketplace, gpu_status_message: str | None = None): 
        super().__init__()
        self.gpu_handler = gpu_handler # Still needed for GPUStatusDialog currently
        self.marketplace = marketplace
        self.logger = logging.getLogger(__name__)
        
        self.setWindowTitle("DanteGPU Beatrice Dashboard")
        self.setMinimumSize(800, 600)
        
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)

        if gpu_status_message:
            self.status_label = QLabel(gpu_status_message)
            if "Warning:" in gpu_status_message:
                 self.status_label.setStyleSheet("color: #ffc107; padding: 5px; border: 1px solid #ffc107; border-radius: 3px; background-color: #4a4a2a;") # Adjusted warning color
            else:
                 self.status_label.setStyleSheet("color: #cccccc; padding: 5px; border: 1px solid #555; border-radius: 3px; background-color: #444;") 
            self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.status_label.setWordWrap(True)
            main_layout.addWidget(self.status_label)
        
        summary_group = QGroupBox("Overall Status")
        summary_layout = QHBoxLayout()
        summary_group.setLayout(summary_layout)
        
        self.active_gpus_label = QLabel("Active GPUs: Loading...")
        self.total_earnings_label = QLabel("Total Earnings: Loading...")
        
        summary_layout.addWidget(self.active_gpus_label)
        summary_layout.addStretch() 
        summary_layout.addWidget(self.total_earnings_label)
        
        # Add Connect Wallet Button to summary layout
        self.connect_wallet_button = QPushButton("🔗 Connect Phantom")
        self.connect_wallet_button.clicked.connect(self.connect_phantom)
        # Optional: Add some styling or fixed width
        self.connect_wallet_button.setStyleSheet("padding: 5px 10px;") 
        summary_layout.addWidget(self.connect_wallet_button)
        
        main_layout.addWidget(summary_group)
        
        self.gpu_table = QTableWidget()
        self.gpu_table.setColumnCount(7) 
        
        is_macos = platform.system() == "Darwin"
        util_header = "CPU (%)" if is_macos else "Util (%)"
        mem_header = "Sys Mem" if is_macos else "Memory"
        self.gpu_table.setHorizontalHeaderLabels([
            "ID", "Model", "Temp (°C)", util_header, mem_header, "Power (W)", "Fan (%)"
        ])
        self.gpu_table.verticalHeader().setVisible(False) 
        self.gpu_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers) 
        self.gpu_table.setAlternatingRowColors(True)
        self.gpu_table.setFocusPolicy(Qt.FocusPolicy.NoFocus) 
        self.gpu_table.setSelectionMode(QTableWidget.SelectionMode.NoSelection) 
        
        header = self.gpu_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents) 
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)          
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents) 
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)          
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)          
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents) 
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents) 
        
        main_layout.addWidget(self.gpu_table)

        self.logger.info("MainWindow UI initialized.")

    def connect_phantom(self):
        self.logger.info("Attempting to initiate Phantom connection...")
        
        # --- Construct the Phantom deeplink URI ---
        # Based on common patterns, but might need adjustment
        # We need a way for Phantom to know which app is connecting.
        # Using a placeholder URL for the app. A real URL or domain is better.
        app_url = urllib.parse.quote("https://dantegpu.app") 
        # Phantom might require a redirect URL, even if we can't easily capture it
        # Using a simple localhost URL as a placeholder redirect.
        redirect_url = urllib.parse.quote("dantegpu://connection-success") 
        
        # Construct the URI (v1 connect is common)
        # Note: Cluster info might also be needed depending on Phantom's requirements
        phantom_uri = f"phantom://v1/connect?app_url={app_url}&redirect_link={redirect_url}"
        
        self.logger.info(f"Opening URI: {phantom_uri}")
        
        try:
            opened = webbrowser.open(phantom_uri)
            if not opened:
                 self.logger.warning("webbrowser.open() returned False. OS might not have handler for phantom://")
                 # Optionally show message to user
                 # QMessageBox.warning(self, "Connection Failed", "Could not automatically open Phantom. Ensure it is installed and configured to handle connection requests.")
            else:
                 # We can't confirm connection success here, just that the request was sent.
                 self.logger.info("Phantom connection request initiated via browser/OS.")
                 # Optionally disable button temporarily or show status
                 self.connect_wallet_button.setText("Request Sent...")
                 self.connect_wallet_button.setEnabled(False)
                 # Re-enable after a delay? Or require app restart?
                 QTimer.singleShot(5000, lambda: (
                      self.connect_wallet_button.setText("🔗 Connect Phantom"), 
                      self.connect_wallet_button.setEnabled(True)
                 ))

        except Exception as e:
            self.logger.error(f"Failed to open Phantom URI: {e}", exc_info=True)
            # Optionally show message to user
            # QMessageBox.critical(self, "Error", f"Could not open Phantom connection URI: {e}")


    def update_stats(self, stats):
        if not stats or 'gpus' not in stats:
            self.active_gpus_label.setText("Active GPUs: N/A")
            self.total_earnings_label.setText("Total Earnings: N/A")
            self.gpu_table.setRowCount(0) 
            self.logger.warning("Received invalid stats data.")
            return
            
        active_gpus = stats.get('active_gpus', 0)
        total_earnings = stats.get('total_earnings', 0.0) 
        self.active_gpus_label.setText(f"Active GPUs: {active_gpus}")
        self.total_earnings_label.setText(f"Total Earnings: {total_earnings:.4f} SOL") 
        
        gpu_list = stats.get('gpus', [])
        self.gpu_table.setRowCount(len(gpu_list))
        
        for row, gpu_data in enumerate(gpu_list):
            gpu_id = gpu_data.get('id', 'N/A')
            model = gpu_data.get('model', 'N/A') 
            temp = gpu_data.get('temperature') 
            util = gpu_data.get('utilization') 
            mem_used = gpu_data.get('memory_used') 
            mem_total = gpu_data.get('memory_total') 
            power = gpu_data.get('power_usage') 
            fan = gpu_data.get('fan_speed') 

            id_item = QTableWidgetItem(str(gpu_id))
            model_item = QTableWidgetItem(model) 
            
            temp_str = f"{temp}" if temp is not None else "N/A"
            temp_item = QTableWidgetItem(temp_str)
            temp_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            power_str = f"{power:.1f}" if power is not None else "N/A"
            power_item = QTableWidgetItem(power_str)
            power_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            fan_str = f"{fan}" if fan is not None else "N/A"
            fan_item = QTableWidgetItem(fan_str)
            fan_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            util_progress = TableProgressBar()
            if util is not None:
                util_progress.setRange(0, 100)
                try:
                     util_int = int(float(util)) # Handle potential float like CPU %
                     util_progress.setValue(util_int)
                except (ValueError, TypeError):
                     self.logger.warning(f"Invalid utilization value for progress bar: {util}")
                     util_progress.setRange(0,0) # Show N/A
            else:
                util_progress.setRange(0, 0) 
                util_progress.setValue(0)

            mem_progress = TableProgressBar()
            if mem_used is not None and mem_total is not None and mem_total > 0:
                mem_progress.setRange(0, 100)
                try:
                     mem_percent = int((mem_used / mem_total) * 100)
                     mem_progress.setValue(mem_percent)
                     mem_progress.text = lambda mu=mem_used, mt=mem_total: f"{format_bytes(mu)} / {format_bytes(mt)}"
                except (ValueError, TypeError, ZeroDivisionError) as e:
                     self.logger.warning(f"Invalid memory value for progress bar: used={mem_used}, total={mem_total}, error={e}")
                     mem_progress.setRange(0,0) # Show N/A
                     mem_progress.text = lambda: "Error"
            else:
                mem_progress.setRange(0, 0)
                mem_progress.setValue(0)
                mem_progress.text = lambda: "N/A"

            self.gpu_table.setItem(row, 0, id_item)
            self.gpu_table.setItem(row, 1, model_item) 
            self.gpu_table.setItem(row, 2, temp_item)
            self.gpu_table.setCellWidget(row, 3, util_progress) 
            self.gpu_table.setCellWidget(row, 4, mem_progress) 
            self.gpu_table.setItem(row, 5, power_item)
            self.gpu_table.setItem(row, 6, fan_item)
            
        self.gpu_table.resizeRowsToContents() 

    def show_gpu_status_dialog(self):
        self.logger.info("GPU Status dialog requested (not implemented yet).")
        pass
        
    def show_settings_dialog(self):
        self.logger.info("Settings dialog requested (not implemented yet).")
        pass
