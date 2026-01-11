# Card Counter Application

A Flask web application for identifying Pokemon cards in pack screenshots.

## Features

- Upload CSV files containing screenshot metadata
- Process screenshots to identify cards using computer vision
- Search for specific cards across all processed screenshots
- Track which screenshots have been processed to avoid duplicates
- SQLite database for storing all data

## Requirements

- Python 3.7+
- Flask
- OpenCV
- Pillow
- Pandas
- NumPy

## Installation

1. Clone this repository or copy the files to your desired location
2. Run the setup script:
   ```bash
   python setup.py
   ```
3. Activate the virtual environment:
   ```bash
   source venv/bin/activate  # Linux/Mac
   venv\Scripts\activate    # Windows
   ```

## Directory Structure

- `card_imgs/` - Directory containing large card images organized by set (A2b, A3, A3a, etc.)
- `uploads/` - Directory where uploaded CSV files and screenshots are stored
- `cardcounter.db` - SQLite database file

## Usage

1. **Prepare your data:**
   - Place your large card images in the `card_imgs/` directory, organized by set
   - Each card image should be named with the card name and be in webp format (367x512 pixels)
   - Prepare your CSV file with the required columns

2. **Run the application:**
   ```bash
   python app.py
   ```

3. **Access the web interface:**
   - Open your browser to `http://localhost:5000`

4. **Load CSV:**
   - Enter the full local file path to your CSV file
   - For Windows paths: Use format like `D:\data\packs.csv`
   - For WSL2 paths: Use format like `/mnt/d/data/packs.csv`
   - Click "Load CSV" to import the data
   - The application will automatically convert Windows paths to WSL2 format

5. **Process Screenshots:**
   - Enter the full local file path to your screenshots directory
   - For Windows paths: Use format like `D:\ptcgp\Screenshots`
   - For WSL2 paths: Use format like `/mnt/d/ptcgp/Screenshots`
   - Click "Process Screenshots" to analyze the images
   - The application will automatically convert Windows paths to WSL2 format
   - The application will process all image files in the specified directory

6. **Search Cards:**
   - Enter a card name in the search box
   - Click "Search" to find all screenshots containing that card

## CSV Format

The CSV file should have the following columns:
- `Timestamp` - When the screenshot was taken
- `OriginalFilename` - Original filename of the screenshot
- `CleanFilename` - Cleaned/normalized filename
- `DeviceAccount` - Account/device that took the screenshot
- `PackType` - Type of pack
- `CardTypes` - Types of cards in the pack
- `CardCounts` - Counts of each card type
- `PackScreenshot` - Filename of the screenshot
- `Shinedust` - Shinedust information

## Image Processing

The application uses OpenCV for:
- Template matching to identify cards
- Edge detection to locate card positions in screenshots
- Image preprocessing (grayscale conversion, resizing)

## Database Schema

The application uses SQLite with the following tables:
- `screenshots` - Stores metadata about each screenshot
- `cards` - Stores information about each card
- `screenshot_cards` - Junction table linking screenshots to cards

## Configuration

You can configure the application by modifying the following in `app.py`:
- `UPLOAD_FOLDER` - Where to store uploaded files
- `ALLOWED_EXTENSIONS` - Allowed file types for upload
- `MAX_CONTENT_LENGTH` - Maximum upload size

## Notes

- The application expects screenshots to be 240x227 pixels
- Large card images should be 367x512 pixels in webp format
- Each screenshot should contain 5-6 cards
- The confidence threshold for card matching is 70% (can be adjusted in `image_processing.py`)
- For local development, the application uses direct file paths instead of uploads to handle large screenshot directories efficiently
- This is a local-only application designed for personal use with large file sizes
- **WSL2 Path Conversion**: The application automatically converts Windows paths (D:\...) to WSL2 paths (/mnt/d/...)
- **Drive Access**: Make sure your Windows drives are mounted in WSL2 (usually at /mnt/d/, /mnt/c/, etc.)