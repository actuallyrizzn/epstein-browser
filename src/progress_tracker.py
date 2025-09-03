"""
Progress Tracking System for OCR Processing

SQLite-based progress tracking for idempotent OCR processing of 33,657 images.

Copyright (C) 2025 Epstein Documents Analysis Team

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""

import sqlite3
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any
import logging

logger = logging.getLogger(__name__)


class ProgressTracker:
    """
    SQLite-based progress tracker for OCR processing
    """
    
    def __init__(self, db_path: str = "ocr_progress.db"):
        """
        Initialize progress tracker
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self._init_database()
    
    def _init_database(self):
        """Initialize SQLite database with required tables"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Create files table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS files (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_path TEXT UNIQUE NOT NULL,
                    file_name TEXT NOT NULL,
                    file_size INTEGER,
                    file_type TEXT,
                    status TEXT DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create processing_log table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS processing_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_id INTEGER,
                    attempt_number INTEGER DEFAULT 1,
                    status TEXT NOT NULL,
                    processing_time REAL,
                    text_length INTEGER,
                    error_message TEXT,
                    model_used TEXT,
                    device_used TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (file_id) REFERENCES files (id)
                )
            """)
            
            # Create text_output table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS text_output (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_id INTEGER,
                    extracted_text TEXT,
                    text_file_path TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (file_id) REFERENCES files (id)
                )
            """)
            
            # Create indexes for better performance
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_files_status ON files(status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_files_path ON files(file_path)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_log_file_id ON processing_log(file_id)")
            
            conn.commit()
            logger.info("Database initialized successfully")
    
    def add_files(self, file_paths: List[Path]) -> int:
        """
        Add files to tracking database
        
        Args:
            file_paths: List of file paths to track
            
        Returns:
            Number of files added
        """
        added_count = 0
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            for file_path in file_paths:
                try:
                    # Get file info
                    file_stat = file_path.stat()
                    file_name = file_path.name
                    file_size = file_stat.st_size
                    file_type = file_path.suffix.lower()
                    
                    # Insert file record
                    cursor.execute("""
                        INSERT OR IGNORE INTO files 
                        (file_path, file_name, file_size, file_type)
                        VALUES (?, ?, ?, ?)
                    """, (str(file_path), file_name, file_size, file_type))
                    
                    if cursor.rowcount > 0:
                        added_count += 1
                        
                except Exception as e:
                    logger.error(f"Failed to add file {file_path}: {e}")
            
            conn.commit()
        
        logger.info(f"Added {added_count} files to tracking database")
        return added_count
    
    def get_pending_files(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get files that need processing
        
        Args:
            limit: Maximum number of files to return
            
        Returns:
            List of file records
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            query = "SELECT * FROM files WHERE status = 'pending' ORDER BY created_at"
            if limit:
                query += f" LIMIT {limit}"
            
            cursor.execute(query)
            return [dict(row) for row in cursor.fetchall()]
    
    def update_file_status(self, file_path: str, status: str, 
                          processing_time: Optional[float] = None,
                          text_length: Optional[int] = None,
                          error_message: Optional[str] = None,
                          model_used: Optional[str] = None,
                          device_used: Optional[str] = None) -> bool:
        """
        Update file processing status
        
        Args:
            file_path: Path to file
            status: New status ('processing', 'completed', 'failed')
            processing_time: Time taken to process
            text_length: Length of extracted text
            error_message: Error message if failed
            model_used: Model used for processing
            device_used: Device used for processing
            
        Returns:
            True if update successful
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Update file status
                cursor.execute("""
                    UPDATE files 
                    SET status = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE file_path = ?
                """, (status, file_path))
                
                if cursor.rowcount == 0:
                    logger.warning(f"File not found in database: {file_path}")
                    return False
                
                # Get file ID
                cursor.execute("SELECT id FROM files WHERE file_path = ?", (file_path,))
                file_id = cursor.fetchone()[0]
                
                # Log processing attempt
                cursor.execute("""
                    INSERT INTO processing_log 
                    (file_id, status, processing_time, text_length, error_message, model_used, device_used)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (file_id, status, processing_time, text_length, error_message, model_used, device_used))
                
                conn.commit()
                return True
                
        except Exception as e:
            logger.error(f"Failed to update status for {file_path}: {e}")
            return False
    
    def save_extracted_text(self, file_path: str, extracted_text: str, 
                           text_file_path: str) -> bool:
        """
        Save extracted text to database
        
        Args:
            file_path: Original file path
            extracted_text: Extracted text content
            text_file_path: Path to saved text file
            
        Returns:
            True if save successful
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Get file ID
                cursor.execute("SELECT id FROM files WHERE file_path = ?", (file_path,))
                result = cursor.fetchone()
                
                if not result:
                    logger.error(f"File not found in database: {file_path}")
                    return False
                
                file_id = result[0]
                
                # Save text output
                cursor.execute("""
                    INSERT OR REPLACE INTO text_output 
                    (file_id, extracted_text, text_file_path)
                    VALUES (?, ?, ?)
                """, (file_id, extracted_text, text_file_path))
                
                conn.commit()
                return True
                
        except Exception as e:
            logger.error(f"Failed to save text for {file_path}: {e}")
            return False
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get processing statistics
        
        Returns:
            Dictionary with processing statistics
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Get file counts by status
            cursor.execute("""
                SELECT status, COUNT(*) as count 
                FROM files 
                GROUP BY status
            """)
            status_counts = dict(cursor.fetchall())
            
            # Get total files
            cursor.execute("SELECT COUNT(*) FROM files")
            total_files = cursor.fetchone()[0]
            
            # Get processing time statistics
            cursor.execute("""
                SELECT 
                    AVG(processing_time) as avg_time,
                    MIN(processing_time) as min_time,
                    MAX(processing_time) as max_time,
                    COUNT(*) as processed_count
                FROM processing_log 
                WHERE status = 'completed' AND processing_time IS NOT NULL
            """)
            time_stats = cursor.fetchone()
            
            # Get error count
            cursor.execute("SELECT COUNT(*) FROM processing_log WHERE status = 'failed'")
            error_count = cursor.fetchone()[0]
            
            return {
                'total_files': total_files,
                'status_counts': status_counts,
                'avg_processing_time': time_stats[0] if time_stats[0] else 0,
                'min_processing_time': time_stats[1] if time_stats[1] else 0,
                'max_processing_time': time_stats[2] if time_stats[2] else 0,
                'processed_count': time_stats[3] if time_stats[3] else 0,
                'error_count': error_count,
                'completion_percentage': (status_counts.get('completed', 0) / total_files * 100) if total_files > 0 else 0
            }
    
    def get_recent_activity(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get recent processing activity
        
        Args:
            limit: Number of recent activities to return
            
        Returns:
            List of recent activities
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT 
                    f.file_name,
                    pl.status,
                    pl.processing_time,
                    pl.created_at,
                    pl.error_message
                FROM processing_log pl
                JOIN files f ON pl.file_id = f.id
                ORDER BY pl.created_at DESC
                LIMIT ?
            """, (limit,))
            
            return [dict(row) for row in cursor.fetchall()]
    
    def get_all_files(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get all files from the database
        
        Args:
            limit: Maximum number of files to return
            
        Returns:
            List of all file records
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            query = "SELECT * FROM files ORDER BY updated_at DESC"
            if limit:
                query += f" LIMIT {limit}"
            
            cursor.execute(query)
            return [dict(row) for row in cursor.fetchall()]
    
    def get_completed_files(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get completed files from the database
        
        Args:
            limit: Maximum number of files to return
            
        Returns:
            List of completed file records
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            query = "SELECT * FROM files WHERE status = 'completed' ORDER BY updated_at DESC"
            if limit:
                query += f" LIMIT {limit}"
            
            cursor.execute(query)
            return [dict(row) for row in cursor.fetchall()]
    
    def get_failed_files(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get failed files from the database
        
        Args:
            limit: Maximum number of files to return
            
        Returns:
            List of failed file records
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            query = "SELECT * FROM files WHERE status = 'failed' ORDER BY updated_at DESC"
            if limit:
                query += f" LIMIT {limit}"
            
            cursor.execute(query)
            return [dict(row) for row in cursor.fetchall()]
    
    def close(self):
        """Close database connections"""
        # SQLite connections are automatically closed when the context manager exits
        # This method is provided for compatibility and future use
        pass


def test_progress_tracker():
    """Test the progress tracker"""
    try:
        # Initialize tracker
        tracker = ProgressTracker("test_progress.db")
        
        # Test adding files
        test_files = [
            Path("test1.jpg"),
            Path("test2.tif"),
            Path("test3.jpg")
        ]
        
        added = tracker.add_files(test_files)
        print(f"Added {added} files")
        
        # Test getting pending files
        pending = tracker.get_pending_files()
        print(f"Pending files: {len(pending)}")
        
        # Test updating status
        if pending:
            file_path = pending[0]['file_path']
            success = tracker.update_file_status(
                file_path, 'completed', 
                processing_time=1.5, 
                text_length=100,
                model_used='trocr-base',
                device_used='cpu'
            )
            print(f"Status update successful: {success}")
        
        # Test statistics
        stats = tracker.get_statistics()
        print(f"Statistics: {stats}")
        
        # Clean up test database
        Path("test_progress.db").unlink(missing_ok=True)
        print("Test completed successfully")
        
    except Exception as e:
        print(f"Test failed: {e}")


if __name__ == "__main__":
    test_progress_tracker()
