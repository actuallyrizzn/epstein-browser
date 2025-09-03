"""
Batch Processor for OCR Processing

Handles batch processing of 33,657 images with progress tracking,
error handling, and graceful exits.

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

import signal
import sys
import time
from pathlib import Path
from typing import List, Dict, Any, Optional
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

from ocr_engine import TrOCREngine
from progress_tracker import ProgressTracker

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class BatchProcessor:
    """
    Batch processor for OCR processing with progress tracking
    """
    
    def __init__(self, data_dir: str = "data", 
                 db_path: str = "ocr_progress.db",
                 max_workers: int = 1,
                 batch_size: int = 100):
        """
        Initialize batch processor
        
        Args:
            data_dir: Directory containing images
            db_path: Path to progress tracking database
            max_workers: Number of parallel workers (1 for CPU, 2-4 for GPU)
            batch_size: Number of files to process in each batch
        """
        self.data_dir = Path(data_dir)
        self.db_path = db_path
        self.max_workers = max_workers
        self.batch_size = batch_size
        
        # Initialize components
        self.ocr_engine = None
        self.progress_tracker = ProgressTracker(db_path)
        self.shutdown_requested = False
        
        # Setup graceful exit handling
        self._setup_signal_handlers()
        
        # Statistics
        self.stats = {
            'processed': 0,
            'failed': 0,
            'start_time': None,
            'last_checkpoint': None
        }
    
    def _setup_signal_handlers(self):
        """Setup graceful exit signal handlers"""
        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}, initiating graceful shutdown...")
            self.shutdown_requested = True
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Windows-specific signals
        if hasattr(signal, 'SIGBREAK'):
            signal.signal(signal.SIGBREAK, signal_handler)
    
    def initialize_ocr_engine(self):
        """Initialize OCR engine"""
        try:
            logger.info("Initializing TrOCR engine...")
            self.ocr_engine = TrOCREngine()
            
            # Print engine info
            info = self.ocr_engine.get_model_info()
            logger.info(f"OCR Engine Info: {info}")
            
        except Exception as e:
            logger.error(f"Failed to initialize OCR engine: {e}")
            raise
    
    def discover_images(self) -> List[Path]:
        """
        Discover all image files in data directory
        
        Returns:
            List of image file paths
        """
        logger.info(f"Discovering images in {self.data_dir}")
        
        image_extensions = {'.jpg', '.jpeg', '.tif', '.tiff', '.png', '.bmp'}
        image_files = []
        
        for ext in image_extensions:
            image_files.extend(self.data_dir.rglob(f"*{ext}"))
            image_files.extend(self.data_dir.rglob(f"*{ext.upper()}"))
        
        logger.info(f"Found {len(image_files)} image files")
        return image_files
    
    def initialize_database(self):
        """Initialize database with all discovered images"""
        logger.info("Initializing database with image files...")
        
        image_files = self.discover_images()
        added_count = self.progress_tracker.add_files(image_files)
        
        logger.info(f"Added {added_count} new files to database")
        return added_count
    
    def process_single_file(self, file_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a single image file
        
        Args:
            file_info: File information from database
            
        Returns:
            Processing result
        """
        file_path = Path(file_info['file_path'])
        
        try:
            # Update status to processing
            self.progress_tracker.update_file_status(
                str(file_path), 'processing'
            )
            
            # Extract text using OCR
            result = self.ocr_engine.extract_text(file_path)
            
            if result['success']:
                # Save extracted text to file
                text_file_path = file_path.with_suffix('.txt')
                text_file_path.write_text(result['text'], encoding='utf-8')
                
                # Save to database
                self.progress_tracker.save_extracted_text(
                    str(file_path), result['text'], str(text_file_path)
                )
                
                # Update status to completed
                self.progress_tracker.update_file_status(
                    str(file_path), 'completed',
                    processing_time=result['processing_time'],
                    text_length=len(result['text']),
                    model_used=result['model_used'],
                    device_used=result['device']
                )
                
                return {
                    'success': True,
                    'file_path': str(file_path),
                    'processing_time': result['processing_time'],
                    'text_length': len(result['text'])
                }
            else:
                # Update status to failed
                self.progress_tracker.update_file_status(
                    str(file_path), 'failed',
                    processing_time=result['processing_time'],
                    error_message=result['error']
                )
                
                return {
                    'success': False,
                    'file_path': str(file_path),
                    'error': result['error']
                }
                
        except Exception as e:
            logger.error(f"Unexpected error processing {file_path}: {e}")
            
            # Update status to failed
            self.progress_tracker.update_file_status(
                str(file_path), 'failed',
                error_message=str(e)
            )
            
            return {
                'success': False,
                'file_path': str(file_path),
                'error': str(e)
            }
    
    def process_batch(self, batch_files: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Process a batch of files
        
        Args:
            batch_files: List of file information dictionaries
            
        Returns:
            Batch processing results
        """
        batch_results = {
            'processed': 0,
            'failed': 0,
            'total_time': 0,
            'errors': []
        }
        
        start_time = time.time()
        
        # Process files in parallel if max_workers > 1
        if self.max_workers > 1:
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                future_to_file = {
                    executor.submit(self.process_single_file, file_info): file_info
                    for file_info in batch_files
                }
                
                for future in as_completed(future_to_file):
                    if self.shutdown_requested:
                        logger.info("Shutdown requested, cancelling remaining tasks...")
                        break
                    
                    file_info = future_to_file[future]
                    try:
                        result = future.result()
                        
                        if result['success']:
                            batch_results['processed'] += 1
                            batch_results['total_time'] += result['processing_time']
                        else:
                            batch_results['failed'] += 1
                            batch_results['errors'].append(result['error'])
                            
                    except Exception as e:
                        logger.error(f"Task failed for {file_info['file_path']}: {e}")
                        batch_results['failed'] += 1
                        batch_results['errors'].append(str(e))
        else:
            # Sequential processing
            for file_info in batch_files:
                if self.shutdown_requested:
                    logger.info("Shutdown requested, stopping batch processing...")
                    break
                
                result = self.process_single_file(file_info)
                
                if result['success']:
                    batch_results['processed'] += 1
                    batch_results['total_time'] += result['processing_time']
                else:
                    batch_results['failed'] += 1
                    batch_results['errors'].append(result['error'])
        
        batch_results['batch_time'] = time.time() - start_time
        return batch_results
    
    def run_processing(self, max_files: Optional[int] = None):
        """
        Run the main processing loop
        
        Args:
            max_files: Maximum number of files to process (None for all)
        """
        logger.info("Starting OCR processing...")
        
        # Initialize OCR engine
        self.initialize_ocr_engine()
        
        # Initialize database
        self.initialize_database()
        
        # Get pending files
        pending_files = self.progress_tracker.get_pending_files(limit=max_files)
        total_files = len(pending_files)
        
        if total_files == 0:
            logger.info("No pending files to process")
            return
        
        logger.info(f"Processing {total_files} files in batches of {self.batch_size}")
        
        self.stats['start_time'] = time.time()
        
        # Process in batches
        for i in range(0, total_files, self.batch_size):
            if self.shutdown_requested:
                logger.info("Shutdown requested, stopping processing...")
                break
            
            batch_files = pending_files[i:i + self.batch_size]
            batch_num = (i // self.batch_size) + 1
            total_batches = (total_files + self.batch_size - 1) // self.batch_size
            
            logger.info(f"Processing batch {batch_num}/{total_batches} ({len(batch_files)} files)")
            
            # Process batch
            batch_results = self.process_batch(batch_files)
            
            # Update statistics
            self.stats['processed'] += batch_results['processed']
            self.stats['failed'] += batch_results['failed']
            self.stats['last_checkpoint'] = time.time()
            
            # Log batch results
            logger.info(f"Batch {batch_num} completed: "
                       f"{batch_results['processed']} processed, "
                       f"{batch_results['failed']} failed, "
                       f"{batch_results['batch_time']:.2f}s")
            
            # Print overall progress
            completed = self.stats['processed'] + self.stats['failed']
            progress_pct = (completed / total_files) * 100
            logger.info(f"Overall progress: {completed}/{total_files} ({progress_pct:.1f}%)")
            
            # Print statistics
            if completed > 0:
                elapsed_time = time.time() - self.stats['start_time']
                avg_time_per_file = elapsed_time / completed
                remaining_files = total_files - completed
                eta_seconds = remaining_files * avg_time_per_file
                eta_hours = eta_seconds / 3600
                
                logger.info(f"ETA: {eta_hours:.1f} hours ({remaining_files} files remaining)")
        
        # Final statistics
        self.print_final_statistics()
    
    def print_final_statistics(self):
        """Print final processing statistics"""
        logger.info("=== FINAL STATISTICS ===")
        
        if self.stats['start_time']:
            total_time = time.time() - self.stats['start_time']
            logger.info(f"Total processing time: {total_time/3600:.2f} hours")
        
        logger.info(f"Files processed: {self.stats['processed']}")
        logger.info(f"Files failed: {self.stats['failed']}")
        
        # Get database statistics
        db_stats = self.progress_tracker.get_statistics()
        logger.info(f"Database statistics: {db_stats}")


def main():
    """Main function for running batch processing"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Batch OCR Processing")
    parser.add_argument("--data-dir", default="data", help="Data directory")
    parser.add_argument("--db-path", default="ocr_progress.db", help="Database path")
    parser.add_argument("--max-workers", type=int, default=1, help="Max parallel workers")
    parser.add_argument("--batch-size", type=int, default=100, help="Batch size")
    parser.add_argument("--max-files", type=int, help="Maximum files to process")
    
    args = parser.parse_args()
    
    # Create and run processor
    processor = BatchProcessor(
        data_dir=args.data_dir,
        db_path=args.db_path,
        max_workers=args.max_workers,
        batch_size=args.batch_size
    )
    
    try:
        processor.run_processing(max_files=args.max_files)
    except KeyboardInterrupt:
        logger.info("Processing interrupted by user")
    except Exception as e:
        logger.error(f"Processing failed: {e}")
        raise


if __name__ == "__main__":
    main()
