"""
Card Counter Image Processing Module

Image processing functionality for the Card Counter application.
This module provides card identification from screenshots using OpenCV.
"""

import typing

import cv2
import numpy as np
import os
import json
import imagehash
from typing import List, Dict, Any, Tuple
from PIL import Image
import logging
import threading

logger = logging.getLogger(__name__)

if typing.TYPE_CHECKING:
    from app.names import C


class ImageProcessor:
    """
    Image processing class for Card Counter application

    Provides functionality for identifying cards in screenshot images.
    """

    _init_lock = threading.Lock()
    _phashes_lock = threading.Lock()

    def __init__(self, card_imgs_dir: str = None):
        """Initialize the image processor"""
        self.card_imgs_dir = card_imgs_dir or os.path.join("resources", "card_imgs")
        self._lock = threading.RLock()

        with ImageProcessor._init_lock:
            self.card_database = self._load_card_database()
            self.card_names = self._load_card_names()

            # Pre-calculated templates for performance
            self.color_templates = {}
            self.phash_templates = {}

            # Vectorized data structures for performance
            self.phash_matrix = None
            self.phash_metadata = []
            self.template_vectors = (
                {}
            )  # {set_name: {'matrix': np.array, 'metadata': list}}
            # 367x512 is what the image size actually is
            self.match_width, self.match_height = 92, 128
            # ratio: 1.395095367847411
            # self.match_width, self.match_height = 150, 209
            # self.match_width, self.match_height = 367, 512

            if self.card_database:
                self._prepare_templates()

    def _load_phashes(self) -> bool:
        """Load pHashes from phashes.json if it exists"""
        hash_file = os.path.join(self.card_imgs_dir, "phashes.json")
        if not os.path.exists(hash_file):
            return False
        # Check to see if the file was created before 2026-02-11. If so,
        # delete it and recreate.
        # phashes created before this date are malformed and will cause
        # issues.
        if os.stat(hash_file).st_mtime < 1770814800:
            logger.info(f"Deleting malformed pHashes file: {hash_file}")
            os.remove(hash_file)
            return False

        try:
            with open(hash_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                for set_name, cards in data.items():
                    if set_name not in self.phash_templates:
                        self.phash_templates[set_name] = {}
                    for card_name, hex_hash in cards.items():
                        self.phash_templates[set_name][card_name] = (
                            imagehash.hex_to_hash(hex_hash)
                        )
            logger.info(f"Loaded pHashes from {hash_file}")
            return True
        except Exception as e:
            logger.error(f"Failed to load pHashes from {hash_file}: {e}")
            return False

    def _save_phashes(self):
        """Save pHashes to phashes.json"""
        hash_file = os.path.join(self.card_imgs_dir, "phashes.json")
        try:
            data = {}
            for set_name, cards in self.phash_templates.items():
                data[set_name] = {}
                for card_name, h in cards.items():
                    data[set_name][card_name] = str(h)

            with open(hash_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            logger.info(f"Saved pHashes to {hash_file}")
        except Exception as e:
            logger.error(f"Failed to save pHashes to {hash_file}: {e}")

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
                if card_file.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
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

    def _load_card_names(self) -> "Dex":
        """Load card names mapping from names.py"""
        from app.names import Dex

        return Dex()

    def _get_card_obj(self, card_name: str, set_name: str) -> "C":
        """Get the display name for a card using the names mapping"""
        # Try to find the card in the names mapping

        # 1. Try the card_name directly (if it already includes the set prefix)
        if self.card_names[card_name]:
            return self.card_names[card_name]

        # 2. Try set_name + "_" + card_name
        # The format in names.py is like "A1_1" for set A1, card 1
        mapping_key = f"{set_name}_{card_name}"

        return self.card_names[mapping_key]

    def _load_and_preprocess_card(self, card_path: str) -> np.ndarray:
        """Load and preprocess a single card image at full resolution"""
        try:
            # # Load image using PIL and convert to RGB
            # with Image.open(card_path) as pil_image:
            #     background = Image.new('RGB', pil_image.size, (255, 255, 255))
            #     background.paste(pil_image, mask=pil_image.split()[3])
            #     # Convert to numpy array
            #     image = np.array(background)
            image = cv2.imread(card_path, cv2.IMREAD_COLOR)
            # # Convert to RGB if needed (from RGBA or grayscale)
            # if len(image.shape) == 3 and image.shape[2] == 4:  # RGBA
            #     image = cv2.cvtColor(image, cv2.COLOR_RGBA2RGB)
            # elif len(image.shape) == 2:  # Grayscale
            #     image = cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)

            # Keep the card at its original resolution for better matching accuracy
            # Full-size cards are typically 367x512 pixels
            return image
        except Exception as e:
            print(f"Error processing card image {card_path}: {e}")
            return None

    def _preprocess_screenshot(self, screenshot_path: str) -> np.ndarray:
        """Load and preprocess a screenshot image"""
        try:
            return cv2.imread(screenshot_path, cv2.IMREAD_COLOR)
        except Exception as e:
            print(f"Error processing screenshot {screenshot_path}: {e}")
            return None

    def load_card_templates(self, template_dir: str):
        """
        Load card templates from directory

        Args:
            template_dir: Directory containing card template images
        """
        with self._lock:
            try:
                logger.info(f"Loading card templates from {template_dir}")

                # Check if directory exists
                if not os.path.isdir(template_dir):
                    raise FileNotFoundError(
                        f"Template directory not found: {template_dir}"
                    )

                # Update card_imgs_dir and reload database
                self.card_imgs_dir = template_dir
                self.card_database = self._load_card_database()

                if self.card_database:
                    self._prepare_templates()  # Optimization: Pre-calculate versions
                    template_count = self.get_template_count()
                    logger.debug(f"Successfully loaded {template_count} card templates")
                    self.loaded = True
                else:
                    raise ValueError(f"No valid card templates found in {template_dir}")

            except Exception as e:
                logger.error(f"Failed to load card templates: {e}")
                raise

    def _prepare_templates(self):
        """Pre-calculate versions of all templates and compute pHashes"""
        self.color_templates = {}
        self.phash_templates = {}

        logger.info("Preparing templates and computing pHashes")

        # Try to load existing hashes
        self._load_phashes()
        new_hashes_computed = False

        for set_name, cards in self.card_database.items():
            self.color_templates[set_name] = {}
            if set_name not in self.phash_templates:
                self.phash_templates[set_name] = {}

            for card_name, template in cards.items():
                # 1. Matching resolution color template
                small = cv2.resize(template, (self.match_width, self.match_height))
                self.color_templates[set_name][card_name] = small

                # 2. pHash (computed from full image for better accuracy)
                if card_name not in self.phash_templates[set_name]:
                    template_pil = Image.fromarray(template)
                    self.phash_templates[set_name][card_name] = imagehash.phash(
                        template_pil
                    )
                    new_hashes_computed = True

        if new_hashes_computed:
            self._save_phashes()

        self._rebuild_vectorized_data()

        # Clear large full-size caches to save memory
        self.card_database = {}
        self.color_templates = {}

    def _rebuild_vectorized_data(self):
        """Build vectorized data structures for faster matching"""
        # 1. Rebuild pHash matrix
        phash_list = []
        self.phash_metadata = []

        for set_name, cards in self.phash_templates.items():
            for card_name, h in cards.items():
                phash_list.append(h.hash.flatten())
                self.phash_metadata.append((set_name, card_name))

        if phash_list:
            self.phash_matrix = np.array(phash_list)
        else:
            self.phash_matrix = None

        # 2. Rebuild template matrices for detailed search
        self.template_vectors = {}

        logger.info(
            f"Vectorizing templates at {self.match_width}x{self.match_height}..."
        )
        for set_name, cards in self.color_templates.items():
            vectors = []
            border_colors = []
            metadata = []
            for card_name, color_img in cards.items():
                # Normalize (already resized in _prepare_templates)
                vec = color_img.astype(np.float32).flatten()
                vec -= np.mean(vec)
                norm = np.linalg.norm(vec)
                if norm > 0:
                    vec /= norm
                vectors.append(vec)
                border_colors.append(self._compute_border_mean(color_img))
                metadata.append(card_name)

            if vectors:
                self.template_vectors[set_name] = {
                    "matrix": np.array(vectors),
                    "border_colors": np.array(border_colors, dtype=np.float32),
                    "metadata": metadata,
                }

    def _compute_border_mean(
        self, image: np.ndarray, border_ratio: float = 0.15
    ) -> np.ndarray:
        height, width = image.shape[:2]
        border = int(min(height, width) * border_ratio)
        if border <= 0:
            return np.mean(image.reshape(-1, 3), axis=0)

        mask = np.zeros((height, width), dtype=bool)
        mask[:border, :] = True
        mask[-border:, :] = True
        mask[:, :border] = True
        mask[:, -border:] = True

        return image[mask].mean(axis=0)

    def process_screenshot(self, image_path: str) -> List[Dict[str, Any]]:
        """
        Process a screenshot to identify cards using fixed position detection

        Args:
            image_path: Path to screenshot image

        Returns:
            List[Dict]: List of identified cards with positions and confidence scores
        """

        if not self.phash_templates:
            raise RuntimeError(
                "Card templates not loaded. Call load_card_templates() first."
            )

        try:
            logger.debug(f"Processing screenshot: {image_path}")
            # Load and preprocess screenshot
            screenshot = self._preprocess_screenshot(image_path)

            if screenshot is None:
                logger.warning(f"Failed to load screenshot: {image_path}")
                return []

            logger.debug(f"Screenshot loaded: {screenshot.shape}")

            # Detect card positions using fixed layout
            card_positions = self._detect_card_positions(screenshot)

            num_cards = len(card_positions)
            logger.debug(f"Detected {num_cards} card positions")

            excluded_sets = ["P-A", "P-B"]

            # If 4 cards, it's always A4b / Deluxe Pack Ex
            # If 5 or 6 cards, it's guaranteed NOT to be A4b
            forced_set = "A4b" if num_cards == 4 else None

            if num_cards in (5, 6):
                excluded_sets.append("A4b")

            if forced_set:
                logger.debug(f"Four-card pack detected, forcing set to {forced_set}")
            if excluded_sets:
                logger.debug(
                    f"{num_cards}-card pack detected, excluding sets: {excluded_sets}"
                )

            # Identify all cards in a single pass
            detected_cards = []
            for i, (x, y, w, h) in enumerate(card_positions):
                logger.debug(f"Scanning card {i+1} at position ({x}, {y})")
                card_region = screenshot[y : y + h, x : x + w]

                if self._is_empty_card_region(card_region):
                    logger.debug(f"Skipping empty card slot at position {i+1}")
                    continue

                # Use force_detailed=True for maximum accuracy since we're only scanning once.
                # This ensures we don't just rely on pHash which can have collisions.
                best_match = self._find_best_card_match(
                    card_region,
                    exclude_sets=excluded_sets,
                    force_detailed=True,
                    force_set=forced_set,
                )

                # The vast majority of the cards will be between 80 and 90% confident.
                # However, there are a few where even though the system has identified
                # it correctly, confidence is still low... push it through anyway, and
                # we'll make sure we have a test case for it.
                if best_match and best_match["confidence"] > 0.6:
                    # Get the display name for this card
                    card_obj: C = self._get_card_obj(
                        best_match["card_name"], best_match["card_set"]
                    )
                    logger.debug(
                        f"Card {i+1}: {card_obj.name} (confidence: {best_match['confidence']:.2f})"
                    )

                    detected_cards.append(
                        {
                            "position": i + 1,
                            "obj": card_obj,
                            "confidence": best_match["confidence"],
                            "x": x,
                            "y": y,
                            "width": w,
                            "height": h,
                        }
                    )
                else:
                    logger.debug(f"No card match found for position {i+1}")

            # Post-processing: Ensure all cards are from the same set
            # If we didn't force a set initially, detect the dominant set and re-evaluate outliers
            if not forced_set and len(detected_cards) > 1:
                # Count cards by set
                set_counts = {}
                for card in detected_cards:
                    # Use set_id.value if it's an enum member
                    card_obj = card.get("obj")
                    if card_obj and hasattr(card_obj.set_id, "value"):
                        card_set = card_obj.set_id.value
                    else:
                        card_set = str(card_obj.set_id) if card_obj else None
                    
                    if card_set:
                        set_counts[card_set] = set_counts.get(card_set, 0) + 1

                # Find the sets with the maximum count
                max_count = max(set_counts.values())
                top_sets = [s for s, count in set_counts.items() if count == max_count]

                # A clear winner exists if there's only one top set and it has more than half of the cards
                is_clear_winner = len(top_sets) == 1 and max_count > len(detected_cards) / 2

                if not is_clear_winner and len(set_counts) > 1:
                    logger.debug(
                        f"No clear winner among {list(set_counts.keys())}. Evaluating confidence..."
                    )
                    best_set = top_sets[0]
                    max_total_confidence = -1
                    best_set_matches = {}

                    for candidate_set in set_counts.keys():
                        total_confidence = 0
                        current_matches = {}
                        for card in detected_cards:
                            # Re-match with forced set to get confidence for this specific set
                            # We do this for all cards to be sure we have the best match within this set
                            x, y, w, h = (
                                card["x"],
                                card["y"],
                                card["width"],
                                card["height"],
                            )
                            card_region = screenshot[y : y + h, x : x + w]
                            match = self._find_best_card_match(
                                card_region,
                                force_detailed=True,
                                force_set=candidate_set,
                            )
                            if match:
                                total_confidence += match["confidence"]
                                current_matches[card["position"]] = match

                        logger.debug(
                            f"Set {candidate_set} total confidence: {total_confidence:.4f}"
                        )
                        if total_confidence > max_total_confidence:
                            max_total_confidence = total_confidence
                            best_set = candidate_set
                            best_set_matches = current_matches

                    dominant_set = best_set
                    # Update detected_cards with the best matches found for the dominant set
                    for i, card in enumerate(detected_cards):
                        pos = card["position"]
                        if pos in best_set_matches:
                            match = best_set_matches[pos]
                            card_obj = self._get_card_obj(
                                match["card_name"], match["card_set"]
                            )
                            detected_cards[i] = {
                                "position": pos,
                                "obj": card_obj,
                                "confidence": match["confidence"],
                                "x": card["x"],
                                "y": card["y"],
                                "width": card["width"],
                                "height": card["height"],
                            }
                    dominant_count = len(detected_cards)
                else:
                    dominant_set = top_sets[0]
                    dominant_count = max_count

                print(f"Dominant set: {dominant_set} with {dominant_count} cards")
                print(f"Set distribution: {set_counts}")

                # If there are outliers (cards from different sets), re-evaluate them
                outliers = []
                for card in detected_cards:
                    card_obj = card.get("obj")
                    if not card_obj:
                        continue
                    
                    card_set = (
                        card_obj.set_id.value
                        if hasattr(card_obj.set_id, "value")
                        else str(card_obj.set_id)
                    )
                    if card_set != dominant_set:
                        outliers.append(card)

                if outliers:
                    print(
                        f"Found {len(outliers)} outlier(s) not matching dominant set {dominant_set}"
                    )

                    # Re-evaluate each outlier by forcing search to dominant set
                    for outlier in outliers:
                        pos = outlier["position"]
                        x, y, w, h = (
                            outlier["x"],
                            outlier["y"],
                            outlier["width"],
                            outlier["height"],
                        )
                        card_region = screenshot[y : y + h, x : x + w]

                        print(
                            f"Re-evaluating card at position {pos} (was {outlier['obj'].id}, forcing to {dominant_set})"
                        )

                        # Re-match with forced set
                        best_match = self._find_best_card_match(
                            card_region,
                            force_detailed=True,
                            force_set=dominant_set,
                        )

                        if best_match and best_match["confidence"] > 0.6:
                            card_obj: C = self._get_card_obj(
                                best_match["card_name"], best_match["card_set"]
                            )
                            print(
                                f"Re-evaluated card {pos}: {card_obj.name} (confidence: {best_match['confidence']:.2f})"
                            )

                            # Update the card in detected_cards
                            for i, card in enumerate(detected_cards):
                                if card["position"] == pos:
                                    detected_cards[i] = {
                                        "position": pos,
                                        "obj": card_obj,
                                        "confidence": best_match["confidence"],
                                        "x": x,
                                        "y": y,
                                        "width": w,
                                        "height": h,
                                    }
                                    break
                        else:
                            logger.debug(f"Re-evaluation failed for position {pos}")

            print(f"Found {len(detected_cards)} cards in {image_path}")
            return detected_cards

        except Exception as e:
            logger.error(f"Failed to process screenshot {image_path}: {e}")
            raise

    def _detect_card_positions(
        self, screenshot: np.ndarray
    ) -> List[Tuple[int, int, int, int]]:
        """
        Detect card positions in a screenshot using the exact pixel placements

        Args:
            screenshot: Screenshot image as numpy array

        Returns:
            List[Tuple]: List of (x, y, width, height) tuples for card positions
        """
        height, width = screenshot.shape[:2]

        # Base resolution that the original coordinates were designed for (240x227)
        base_w, base_h = 240, 227

        # Calculate scaling factors
        scale_x = width / base_w
        scale_y = height / base_h

        def scale_pos(pos):
            x, y, w, h = pos
            return (
                int(round(x * scale_x)),
                int(round(y * scale_y)),
                int(round(w * scale_x)),
                int(round(h * scale_y)),
            )

        # #e7f0f7 in grayscale ≈ 239
        background_threshold = 235

        # Detect layout: check if there are 2 or 3 cards on top row
        det_top_x, det_top_y, det_top_w, det_top_h = scale_pos((0, 8, 30, 50))

        if det_top_y + det_top_h <= height and det_top_x + det_top_w <= width:
            detection_region_top = screenshot[
                det_top_y : det_top_y + det_top_h, det_top_x : det_top_x + det_top_w
            ]
            avg_color_top = np.mean(detection_region_top)

            if avg_color_top > background_threshold:
                # 2 cards on top row
                top_base = [
                    (39, 5, 75, 106),  # position 1
                    (124, 5, 75, 106),  # position 2
                ]
            else:
                # 3 cards on top row
                top_base = [
                    (0, 5, 75, 106),  # position 1
                    (81, 5, 75, 106),  # position 2
                    (164, 5, 75, 106),  # position 3
                ]
        else:
            # Fallback to 3-card layout
            top_base = [
                (0, 5, 75, 106),
                (81, 5, 75, 106),
                (164, 5, 75, 106),
            ]

        top_row_positions = [scale_pos(p) for p in top_base]

        # Detect layout: check if there are 2 or 3 cards on bottom row
        # Scale the detection rectangle: (x=0, y=124, w=30, h=50)
        det_x, det_y, det_w, det_h = scale_pos((0, 124, 30, 50))

        if det_y + det_h <= height and det_x + det_w <= width:
            detection_region = screenshot[det_y : det_y + det_h, det_x : det_x + det_w]
            avg_color = np.mean(detection_region)

            if avg_color > background_threshold:
                # 2 cards on bottom row
                bottom_base = [
                    (39, 121, 75, 106),  # position 4
                    (124, 121, 75, 106),  # position 5
                ]
            else:
                # 3 cards on bottom row
                bottom_base = [
                    (0, 121, 75, 106),  # position 4
                    (81, 121, 75, 106),  # position 5
                    (164, 121, 75, 106),  # position 6
                ]
        else:
            # Fallback to 2-card layout
            bottom_base = [(39, 121, 75, 106), (124, 121, 75, 106)]

        bottom_positions = [scale_pos(p) for p in bottom_base]

        return top_row_positions + bottom_positions

    def _is_empty_card_region(self, card_region: np.ndarray) -> bool:
        """
        Determine if a card region is an empty (unrendered) slot based on
        the average color of a small center box.
        """
        if card_region is None or card_region.size == 0:
            return False

        height, width = card_region.shape[:2]
        box_size = 20
        half = box_size // 2

        center_x = width // 2
        center_y = height // 2

        x0 = max(center_x - half, 0)
        y0 = max(center_y - half, 0)
        x1 = min(center_x + half, width)
        y1 = min(center_y + half, height)

        if x1 <= x0 or y1 <= y0:
            return False

        center_box = card_region[y0:y1, x0:x1]
        avg_color = np.mean(center_box.reshape(-1, 3), axis=0)

        empty_color = np.array([189, 206, 226], dtype=np.float32)  # #bdcee2
        distance = np.linalg.norm(avg_color - empty_color)
        return distance <= 3.0

    def _find_best_card_match(
        self,
        card_region: np.ndarray,
        force_detailed: bool = False,
        exclude_sets: List[str] = None,
        force_set: str = None,
    ) -> Dict[str, Any]:
        """
        Find the best matching card in the database for a card region

        Args:
            card_region: Card image region as numpy array
            force_detailed: If True, always perform detailed search regardless of quick search confidence
            exclude_sets: If provided, do not search within these sets
            force_set: If provided, only search within this specific set

        Returns:
            Dict: Best match result with card_name, card_set, and confidence
        """
        # Multi-stage matching for better performance:
        # 1. Quick search using pHash and Hamming distance to identify likely sets
        # 2. Detailed search at full resolution within the candidate sets

        # Stage 1: Quick search using pHash
        # Compute pHash for the region directly from the provided region
        region_pil = Image.fromarray(card_region)
        region_hash = imagehash.phash(region_pil)

        # Quick search to identify candidate sets and best card match
        set_scores = {}

        # Filter indices based on force_set or exclude_sets
        if force_set:
            indices = [
                i for i, m in enumerate(self.phash_metadata) if m[0] == force_set
            ]
        elif exclude_sets:
            exclude_set = set(exclude_sets)
            indices = [
                i for i, m in enumerate(self.phash_metadata) if m[0] not in exclude_set
            ]
        else:
            indices = list(range(len(self.phash_metadata)))

        sub_matrix = self.phash_matrix[indices]
        q_hash = region_hash.hash.flatten()
        # Hamming distance: count non-matching bits
        distances = np.count_nonzero(sub_matrix != q_hash, axis=1)
        scores = 1.0 - (distances / 64.0)

        # Build set_scores and phash_score_map in one pass
        phash_score_map = {}
        for i, score in enumerate(scores):
            meta_idx = indices[i]
            s_name, c_name = self.phash_metadata[meta_idx]
            key = f"{s_name}_{c_name}"
            phash_score_map[key] = float(score)

            if score > set_scores.get(s_name, 0):
                set_scores[s_name] = score

        # Stage 2: Hybrid search combining pHash and detailed correlation
        if not set_scores:
            return None

        # Upscale card region to match matching resolution for detailed matching
        upscaled_region = cv2.resize(card_region, (self.match_width, self.match_height))

        # Normalize query region for correlation
        q_vec = upscaled_region.astype(np.float32).flatten()
        q_vec -= np.mean(q_vec)
        q_norm = np.linalg.norm(q_vec)
        if q_norm > 0:
            q_vec /= q_norm
        query_border = self._compute_border_mean(upscaled_region)

        # Get top candidate sets (top 3 or within 0.05 of best)
        if force_set:
            candidate_sets = [force_set] if force_set in set_scores else []
            if not candidate_sets:
                return None
            sorted_sets = [(force_set, set_scores[force_set])]
        else:
            sorted_sets = sorted(set_scores.items(), key=lambda x: x[1], reverse=True)
            top_set_score = sorted_sets[0][1]
            candidate_sets = []
            for s_name, s_score in sorted_sets:
                if len(candidate_sets) < 3 or s_score >= top_set_score - 0.05:
                    candidate_sets.append(s_name)
                if len(candidate_sets) >= 5:
                    break

        # Search each candidate set with vectorized hybrid scoring
        best_match = None
        best_hybrid_score = -1
        best_set_name = sorted_sets[0][0]

        for search_set in candidate_sets:
            data = self.template_vectors[search_set]
            matrix = data["matrix"]
            border_colors = data.get("border_colors")
            metadata = data["metadata"]

            # Vectorized correlation scores
            corr_scores = matrix @ q_vec
            if border_colors is None:
                border_scores = np.zeros_like(corr_scores)
            else:
                color_diffs = np.linalg.norm(border_colors - query_border, axis=1)
                max_color_distance = np.sqrt(3 * (255.0**2))
                border_scores = 1.0 - (color_diffs / max_color_distance)
                border_scores = np.clip(border_scores, 0.0, 1.0)

            # Vectorized pHash scores lookup
            phash_scores = np.array(
                [phash_score_map.get(f"{search_set}_{cn}", 0.0) for cn in metadata],
                dtype=np.float32,
            )

            # Vectorized hybrid scores
            hybrid_scores = 0.60 * phash_scores + 0.15 * corr_scores + 0.25 * border_scores

            # Find best in this set
            best_idx = int(np.argmax(hybrid_scores))
            best_set_hybrid = float(hybrid_scores[best_idx])

            # Tie-breaking logic
            is_better = False
            if best_set_hybrid > best_hybrid_score + 0.005:
                is_better = True
            elif abs(best_set_hybrid - best_hybrid_score) <= 0.005:
                if search_set == best_set_name and (
                    best_match is None or best_match["card_set"] != best_set_name
                ):
                    is_better = True
                elif best_match and search_set == best_match.get("card_set"):
                    if float(corr_scores[best_idx]) > best_match.get("corr_score", 0):
                        is_better = True

            if is_better:
                best_hybrid_score = best_set_hybrid
                best_match = {
                    "card_name": metadata[best_idx],
                    "card_set": search_set,
                    "confidence": best_set_hybrid,
                    "phash_score": float(phash_scores[best_idx]),
                    "corr_score": float(corr_scores[best_idx]),
                    "hybrid_score": best_set_hybrid,
                }

        if best_match:
            return best_match

        return None

    def get_template_count(self) -> int:
        """
        Get the number of loaded templates

        Returns:
            int: Number of loaded card templates
        """
        # Count templates across all sets
        count = 0
        for set_name, cards in self.phash_templates.items():
            count += len(cards)
        return count

    def get_loaded_template_codes(self) -> List[str]:
        """
        Get list of loaded template codes

        Returns:
            List[str]: List of card codes for loaded templates
        """
        # Collect all card codes from all sets
        codes = []
        for set_name, cards in self.phash_templates.items():
            for card_name in cards.keys():
                codes.append(f"{set_name}_{card_name}")
        return codes
