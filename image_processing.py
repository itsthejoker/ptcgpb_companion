import os
import cv2
import numpy as np
from typing import List, Dict, Tuple
from PIL import Image

class ImageProcessor:
    def __init__(self, card_imgs_dir: str = 'card_imgs'):
        self.card_imgs_dir = card_imgs_dir
        self.card_database = self._load_card_database()
        self.card_names = self._load_card_names()
    
    def _load_card_database(self) -> Dict[str, Dict[str, np.ndarray]]:
        """Load all card images from the card_imgs directory"""
        card_db = {}
        
        if not os.path.exists(self.card_imgs_dir):
            print(f"Card images directory not found: {self.card_imgs_dir}")
            return card_db
        
        # Walk through all subdirectories (sets)
        for set_name in os.listdir(self.card_imgs_dir):
            set_path = os.path.join(self.card_imgs_dir, set_name)
            
            if not os.path.isdir(set_path):
                continue
            
            # Initialize set in database
            if set_name not in card_db:
                card_db[set_name] = {}
            
            # Load all card images in this set
            for card_file in os.listdir(set_path):
                if card_file.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')):
                    card_name = os.path.splitext(card_file)[0]
                    card_path = os.path.join(set_path, card_file)
                    
                    try:
                        # Load and preprocess the card image
                        card_image = self._load_and_preprocess_card(card_path)
                        if card_image is not None:
                            card_db[set_name][card_name] = card_image
                    except Exception as e:
                        print(f"Error loading card {card_name} from {set_name}: {e}")
        
        return card_db
    
    def _load_card_names(self) -> Dict[str, str]:
        """Load card names mapping from names.py"""
        try:
            import names
            return names.cards
        except ImportError:
            print("names.py not found, using original card names")
            return {}
    
    def _get_display_name(self, card_name: str, set_name: str) -> str:
        """Get the display name for a card using the names mapping"""
        # Try to find the card in the names mapping
        # The format in names.py is like "A1_1" for set A1, card 1
        mapping_key = f"{set_name}_{card_name}"
        
        if mapping_key in self.card_names:
            return self.card_names[mapping_key]
        else:
            # Fallback to original name if not found
            return card_name
    
    def _load_and_preprocess_card(self, card_path: str) -> np.ndarray:
        """Load and preprocess a single card image at full resolution"""
        try:
            # Load image using PIL and convert to RGB
            pil_image = Image.open(card_path)
            
            # Convert to numpy array
            image = np.array(pil_image)
            
            # Convert to RGB if needed (from RGBA or grayscale)
            if len(image.shape) == 3 and image.shape[2] == 4:  # RGBA
                image = cv2.cvtColor(image, cv2.COLOR_RGBA2RGB)
            elif len(image.shape) == 2:  # Grayscale
                image = cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)
            
            # Keep the card at its original resolution for better matching accuracy
            # Full-size cards are typically 367x512 pixels
            return image
        except Exception as e:
            print(f"Error processing card image {card_path}: {e}")
            return None
    
    def _preprocess_screenshot(self, screenshot_path: str) -> np.ndarray:
        """Load and preprocess a screenshot image"""
        try:
            # Load image
            pil_image = Image.open(screenshot_path)
            image = np.array(pil_image)
            
            # Convert to RGB if needed (from RGBA)
            if len(image.shape) == 3 and image.shape[2] == 4:  # RGBA
                image = cv2.cvtColor(image, cv2.COLOR_RGBA2RGB)
            elif len(image.shape) == 2:  # Grayscale
                image = cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)
            
            return image
        except Exception as e:
            print(f"Error processing screenshot {screenshot_path}: {e}")
            return None
    
    def _detect_card_positions(self, screenshot: np.ndarray) -> List[Tuple[int, int, int, int]]:
        """Detect card positions in a screenshot using the exact pixel placements from the comments"""
        # IMPORTANT!!! Based on the comments, use these exact pixel positions:
        # Screenshots are 240x227 pixels with cards arranged as:
        # - 3 cards on top row
        # - 2 or 3 cards on bottom row
        
        # Card layout looks like this:
        # position 1: (x=0, y=5, w=75, h=106)
        # position 2: (x=81, y=5, w=75, h=106)
        # position 3: (x=164, y=5, w=75, h=106)

        # IF THREE CARDS ON BOTTOM ROW:
        # position 4: (x=0, y=121, w=75, h=106)
        # position 5: (x=81, y=121, w=75, h=106)
        # position 6: (x=164, y=121, w=75, h=106)

        # IF TWO CARDS ON BOTTOM ROW:
        # position 4: (x=39, y=121, w=75, h=106)
        # position 5: (x=124, y=121, w=75, h=106)

        # HOW TO DETECT IF THERE ARE TWO OR THREE BOTTOM IMAGES:
        # Check the average color of the following rectangle:
        # (x=0, y=124, w=30, h=50)
        # If there are only two cards on the bottom row, the color will be very close to #e7f0f7.
        # If there are three cards on the bottom row, the color will be completely random.

        height, width = screenshot.shape[:2]  # Handle both grayscale and color images
        
        # Start with the known top row positions (always 3 cards)
        top_row_positions = [
            (0, 5, 75, 106),     # position 1
            (81, 5, 75, 106),    # position 2
            (164, 5, 75, 106)    # position 3
        ]
        
        # HOW TO DETECT IF THERE ARE TWO OR THREE BOTTOM IMAGES:
        # Check the average color of the following rectangle:
        # (x=0, y=124, w=30, h=50)
        # If there are only two cards on the bottom row, the color will be very close to #e7f0f7.
        # If there are three cards on the bottom row, the color will be completely random.
        
        # Check the detection rectangle to determine layout
        detection_rect = (0, 124, 30, 50)
        x, y, w, h = detection_rect
        
        if y + h <= height and x + w <= width:  # Check bounds
            detection_region = screenshot[y:y+h, x:x+w]
            
            # Calculate average color of the detection region
            avg_color = np.mean(detection_region)
            
            # Convert #e7f0f7 to grayscale for comparison
            # #e7f0f7 in RGB is (231, 240, 247), grayscale ≈ 239
            background_threshold = 235  # Allow some tolerance
            
            # If the average color is close to the background color, there are 2 cards
            # If it's random (different from background), there are 3 cards
            if avg_color > background_threshold:
                # 2 cards on bottom row (total 5 cards)
                bottom_positions = [
                    (39, 121, 75, 106),    # position 4
                    (124, 121, 75, 106)    # position 5
                ]
            else:
                # 3 cards on bottom row (total 6 cards)
                bottom_positions = [
                    (0, 121, 75, 106),     # position 4
                    (81, 121, 75, 106),    # position 5
                    (164, 121, 75, 106)   # position 6
                ]
        else:
            # Fallback to 2-card layout if detection rectangle is out of bounds
            bottom_positions = [
                (39, 121, 75, 106),    # position 4
                (124, 121, 75, 106)    # position 5
            ]
        
        # Combine top and bottom positions
        all_positions = top_row_positions + bottom_positions
        
        return all_positions
    

    
    def identify_cards_in_screenshot(self, screenshot_path: str) -> List[Dict[str, any]]:
        """Identify cards in a screenshot with set-aware recognition and consistency checking"""
        import logging
        logger = logging.getLogger(__name__)
        
        logger.info(f"Processing screenshot: {screenshot_path}")
        
        # Load and preprocess screenshot
        screenshot = self._preprocess_screenshot(screenshot_path)
        
        if screenshot is None:
            logger.warning(f"Failed to load screenshot: {screenshot_path}")
            return []
        
        logger.info(f"Screenshot loaded: {screenshot.shape}")
        
        # Detect card positions
        card_positions = self._detect_card_positions(screenshot)
        
        logger.info(f"Detected {len(card_positions)} card positions")
        
        # Phase 1: Run detection once on all cards without set filtering
        initial_results = []
        
        for i, (x, y, w, h) in enumerate(card_positions):
            logger.info(f"Processing card {i+1} at position ({x}, {y}) with size {w}x{h}")
            
            # Extract card region
            card_region = screenshot[y:y+h, x:x+w]
            
            # Find best match across all sets
            best_match = self._find_best_card_match(card_region)
            
            if best_match:
                # Get the display name for this card
                display_name = self._get_display_name(best_match['card_name'], best_match['card_set'])
                logger.info(f"Found card: {display_name} (confidence: {best_match['confidence']:.2f})")
                initial_results.append({
                    'position': i + 1,
                    'card_name': best_match['card_name'],  # Use original card name (e.g., "B1_68")
                    'card_set': best_match['card_set'],
                    'confidence': best_match['confidence'],
                    'display_name': display_name,  # Store display name separately
                    'x': x,
                    'y': y,
                    'width': w,
                    'height': h
                })
            else:
                logger.info(f"No card match found for position {i+1}")
                initial_results.append(None)
        
        # Phase 2: Verify set consistency and re-scan inconsistent cards
        results = self._verify_and_fix_set_consistency(screenshot, card_positions, initial_results)
        
        logger.info(f"Identified {len(results)} cards in screenshot")
        return results
    
    def _find_best_card_match(self, card_region: np.ndarray, preferred_set: str = None) -> Dict[str, any]:
        """Find the best matching card in the database for a card region"""
        import logging
        logger = logging.getLogger(__name__)
        
        best_match = None
        best_score = -1
        
        # Multi-stage matching for better performance:
        # 1. Quick search at reduced resolution to identify likely set
        # 2. Detailed search at full resolution within the identified set
        
        # Stage 1: Quick search at reduced resolution
        quick_target_width = 80  # Reduced resolution for quick search
        aspect_ratio = card_region.shape[1] / card_region.shape[0]
        quick_target_height = int(quick_target_width / aspect_ratio)
        quick_region = cv2.resize(card_region, (quick_target_width, quick_target_height))
        
        # Convert to grayscale for quick search
        if len(quick_region.shape) == 3:
            quick_gray = cv2.cvtColor(quick_region, cv2.COLOR_RGB2GRAY)
        else:
            quick_gray = quick_region
        
        # Quick search to identify likely set
        set_scores = {}
        for set_name, cards in self.card_database.items():
            for card_name, template in cards.items():
                # Create a quick version of the template
                quick_template = cv2.resize(template, (quick_target_width, quick_target_height))
                if len(quick_template.shape) == 3:
                    quick_template_gray = cv2.cvtColor(quick_template, cv2.COLOR_RGB2GRAY)
                else:
                    quick_template_gray = quick_template
                
                result = cv2.matchTemplate(quick_gray, quick_template_gray, cv2.TM_CCORR_NORMED)
                min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
                
                if max_val > set_scores.get(set_name, 0):
                    set_scores[set_name] = max_val
        
        # Determine the most likely set from quick search
        likely_set = None
        if set_scores:
            likely_set = max(set_scores.items(), key=lambda x: x[1])[0]
            logger.info(f"Quick search identified likely set: {likely_set} (score: {set_scores[likely_set]:.3f})")
        
        # Stage 2: Detailed search at full resolution
        # Use the likely set from quick search or the preferred set if specified
        search_set = preferred_set or likely_set
        
        # Upscale card region to match full card resolution for detailed matching
        target_width, target_height = 367, 512  # Standard full card size
        upscaled_region = cv2.resize(card_region, (target_width, target_height))
        
        # Convert to grayscale once for efficiency
        if len(upscaled_region.shape) == 3:
            upscaled_gray = cv2.cvtColor(upscaled_region, cv2.COLOR_RGB2GRAY)
        else:
            upscaled_gray = upscaled_region
        
        # Detailed search in the identified set
        if search_set and search_set in self.card_database:
            logger.info(f"Performing detailed search in set: {search_set}")
            
            for card_name, template in self.card_database[search_set].items():
                # Template matching - use TM_CCORR_NORMED for better results
                # Convert template to grayscale
                if len(template.shape) == 3:
                    template_gray = cv2.cvtColor(template, cv2.COLOR_RGB2GRAY)
                else:
                    template_gray = template
                
                result = cv2.matchTemplate(upscaled_gray, template_gray, cv2.TM_CCORR_NORMED)
                min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
                
                # If this is the best match so far
                if max_val > best_score:
                    best_score = max_val
                    # Keep the full card name (e.g., "B1_68")
                    clean_card_name = card_name
                    
                    best_match = {
                        'card_name': clean_card_name,
                        'card_set': search_set,
                        'confidence': max_val
                    }
        else:
            logger.info("No set identified for detailed search, skipping")
        
        # Debug: Log the best match found
        if best_match:
            logger.info(f"Best match: {best_match['card_name']} (confidence: {best_match['confidence']:.2f})")
            if best_match['confidence'] <= 0.7:
                logger.info(f"Match below confidence threshold (0.7): {best_match['confidence']:.2f}")
        else:
            logger.info("No match found in card database")
        
        # Only return matches with reasonable confidence
        # Lowered threshold for testing - can be adjusted based on results
        if best_match and best_match['confidence'] > 0.3:  # 50% confidence threshold
            return best_match
        
        return None

    def _verify_and_fix_set_consistency(self, screenshot: np.ndarray, card_positions: List[Tuple[int, int, int, int]], initial_results: List[Dict]) -> List[Dict]:
        """Verify set consistency and re-scan inconsistent cards"""
        import logging
        logger = logging.getLogger(__name__)
        
        # Filter out None results (cards that weren't recognized)
        valid_results = [result for result in initial_results if result is not None]
        
        if not valid_results:
            logger.info("No cards were recognized, returning empty results")
            return [result for result in initial_results if result is not None]
        
        # Count set occurrences
        set_counts = {}
        for result in valid_results:
            card_set = result['card_set']
            set_counts[card_set] = set_counts.get(card_set, 0) + 1
        
        logger.info(f"Set distribution: {set_counts}")
        
        # Find the dominant set (most common set)
        dominant_set = max(set_counts.items(), key=lambda x: x[1])[0]
        dominant_count = set_counts[dominant_set]
        total_valid_cards = len(valid_results)
        
        logger.info(f"Dominant set: {dominant_set} ({dominant_count}/{total_valid_cards} cards)")
        
        # Check if we have clear set consistency
        # If 4 out of 5 cards are from the same set, we consider it consistent
        if dominant_count >= 4 and total_valid_cards >= 4:
            logger.info("Set consistency verified - proceeding with dominant set")
            return [result for result in initial_results if result is not None]
        
        # If we have 3 out of 5 cards from the same set, we might need to re-scan
        # But first check if there are any inconsistent cards
        inconsistent_indices = []
        for i, result in enumerate(initial_results):
            if result is not None and result['card_set'] != dominant_set:
                inconsistent_indices.append(i)
        
        if inconsistent_indices and dominant_count >= 3:
            logger.info(f"Found {len(inconsistent_indices)} inconsistent cards, re-scanning with dominant set constraint")
            
            # Re-scan only the inconsistent cards, constrained to the dominant set
            final_results = initial_results.copy()
            
            for i in inconsistent_indices:
                x, y, w, h = card_positions[i]
                card_region = screenshot[y:y+h, x:x+w]
                
                # Re-scan this card, but only look in the dominant set
                best_match = self._find_best_card_match(card_region, preferred_set=dominant_set)
                
                if best_match:
                    display_name = self._get_display_name(best_match['card_name'], best_match['card_set'])
                    logger.info(f"Re-scanned card {i+1}: {display_name} (confidence: {best_match['confidence']:.2f})")
                    final_results[i] = {
                        'position': i + 1,
                        'card_name': best_match['card_name'],
                        'card_set': best_match['card_set'],
                        'confidence': best_match['confidence'],
                        'display_name': display_name,
                        'x': x,
                        'y': y,
                        'width': w,
                        'height': h
                    }
                else:
                    logger.info(f"Re-scan failed for card {i+1}, keeping original result")
            
            return final_results
        
        # If we don't have clear consistency, return the original results (filtering out None values)
        logger.info("No clear set consistency, returning original results")
        return [result for result in initial_results if result is not None]
    
    def get_all_cards(self) -> List[Dict[str, str]]:
        """Get a list of all cards in the database"""
        cards = []
        
        for set_name, card_dict in self.card_database.items():
            for card_name in card_dict.keys():
                cards.append({
                    'card_name': card_name,
                    'card_set': set_name
                })
        
        return cards
