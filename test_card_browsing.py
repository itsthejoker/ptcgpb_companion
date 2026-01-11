#!/usr/bin/env python3

"""
Test script for card browsing functionality
This script tests the card browsing interface without requiring all dependencies
"""

import sys
import os

# Add the app directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

# Mock the image_processing module to avoid import errors
class MockImageProcessor:
    pass

# Create a mock image_processing module
import types
image_processing = types.ModuleType('image_processing')
image_processing.ImageProcessor = MockImageProcessor
sys.modules['app.image_processing'] = image_processing

# Now import the main application
from PyQt6.QtWidgets import QApplication
from app.main_window import MainWindow

def test_card_browsing():
    """Test the card browsing functionality"""
    print("Starting card browsing test...")
    
    # Create Qt application
    app = QApplication(sys.argv)
    
    # Create main window
    window = MainWindow()
    window.show()
    
    print("Main window created successfully")
    print("Testing card browsing interface...")
    
    # Test that the cards tab exists
    if hasattr(window, 'tab_widget'):
        print("✓ Tab widget found")
        
        # Find the Cards tab
        for i in range(window.tab_widget.count()):
            if window.tab_widget.tabText(i) == "Cards":
                print("✓ Cards tab found")
                
                # Test that the card table exists
                if hasattr(window, 'cards_table'):
                    print("✓ Card table found")
                    
                    # Test that the card model exists
                    if hasattr(window, 'card_model'):
                        print("✓ Card model found")
                        
                        # Test that filters exist
                        if hasattr(window, 'set_filter') and hasattr(window, 'rarity_filter'):
                            print("✓ Filters found")
                            
                            # Test that search box exists
                            if hasattr(window, 'search_box'):
                                print("✓ Search box found")
                                
                                print("\n✅ All card browsing components are present!")
                                print("The card browsing interface has been successfully implemented.")
                                
                                # Run the application
                                print("\nRunning application for manual testing...")
                                print("You can now:")
                                print("- Browse cards in the Cards tab")
                                print("- Use filters to narrow down results")
                                print("- Search for specific cards")
                                print("- View card details with tooltips")
                                
                                return app.exec()
                            else:
                                print("❌ Search box not found")
                        else:
                            print("❌ Filters not found")
                    else:
                        print("❌ Card model not found")
                else:
                    print("❌ Card table not found")
                break
        else:
            print("❌ Cards tab not found")
    else:
        print("❌ Tab widget not found")
    
    print("❌ Card browsing test failed")
    return 1

if __name__ == "__main__":
    sys.exit(test_card_browsing())