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
    """Index all image files"""
    if not DATA_DIR.exists():
        logger.error(f"Data directory {DATA_DIR} does not exist!")
        return
    
    stats = {
        'images_indexed': 0,
        'directories_indexed': 0,
        'errors': 0
    }
    
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        
        # Clear existing data
        cursor.execute("DELETE FROM images")
        cursor.execute("DELETE FROM directories")
        
        # Index directories first
        logger.info("Indexing directories...")
        for dir_path in DATA_DIR.rglob("*"):
            if dir_path.is_dir():
                try:
                    relative_path = str(dir_path.relative_to(DATA_DIR))
                    parent_path = str(dir_path.parent.relative_to(DATA_DIR)) if dir_path.parent != DATA_DIR else None
                    level = len(relative_path.split('\\')) - 1
                    
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
        for file_path in DATA_DIR.rglob("*"):
            if file_path.is_file() and file_path.suffix.lower() in IMAGE_EXTENSIONS:
                try:
                    relative_path = str(file_path.relative_to(DATA_DIR))
                    directory_path = str(file_path.parent.relative_to(DATA_DIR))
                    
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
                    
                    # Insert image record
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
                    
                    if stats['images_indexed'] % 1000 == 0:
                        logger.info(f"Indexed {stats['images_indexed']} images...")
                        
                except Exception as e:
                    logger.error(f"Error indexing image {file_path}: {e}")
                    stats['errors'] += 1
        
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
    print(f"📁 Images indexed: {stats['images_indexed']:,}")
    print(f"📂 Directories indexed: {stats['directories_indexed']}")
    print(f"❌ Errors: {stats['errors']}")


if __name__ == "__main__":
    main()
