#!/usr/bin/env python3
"""
EasyOCR Processor for Epstein Documents

High-quality OCR processing using EasyOCR for the full dataset.

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
from PIL import Image
import easyocr
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import signal
import sys

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
DATA_DIR = Path("data")
DB_PATH = "images.db"
MAX_WORKERS = 2  # Conservative for CPU usage
BATCH_SIZE = 100  # Process in batches
MIN_CONFIDENCE = 0.3  # Lower threshold for legal documents

class EasyOCRProcessor:
    """EasyOCR processor for document OCR"""
    
    def __init__(self):
        self.reader = None
        self.processed_count = 0
        self.total_count = 0
        self.start_time = None
        self.should_stop = False
        
        # Set up signal handler for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully"""
        logger.info("Received shutdown signal. Stopping gracefully...")
        self.should_stop = True
    
    def initialize(self):
        """Initialize EasyOCR reader"""
        try:
            logger.info("Initializing EasyOCR...")
            self.reader = easyocr.Reader(['en'], gpu=False, verbose=False)
            logger.info("EasyOCR initialized successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize EasyOCR: {e}")
            return False
    
    def process_image(self, image_path: Path) -> str:
        """Process a single image and return OCR text"""
        try:
            # Read text from image
            results = self.reader.readtext(str(image_path))
            
            # Extract text from results
            text_parts = []
            for (bbox, text, confidence) in results:
                if confidence >= MIN_CONFIDENCE:
                    text_parts.append(text)
            
            # Join all text parts
            full_text = ' '.join(text_parts)
            return full_text.strip()
            
        except Exception as e:
            logger.error(f"Error processing {image_path}: {e}")
            return ""
    
    def save_ocr_text(self, file_path: Path, text: str) -> bool:
        """Save OCR text to a .txt file"""
        try:
            ocr_file = file_path.with_suffix('.txt')
            ocr_file.write_text(text, encoding='utf-8')
            return True
        except Exception as e:
            logger.error(f"Failed to save OCR text for {file_path}: {e}")
            return False
    
    def update_database(self, image_id: int, has_ocr: bool, ocr_path: str = None):
        """Update database with OCR status"""
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE images 
                SET has_ocr_text = ?, ocr_text_path = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (has_ocr, ocr_path, image_id))
            
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Failed to update database for image {image_id}: {e}")
    
    def get_unprocessed_images(self, limit: int = None):
        """Get images that haven't been processed yet"""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        query = """
            SELECT id, file_path, file_name, file_type 
            FROM images 
            WHERE has_ocr_text = FALSE
            ORDER BY id
        """
        
        if limit:
            query += f" LIMIT {limit}"
        
        cursor.execute(query)
        images = cursor.fetchall()
        conn.close()
        
        return images
    
    def get_total_counts(self):
        """Get total counts for progress tracking"""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        total_images = cursor.execute('SELECT COUNT(*) FROM images').fetchone()[0]
        processed_images = cursor.execute('SELECT COUNT(*) FROM images WHERE has_ocr_text = TRUE').fetchone()[0]
        
        conn.close()
        
        return total_images, processed_images
    
    def process_batch(self, images_batch):
        """Process a batch of images"""
        batch_results = []
        
        for image_id, file_path, file_name, file_type in images_batch:
            if self.should_stop:
                break
                
            full_path = DATA_DIR / file_path
            
            if not full_path.exists():
                logger.warning(f"File not found: {full_path}")
                self.update_database(image_id, False)
                continue
            
            # Process with OCR
            start_time = time.time()
            ocr_text = self.process_image(full_path)
            processing_time = time.time() - start_time
            
            if ocr_text and len(ocr_text.strip()) > 10:  # Only save if we got meaningful text
                # Save OCR text
                if self.save_ocr_text(full_path, ocr_text):
                    # Update database
                    ocr_text_path = str(full_path.with_suffix('.txt').relative_to(DATA_DIR))
                    self.update_database(image_id, True, ocr_text_path)
                    
                    result = {
                        'id': image_id,
                        'file_name': file_name,
                        'text_length': len(ocr_text),
                        'processing_time': processing_time,
                        'success': True
                    }
                    logger.info(f"✅ {file_name}: {len(ocr_text)} chars in {processing_time:.2f}s")
                else:
                    self.update_database(image_id, False)
                    result = {
                        'id': image_id,
                        'file_name': file_name,
                        'text_length': 0,
                        'processing_time': processing_time,
                        'success': False,
                        'error': 'Failed to save OCR text'
                    }
            else:
                self.update_database(image_id, False)
                result = {
                    'id': image_id,
                    'file_name': file_name,
                    'text_length': len(ocr_text),
                    'processing_time': processing_time,
                    'success': False,
                    'error': 'No meaningful text extracted'
                }
                logger.warning(f"⚠️ {file_name}: No meaningful text ({len(ocr_text)} chars)")
            
            batch_results.append(result)
            self.processed_count += 1
            
            # Progress update
            if self.processed_count % 10 == 0:
                elapsed = time.time() - self.start_time
                rate = self.processed_count / elapsed if elapsed > 0 else 0
                remaining = self.total_count - self.processed_count
                eta = remaining / rate if rate > 0 else 0
                
                logger.info(f"Progress: {self.processed_count}/{self.total_count} "
                          f"({self.processed_count/self.total_count*100:.1f}%) "
                          f"Rate: {rate:.1f} images/s ETA: {eta/60:.1f} min")
        
        return batch_results
    
    def run(self, max_images: int = None):
        """Run OCR processing on the dataset"""
        if not self.initialize():
            return False
        
        # Get total counts
        total_images, processed_images = self.get_total_counts()
        self.total_count = total_images - processed_images
        
        if max_images:
            self.total_count = min(self.total_count, max_images)
        
        logger.info(f"Starting OCR processing...")
        logger.info(f"Total images: {total_images}")
        logger.info(f"Already processed: {processed_images}")
        logger.info(f"Remaining to process: {self.total_count}")
        
        if self.total_count == 0:
            logger.info("No images to process!")
            return True
        
        self.start_time = time.time()
        
        # Process in batches
        offset = 0
        while offset < self.total_count and not self.should_stop:
            batch_size = min(BATCH_SIZE, self.total_count - offset)
            
            # Get batch of unprocessed images
            images_batch = self.get_unprocessed_images(limit=batch_size)
            
            if not images_batch:
                break
            
            logger.info(f"Processing batch {offset//BATCH_SIZE + 1}: "
                       f"images {offset + 1}-{offset + len(images_batch)}")
            
            # Process batch
            batch_results = self.process_batch(images_batch)
            
            # Batch summary
            successful = sum(1 for r in batch_results if r['success'])
            total_chars = sum(r['text_length'] for r in batch_results)
            avg_time = sum(r['processing_time'] for r in batch_results) / len(batch_results)
            
            logger.info(f"Batch complete: {successful}/{len(batch_results)} successful, "
                       f"{total_chars} total chars, {avg_time:.2f}s avg time")
            
            offset += len(images_batch)
        
        # Final summary
        if not self.should_stop:
            elapsed = time.time() - self.start_time
            rate = self.processed_count / elapsed if elapsed > 0 else 0
            
            logger.info("=" * 50)
            logger.info("OCR PROCESSING COMPLETE")
            logger.info("=" * 50)
            logger.info(f"Total processed: {self.processed_count}")
            logger.info(f"Total time: {elapsed/60:.1f} minutes")
            logger.info(f"Average rate: {rate:.1f} images/second")
            
            # Get final counts
            _, final_processed = self.get_total_counts()
            logger.info(f"Total images with OCR: {final_processed}")
        else:
            logger.info("Processing stopped by user")
        
        return True

def main():
    """Main function"""
    print("🔍 EasyOCR Document Processor")
    print("=" * 50)
    
    processor = EasyOCRProcessor()
    
    # Check if we want to process a limited number for testing
    import sys
    max_images = None
    if len(sys.argv) > 1:
        try:
            max_images = int(sys.argv[1])
            print(f"Processing limited to {max_images} images for testing")
        except ValueError:
            print("Invalid number provided, processing all images")
    
    success = processor.run(max_images=max_images)
    
    if success:
        print("\n✅ OCR processing completed successfully!")
        print("Check the web app to see the results:")
        print("  http://localhost:8080")
    else:
        print("\n❌ OCR processing failed!")

if __name__ == "__main__":
    main()
