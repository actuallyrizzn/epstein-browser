#!/usr/bin/env python3
"""
Error Detection & Rescan Pass for Epstein Documents

This script identifies poor OCR quality and automatically reprocesses them
with better settings. Implements the simplified approach from the project plan.

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
import argparse
from pathlib import Path
from datetime import datetime
import subprocess
import tempfile
import shutil
from typing import List, Dict, Tuple, Optional

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
DATA_DIR = Path("data")
DB_PATH = "images.db"
OCR_MAX_ATTEMPTS = 3


class ErrorDetectionRescan:
    """Error Detection & Rescan Pass implementation"""
    
    def __init__(self, data_dir: str = "data", db_path: str = "images.db", 
                 max_attempts: int = 3, dry_run: bool = False):
        """
        Initialize the error detection and rescan system
        
        Args:
            data_dir: Path to data directory
            db_path: Path to SQLite database
            max_attempts: Maximum rescan attempts per document
            dry_run: If True, don't make actual changes
        """
        self.data_dir = Path(data_dir)
        self.db_path = Path(db_path)
        self.max_attempts = max_attempts
        self.dry_run = dry_run
        
        # Statistics
        self.stats = {
            'total_checked': 0,
            'bad_ocr_found': 0,
            'rescanned': 0,
            'rescanned_successful': 0,
            'rescanned_failed': 0,
            'already_max_attempts': 0,
            'errors': 0
        }
        
        logger.info(f"Initialized Error Detection & Rescan:")
        logger.info(f"  Data directory: {self.data_dir}")
        logger.info(f"  Database: {self.db_path}")
        logger.info(f"  Max attempts: {self.max_attempts}")
        logger.info(f"  Dry run: {self.dry_run}")
    
    def migrate_database_schema(self):
        """Idempotent database schema migration for new fields"""
        with sqlite3.connect(self.db_path) as conn:
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
    
    def check_ocr_quality(self, ocr_text: str) -> Tuple[int, str]:
        """
        Check OCR quality using simple heuristics
        
        Args:
            ocr_text: The OCR text to check
            
        Returns:
            Tuple of (quality_score, reason)
            - quality_score: 0-100 (0 = bad, 100 = good)
            - reason: Human-readable reason for the score
        """
        if not ocr_text or not ocr_text.strip():
            return 0, "Empty or whitespace-only text"
        
        text = ocr_text.strip()
        
        # Check 1: Content that's just repeated zeros with spaces
        if text.replace(' ', '').replace('0', '') == '':
            return 0, "Only zeros and spaces"
        
        # Check 2: Content that's all zeros when stripped of whitespace
        if text.replace(' ', '') == '0' * len(text.replace(' ', '')):
            return 0, "All zeros when stripped of spaces"
        
        # Check 3: Very short content that's mostly zeros (like "0 0")
        if len(text) < 20 and text.count('0') > len(text) * 0.5:
            return 0, f"Too many zeros in short text ({text.count('0')}/{len(text)} chars)"
        
        # Check 4: Very short content (< 10 characters) - but only if not caught by above
        if len(text) < 10:
            return 0, f"Too short ({len(text)} characters)"
        
        # Check 5: Very repetitive patterns (like "0 0 00 0")
        words = text.split()
        if len(words) > 3:
            # Check if most words are just zeros or very short
            zero_words = sum(1 for word in words if word.replace('0', '') == '')
            if zero_words / len(words) > 0.7:  # More than 70% are just zeros
                return 0, f"Too many zero patterns ({zero_words}/{len(words)} words)"
        
        # Check 6: Corrupted OCR with binary/metadata content
        # Look for patterns that indicate corrupted OCR
        binary_indicators = ['JFIF', '␦', '\\', '{', '}', '|', '~', '`', '^', '[', ']']
        binary_count = sum(1 for char in text if ord(char) < 32 or char in binary_indicators)
        if binary_count > len(text) * 0.1:  # More than 10% binary/corrupted characters
            return 0, f"Too many binary/corrupted characters ({binary_count}/{len(text)} chars)"
        
        # Check 7: Very short meaningful content (after removing binary chars)
        meaningful_chars = sum(1 for char in text if char.isalnum() or char in ' .,;:!?()[]{}"\'`~@#$%^&*+-=<>/\\|_')
        if meaningful_chars < 10:
            return 0, f"Too few meaningful characters ({meaningful_chars} chars)"
        
        # If we get here, the OCR looks acceptable
        return 100, "Passed all quality checks"
    
    def get_ocr_text(self, file_path: str) -> Optional[str]:
        """
        Get OCR text from file
        
        Args:
            file_path: Path to OCR text file
            
        Returns:
            OCR text content or None if file doesn't exist/readable
        """
        try:
            ocr_file = self.data_dir / file_path
            if not ocr_file.exists():
                return None
            
            content = ocr_file.read_text(encoding='utf-8', errors='ignore')
            return content.strip() if content else None
            
        except Exception as e:
            logger.warning(f"Error reading OCR file {file_path}: {e}")
            return None
    
    def nuke_bad_ocr(self, file_path: str) -> bool:
        """
        Delete bad OCR file and update database to mark as needing reprocessing
        
        Args:
            file_path: Path to image file (will be converted to OCR .txt path)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Convert image path to OCR text path
            ocr_path = file_path.rsplit('.', 1)[0] + '.txt'
            ocr_file = self.data_dir / ocr_path
            
            if self.dry_run:
                logger.info(f"[DRY RUN] Would delete OCR file: {ocr_file}")
                return True
            
            # Delete the OCR file
            if ocr_file.exists():
                ocr_file.unlink()
                logger.info(f"Deleted bad OCR file: {ocr_file}")
            else:
                logger.warning(f"OCR file not found: {ocr_file}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error deleting OCR file {file_path}: {e}")
            return False
    
    def find_image_file(self, file_path: str) -> Optional[Path]:
        """
        Find the corresponding image file for an OCR text file
        
        Args:
            file_path: Path to OCR text file (e.g., "path/to/file.txt")
            
        Returns:
            Path to corresponding image file or None if not found
        """
        # Remove .txt extension and try common image extensions
        base_path = file_path.rsplit('.', 1)[0]
        image_extensions = ['.tif', '.tiff', '.jpg', '.jpeg', '.png', '.bmp']
        
        for ext in image_extensions:
            image_path = self.data_dir / f"{base_path}{ext}"
            if image_path.exists():
                return image_path
        
        return None
    
    def update_database(self, doc_id: int, quality_score: int, rescan_attempts: int, 
                       ocr_text_path: str = None, nuke_ocr: bool = False) -> bool:
        """
        Update database with quality score and rescan attempts
        
        Args:
            doc_id: Document ID
            quality_score: OCR quality score (0-100)
            rescan_attempts: Number of rescan attempts
            ocr_text_path: Path to OCR text file (if updated)
            nuke_ocr: If True, mark as needing reprocessing (has_ocr_text = FALSE)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if self.dry_run:
                logger.info(f"[DRY RUN] Would update database: doc_id={doc_id}, "
                           f"quality_score={quality_score}, rescan_attempts={rescan_attempts}, "
                           f"nuke_ocr={nuke_ocr}")
                return True
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                if nuke_ocr:
                    # Mark as needing reprocessing - reset OCR flags
                    cursor.execute("""
                        UPDATE images 
                        SET has_ocr_text = FALSE, ocr_text_path = NULL,
                            ocr_quality_score = NULL, ocr_rescan_attempts = 0,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                    """, (doc_id,))
                elif ocr_text_path:
                    # Update with new OCR text path
                    cursor.execute("""
                        UPDATE images 
                        SET ocr_quality_score = ?, ocr_rescan_attempts = ?, 
                            ocr_text_path = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                    """, (quality_score, rescan_attempts, ocr_text_path, doc_id))
                else:
                    # Update quality score and attempts only
                    cursor.execute("""
                        UPDATE images 
                        SET ocr_quality_score = ?, ocr_rescan_attempts = ?, 
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                    """, (quality_score, rescan_attempts, doc_id))
                
                conn.commit()
                return True
                
        except Exception as e:
            logger.error(f"Error updating database for doc_id {doc_id}: {e}")
            return False
    
    def process_document(self, doc: Dict) -> bool:
        """
        Process a single document for error detection and rescan
        
        Args:
            doc: Document dictionary with id, file_path, has_ocr_text, ocr_rescan_attempts
            
        Returns:
            True if processed successfully, False otherwise
        """
        doc_id = doc['id']
        file_path = doc['file_path']
        has_ocr = doc['has_ocr_text']
        rescan_attempts = doc.get('ocr_rescan_attempts', 0)
        
        self.stats['total_checked'] += 1
        
        # Skip if no OCR text
        if not has_ocr:
            logger.debug(f"Document {doc_id} has no OCR text, skipping")
            return True
        
        # Skip if already at max attempts
        if rescan_attempts >= self.max_attempts:
            self.stats['already_max_attempts'] += 1
            logger.debug(f"Document {doc_id} already at max attempts ({rescan_attempts})")
            return True
        
        # Get OCR text
        ocr_text = self.get_ocr_text(file_path)
        if not ocr_text:
            logger.warning(f"Could not read OCR text for document {doc_id}")
            self.stats['errors'] += 1
            return False
        
        # Check quality
        logger.debug(f"OCR text for document {doc_id}: '{ocr_text[:100]}{'...' if len(ocr_text) > 100 else ''}'")
        quality_score, reason = self.check_ocr_quality(ocr_text)
        
        # Update database with quality score
        if not self.update_database(doc_id, quality_score, rescan_attempts):
            self.stats['errors'] += 1
            return False
        
        # If quality is good, we're done
        if quality_score == 100:
            logger.debug(f"Document {doc_id} has good OCR quality: {reason}")
            return True
        
        # Quality is bad, nuke it and let cron job reprocess
        self.stats['bad_ocr_found'] += 1
        logger.info(f"Document {doc_id} has bad OCR quality: {reason}")
        
        # Nuke the bad OCR file
        if self.nuke_bad_ocr(file_path):
            # Update database to mark as needing reprocessing
            self.update_database(doc_id, quality_score, rescan_attempts + 1, nuke_ocr=True)
            logger.info(f"Nuked bad OCR for document {doc_id}, cron job will reprocess it")
            self.stats['rescanned'] += 1
            self.stats['rescanned_successful'] += 1
        else:
            logger.warning(f"Failed to nuke OCR for document {doc_id}")
            self.stats['rescanned_failed'] += 1
            self.stats['errors'] += 1
        
        return True
    
    def run_error_detection(self, limit: int = None) -> None:
        """
        Run the error detection and rescan process
        
        Args:
            limit: Maximum number of documents to process (for testing)
        """
        logger.info("Starting Error Detection & Rescan Pass")
        start_time = datetime.now()
        
        # Ensure database schema is up to date
        self.migrate_database_schema()
        
        # Get documents with OCR text that haven't reached max attempts
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            query = """
                SELECT id, file_path, has_ocr_text, 
                       COALESCE(ocr_rescan_attempts, 0) as ocr_rescan_attempts
                FROM images 
                WHERE has_ocr_text = TRUE 
                  AND COALESCE(ocr_rescan_attempts, 0) < ?
                ORDER BY id
            """
            
            if limit:
                query += f" LIMIT {limit}"
            
            cursor.execute(query, (self.max_attempts,))
            documents = [dict(row) for row in cursor.fetchall()]
        
        logger.info(f"Found {len(documents)} documents to process")
        
        # Process each document
        for i, doc in enumerate(documents, 1):
            logger.info(f"Processing document {i}/{len(documents)}: ID {doc['id']}")
            
            try:
                self.process_document(doc)
            except Exception as e:
                logger.error(f"Error processing document {doc['id']}: {e}")
                self.stats['errors'] += 1
        
        # Print final statistics
        elapsed = datetime.now() - start_time
        logger.info("Error Detection & Rescan Pass completed")
        logger.info(f"Time elapsed: {elapsed.total_seconds():.2f} seconds")
        logger.info("Statistics:")
        for key, value in self.stats.items():
            logger.info(f"  {key.replace('_', ' ').title()}: {value}")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Error Detection & Rescan Pass for Epstein Documents")
    parser.add_argument("--data-dir", default="data", help="Path to data directory")
    parser.add_argument("--db-path", default="images.db", help="Path to SQLite database")
    parser.add_argument("--max-attempts", type=int, default=3, help="Maximum rescan attempts per document")
    parser.add_argument("--limit", type=int, help="Limit number of documents to process (for testing)")
    parser.add_argument("--dry-run", action="store_true", help="Don't make actual changes")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Initialize and run error detection
    detector = ErrorDetectionRescan(
        data_dir=args.data_dir,
        db_path=args.db_path,
        max_attempts=args.max_attempts,
        dry_run=args.dry_run
    )
    
    detector.run_error_detection(limit=args.limit)


if __name__ == "__main__":
    main()
