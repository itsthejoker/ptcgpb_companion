#!/usr/bin/env python3

"""
Simple test script to verify that the database connection pooling works correctly
with multiple threads accessing the database simultaneously.
"""

import threading
import time
from database import Database

def test_concurrent_reads(thread_id, db, num_operations=5):
    """Test concurrent database reads"""
    try:
        print(f"Thread {thread_id}: Starting {num_operations} read operations")
        
        for i in range(num_operations):
            # Test various database read operations
            total_screenshots = db.get_total_screenshots_count()
            processed_count = db.get_processed_screenshots_count()
            
            if i == 0:  # Only print first result to reduce output
                print(f"Thread {thread_id}: Read {i+1}/{num_operations} - Total: {total_screenshots}, Processed: {processed_count}")
        
        print(f"Thread {thread_id}: Completed successfully")
        return True
        
    except Exception as e:
        print(f"Thread {thread_id}: ERROR - {e}")
        return False

def main():
    print("Testing database connection pooling with concurrent reads...")
    
    # Initialize database
    db = Database()
    
    # Create multiple threads to simulate concurrent access
    num_threads = 4
    threads = []
    results = []
    
    print(f"Starting {num_threads} concurrent threads...")
    
    # Start threads
    for i in range(num_threads):
        thread = threading.Thread(target=lambda tid: results.append(test_concurrent_reads(tid, db, 3)), args=(i,))
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