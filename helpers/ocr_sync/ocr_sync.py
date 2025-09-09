#!/usr/bin/env python3
"""
OCR Text Sync Script

Polls the production site and pulls down OCR texts, placing them in the identical
spot they need to be in the local data folder. Includes dry run and limited run modes
for safe testing.

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

import os
import sys
import json
import time
import sqlite3
import argparse
import requests
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from urllib.parse import urljoin, urlparse
import logging
from datetime import datetime, timedelta

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('ocr_sync.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class OCRSync:
    """OCR text synchronization from production site to local data folder"""
    
    def __init__(self, prod_url: str, local_data_dir: str, dry_run: bool = False, 
                 limited_run: Optional[int] = None, batch_size: int = 50):
        """
        Initialize OCR sync
        
        Args:
            prod_url: Production site base URL (e.g., 'https://epstein-docs.example.com')
            local_data_dir: Local data directory path
            dry_run: If True, only show what would be downloaded without making changes
            limited_run: If set, only process this many documents (for testing)
            batch_size: Number of documents to process in each batch
        """
        self.prod_url = prod_url.rstrip('/')
        
        # Handle relative paths - if data_dir is relative, make it relative to project root
        if not Path(local_data_dir).is_absolute():
            # Get the project root (two levels up from this script)
            script_dir = Path(__file__).parent
            project_root = script_dir.parent.parent
            self.local_data_dir = project_root / local_data_dir
        else:
            self.local_data_dir = Path(local_data_dir)
            
        self.dry_run = dry_run
        self.limited_run = limited_run
        self.batch_size = batch_size
        
        # Ensure local data directory exists
        if not self.local_data_dir.exists():
            raise FileNotFoundError(f"Local data directory not found: {self.local_data_dir}")
        
        # Initialize counters
        self.stats = {
            'total_documents': 0,
            'documents_with_ocr': 0,
            'already_downloaded': 0,
            'downloaded': 0,
            'failed': 0,
            'skipped': 0
        }
        
        # Setup session with timeout and redirect handling
        self.session = requests.Session()
        self.session.timeout = 30
        # Allow redirects and handle HTTPS
        self.session.allow_redirects = True
        
        # Rate limiting - be respectful to the server
        # /api/document/{id} uses 'stats' rate limit: 300 requests per 60 seconds = 5 requests per second
        # We'll be conservative and use 200ms between requests (5 requests per second)
        self.request_delay = 0.2  # 200ms between requests (5 per second)
        self.batch_delay = 1.0    # 1 second between batches
        
        # Progress tracking and cache files (in .cache subdirectory)
        cache_dir = Path(__file__).parent / '.cache'
        cache_dir.mkdir(exist_ok=True)
        self.progress_file = cache_dir / '.ocr_sync_progress.json'
        self.cache_file = cache_dir / '.ocr_sync_cache.json'
        
        logger.info(f"Initialized OCR sync:")
        logger.info(f"  Production URL: {self.prod_url}")
        logger.info(f"  Local data dir: {self.local_data_dir}")
        logger.info(f"  Dry run: {self.dry_run}")
        logger.info(f"  Limited run: {self.limited_run}")
        logger.info(f"  Batch size: {self.batch_size}")
    
    def load_progress(self) -> Dict:
        """Load progress from file"""
        if self.progress_file.exists():
            try:
                with open(self.progress_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load progress file: {e}")
        return {'last_processed_id': 0, 'processed_documents': set()}
    
    def save_progress(self, last_id: int, processed_docs: set) -> None:
        """Save progress to file"""
        if not self.dry_run:
            try:
                progress_data = {
                    'last_processed_id': last_id,
                    'processed_documents': list(processed_docs),
                    'timestamp': datetime.now().isoformat()
                }
                with open(self.progress_file, 'w') as f:
                    json.dump(progress_data, f, indent=2)
            except Exception as e:
                logger.warning(f"Failed to save progress file: {e}")
    
    def load_cache(self) -> Optional[Dict]:
        """Load cache from disk"""
        if not self.cache_file.exists():
            return None
        
        try:
            with open(self.cache_file, 'r') as f:
                cache_data = json.load(f)
            
            # Validate cache structure
            required_keys = ['local_ocr_files', 'metadata']
            if not all(key in cache_data for key in required_keys):
                logger.warning("Cache file is corrupted, ignoring")
                return None
            
            return cache_data
        except Exception as e:
            logger.warning(f"Failed to load cache: {e}")
            return None
    
    def save_cache(self, local_ocr_files: Dict) -> bool:
        """Save cache to disk"""
        if self.dry_run:
            return True
            
        try:
            cache_data = {
                'metadata': {
                    'created_at': datetime.now().isoformat(),
                    'local_data_dir': str(self.local_data_dir),
                    'prod_url': self.prod_url
                },
                'local_ocr_files': local_ocr_files
            }
            
            with open(self.cache_file, 'w') as f:
                json.dump(cache_data, f, indent=2)
            
            logger.debug(f"Cache saved to {self.cache_file}")
            return True
        except Exception as e:
            logger.warning(f"Failed to save cache: {e}")
            return False
    
    def is_cache_valid(self, cache_data: Dict, max_age_hours: int = 24) -> bool:
        """Check if cache is still valid"""
        try:
            created_at = datetime.fromisoformat(cache_data['metadata']['created_at'])
            age = datetime.now() - created_at
            
            if age > timedelta(hours=max_age_hours):
                logger.info(f"Cache is {age} old, considered stale")
                return False
            
            # Check if paths match
            if (cache_data['metadata']['local_data_dir'] != str(self.local_data_dir) or
                cache_data['metadata']['prod_url'] != self.prod_url):
                logger.info("Cache paths don't match current configuration")
                return False
            
            return True
        except Exception as e:
            logger.warning(f"Failed to validate cache: {e}")
            return False
    
    def scan_local_ocr_files(self) -> Dict[str, Dict]:
        """Scan local OCR files and build manifest"""
        logger.info(f"Scanning local OCR files in {self.local_data_dir}")
        manifest = {}
        
        for ocr_file in self.local_data_dir.rglob('*.txt'):
            if ocr_file.is_file():
                try:
                    # Get relative path from data directory
                    rel_path = str(ocr_file.relative_to(self.local_data_dir)).replace('\\', '/')
                    
                    # Convert back to original file path (remove .txt extension)
                    original_path = rel_path.rsplit('.', 1)[0]
                    
                    manifest[original_path] = {
                        'path': original_path,
                        'ocr_path': rel_path,
                        'size': ocr_file.stat().st_size,
                        'mtime': ocr_file.stat().st_mtime,
                        'local_path': str(ocr_file)
                    }
                except Exception as e:
                    logger.debug(f"Error processing {ocr_file}: {e}")
        
        logger.info(f"Found {len(manifest)} local OCR files")
        return manifest
    
    def has_local_ocr_text(self, file_path: str) -> bool:
        """
        Check if OCR text already exists locally for a file
        
        Args:
            file_path: Original file path from production
            
        Returns:
            True if OCR text exists locally, False otherwise
        """
        ocr_file = self.get_local_ocr_path(file_path)
        return ocr_file.exists() and ocr_file.stat().st_size > 0
    
    def get_production_stats(self) -> Dict:
        """Get statistics from production site"""
        try:
            url = f"{self.prod_url}/api/stats"
            logger.info(f"Fetching production stats from {url}")
            
            response = self.session.get(url)
            response.raise_for_status()
            
            stats = response.json()
            logger.info(f"Production stats: {stats}")
            return stats
            
        except requests.RequestException as e:
            logger.error(f"Failed to fetch production stats: {e}")
            raise
    
    def get_document_by_id(self, doc_id: int) -> Optional[Dict]:
        """
        Get a single document by ID from production site
        
        Args:
            doc_id: Document ID
            
        Returns:
            Document dictionary or None if not found
        """
        max_retries = 3
        base_delay = 1.0
        
        for attempt in range(max_retries):
            try:
                url = f"{self.prod_url}/api/document/{doc_id}"
                response = self.session.get(url)
                
                # Check for rate limiting
                if response.status_code == 429:
                    retry_after = int(response.headers.get('Retry-After', 60))
                    logger.warning(f"Rate limited for document {doc_id}. Waiting {retry_after} seconds...")
                    time.sleep(retry_after)
                    continue
                
                if response.status_code == 200:
                    # Check rate limit headers and adjust delay if needed
                    remaining = response.headers.get('X-RateLimit-Remaining')
                    if remaining and int(remaining) < 10:  # If less than 10 requests remaining
                        logger.debug(f"Rate limit remaining: {remaining}. Adding extra delay...")
                        time.sleep(1.0)  # Extra 1 second delay
                    
                    return response.json()
                elif response.status_code == 404:
                    return None
                else:
                    logger.warning(f"Unexpected status code {response.status_code} for document {doc_id}")
                    return None
                    
            except requests.RequestException as e:
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)  # Exponential backoff
                    logger.warning(f"Failed to fetch document {doc_id} (attempt {attempt + 1}): {e}. Retrying in {delay}s...")
                    time.sleep(delay)
                else:
                    logger.warning(f"Failed to fetch document {doc_id} after {max_retries} attempts: {e}")
                    return None
    
    def get_document_range(self, start_id: int, end_id: int) -> List[Dict]:
        """
        Get a range of documents by iterating through IDs
        
        Args:
            start_id: Starting document ID
            end_id: Ending document ID (inclusive)
            
        Returns:
            List of document dictionaries with OCR text
        """
        documents = []
        
        for doc_id in range(start_id, end_id + 1):
            document = self.get_document_by_id(doc_id)
            if document and document.get('has_ocr_text', False):
                documents.append(document)
                logger.debug(f"Found document {doc_id} with OCR text")
                
                # Check if this document exists in local database and update if needed
                self.check_and_update_database_entry(doc_id, document)
            
            # Rate limiting - be respectful to the server
            time.sleep(self.request_delay)
            
            # Progress update every 100 documents
            if doc_id % 100 == 0:
                logger.info(f"Checked {doc_id - start_id + 1} documents, found {len(documents)} with OCR")
        
        logger.info(f"Found {len(documents)} documents with OCR in range {start_id}-{end_id}")
        return documents
    
    def get_ocr_text_from_production(self, document: Dict) -> Optional[str]:
        """
        Get OCR text for a specific document from production site
        
        Args:
            document: Document dictionary with id, file_path, etc.
            
        Returns:
            OCR text content or None if not available
        """
        try:
            # Try to get OCR text via the document API
            doc_id = document.get('id')
            if not doc_id:
                logger.warning(f"No document ID found for document: {document}")
                return None
            
            # First try the document API endpoint
            url = f"{self.prod_url}/api/document/{doc_id}"
            response = self.session.get(url)
            
            if response.status_code == 200:
                doc_data = response.json()
                ocr_text = doc_data.get('ocr_text')
                if ocr_text:
                    logger.debug(f"Retrieved OCR text for document {doc_id} via API")
                    return ocr_text
            
            # If API doesn't have OCR text, try to construct the OCR file URL
            file_path = document.get('file_path', '')
            if not file_path:
                logger.warning(f"No file path found for document: {document}")
                return None
            
            # Construct OCR text file URL (replace extension with .txt)
            ocr_file_path = file_path.rsplit('.', 1)[0] + '.txt'
            ocr_url = f"{self.prod_url}/api/ocr-text/{ocr_file_path}"
            
            logger.debug(f"Trying to fetch OCR text from: {ocr_url}")
            response = self.session.get(ocr_url)
            
            if response.status_code == 200:
                logger.debug(f"Retrieved OCR text for {file_path} via file URL")
                return response.text
            else:
                logger.warning(f"OCR text not available for {file_path} (status: {response.status_code})")
                return None
                
        except requests.RequestException as e:
            logger.error(f"Failed to get OCR text for document {document.get('id', 'unknown')}: {e}")
            return None
    
    def get_local_ocr_path(self, file_path: str) -> Path:
        """
        Get the local path where OCR text should be stored
        
        Args:
            file_path: Original file path from production
            
        Returns:
            Path object for local OCR text file
        """
        # Convert backslashes to forward slashes for cross-platform compatibility
        file_path = file_path.replace('\\', '/')
        
        # Create the OCR text file path by replacing the extension with .txt
        ocr_file = self.local_data_dir / file_path
        ocr_file = ocr_file.with_suffix('.txt')
        
        return ocr_file
    
    def save_ocr_text(self, file_path: str, ocr_text: str) -> bool:
        """
        Save OCR text to local file
        
        Args:
            file_path: Original file path from production
            ocr_text: OCR text content
            
        Returns:
            True if successful, False otherwise
        """
        try:
            ocr_file = self.get_local_ocr_path(file_path)
            
            if self.dry_run:
                logger.info(f"[DRY RUN] Would save OCR text to: {ocr_file}")
                logger.info(f"[DRY RUN] Content length: {len(ocr_text)} characters")
                return True
            
            # Ensure parent directory exists
            ocr_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Write OCR text to file
            ocr_file.write_text(ocr_text, encoding='utf-8')
            
            logger.info(f"Saved OCR text to: {ocr_file}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save OCR text for {file_path}: {e}")
            return False
    
    def check_and_update_database_entry(self, doc_id: int, document: Dict) -> bool:
        """
        Check if document exists in database and update OCR status if needed
        
        Args:
            doc_id: Document ID
            document: Document dictionary from production API
            
        Returns:
            True if document exists and was updated, False if document doesn't exist
        """
        try:
            if self.dry_run:
                logger.debug(f"[DRY RUN] Would check database for document {doc_id}")
                return True
            
            # Connect to local database
            db_path = self.local_data_dir.parent / 'images.db'
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            
            # Check if document exists in database
            cursor.execute("SELECT id, has_ocr_text, file_path FROM images WHERE id = ?", (doc_id,))
            result = cursor.fetchone()
            
            if result:
                db_id, has_ocr_text, file_path = result
                
                # Check if OCR text exists locally
                if file_path and self.has_local_ocr_text(file_path):
                    # Update database to mark as having OCR text
                    ocr_text_path = str(self.get_local_ocr_path(file_path).relative_to(self.local_data_dir))
                    cursor.execute("""
                        UPDATE images 
                        SET has_ocr_text = ?, ocr_text_path = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                    """, (True, ocr_text_path, doc_id))
                    
                    conn.commit()
                    logger.debug(f"Updated database for document {doc_id}: marked as having OCR text")
                else:
                    logger.debug(f"Document {doc_id} exists in database but no local OCR file found")
            else:
                logger.debug(f"Document {doc_id} not found in local database")
            
            conn.close()
            return result is not None
            
        except Exception as e:
            logger.error(f"Failed to check database for document {doc_id}: {e}")
            return False

    def update_database(self, doc_id: int, has_ocr: bool, ocr_text_path: str = None) -> bool:
        """
        Update database to mark document as having OCR text
        
        Args:
            doc_id: Document ID
            has_ocr: Whether the document has OCR text
            ocr_text_path: Path to OCR text file (relative to data directory)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if self.dry_run:
                logger.info(f"[DRY RUN] Would update database: doc_id={doc_id}, has_ocr={has_ocr}, ocr_path={ocr_text_path}")
                return True
            
            # Connect to local database
            db_path = self.local_data_dir.parent / 'images.db'
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            
            # Update the images table
            cursor.execute("""
                UPDATE images 
                SET has_ocr_text = ?, ocr_text_path = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (has_ocr, ocr_text_path, doc_id))
            
            conn.commit()
            conn.close()
            
            logger.debug(f"Updated database for document {doc_id}: has_ocr={has_ocr}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update database for document {doc_id}: {e}")
            return False
    
    def process_document(self, document: Dict) -> bool:
        """
        Process a single document (download and save OCR text)
        
        Args:
            document: Document dictionary
            
        Returns:
            True if successful, False otherwise
        """
        file_path = document.get('file_path', '')
        doc_id = document.get('id', 'unknown')
        
        if not file_path:
            logger.warning(f"No file path for document {doc_id}")
            self.stats['failed'] += 1
            return False
        
        # Check if OCR text already exists locally (idempotent check)
        if self.has_local_ocr_text(file_path):
            logger.debug(f"OCR text already exists locally: {file_path}")
            self.stats['already_downloaded'] += 1
            return True
        
        # Get OCR text from production
        logger.info(f"Processing document {doc_id}: {file_path}")
        ocr_text = self.get_ocr_text_from_production(document)
        
        if not ocr_text:
            logger.warning(f"No OCR text available for document {doc_id}")
            self.stats['skipped'] += 1
            return False
        
        # Save OCR text locally
        if self.save_ocr_text(file_path, ocr_text):
            # Update database to mark document as having OCR text
            ocr_text_path = str(self.get_local_ocr_path(file_path).relative_to(self.local_data_dir))
            if self.update_database(doc_id, True, ocr_text_path):
                self.stats['downloaded'] += 1
                return True
            else:
                logger.warning(f"Failed to update database for document {doc_id}")
                self.stats['failed'] += 1
                return False
        else:
            self.stats['failed'] += 1
            return False
    
    def process_batch(self, documents: List[Dict]) -> None:
        """Process a batch of documents"""
        logger.info(f"Processing batch of {len(documents)} documents")
        
        for i, document in enumerate(documents, 1):
            try:
                self.process_document(document)
                
                # Progress update
                if i % 10 == 0:
                    logger.info(f"Processed {i}/{len(documents)} documents in current batch")
                
                # Rate limiting - be respectful to the server
                time.sleep(self.request_delay)
                
            except Exception as e:
                logger.error(f"Error processing document {document.get('id', 'unknown')}: {e}")
                self.stats['failed'] += 1
    
    def sync_existing_ocr_files(self) -> None:
        """
        Scan existing OCR files and update database to match
        This ensures database is in sync with what's actually on disk
        """
        logger.info("Syncing existing OCR files with database...")
        
        # Connect to local database
        db_path = self.local_data_dir.parent / 'images.db'
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        # Get all images from database
        cursor.execute("SELECT id, file_path FROM images")
        # Normalize paths to use forward slashes for consistent matching
        db_images = {row[1].replace('\\', '/'): row[0] for row in cursor.fetchall()}
        
        # Debug: show some sample database paths
        sample_paths = list(db_images.keys())[:5]
        logger.debug(f"Sample database paths: {sample_paths}")
        
        # Scan all OCR files
        ocr_files = list(self.local_data_dir.rglob('*.txt'))
        updated_count = 0
        missing_count = 0
        
        for ocr_file in ocr_files:
            if not ocr_file.is_file():
                continue
                
            try:
                # Get relative path from data directory
                rel_path = str(ocr_file.relative_to(self.local_data_dir)).replace('\\', '/')
                
                # Convert back to original file path (remove .txt extension and add .jpg)
                original_path = rel_path.rsplit('.', 1)[0] + '.jpg'
                
                # Debug: show some sample OCR file paths
                if missing_count < 5:
                    logger.debug(f"Sample OCR file path: {original_path}")
                    # Check if this specific path exists in database
                    if original_path in db_images:
                        logger.debug(f"  -> Found in database as ID {db_images[original_path]}")
                    else:
                        logger.debug(f"  -> NOT found in database")
                        # Show a few similar database paths for comparison
                        similar_paths = [p for p in db_images.keys() if 'DOJ-OGR-00000699' in p]
                        logger.debug(f"  -> Similar database paths: {similar_paths}")
                
                # Check if this file exists in database
                if original_path in db_images:
                    doc_id = db_images[original_path]
                    
                    # Check if database already has this marked as having OCR
                    cursor.execute("SELECT has_ocr_text FROM images WHERE id = ?", (doc_id,))
                    result = cursor.fetchone()
                    
                    if result and not result[0]:  # Not marked as having OCR
                        # Update database
                        ocr_text_path = rel_path
                        cursor.execute("""
                            UPDATE images 
                            SET has_ocr_text = ?, ocr_text_path = ?, updated_at = CURRENT_TIMESTAMP
                            WHERE id = ?
                        """, (True, ocr_text_path, doc_id))
                        conn.commit()
                        updated_count += 1
                        logger.info(f"Updated database for existing OCR file: {original_path}")
                else:
                    missing_count += 1
                    logger.debug(f"OCR file exists but no database entry: {original_path}")
                    
            except Exception as e:
                logger.warning(f"Error processing OCR file {ocr_file}: {e}")
        
        conn.commit()
        conn.close()
        
        logger.info(f"Database sync complete: {updated_count} files updated, {missing_count} files not in database")

    def sync_ocr_texts(self) -> None:
        """Main sync process"""
        logger.info("Starting OCR text synchronization")
        start_time = time.time()
        
        # First, sync existing OCR files with database
        self.sync_existing_ocr_files()
        
        try:
            # Load local OCR file manifest (for idempotency)
            local_ocr_files = None
            cache_used = False
            
            # Try to load from cache first
            cache_data = self.load_cache()
            if cache_data and self.is_cache_valid(cache_data):
                logger.info("Using cached local OCR file manifest (much faster!)")
                local_ocr_files = cache_data['local_ocr_files']
                cache_used = True
            else:
                logger.info("Cache not available or invalid, scanning local OCR files...")
                local_ocr_files = self.scan_local_ocr_files()
                self.save_cache(local_ocr_files)
            
            # Get production stats
            prod_stats = self.get_production_stats()
            self.stats['total_documents'] = prod_stats.get('total_images', 0)
            self.stats['documents_with_ocr'] = prod_stats.get('images_with_ocr', 0)
            
            logger.info(f"Production has {self.stats['total_documents']} total documents")
            logger.info(f"Production has {self.stats['documents_with_ocr']} documents with OCR")
            logger.info(f"Local has {len(local_ocr_files)} OCR files")
            
            # Load progress to resume from where we left off
            progress = self.load_progress()
            last_processed_id = progress.get('last_processed_id', 0)
            processed_docs = set(progress.get('processed_documents', []))
            
            if last_processed_id > 0:
                logger.info(f"Resuming from document ID {last_processed_id + 1}")
            
            # Get first and last document IDs
            first_id = max(1, last_processed_id + 1)
            last_id = self.stats['total_documents']
            
            logger.info(f"Scanning document IDs {first_id} to {last_id} for OCR text")
            
            # Process documents in batches by ID range
            batch_size = self.batch_size
            total_processed = 0
            
            for start_id in range(first_id, last_id + 1, batch_size):
                end_id = min(start_id + batch_size - 1, last_id)
                
                logger.info(f"Processing document range {start_id}-{end_id}")
                
                # Get documents with OCR in this range
                documents = self.get_document_range(start_id, end_id)
                
                if documents:
                    # Filter out documents we already have locally (idempotent)
                    documents_to_process = []
                    for doc in documents:
                        file_path = doc.get('file_path', '')
                        if file_path:
                            # Check if we already have this OCR file locally
                            if self.has_local_ocr_text(file_path):
                                self.stats['already_downloaded'] += 1
                                processed_docs.add(str(doc.get('id', '')))
                                logger.debug(f"OCR text already exists locally: {file_path}")
                            else:
                                documents_to_process.append(doc)
                        else:
                            self.stats['skipped'] += 1
                    
                    if documents_to_process:
                        logger.info(f"Processing {len(documents_to_process)} new documents (skipped {len(documents) - len(documents_to_process)} already downloaded)")
                        
                        # Process documents one by one to respect limited run
                        for doc in documents_to_process:
                            # Check limit BEFORE processing
                            if self.limited_run and total_processed >= self.limited_run:
                                logger.info(f"Reached limited run limit of {self.limited_run} documents")
                                break
                                
                            self.process_document(doc)
                            total_processed += 1
                            processed_docs.add(str(doc.get('id', '')))
                            
                            # Check limit AFTER processing to break immediately
                            if self.limited_run and total_processed >= self.limited_run:
                                logger.info(f"Reached limited run limit of {self.limited_run} documents")
                                break
                    else:
                        logger.info(f"All {len(documents)} documents in this batch already downloaded")
                
                # Save progress after each batch
                self.save_progress(end_id, processed_docs)
                
                # Check if we've hit the limited run limit (total processed, not per batch)
                if self.limited_run and total_processed >= self.limited_run:
                    logger.info(f"Reached limited run limit of {self.limited_run} documents")
                    break
                
                # Rate limiting between batches
                time.sleep(self.batch_delay)
            
            # Final statistics
            elapsed_time = time.time() - start_time
            logger.info("OCR text synchronization completed")
            logger.info(f"Time elapsed: {elapsed_time:.2f} seconds")
            logger.info(f"Statistics:")
            logger.info(f"  Total documents: {self.stats['total_documents']}")
            logger.info(f"  Documents with OCR: {self.stats['documents_with_ocr']}")
            logger.info(f"  Already downloaded: {self.stats['already_downloaded']}")
            logger.info(f"  Downloaded: {self.stats['downloaded']}")
            logger.info(f"  Failed: {self.stats['failed']}")
            logger.info(f"  Skipped: {self.stats['skipped']}")
            
        except Exception as e:
            logger.error(f"OCR synchronization failed: {e}")
            raise


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Sync OCR texts from production site to local data folder')
    parser.add_argument('prod_url', help='Production site base URL (e.g., https://epstein-docs.example.com)')
    parser.add_argument('--data-dir', default='data', help='Local data directory (default: data)')
    parser.add_argument('--dry-run', action='store_true', help='Dry run mode - show what would be downloaded without making changes')
    parser.add_argument('--limited-run', type=int, help='Limited run mode - only process this many documents (for testing)')
    parser.add_argument('--batch-size', type=int, default=50, help='Batch size for processing (default: 50)')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose logging')
    
    args = parser.parse_args()
    
    # Set logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Validate arguments
    if not args.prod_url.startswith(('http://', 'https://')):
        logger.error("Production URL must start with http:// or https://")
        sys.exit(1)
    
    # Resolve data directory path (same logic as in OCRSync.__init__)
    if not Path(args.data_dir).is_absolute():
        script_dir = Path(__file__).parent
        project_root = script_dir.parent.parent
        resolved_data_dir = project_root / args.data_dir
    else:
        resolved_data_dir = Path(args.data_dir)
    
    if not resolved_data_dir.exists():
        logger.error(f"Data directory does not exist: {resolved_data_dir}")
        logger.error(f"Resolved from: {args.data_dir}")
        sys.exit(1)
    
    try:
        # Create OCR sync instance
        sync = OCRSync(
            prod_url=args.prod_url,
            local_data_dir=args.data_dir,
            dry_run=args.dry_run,
            limited_run=args.limited_run,
            batch_size=args.batch_size
        )
        
        # Run synchronization
        sync.sync_ocr_texts()
        
    except KeyboardInterrupt:
        logger.info("Synchronization interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Synchronization failed: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
