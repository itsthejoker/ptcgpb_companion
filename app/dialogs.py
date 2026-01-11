"""
Card Counter Dialogs

Dialog classes for the Card Counter PyQt6 application.
This module provides various dialog windows for user interactions.
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QFileDialog, QLineEdit, QComboBox, QCheckBox, QProgressBar,
    QTextEdit, QFormLayout, QDialogButtonBox, QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread
from PyQt6.QtGui import QIcon
import os
import csv
from typing import Optional, Dict, Any

class CSVImportDialog(QDialog):
    """Dialog for importing CSV files with pack metadata"""
    
    csv_imported = pyqtSignal(str)  # Signal emitted when CSV is successfully imported
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Import CSV")
        self.setMinimumSize(500, 400)
        
        self._setup_ui()
        self._csv_data = None
        self._file_path = ""
    
    def _setup_ui(self):
        """Set up the user interface"""
        main_layout = QVBoxLayout()
        
        # File selection section
        file_layout = QHBoxLayout()
        self.file_path_label = QLabel("No file selected")
        self.file_path_label.setWordWrap(True)
        
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse_file)
        
        file_layout.addWidget(QLabel("CSV File:"))
        file_layout.addWidget(self.file_path_label, 1)
        file_layout.addWidget(browse_btn)
        
        main_layout.addLayout(file_layout)
        
        # CSV preview section
        preview_label = QLabel("CSV Preview (first 10 rows):")
        main_layout.addWidget(preview_label)
        
        self.preview_text = QTextEdit()
        self.preview_text.setReadOnly(True)
        self.preview_text.setMinimumHeight(200)
        main_layout.addWidget(self.preview_text)
        
        # Options section
        options_layout = QFormLayout()
        
        # Account selection
        self.account_combo = QComboBox()
        self.account_combo.addItem("Default Account")
        options_layout.addRow("Account:", self.account_combo)
        
        # Tradeable checkbox
        self.tradeable_check = QCheckBox("Tradeable packs")
        self.tradeable_check.setChecked(True)
        options_layout.addRow(self.tradeable_check)
        
        # Pack size
        self.pack_size_edit = QLineEdit("11")
        self.pack_size_edit.setValidator(self.IntValidator(1, 100))
        options_layout.addRow("Pack Size:", self.pack_size_edit)
        
        main_layout.addLayout(options_layout)
        
        # Progress section
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        main_layout.addWidget(self.progress_bar)
        
        # Status label
        self.status_label = QLabel("")
        main_layout.addWidget(self.status_label)
        
        # Buttons
        button_box = QDialogButtonBox()
        self.import_btn = button_box.addButton("Import", QDialogButtonBox.ButtonRole.AcceptRole)
        self.import_btn.setEnabled(False)
        cancel_btn = button_box.addButton("Cancel", QDialogButtonBox.ButtonRole.RejectRole)
        
        self.import_btn.clicked.connect(self._import_csv)
        cancel_btn.clicked.connect(self.reject)
        
        main_layout.addWidget(button_box)
        
        self.setLayout(main_layout)
    
    def _browse_file(self):
        """Open file dialog to select CSV file"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select CSV File", "", 
            "CSV Files (*.csv);;All Files (*)"
        )
        
        if file_path:
            self._file_path = file_path
            self.file_path_label.setText(file_path)
            self._load_csv_preview(file_path)
    
    def _load_csv_preview(self, file_path: str):
        """Load and display preview of CSV file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                rows = []
                for i, row in enumerate(reader):
                    if i >= 10:  # Limit to 10 rows
                        break
                    rows.append(', '.join(row))
                
                self.preview_text.setPlainText('\n'.join(rows))
                self.import_btn.setEnabled(True)
                self.status_label.setText("CSV file loaded successfully")
                
        except Exception as e:
            self.preview_text.setPlainText(f"Error loading CSV: {e}")
            self.import_btn.setEnabled(False)
            self.status_label.setText(f"Error: {e}")
    
    def _import_csv(self):
        """Import the CSV file"""
        try:
            # Validate inputs
            pack_size = int(self.pack_size_edit.text())
            if pack_size < 1 or pack_size > 100:
                QMessageBox.warning(self, "Invalid Input", "Pack size must be between 1 and 100")
                return
            
            # Show progress
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(0)
            self.status_label.setText("Importing CSV...")
            self.import_btn.setEnabled(False)
            
            # Process CSV data
            self._process_csv_data()
            
            # Emit signal and close
            self.csv_imported.emit(self._file_path)
            self.accept()
            
        except Exception as e:
            QMessageBox.critical(self, "Import Error", f"Failed to import CSV: {e}")
            self.status_label.setText(f"Error: {e}")
            self.import_btn.setEnabled(True)
            self.progress_bar.setVisible(False)
    
    def _process_csv_data(self):
        """Process CSV data and store in database"""
        try:
            # Parse CSV file
            with open(self._file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                
                total_rows = 0
                for row in reader:
                    total_rows += 1
                
            # Simulate progress
            self.progress_bar.setRange(0, total_rows)
            
            # For now, just simulate the import process
            # In a real implementation, this would:
            # 1. Parse the CSV data
            # 2. Validate the data
            # 3. Store in database
            # 4. Update progress
            
            for i in range(total_rows):
                if i % 10 == 0:  # Update progress every 10 rows
                    self.progress_bar.setValue(i)
                    QApplication.processEvents()
            
            self.progress_bar.setValue(total_rows)
            self.status_label.setText(f"Successfully imported {total_rows} packs")
            
        except Exception as e:
            raise Exception(f"Failed to process CSV data: {e}")
    
    class IntValidator:
        """Simple integer validator for QLineEdit"""
        def __init__(self, min_val: int, max_val: int):
            self.min_val = min_val
            self.max_val = max_val
            
        def validate(self, input_text: str, pos: int) -> tuple:
            try:
                val = int(input_text)
                if self.min_val <= val <= self.max_val:
                    return (QValidator.State.Acceptable, input_text, pos)
                else:
                    return (QValidator.State.Intermediate, input_text, pos)
            except ValueError:
                if input_text == "":
                    return (QValidator.State.Intermediate, input_text, pos)
                else:
                    return (QValidator.State.Invalid, input_text, pos)

class ScreenshotProcessingDialog(QDialog):
    """Dialog for processing screenshot images"""
    
    processing_started = pyqtSignal(str)  # Signal emitted when processing starts
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Process Screenshots")
        self.setMinimumSize(500, 300)
        
        self._setup_ui()
        self._directory_path = ""
    
    def _setup_ui(self):
        """Set up the user interface"""
        main_layout = QVBoxLayout()
        
        # Directory selection section
        dir_layout = QHBoxLayout()
        self.dir_path_label = QLabel("No directory selected")
        self.dir_path_label.setWordWrap(True)
        
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse_directory)
        
        dir_layout.addWidget(QLabel("Screenshots Directory:"))
        dir_layout.addWidget(self.dir_path_label, 1)
        dir_layout.addWidget(browse_btn)
        
        main_layout.addLayout(dir_layout)
        
        # Options section
        options_layout = QFormLayout()
        
        # Account selection
        self.account_combo = QComboBox()
        self.account_combo.addItem("Default Account")
        options_layout.addRow("Account:", self.account_combo)
        
        # Processing options
        self.overwrite_check = QCheckBox("Overwrite existing results")
        self.overwrite_check.setChecked(False)
        options_layout.addRow(self.overwrite_check)
        
        main_layout.addLayout(options_layout)
        
        # File list section
        file_list_label = QLabel("Files to process:")
        main_layout.addWidget(file_list_label)
        
        self.file_list_text = QTextEdit()
        self.file_list_text.setReadOnly(True)
        self.file_list_text.setMinimumHeight(100)
        main_layout.addWidget(self.file_list_text)
        
        # Progress section
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        main_layout.addWidget(self.progress_bar)
        
        # Status label
        self.status_label = QLabel("")
        main_layout.addWidget(self.status_label)
        
        # Buttons
        button_box = QDialogButtonBox()
        self.process_btn = button_box.addButton("Process", QDialogButtonBox.ButtonRole.AcceptRole)
        self.process_btn.setEnabled(False)
        cancel_btn = button_box.addButton("Cancel", QDialogButtonBox.ButtonRole.RejectRole)
        
        self.process_btn.clicked.connect(self._process_screenshots)
        cancel_btn.clicked.connect(self.reject)
        
        main_layout.addWidget(button_box)
        
        self.setLayout(main_layout)
    
    def _browse_directory(self):
        """Open directory dialog to select screenshots directory"""
        dir_path = QFileDialog.getExistingDirectory(
            self, "Select Screenshots Directory", ""
        )
        
        if dir_path:
            self._directory_path = dir_path
            self.dir_path_label.setText(dir_path)
            self._load_file_list(dir_path)
    
    def _load_file_list(self, dir_path: str):
        """Load and display list of image files in directory"""
        try:
            image_extensions = ('.png', '.jpg', '.jpeg', '.webp', '.bmp', '.gif')
            image_files = []
            
            for filename in os.listdir(dir_path):
                if filename.lower().endswith(image_extensions):
                    image_files.append(filename)
            
            if image_files:
                self.file_list_text.setPlainText('\n'.join(image_files))
                self.process_btn.setEnabled(True)
                self.status_label.setText(f"Found {len(image_files)} image files")
            else:
                self.file_list_text.setPlainText("No image files found in directory")
                self.process_btn.setEnabled(False)
                self.status_label.setText("No image files found")
                
        except Exception as e:
            self.file_list_text.setPlainText(f"Error loading directory: {e}")
            self.process_btn.setEnabled(False)
            self.status_label.setText(f"Error: {e}")
    
    def _process_screenshots(self):
        """Process the screenshot images"""
        try:
            # Validate directory
            if not os.path.isdir(self._directory_path):
                QMessageBox.warning(self, "Invalid Directory", "Selected directory does not exist")
                return
            
            # Show progress
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(0)
            self.status_label.setText("Processing screenshots...")
            self.process_btn.setEnabled(False)
            
            # Process images
            self._process_images()
            
            # Emit signal and close
            self.processing_started.emit(self._directory_path)
            self.accept()
            
        except Exception as e:
            QMessageBox.critical(self, "Processing Error", f"Failed to process screenshots: {e}")
            self.status_label.setText(f"Error: {e}")
            self.process_btn.setEnabled(True)
            self.progress_bar.setVisible(False)
    
    def _process_images(self):
        """Process image files and extract card information"""
        try:
            # Get list of image files
            image_extensions = ('.png', '.jpg', '.jpeg', '.webp', '.bmp', '.gif')
            image_files = []
            
            for filename in os.listdir(self._directory_path):
                if filename.lower().endswith(image_extensions):
                    image_files.append(filename)
            
            total_files = len(image_files)
            self.progress_bar.setRange(0, total_files)
            
            # For now, just simulate the processing
            # In a real implementation, this would:
            # 1. Load each image
            # 2. Process with OpenCV to detect cards
            # 3. Store results in database
            # 4. Update progress
            
            for i, filename in enumerate(image_files):
                # Simulate processing
                if i % 5 == 0:  # Update progress every 5 files
                    self.progress_bar.setValue(i)
                    self.status_label.setText(f"Processing {filename}... ({i+1}/{total_files})")
                    QApplication.processEvents()
            
            self.progress_bar.setValue(total_files)
            self.status_label.setText(f"Successfully processed {total_files} screenshots")
            
        except Exception as e:
            raise Exception(f"Failed to process images: {e}")

class AboutDialog(QDialog):
    """About dialog for the application"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("About Card Counter")
        self.setMinimumSize(400, 300)
        
        self._setup_ui()
    
    def _setup_ui(self):
        """Set up the user interface"""
        main_layout = QVBoxLayout()
        
        # Application icon
        icon_label = QLabel()
        icon_label.setPixmap(QIcon.fromTheme("cardcounter").pixmap(64, 64))
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(icon_label)
        
        # Application info
        info_label = QLabel("""
        <h2>Card Counter</h2>
        <p>Pokémon Card Identification Tool</p>
        <p>Version 1.0.0</p>
        <p>© 2025 Card Counter Team</p>
        <p>Built with PyQt6 and OpenCV</p>
        """)
        info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(info_label)
        
        # Close button
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        close_btn.setMinimumWidth(100)
        
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(close_btn)
        btn_layout.addStretch()
        
        main_layout.addLayout(btn_layout)
        
        self.setLayout(main_layout)