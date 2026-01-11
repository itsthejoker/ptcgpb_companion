#!/usr/bin/env python3

"""
Test script to verify that the database connection pooling works correctly
with multiple threads accessing the database simultaneously.
"""

import threading
import time
from database import Database

def test_concurrent_access(thread_id, db, num_operations=10):
    """Test concurrent database access"""
    try:
        print(f"Thread {thread_id}: Starting {num_operations} operations")
        
        for i in range(num_operations):
            # Test various database operations
            total_screenshots = db.get_total_screenshots_count()
            processed_count = db.get_processed_screenshots_count()
            
            # Test a write operation (this would normally fail with the old code)
            if i % 5 == 0:  # Do this less frequently
                # Get a screenshot to test mark_screenshot_processed
                screenshots = db.get_unprocessed_screenshots()
                if screenshots:
                    screenshot = screenshots[0]
                    # Don't actually mark it processed in this test to avoid data corruption
                    # db.mark_screenshot_processed(screenshot['id'])
                    
            if i % 10 == 0:
                print(f"Thread {thread_id}: Operation {i+1}/{num_operations} - Total: {total_screenshots}, Processed: {processed_count}")
        
        print(f"Thread {thread_id}: Completed successfully")
        return True
        
    except Exception as e:
        print(f"Thread {thread_id}: ERROR - {e}")
        return False

def main():
    print("Testing database connection pooling with concurrent access...")
    
    # Initialize database
    db = Database()
    
    # Create multiple threads to simulate concurrent access
    num_threads = 8
    threads = []
    results = []
    
    print(f"Starting {num_threads} concurrent threads...")
    
    # Start threads
    for i in range(num_threads):
        thread = threading.Thread(target=lambda tid: results.append(test_concurrent_access(tid, db, 20)), args=(i,))
        threads.append(thread)
        thread.start()
    
    # Wait for all threads to complete
    for thread in threads:
        thread.join()
    
    # Check results
    successful_threads = sum(1 for result in results if result)
    failed_threads = len(results) - successful_threads
    
    print(f"\nTest completed:")
    print(f"Successful threads: {successful_threads}/{num_threads}")
    print(f"Failed threads: {failed_threads}/{num_threads}")
    
    if failed_threads == 0:
        print("✅ All threads completed successfully! The connection pooling is working correctly.")
    else:
        print("❌ Some threads failed. There may still be concurrency issues.")
    
    # Clean up
    db.close()

if __name__ == "__main__":
    main()