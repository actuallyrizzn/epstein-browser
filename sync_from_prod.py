#!/usr/bin/env python3
"""
Sync Missing Files from Production Site
Pulls missing DOJ-OGR-00000001 and DOJ-OGR-00000002 files from epstein.rizzn.net
"""
import requests
import os
from pathlib import Path
import time
import urllib.parse

PROD_BASE_URL = "https://epstein.rizzn.net"
LOCAL_DATA_DIR = Path("data/Prod 01_20250822/VOL00001/IMAGES/IMAGES001")

def download_file(url, local_path):
    """Download a file from URL to local path"""
    try:
        print(f"Downloading {url}...")
        response = requests.get(url, stream=True, timeout=30)
        response.raise_for_status()
        
        # Create directory if it doesn't exist
        local_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(local_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        print(f"✓ Downloaded {local_path.name} ({len(response.content)} bytes)")
        return True
    except Exception as e:
        print(f"✗ Failed to download {url}: {e}")
        return False

def check_prod_file_exists(filename):
    """Check if a file exists on production site by trying to access it"""
    try:
        # Try different URL patterns
        patterns = [
            f"{PROD_BASE_URL}/image/Prod%2001_20250822/VOL00001/IMAGES/IMAGES001/{filename}",
            f"{PROD_BASE_URL}/image/Prod%2001_20250822/VOL00001/IMAGES/IMAGES001/{urllib.parse.quote(filename)}",
            f"{PROD_BASE_URL}/image/Prod 01_20250822/VOL00001/IMAGES/IMAGES001/{filename}",
        ]
        
        for url in patterns:
            try:
                response = requests.head(url, timeout=10)
                if response.status_code == 200:
                    print(f"✓ Found {filename} at {url}")
                    return url
            except:
                continue
        
        return None
    except Exception as e:
        print(f"Error checking {filename}: {e}")
        return None

def main():
    print("=== SYNCING MISSING FILES FROM PRODUCTION ===")
    print()
    
    # Files we need to check for
    missing_files = [
        "DOJ-OGR-00000001.tif",
        "DOJ-OGR-00000001.jpg", 
        "DOJ-OGR-00000002.tif",
        "DOJ-OGR-00000002.jpg"
    ]
    
    downloaded_count = 0
    
    for filename in missing_files:
        local_path = LOCAL_DATA_DIR / filename
        
        # Skip if already exists locally
        if local_path.exists():
            print(f"✓ {filename} already exists locally")
            continue
        
        # Check if it exists on production
        prod_url = check_prod_file_exists(filename)
        if not prod_url:
            print(f"✗ {filename} not found on production")
            continue
        
        # Download it
        if download_file(prod_url, local_path):
            downloaded_count += 1
        
        # Be nice to the server
        time.sleep(1)
    
    print()
    print(f"Downloaded {downloaded_count} missing files")
    
    if downloaded_count > 0:
        print("Now run: python index_images.py")
        print("Then restart the app to see the fixed document sequence")

if __name__ == "__main__":
    main()
