"""
Card Counter Main Window

Main application window for the Card Counter PyQt6 application.
This module provides the primary user interface for the application.
"""

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QTabWidget, QStatusBar, QToolBar, QMenuBar, QMenu,
    QTableView, QComboBox, QLineEdit, QHeaderView, QAbstractItemView, QDialog
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QAction, QIcon

# Import models
from app.models import CardModel

# Import dialogs
from app.dialogs import CSVImportDialog, ScreenshotProcessingDialog, AboutDialog

# Import workers
from app.workers import CSVImportWorker, ScreenshotProcessingWorker
from PyQt6.QtCore import QThreadPool

class MainWindow(QMainWindow):
    """
    Main application window for Card Counter
    
    Provides the primary user interface with menu bar, toolbar,
    tab-based central widget, and status bar.
    """
    
    def __init__(self):
        """Initialize the main window"""
        super().__init__()
        
        # Set window properties
        self.setWindowTitle("Card Counter")
        self.setMinimumSize(800, 600)
        
        # Initialize UI components
        self._setup_menu_bar()
        self._setup_toolbar()
        self._setup_central_widget()
        self._setup_status_bar()
        
        # Initialize processing status
        self._setup_processing_status()
        
        # Initialize database
        self._init_database()
        
        # Initialize thread pool
        self._init_thread_pool()
    
    def _init_database(self):
        """Initialize database connection"""
        try:
            from app.database import Database
            self.db = Database()
            print("Database initialized successfully")
        except Exception as e:
            print(f"Failed to initialize database: {e}")
            # Show error message to user
            from app.utils import show_error_message
            show_error_message("Database Error", f"Failed to initialize database: {e}")
    
    def _init_thread_pool(self):
        """Initialize thread pool for background processing"""
        self.thread_pool = QThreadPool()
        self.thread_pool.setMaxThreadCount(4)  # Limit to 4 concurrent workers
        print(f"Thread pool initialized with max {self.thread_pool.maxThreadCount()} threads")
        
        # Store active workers for cancellation
        self.active_workers = []
    
    def _setup_menu_bar(self):
        """Set up the menu bar"""
        menu_bar = self.menuBar()
        
        # File menu
        file_menu = menu_bar.addMenu("&File")
        
        # Import CSV action
        import_csv_action = QAction("&Import CSV", self)
        import_csv_action.setShortcut("Ctrl+I")
        import_csv_action.triggered.connect(self._on_import_csv)
        file_menu.addAction(import_csv_action)
        
        # Process Screenshots action
        process_action = QAction("&Process Screenshots", self)
        process_action.setShortcut("Ctrl+P")
        process_action.triggered.connect(self._on_process_screenshots)
        file_menu.addAction(process_action)
        
        # Exit action
        exit_action = QAction("E&xit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addSeparator()
        file_menu.addAction(exit_action)
        
        # View menu
        view_menu = menu_bar.addMenu("&View")
        
        # Help menu
        help_menu = menu_bar.addMenu("&Help")
        
        # About action
        about_action = QAction("&About", self)
        about_action.triggered.connect(self._on_about)
        help_menu.addAction(about_action)
    
    def _setup_toolbar(self):
        """Set up the toolbar"""
        toolbar = QToolBar("Main Toolbar")
        toolbar.setIconSize(QSize(24, 24))
        self.addToolBar(toolbar)
        
        # Import CSV button
        import_csv_btn = QPushButton("Import CSV")
        import_csv_btn.clicked.connect(self._on_import_csv)
        toolbar.addWidget(import_csv_btn)
        
        # Process Screenshots button
        process_btn = QPushButton("Process Screenshots")
        process_btn.clicked.connect(self._on_process_screenshots)
        toolbar.addWidget(process_btn)
        
        # Add separator
        toolbar.addSeparator()
        
        # Add some spacing
        toolbar.addWidget(QLabel("  "))
    
    def _setup_central_widget(self):
        """Set up the central widget with tab interface"""
        # Create main widget and layout
        main_widget = QWidget()
        main_layout = QVBoxLayout()
        main_widget.setLayout(main_layout)
        
        # Create tab widget
        self.tab_widget = QTabWidget()
        
        # Add tabs
        self._setup_dashboard_tab()
        self._setup_cards_tab()
        self._setup_processing_tab()
        self._setup_search_tab()
        
        main_layout.addWidget(self.tab_widget)
        self.setCentralWidget(main_widget)
    
    def _setup_dashboard_tab(self):
        """Set up the dashboard tab"""
        dashboard_widget = QWidget()
        dashboard_layout = QVBoxLayout()
        
        # Add dashboard content
        dashboard_layout.addWidget(QLabel("Dashboard Content"))
        dashboard_layout.addWidget(QLabel("Statistics and quick actions will go here"))
        
        dashboard_widget.setLayout(dashboard_layout)
        self.tab_widget.addTab(dashboard_widget, "Dashboard")
    
    def _setup_cards_tab(self):
        """Set up the cards tab"""
        cards_widget = QWidget()
        cards_layout = QVBoxLayout()
        
        # Create filter controls
        filter_layout = QHBoxLayout()
        
        # Set filter
        self.set_filter = QComboBox()
        self.set_filter.addItem("All Sets")
        self.set_filter.setMinimumWidth(150)
        filter_layout.addWidget(QLabel("Set:"))
        filter_layout.addWidget(self.set_filter)
        
        # Rarity filter
        self.rarity_filter = QComboBox()
        self.rarity_filter.addItem("All Rarities")
        self.rarity_filter.setMinimumWidth(150)
        filter_layout.addWidget(QLabel("Rarity:"))
        filter_layout.addWidget(self.rarity_filter)
        
        # Account filter
        self.account_filter = QComboBox()
        self.account_filter.addItem("All Accounts")
        self.account_filter.setMinimumWidth(150)
        filter_layout.addWidget(QLabel("Account:"))
        filter_layout.addWidget(self.account_filter)
        
        # Search box
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search cards...")
        self.search_box.setMinimumWidth(200)
        filter_layout.addWidget(self.search_box)
        
        # Add filter controls to layout
        cards_layout.addLayout(filter_layout)
        
        # Create table view for cards
        self.cards_table = QTableView()
        self.cards_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.cards_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.cards_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        
        # Set up horizontal header
        horizontal_header = self.cards_table.horizontalHeader()
        horizontal_header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        horizontal_header.setStretchLastSection(True)
        
        # Set up vertical header
        vertical_header = self.cards_table.verticalHeader()
        vertical_header.setVisible(False)
        
        # Add table to layout
        cards_layout.addWidget(self.cards_table)
        
        # Set up card model
        self._setup_card_model()
        
        cards_widget.setLayout(cards_layout)
        self.tab_widget.addTab(cards_widget, "Cards")
    
    def _setup_processing_tab(self):
        """Set up the processing tab"""
        processing_widget = QWidget()
        processing_layout = QVBoxLayout()
        
        # Add processing content
        processing_layout.addWidget(QLabel("Processing Status"))
        processing_layout.addWidget(QLabel("Background task monitoring will go here"))
        
        processing_widget.setLayout(processing_layout)
        self.tab_widget.addTab(processing_widget, "Processing")
    
    def _setup_processing_status(self):
        """Set up processing status tracking"""
        # This will be expanded in future phases
        self.processing_tasks = []
    
    def _setup_search_tab(self):
        """Set up the search tab"""
        search_widget = QWidget()
        search_layout = QVBoxLayout()
        
        # Add search content
        search_layout.addWidget(QLabel("Search"))
        search_layout.addWidget(QLabel("Advanced search functionality will go here"))
        
        search_widget.setLayout(search_layout)
        self.tab_widget.addTab(search_widget, "Search")
    
    def _setup_card_model(self):
        """Set up the card model and load initial data"""
        try:
            # Create card model
            self.card_model = CardModel()
            self.cards_table.setModel(self.card_model)
            
            # Load initial card data
            self._load_card_data()
            
            # Connect filter signals
            self.set_filter.currentIndexChanged.connect(self._apply_filters)
            self.rarity_filter.currentIndexChanged.connect(self._apply_filters)
            self.account_filter.currentIndexChanged.connect(self._apply_filters)
            self.search_box.textChanged.connect(self._apply_filters)
            
        except Exception as e:
            print(f"Error setting up card model: {e}")
            self.statusBar().showMessage(f"Error loading card data: {e}")
    
    def _load_card_data(self):
        """Load card data from database"""
        try:
            if hasattr(self, 'db') and self.db:
                # Get all cards with counts and account information
                cards = self.db.get_all_cards_with_counts()
                
                # Process data for the model
                card_data = []
                for card in cards:
                    card_info = {
                        'card_code': card[0],
                        'card_name': card[1],
                        'set_name': card[2],
                        'rarity': card[3],
                        'count': card[4],
                        'account_count': card[5]
                    }
                    card_data.append(card_info)
                
                # Update model
                self.card_model.update_data(card_data)
                
                # Update filter options
                self._update_filter_options(card_data)
                
                self.statusBar().showMessage(f"Loaded {len(card_data)} cards")
            else:
                self.statusBar().showMessage("Database not available")
                
        except Exception as e:
            print(f"Error loading card data: {e}")
            self.statusBar().showMessage(f"Error loading card data: {e}")
    
    def _update_filter_options(self, card_data):
        """Update filter options based on available data"""
        try:
            # Update set filter
            sets = set()
            for card in card_data:
                if card.get('set_name'):
                    sets.add(card['set_name'])
            
            current_set = self.set_filter.currentText()
            self.set_filter.clear()
            self.set_filter.addItem("All Sets")
            for set_name in sorted(sets):
                self.set_filter.addItem(set_name)
            
            # Restore previous selection if possible
            if current_set != "All Sets" and current_set in sets:
                index = self.set_filter.findText(current_set)
                if index >= 0:
                    self.set_filter.setCurrentIndex(index)
            
            # Update rarity filter
            rarities = set()
            for card in card_data:
                if card.get('rarity'):
                    rarities.add(card['rarity'])
            
            current_rarity = self.rarity_filter.currentText()
            self.rarity_filter.clear()
            self.rarity_filter.addItem("All Rarities")
            for rarity in sorted(rarities):
                self.rarity_filter.addItem(rarity)
            
            # Restore previous selection if possible
            if current_rarity != "All Rarities" and current_rarity in rarities:
                index = self.rarity_filter.findText(current_rarity)
                if index >= 0:
                    self.rarity_filter.setCurrentIndex(index)
            
            # Update account filter (placeholder - would need account data)
            # For now, just keep "All Accounts"
            
        except Exception as e:
            print(f"Error updating filter options: {e}")
    
    def _apply_filters(self):
        """Apply current filters to the card data"""
        try:
            # Get current filter values
            set_filter = self.set_filter.currentText()
            rarity_filter = self.rarity_filter.currentText()
            account_filter = self.account_filter.currentText()
            search_text = self.search_box.text().strip().lower()
            
            # Get all cards
            all_cards = []
            if hasattr(self.card_model, '_data'):
                all_cards = self.card_model._data
            
            # Apply filters
            filtered_cards = []
            for card in all_cards:
                # Apply set filter
                if set_filter != "All Sets" and card.get('set_name') != set_filter:
                    continue
                
                # Apply rarity filter
                if rarity_filter != "All Rarities" and card.get('rarity') != rarity_filter:
                    continue
                
                # Apply search filter
                if search_text:
                    card_name = card.get('card_name', '').lower()
                    set_name = card.get('set_name', '').lower()
                    rarity = card.get('rarity', '').lower()
                    
                    if (search_text not in card_name and 
                        search_text not in set_name and 
                        search_text not in rarity):
                        continue
                
                filtered_cards.append(card)
            
            # Update model with filtered data
            self.card_model.update_data(filtered_cards)
            self.statusBar().showMessage(f"Showing {len(filtered_cards)} of {len(all_cards)} cards")
            
        except Exception as e:
            print(f"Error applying filters: {e}")
            self.statusBar().showMessage(f"Error applying filters: {e}")
    
    def _setup_status_bar(self):
        """Set up the status bar"""
        status_bar = QStatusBar()
        status_bar.showMessage("Ready")
        self.setStatusBar(status_bar)
    
    def _on_import_csv(self):
        """Handle Import CSV action"""
        print("Import CSV action triggered")
        
        try:
            # Create and show CSV import dialog
            dialog = CSVImportDialog(self)
            dialog.csv_imported.connect(self._on_csv_imported)
            
            if dialog.exec() == QDialog.DialogCode.Accepted:
                self.statusBar().showMessage("CSV import completed")
            else:
                self.statusBar().showMessage("CSV import cancelled")
                
        except Exception as e:
            print(f"Error importing CSV: {e}")
            self.statusBar().showMessage(f"Error importing CSV: {e}")
    
    def _on_csv_imported(self, file_path: str):
        """Handle successful CSV import - start background processing"""
        print(f"Starting background CSV import from: {file_path}")
        self.statusBar().showMessage(f"Starting background CSV import...")
        
        try:
            # Create worker for CSV import
            worker = CSVImportWorker(
                file_path=file_path,
                account_id=1,  # Default account for now
                pack_size=11,  # Default pack size
                tradeable=True
            )
            
            # Connect signals
            worker.signals.progress.connect(self._on_csv_import_progress)
            worker.signals.status.connect(self._on_csv_import_status)
            worker.signals.result.connect(self._on_csv_import_result)
            worker.signals.error.connect(self._on_csv_import_error)
            worker.signals.finished.connect(self._on_csv_import_finished)
            
            # Store worker for cancellation
            self.active_workers.append(worker)
            
            # Start worker
            self.thread_pool.start(worker)
            
            self.statusBar().showMessage("CSV import started in background")
            
        except Exception as e:
            print(f"Error starting CSV import worker: {e}")
            self.statusBar().showMessage(f"Error starting CSV import: {e}")
    
    def _on_csv_import_progress(self, current: int, total: int):
        """Handle CSV import progress updates"""
        self.statusBar().showMessage(f"CSV import progress: {current}/{total}")
    
    def _on_csv_import_status(self, status: str):
        """Handle CSV import status updates"""
        print(f"CSV import status: {status}")
        self.statusBar().showMessage(status)
    
    def _on_csv_import_result(self, result: dict):
        """Handle CSV import result"""
        print(f"CSV import result: {result}")
        self.statusBar().showMessage(f"CSV import completed: {result.get('total_rows', 0)} packs imported")
    
    def _on_csv_import_error(self, error: str):
        """Handle CSV import errors"""
        print(f"CSV import error: {error}")
        self.statusBar().showMessage(f"CSV import error: {error}")
    
    def _on_csv_import_finished(self):
        """Handle CSV import completion"""
        print("CSV import finished")
        self.statusBar().showMessage("CSV import finished")
        
        # Clean up worker
        if self.active_workers:
            self.active_workers.pop()
    
    def _on_process_screenshots(self):
        """Handle Process Screenshots action"""
        print("Process Screenshots action triggered")
        
        try:
            # Create and show screenshot processing dialog
            dialog = ScreenshotProcessingDialog(self)
            dialog.processing_started.connect(self._on_processing_started)
            
            if dialog.exec() == QDialog.DialogCode.Accepted:
                self.statusBar().showMessage("Screenshot processing completed")
            else:
                self.statusBar().showMessage("Screenshot processing cancelled")
                
        except Exception as e:
            print(f"Error processing screenshots: {e}")
            self.statusBar().showMessage(f"Error processing screenshots: {e}")
    
    def _on_processing_started(self, directory_path: str):
        """Handle successful processing start"""
        print(f"Processing started for directory: {directory_path}")
        self.statusBar().showMessage(f"Processing screenshots from: {directory_path}")
    
    def _on_about(self):
        """Handle About action"""
        print("About action triggered")
        
        try:
            # Create and show about dialog
            dialog = AboutDialog(self)
            dialog.exec()
            
        except Exception as e:
            print(f"Error showing about dialog: {e}")
            self.statusBar().showMessage(f"Error showing about dialog: {e}")
    
    def closeEvent(self, event):
        """Handle window close event"""
        print("Closing application...")
        
        # Clean up database connections
        if hasattr(self, 'db'):
            self.db.close()
            print("Database connections closed")
        
        event.accept()
