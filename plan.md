# Card Counter Migration Plan: Flask to PyQt6 Portable Application

## Table of Contents
1. [Application Overview](#1-application-overview)
2. [Migration Strategy](#2-migration-strategy)
3. [Portable Distribution Structure](#3-portable-distribution-structure)
4. [Core Functionality Migration](#4-core-functionality-migration)
5. [UI Design and Implementation](#5-ui-design-and-implementation)
6. [Background Processing](#6-background-processing)
7. [Portable-Specific Adjustments](#7-portable-specific-adjustments)
8. [Launch Scripts](#8-launch-scripts)
9. [Error Handling](#9-error-handling)
10. [Testing Strategy](#10-testing-strategy)
11. [Implementation Roadmap](#11-implementation-roadmap)
12. [Success Criteria](#12-success-criteria)

## 1. Application Overview

### Current Application: Card Counter
- **Type:** Flask web application for Pokémon card identification
- **Purpose:** Processes screenshots of card packs and identifies individual cards using image recognition
- **Current Users:** Web-based interface with CSV upload and image processing

### Key Components:
- **Database:** SQLite-based storage for screenshots, cards, and relationships
- **Image Processing:** OpenCV-based card identification from screenshots  
- **Web Interface:** Flask routes and templates using Pico CSS
- **Card Data:** Mapping of card codes to human-readable names

### Current Workflow:
1. User uploads CSV file containing pack metadata
2. User provides path to screenshot images
3. System processes images in background to identify cards
4. Results stored in database and displayed in web interface
5. Users browse, search, and filter cards through web UI

## 2. Migration Strategy

### Target Architecture: PyQt6 Portable Desktop Application
- **Platform:** Cross-platform (Windows, macOS, Linux)
- **Distribution:** Self-contained ZIP file
- **Dependencies:** Python 3.8+ with virtual environment
- **User Experience:** Native desktop application with no installation required

### Migration Approach:
1. **Preserve Core Functionality:** Maintain all existing features
2. **Improve User Experience:** Native desktop interface with better feedback
3. **Enhance Performance:** Optimized for local processing
4. **Simplify Deployment:** Single ZIP file distribution
5. **Maintain Data Portability:** Self-contained data storage

## 3. Portable Distribution Structure

```
cardcounter-portable/
├── main.py                  # Main entry point
├── app/                     # Application code
│   ├── __init__.py
│   ├── main_window.py
│   ├── database.py
│   ├── image_processing.py
│   ├── models.py
│   ├── workers.py
│   └── utils.py
├── resources/               # Application resources
│   ├── icons/               # Application icons
│   ├── styles/              # QSS stylesheets
│   ├── card_imgs/           # Card images (copied from original)
│   └── static/              # Static assets
├── data/                    # User data directory
│   ├── uploads/             # Uploads directory
│   ├── cardcounter.db       # SQLite database (empty or starter)
│   └── logs/                # Log files
├── requirements.txt         # Python dependencies
├── run.bat                  # Windows batch file
├── run.sh                   # Linux/macOS shell script
├── README.md                # Usage instructions
└── LICENSE                  # License information
```

## 4. Core Functionality Migration

### Database Module (`app/database.py`)
- **Preserve:** Existing SQLite database structure and queries
- **Modify:** Connection handling for desktop use (no thread-local storage)
- **Add:** Portable path resolution for database files
- **Enhance:** Error handling for file system issues

### Image Processing Module (`app/image_processing.py`)
- **Preserve:** Core OpenCV processing logic
- **Modify:** Add progress signal emission for Qt progress bars
- **Add:** Cancellation support for long-running operations
- **Enhance:** Memory management for large image sets

### Data Models (`app/models.py`)
```python
from PyQt6.QtCore import QAbstractTableModel, Qt, QModelIndex
from PyQt6.QtGui import QIcon

class CardModel(QAbstractTableModel):
    """Model for displaying cards in QTableView"""
    def __init__(self, data=None):
        super().__init__()
        self._data = data or []
        self._headers = ["Card", "Set", "Rarity", "Count", "Accounts"]
    
    def rowCount(self, parent=QModelIndex()) -> int:
        return len(self._data)
    
    def data(self, index, role=Qt.ItemDataRole):
        # Implementation for displaying card data
        pass
    
    def update_data(self, new_data):
        self.beginResetModel()
        self._data = new_data
        self.endResetModel()
```

## 5. UI Design and Implementation

### Main Window Structure
- **Menu Bar:** File (Import CSV, Process Screenshots, Exit), View, Help
- **Toolbar:** Quick access buttons for common actions
- **Central Widget:** Tab-based interface
  - **Dashboard Tab:** Overview statistics and quick actions
  - **Cards Tab:** Main card browsing interface
  - **Processing Tab:** Background task monitoring
  - **Search Tab:** Advanced search functionality
- **Status Bar:** Progress indicators and status messages

### Key UI Components
1. **Card Browser:**
   - QTableView with custom CardModel
   - Filter sidebar with QComboBox for sets, rarities, accounts
   - Search bar with real-time filtering
   - Card detail panel with image preview

2. **Import Dialogs:**
   - CSV Import Dialog: File path selection, validation, preview
   - Screenshot Processing Dialog: Directory selection, options, progress

3. **Processing Status:**
   - QListWidget for active/completed tasks
   - Detailed task view with progress bars
   - Log viewer for debugging

## 6. Background Processing

### Worker Pattern Implementation
```python
from PyQt6.QtCore import QRunnable, pyqtSignal

class ScreenshotProcessor(QRunnable):
    progress_signal = pyqtSignal(int, int)  # current, total
    status_signal = pyqtSignal(str)
    completed_signal = pyqtSignal(dict)
    error_signal = pyqtSignal(str)
    
    def __init__(self, screenshots_path: str, task_id: str):
        super().__init__()
        self.screenshots_path = screenshots_path
        self.task_id = task_id
        self._is_cancelled = False
    
    def run(self):
        # Process screenshots with progress updates
        pass
    
    def cancel(self):
        self._is_cancelled = True
```

### Thread Pool Management
- Use QThreadPool for background operations
- Limit to 4 concurrent workers to prevent resource exhaustion
- Implement proper cleanup on application exit

## 7. Portable-Specific Adjustments

### Path Handling
```python
def get_portable_path(*parts):
    """Get absolute path relative to application root"""
    if hasattr(sys, '_MEIPASS'):  # PyInstaller
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, *parts)
```

### Portable Settings
```python
class PortableSettings:
    def __init__(self):
        self.config_path = get_portable_path('data', 'config.ini')
        self.settings = QSettings(self.config_path, QSettings.Format.IniFormat)
    
    def load_settings(self):
        # Load from portable config file
        pass
    
    def save_settings(self):
        # Save to portable config file
        pass
```

### Data Directory Initialization
```python
def initialize_data_directory():
    """Ensure data directory structure exists"""
    data_dir = get_portable_path('data')
    os.makedirs(data_dir, exist_ok=True)
    os.makedirs(os.path.join(data_dir, 'uploads'), exist_ok=True)
    os.makedirs(os.path.join(data_dir, 'logs'), exist_ok=True)
    
    # Initialize database if it doesn't exist
    db_path = os.path.join(data_dir, 'cardcounter.db')
    if not os.path.exists(db_path):
        db = Database(db_path)
        db._initialize_database()
```

## 8. Launch Scripts

### Windows (`run.bat`)
```bat
@echo off
setlocal

:: Check Python installation
python --version >nul 2>&1
if errorlevel 1 (
    echo Error: Python is not installed or not in PATH
    echo Please install Python 3.8+ from https://www.python.org/downloads/
    pause
    exit /b 1
)

:: Check and install requirements
if not exist ".venv" (
    echo Setting up Python virtual environment...
    python -m venv .venv
    call .venv\Scripts\activate
    pip install --upgrade pip
    pip install -r requirements.txt
) else (
    call .venv\Scripts\activate
)

:: Run the application
python main.py

endlocal
```

### Linux/macOS (`run.sh`)
```bash
#!/bin/bash

# Check Python installation
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is not installed"
    echo "Please install Python 3.8+"
    exit 1
fi

# Check and install requirements
if [ ! -d ".venv" ]; then
    echo "Setting up Python virtual environment..."
    python3 -m venv .venv
    source .venv/bin/activate
    pip install --upgrade pip
    pip install -r requirements.txt
else
    source .venv/bin/activate
fi

# Run the application
python main.py
```

## 9. Error Handling

### Dependency Checking
```python
def check_dependencies():
    """Check if all required dependencies are available"""
    required_modules = ['PyQt6', 'cv2', 'numpy', 'pandas', 'PIL']
    
    missing = []
    for module in required_modules:
        try:
            __import__(module)
        except ImportError:
            missing.append(module)
    
    if missing:
        error_msg = f"Missing required dependencies: {', '.join(missing)}"
        error_msg += "\nPlease run: pip install -r requirements.txt"
        QMessageBox.critical(None, "Dependency Error", error_msg)
        return False
    
    return True
```

### Graceful Degradation
- Provide clear error messages for missing dependencies
- Offer automatic recovery options where possible
- Maintain application state on errors
- Log errors for debugging

## 10. Testing Strategy

### Test Cases
1. **Fresh Extraction:** Test on clean system with no prior installation
2. **Dependency Installation:** Verify automatic setup works
3. **Data Portability:** Test moving between different machines
4. **Path Handling:** Verify relative paths work correctly
5. **Error Recovery:** Test handling of missing dependencies

### Platform Testing
- **Windows:** 10/11 (32-bit and 64-bit)
- **macOS:** Intel & Apple Silicon
- **Linux:** Ubuntu, Fedora, Arch

### Regression Testing
- Verify all Flask features work in PyQt6 version
- Work with the user to test with real card data and images
- Performance comparison with original

## 11. Implementation Roadmap

### Phase 1: Foundation (Week 1)
- Set up PyQt6 project structure
- Create basic main window skeleton
- Implement database integration
- Test core functionality without UI

### Phase 2: Core Features (Week 2)
- Implement card browsing interface
- Create import dialogs (CSV and screenshots)
- Set up background processing with QThread
- Basic search and filtering

### Phase 3: Portable Features (Week 3)
- Implement portable path handling
- Create launch scripts
- Set up data directory management
- Test portable distribution

### Phase 4: Polish and Testing (Week 4)
- Refine UI/UX based on testing
- Implement proper error handling
- Add progress indicators and status updates
- Comprehensive testing with real data

## 12. Success Criteria

1. **Functional Parity:** All existing Flask features work in PyQt6 version
2. **Portability:** Application runs from ZIP file without installation
3. **Performance:** Desktop app performs at least as well as web version
4. **User Experience:** Intuitive desktop interface with proper feedback
5. **Reliability:** Robust error handling and recovery
6. **Cross-Platform:** Works on Windows, macOS, and Linux
7. **Self-Contained:** All dependencies included or automatically installed

## Advantages of Portable ZIP Approach

1. **No Installation Required:** Just extract and run
2. **Self-Contained:** All dependencies included or automatically installed
3. **Easy Distribution:** Single ZIP file for all platforms
4. **Portable Data:** User data stays with the application
5. **Simple Updates:** Replace ZIP file to update
6. **No Admin Rights Needed:** Works in user directories
7. **Easy Backup:** Copy the entire folder
8. **Cross-Platform:** Same distribution works everywhere

This plan provides a comprehensive roadmap for migrating the Flask web application to a portable PyQt6 desktop application that can be distributed as a single ZIP file, maintaining all existing functionality while providing a robust desktop experience.
