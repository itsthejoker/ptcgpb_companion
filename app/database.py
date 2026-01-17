"""
Card Counter Database Module

PyQt6-compatible database module for the Card Counter application.
This module provides database access for the portable desktop application.
"""

import sqlite3
import threading
import os
from typing import List, Dict, Any, Optional
import logging
from contextlib import contextmanager

logger = logging.getLogger(__name__)

CREATE_SCREENSHOT_TABLE_SQL = """
    CREATE TABLE IF NOT EXISTS screenshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT,
        original_filename TEXT,
        clean_filename TEXT,
        account TEXT,
        pack_type TEXT,
        card_types TEXT,
        card_counts TEXT,
        pack_screenshot TEXT UNIQUE,
        screenshot_path TEXT,
        shinedust TEXT,
        processed BOOLEAN DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
"""

CREATE_CARD_TABLE_SQL = """
    CREATE TABLE IF NOT EXISTS cards (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        card_name TEXT,
        card_set TEXT,
        card_code TEXT,
        image_path TEXT,
        rarity TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(card_code, card_set)
    )
"""

CREATE_MIGRATIONS_TABLE_SQL = """
    CREATE TABLE IF NOT EXISTS migrations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        migration_name TEXT UNIQUE,
        applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        completed BOOLEAN DEFAULT 0
    )
"""

SCREENSHOT_CARDS_TABLE_SQL = """
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
"""

CREATE_ACCOUNTS_TABLE_SQL = """
    CREATE TABLE IF NOT EXISTS accounts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        account_name TEXT UNIQUE,
        shinedust TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
"""


class Migration:
    def __init__(self, migration_name: str, sql: str = None, message: str = None):
        self.migration_name = migration_name
        self.sql = sql
        self.message = message

    def __repr__(self):
        return f"Migration('{self.migration_name}')"

    def __eq__(self, other):
        if isinstance(other, Migration):
            return self.migration_name == other.migration_name
        return False

    def exists(self) -> bool:
        conn = self.db._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM migrations WHERE migration_name = ?",
                (self.migration_name,),
            )
            return cursor.fetchone() is not None
        finally:
            self.db._return_connection()

    def mark_migration_complete(self):
        conn = self.db._get_connection()
        try:
            cursor = conn.cursor()
            # Migrations are unique, so if it exists in the db, that's all that we need
            cursor.execute(
                "INSERT OR REPLACE INTO migrations (migration_name, completed) VALUES (?, 1)",
                (self.migration_name,),
            )
            self.db._commit(conn)
        finally:
            self.db._return_connection()

    def get_cursor(self):
        return self.db._get_connection().cursor()

    def check_constraints(self) -> bool:
        """Check if the migration can or should be applied. True is for go, False is for no-go"""
        raise NotImplementedError

    def migrate(self) -> bool:
        conn = self.db._get_connection()
        try:
            cursor = conn.cursor()
            if self.exists():
                return False
            if not self.check_constraints():
                # If constraints say we don't need it but it's not in migrations table, mark it as complete
                self.mark_migration_complete()
                return False
            cursor.execute(self.sql)
            self.db._commit(conn)
            self.mark_migration_complete()

            logger.info(f"Applied migration: {self.migration_name}")
            return True
        finally:
            self.db._return_connection()

    def check_for_column_in_table(self, column: str, table: str) -> bool:
        cursor = self.get_cursor()
        cursor.execute(f"PRAGMA table_info({table})")
        columns = [row[1] for row in cursor.fetchall()]
        return column not in columns

    def post_migration(self):
        """Any code that should be run after all migrations have run."""
        raise NotImplementedError


class ScreenshotMigration(Migration):
    def __init__(self, db: "Database"):
        super().__init__("add_screenshot_path")
        self.db = db
        self.message = "Adding screenshot_path column to screenshots table"
        self.sql = "ALTER TABLE screenshots ADD COLUMN screenshot_path TEXT"

    def check_constraints(self):
        return self.check_for_column_in_table("screenshot_path", "screenshots")


class ShinedustMigration(Migration):
    def __init__(self, db: "Database"):
        super().__init__("add_shinedust_column")
        self.db = db
        self.message = "Adding shinedust column to screenshots table"
        self.sql = "ALTER TABLE screenshots ADD COLUMN shinedust TEXT"

    def check_constraints(self):
        return self.check_for_column_in_table("shinedust", "screenshots")


class CardCodeMigration(Migration):
    def __init__(self, db: "Database"):
        super().__init__("add_card_code_to_cards")
        self.db = db
        self.message = "Adding card_code column to cards table and recreating table for UNIQUE constraint"

    def check_constraints(self):
        return self.check_for_column_in_table("card_code", "cards")

    def migrate(self) -> bool:
        conn = self.db._get_connection()
        try:
            cursor = conn.cursor()
            if self.exists():
                return False
            if not self.check_constraints():
                return False

            logger.info(self.message)

            # SQLite doesn't support dropping/modifying UNIQUE constraints easily.
            # The safest way is to recreate the table.
            cursor.execute("ALTER TABLE cards RENAME TO cards_old")
            cursor.execute(
                """
                CREATE TABLE cards (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    card_name TEXT,
                    card_set TEXT,
                    card_code TEXT,
                    image_path TEXT,
                    rarity TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(card_code, card_set)
                )
            """
            )

            # Copy data and try to infer card_code from image_path
            cursor.execute(
                "SELECT id, card_name, card_set, image_path, rarity, created_at FROM cards_old"
            )
            for row in cursor.fetchall():
                cid, name, cset, img_path, rarity, created = row
                # Infer code from image_path: "A2b/A2b_80.webp" -> "A2b_80"
                code = None
                if img_path:
                    base = os.path.basename(img_path)
                    code = os.path.splitext(base)[0]

                if not code:
                    code = f"{cset}_{name}"

                cursor.execute(
                    """
                    INSERT INTO cards (id, card_name, card_set, card_code, image_path, rarity, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                    (cid, name, cset, code, img_path, rarity, created),
                )

            cursor.execute("DROP TABLE cards_old")
            self.db._commit(conn)
            self.mark_migration_complete()
            logger.info(f"Applied migration: {self.migration_name}")
            return True

        except Exception as e:
            logger.error(f"Failed to migrate cards table: {e}")
            raise
        finally:
            self.db._return_connection()


class AccountsMigration(Migration):
    def __init__(self, db: "Database"):
        super().__init__("create_accounts_table")
        self.db = db
        self.message = (
            "Creating accounts table for storing account-level data like shinedust"
        )
        self.sql = CREATE_ACCOUNTS_TABLE_SQL

    def check_constraints(self):
        cursor = self.get_cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='accounts'"
        )
        return cursor.fetchone() is None


MIGRATIONS = [
    ScreenshotMigration,
    ShinedustMigration,
    CardCodeMigration,
    AccountsMigration,
]


class Database:
    """
    Database class for Card Counter application

    Provides thread-safe access to SQLite database for storing
    screenshots, cards, and their relationships.
    """

    # Class-level storage to track initialized databases
    _initialized_paths = set()
    _init_lock = threading.Lock()

    def __init__(self, db_path: str = None):
        """
        Initialize the database

        Args:
            db_path: Path to database file. If None, uses default portable path.
        """
        if db_path is None:
            from app.utils import get_portable_path

            db_path = get_portable_path("data", "cardcounter.db")

        self.db_path = db_path

        # Thread-local storage for database connections
        # SQLite connections are thread-bound, so each thread must have its own connection
        self.local_data = threading.local()

        # Track if any migration was applied during this session
        self.migration_applied = False

        # Only initialize the database once per path
        with Database._init_lock:
            if self.db_path not in Database._initialized_paths:
                self._initialize_database()
                self._migrate()
                Database._initialized_paths.add(self.db_path)

    def _migrate(self):
        for migration_class in MIGRATIONS:
            migration = migration_class(self)
            if migration.migrate():
                self.migration_applied = True

        for migration_class in MIGRATIONS:
            migration = migration_class(self)
            try:
                migration.post_migration()
            except NotImplementedError:
                pass

    @contextmanager
    def transaction(self):
        """
        Context manager for database transactions.

        Usage:
            with db.transaction():
                db.add_screenshot(...)
                db.add_card(...)
        """
        conn = self._get_connection()
        previous_state = getattr(self.local_data, "in_transaction", False)
        self.local_data.in_transaction = True
        try:
            # Check if we are already in a transaction to avoid nested BEGIN
            if not previous_state:
                conn.execute("BEGIN IMMEDIATE TRANSACTION")
            yield conn
            if not previous_state:
                conn.commit()
        except Exception:
            if not previous_state:
                conn.rollback()
            raise
        finally:
            self.local_data.in_transaction = previous_state

    def _commit(self, conn):
        """Commit the current transaction if not managed by transaction() context manager"""
        if not getattr(self.local_data, "in_transaction", False):
            conn.commit()

    def _initialize_database(self):
        """Initialize the database with required tables"""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()

            # Enable WAL mode for better concurrency (only needs to be set once)
            try:
                cursor.execute("PRAGMA journal_mode=WAL;")
                cursor.execute("PRAGMA synchronous=NORMAL;")
                logger.info("Enabled WAL mode for better concurrency")
            except sqlite3.OperationalError:
                # WAL mode might not be available, continue with default
                logger.warning("WAL mode not available, using default journal mode")

            # Create screenshots table
            cursor.execute(CREATE_SCREENSHOT_TABLE_SQL)

            # Create cards table
            cursor.execute(CREATE_CARD_TABLE_SQL)

            # Create migrations table
            cursor.execute(CREATE_MIGRATIONS_TABLE_SQL)

            # Create accounts table
            cursor.execute(CREATE_ACCOUNTS_TABLE_SQL)

            # Create index for faster searches (only for tables that exist)
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_screenshots_clean_filename ON screenshots(clean_filename)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_screenshots_original_filename ON screenshots(original_filename)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_screenshots_account ON screenshots(account)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_screenshots_timestamp ON screenshots(timestamp)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_screenshots_processed ON screenshots(processed)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_cards_name ON cards(card_name)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_screenshots_pack_screenshot ON screenshots(pack_screenshot)"
            )

            conn.commit()

            # Create screenshot_cards junction table
            cursor.execute(SCREENSHOT_CARDS_TABLE_SQL)

            # Create index for screenshot_cards table
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_screenshot_cards_screenshot_id ON screenshot_cards(screenshot_id)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_screenshot_cards_card_id ON screenshot_cards(card_id)"
            )

            conn.commit()
            logger.info(f"Database initialized at {self.db_path}")

        finally:
            conn.close()

    def add_screenshot(self, data: Dict[str, Any]) -> tuple:
        """
        Add a screenshot record to the database

        Args:
            data: Dictionary containing screenshot data

        Returns:
            tuple: (screenshot_id, is_new) where is_new is True if this was a new record,
                   False if it was a duplicate
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()

            # Requirement: CleanFilename is the account name
            # We prioritize CleanFilename for the account field
            account = data.get("CleanFilename", data.get("Account", "Account Unknown"))
            if not account or account == "Default":
                account = "Account Unknown"

            # Check if this screenshot already exists
            cursor.execute(
                "SELECT id FROM screenshots WHERE pack_screenshot = ?",
                (data["PackScreenshot"],),
            )
            existing = cursor.fetchone()

            if existing:
                screenshot_id = existing[0]
                # Update metadata if it was missing or empty
                # Also backfill account information if it was previously unknown
                cursor.execute(
                    """
                    UPDATE screenshots SET 
                        pack_type = CASE WHEN pack_type = 'Unknown' OR pack_type = '' THEN ? ELSE pack_type END,
                        card_types = CASE WHEN card_types = '' THEN ? ELSE card_types END,
                        card_counts = CASE WHEN card_counts = '0' OR card_counts = '' OR card_counts IS NULL THEN ? ELSE card_counts END,
                        account = CASE WHEN account = 'Account Unknown' OR account = 'Default' OR account = '' OR account LIKE '%.png' OR account LIKE '%.jpg' THEN ? ELSE account END,
                        clean_filename = CASE WHEN clean_filename = 'Account Unknown' OR clean_filename = 'Default' OR clean_filename = '' OR clean_filename LIKE '%.png' OR clean_filename LIKE '%.jpg' THEN ? ELSE clean_filename END,
                        screenshot_path = CASE WHEN screenshot_path IS NULL OR screenshot_path = '' THEN ? ELSE screenshot_path END,
                        shinedust = COALESCE(NULLIF(?, ''), shinedust)
                    WHERE id = ?
                """,
                    (
                        data["PackType"],
                        data["CardTypes"],
                        data["CardCounts"],
                        account,
                        data.get("CleanFilename", account),
                        data.get("ScreenshotPath"),
                        data.get("Shinedust"),
                        screenshot_id,
                    ),
                )
                self._commit(conn)

                # Also update accounts table
                if data.get("Shinedust"):
                    self.update_account_shinedust(account, data["Shinedust"])

                return screenshot_id, False  # Return existing ID and False for is_new

            cursor.execute(
                """
                INSERT INTO screenshots (
                    timestamp, original_filename, clean_filename, account,
                    pack_type, card_types, card_counts, pack_screenshot,
                    screenshot_path, shinedust
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    data["Timestamp"],
                    data["OriginalFilename"],
                    data.get("CleanFilename") or account,
                    account,
                    data["PackType"],
                    data["CardTypes"],
                    data["CardCounts"],
                    data["PackScreenshot"],
                    data.get("ScreenshotPath"),
                    data["Shinedust"],
                ),
            )

            self._commit(conn)

            # Also update accounts table
            if data.get("Shinedust"):
                self.update_account_shinedust(account, data["Shinedust"])

            return cursor.lastrowid, True  # Return new ID and True for is_new

        except Exception as e:
            logger.error(f"Error adding screenshot: {e}")
            raise
        finally:
            self._return_connection()

    def update_account_shinedust(self, account_name: str, shinedust: str) -> None:
        """
        Update the shinedust amount for an account in the accounts table.

        Args:
            account_name: Name of the account
            shinedust: Shinedust amount
        """
        if not account_name or account_name == "Account Unknown":
            return

        if not shinedust or not str(shinedust).strip():
            return

        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            # We use INSERT OR REPLACE to update the shinedust for the account
            cursor.execute(
                """
                INSERT INTO accounts (account_name, shinedust) 
                VALUES (?, ?) 
                ON CONFLICT(account_name) DO UPDATE SET 
                    shinedust = excluded.shinedust 
                WHERE excluded.shinedust IS NOT NULL AND excluded.shinedust != ''
            """,
                (account_name, shinedust),
            )
            self._commit(conn)
        except sqlite3.OperationalError as e:
            # Handle older SQLite versions that don't support ON CONFLICT
            if "syntax error" in str(e).lower() and "ON CONFLICT" in str(e):
                # Fallback to manual check and update
                pass
            else:
                # If it's another operational error, re-raise
                raise

            # Manual fallback
            cursor.execute(
                "SELECT id FROM accounts WHERE account_name = ?", (account_name,)
            )
            existing = cursor.fetchone()
            if existing:
                cursor.execute(
                    "UPDATE accounts SET shinedust = ? WHERE account_name = ?",
                    (shinedust, account_name),
                )
            else:
                cursor.execute(
                    "INSERT INTO accounts (account_name, shinedust) VALUES (?, ?)",
                    (account_name, shinedust),
                )
            self._commit(conn)
        except Exception as e:
            logger.error(f"Error updating account shinedust: {e}")
            raise
        finally:
            self._return_connection()

    def add_card(
        self,
        card_name: str,
        card_set: str,
        image_path: str,
        rarity: str = None,
        card_code: str = None,
    ) -> int:
        """
        Add a card to the database

        Args:
            card_name: Name of the card
            card_set: Set the card belongs to
            image_path: Path to card image
            rarity: Rarity of the card (optional)
            card_code: Unique code for the card (optional)

        Returns:
            int: ID of the card
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()

            # If card_code not provided, infer from image_path or use set_name
            if not card_code:
                if image_path:
                    card_code = os.path.splitext(os.path.basename(image_path))[0]
                else:
                    card_code = f"{card_set}_{card_name}"

            cursor.execute(
                """
                INSERT OR IGNORE INTO cards (card_name, card_set, card_code, image_path, rarity)
                VALUES (?, ?, ?, ?, ?)
            """,
                (card_name, card_set, card_code, image_path, rarity),
            )

            self._commit(conn)

            # Get the card ID
            cursor.execute(
                "SELECT id FROM cards WHERE card_code = ? AND card_set = ?",
                (card_code, card_set),
            )
            result = cursor.fetchone()
            return result[0] if result else None

        except Exception as e:
            logger.error(f"Error adding card: {e}")
            raise
        finally:
            self._return_connection()

    def add_screenshot_card(
        self, screenshot_id: int, card_id: int, position: int, confidence: float
    ):
        """
        Add a relationship between a screenshot and a card

        Args:
            screenshot_id: ID of the screenshot
            card_id: ID of the card
            position: Position of the card in the screenshot
            confidence: Confidence score for the card identification
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT OR IGNORE INTO screenshot_cards (screenshot_id, card_id, position, confidence)
                VALUES (?, ?, ?, ?)
            """,
                (screenshot_id, card_id, position, confidence),
            )

            self._commit(conn)
        except Exception as e:
            logger.error(f"Error adding screenshot_card relationship: {e}")
            raise
        finally:
            self._return_connection()

    def mark_screenshot_processed(self, screenshot_id: int):
        """
        Mark a screenshot as processed

        Args:
            screenshot_id: ID of the screenshot to mark as processed
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE screenshots SET processed = 1 WHERE id = ?", (screenshot_id,)
            )
            self._commit(conn)
        finally:
            self._return_connection()

    def check_screenshot_exists(self, filename: str, account: str = None) -> bool:
        """
        Check if a screenshot with the given filename has already been processed.
        If account is provided, checks for that specific account.

        Args:
            filename: Name of the screenshot file
            account: Optional account name

        Returns:
            bool: True if it exists and is processed, False otherwise
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            if account:
                cursor.execute(
                    """
                    SELECT processed FROM screenshots 
                    WHERE (original_filename = ? OR pack_screenshot = ?) AND account = ?
                """,
                    (filename, filename, account),
                )
            else:
                cursor.execute(
                    """
                    SELECT processed FROM screenshots 
                    WHERE original_filename = ? OR pack_screenshot = ?
                """,
                    (filename, filename),
                )

            results = cursor.fetchall()
            # If any matching record is processed, we consider it processed
            return any(row[0] == 1 for row in results)
        except Exception as e:
            logger.error(f"Error checking if screenshot exists: {e}")
            return False
        finally:
            self._return_connection()

    def get_unprocessed_files(self, filenames: List[str]) -> List[str]:
        """
        Given a list of filenames, returns only those that are NOT already
        processed in the database.

        Args:
            filenames: List of filenames to check

        Returns:
            List[str]: List of filenames that are not processed
        """
        if not filenames:
            return []

        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            # Handle large batches by chunking to avoid SQLite limits
            batch_size = (
                450  # SQLite limit is usually 999 parameters, we use 2x parameters
            )

            all_processed = set()
            for i in range(0, len(filenames), batch_size):
                chunk = filenames[i : i + batch_size]
                placeholders = ", ".join(["?"] * len(chunk))
                query = f"""
                    SELECT original_filename, pack_screenshot 
                    FROM screenshots 
                    WHERE processed = 1 AND (original_filename IN ({placeholders}) OR pack_screenshot IN ({placeholders}))
                """
                cursor.execute(query, chunk + chunk)
                for row in cursor.fetchall():
                    if row[0]:
                        all_processed.add(row[0])
                    if row[1]:
                        all_processed.add(row[1])

            return [f for f in filenames if f not in all_processed]
        except Exception as e:
            logger.error(f"Error filtering unprocessed files: {e}")
            return filenames
        finally:
            self._return_connection()

    def _get_connection(self):
        """
        Get a database connection for the current thread

        Returns:
            sqlite3.Connection: Database connection
        """
        # Check if this thread already has a connection
        if hasattr(self.local_data, "connection"):
            return self.local_data.connection

        # Create a new connection for this thread
        # SQLite connections are thread-bound, so each thread must have its own connection
        # Enable WAL mode for better concurrency
        conn = sqlite3.connect(self.db_path, timeout=30.0, isolation_level=None)

        # Set busy timeout to handle locking issues
        try:
            conn.execute("PRAGMA busy_timeout=30000;")  # 30 seconds
        except sqlite3.OperationalError:
            # busy_timeout might not be available, continue with default
            pass

        # Store it in thread-local storage
        self.local_data.connection = conn
        return conn

    def _return_connection(self):
        """
        No-op to allow for connection reuse within the same thread.
        Connections are now kept in thread-local storage until explicitly closed.
        """
        # Connection stays in self.local_data.connection for reuse
        pass

    def get_all_cards(self) -> List[Dict[str, Any]]:
        """
        Get all cards in the database

        Returns:
            List[Dict]: List of all card records
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM cards")

            columns = [column[0] for column in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
        finally:
            self._return_connection()

    def get_all_cards_with_counts(self, account: str = None) -> List[tuple]:
        """
        Get all cards with their counts, optionally filtered by account

        Args:
            account: Optional account name to filter by

        Returns:
            List[tuple]: List of tuples containing (card_code, card_name, set_name,
                       rarity, total_count, image_path)
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()

            # Query to get card counts
            if account:
                query = """
                    SELECT 
                        c.card_code,
                        c.card_name,
                        c.card_set as set_name,
                        c.rarity,
                        COUNT(sc.id) as total_count,
                        c.image_path
                    FROM cards c
                    LEFT JOIN screenshot_cards sc ON c.id = sc.card_id
                    LEFT JOIN screenshots s ON sc.screenshot_id = s.id AND s.account = ?
                    GROUP BY c.card_code, c.card_name, c.card_set, c.rarity, c.image_path
                    ORDER BY c.card_set, c.card_code
                """
                cursor.execute(query, (account,))
            else:
                query = """
                    SELECT 
                        c.card_code,
                        c.card_name,
                        c.card_set as set_name,
                        c.rarity,
                        COUNT(sc.id) as total_count,
                        c.image_path
                    FROM cards c
                    LEFT JOIN screenshot_cards sc ON c.id = sc.card_id
                    GROUP BY c.card_code, c.card_name, c.card_set, c.rarity, c.image_path
                    ORDER BY c.card_set, c.card_code
                """
                cursor.execute(query)

            return cursor.fetchall()
        finally:
            self._return_connection()

    def get_accounts_for_card(self, card_code: str) -> List[tuple]:
        """
        Get all accounts that have a specific card and their counts

        Args:
            card_code: Card code in format NAME_SET

        Returns:
            List[tuple]: List of tuples containing (account_name, count, screenshot_path, shinedust)
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()

            query = """
                SELECT 
                    s.account,
                    COUNT(sc.id) as card_count,
                    s.screenshot_path,
                    COALESCE(NULLIF(a.shinedust, ''), s.shinedust) as shinedust
                FROM screenshots s
                JOIN screenshot_cards sc ON s.id = sc.screenshot_id
                JOIN cards c ON sc.card_id = c.id
                LEFT JOIN accounts a ON s.account = a.account_name
                WHERE c.card_code = ?
                GROUP BY s.account, s.screenshot_path, a.shinedust, s.shinedust
                ORDER BY card_count DESC, s.account ASC
            """

            cursor.execute(query, (card_code,))
            return cursor.fetchall()
        finally:
            self._return_connection()

    def remove_card_from_account(self, card_code: str, account_name: str) -> bool:
        """
        Remove one instance of a card from an account.

        Args:
            card_code: Card code
            account_name: Account name

        Returns:
            bool: True if a card was removed, False otherwise
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            # Find one screenshot_cards entry to delete
            query = """
                DELETE FROM screenshot_cards 
                WHERE id = (
                    SELECT sc.id 
                    FROM screenshot_cards sc
                    JOIN screenshots s ON sc.screenshot_id = s.id
                    JOIN cards c ON sc.card_id = c.id
                    WHERE s.account = ? AND c.card_code = ?
                    LIMIT 1
                )
            """
            cursor.execute(query, (account_name, card_code))
            removed = cursor.rowcount > 0
            if removed:
                self._commit(conn)
            return removed
        finally:
            self._return_connection()

    def remove_card_from_account_precise(
        self, card_code: str, account_name: str, screenshot_path: str = None
    ) -> bool:
        """
        Remove one instance of a card from an account, optionally from a specific screenshot.

        Args:
            card_code: The card code to remove
            account_name: The account to remove it from
            screenshot_path: Optional path to the screenshot to remove from

        Returns:
            bool: True if a card was removed, False otherwise
        """
        if not screenshot_path:
            return self.remove_card_from_account(card_code, account_name)

        conn = self._get_connection()
        try:
            cursor = conn.cursor()

            # Find one instance of this card for this account and screenshot
            query = """
                DELETE FROM screenshot_cards 
                WHERE id = (
                    SELECT sc.id 
                    FROM screenshot_cards sc
                    JOIN screenshots s ON sc.screenshot_id = s.id
                    JOIN cards c ON sc.card_id = c.id
                    WHERE s.account = ? AND c.card_code = ? AND s.screenshot_path = ?
                    LIMIT 1
                )
            """
            cursor.execute(query, (account_name, card_code, screenshot_path))
            removed = cursor.rowcount > 0
            if removed:
                self._commit(conn)
                return True

            # Fallback to general removal if path-specific fails (e.g. if path was updated)
            return self.remove_card_from_account(card_code, account_name)
        finally:
            self._return_connection()

    def get_all_accounts(self) -> List[str]:
        """
        Get a list of all unique accounts in the database

        Returns:
            List[str]: List of account names
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT account FROM screenshots ORDER BY account")
            return [row[0] for row in cursor.fetchall() if row[0]]
        finally:
            self._return_connection()

    def get_total_cards_count(self) -> int:
        """
        Get total count of all cards found in screenshots

        Returns:
            int: Total count of cards
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM screenshot_cards")
            return cursor.fetchone()[0]
        finally:
            self._return_connection()

    def get_unique_cards_count(self) -> int:
        """
        Get count of unique cards (distinct card_name + card_set combinations)

        Returns:
            int: Count of unique cards
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COUNT(*) FROM (SELECT DISTINCT card_name, card_set FROM cards)"
            )
            return cursor.fetchone()[0]
        finally:
            self._return_connection()

    def get_total_packs_count(self) -> int:
        """
        Get total count of packs (screenshots)

        Returns:
            int: Total count of packs
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM screenshots")
            return cursor.fetchone()[0]
        finally:
            self._return_connection()

    def get_last_processed_timestamp(self) -> Optional[str]:
        """
        Get the timestamp of the last processed screenshot

        Returns:
            str: Last processed timestamp, or None if no screenshots processed
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT timestamp FROM screenshots 
                WHERE processed = 1 
                ORDER BY timestamp DESC 
                LIMIT 1
            """
            )
            result = cursor.fetchone()
            return result[0] if result else None
        finally:
            self._return_connection()

    def get_recent_activity(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get recent activity (processed screenshots)

        Args:
            limit: Maximum number of recent activities to return

        Returns:
            List[Dict]: List of recent activities with timestamp and description
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT timestamp, pack_screenshot, pack_type, card_counts 
                FROM screenshots 
                WHERE processed = 1 
                ORDER BY timestamp DESC 
                LIMIT ?
            """,
                (limit,),
            )

            activities = []
            for row in cursor.fetchall():
                timestamp, pack_screenshot, pack_type, card_counts = row
                description = f"Processed {pack_type} pack: {card_counts} cards"
                activities.append(
                    {
                        "timestamp": timestamp,
                        "description": description,
                        "pack_screenshot": pack_screenshot,
                    }
                )

            return activities
        finally:
            self._return_connection()

    def advanced_search_cards(
        self,
        card_name: str = None,
        card_set: str = None,
        rarity: str = None,
        pack_id: str = None,
    ) -> List[Dict[str, Any]]:
        """
        Advanced search for cards with multiple criteria

        Args:
            card_name: Card name to search for (partial match)
            card_set: Card set to filter by
            rarity: Rarity to filter by
            pack_id: Pack ID to filter by

        Returns:
            List[Dict]: List of matching card records with screenshot information
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()

            # Build query based on provided criteria
            query = """
                SELECT DISTINCT 
                    c.card_name, c.card_set, c.rarity, 
                    s.pack_screenshot, s.pack_type, s.timestamp,
                    c.image_path
                FROM cards c
                LEFT JOIN screenshot_cards sc ON c.id = sc.card_id
                LEFT JOIN screenshots s ON sc.screenshot_id = s.id
                WHERE 1=1
            """

            params = []

            # Add filters based on provided criteria
            if card_name:
                query += " AND c.card_name LIKE ?"
                params.append(f"%{card_name}%")

            if card_set and card_set != "All Sets":
                query += " AND c.card_set = ?"
                params.append(card_set)

            if rarity and rarity != "All Rarities":
                query += " AND c.rarity = ?"
                params.append(rarity)

            if pack_id:
                query += " AND s.pack_screenshot LIKE ?"
                params.append(f"%{pack_id}%")

            query += " ORDER BY c.card_name, c.card_set, s.timestamp DESC"

            cursor.execute(query, params)

            results = []
            for row in cursor.fetchall():
                (
                    card_name,
                    card_set,
                    rarity,
                    pack_screenshot,
                    pack_type,
                    timestamp,
                    image_path,
                ) = row
                results.append(
                    {
                        "card_name": card_name,
                        "set_name": card_set,
                        "rarity": rarity,
                        "pack_id": pack_screenshot,
                        "pack_type": pack_type,
                        "timestamp": timestamp,
                        "image_path": image_path,
                    }
                )

            return results
        finally:
            self._return_connection()

    def close(self):
        """Close the database connection for the current thread"""
        if hasattr(self.local_data, "connection"):
            try:
                self.local_data.connection.close()
                delattr(self.local_data, "connection")
            except:
                pass
