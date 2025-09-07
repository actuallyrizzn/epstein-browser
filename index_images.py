#!/usr/bin/env python3
"""
Image Indexer for Epstein Documents

Simple script to scan and index all image files into a SQLite database
so we can understand what we're working with.

Copyright (C) 2025 Epstein Documents OCR Project

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published
by the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""

import sqlite3
import logging
from pathlib import Path
from datetime import datetime
import hashlib

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
DATA_DIR = Path("data")
DB_PATH = "images.db"
IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.tif', '.tiff', '.bmp', '.webp', '.gif'}


def init_database():
    """Initialize the SQLite database"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        
        # Create images table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS images (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_path TEXT UNIQUE NOT NULL,
                file_name TEXT NOT NULL,
                file_size INTEGER NOT NULL,
                file_type TEXT NOT NULL,
                directory_path TEXT NOT NULL,
                volume TEXT,
                subdirectory TEXT,
                file_hash TEXT,
                has_ocr_text BOOLEAN DEFAULT FALSE,
                ocr_text_path TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create directories table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS directories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                path TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                parent_path TEXT,
                level INTEGER NOT NULL,
                file_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_images_path ON images(file_path)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_images_directory ON images(directory_path)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_images_volume ON images(volume)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_images_type ON images(file_type)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_directories_path ON directories(path)")
        
        conn.commit()
        logger.info("Database initialized successfully")


def calculate_file_hash(file_path: Path) -> str:
    """Calculate MD5 hash of file"""
    try:
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    except Exception as e:
        logger.warning(f"Could not calculate hash for {file_path}: {e}")
        return ""


def index_images():
    """Index all image files (idempotent - preserves existing data)"""
    if not DATA_DIR.exists():
        logger.error(f"Data directory {DATA_DIR} does not exist!")
        return
    
    stats = {
        'images_indexed': 0,
        'images_updated': 0,
        'images_skipped': 0,
        'images_deleted': 0,
        'directories_indexed': 0,
        'directories_updated': 0,
        'errors': 0
    }
    
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        
        # Get existing data for comparison
        existing_images = {}
        cursor.execute("SELECT file_path, file_hash, has_ocr_text, ocr_text_path FROM images")
        for row in cursor.fetchall():
            existing_images[row[0]] = {
                'hash': row[1],
                'has_ocr_text': row[2],
                'ocr_text_path': row[3]
            }
        
        existing_directories = set()
        cursor.execute("SELECT path FROM directories")
        for row in cursor.fetchall():
            existing_directories.add(row[0])
        
        # Track current files to detect deletions
        current_files = set()
        current_directories = set()
        
        # Index directories first
        logger.info("Indexing directories...")
        for dir_path in DATA_DIR.rglob("*"):
            if dir_path.is_dir():
                try:
                    relative_path = str(dir_path.relative_to(DATA_DIR))
                    parent_path = str(dir_path.parent.relative_to(DATA_DIR)) if dir_path.parent != DATA_DIR else None
                    level = len(relative_path.split('\\')) - 1
                    current_directories.add(relative_path)
                    
                    if relative_path in existing_directories:
                        # Directory exists, update if needed
                        cursor.execute("""
                            UPDATE directories 
                            SET name = ?, parent_path = ?, level = ?
                            WHERE path = ?
                        """, (dir_path.name, parent_path, level, relative_path))
                        stats['directories_updated'] += 1
                    else:
                        # New directory
                        cursor.execute("""
                            INSERT INTO directories (path, name, parent_path, level)
                            VALUES (?, ?, ?, ?)
                        """, (relative_path, dir_path.name, parent_path, level))
                        stats['directories_indexed'] += 1
                        
                except Exception as e:
                    logger.error(f"Error indexing directory {dir_path}: {e}")
                    stats['errors'] += 1
        
        # Index images
        logger.info("Indexing images...")
        # Get all image files and sort them properly
        image_files = []
        for file_path in DATA_DIR.rglob("*"):
            if file_path.is_file() and file_path.suffix.lower() in IMAGE_EXTENSIONS:
                image_files.append(file_path)
        
        # Sort by path to ensure consistent order (IMAGES001, IMAGES002, etc.)
        image_files.sort(key=lambda x: str(x))
        
        for file_path in image_files:
                try:
                    relative_path = str(file_path.relative_to(DATA_DIR))
                    directory_path = str(file_path.parent.relative_to(DATA_DIR))
                    current_files.add(relative_path)
                    
                    # Extract volume and subdirectory info
                    path_parts = relative_path.split('\\')
                    volume = None
                    subdirectory = None
                    
                    for part in path_parts:
                        if part.startswith('VOL'):
                            volume = part
                            break
                    
                    if len(path_parts) > 2:
                        subdirectory = '\\'.join(path_parts[2:-1]) if len(path_parts) > 3 else path_parts[2]
                    
                    # Check for OCR text file
                    ocr_text_path = file_path.with_suffix('.txt')
                    has_ocr_text = ocr_text_path.exists()
                    
                    # Calculate file hash
                    file_hash = calculate_file_hash(file_path)
                    
                    # Check if file already exists and if it's changed
                    if relative_path in existing_images:
                        existing_data = existing_images[relative_path]
                        
                        # Check if file has changed (hash comparison)
                        if existing_data['hash'] == file_hash:
                            # File unchanged, preserve OCR status
                            stats['images_skipped'] += 1
                            continue
                        else:
                            # File changed, update but preserve OCR status if still valid
                            if existing_data['has_ocr_text'] and has_ocr_text:
                                # Keep existing OCR status
                                has_ocr_text = existing_data['has_ocr_text']
                                ocr_text_path_str = existing_data['ocr_text_path']
                            else:
                                # Update OCR status based on current file
                                ocr_text_path_str = str(ocr_text_path.relative_to(DATA_DIR)) if has_ocr_text else None
                            
                            cursor.execute("""
                                UPDATE images 
                                SET file_name = ?, file_size = ?, file_type = ?, directory_path = ?,
                                    volume = ?, subdirectory = ?, file_hash = ?, has_ocr_text = ?, 
                                    ocr_text_path = ?, updated_at = CURRENT_TIMESTAMP
                                WHERE file_path = ?
                            """, (
                                file_path.name,
                                file_path.stat().st_size,
                                file_path.suffix.lower(),
                                directory_path,
                                volume,
                                subdirectory,
                                file_hash,
                                has_ocr_text,
                                ocr_text_path_str,
                                relative_path
                            ))
                            stats['images_updated'] += 1
                    else:
                        # New file
                        cursor.execute("""
                            INSERT INTO images 
                            (file_path, file_name, file_size, file_type, directory_path, 
                             volume, subdirectory, file_hash, has_ocr_text, ocr_text_path)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            relative_path,
                            file_path.name,
                            file_path.stat().st_size,
                            file_path.suffix.lower(),
                            directory_path,
                            volume,
                            subdirectory,
                            file_hash,
                            has_ocr_text,
                            str(ocr_text_path.relative_to(DATA_DIR)) if has_ocr_text else None
                        ))
                        stats['images_indexed'] += 1
                    
                    total_processed = stats['images_indexed'] + stats['images_updated'] + stats['images_skipped']
                    if total_processed % 1000 == 0:
                        logger.info(f"Processed {total_processed} images... (new: {stats['images_indexed']}, updated: {stats['images_updated']}, skipped: {stats['images_skipped']})")
                        
                except Exception as e:
                    logger.error(f"Error indexing image {file_path}: {e}")
                    stats['errors'] += 1
        
        # Handle deleted files
        logger.info("Checking for deleted files...")
        for existing_path in existing_images:
            if existing_path not in current_files:
                cursor.execute("DELETE FROM images WHERE file_path = ?", (existing_path,))
                stats['images_deleted'] += 1
        
        # Handle deleted directories
        for existing_dir in existing_directories:
            if existing_dir not in current_directories:
                cursor.execute("DELETE FROM directories WHERE path = ?", (existing_dir,))
        
        # Update directory file counts
        logger.info("Updating directory file counts...")
        cursor.execute("""
            UPDATE directories 
            SET file_count = (
                SELECT COUNT(*) 
                FROM images 
                WHERE images.directory_path = directories.path
            )
        """)
        
        conn.commit()
    
    logger.info(f"Indexing complete: {stats}")
    return stats


def show_statistics():
    """Show database statistics"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        
        # Total images
        cursor.execute("SELECT COUNT(*) FROM images")
        total_images = cursor.fetchone()[0]
        
        # Images with OCR
        cursor.execute("SELECT COUNT(*) FROM images WHERE has_ocr_text = TRUE")
        images_with_ocr = cursor.fetchone()[0]
        
        # Total directories
        cursor.execute("SELECT COUNT(*) FROM directories")
        total_directories = cursor.fetchone()[0]
        
        # Volume breakdown
        cursor.execute("""
            SELECT volume, COUNT(*) as image_count 
            FROM images 
            WHERE volume IS NOT NULL 
            GROUP BY volume 
            ORDER BY volume
        """)
        volumes = cursor.fetchall()
        
        # Directory breakdown
        cursor.execute("""
            SELECT path, file_count 
            FROM directories 
            WHERE file_count > 0 
            ORDER BY file_count DESC 
            LIMIT 10
        """)
        top_directories = cursor.fetchall()
        
        print(f"\n{'='*60}")
        print(f"DATABASE STATISTICS")
        print(f"{'='*60}")
        print(f"Total images: {total_images:,}")
        print(f"Images with OCR: {images_with_ocr:,}")
        print(f"OCR percentage: {(images_with_ocr/total_images*100):.1f}%" if total_images > 0 else "0%")
        print(f"Total directories: {total_directories}")
        
        print(f"\nVOLUME BREAKDOWN:")
        for volume, count in volumes:
            print(f"  {volume}: {count:,} images")
        
        print(f"\nTOP DIRECTORIES BY FILE COUNT:")
        for path, count in top_directories:
            print(f"  {path}: {count:,} images")
        
        print(f"{'='*60}")


def main():
    """Main function"""
    print("🔍 Epstein Documents Image Indexer")
    print("=" * 50)
    
    # Initialize database
    logger.info("Initializing database...")
    init_database()
    
    # Index images
    logger.info("Starting image indexing...")
    stats = index_images()
    
    # Show statistics
    show_statistics()
    
    print(f"\n✅ Indexing complete!")
    print(f"📊 Database: {DB_PATH}")
    print(f"📁 New images: {stats['images_indexed']:,}")
    print(f"🔄 Updated images: {stats['images_updated']:,}")
    print(f"⏭️ Skipped images: {stats['images_skipped']:,}")
    print(f"🗑️ Deleted images: {stats['images_deleted']:,}")
    print(f"📂 New directories: {stats['directories_indexed']}")
    print(f"🔄 Updated directories: {stats['directories_updated']}")
    print(f"❌ Errors: {stats['errors']}")


if __name__ == "__main__":
    main()
