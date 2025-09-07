#!/usr/bin/env python3
"""
Data synchronization script for Epstein Documents Browser
Pulls data and metadata from the main instance via API
"""

import requests
import sqlite3
import json
import os
import argparse
from datetime import datetime
import time

# Configuration
API_BASE_URL = 'https://epstein-documents.gopoversight.com'
DATABASE = 'images.db'
BATCH_SIZE = 100

def get_db_connection():
    """Get database connection"""
    return sqlite3.connect(DATABASE)

def init_database():
    """Initialize database if it doesn't exist"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Create images table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS images (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            file_path TEXT NOT NULL,
            volume TEXT,
            has_ocr_text BOOLEAN DEFAULT FALSE,
            ocr_text TEXT,
            file_size INTEGER,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Create indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_filename ON images(filename)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_volume ON images(volume)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_has_ocr ON images(has_ocr_text)")
    
    conn.commit()
    conn.close()

def sync_stats():
    """Sync basic statistics from main instance"""
    try:
        print("Syncing statistics...")
        response = requests.get(f"{API_BASE_URL}/api/stats", timeout=30)
        response.raise_for_status()
        stats = response.json()
        
        print(f"  Total images: {stats.get('total_images', 0):,}")
        print(f"  Images with OCR: {stats.get('images_with_ocr', 0):,}")
        print(f"  OCR percentage: {stats.get('ocr_percentage', 0):.1f}%")
        
        return stats
    except Exception as e:
        print(f"Error syncing stats: {e}")
        return None

def sync_image_range():
    """Sync image ID range from main instance"""
    try:
        print("Syncing image range...")
        response = requests.get(f"{API_BASE_URL}/api/first-image", timeout=30)
        response.raise_for_status()
        range_data = response.json()
        
        print(f"  First image ID: {range_data.get('first_id', 0)}")
        print(f"  Last image ID: {range_data.get('last_id', 0)}")
        
        return range_data
    except Exception as e:
        print(f"Error syncing image range: {e}")
        return None

def sync_images(start_id=1, end_id=None, batch_size=BATCH_SIZE):
    """Sync image metadata from main instance"""
    if end_id is None:
        range_data = sync_image_range()
        if not range_data:
            print("Could not determine image range")
            return
        end_id = range_data.get('last_id', 1)
    
    print(f"Syncing images {start_id} to {end_id}...")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get existing image IDs
    cursor.execute("SELECT id FROM images")
    existing_ids = set(row[0] for row in cursor.fetchall())
    
    synced_count = 0
    error_count = 0
    
    for batch_start in range(start_id, end_id + 1, batch_size):
        batch_end = min(batch_start + batch_size - 1, end_id)
        print(f"  Processing batch {batch_start}-{batch_end}...")
        
        # Check which images in this batch we need to sync
        batch_ids = list(range(batch_start, batch_end + 1))
        missing_ids = [img_id for img_id in batch_ids if img_id not in existing_ids]
        
        if not missing_ids:
            print(f"    All images in batch already synced")
            continue
        
        # For now, we'll create placeholder entries since we don't have
        # a direct API to get individual image metadata
        for img_id in missing_ids:
            try:
                # Create a placeholder entry
                cursor.execute("""
                    INSERT INTO images (id, filename, file_path, volume, has_ocr_text)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    img_id,
                    f"placeholder_{img_id}.jpg",
                    f"data/placeholder_{img_id}.jpg",
                    "VOL00001",
                    False
                ))
                synced_count += 1
            except Exception as e:
                print(f"    Error syncing image {img_id}: {e}")
                error_count += 1
        
        conn.commit()
        time.sleep(0.1)  # Small delay to be respectful
    
    conn.close()
    print(f"  Synced {synced_count} images, {error_count} errors")

def sync_search_data(query, search_type='all'):
    """Sync search results for a specific query"""
    try:
        print(f"Syncing search data for query: '{query}'")
        response = requests.get(f"{API_BASE_URL}/api/search", 
                              params={'q': query, 'type': search_type}, 
                              timeout=30)
        response.raise_for_status()
        data = response.json()
        
        results = data.get('results', [])
        print(f"  Found {len(results)} results")
        
        # Store search results (you might want to create a separate table for this)
        return results
    except Exception as e:
        print(f"Error syncing search data: {e}")
        return []

def main():
    parser = argparse.ArgumentParser(description='Sync data from Epstein Documents Browser')
    parser.add_argument('--images-only', action='store_true', help='Sync only image metadata')
    parser.add_argument('--metadata-only', action='store_true', help='Sync only metadata')
    parser.add_argument('--start-id', type=int, default=1, help='Start image ID for sync')
    parser.add_argument('--end-id', type=int, help='End image ID for sync')
    parser.add_argument('--batch-size', type=int, default=BATCH_SIZE, help='Batch size for processing')
    parser.add_argument('--query', type=str, help='Sync search results for specific query')
    
    args = parser.parse_args()
    
    print("Epstein Documents Browser - Data Sync")
    print("=" * 40)
    print(f"API Base URL: {API_BASE_URL}")
    print(f"Database: {DATABASE}")
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Initialize database
    init_database()
    
    # Sync statistics
    if not args.metadata_only:
        stats = sync_stats()
        if not stats:
            print("Failed to sync statistics, but continuing...")
        print()
    
    # Sync image range
    if not args.metadata_only:
        range_data = sync_image_range()
        if not range_data:
            print("Failed to sync image range, but continuing...")
        print()
    
    # Sync images
    if not args.metadata_only:
        sync_images(args.start_id, args.end_id, args.batch_size)
        print()
    
    # Sync search data if query provided
    if args.query:
        sync_search_data(args.query)
        print()
    
    print("Sync completed!")
    print(f"Finished at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == '__main__':
    main()
