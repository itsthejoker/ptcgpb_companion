import os
import shutil
import json
import time
from pathlib import Path
import numpy as np
import cv2
import django
from django.conf import settings

# Ensure we can import from the root directory
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Configure Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings")
try:
    django.setup()
except Exception:
    if not settings.configured:
        settings.configure(
            INSTALLED_APPS=("app.db",),
            DATABASES={
                "default": {
                    "ENGINE": "django.db.backends.sqlite3",
                    "NAME": ":memory:",
                }
            },
        )
        django.setup()

from app.image_processing import ImageProcessor

def test_force_recompute_invalidates_phashes():
    temp_dir = Path("test_card_imgs_tmp")
    if temp_dir.exists():
        shutil.rmtree(temp_dir)
    temp_dir.mkdir()
    
    try:
        # Create a mock set and image
        set_dir = temp_dir / "S1"
        set_dir.mkdir()
        img = np.ones((100, 100, 3), dtype=np.uint8) * 255
        cv2.imwrite(str(set_dir / "1.png"), img)
        
        # Reset session_refreshed for testing
        ImageProcessor._session_refreshed = False

        # First initialization
        p1 = ImageProcessor(str(temp_dir))
        hash_file = temp_dir / "phashes.json"
        assert hash_file.exists()
        
        # Add a "corrupt" or "old" entry to phashes.json to see if it survives
        with open(hash_file, "r") as f:
            data = json.load(f)
        data["OLD_SET"] = {"OLD_CARD": "OLD_HASH"}
        with open(hash_file, "w") as f:
            json.dump(data, f)
            
        mtime1 = os.path.getmtime(hash_file)
        time.sleep(1.1)
        
        # Initialize with force_recompute=True
        p2 = ImageProcessor(str(temp_dir), force_recompute=True)
        
        # Verify it was recreated
        mtime2 = os.path.getmtime(hash_file)
        assert mtime2 > mtime1
        
        with open(hash_file, "r") as f:
            data2 = json.load(f)
            
        # "OLD_SET" should be GONE because the file was deleted and recreated from scratch
        assert "OLD_SET" not in data2
        assert "S1" in data2
        assert "1" in data2["S1"]
    finally:
        if temp_dir.exists():
            shutil.rmtree(temp_dir)

if __name__ == "__main__":
    test_force_recompute_invalidates_phashes()
    print("Test passed!")
