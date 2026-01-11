#!/usr/bin/env python3
"""
Test script to verify the database optimization for screenshot duplicate checking.
This script will:
1. Create a test database
2. Add some test data
3. Test the duplicate checking performance
4. Verify no data is lost
"""

import sqlite3
import time
import os
from database import Database

def test_duplicate_checking_performance():
    """Test the performance of duplicate checking with and without the index"""
    
    # Create a test database
    test_db_path = 'test_optimization.db'
    
    # Clean up if it exists
    if os.path.exists(test_db_path):
        os.remove(test_db_path)
    
    print("Creating test database...")
    db = Database(test_db_path)
    
    # Add some test data
    test_screenshots = []
    for i in range(1000):
        test_screenshot = {
            'Timestamp': '2023-01-01 12:00:00',
            'OriginalFilename': f'test_{i}.png',
            'CleanFilename': f'test_{i}_clean.png',
            'DeviceAccount': 'test_device',
            'PackType': 'A1',
            'CardTypes': 'Common',
            'CardCounts': '5',
            'PackScreenshot': f'unique_screenshot_hash_{i}',
            'Shinedust': '100'
        }
        test_screenshots.append(test_screenshot)
    
    print("Adding test data...")
    start_time = time.time()
    
    # Add all test data
    for screenshot in test_screenshots:
        db.add_screenshot(screenshot)
    
    end_time = time.time()
    print(f"Added {len(test_screenshots)} screenshots in {end_time - start_time:.2f} seconds")
    
    # Now test duplicate checking performance
    print("\nTesting duplicate checking performance...")
    
    # Test with existing screenshots (should be fast with index)
    start_time = time.time()
    
    duplicate_count = 0
    for screenshot in test_screenshots:
        screenshot_id, is_new = db.add_screenshot(screenshot)
        if not is_new:
            duplicate_count += 1
    
    end_time = time.time()
    print(f"Checked {len(test_screenshots)} screenshots for duplicates in {end_time - start_time:.2f} seconds")
    print(f"Found {duplicate_count} duplicates (should be {len(test_screenshots)})")
    
    # Test with new screenshots (should be fast)
    new_screenshots = []
    for i in range(1000, 2000):
        new_screenshot = {
            'Timestamp': '2023-01-01 12:00:00',
            'OriginalFilename': f'test_{i}.png',
            'CleanFilename': f'test_{i}_clean.png',
            'DeviceAccount': 'test_device',
            'PackType': 'A1',
            'CardTypes': 'Common',
            'CardCounts': '5',
            'PackScreenshot': f'unique_screenshot_hash_{i}',
            'Shinedust': '100'
        }
        new_screenshots.append(new_screenshot)
    
    print("\nTesting new screenshot insertion performance...")
    start_time = time.time()
    
    new_count = 0
    for screenshot in new_screenshots:
        screenshot_id, is_new = db.add_screenshot(screenshot)
        if is_new:
            new_count += 1
    
    end_time = time.time()
    print(f"Added {new_count} new screenshots in {end_time - start_time:.2f} seconds")
    
    # Verify data integrity
    print("\nVerifying data integrity...")
    total_screenshots = db.get_total_screenshots_count()
    print(f"Total screenshots in database: {total_screenshots}")
    
    # Check that we have the expected number
    expected_count = len(test_screenshots) + new_count
    if total_screenshots == expected_count:
        print("✓ Data integrity verified - correct number of screenshots")
    else:
        print(f"✗ Data integrity issue - expected {expected_count}, got {total_screenshots}")
    
    # Check that all original screenshots are still there
    cursor = sqlite3.connect(test_db_path).cursor()
    cursor.execute('SELECT COUNT(*) FROM screenshots WHERE pack_screenshot LIKE "unique_screenshot_hash_%"')
    actual_unique_count = cursor.fetchone()[0]
    
    if actual_unique_count == expected_count:
        print("✓ All test screenshots are present in database")
    else:
        print(f"✗ Missing screenshots - expected {expected_count}, found {actual_unique_count}")
    
    # Clean up
    os.remove(test_db_path)
    print(f"\nTest completed successfully!")

if __name__ == "__main__":
    test_duplicate_checking_performance()