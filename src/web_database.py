#!/usr/bin/env python3
"""
Web Database for Epstein Documents Browser

This module provides a separate database specifically for the web application
to index and browse all downloaded files, independent of OCR processing tracking.

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
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import hashlib

logger = logging.getLogger(__name__)


class WebDatabase:
    """Database for web application file indexing and browsing"""
    
    def __init__(self, db_path: str = "web_database.db"):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Initialize the database with required tables"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Files table - indexes all downloaded files
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS files (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_path TEXT UNIQUE NOT NULL,
                    file_name TEXT NOT NULL,
                    file_size INTEGER NOT NULL,
                    file_type TEXT NOT NULL,
                    directory_path TEXT NOT NULL,
                    volume TEXT,
                    subdirectory TEXT,
                    file_hash TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Directories table - tracks directory structure
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
            
            # OCR status table - links to OCR progress
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS ocr_status (
                    file_id INTEGER PRIMARY KEY,
                    has_ocr_text BOOLEAN DEFAULT FALSE,
                    ocr_text_path TEXT,
                    ocr_processed_at TIMESTAMP,
                    ocr_status TEXT DEFAULT 'pending',
                    FOREIGN KEY (file_id) REFERENCES files (id)
                )
            """)
            
            # Create indexes for better performance
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_files_path ON files(file_path)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_files_directory ON files(directory_path)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_files_volume ON files(volume)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_files_type ON files(file_type)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_directories_path ON directories(path)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_directories_parent ON directories(parent_path)")
            
            conn.commit()
            logger.info("Web database initialized successfully")
    
    def calculate_file_hash(self, file_path: Path) -> str:
        """Calculate MD5 hash of file for duplicate detection"""
        try:
            hash_md5 = hashlib.md5()
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except Exception as e:
            logger.warning(f"Could not calculate hash for {file_path}: {e}")
            return ""
    
    def index_directory(self, data_dir: Path) -> Dict[str, int]:
        """Index all files in the data directory"""
        stats = {
            'files_indexed': 0,
            'directories_indexed': 0,
            'errors': 0
        }
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Clear existing data
            cursor.execute("DELETE FROM files")
            cursor.execute("DELETE FROM directories")
            cursor.execute("DELETE FROM ocr_status")
            
            # Index directories first
            for dir_path in data_dir.rglob("*"):
                if dir_path.is_dir():
                    try:
                        self._index_directory(cursor, dir_path, data_dir)
                        stats['directories_indexed'] += 1
                    except Exception as e:
                        logger.error(f"Error indexing directory {dir_path}: {e}")
                        stats['errors'] += 1
            
            # Index files
            image_extensions = {'.jpg', '.jpeg', '.png', '.tif', '.tiff', '.bmp', '.webp', '.gif'}
            for file_path in data_dir.rglob("*"):
                if file_path.is_file() and file_path.suffix.lower() in image_extensions:
                    try:
                        self._index_file(cursor, file_path, data_dir)
                        stats['files_indexed'] += 1
                    except Exception as e:
                        logger.error(f"Error indexing file {file_path}: {e}")
                        stats['errors'] += 1
            
            # Update directory file counts
            self._update_directory_counts(cursor)
            
            conn.commit()
        
        logger.info(f"Indexing complete: {stats}")
        return stats
    
    def _index_directory(self, cursor: sqlite3.Cursor, dir_path: Path, data_dir: Path):
        """Index a single directory"""
        relative_path = str(dir_path.relative_to(data_dir))
        parent_path = str(dir_path.parent.relative_to(data_dir)) if dir_path.parent != data_dir else None
        level = len(relative_path.split('\\')) - 1
        
        cursor.execute("""
            INSERT OR REPLACE INTO directories (path, name, parent_path, level)
            VALUES (?, ?, ?, ?)
        """, (relative_path, dir_path.name, parent_path, level))
    
    def _index_file(self, cursor: sqlite3.Cursor, file_path: Path, data_dir: Path):
        """Index a single file"""
        relative_path = str(file_path.relative_to(data_dir))
        directory_path = str(file_path.parent.relative_to(data_dir))
        
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
        file_hash = self.calculate_file_hash(file_path)
        
        # Insert file record
        cursor.execute("""
            INSERT OR REPLACE INTO files 
            (file_path, file_name, file_size, file_type, directory_path, volume, subdirectory, file_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            relative_path,
            file_path.name,
            file_path.stat().st_size,
            file_path.suffix.lower(),
            directory_path,
            volume,
            subdirectory,
            file_hash
        ))
        
        # Get file ID for OCR status
        cursor.execute("SELECT id FROM files WHERE file_path = ?", (relative_path,))
        file_id = cursor.fetchone()[0]
        
        # Insert OCR status
        cursor.execute("""
            INSERT OR REPLACE INTO ocr_status 
            (file_id, has_ocr_text, ocr_text_path, ocr_processed_at, ocr_status)
            VALUES (?, ?, ?, ?, ?)
        """, (
            file_id,
            has_ocr_text,
            str(ocr_text_path.relative_to(data_dir)) if has_ocr_text else None,
            datetime.now().isoformat() if has_ocr_text else None,
            'completed' if has_ocr_text else 'pending'
        ))
    
    def _update_directory_counts(self, cursor: sqlite3.Cursor):
        """Update file counts for each directory"""
        cursor.execute("""
            UPDATE directories 
            SET file_count = (
                SELECT COUNT(*) 
                FROM files 
                WHERE files.directory_path = directories.path
            )
        """)
    
    def get_directory_tree(self) -> List[Dict[str, Any]]:
        """Get the complete directory tree structure"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT * FROM directories 
                ORDER BY level, path
            """)
            
            return [dict(row) for row in cursor.fetchall()]
    
    def get_files_by_directory(self, directory_path: str, page: int = 1, per_page: int = 50) -> Tuple[List[Dict[str, Any]], int]:
        """Get files in a specific directory with pagination"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Get total count
            cursor.execute("SELECT COUNT(*) FROM files WHERE directory_path = ?", (directory_path,))
            total = cursor.fetchone()[0]
            
            # Get paginated results
            offset = (page - 1) * per_page
            cursor.execute("""
                SELECT f.*, o.has_ocr_text, o.ocr_status, o.ocr_text_path
                FROM files f
                LEFT JOIN ocr_status o ON f.id = o.file_id
                WHERE f.directory_path = ?
                ORDER BY f.file_name
                LIMIT ? OFFSET ?
            """, (directory_path, per_page, offset))
            
            files = [dict(row) for row in cursor.fetchall()]
            
            return files, total
    
    def get_files_by_volume(self, volume: str, page: int = 1, per_page: int = 50) -> Tuple[List[Dict[str, Any]], int]:
        """Get files in a specific volume with pagination"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Get total count
            cursor.execute("SELECT COUNT(*) FROM files WHERE volume = ?", (volume,))
            total = cursor.fetchone()[0]
            
            # Get paginated results
            offset = (page - 1) * per_page
            cursor.execute("""
                SELECT f.*, o.has_ocr_text, o.ocr_status, o.ocr_text_path
                FROM files f
                LEFT JOIN ocr_status o ON f.id = o.file_id
                WHERE f.volume = ?
                ORDER BY f.file_name
                LIMIT ? OFFSET ?
            """, (volume, per_page, offset))
            
            files = [dict(row) for row in cursor.fetchall()]
            
            return files, total
    
    def get_all_files(self, page: int = 1, per_page: int = 50) -> Tuple[List[Dict[str, Any]], int]:
        """Get all files with pagination"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Get total count
            cursor.execute("SELECT COUNT(*) FROM files")
            total = cursor.fetchone()[0]
            
            # Get paginated results
            offset = (page - 1) * per_page
            cursor.execute("""
                SELECT f.*, o.has_ocr_text, o.ocr_status, o.ocr_text_path
                FROM files f
                LEFT JOIN ocr_status o ON f.id = o.file_id
                ORDER BY f.file_name
                LIMIT ? OFFSET ?
            """, (per_page, offset))
            
            files = [dict(row) for row in cursor.fetchall()]
            
            return files, total
    
    def get_file_by_path(self, file_path: str) -> Optional[Dict[str, Any]]:
        """Get a specific file by its path"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT f.*, o.has_ocr_text, o.ocr_status, o.ocr_text_path
                FROM files f
                LEFT JOIN ocr_status o ON f.id = o.file_id
                WHERE f.file_path = ?
            """, (file_path,))
            
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get overall statistics"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Total files
            cursor.execute("SELECT COUNT(*) FROM files")
            total_files = cursor.fetchone()[0]
            
            # Files with OCR
            cursor.execute("SELECT COUNT(*) FROM ocr_status WHERE has_ocr_text = TRUE")
            files_with_ocr = cursor.fetchone()[0]
            
            # Total directories
            cursor.execute("SELECT COUNT(*) FROM directories")
            total_directories = cursor.fetchone()[0]
            
            # Volume breakdown
            cursor.execute("""
                SELECT volume, COUNT(*) as file_count 
                FROM files 
                WHERE volume IS NOT NULL 
                GROUP BY volume 
                ORDER BY volume
            """)
            volumes = [{'volume': row[0], 'file_count': row[1]} for row in cursor.fetchall()]
            
            return {
                'total_files': total_files,
                'files_with_ocr': files_with_ocr,
                'total_directories': total_directories,
                'volumes': volumes,
                'ocr_percentage': (files_with_ocr / total_files * 100) if total_files > 0 else 0
            }
    
    def close(self):
        """Close database connection"""
        pass  # SQLite connections are closed automatically


if __name__ == "__main__":
    # Test the web database
    import sys
    from pathlib import Path
    
    logging.basicConfig(level=logging.INFO)
    
    # Initialize database
    db = WebDatabase()
    
    # Index the data directory
    data_dir = Path("data")
    if data_dir.exists():
        print("Indexing data directory...")
        stats = db.index_directory(data_dir)
        print(f"Indexing complete: {stats}")
        
        # Show statistics
        stats = db.get_statistics()
        print(f"\nDatabase Statistics:")
        print(f"Total files: {stats['total_files']}")
        print(f"Files with OCR: {stats['files_with_ocr']}")
        print(f"Total directories: {stats['total_directories']}")
        print(f"OCR percentage: {stats['ocr_percentage']:.1f}%")
        
        # Show volumes
        print(f"\nVolumes:")
        for vol in stats['volumes']:
            print(f"  {vol['volume']}: {vol['file_count']} files")
    else:
        print("Data directory not found!")
        sys.exit(1)
