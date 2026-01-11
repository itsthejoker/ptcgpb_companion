#!/usr/bin/env python3
"""
Comparison test to demonstrate the performance improvement from adding the index.
This script will test the duplicate checking performance with and without the index.
"""

import sqlite3
import time
import os

def test_without_index():
    """Test performance without the pack_screenshot index"""
    test_db_path = 'test_without_index.db'
    
    # Clean up if it exists
    if os.path.exists(test_db_path):
        os.remove(test_db_path)
    
    print("Testing WITHOUT index...")
    
    # Create database without the pack_screenshot index
    conn = sqlite3.connect(test_db_path)
    cursor = conn.cursor()
    
    # Create tables
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS screenshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pack_screenshot TEXT UNIQUE,
            other_data TEXT
        )
    ''')
    
    # Only create the old indexes (without pack_screenshot index)
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_screenshots_clean_filename ON screenshots(other_data)')
    
    conn.commit()
    
    # Add test data
    print("Adding test data...")
    start_time = time.time()
    
    for i in range(1000):
        cursor.execute('INSERT INTO screenshots (pack_screenshot, other_data) VALUES (?, ?)', 
                      (f'unique_screenshot_hash_{i}', f'data_{i}'))
    
    conn.commit()
    end_time = time.time()
    print(f"Added 1000 screenshots in {end_time - start_time:.2f} seconds")
    
    # Test duplicate checking performance
    print("Testing duplicate checking performance...")
    start_time = time.time()
    
    duplicate_count = 0
    for i in range(1000):
        cursor.execute('SELECT id FROM screenshots WHERE pack_screenshot = ?', (f'unique_screenshot_hash_{i}',))
        if cursor.fetchone():
            duplicate_count += 1
    
    end_time = time.time()
    without_index_time = end_time - start_time
    print(f"Checked 1000 screenshots for duplicates in {without_index_time:.2f} seconds")
    print(f"Found {duplicate_count} duplicates")
    
    conn.close()
    os.remove(test_db_path)
    
    return without_index_time

def test_with_index():
    """Test performance with the pack_screenshot index"""
    test_db_path = 'test_with_index.db'
    
    # Clean up if it exists
    if os.path.exists(test_db_path):
        os.remove(test_db_path)
    
    print("\nTesting WITH index...")
    
    # Create database with the pack_screenshot index
    conn = sqlite3.connect(test_db_path)
    cursor = conn.cursor()
    
    # Create tables
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS screenshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pack_screenshot TEXT UNIQUE,
            other_data TEXT
        )
    ''')
    
    # Create the new index on pack_screenshot
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_screenshots_clean_filename ON screenshots(other_data)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_screenshots_pack_screenshot ON screenshots(pack_screenshot)')
    
    conn.commit()
    
    # Add test data
    print("Adding test data...")
    start_time = time.time()
    
    for i in range(1000):
        cursor.execute('INSERT INTO screenshots (pack_screenshot, other_data) VALUES (?, ?)', 
                      (f'unique_screenshot_hash_{i}', f'data_{i}'))
    
    conn.commit()
    end_time = time.time()
    print(f"Added 1000 screenshots in {end_time - start_time:.2f} seconds")
    
    # Test duplicate checking performance
    print("Testing duplicate checking performance...")
    start_time = time.time()
    
    duplicate_count = 0
    for i in range(1000):
        cursor.execute('SELECT id FROM screenshots WHERE pack_screenshot = ?', (f'unique_screenshot_hash_{i}',))
        if cursor.fetchone():
            duplicate_count += 1
    
    end_time = time.time()
    with_index_time = end_time - start_time
    print(f"Checked 1000 screenshots for duplicates in {with_index_time:.2f} seconds")
    print(f"Found {duplicate_count} duplicates")
    
    conn.close()
    os.remove(test_db_path)
    
    return with_index_time

def main():
    """Run the performance comparison"""
    print("Performance Comparison: Duplicate Checking with vs without Index")
    print("=" * 60)
    
    without_index_time = test_without_index()
    with_index_time = test_with_index()
    
    print("\n" + "=" * 60)
    print("RESULTS:")
    print(f"Without index: {without_index_time:.3f} seconds")
    print(f"With index:    {with_index_time:.3f} seconds")
    
    if with_index_time < without_index_time:
        speedup = without_index_time / with_index_time
        improvement = ((without_index_time - with_index_time) / without_index_time) * 100
        print(f"\n✓ IMPROVEMENT: {speedup:.1f}x faster ({improvement:.1f}% improvement)")
    else:
        print("\n✗ No significant improvement detected")

if __name__ == "__main__":
    main()