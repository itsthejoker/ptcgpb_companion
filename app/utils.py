"""
Card Counter Utilities

Utility functions for the Card Counter application including:
- Dependency checking
- Path handling
- Data directory management
- Error handling
"""

import os
import logging
import tomllib
import json
import uuid
from datetime import datetime

from PyQt6.QtWidgets import QMessageBox
from PyQt6.QtCore import QSettings

from settings import BASE_DIR

logger = logging.getLogger(__name__)

DEFAULT_SETTINGS = {
    "General/csv_import_path": "",
    "General/screenshots_dir": "",
    "General/language": "",
    "Screenshots/watch_directory": True,
    "Screenshots/check_interval": 5,
    "Logging/enabled": False,
    "Debug/max_cores": 0,
}

# Order in which sections should be displayed in the Preferences dialog
SECTION_ORDER = ["General", "Screenshots", "Logging", "Debug"]


def get_app_version():
    """
    Get the application version from pyproject.toml or package metadata

    Returns:
        str: Version string
    """
    # Try getting version from package metadata first
    try:
        import importlib.metadata

        return importlib.metadata.version("ptcgpb-companion")
    except Exception:
        pass

    # Fallback to pyproject.toml
    try:
        pyproject_path = BASE_DIR / "pyproject.toml"
        if os.path.exists(pyproject_path):
            with open(pyproject_path, "rb") as f:
                data = tomllib.load(f)
                return data.get("project", {}).get("version", "unknown")
        return "unknown"
    except Exception as e:
        logger.error(f"Failed to load version from pyproject.toml: {e}")
        return "unknown"


def initialize_data_directory():
    """
    Ensure data directory structure exists

    Creates the following structure:
    - data/
      - logs/
      - cardcounter.db (if doesn't exist)
    """
    data_dir = BASE_DIR / "data"
    os.makedirs(data_dir, exist_ok=True)
    os.makedirs(data_dir / "logs", exist_ok=True)

    # Initialize settings and ensure defaults are set
    PortableSettings()


def check_dependencies():
    """
    Check if all required dependencies are available

    Returns:
        bool: True if all dependencies are available, False otherwise
    """
    required_modules = ["PyQt6", "cv2", "numpy", "PIL"]

    missing = []
    for module in required_modules:
        try:
            __import__(module)
        except ImportError:
            missing.append(module)

    if missing:
        error_msg = f"Missing required dependencies: {', '.join(missing)}"
        error_msg += "\nPlease run: pip install -r requirements.txt"
        logger.error(error_msg)
        return False

    logger.info("All dependencies are available")
    return True


def record_traded_card(account: str, card_code: str):
    """
    Record a removed card in removed_cards.json

    Args:
        account: Account name
        card_code: Card code
    """
    try:
        file_path = BASE_DIR / "data" / "removed_cards.json"
        removed_cards = []

        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as f:
                try:
                    removed_cards = json.load(f)
                except json.JSONDecodeError:
                    logger.warning(f"Could not decode {file_path}, starting fresh")

        removed_cards.append({"account": account, "card_code": card_code})

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(removed_cards, f, indent=4)

        logger.info(f"Recorded removal: {card_code} from {account}")
    except Exception as e:
        logger.error(f"Failed to record removed card: {e}")


def get_traded_cards() -> list:
    """
    Get the list of removed cards from removed_cards.json

    Returns:
        list: List of dicts with account and card_code
    """
    file_path = BASE_DIR / "data" / "removed_cards.json"
    if not os.path.exists(file_path):
        return []

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to read removed cards: {e}")
        return []


def clear_traded_cards():
    """
    Clear the removed_cards.json file
    """
    file_path = BASE_DIR / "data" / "removed_cards.json"
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
            logger.info(f"Cleared {file_path}")
        except Exception as e:
            logger.error(f"Failed to clear removed cards: {e}")


def extract_screenshot_date(filename: str):
    """
    Extract date from screenshot filename.

    Expected format starts with YYYYMMDD, optionally followed by time.
    """
    if not filename:
        return None

    base_name = os.path.basename(filename)
    if len(base_name) < 8:
        return None

    date_part = base_name[:8]
    if not date_part.isdigit():
        return None

    try:
        return datetime.strptime(date_part, "%Y%m%d").date()
    except ValueError:
        return None


def _get_skipped_screenshots_path():
    return BASE_DIR / "data" / "skipped_screenshots.json"


def load_skipped_screenshots():
    """
    Load skipped screenshots list and count.
    """
    file_path = _get_skipped_screenshots_path()
    if not os.path.exists(file_path):
        return set(), 0

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            payload = json.load(f)
    except Exception as e:
        logger.error(f"Failed to read skipped screenshots: {e}")
        return set(), 0

    if isinstance(payload, list):
        files = payload
        count = len(payload)
    elif isinstance(payload, dict):
        files = payload.get("files", [])
        count = payload.get("count", len(files))
    else:
        return set(), 0

    try:
        count = int(count)
    except (TypeError, ValueError):
        count = len(files)

    if count < len(files):
        count = len(files)

    return set(files), count


def record_skipped_screenshots(filenames):
    """
    Record skipped screenshot filenames and return (newly_added, total_count).
    """
    if not filenames:
        return 0, load_skipped_screenshots()[1]

    file_path = _get_skipped_screenshots_path()
    os.makedirs(os.path.dirname(file_path), exist_ok=True)

    existing_files, existing_count = load_skipped_screenshots()
    before_count = len(existing_files)
    existing_files.update(filenames)
    added_count = len(existing_files) - before_count
    total_count = existing_count + added_count

    payload = {
        "files": sorted(existing_files),
        "count": total_count,
    }

    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=4)
    except Exception as e:
        logger.error(f"Failed to write skipped screenshots: {e}")

    return added_count, total_count


class PortableSettings:
    """
    Portable settings management using QSettings

    Stores settings in a portable INI file within the data directory.
    """

    def __init__(self):
        config_path = BASE_DIR / "data" / "config.ini"
        # Ensure directory exists
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        self.settings = QSettings(str(config_path), QSettings.Format.IniFormat)
        self._initialize_defaults()

    def _initialize_defaults(self):
        """Ensure all default settings exist"""
        for key, value in DEFAULT_SETTINGS.items():
            if self.settings.value(key) is None:
                self.settings.setValue(key, value)
        self.settings.sync()

    def load_settings(self):
        """Load settings from portable config file"""
        self.settings.sync()

    def save_settings(self):
        """Save settings to portable config file"""
        self.settings.sync()

    def get_setting(self, key, default=None):
        """Get a specific setting"""
        # If no default provided, try to get it from DEFAULT_SETTINGS
        if default is None and key in DEFAULT_SETTINGS:
            default = DEFAULT_SETTINGS[key]

        value = self.settings.value(key, default)

        # QSettings often returns strings for booleans/integers from INI files
        # We want to cast them if we know the expected type from the default
        if isinstance(default, bool) and not isinstance(value, bool):
            return str(value).lower() == "true"
        if isinstance(default, int) and not isinstance(value, int):
            try:
                return int(value)
            except (ValueError, TypeError):
                return default

        return value

    def set_setting(self, key, value):
        """Set a specific setting"""
        self.settings.setValue(key, value)
        self.settings.sync()


def show_error_message(title, message):
    """
    Show an error message dialog

    Args:
        title: Dialog title
        message: Error message
    """
    msg_box = QMessageBox()
    msg_box.setIcon(QMessageBox.Icon.Critical)
    msg_box.setWindowTitle(title)
    msg_box.setText(message)
    msg_box.exec()


def show_info_message(title, message):
    """
    Show an information message dialog

    Args:
        title: Dialog title
        message: Information message
    """
    msg_box = QMessageBox()
    msg_box.setIcon(QMessageBox.Icon.Information)
    msg_box.setWindowTitle(title)
    msg_box.setText(message)
    msg_box.exec()


def get_task_id() -> str:
    return str(uuid.uuid4()).split("-")[0]


def clean_card_name(full_name: str) -> str:
    """
    Remove the rarity suffix from a card name (e.g., 'Bulbasaur (1D)' -> 'Bulbasaur').
    """
    import re

    if not full_name:
        return ""
    return re.sub(r"\s*\([^)]+\)$", "", full_name).strip()


def find_update_payload(extract_dir: str):
    """Locate the _internal directory and exe within an extracted update folder."""
    if not extract_dir or not os.path.isdir(extract_dir):
        return None

    internal_dirs = []
    exe_files = []

    for root, dirs, files in os.walk(extract_dir):
        for dirname in dirs:
            if dirname.lower() == "_internal":
                internal_dirs.append(os.path.join(root, dirname))
        for filename in files:
            if filename.lower().endswith(".exe"):
                exe_files.append(os.path.join(root, filename))

    if not internal_dirs or not exe_files:
        return None

    for internal_dir in internal_dirs:
        parent_dir = os.path.dirname(internal_dir)
        for exe_path in exe_files:
            if os.path.dirname(exe_path) == parent_dir:
                return internal_dir, exe_path

    return internal_dirs[0], exe_files[0]
