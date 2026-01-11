# Flask application for card counter
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
import os
import pandas as pd
import sqlite3
import logging
from datetime import datetime
from database import Database
from image_processing import ImageProcessor
from names import sets as set_names, cards as card_names
import threading
import queue
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['ALLOWED_EXTENSIONS'] = {'csv'}
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB limit

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('cardcounter.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Add custom Jinja2 filters
def url_encode_filter(s):
    """URL encode a string for use in URLs"""
    import urllib.parse
    return urllib.parse.quote_plus(str(s))

def get_display_card_name(raw_card_name, raw_set_name):
    """Convert raw card name to display name using names.py mapping"""
    # Handle different card name formats
    # Format 1: "A2_205" (full format with set prefix)
    # Format 2: "205" (just the number)
    # Format 3: "cover" (special case)
    
    # Try format 1 first (full format)
    if f"{raw_set_name}_" in raw_card_name:
        # This is already in full format like "A2_205"
        mapping_key = raw_card_name
    else:
        # This is just the number part, add the set prefix
        mapping_key = f"{raw_set_name}_{raw_card_name}"
    
    if mapping_key in card_names:
        return card_names[mapping_key]
    else:
        # Fallback to original name if not found
        return raw_card_name

def get_display_set_name(raw_set_name):
    """Convert raw set name to display name using names.py mapping"""
    if raw_set_name in set_names:
        return set_names[raw_set_name]
    else:
        # Fallback to original name if not found
        return raw_set_name

def get_image_card_name(raw_card_name):
    """Extract the correct card name for image paths"""
    # Handle cases where the card name might be in format "A3b_A3b_84"
    # We want to extract just "A3b_84" for the image path
    parts = raw_card_name.split('_')
    if len(parts) >= 3 and parts[0] == parts[1]:
        # Format like "A3b_A3b_84" -> extract "A3b_84"
        return f"{parts[1]}_{parts[2]}"
    elif len(parts) == 2 and parts[0] in set_names:
        # Format like "A3b_84" -> keep as is
        return raw_card_name
    else:
        # Fallback to original name
        return raw_card_name

def get_card_rarity(card_name, card_set):
    """Extract rarity from card name using names.py mapping"""
    # Try to find the display name to extract rarity
    # Handle both formats: "A2_84" and just "84"
    mapping_key = f"{card_set}_{card_name}" if not card_name.startswith(f"{card_set}_") else card_name
    
    if mapping_key in card_names:
        display_name = card_names[mapping_key]
        # Look for patterns like (1D), (2D), (3D), (4D), (1S), (2S), (3S)
        import re
        match = re.search(r'\(([0-9][A-Z])\)', display_name)
        if match:
            rarity_code = match.group(1)
            
            # Map rarity codes to human-readable names
            rarity_map = {
                '1D': 'Common',
                '2D': 'Uncommon',
                '3D': 'Rare',
                '4D': 'Ultra Rare',
                '1S': 'Common (Shiny)',
                '2S': 'Uncommon (Shiny)',
                '3S': 'Rare (Shiny)'
            }
            
            return rarity_map.get(rarity_code, 'Unknown')
    
    return 'Unknown'

app.jinja_env.filters['url_encode'] = url_encode_filter

# Initialize database and image processor
db = Database()
image_processor = ImageProcessor()

# Ensure upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Global variables for background processing
processing_queue = queue.Queue()
processing_status = {}
processing_lock = threading.Lock()

# Helper function to log and flash messages
def log_and_flash(message, category='info'):
    logger.info(message)
    flash(message, category)

def process_screenshots_background(screenshots_path, task_id):
    """Process screenshots in the background"""
    try:
        logger.info(f"Background task {task_id}: Processing screenshots from path: {screenshots_path}")
        
        # Update status
        with processing_lock:
            processing_status[task_id] = {
                'status': 'processing',
                'progress': 0,
                'total': 0,
                'processed': 0,
                'errors': 0,
                'start_time': datetime.now().isoformat(),
                'message': 'Starting processing...'
            }
        
        # Try to handle Windows paths in WSL2
        screenshots_path = screenshots_path.strip()
        
        # Convert Windows path to WSL2 path if needed
        import re
        drive_match = re.match(r'^([A-Za-z]):[\\/]', screenshots_path)
        if drive_match:
            drive_letter = drive_match.group(1)
            original_path = screenshots_path
            screenshots_path = screenshots_path.replace(f'{drive_letter}:\\', f'/mnt/{drive_letter.lower()}/')
            screenshots_path = screenshots_path.replace(f'{drive_letter}:/', f'/mnt/{drive_letter.lower()}/')
            screenshots_path = screenshots_path.replace('\\', '/')
            logger.info(f"Background task {task_id}: Converted Windows path: {original_path} -> {screenshots_path}")
        
        # Check if the path exists
        if not os.path.exists(screenshots_path):
            error_msg = f'Screenshot path does not exist: {screenshots_path}'
            logger.error(f"Background task {task_id}: {error_msg}")
            with processing_lock:
                processing_status[task_id]['status'] = 'error'
                processing_status[task_id]['message'] = error_msg
            return
        
        # Check if it's a directory
        if not os.path.isdir(screenshots_path):
            error_msg = f'Path is not a directory: {screenshots_path}'
            logger.error(f"Background task {task_id}: {error_msg}")
            with processing_lock:
                processing_status[task_id]['status'] = 'error'
                processing_status[task_id]['message'] = error_msg
            return
        
        logger.info(f"Background task {task_id}: Found screenshots directory: {screenshots_path}")
        
        # Count total image files first
        image_files = [f for f in os.listdir(screenshots_path) 
                      if f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp', '.gif'))]
        total_images = len(image_files)
        
        with processing_lock:
            processing_status[task_id]['total'] = total_images
            processing_status[task_id]['message'] = f'Found {total_images} image files to process'
        
        logger.info(f"Background task {task_id}: Found {total_images} image files to process")
        
        processed_count = 0
        error_count = 0
        skipped_count = 0
        start_time = datetime.now()
        
        # Use ThreadPoolExecutor for parallel processing
        max_workers = min(4, total_images)  # Limit to 4 threads to avoid overwhelming the system
        
        def process_single_screenshot(filename, index, screenshot_lookup):
            """Process a single screenshot"""
            nonlocal processed_count, error_count, skipped_count
            try:
                screenshot_path = os.path.join(screenshots_path, filename)
                
                # Check if this screenshot has already been processed
                # Use the pre-loaded screenshot lookup for efficiency
                matching_screenshot = screenshot_lookup.get(filename)
                
                if not matching_screenshot:
                    logger.warning(f"Background task {task_id}: No matching CSV record found for screenshot: {filename}")
                    return None
                
                # Check if this screenshot is already processed
                if matching_screenshot['processed']:
                    logger.info(f"Background task {task_id}: Screenshot {filename} already processed, skipping")
                    return "skipped"
                
                logger.info(f"Background task {task_id}: Processing screenshot {index+1}/{total_images}: {filename}")
                
                # Process the screenshot to identify cards
                cards_found = image_processor.identify_cards_in_screenshot(screenshot_path)
                
                logger.info(f"Background task {task_id}: Found {len(cards_found)} cards in {filename}")
                
                # Add the found cards to the database
                for card_info in cards_found:
                    # Add the card to the cards table if it doesn't exist
                    rarity = get_card_rarity(card_info['card_name'], card_info['card_set'])
                    card_id = db.add_card(
                        card_info['card_name'],
                        card_info['card_set'],
                        f"{card_info['card_set']}/{card_info['card_name']}.webp",  # Assuming webp format
                        rarity
                    )
                    
                    # Add the relationship between screenshot and card
                    db.add_screenshot_card(
                        matching_screenshot['id'],
                        card_id,
                        card_info['position'],
                        card_info['confidence']
                    )
                
                # Mark the screenshot as processed
                db.mark_screenshot_processed(matching_screenshot['id'])
                
                return True
                
            except Exception as e:
                logger.error(f"Background task {task_id}: Error processing screenshot {filename}: {e}", exc_info=True)
                return False
        
        # Load all screenshots once at the beginning for efficiency
        all_screenshots = db.get_all_screenshots()
        # Create a lookup dictionary for faster access
        screenshot_lookup = {screenshot['pack_screenshot']: screenshot for screenshot in all_screenshots}
        
        # Process all image files in parallel
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks
            future_to_filename = {executor.submit(process_single_screenshot, filename, i, screenshot_lookup): (filename, i) 
                                for i, filename in enumerate(image_files)}
            
            # Process results as they complete
            for future in as_completed(future_to_filename):
                filename, i = future_to_filename[future]
                try:
                    result = future.result()
                    if result == "skipped":
                        skipped_count += 1
                    elif result:
                        processed_count += 1
                    else:
                        error_count += 1
                except Exception as e:
                    logger.error(f"Background task {task_id}: Exception in future for {filename}: {e}")
                    error_count += 1
                
                # Update progress every few files or at the end
                completed_count = processed_count + skipped_count + error_count
                if processed_count % 5 == 0 or completed_count == total_images:
                    with processing_lock:
                        processing_status[task_id]['processed'] = processed_count
                        processing_status[task_id]['skipped'] = skipped_count
                        processing_status[task_id]['errors'] = error_count
                        processing_status[task_id]['progress'] = completed_count / total_images if total_images > 0 else 1.0
                        processing_status[task_id]['message'] = f'Processed {processed_count}/{total_images} screenshots ({skipped_count} skipped)'
                
                logger.info(f"Background task {task_id}: Completed {processed_count + error_count}/{total_images} screenshots")
        
        end_time = datetime.now()
        processing_time = (end_time - start_time).total_seconds()
        
        with processing_lock:
            processing_status[task_id]['status'] = 'completed'
            processing_status[task_id]['processed'] = processed_count
            processing_status[task_id]['skipped'] = skipped_count
            processing_status[task_id]['errors'] = error_count
            processing_status[task_id]['progress'] = 1.0
            processing_status[task_id]['end_time'] = end_time.isoformat()
            processing_status[task_id]['processing_time'] = processing_time
            
            message_parts = []
            if processed_count > 0:
                message_parts.append(f'Successfully processed {processed_count} screenshots')
            if skipped_count > 0:
                message_parts.append(f'{skipped_count} screenshots were already processed and skipped')
            if error_count > 0:
                message_parts.append(f'{error_count} errors occurred')
            
            if message_parts:
                processing_status[task_id]['message'] = ', '.join(message_parts) + f' in {processing_time:.2f} seconds'
            else:
                processing_status[task_id]['message'] = 'No screenshots were processed'
        
        logger.info(f"Background task {task_id}: {processing_status[task_id]['message']}")
        
    except Exception as e:
        logger.error(f"Background task {task_id}: Fatal error in background processing: {e}", exc_info=True)
        with processing_lock:
            processing_status[task_id]['status'] = 'error'
            processing_status[task_id]['message'] = f'Fatal error: {str(e)}'

@app.route('/')
def index():
    # Get some basic stats for the dashboard
    total_screenshots = db.get_total_screenshots_count()
    processed_screenshots = db.get_processed_screenshots_count()
    cards_in_db = len(db.get_all_cards())
    total_cards_found = db.get_total_cards_count()
    
    return render_template('index.html', 
                         total_screenshots=total_screenshots,
                         processed_screenshots=processed_screenshots,
                         cards_in_db=cards_in_db,
                         total_cards_found=total_cards_found)

@app.route('/debug')
def debug():
    """Debug page for testing with limited data"""
    return render_template('debug.html')

@app.route('/cards')
def cards():
    """Page to browse all cards found in screenshots"""
    # Get filter parameters
    account_filter = request.args.get('account_filter', '')
    set_filter = request.args.get('set_filter', '')
    search_query = request.args.get('search', '')
    rarity_filter = request.args.getlist('rarity_filter')  # Multi-select filter
    
    # Get all cards with their associated screenshot information
    query = '''
        SELECT c.card_name, c.card_set, c.rarity, sc.position, sc.confidence, 
               s.clean_filename, s.device_account, s.pack_screenshot
        FROM screenshot_cards sc
        JOIN cards c ON sc.card_id = c.id
        JOIN screenshots s ON sc.screenshot_id = s.id
    '''
    
    conditions = []
    params = []
    
    if account_filter:
        conditions.append('s.clean_filename = ?')
        params.append(account_filter)
    
    if set_filter:
        conditions.append('c.card_set = ?')
        params.append(set_filter)

    if rarity_filter and rarity_filter != ['']:
        rarity_conditions = []
        for rarity in rarity_filter:
            if rarity:  # Skip empty values
                rarity_conditions.append('c.rarity = ?')
                params.append(rarity)
        if rarity_conditions:  # Only add condition if we have valid rarities
            conditions.append('(' + ' OR '.join(rarity_conditions) + ')')
    
    if search_query:
        # Search by display name instead of raw card name
        # We need to find all cards whose display names match the search query
        matching_cards = []
        for raw_set in set_names.keys():
            for raw_card, display_name in card_names.items():
                if raw_card.startswith(f"{raw_set}_") and search_query.lower() in display_name.lower():
                    # Handle both database formats:
                    # Format 1: card_name = "84", card_set = "A3b" (expected format)
                    # Format 2: card_name = "A3b_84", card_set = "A3b" (actual format in DB)
                    card_name_part = raw_card.split('_', 1)[1]
                    
                    # Add both possible formats to search for
                    matching_cards.append((card_name_part, raw_set))  # Format 1
                    matching_cards.append((raw_card, raw_set))       # Format 2 (full format)
        
        if matching_cards:
            # Create a condition that matches any of the found cards
            card_conditions = []
            for card_name_part, raw_set in matching_cards:
                card_conditions.append('(c.card_name = ? AND c.card_set = ?)')
                params.extend([card_name_part, raw_set])
            conditions.append('(' + ' OR '.join(card_conditions) + ')')
        else:
            # If no matches found, add a condition that will never be true
            conditions.append('1 = 0')
    
    if conditions:
        query += ' WHERE ' + ' AND '.join(conditions)
    
    query += ' ORDER BY c.card_set, c.card_name, s.device_account, s.clean_filename, sc.position'
    
    with sqlite3.connect('cardcounter.db') as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        
        columns = [column[0] for column in cursor.description]
        all_cards = []
        for row in cursor.fetchall():
            card_data = dict(zip(columns, row))
            # Convert raw card name to display name
            card_data['display_card_name'] = get_display_card_name(card_data['card_name'], card_data['card_set'])
            # Convert raw set name to display name
            card_data['display_set_name'] = get_display_set_name(card_data['card_set'])
            # Get the correct card name for image paths
            card_data['image_card_name'] = get_image_card_name(card_data['card_name'])
            # Include rarity information
            card_data['rarity'] = card_data.get('rarity', 'Unknown')
            all_cards.append(card_data)
    
    # Group cards by unique card+set combinations
    grouped_cards = {}
    for card in all_cards:
        # Create a unique key for each card+set combination
        unique_key = f"{card['card_name']}_{card['card_set']}"
        
        if unique_key not in grouped_cards:
            grouped_cards[unique_key] = {
                'card_name': card['card_name'],
                'card_set': card['card_set'],
                'display_card_name': card['display_card_name'],
                'display_set_name': card['display_set_name'],
                'image_card_name': card['image_card_name'],
                'instances': [],
                'total_count': 0
            }
        
        # Add this instance to the group
        grouped_cards[unique_key]['instances'].append({
            'account': card['clean_filename'],
            'screenshot': card['pack_screenshot'],
            'actual_filename': card['pack_screenshot'],
            'position': card['position'],
            'confidence': card['confidence']
        })
        grouped_cards[unique_key]['total_count'] += 1
    
    # Convert the grouped cards dictionary to a list for the template
    grouped_cards_list = list(grouped_cards.values())
    
    # Sort the grouped cards by set name and card name
    grouped_cards_list.sort(key=lambda x: (x['display_set_name'], x['display_card_name']))
    
    # Get unique accounts and sets for filters
    accounts = []
    sets = []
    
    if not account_filter:
        with sqlite3.connect('cardcounter.db') as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT DISTINCT clean_filename FROM screenshots WHERE processed = 1 ORDER BY clean_filename')
            accounts = [row[0] for row in cursor.fetchall() if row[0]]
    
    if not set_filter:
        with sqlite3.connect('cardcounter.db') as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT DISTINCT card_set FROM cards ORDER BY card_set')
            raw_sets = [row[0] for row in cursor.fetchall() if row[0]]
            # Convert raw set names to display names for the dropdown
            sets = []
            for raw_set in raw_sets:
                sets.append({
                    'raw_name': raw_set,
                    'display_name': get_display_set_name(raw_set)
                })
    
    # Get available rarities for filter
    rarities = []
    with sqlite3.connect('cardcounter.db') as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT DISTINCT rarity FROM cards WHERE rarity IS NOT NULL AND rarity != "Unknown" ORDER BY rarity')
        rarities = [row[0] for row in cursor.fetchall()]
    
    return render_template('cards.html',
                         grouped_cards=grouped_cards_list,
                         accounts=accounts,
                         sets=sets,
                         rarities=rarities,
                         current_account=account_filter,
                         current_set=set_filter,
                         search_query=search_query,
                         current_rarities=rarity_filter)

@app.route('/upload', methods=['POST'])
def upload_csv():
    # Get the local CSV file path from the form
    csv_path = request.form.get('csv_path')
    
    if not csv_path:
        log_and_flash('No CSV path provided', 'error')
        return redirect(url_for('index'))
    
    logger.info(f"Processing CSV file from path: {csv_path}")
    log_and_flash(f'Starting CSV processing...', 'info')
    
    # Try to handle Windows paths in WSL2 (same as screenshots)
    csv_path = csv_path.strip()
    
    # Convert Windows path to WSL2 path if needed
    import re
    drive_match = re.match(r'^([A-Za-z]):[\\/]', csv_path)
    if drive_match:
        drive_letter = drive_match.group(1)
        original_path = csv_path
        csv_path = csv_path.replace(f'{drive_letter}:\\', f'/mnt/{drive_letter.lower()}/')
        csv_path = csv_path.replace(f'{drive_letter}:/', f'/mnt/{drive_letter.lower()}/')
        csv_path = csv_path.replace('\\', '/')
        logger.info(f"Converted Windows path: {original_path} -> {csv_path}")
    
    # Check if the path exists
    if not os.path.exists(csv_path):
        logger.error(f'CSV file does not exist: {csv_path}')
        log_and_flash(f'CSV file does not exist: {csv_path}. Make sure the path is accessible from WSL2.', 'error')
        return redirect(url_for('index'))
    
    # Check if it's a file
    if not os.path.isfile(csv_path):
        logger.error(f'Path is not a file: {csv_path}')
        log_and_flash(f'Path is not a file: {csv_path}', 'error')
        return redirect(url_for('index'))
    
    # Check if it's a CSV file
    if not csv_path.lower().endswith('.csv'):
        logger.error(f'File is not a CSV: {csv_path}')
        log_and_flash(f'File is not a CSV: {csv_path}', 'error')
        return redirect(url_for('index'))
    
    try:
        logger.info(f'Loading CSV file: {csv_path}')
        log_and_flash('Loading CSV file...', 'info')
        
        # Parse CSV file directly from the provided path
        df = pd.read_csv(csv_path)
        
        logger.info(f'Loaded {len(df)} records from CSV')
        
        # Validate required columns
        required_columns = ['Timestamp', 'OriginalFilename', 'CleanFilename', 'DeviceAccount', 
                          'PackType', 'CardTypes', 'CardCounts', 'PackScreenshot', 'Shinedust']
        
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            logger.error(f'CSV file is missing required columns: {missing_columns}')
            log_and_flash(f'CSV file is missing required columns: {missing_columns}', 'error')
            return redirect(url_for('index'))
        
        logger.info('CSV validation passed, processing records...')
        log_and_flash('CSV validation passed, processing records...', 'info')
        
        # Process each row
        processed_count = 0
        new_records = 0
        duplicate_records = 0
        start_time = datetime.now()
        
        for index, row in df.iterrows():
            row_dict = row.to_dict()
            
            # Add screenshot to database
            screenshot_id, is_new = db.add_screenshot(row_dict)
            
            # For now, just add the screenshot record
            # Image processing will be handled separately
            
            processed_count += 1
            if is_new:
                new_records += 1
            else:
                duplicate_records += 1
            
            # Log progress every 100 records
            if processed_count % 100 == 0:
                logger.info(f'Processed {processed_count}/{len(df)} records...')
        
        end_time = datetime.now()
        processing_time = (end_time - start_time).total_seconds()
        
        logger.info(f'Successfully processed {processed_count} records ({new_records} new, {duplicate_records} duplicates) in {processing_time:.2f} seconds')
        
        if new_records > 0 and duplicate_records > 0:
            log_and_flash(f'Successfully processed {processed_count} records from CSV file: {new_records} new records, {duplicate_records} duplicates. Completed in {processing_time:.2f} seconds', 'success')
        elif new_records > 0:
            log_and_flash(f'Successfully processed {processed_count} records from CSV file: {new_records} new records. Completed in {processing_time:.2f} seconds', 'success')
        elif duplicate_records > 0:
            log_and_flash(f'Successfully processed {processed_count} records from CSV file: all were duplicates. Completed in {processing_time:.2f} seconds', 'warning')
        else:
            log_and_flash(f'Successfully processed {processed_count} records from CSV file. Completed in {processing_time:.2f} seconds', 'success')
        
    except Exception as e:
        logger.error(f'Error processing CSV file: {str(e)}', exc_info=True)
        log_and_flash(f'Error processing CSV file: {str(e)}', 'error')
        return redirect(url_for('index'))
    
    return redirect(url_for('index'))

@app.route('/search')
def search_cards():
    card_name = request.args.get('card_name', '')
    
    if not card_name:
        flash('Please enter a card name to search', 'error')
        return redirect(url_for('index'))
    
    results = db.search_cards(card_name)
    
    # Convert raw card names to display names for the template
    enhanced_results = []
    for result in results:
        enhanced_result = result.copy()
        enhanced_result['display_card_name'] = get_display_card_name(result['card_name'], result['card_set'])
        enhanced_result['display_set_name'] = get_display_set_name(result['card_set'])
        enhanced_results.append(enhanced_result)
    
    return render_template('search_results.html', results=enhanced_results, card_name=card_name)

@app.route('/processing_status')
def get_processing_status():
    """Get the status of background processing tasks"""
    task_id = request.args.get('task_id')
    
    if task_id:
        # Return status for a specific task
        with processing_lock:
            task_status = processing_status.get(task_id, {'status': 'not_found', 'message': 'Task not found'})
        return jsonify(task_status)
    else:
        # Return status for all tasks
        with processing_lock:
            all_statuses = processing_status.copy()
        return jsonify(all_statuses)

@app.route('/processing_status_page')
def processing_status_page():
    """Page to show processing status"""
    with processing_lock:
        active_tasks = {task_id: status for task_id, status in processing_status.items() 
                       if status.get('status') in ['processing', 'queued']}
        completed_tasks = {task_id: status for task_id, status in processing_status.items() 
                          if status.get('status') in ['completed', 'error']}
    
    return render_template('processing_status.html', 
                         active_tasks=active_tasks, 
                         completed_tasks=completed_tasks)

@app.route('/debug/test_screenshots', methods=['POST'])
def debug_test_screenshots():
    """Debug endpoint to test with a limited number of screenshots"""
    screenshots_path = request.form.get('screenshots_path')
    limit = int(request.form.get('limit', 5))  # Default to 5 screenshots
    
    if not screenshots_path:
        log_and_flash('No screenshots path provided for debug test', 'error')
        return redirect(url_for('debug'))
    
    logger.info(f"Debug testing with {limit} screenshots from: {screenshots_path}")
    log_and_flash(f'Starting debug test with {limit} screenshots...', 'info')
    
    # Try to handle Windows paths in WSL2
    screenshots_path = screenshots_path.strip()
    
    # Convert Windows path to WSL2 path if needed
    import re
    drive_match = re.match(r'^([A-Za-z]):[\\/]', screenshots_path)
    if drive_match:
        drive_letter = drive_match.group(1)
        original_path = screenshots_path
        screenshots_path = screenshots_path.replace(f'{drive_letter}:\\', f'/mnt/{drive_letter.lower()}/')
        screenshots_path = screenshots_path.replace(f'{drive_letter}:/', f'/mnt/{drive_letter.lower()}/')
        screenshots_path = screenshots_path.replace('\\', '/')
        logger.info(f"Converted Windows path: {original_path} -> {screenshots_path}")
    
    # Check if the path exists
    if not os.path.exists(screenshots_path):
        logger.error(f'Debug screenshot path does not exist: {screenshots_path}')
        log_and_flash(f'Screenshot path does not exist: {screenshots_path}', 'error')
        return redirect(url_for('debug'))
    
    # Check if it's a directory
    if not os.path.isdir(screenshots_path):
        logger.error(f'Debug path is not a directory: {screenshots_path}')
        log_and_flash(f'Path is not a directory: {screenshots_path}', 'error')
        return redirect(url_for('debug'))
    
    logger.info(f'Found debug screenshots directory: {screenshots_path}')
    log_and_flash('Found screenshots directory, scanning for image files...', 'info')
    
    # Get all image files
    image_files = [f for f in os.listdir(screenshots_path) 
                  if f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp', '.gif'))]
    
    if len(image_files) == 0:
        log_and_flash('No image files found in directory', 'error')
        return redirect(url_for('debug'))
    
    # Limit to specified number of files
    image_files = image_files[:limit]
    logger.info(f'Testing with {len(image_files)} screenshots: {image_files}')
    log_and_flash(f'Testing with {len(image_files)} screenshots...', 'info')
    
    # Load unprocessed screenshots once at the beginning for efficiency
    existing_screenshots = db.get_unprocessed_screenshots()
    screenshot_lookup = {screenshot['pack_screenshot']: screenshot for screenshot in existing_screenshots}
    
    processed_count = 0
    error_count = 0
    start_time = datetime.now()
    
    # Process limited number of screenshots
    for i, filename in enumerate(image_files):
        try:
            screenshot_path = os.path.join(screenshots_path, filename)
            
            # Check if this screenshot has already been processed
            # Use the pre-loaded screenshot lookup for efficiency
            matching_screenshot = screenshot_lookup.get(filename)
            
            if not matching_screenshot:
                logger.warning(f"No matching CSV record found for screenshot: {filename}")
                continue
            
            if not matching_screenshot:
                logger.warning(f"No matching CSV record found for screenshot: {filename}")
                continue
            
            logger.info(f'Debug processing screenshot {i+1}/{len(image_files)}: {filename}')
            
            # Process the screenshot to identify cards
            cards_found = image_processor.identify_cards_in_screenshot(screenshot_path)
            
            logger.info(f'Found {len(cards_found)} cards in {filename}')
            
            # Add the found cards to the database
            for card_info in cards_found:
                # Add the card to the cards table if it doesn't exist
                rarity = get_card_rarity(card_info['card_name'], card_info['card_set'])
                card_id = db.add_card(
                    card_info['card_name'],
                    card_info['card_set'],
                    f"{card_info['card_set']}/{card_info['card_name']}.webp",
                    rarity
                )
                
                # Add the relationship between screenshot and card
                db.add_screenshot_card(
                    matching_screenshot['id'],
                    card_id,
                    card_info['position'],
                    card_info['confidence']
                )
            
            # Mark the screenshot as processed
            db.mark_screenshot_processed(matching_screenshot['id'])
            
            processed_count += 1
            
        except Exception as e:
            logger.error(f"Error processing screenshot {filename}: {e}", exc_info=True)
            error_count += 1
    
    end_time = datetime.now()
    processing_time = (end_time - start_time).total_seconds()
    
    if processed_count > 0:
        logger.info(f'Debug test: Successfully processed {processed_count} screenshots in {processing_time:.2f} seconds')
        log_and_flash(f'Debug test: Successfully processed {processed_count} screenshots in {processing_time:.2f} seconds', 'success')
    else:
        logger.info('Debug test: No screenshots were processed (check CSV data)')
        log_and_flash('Debug test: No screenshots were processed (check CSV data)', 'info')
    
    if error_count > 0:
        logger.warning(f'Debug test: Encountered {error_count} errors during processing')
        log_and_flash(f'Debug test: Encountered {error_count} errors during processing', 'warning')
    
    return redirect(url_for('debug'))

@app.route('/process_screenshots', methods=['POST'])
def process_screenshots():
    # Get the local file path from the form
    screenshots_path = request.form.get('screenshots_path')
    
    if not screenshots_path:
        log_and_flash('No screenshots path provided', 'error')
        return redirect(url_for('index'))
    
    logger.info(f"Starting background processing for screenshots from path: {screenshots_path}")
    
    # Generate a unique task ID
    import uuid
    task_id = str(uuid.uuid4())
    
    # Start the background processing thread
    processing_thread = threading.Thread(
        target=process_screenshots_background,
        args=(screenshots_path, task_id),
        daemon=True
    )
    processing_thread.start()
    
    # Immediately return a response to the browser
    log_and_flash(f'Started background processing of screenshots. Task ID: {task_id}', 'info')
    logger.info(f"Background processing started with task ID: {task_id}")
    
    return redirect(url_for('index'))

def cleanup_old_processing_status():
    """Clean up old processing status entries"""
    try:
        with processing_lock:
            # Keep only the last 10 completed/error tasks
            completed_tasks = {task_id: status for task_id, status in processing_status.items() 
                              if status.get('status') in ['completed', 'error']}
            
            # Sort by end_time (newest first)
            sorted_tasks = sorted(completed_tasks.items(), 
                                key=lambda x: x[1].get('end_time', ''), 
                                reverse=True)
            
            # Keep only the 10 most recent completed tasks
            tasks_to_keep = sorted_tasks[:10]
            task_ids_to_keep = {task_id for task_id, _ in tasks_to_keep}
            
            # Remove old completed tasks
            for task_id in list(processing_status.keys()):
                if task_id not in task_ids_to_keep and processing_status[task_id].get('status') in ['completed', 'error']:
                    del processing_status[task_id]
                    logger.info(f"Cleaned up old processing status for task: {task_id}")
                    
    except Exception as e:
        logger.error(f"Error cleaning up processing status: {e}", exc_info=True)

# Schedule periodic cleanup (every hour)
import atexit

def periodic_cleanup():
    """Periodic cleanup function"""
    cleanup_old_processing_status()
    # Schedule next cleanup in 1 hour
    threading.Timer(3600, periodic_cleanup).start()

# Start periodic cleanup
periodic_cleanup()

# Cleanup on exit
atexit.register(cleanup_old_processing_status)

if __name__ == '__main__':
    app.run(debug=True)
