import sys
import logging
import platform
import asyncio
import threading 
import queue 
import webbrowser
import urllib.parse
from pathlib import Path
from PyQt6.QtWidgets import QApplication, QSystemTrayIcon, QMenu, QPushButton # Added QPushButton back
from PyQt6.QtGui import QIcon, QAction 
from PyQt6.QtCore import QTimer, pyqtSignal, QObject 

from ui.main_window import MainWindow
from ui.settings_dialog import SettingsDialog 
from ui.gpu_status_dialog import GPUStatusDialog 
from daemon.core import BeatriceDaemon
from daemon.services.gpu_monitor import GPUMonitorService
from core.marketplace import MarketplaceConnector 
from utils.config import ConfigManager
from utils.logger import setup_logger
# Import web server functions
from web.local_server import start_local_server, stop_local_server 

class Communicate(QObject):
    stats_update = pyqtSignal(dict) 
    wallet_update = pyqtSignal(str) # Signal for wallet address updates

class DanteGPU:
    def __init__(self):
        self.logger = setup_logger(__name__) 
        self.config = ConfigManager()
        
        log_level_str = self.config.get("log_level", "INFO").upper()
        log_level = getattr(logging, log_level_str, logging.INFO)
        logging.getLogger().setLevel(log_level) 
        for handler in logging.getLogger().handlers: 
             handler.setLevel(log_level)
        self.logger.info(f"Log level set to {log_level_str}")

        self.logger.info("DanteGPU starting up... 🚀")
        
        self.marketplace = MarketplaceConnector() 
        self.latest_stats: dict = {} 
        self.connected_wallet: Optional[str] = self.config.get("wallet_address") # Load initial wallet address

        self.app = QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False) 
        self.apply_stylesheet() 
        
        self.comm = Communicate()
        self.comm.stats_update.connect(self.handle_stats_update) 
        self.comm.wallet_update.connect(self.handle_wallet_update) # Connect wallet signal

        # --- Queues ---
        self.daemon_update_queue = queue.Queue() # For stats from daemon
        self.wallet_update_queue = queue.Queue() # For wallet address from web server

        # --- Init Daemon ---
        self.daemon = BeatriceDaemon()
        self.daemon.update_queue = self.daemon_update_queue # Pass the correct queue
        monitor_interval = self.config.get("monitoring_interval", 5) 
        self.gpu_monitor_service = GPUMonitorService(monitoring_interval=monitor_interval)
        self.daemon.register_service(self.gpu_monitor_service)
        
        # --- Init Web Server ---
        self.web_server_port = 51345 # Define port
        self.web_server_app_instance = None # To store the app instance for shutdown
        self.web_server_thread = None
        self.local_server_url = f"http://127.0.0.1:{self.web_server_port}/connect"

        # --- Init UI ---
        gpu_status_message = None 
        if not IS_MACOS and NVIDIA_AVAILABLE and not self.gpu_monitor_service.nvidia_initialized:
             gpu_status_message = "Warning: NVIDIA SMI failed to initialize. GPU monitoring may be limited."
             self.logger.warning(gpu_status_message)
        elif not IS_MACOS and not NVIDIA_AVAILABLE:
             gpu_status_message = "Info: NVIDIA library not found. GPU monitoring disabled."
        
        self.main_window = MainWindow(None, self.marketplace, gpu_status_message) 
        
        # Connect the button signal AFTER main_window is created
        # Ensure the button attribute exists before connecting
        if hasattr(self.main_window, 'connect_wallet_button'):
             self.main_window.connect_wallet_button.clicked.connect(self.open_wallet_connect_page)
        else:
             self.logger.error("Could not find connect_wallet_button on MainWindow to connect signal.")
             
        self.update_connect_button_state() # Update button based on loaded wallet address
        
        self.setup_system_tray()
        
        # --- Setup UI Update Timers ---
        self.stats_update_timer = QTimer() # Renamed from ui_update_timer
        self.stats_update_timer.timeout.connect(self.check_daemon_queue)
        self.stats_update_timer.start(500) 

        self.wallet_update_timer = QTimer() # Timer to check wallet queue
        self.wallet_update_timer.timeout.connect(self.check_wallet_queue)
        self.wallet_update_timer.start(600) # Check slightly less often

        # --- Start Background Threads ---
        self.daemon_thread = threading.Thread(target=self.run_daemon_async, daemon=True) 
        self.daemon_thread.start()
        
        self.web_server_thread = threading.Thread(target=self.run_web_server_async, daemon=True)
        self.web_server_thread.start()
        
        self.logger.info("DanteGPU initialization complete ✨")

    def run_daemon_async(self):
        self.logger.info("Starting BeatriceDaemon asyncio loop in background thread...")
        try:
            asyncio.run(self.daemon.start())
        except Exception as e:
            self.logger.critical(f"BeatriceDaemon thread crashed: {e}", exc_info=True)
        finally:
             self.logger.info("BeatriceDaemon asyncio loop finished.")
             
    def run_web_server_async(self):
        self.logger.info("Starting Local Web Server asyncio loop in background thread...")
        try:
            # Need to get the app instance back to stop it later
            # Modifying start_local_server or running differently might be needed
            # For now, run it directly, shutdown might be abrupt
            asyncio.run(start_local_server(port=self.web_server_port, update_queue=self.wallet_update_queue))
        except OSError:
             self.logger.error(f"Web server port {self.web_server_port} likely already in use.")
             # TODO: Communicate this error to the UI?
        except Exception as e:
            self.logger.critical(f"Local Web Server thread crashed: {e}", exc_info=True)
        finally:
             self.logger.info("Local Web Server asyncio loop finished.")

    def check_daemon_queue(self):
        try:
            stats_data = self.daemon_update_queue.get_nowait() 
            self.comm.stats_update.emit(stats_data) 
        except queue.Empty: 
            pass 
        except Exception as e:
            self.logger.error(f"Error checking daemon queue: {e}", exc_info=True)
            
    def check_wallet_queue(self):
        try:
            wallet_data = self.wallet_update_queue.get_nowait() 
            if wallet_data.get("type") == "wallet_update":
                 address = wallet_data.get("address")
                 if address:
                      self.comm.wallet_update.emit(address)
        except queue.Empty: 
            pass 
        except Exception as e:
            self.logger.error(f"Error checking wallet queue: {e}", exc_info=True)

    def handle_stats_update(self, stats_data: dict):
        self.logger.debug("Received stats update from daemon.")
        self.latest_stats = stats_data 
        self.main_window.update_stats(stats_data)
        self.update_tray_tooltip(stats_data) 
        
    def handle_wallet_update(self, address: str):
        self.logger.info(f"Received wallet address update: {address}")
        self.connected_wallet = address
        self.config.set("wallet_address", address) # Save the connected address
        self.update_connect_button_state() # Update button text/state
        # Optionally show a success message in UI
        
    def update_connect_button_state(self):
         if self.connected_wallet:
              # Display partial address
              short_address = f"{self.connected_wallet[:6]}...{self.connected_wallet[-4:]}"
              self.main_window.connect_wallet_button.setText(f"✅ Connected: {short_address}")
              self.main_window.connect_wallet_button.setToolTip(f"Connected Wallet: {self.connected_wallet}\nClick to disconnect (Not Implemented)")
              # self.main_window.connect_wallet_button.setEnabled(False) # Or allow disconnect?
         else:
              self.main_window.connect_wallet_button.setText("🔗 Connect Phantom")
              self.main_window.connect_wallet_button.setToolTip("Connect Phantom Wallet via Browser")
              self.main_window.connect_wallet_button.setEnabled(True)


    def apply_stylesheet(self):
        stylesheet = """
            QWidget { background-color: #2b2b2b; color: #f0f0f0; font-size: 11pt; }
            QMainWindow { background-color: #3c3f41; }
            QGroupBox { background-color: #3c3f41; border: 1px solid #555; border-radius: 5px; margin-top: 1ex; font-weight: bold; }
            QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left; padding: 0 3px; background-color: #555; color: #f0f0f0; border-radius: 3px; }
            QLabel { background-color: transparent; }
            QTableWidget { background-color: #3c3f41; border: 1px solid #555; gridline-color: #555; alternate-background-color: #45494c; }
            QHeaderView::section { background-color: #555; color: #f0f0f0; padding: 4px; border: 1px solid #3c3f41; font-weight: bold; }
            QTableWidget::item { padding: 5px; }
            QProgressBar { border: 1px solid #555; border-radius: 5px; text-align: center; background-color: #45494c; color: #f0f0f0; }
            QProgressBar::chunk { background-color: #007bff; width: 10px; margin: 0.5px; border-radius: 4px; }
            QToolTip { background-color: #2b2b2b; color: #f0f0f0; border: 1px solid #555; }
            QMenu { background-color: #3c3f41; border: 1px solid #555; }
            QMenu::item { padding: 5px 20px; }
            QMenu::item:selected { background-color: #007bff; }
            QMenu::separator { height: 1px; background: #555; margin-left: 10px; margin-right: 5px; }
            QPushButton { padding: 5px 10px; background-color: #007bff; color: white; border: none; border-radius: 3px; }
            QPushButton:hover { background-color: #0056b3; }
            QPushButton:disabled { background-color: #555; }
        """
        self.app.setStyleSheet(stylesheet)

    def setup_system_tray(self):
        self.tray = QSystemTrayIcon()
        icon_path = Path(__file__).resolve().parent / "resources" / "icons" / "tray_icon.png"
        if not icon_path.is_file():
             self.logger.warning(f"Tray icon not found at {icon_path}, attempting to use a default system icon.")
             fallback_icon = QIcon.fromTheme("dialog-information") 
             if not fallback_icon.isNull(): 
                 self.tray.setIcon(fallback_icon)
             else:
                  self.logger.error("Could not load default system tray icon.")
        else:
             self.tray.setIcon(QIcon(str(icon_path)))
        self.tray.setToolTip("DanteGPU - GPU Mining Done Right 🎮")
        menu = self.create_tray_menu()
        self.tray.setContextMenu(menu)
        self.tray.show()

    def create_tray_menu(self):
        menu = QMenu()
        dashboard_action = QAction("Dashboard 📊", self.app)
        dashboard_action.triggered.connect(self.main_window.show)
        menu.addAction(dashboard_action)
        status_action = QAction("GPU Status 🎮", self.app)
        status_action.triggered.connect(self.show_gpu_status)
        menu.addAction(status_action)
        settings_action = QAction("Settings ⚙️", self.app)
        settings_action.triggered.connect(self.show_settings)
        menu.addAction(settings_action)
        menu.addSeparator()
        exit_action = QAction("Exit 👋", self.app)
        exit_action.triggered.connect(self.cleanup_and_exit)
        menu.addAction(exit_action)
        return menu

    def update_tray_tooltip(self, stats):
        tooltip = "DanteGPU Status:\n"
        tooltip += f"GPUs Active: {stats.get('active_gpus', 'N/A')}\n" 
        tooltip += f"Total Earnings: {stats.get('total_earnings', 0.0):.4f} SOL" 
        self.tray.setToolTip(tooltip)

    def show_gpu_status(self):
        self.logger.info("Opening detailed GPU status dialog.")
        dialog = GPUStatusDialog(self.latest_stats, self.main_window) 
        dialog.exec() 
        self.logger.info("Detailed GPU status dialog closed.")

    def show_settings(self):
        self.logger.info("Opening settings dialog.")
        dialog = SettingsDialog(self.main_window) 
        if dialog.exec():
            self.logger.info("Settings dialog accepted (saved).")
            new_level_str = self.config.get("log_level", "INFO").upper()
            new_level = getattr(logging, new_level_str, logging.INFO)
            if logging.getLogger().level != new_level:
                 self.logger.info(f"Log level changed to {new_level_str}. Applying...")
                 logging.getLogger().setLevel(new_level)
                 for handler in logging.getLogger().handlers:
                      handler.setLevel(new_level)
            
            new_interval = self.config.get("monitoring_interval", 5)
            if self.gpu_monitor_service.monitoring_interval != new_interval:
                 self.logger.info(f"Monitoring interval changed to {new_interval} seconds. Applying...")
                 self.gpu_monitor_service.monitoring_interval = new_interval
        else:
            self.logger.info("Settings dialog cancelled.")
            
    # Renamed from connect_phantom
    def open_wallet_connect_page(self):
         self.logger.info(f"Opening wallet connection page in browser: {self.local_server_url}")
         try:
              webbrowser.open(self.local_server_url)
         except Exception as e:
              self.logger.error(f"Failed to open web browser: {e}", exc_info=True)
              # Show error message to user?

    def cleanup_and_exit(self):
        self.logger.info("Shutting down DanteGPU... 👋")
        
        # Stop Daemon Thread
        if self.daemon_thread and self.daemon_thread.is_alive():
             self.logger.info("Requesting daemon stop...")
             try:
                  loop = asyncio.get_event_loop_policy().get_event_loop() 
                  if loop.is_running():
                       future = asyncio.run_coroutine_threadsafe(self.daemon.stop(), loop)
                       self.logger.info("Daemon stop scheduled.")
                       try: future.result(timeout=7.0) 
                       except TimeoutError: self.logger.warning("Timeout waiting for daemon stop.")
                       except Exception as fe: self.logger.error(f"Error waiting for daemon stop future: {fe}")
                  else:
                       self.logger.warning("Daemon loop not running.")
                       if hasattr(self.daemon, '_is_running'): self.daemon._is_running = False 
             except RuntimeError as e:
                  self.logger.warning(f"Could not get loop to schedule daemon stop: {e}.")
                  if hasattr(self.daemon, '_is_running'): self.daemon._is_running = False
             except Exception as e:
                  self.logger.error(f"Error scheduling daemon stop: {e}")
                  if hasattr(self.daemon, '_is_running'): self.daemon._is_running = False 

        # Stop Web Server Thread (Needs improvement in local_server.py for graceful shutdown)
        if self.web_server_thread and self.web_server_thread.is_alive():
             self.logger.info("Stopping local web server (may be abrupt)...")
             # Currently no clean way to stop the asyncio.run() from another thread
             # The thread is daemonized, so it should exit when main app exits, but cleanup won't run.
             # TODO: Implement proper shutdown signal for web server if needed.
             pass 

        self.marketplace.disconnect() 
        self.tray.hide()
        self.app.quit() 

    def run(self):
        try:
            if self.config.get("autostart_minimized", False):
                self.logger.info("Starting minimized in system tray (Window hidden)")
            else:
                self.main_window.show()
            
            exit_code = self.app.exec()
            self.logger.info(f"Qt application event loop finished with exit code {exit_code}.")
            
            # Ensure background threads are joined after event loop finishes
            if self.daemon_thread and self.daemon_thread.is_alive():
                 self.logger.info("Waiting for daemon thread to exit...")
                 self.daemon_thread.join(timeout=5.0) 
                 if self.daemon_thread.is_alive(): self.logger.warning("Daemon thread did not exit cleanly.")
            if self.web_server_thread and self.web_server_thread.is_alive():
                 self.logger.info("Waiting for web server thread to exit...")
                 self.web_server_thread.join(timeout=2.0) # Shorter timeout for web server
                 if self.web_server_thread.is_alive(): self.logger.warning("Web server thread did not exit cleanly.")
                 
            return exit_code
            
        except Exception as e:
            self.logger.critical(f"Application crashed: {e}", exc_info=True)
            # Ensure cleanup is attempted even on crash
            self.cleanup_and_exit() 
            return 1

IS_MACOS = platform.system() == "Darwin"
NVIDIA_AVAILABLE = False
if not IS_MACOS:
    try:
        import nvidia_smi
        NVIDIA_AVAILABLE = True
    except ImportError:
        pass 
    except Exception:
         pass 

if __name__ == "__main__":
    dante_gpu = DanteGPU()
    sys.exit(dante_gpu.run())
