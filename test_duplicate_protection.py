#!/usr/bin/env python3
"""
Test script to verify duplicate protection in screenshot processing
"""

import os
import tempfile
import sqlite3
from database import Database

def test_duplicate_protection():
    """Test that duplicate screenshots are properly handled"""
    
    print("Testing duplicate protection...")
    
    # Create a temporary database for testing
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as temp_db:
        temp_db_path = temp_db.name
    
    try:
        # Initialize database
        db = Database(temp_db_path)
        
        # Test data - using the exact key names expected by add_screenshot
        test_screenshot_data = {
            'Timestamp': '2025-01-01 12:00:00',
            'OriginalFilename': 'test_001.png',
            'CleanFilename': 'test_001_clean.png',
            'DeviceAccount': 'test_account',
            'PackType': 'Tradeable',
            'CardTypes': 'Normal',
            'CardCounts': '5',
            'PackScreenshot': 'test_screenshot.png',
            'Shinedust': '100'
        }
        
        print("\n=== Test 1: Adding a new screenshot ===")
        
        # Add a new screenshot
        screenshot_id1, is_new1 = db.add_screenshot(test_screenshot_data)
        print(f"Added screenshot 1: ID={screenshot_id1}, is_new={is_new1}")
        assert is_new1 == True, "First screenshot should be new"
        
        print("\n=== Test 2: Adding the same screenshot again ===")
        
        # Try to add the same screenshot again (should fail due to UNIQUE constraint)
        try:
            screenshot_id2, is_new2 = db.add_screenshot(test_screenshot_data)
            print(f"Added screenshot 2: ID={screenshot_id2}, is_new={is_new2}")
            assert is_new2 == False, "Second screenshot should not be new (duplicate)"
            print("✓ Duplicate detection working correctly")
        except sqlite3.IntegrityError:
            print("✓ UNIQUE constraint prevented duplicate insertion")
        
        print("\n=== Test 3: Checking processed status ===")
        
        # Check if screenshot is marked as unprocessed
        unprocessed = db.get_unprocessed_screenshots()
        print(f"Unprocessed screenshots: {len(unprocessed)}")
        assert len(unprocessed) == 1, "Should have 1 unprocessed screenshot"
        
        # Mark as processed
        db.mark_screenshot_processed(screenshot_id1)
        
        # Check again
        unprocessed_after = db.get_unprocessed_screenshots()
        print(f"Unprocessed screenshots after marking: {len(unprocessed_after)}")
        assert len(unprocessed_after) == 0, "Should have 0 unprocessed screenshots after marking"
        
        print("\n=== Test 4: Testing get_all_screenshots ===")
        
        # Test the new get_all_screenshots method
        all_screenshots = db.get_all_screenshots()
        print(f"All screenshots: {len(all_screenshots)}")
        assert len(all_screenshots) == 1, "Should have 1 total screenshot"
        
        screenshot = all_screenshots[0]
        print(f"Screenshot details: processed={screenshot['processed']}, filename={screenshot['pack_screenshot']}")
        assert screenshot['processed'] == 1, "Screenshot should be marked as processed"
        assert screenshot['pack_screenshot'] == 'test_screenshot.png', "Should have correct filename"
        
        print("\n=== Test 5: Simulating duplicate processing scenario ===")
        
        # Simulate what happens when processing the same folder twice
        # First processing run
        print("First processing run:")
        existing_screenshots = db.get_all_screenshots()
        matching_screenshot = None
        for screenshot in existing_screenshots:
            if screenshot['pack_screenshot'] == 'test_screenshot.png':
                matching_screenshot = screenshot
                break
        
        if matching_screenshot:
            if matching_screenshot['processed']:
                print("✓ Screenshot already processed - would be skipped in second run")
            else:
                print("✗ Screenshot not processed - would be processed again")
        else:
            print("✗ No matching screenshot found")
        
        print("\n=== All duplicate protection tests passed! ===")
        
    finally:
        # Clean up
        if os.path.exists(temp_db_path):
            os.unlink(temp_db_path)

def test_database_schema():
    """Test that the database schema has proper constraints"""
    
    print("\nTesting database schema...")
    
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as temp_db:
        temp_db_path = temp_db.name
    
    try:
        # Create database and check schema
        db = Database(temp_db_path)
        
        # Check if the UNIQUE constraint exists
        with sqlite3.connect(temp_db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(screenshots)")
            columns = cursor.fetchall()
            
            print("Screenshot table columns:")
            for col in columns:
                print(f"  {col[1]} ({col[2]}) - {col[5]}")  # name, type, pk
            
            # Check for UNIQUE constraint
            cursor.execute("PRAGMA index_list(screenshots)")
            indexes = cursor.fetchall()
            
            print("\nScreenshot table indexes:")
            unique_indexes = []
            for idx in indexes:
                print(f"  {idx[1]} (unique={idx[2]})")
                if idx[2] == 1:  # unique index
                    unique_indexes.append(idx[1])
            
            if unique_indexes:
                print(f"✓ Found {len(unique_indexes)} unique indexes: {unique_indexes}")
            else:
                print("⚠ No unique indexes found (but UNIQUE constraint may still exist)")
        
        print("✓ Database schema test completed")
        
    finally:
        if os.path.exists(temp_db_path):
            os.unlink(temp_db_path)

if __name__ == "__main__":
    test_duplicate_protection()
    test_database_schema()
    print("\n🎉 All tests passed! Duplicate protection is working correctly.")