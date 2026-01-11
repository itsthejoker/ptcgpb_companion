#!/usr/bin/env python3
"""
Phase 1 Test Script

Test script to verify that Phase 1 foundation is working correctly.
This script tests the core functionality without requiring the full UI.
"""

import sys
import os
import tempfile
import shutil

# Add app directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_database_initialization():
    """Test database initialization"""
    print("Testing database initialization...")
    
    # Create temporary directory for test database
    temp_dir = tempfile.mkdtemp()
    test_db_path = os.path.join(temp_dir, 'test_cardcounter.db')
    
    try:
        from app.database import Database
        
        # Test database creation
        db = Database(test_db_path)
        print("✅ Database created successfully")
        
        # Test basic operations
        test_data = {
            'Timestamp': '2024-01-01 12:00:00',
            'OriginalFilename': 'test.png',
            'CleanFilename': 'test_clean.png',
            'DeviceAccount': 'test_account',
            'PackType': 'Tradeable',
            'CardTypes': 'A1,A2',
            'CardCounts': '5,3',
            'PackScreenshot': 'test_screenshot.png',
            'Shinedust': '100'
        }
        
        # Test adding screenshot
        screenshot_id, is_new = db.add_screenshot(test_data)
        assert is_new == True, "Screenshot should be new"
        assert screenshot_id > 0, "Screenshot ID should be positive"
        print("✅ Screenshot added successfully")
        
        # Test adding card
        card_id = db.add_card('test_card', 'A1', 'test_path.png', 'Common')
        assert card_id > 0, "Card ID should be positive"
        print("✅ Card added successfully")
        
        # Test adding screenshot-card relationship
        db.add_screenshot_card(screenshot_id, card_id, 1, 0.95)
        print("✅ Screenshot-card relationship added successfully")
        
        # Test marking as processed
        db.mark_screenshot_processed(screenshot_id)
        print("✅ Screenshot marked as processed")
        
        # Test query operations
        screenshots = db.get_all_screenshots()
        assert len(screenshots) == 1, "Should have 1 screenshot"
        print("✅ Query operations working")
        
        # Test counts
        total_count = db.get_total_screenshots_count()
        processed_count = db.get_processed_screenshots_count()
        assert total_count == 1, "Total count should be 1"
        assert processed_count == 1, "Processed count should be 1"
        print("✅ Count operations working")
        
        # Clean up
        db.close()
        print("✅ Database closed successfully")
        
        return True
        
    except Exception as e:
        print(f"❌ Database test failed: {e}")
        return False
    finally:
        # Clean up temporary directory
        shutil.rmtree(temp_dir, ignore_errors=True)

def test_utils():
    """Test utility functions"""
    print("\nTesting utility functions...")
    
    try:
        from app.utils import get_portable_path, PortableSettings
        
        # Test portable path
        path = get_portable_path('test', 'path')
        assert path.endswith('test/path'), "Portable path should end with test/path"
        print("✅ Portable path function working")
        
        # Test settings
        settings = PortableSettings()
        settings.set_setting('test_key', 'test_value')
        value = settings.get_setting('test_key')
        assert value == 'test_value', "Settings should work"
        print("✅ Settings management working")
        
        return True
        
    except Exception as e:
        print(f"❌ Utility test failed: {e}")
        return False

def test_imports():
    """Test that all modules can be imported"""
    print("\nTesting module imports...")
    
    try:
        # Test main imports
        from app.main_window import MainWindow
        from app.database import Database
        from app.utils import check_dependencies
        from app.image_processing import ImageProcessor
        
        print("✅ All modules imported successfully")
        return True
        
    except Exception as e:
        print(f"❌ Import test failed: {e}")
        return False

def main():
    """Run all tests"""
    print("🧪 Running Phase 1 Tests")
    print("=" * 50)
    
    tests = [
        test_imports,
        test_utils,
        test_database_initialization,
    ]
    
    results = []
    for test in tests:
        results.append(test())
    
    print("\n" + "=" * 50)
    print("📊 Test Results:")
    
    passed = sum(results)
    total = len(results)
    
    if passed == total:
        print(f"🎉 All {total} tests passed! Phase 1 foundation is working correctly.")
        return 0
    else:
        print(f"❌ {total - passed} out of {total} tests failed.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
