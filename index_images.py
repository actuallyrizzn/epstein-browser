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
import argparse

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


def migrate_database_schema():
    """Idempotent database schema migration for new fields"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        
        # Check if images table exists
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='images'
        """)
        if not cursor.fetchone():
            logger.info("Images table does not exist, skipping migration")
            return
        
        # Get current table schema
        cursor.execute("PRAGMA table_info(images)")
        columns = {row[1]: row for row in cursor.fetchall()}
        
        # Add ocr_quality_score column if it doesn't exist
        if 'ocr_quality_score' not in columns:
            logger.info("Adding ocr_quality_score column to images table")
            cursor.execute("""
                ALTER TABLE images ADD COLUMN ocr_quality_score INTEGER DEFAULT NULL
            """)
        else:
            logger.debug("ocr_quality_score column already exists")
        
        # Add ocr_rescan_attempts column if it doesn't exist
        if 'ocr_rescan_attempts' not in columns:
            logger.info("Adding ocr_rescan_attempts column to images table")
            cursor.execute("""
                ALTER TABLE images ADD COLUMN ocr_rescan_attempts INTEGER DEFAULT 0
            """)
        else:
            logger.debug("ocr_rescan_attempts column already exists")
        
        # Create indexes for new columns
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_images_ocr_quality_score ON images(ocr_quality_score)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_images_ocr_rescan_attempts ON images(ocr_rescan_attempts)")
        
        conn.commit()
        logger.info("Database schema migration completed successfully")


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
        
        # Create OCR content table for full-text search
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ocr_content (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                image_id INTEGER NOT NULL,
                content TEXT NOT NULL,
                content_hash TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (image_id) REFERENCES images (id) ON DELETE CASCADE
            )
        """)
        
        # Note: FTS5 table removed - using database search instead
        
        # Create indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_images_path ON images(file_path)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_images_directory ON images(directory_path)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_images_volume ON images(volume)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_images_type ON images(file_type)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_images_has_ocr_text ON images(has_ocr_text)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_images_file_name ON images(file_name)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_ocr_content_image_id ON ocr_content(image_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_ocr_content_search ON ocr_content(content)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_directories_path ON directories(path)")
        
        conn.commit()
        logger.info("Database initialized successfully")
        
        # Run schema migration for new fields
        migrate_database_schema()


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


def index_ocr_content(image_id: int, ocr_text_path: Path, cursor) -> bool:
    """Index OCR content for full-text search"""
    try:
        if not ocr_text_path.exists():
            return False
            
        # Read OCR content
        content = ocr_text_path.read_text(encoding='utf-8', errors='ignore')
        if not content.strip():
            return False
            
        # Calculate content hash
        content_hash = hashlib.md5(content.encode('utf-8')).hexdigest()
        
        # Check if OCR content already exists and is unchanged
        cursor.execute("""
            SELECT id, content_hash FROM ocr_content WHERE image_id = ?
        """, (image_id,))
        existing = cursor.fetchone()
        
        if existing and existing[1] == content_hash:
            # Content unchanged, skip
            return True
            
        # Delete existing OCR content if it exists
        if existing:
            cursor.execute("DELETE FROM ocr_content WHERE image_id = ?", (image_id,))
        
        # Insert new OCR content
        cursor.execute("""
            INSERT INTO ocr_content (image_id, content, content_hash)
            VALUES (?, ?, ?)
        """, (image_id, content, content_hash))
        
        return True
        
    except Exception as e:
        logger.error(f"Error indexing OCR content for image {image_id}: {e}")
        return False


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
        'ocr_content_indexed': 0,
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
                            
                            # Index OCR content if available
                            if has_ocr_text:
                                cursor.execute("SELECT id FROM images WHERE file_path = ?", (relative_path,))
                                image_id = cursor.fetchone()[0]
                                if index_ocr_content(image_id, ocr_text_path, cursor):
                                    stats['ocr_content_indexed'] = stats.get('ocr_content_indexed', 0) + 1
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
                        
                        # Index OCR content if available
                        if has_ocr_text:
                            cursor.execute("SELECT id FROM images WHERE file_path = ?", (relative_path,))
                            image_id = cursor.fetchone()[0]
                            if index_ocr_content(image_id, ocr_text_path, cursor):
                                stats['ocr_content_indexed'] = stats.get('ocr_content_indexed', 0) + 1
                    
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
        
        # Index OCR content for existing images that have OCR but no content indexed
        logger.info("Indexing OCR content for existing images...")
        cursor.execute("""
            SELECT i.id, i.file_path, i.has_ocr_text, i.ocr_text_path
            FROM images i
            LEFT JOIN ocr_content oc ON i.id = oc.image_id
            WHERE i.has_ocr_text = TRUE AND oc.image_id IS NULL
        """)
        ocr_images = cursor.fetchall()
        
        for image_id, file_path, has_ocr_text, ocr_text_path in ocr_images:
            try:
                if ocr_text_path:
                    ocr_file_path = DATA_DIR / ocr_text_path
                else:
                    # Fallback to .txt extension
                    ocr_file_path = DATA_DIR / file_path.replace(file_path.split('.')[-1], 'txt')
                
                if index_ocr_content(image_id, ocr_file_path, cursor):
                    stats['ocr_content_indexed'] = stats.get('ocr_content_indexed', 0) + 1
                    
                if stats['ocr_content_indexed'] % 1000 == 0:
                    logger.info(f"Indexed {stats['ocr_content_indexed']} OCR content records...")
                    
            except Exception as e:
                logger.error(f"Error indexing OCR content for image {image_id}: {e}")
                stats['errors'] += 1
        
        conn.commit()
    
    logger.info(f"Indexing complete: {stats}")
    return stats


def index_ocr_content_only():
    """Index OCR content for all existing images that have OCR but no content indexed"""
    if not DATA_DIR.exists():
        logger.error(f"Data directory {DATA_DIR} does not exist!")
        return
    
    stats = {
        'ocr_content_indexed': 0,
        'errors': 0
    }
    
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        
        # Get all images that have OCR but no content indexed
        logger.info("Finding images with OCR that need content indexing...")
        cursor.execute("""
            SELECT i.id, i.file_path, i.has_ocr_text, i.ocr_text_path
            FROM images i
            LEFT JOIN ocr_content oc ON i.id = oc.image_id
            WHERE i.has_ocr_text = TRUE AND oc.image_id IS NULL
        """)
        ocr_images = cursor.fetchall()
        
        total_images = len(ocr_images)
        logger.info(f"Found {total_images} images with OCR that need content indexing")
        
        for i, (image_id, file_path, has_ocr_text, ocr_text_path) in enumerate(ocr_images):
            try:
                if ocr_text_path:
                    ocr_file_path = DATA_DIR / ocr_text_path
                else:
                    # Fallback to .txt extension
                    ocr_file_path = DATA_DIR / file_path.replace(file_path.split('.')[-1], 'txt')
                
                if index_ocr_content(image_id, ocr_file_path, cursor):
                    stats['ocr_content_indexed'] += 1
                    
                if (i + 1) % 1000 == 0:
                    logger.info(f"Indexed {i + 1}/{total_images} OCR content records... ({stats['ocr_content_indexed']} successful)")
                    
            except Exception as e:
                logger.error(f"Error indexing OCR content for image {image_id}: {e}")
                stats['errors'] += 1
        
        conn.commit()
    
    logger.info(f"OCR content indexing complete: {stats}")
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
    parser = argparse.ArgumentParser(description='Epstein Documents Image Indexer')
    parser.add_argument('--ocr-only', action='store_true', 
                       help='Only index OCR content for existing images (skip image indexing)')
    parser.add_argument('--stats-only', action='store_true',
                       help='Only show database statistics (no indexing)')
    
    args = parser.parse_args()
    
    print("🔍 Epstein Documents Image Indexer")
    print("=" * 50)
    
    # Initialize database
    logger.info("Initializing database...")
    init_database()
    
    if args.stats_only:
        # Only show statistics
        show_statistics()
        return
    
    if args.ocr_only:
        # Only index OCR content
        logger.info("Starting OCR content indexing only...")
        stats = index_ocr_content_only()
        
        print(f"\n✅ OCR content indexing complete!")
        print(f"📊 Database: {DB_PATH}")
        print(f"📝 OCR content indexed: {stats['ocr_content_indexed']:,}")
        print(f"❌ Errors: {stats['errors']}")
    else:
        # Full indexing
        logger.info("Starting full image indexing...")
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
        print(f"📝 OCR content indexed: {stats['ocr_content_indexed']:,}")
        print(f"❌ Errors: {stats['errors']}")


if __name__ == "__main__":
    main()
