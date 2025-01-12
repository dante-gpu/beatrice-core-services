from PyQt6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QLabel
from PyQt6.QtCore import Qt

class MainWindow(QMainWindow):
    def __init__(self, gpu_handler, marketplace):
        super().__init__()
        self.gpu_handler = gpu_handler
        self.marketplace = marketplace
        
        self.setWindowTitle("DanteGPU Dashboard")
        self.setMinimumSize(800, 600)
        
        # Main widget and layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)
        
        # Label for GPU information
        self.gpu_info = QLabel("Loading GPU information...")
        layout.addWidget(self.gpu_info)
        
    def update_stats(self, stats):
        """Update GPU statistics"""
        if not stats:
            self.gpu_info.setText("No GPU information available")
            return
            
        info_text = f"Active GPUs: {stats.get('active_gpus', 0)}\n"
        info_text += f"Total Earnings: {stats.get('total_earnings', 0)} SOL"
        self.gpu_info.setText(info_text)
        
    def show_gpu_status_dialog(self):
        """Show GPU status dialog"""
        pass
        
    def show_settings_dialog(self):
        """Show settings dialog"""
        pass 