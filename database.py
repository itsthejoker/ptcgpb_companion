import sqlite3
import os
from typing import List, Dict, Any, Optional
import threading

class Database:
    def __init__(self, db_path: str = 'cardcounter.db'):
        self.db_path = db_path
        self._initialize_database()
        # Thread-local storage for database connections
        self.local_data = threading.local()
    
    def _initialize_database(self):
        """Initialize the database with required tables"""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            
            # Enable WAL mode for better concurrency (only needs to be set once)
            try:
                cursor.execute('PRAGMA journal_mode=WAL;')
                cursor.execute('PRAGMA synchronous=NORMAL;')
                print("Enabled WAL mode for better concurrency")
            except sqlite3.OperationalError:
                # WAL mode might not be available, continue with default
                print("WAL mode not available, using default journal mode")
            
            # Create screenshots table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS screenshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT,
                    original_filename TEXT,
                    clean_filename TEXT,
                    device_account TEXT,
                    pack_type TEXT,
                    card_types TEXT,
                    card_counts TEXT,
                    pack_screenshot TEXT UNIQUE,
                    shinedust TEXT,
                    processed BOOLEAN DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create cards table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS cards (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    card_name TEXT,
                    card_set TEXT,
                    image_path TEXT,
                    rarity TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(card_name, card_set)
                )
            ''')
            
            # Add rarity column to existing cards table if it doesn't exist
            self._add_rarity_column_if_not_exists(conn)
            
            # Create index for faster searches (only for tables that exist)
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_screenshots_clean_filename ON screenshots(clean_filename)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_cards_name ON cards(card_name)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_screenshots_pack_screenshot ON screenshots(pack_screenshot)')
            
            conn.commit()
            
            # Create screenshot_cards junction table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS screenshot_cards (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    screenshot_id INTEGER,
                    card_id INTEGER,
                    position INTEGER,
                    confidence REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (screenshot_id) REFERENCES screenshots(id),
                    FOREIGN KEY (card_id) REFERENCES cards(id),
                    UNIQUE(screenshot_id, card_id, position)
                )
            ''')
            
            # Create index for screenshot_cards table
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_screenshot_cards ON screenshot_cards(screenshot_id, card_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_screenshots_pack_screenshot ON screenshots(pack_screenshot)')
            
            conn.commit()
        finally:
            conn.close()
    
    def add_screenshot(self, data: Dict[str, Any]) -> tuple:
        """Add a screenshot record to the database
        
        Returns:
            tuple: (screenshot_id, is_new) where is_new is True if this was a new record, False if it was a duplicate
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            
            # Check if this screenshot already exists
            cursor.execute('SELECT id FROM screenshots WHERE pack_screenshot = ?', (data['PackScreenshot'],))
            existing = cursor.fetchone()
            
            if existing:
                return existing[0], False  # Return existing ID and False for is_new
            
            cursor.execute('''
                INSERT INTO screenshots (
                    timestamp, original_filename, clean_filename, device_account, 
                    pack_type, card_types, card_counts, pack_screenshot, shinedust
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                data['Timestamp'],
                data['OriginalFilename'],
                data['CleanFilename'],
                data['DeviceAccount'],
                data['PackType'],
                data['CardTypes'],
                data['CardCounts'],
                data['PackScreenshot'],
                data['Shinedust']
            ))
            
            conn.commit()
            return cursor.lastrowid, True  # Return new ID and True for is_new
        except Exception as e:
            print(f"Error adding screenshot: {e}")
            raise
        finally:
            self._return_connection()
    
    def add_card(self, card_name: str, card_set: str, image_path: str, rarity: str = None) -> int:
        """Add a card to the database"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT OR IGNORE INTO cards (card_name, card_set, image_path, rarity)
                VALUES (?, ?, ?, ?)
            ''', (card_name, card_set, image_path, rarity))
            
            conn.commit()
            
            # Get the card ID
            cursor.execute('SELECT id FROM cards WHERE card_name = ? AND card_set = ?', (card_name, card_set))
            result = cursor.fetchone()
            return result[0] if result else None
        except Exception as e:
            print(f"Error adding card: {e}")
            raise
        finally:
            self._return_connection()
    
    def add_screenshot_card(self, screenshot_id: int, card_id: int, position: int, confidence: float):
        """Add a relationship between a screenshot and a card"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT OR IGNORE INTO screenshot_cards (screenshot_id, card_id, position, confidence)
                VALUES (?, ?, ?, ?)
            ''', (screenshot_id, card_id, position, confidence))
            
            conn.commit()
        except Exception as e:
            print(f"Error adding screenshot_card relationship: {e}")
            raise
        finally:
            self._return_connection()
    
    def mark_screenshot_processed(self, screenshot_id: int):
        """Mark a screenshot as processed"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('UPDATE screenshots SET processed = 1 WHERE id = ?', (screenshot_id,))
            conn.commit()
        finally:
            self._return_connection()

    def update_card_rarity(self, card_name: str, card_set: str, rarity: str):
        """Update the rarity for a specific card"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE cards 
                SET rarity = ? 
                WHERE card_name = ? AND card_set = ?
            ''', (rarity, card_name, card_set))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            self._return_connection()

    def update_all_cards_rarity(self):
        """Update rarity information for all cards based on card names"""
        from names import cards as card_names
        
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            
            # Get all cards from database
            cursor.execute('SELECT card_name, card_set FROM cards')
            all_cards = cursor.fetchall()
            
            updated_count = 0
            
            for card_name, card_set in all_cards:
                # Try to find the display name to extract rarity
                # Handle both formats: "A2_84" and just "84"
                mapping_key = f"{card_set}_{card_name}" if not card_name.startswith(f"{card_set}_") else card_name
                
                if mapping_key in card_names:
                    display_name = card_names[mapping_key]
                    rarity = self._extract_rarity_from_display_name(display_name)
                    if rarity:
                        cursor.execute('''
                            UPDATE cards 
                            SET rarity = ? 
                            WHERE card_name = ? AND card_set = ?
                        ''', (rarity, card_name, card_set))
                        updated_count += 1
            
            conn.commit()
            return updated_count
        finally:
            self._return_connection()

    def _get_connection(self):
        """Get a database connection for the current thread"""
        # Check if this thread already has a connection
        if hasattr(self.local_data, 'connection'):
            return self.local_data.connection
        
        # Create a new connection for this thread
        # SQLite connections are thread-bound, so each thread must have its own connection
        # Enable WAL mode for better concurrency
        conn = sqlite3.connect(self.db_path, timeout=30.0, isolation_level=None)
        
        # Set busy timeout to handle locking issues
        try:
            conn.execute('PRAGMA busy_timeout=30000;')  # 30 seconds
        except sqlite3.OperationalError:
            # busy_timeout might not be available, continue with default
            pass
        
        # Store it in thread-local storage
        self.local_data.connection = conn
        return conn

    def _return_connection(self):
        """Close the connection for this thread"""
        if hasattr(self.local_data, 'connection'):
            conn = self.local_data.connection
            
            # Reset the thread-local connection
            delattr(self.local_data, 'connection')
            
            # Close the connection since we're not using a pool anymore
            try:
                conn.close()
            except:
                pass

    def _add_rarity_column_if_not_exists(self, conn):
        """Add rarity column to cards table if it doesn't exist"""
        cursor = conn.cursor()
        
        # Check if rarity column exists
        cursor.execute("PRAGMA table_info(cards)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'rarity' not in columns:
            # Add the rarity column
            cursor.execute("ALTER TABLE cards ADD COLUMN rarity TEXT")
            print("Added 'rarity' column to cards table")
        
    def _extract_rarity_from_display_name(self, display_name: str) -> str:
        """Extract rarity from card display name"""
        # Look for patterns like (1D), (2D), (3D), (4D), (1S), (2S), (3S)
        import re
        match = re.search(r'\(([0-9][A-Z])\)', display_name)
        if match:
            rarity_code = match.group(1)
            
            # Map rarity codes to human-readable names
            rarity_map = {
                '1D': 'Common',
                '2D': 'Uncommon',
                '3D': 'Rare',
                '4D': 'Ultra Rare',
                '1S': 'Common (Shiny)',
                '2S': 'Uncommon (Shiny)',
                '3S': 'Rare (Shiny)'
            }
            
            return rarity_map.get(rarity_code, 'Unknown')
        
        return 'Unknown'
    
    def get_all_screenshots(self) -> List[Dict[str, Any]]:
        """Get all screenshots (both processed and unprocessed)"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM screenshots')
            
            columns = [column[0] for column in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
        finally:
            self._return_connection()
    
    def get_unprocessed_screenshots(self) -> List[Dict[str, Any]]:
        """Get all unprocessed screenshots"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM screenshots WHERE processed = 0')
            
            columns = [column[0] for column in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
        finally:
            self._return_connection()
    
    def get_processed_screenshots_count(self) -> int:
        """Get count of processed screenshots"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM screenshots WHERE processed = 1')
            return cursor.fetchone()[0]
        finally:
            self._return_connection()
    
    def get_total_screenshots_count(self) -> int:
        """Get total count of all screenshots"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM screenshots')
            return cursor.fetchone()[0]
        finally:
            self._return_connection()
    
    def search_cards(self, card_name: str) -> List[Dict[str, Any]]:
        """Search for screenshots containing a specific card by display name"""
        if not card_name:
            return []
        
        # Import names module to get display name mappings
        try:
            import names
            card_names = names.cards
            set_names = names.sets
        except ImportError:
            # Fallback to raw card name search if names module not available
            conn = self._get_connection()
            try:
                cursor = conn.cursor()
                
                query = '''
                    SELECT s.clean_filename, c.card_name, c.card_set, sc.position, sc.confidence
                    FROM screenshot_cards sc
                    JOIN screenshots s ON sc.screenshot_id = s.id
                    JOIN cards c ON sc.card_id = c.id
                    WHERE c.card_name LIKE ?
                    ORDER BY s.clean_filename, sc.position
                '''
                
                cursor.execute(query, (f'%{card_name}%',))
                
                columns = [column[0] for column in cursor.description]
                return [dict(zip(columns, row)) for row in cursor.fetchall()]
            finally:
                self._return_connection()
        
        # Find all cards whose display names match the search query (partial match)
        matching_card_ids = []
        
        for raw_set in set_names.keys():
            for raw_card, display_name in card_names.items():
                if raw_card.startswith(f"{raw_set}_") and card_name.lower() in display_name.lower():
                    # This card's display name matches the search query
                    # We need to find the card_id for this card in the database
                    # The card could be stored in either format:
                    # Format 1: card_name = "84", card_set = "A3b"
                    # Format 2: card_name = "A3b_84", card_set = "A3b"
                    
                    card_name_part = raw_card.split('_', 1)[1]
                    
                    # Search for both possible formats
                    conn = self._get_connection()
                    try:
                        cursor = conn.cursor()
                        
                        # Try format 2 first (full format)
                        cursor.execute('SELECT id FROM cards WHERE card_name = ? AND card_set = ?', 
                                     (raw_card, raw_set))
                        row = cursor.fetchone()
                        if row:
                            matching_card_ids.append(row[0])
                            continue
                        
                        # Try format 1 (just the number)
                        cursor.execute('SELECT id FROM cards WHERE card_name = ? AND card_set = ?', 
                                     (card_name_part, raw_set))
                        row = cursor.fetchone()
                        if row:
                            matching_card_ids.append(row[0])
                    finally:
                        self._return_connection()
        
        # If no matches found, return empty list
        if not matching_card_ids:
            return []
        
        # Now search for screenshots containing any of the matching cards
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            
            # Create a query with OR conditions for each matching card
            placeholders = ','.join(['?'] * len(matching_card_ids))
            
            query = f'''
                SELECT s.clean_filename, c.card_name, c.card_set, sc.position, sc.confidence
                FROM screenshot_cards sc
                JOIN screenshots s ON sc.screenshot_id = s.id
                JOIN cards c ON sc.card_id = c.id
                WHERE sc.card_id IN ({placeholders})
                ORDER BY s.clean_filename, sc.position
            '''
            
            cursor.execute(query, matching_card_ids)
            
            columns = [column[0] for column in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
        finally:
            self._return_connection()
    
    def get_screenshot_by_id(self, screenshot_id: int) -> Optional[Dict[str, Any]]:
        """Get a screenshot by ID"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM screenshots WHERE id = ?', (screenshot_id,))
            
            row = cursor.fetchone()
            if row:
                columns = [column[0] for column in cursor.description]
                return dict(zip(columns, row))
            return None
        finally:
            self._return_connection()
    
    def get_all_cards(self) -> List[Dict[str, Any]]:
        """Get all cards in the database"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM cards')
            
            columns = [column[0] for column in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
        finally:
            self._return_connection()
    
    def get_cards_by_screenshot(self, screenshot_id: int) -> List[Dict[str, Any]]:
        """Get all cards found in a specific screenshot"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            
            query = '''
                SELECT c.card_name, c.card_set, sc.position, sc.confidence
                FROM screenshot_cards sc
                JOIN cards c ON sc.card_id = c.id
                WHERE sc.screenshot_id = ?
                ORDER BY sc.position
            '''
            
            cursor.execute(query, (screenshot_id,))
            
            columns = [column[0] for column in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
        finally:
            self._return_connection()
    
    def get_total_cards_count(self) -> int:
        """Get total count of all cards found in screenshots"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM screenshot_cards')
            return cursor.fetchone()[0]
        finally:
            self._return_connection()
    
    def close(self):
        """Close the database connection for this thread"""
        # Close any thread-local connections
        if hasattr(self.local_data, 'connection'):
            try:
                self.local_data.connection.close()
            except:
                pass
            delattr(self.local_data, 'connection')