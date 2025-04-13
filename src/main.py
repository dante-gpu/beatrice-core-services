import sys
import logging
from pathlib import Path
from PyQt6.QtWidgets import QApplication, QSystemTrayIcon, QMenu
from PyQt6.QtGui import QIcon, QAction
from PyQt6.QtCore import QTimer

from ui.main_window import MainWindow
from core.gpu_handler import GPUHandler
from core.marketplace import MarketplaceConnector
from utils.config import ConfigManager
from utils.logger import setup_logger

"""
DanteGPU Main Application fr fr 🔥
---------------------------------

The main entry point that brings all the drip together.
System tray integration + GPU monitoring + Marketplace vibes

No cap features:
- System tray that stays humble
- Auto-start on boot (optional)
- Real-time GPU stats
- Marketplace integration
- Config that remembers your preferences
"""

class DanteGPU:
    def __init__(self):
        self.logger = setup_logger(__name__)
        self.logger.info("DanteGPU starting up... 🚀")
        
        # Init core components
        self.config = ConfigManager()
        self.gpu_handler = GPUHandler()
        self.marketplace = MarketplaceConnector()
        
        # Init UI
        self.app = QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False)  # Keep running in system tray
        
        # Load main window
        self.main_window = MainWindow(self.gpu_handler, self.marketplace)
        
        # Setup system tray
        self.setup_system_tray()
        
        # Setup auto-monitoring
        self.monitoring_timer = QTimer()
        self.monitoring_timer.timeout.connect(self.update_stats)
        
        self.logger.info("DanteGPU initialization complete ✨")

    def setup_system_tray(self):
        """Setup that system tray drip"""
        self.tray = QSystemTrayIcon()
        icon_path = Path(__file__).parent / "resources" / "icons" / "tray_icon.png"
        self.tray.setIcon(QIcon(str(icon_path)))
        self.tray.setToolTip("DanteGPU - GPU Mining Done Right 🎮")
        
        # Create tray menu
        menu = self.create_tray_menu()
        self.tray.setContextMenu(menu)
        self.tray.show()

    def create_tray_menu(self):
        """Create that bussin tray menu fr fr"""
        
        menu = QMenu()
        
        # Dashboard action
        dashboard_action = QAction("Dashboard 📊", self.app)
        dashboard_action.triggered.connect(self.main_window.show)
        menu.addAction(dashboard_action)
        
        # GPU Status action
        status_action = QAction("GPU Status 🎮", self.app)
        status_action.triggered.connect(self.show_gpu_status)
        menu.addAction(status_action)
        
        # Settings action
        settings_action = QAction("Settings ⚙️", self.app)
        settings_action.triggered.connect(self.show_settings)
        menu.addAction(settings_action)
        
        menu.addSeparator()
        
        # Exit action
        exit_action = QAction("Exit 👋", self.app)
        exit_action.triggered.connect(self.cleanup_and_exit)
        menu.addAction(exit_action)
        
        return menu

    def update_stats(self):
        """Update them GPU stats fr fr"""
        try:
            stats = self.gpu_handler.get_current_stats()
            self.main_window.update_stats(stats)
            self.update_tray_tooltip(stats)
        except Exception as e:
            self.logger.error(f"Failed to update stats: {str(e)}")

    def update_tray_tooltip(self, stats):
        """Keep that tray tooltip fresh with latest stats"""
        tooltip = "DanteGPU Status:\n"
        tooltip += f"GPUs Active: {stats['active_gpus']}\n"
        tooltip += f"Total Earnings: {stats['total_earnings']} SOL"
        self.tray.setToolTip(tooltip)

    def show_gpu_status(self):
        """Show them GPU stats in a quick view"""
        self.main_window.show_gpu_status_dialog()

    def show_settings(self):
        """Pop them settings fr fr"""
        self.main_window.show_settings_dialog()

    def cleanup_and_exit(self):
        """Exit but make it clean"""
        self.logger.info("Shutting down DanteGPU... 👋")
        self.gpu_handler.cleanup()
        self.marketplace.disconnect()
        self.tray.hide()
        self.app.quit()

    def run(self):
        """Run this bad boy"""
        try:
            # Start GPU monitoring
            self.monitoring_timer.start(1000)  # Update every second
            
            # If autostart is enabled, minimize to tray
            if self.config.get("autostart_minimized", False):
                self.logger.info("Starting minimized in system tray")
            else:
                self.main_window.show()
            
            # Start the app
            return self.app.exec()
            
        except Exception as e:
            self.logger.error(f"Application crashed: {str(e)}")
            return 1

if __name__ == "__main__":
    dante_gpu = DanteGPU()
    sys.exit(dante_gpu.run())
