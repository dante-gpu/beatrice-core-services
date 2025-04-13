import sys
import os
import plistlib
import logging
from pathlib import Path

APP_LABEL = "com.dantegpu.beatrice.login" 
LAUNCH_AGENTS_DIR = Path.home() / "Library" / "LaunchAgents"
PLIST_FILENAME = f"{APP_LABEL}.plist"
PLIST_PATH = LAUNCH_AGENTS_DIR / PLIST_FILENAME

logger = logging.getLogger(__name__)

def _get_paths():
    python_executable = sys.executable 
    
    try:
        project_root = Path(__file__).resolve().parent.parent.parent 
        main_script_path = project_root / "src" / "main.py"
        if not main_script_path.is_file():
             logger.warning("Could not automatically determine main.py path relative to autostart_macos.py. Trying another method.")
             main_script_path = Path(sys.argv[0]).resolve() 
             project_root = main_script_path.parent.parent 
             
        if not Path(python_executable).is_file():
             logger.error(f"Python executable path seems invalid: {python_executable}")
             return None, None, None
        if not main_script_path.is_file():
             logger.error(f"Main script path seems invalid: {main_script_path}")
             return None, None, None
        if not project_root.is_dir():
             logger.error(f"Project root path seems invalid: {project_root}")
             return None, None, None

        logger.debug(f"Autostart paths determined: Python='{python_executable}', Script='{main_script_path}', Root='{project_root}'")
        return python_executable, str(main_script_path), str(project_root)

    except Exception as e:
        logger.error(f"Error determining paths for autostart: {e}")
        return None, None, None


def enable_autostart() -> bool:
    logger.info("Enabling autostart on login...")
    python_executable, main_script_path, project_root = _get_paths()

    if not all([python_executable, main_script_path, project_root]):
        logger.error("Could not determine necessary paths. Autostart NOT enabled.")
        return False

    plist_data = {
        "Label": APP_LABEL,
        "ProgramArguments": [
            python_executable,
            main_script_path
        ],
        "RunAtLoad": True, 
        "WorkingDirectory": project_root, 
    }

    try:
        LAUNCH_AGENTS_DIR.mkdir(parents=True, exist_ok=True)
        
        with open(PLIST_PATH, 'wb') as fp:
            plistlib.dump(plist_data, fp)
            
        logger.info(f"Autostart enabled. Plist file created at: {PLIST_PATH}")
        return True
    except Exception as e:
        logger.error(f"Failed to create or write plist file for autostart: {e}")
        return False

def disable_autostart() -> bool:
    logger.info("Disabling autostart on login...")
    try:
        if PLIST_PATH.exists():
            PLIST_PATH.unlink()
            logger.info(f"Autostart disabled. Plist file removed: {PLIST_PATH}")
            return True
        else:
            logger.info("Autostart plist file does not exist. Nothing to disable.")
            return True 
    except Exception as e:
        logger.error(f"Failed to remove plist file for autostart: {e}")
        return False

def is_autostart_enabled() -> bool:
    return PLIST_PATH.exists()
