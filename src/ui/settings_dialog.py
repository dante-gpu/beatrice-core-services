import logging
import platform 
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QFormLayout, QComboBox, 
                             QCheckBox, QDialogButtonBox, QLabel, QWidget,
                             QMessageBox, QSpinBox, QLineEdit) # Import QLineEdit
from PyQt6.QtCore import Qt

try:
    from ..utils.config import ConfigManager
except ImportError:
    from utils.config import ConfigManager

IS_MACOS = platform.system() == "Darwin"
if IS_MACOS:
    try:
        from ..utils.autostart_macos import enable_autostart, disable_autostart, is_autostart_enabled
        AUTOSTART_SUPPORTED = True
    except ImportError:
        try:
             from utils.autostart_macos import enable_autostart, disable_autostart, is_autostart_enabled
             AUTOSTART_SUPPORTED = True
        except ImportError:
             logging.getLogger(__name__).error("Could not import autostart_macos functions.", exc_info=True)
             AUTOSTART_SUPPORTED = False
else:
    AUTOSTART_SUPPORTED = False
    def enable_autostart(): return False
    def disable_autostart(): return True
    def is_autostart_enabled(): return False


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.logger = logging.getLogger(__name__)
        self.config = ConfigManager() 

        self.setWindowTitle("Settings")
        self.setMinimumWidth(400)

        main_layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        self.log_level_combo = QComboBox()
        self.log_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        self.log_level_combo.addItems(self.log_levels)
        
        self.interval_spinbox = QSpinBox()
        self.interval_spinbox.setRange(1, 300) 
        self.interval_spinbox.setSuffix(" seconds")

        # Wallet Address Input
        self.wallet_address_input = QLineEdit()
        self.wallet_address_input.setPlaceholderText("Enter your Solana wallet address (e.g., Phantom)")
        
        self.autostart_macos_label = QLabel("Autostart on Login (macOS):")
        self.autostart_macos_check = QCheckBox("Enable application launch on user login")
        
        form_layout.addRow(QLabel("Console Log Level:"), self.log_level_combo)
        form_layout.addRow(QLabel("Monitoring Interval:"), self.interval_spinbox)
        form_layout.addRow(QLabel("Solana Wallet Address:"), self.wallet_address_input)
        
        if AUTOSTART_SUPPORTED:
             form_layout.addRow(self.autostart_macos_label, self.autostart_macos_check)
        else:
             self.autostart_macos_label.setVisible(False)
             self.autostart_macos_check.setVisible(False)

        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.accept) 
        button_box.rejected.connect(self.reject) 

        main_layout.addLayout(form_layout)
        main_layout.addWidget(button_box)

        self.load_settings()
        self.logger.debug("SettingsDialog initialized.")

    def load_settings(self):
        try:
            current_log_level = self.config.get("log_level", "INFO").upper()
            if current_log_level in self.log_levels:
                self.log_level_combo.setCurrentText(current_log_level)
            else:
                 self.logger.warning(f"Invalid log_level '{current_log_level}' in config, defaulting to INFO.")
                 self.log_level_combo.setCurrentText("INFO")
            
            current_interval = self.config.get("monitoring_interval", 5)
            self.interval_spinbox.setValue(int(current_interval))
            
            # Load Wallet Address
            current_wallet = self.config.get("wallet_address", "")
            self.wallet_address_input.setText(current_wallet)

            if AUTOSTART_SUPPORTED:
                current_autostart_state = is_autostart_enabled() 
                self.autostart_macos_check.setChecked(current_autostart_state)
                self.logger.debug(f"Loaded macOS autostart state: {current_autostart_state}")
            
            self.logger.debug("Settings loaded into dialog.")

        except Exception as e:
            self.logger.error(f"Error loading settings into dialog: {e}")


    def save_settings(self) -> bool:
        config_save_success = False
        try:
            new_log_level = self.log_level_combo.currentText()
            new_interval = self.interval_spinbox.value()
            new_wallet_address = self.wallet_address_input.text().strip() # Get text and strip whitespace
            new_autostart_minimized_config = self.autostart_macos_check.isChecked() if AUTOSTART_SUPPORTED else False 

            # Optional: Add basic validation for Solana address format? 
            # For now, just save whatever user enters.
            # A simple check could be length, e.g., 32-44 chars, starts with specific chars?
            # if new_wallet_address and not (32 <= len(new_wallet_address) <= 44):
            #     QMessageBox.warning(self, "Invalid Address", "Wallet address seems invalid. Please check.")
            #     return False # Prevent saving if validation fails

            self.config.set("log_level", new_log_level)
            self.config.set("monitoring_interval", new_interval)
            self.config.set("wallet_address", new_wallet_address) # Save wallet address
            self.config.set("autostart_minimized", new_autostart_minimized_config) 
            
            self.logger.info(f"Config settings saved: LogLevel={new_log_level}, Interval={new_interval}, Wallet={new_wallet_address}, AutostartMinimized={new_autostart_minimized_config}")
            config_save_success = True
        except Exception as e:
            self.logger.error(f"Error saving config settings: {e}")
            QMessageBox.critical(self, "Save Error", f"Failed to save config settings: {e}")
            return False 

        autostart_action_success = True 
        if AUTOSTART_SUPPORTED:
            autostart_action_success = False 
            should_be_enabled = self.autostart_macos_check.isChecked()
            currently_enabled = is_autostart_enabled()
            
            operation_needed = should_be_enabled != currently_enabled
            operation_result = True 

            if operation_needed:
                if should_be_enabled:
                    self.logger.info("Attempting to enable macOS autostart...")
                    operation_result = enable_autostart()
                    if not operation_result:
                         QMessageBox.critical(self, "Autostart Error", "Failed to enable autostart. Check logs and permissions for ~/Library/LaunchAgents.")
                else:
                    self.logger.info("Attempting to disable macOS autostart...")
                    operation_result = disable_autostart()
                    if not operation_result:
                         QMessageBox.critical(self, "Autostart Error", "Failed to disable autostart. Check logs and permissions for ~/Library/LaunchAgents.")
            
            if operation_result:
                 self.logger.info(f"macOS autostart state successfully set to: {should_be_enabled}")
                 autostart_action_success = True
            else:
                 self.logger.error("Failed to change macOS autostart state.")

        return config_save_success and autostart_action_success

    def accept(self):
        if self.save_settings():
            super().accept() 
        else:
            self.logger.error("Dialog accept cancelled due to save failure.")
            QMessageBox.critical(self, "Save Error", "Failed to save settings. Please check logs for details.")
