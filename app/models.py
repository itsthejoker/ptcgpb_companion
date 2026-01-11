from PyQt6.QtCore import QAbstractTableModel, Qt, QModelIndex, pyqtSignal
from PyQt6.QtGui import QIcon, QPixmap
from typing import List, Dict, Any, Optional
import os

class CardModel(QAbstractTableModel):
    """Model for displaying cards in QTableView"""
    
    def __init__(self, data=None):
        super().__init__()
        self._data = data or []
        self._headers = ["Card", "Set", "Rarity", "Count", "Accounts"]
        
    def rowCount(self, parent=QModelIndex()) -> int:
        return len(self._data)
    
    def columnCount(self, parent=QModelIndex()) -> int:
        return len(self._headers)
    
    def data(self, index, role=Qt.ItemDataRole):
        if not index.isValid():
            return None
            
        row = index.row()
        col = index.column()
        
        if row >= len(self._data) or col >= len(self._headers):
            return None
            
        card_data = self._data[row]
        
        if role == Qt.ItemDataRole.DisplayRole:
            # Return text for display
            if col == 0:  # Card column
                return card_data.get('card_name', 'Unknown')
            elif col == 1:  # Set column
                return card_data.get('set_name', 'Unknown')
            elif col == 2:  # Rarity column
                return card_data.get('rarity', 'Unknown')
            elif col == 3:  # Count column
                return str(card_data.get('count', 0))
            elif col == 4:  # Accounts column
                return str(card_data.get('account_count', 0))
                
        elif role == Qt.ItemDataRole.DecorationRole and col == 0:
            # Return icon for card column
            card_code = card_data.get('card_code')
            if card_code:
                # Try to find card image
                image_path = self._find_card_image(card_code)
                if image_path and os.path.exists(image_path):
                    return QIcon(image_path)
                    
        elif role == Qt.ItemDataRole.ToolTipRole:
            # Return tooltip with detailed information
            tooltip = f"{card_data.get('card_name', 'Unknown')}\n"
            tooltip += f"Set: {card_data.get('set_name', 'Unknown')}\n"
            tooltip += f"Rarity: {card_data.get('rarity', 'Unknown')}\n"
            tooltip += f"Count: {card_data.get('count', 0)}\n"
            tooltip += f"Accounts: {card_data.get('account_count', 0)}"
            return tooltip
            
        return None
    
    def headerData(self, section, orientation, role=Qt.ItemDataRole):
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            if 0 <= section < len(self._headers):
                return self._headers[section]
        return None
        
    def update_data(self, new_data):
        """Update the model with new data"""
        self.beginResetModel()
        self._data = new_data
        self.endResetModel()
    
    def _find_card_image(self, card_code: str) -> Optional[str]:
        """Find the path to a card image based on card code"""
        # Try to find card image in resources
        # Card code format: SET_NUMBER (e.g., A1_1, A2_10, etc.)
        if '_' in card_code:
            set_code, card_number = card_code.split('_', 1)
            
            # Try different resource paths
            possible_paths = [
                f"resources/card_imgs/{set_code}/{card_code}.webp",
                f"resources/card_imgs/{set_code}/{card_code}.png",
                f"resources/card_imgs/{set_code}/{card_code}.jpg",
                f"static/card_imgs/{set_code}/{card_code}.webp",
                f"static/card_imgs/{set_code}/{card_code}.png",
                f"static/card_imgs/{set_code}/{card_code}.jpg",
            ]
            
            for path in possible_paths:
                if os.path.exists(path):
                    return path
                    
        return None

class ProcessingTaskModel(QAbstractTableModel):
    """Model for displaying processing tasks"""
    
    def __init__(self, data=None):
        super().__init__()
        self._data = data or []
        self._headers = ["Task ID", "Status", "Progress", "Description"]
    
    def rowCount(self, parent=QModelIndex()) -> int:
        return len(self._data)
    
    def columnCount(self, parent=QModelIndex()) -> int:
        return len(self._headers)
    
    def data(self, index, role=Qt.ItemDataRole):
        if not index.isValid():
            return None
            
        row = index.row()
        col = index.column()
        
        if row >= len(self._data) or col >= len(self._headers):
            return None
            
        task_data = self._data[row]
        
        if role == Qt.ItemDataRole.DisplayRole:
            if col == 0:  # Task ID
                return task_data.get('task_id', '')
            elif col == 1:  # Status
                return task_data.get('status', 'Unknown')
            elif col == 2:  # Progress
                return f"{task_data.get('progress', 0)}%"
            elif col == 3:  # Description
                return task_data.get('description', '')
                
        return None
    
    def headerData(self, section, orientation, role=Qt.ItemDataRole):
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            if 0 <= section < len(self._headers):
                return self._headers[section]
        return None
        
    def update_data(self, new_data):
        """Update the model with new data"""
        self.beginResetModel()
        self._data = new_data
        self.endResetModel()

class SearchResultModel(QAbstractTableModel):
    """Model for displaying search results"""
    
    def __init__(self, data=None):
        super().__init__()
        self._data = data or []
        self._headers = ["Card", "Set", "Rarity", "Pack", "Screenshot"]
    
    def rowCount(self, parent=QModelIndex()) -> int:
        return len(self._data)
    
    def columnCount(self, parent=QModelIndex()) -> int:
        return len(self._headers)
    
    def data(self, index, role=Qt.ItemDataRole):
        if not index.isValid():
            return None
            
        row = index.row()
        col = index.column()
        
        if row >= len(self._data) or col >= len(self._headers):
            return None
            
        result_data = self._data[row]
        
        if role == Qt.ItemDataRole.DisplayRole:
            if col == 0:  # Card
                return result_data.get('card_name', 'Unknown')
            elif col == 1:  # Set
                return result_data.get('set_name', 'Unknown')
            elif col == 2:  # Rarity
                return result_data.get('rarity', 'Unknown')
            elif col == 3:  # Pack
                return result_data.get('pack_id', '')
            elif col == 4:  # Screenshot
                return result_data.get('screenshot_name', '')
                
        return None
    
    def headerData(self, section, orientation, role=Qt.ItemDataRole):
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            if 0 <= section < len(self._headers):
                return self._headers[section]
        return None
        
    def update_data(self, new_data):
        """Update the model with new data"""
        self.beginResetModel()
        self._data = new_data
        self.endResetModel()