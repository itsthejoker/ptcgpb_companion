#!/usr/bin/env python3

import sys
import os
sys.path.append('.')

import cv2
import numpy as np
from PIL import Image
from image_processing import ImageProcessor

def visual_debug():
    """Create visual debug images to understand the matching issue"""
    
    # Test with the first example
    example_path = 'examples/20251206235755_3_Tradeable_11_packs.png'
    
    # Initialize processor
    processor = ImageProcessor()
    
    # Load and preprocess the screenshot
    img = Image.open(example_path)
    img_array = np.array(img)
    
    # Convert to grayscale like the processor does
    if len(img_array.shape) == 3 and img_array.shape[2] == 4:  # RGBA
        rgb = cv2.cvtColor(img_array, cv2.COLOR_RGBA2RGB)
        gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    elif len(img_array.shape) == 3:  # RGB
        gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
    else:  # Already grayscale
        gray = img_array
    
    # Get card positions
    card_positions = processor._detect_card_positions(gray)
    
    # Save the original grayscale image
    cv2.imwrite('debug_original_gray.png', gray)
    
    # Extract and save individual card regions
    for i, (x, y, w, h) in enumerate(card_positions[:5]):
        card_region = gray[y:y+h, x:x+w]
        cv2.imwrite(f'debug_card_{i+1}_region.png', card_region)
        
        # Also save the resized version that's used for matching
        target_width = 40
        aspect_ratio = card_region.shape[1] / card_region.shape[0]
        target_height = int(target_width / aspect_ratio)
        resized_region = cv2.resize(card_region, (target_width, target_height))
        cv2.imwrite(f'debug_card_{i+1}_resized.png', resized_region)
    
    # Save some template images for comparison
    expected_cards = ['A4_117', 'A4_107', 'A4_110']
    
    for card_name in expected_cards:
        set_name = card_name.split('_')[0]
        if set_name in processor.card_database and card_name in processor.card_database[set_name]:
            template = processor.card_database[set_name][card_name]
            cv2.imwrite(f'debug_template_{card_name}.png', template)
    
    # Save the cover template too
    if 'A4' in processor.card_database and 'cover' in processor.card_database['A4']:
        cover_template = processor.card_database['A4']['cover']
        cv2.imwrite('debug_template_A4_cover.png', cover_template)
    
    print("Debug images saved. Compare:")
    print("- debug_card_*_region.png (original card regions from screenshot)")
    print("- debug_card_*_resized.png (resized card regions used for matching)")
    print("- debug_template_*.png (template images from database)")

if __name__ == '__main__':
    visual_debug()