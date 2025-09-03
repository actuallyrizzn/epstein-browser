"""
Optimized Batch Processor for Epstein Documents OCR

High-performance batch processing system with advanced optimizations:
- Intelligent work distribution
- Memory management
- Progress tracking with ETA
- Graceful shutdown handling
- Performance monitoring

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

import os
import sys
import time
import signal
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime, timedelta
import multiprocessing as mp

from optimized_ocr_engine import OptimizedTrOCREngine
from progress_tracker import ProgressTracker

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('ocr_processing.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class OptimizedBatchProcessor:
    """
    Optimized batch processor for large-scale OCR processing
    """
    
    def __init__(self,
                 data_dir: str = "data",
                 output_dir: str = "data/ocr_output",
                 db_path: str = "ocr_progress.db",
                 max_workers: int = None,
                 batch_size: int = 8,
                 use_multiprocessing: bool = False,
                 enable_preprocessing: bool = True,
                 model_name: str = "microsoft/trocr-base-printed"):
        """
        Initialize optimized batch processor
        
        Args:
            data_dir: Directory containing images
            output_dir: Directory for OCR output
            db_path: Path to progress database
            max_workers: Maximum number of workers
            batch_size: Batch size for processing
            use_multiprocessing: Use multiprocessing instead of threading
            enable_preprocessing: Enable image preprocessing
            model_name: TrOCR model to use
        """
        self.data_dir = Path(data_dir)
        self.output_dir = Path(output_dir)
        self.db_path = db_path
        self.max_workers = max_workers or min(mp.cpu_count(), 8)
        self.batch_size = batch_size
        self.use_multiprocessing = use_multiprocessing
        self.enable_preprocessing = enable_preprocessing
        self.model_name = model_name
        
        # Initialize components
        self.progress_tracker = ProgressTracker(db_path)
        self.ocr_engine = None
        self.shutdown_requested = False
        
        # Performance tracking
        self.start_time = None
        self.last_progress_time = None
        self.processing_stats = {}
        
        # Setup signal handlers for graceful shutdown
        self._setup_signal_handlers()
        
        logger.info(f"OptimizedBatchProcessor initialized:")
        logger.info(f"  Data directory: {self.data_dir}")
        logger.info(f"  Output directory: {self.output_dir}")
        logger.info(f"  Max workers: {self.max_workers}")
        logger.info(f"  Batch size: {self.batch_size}")
        logger.info(f"  Multiprocessing: {self.use_multiprocessing}")
        logger.info(f"  Preprocessing: {self.enable_preprocessing}")
    
    def _setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown"""
        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}, initiating graceful shutdown...")
            self.shutdown_requested = True
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    
    def _discover_image_files(self) -> List[Path]:
        """Discover all image files in the data directory"""
        logger.info("Discovering image files...")
        
        image_extensions = {'.jpg', '.jpeg', '.png', '.tif', '.tiff', '.bmp', '.webp'}
        image_files = []
        
        for ext in image_extensions:
            pattern = f"**/*{ext}"
            files = list(self.data_dir.glob(pattern))
            image_files.extend(files)
            
            # Also check uppercase extensions
            pattern = f"**/*{ext.upper()}"
            files = list(self.data_dir.glob(pattern))
            image_files.extend(files)
        
        # Remove duplicates and sort
        image_files = sorted(list(set(image_files)))
        
        logger.info(f"Found {len(image_files)} image files")
        return image_files
    
    def _filter_pending_files(self, image_files: List[Path]) -> List[Path]:
        """Filter out already processed files"""
        logger.info("Filtering pending files...")
        
        pending_files = []
        for image_file in image_files:
            # Check if already processed
            if not self.progress_tracker.is_file_processed(str(image_file)):
                pending_files.append(image_file)
        
        logger.info(f"Found {len(pending_files)} pending files out of {len(image_files)} total")
        return pending_files
    
    def _create_output_structure(self, image_file: Path) -> Path:
        """Create output directory structure matching input structure"""
        # Get relative path from data directory
        rel_path = image_file.relative_to(self.data_dir)
        
        # Create output path maintaining directory structure
        output_file = self.output_dir / rel_path.with_suffix('.txt')
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        return output_file
    
    def _progress_callback(self, image_path: str, success: bool, processing_time: float, text: str):
        """Callback for progress updates"""
        try:
            # Update progress tracker
            if success:
                self.progress_tracker.update_file_status(
                    image_path, 'completed',
                    processing_time=processing_time,
                    text_length=len(text),
                    model_used=self.model_name,
                    device_used='cpu'  # We'll detect this dynamically
                )
            else:
                self.progress_tracker.update_file_status(
                    image_path, 'failed',
                    processing_time=processing_time,
                    error_message="Processing failed"
                )
            
            # Log progress periodically
            current_time = time.time()
            if (self.last_progress_time is None or 
                current_time - self.last_progress_time > 30):  # Every 30 seconds
                
                stats = self.progress_tracker.get_statistics()
                self._log_progress(stats)
                self.last_progress_time = current_time
                
        except Exception as e:
            logger.error(f"Error in progress callback: {e}")
    
    def _log_progress(self, stats: Dict[str, Any]):
        """Log current progress with ETA"""
        if stats['total_files'] == 0:
            return
        
        processed = stats['processed_count']
        total = stats['total_files']
        percentage = (processed / total * 100) if total > 0 else 0
        
        # Calculate ETA
        if processed > 0 and self.start_time:
            elapsed_time = time.time() - self.start_time
            avg_time_per_file = elapsed_time / processed
            remaining_files = total - processed
            eta_seconds = remaining_files * avg_time_per_file
            eta = datetime.now() + timedelta(seconds=eta_seconds)
            eta_str = eta.strftime("%Y-%m-%d %H:%M:%S")
        else:
            eta_str = "Calculating..."
        
        logger.info(f"Progress: {processed}/{total} ({percentage:.1f}%) - ETA: {eta_str}")
        
        if stats['avg_processing_time'] > 0:
            logger.info(f"  Avg processing time: {stats['avg_processing_time']:.2f}s")
            logger.info(f"  Images per minute: {60 / stats['avg_processing_time']:.1f}")
    
    def _initialize_ocr_engine(self):
        """Initialize the OCR engine"""
        if self.ocr_engine is None:
            logger.info("Initializing OCR engine...")
            self.ocr_engine = OptimizedTrOCREngine(
                model_name=self.model_name,
                max_workers=self.max_workers,
                batch_size=self.batch_size,
                enable_preprocessing=self.enable_preprocessing
            )
    
    def _cleanup_ocr_engine(self):
        """Cleanup OCR engine resources"""
        if self.ocr_engine:
            logger.info("Cleaning up OCR engine...")
            self.ocr_engine.cleanup()
            self.ocr_engine = None
    
    def run_processing(self, 
                      max_files: Optional[int] = None,
                      resume: bool = True) -> Dict[str, Any]:
        """
        Run the optimized OCR processing
        
        Args:
            max_files: Maximum number of files to process (None for all)
            resume: Resume from previous progress
            
        Returns:
            Dictionary with processing results
        """
        try:
            self.start_time = time.time()
            logger.info("Starting optimized OCR processing...")
            
            # Discover image files
            all_image_files = self._discover_image_files()
            
            if not all_image_files:
                logger.warning("No image files found!")
                return {'error': 'No image files found'}
            
            # Filter pending files
            if resume:
                pending_files = self._filter_pending_files(all_image_files)
            else:
                pending_files = all_image_files
                # Clear progress database
                self.progress_tracker.clear_all_files()
            
            if not pending_files:
                logger.info("No pending files to process!")
                return {'message': 'No pending files to process'}
            
            # Limit files if specified
            if max_files:
                pending_files = pending_files[:max_files]
                logger.info(f"Limited to {max_files} files")
            
            # Add files to progress tracker
            self.progress_tracker.add_files([str(f) for f in pending_files])
            
            # Initialize OCR engine
            self._initialize_ocr_engine()
            
            # Process files
            logger.info(f"Processing {len(pending_files)} files...")
            
            # Convert to string paths for the OCR engine
            image_paths = [str(f) for f in pending_files]
            
            # Process with the optimized engine
            stats = self.ocr_engine.process_images(
                image_paths=image_paths,
                output_dir=str(self.output_dir),
                use_multiprocessing=self.use_multiprocessing,
                progress_callback=self._progress_callback
            )
            
            # Final statistics
            final_stats = self.progress_tracker.get_statistics()
            total_time = time.time() - self.start_time
            
            logger.info("Processing completed!")
            logger.info(f"Total time: {total_time:.2f} seconds ({total_time/3600:.2f} hours)")
            logger.info(f"Final statistics: {final_stats}")
            
            return {
                'success': True,
                'total_files': len(pending_files),
                'successful': stats['successful'],
                'failed': stats['failed'],
                'success_rate': stats['success_rate'],
                'total_time': total_time,
                'avg_processing_time': stats['avg_processing_time'],
                'images_per_minute': stats['images_per_minute'],
                'final_stats': final_stats
            }
            
        except KeyboardInterrupt:
            logger.info("Processing interrupted by user")
            return {'error': 'Processing interrupted by user'}
        except Exception as e:
            logger.error(f"Error during processing: {e}")
            return {'error': str(e)}
        finally:
            # Cleanup
            self._cleanup_ocr_engine()
            if hasattr(self, 'progress_tracker'):
                self.progress_tracker.close()
    
    def get_current_progress(self) -> Dict[str, Any]:
        """Get current processing progress"""
        return self.progress_tracker.get_statistics()
    
    def estimate_completion_time(self) -> str:
        """Estimate completion time based on current progress"""
        stats = self.get_current_progress()
        
        if stats['processed_count'] == 0 or stats['avg_processing_time'] == 0:
            return "Cannot estimate - no processing data"
        
        remaining_files = stats['total_files'] - stats['processed_count']
        eta_seconds = remaining_files * stats['avg_processing_time']
        eta = datetime.now() + timedelta(seconds=eta_seconds)
        
        return eta.strftime("%Y-%m-%d %H:%M:%S")


def main():
    """Main function for testing the optimized batch processor"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Optimized OCR Batch Processor")
    parser.add_argument("--data-dir", default="data", help="Data directory")
    parser.add_argument("--output-dir", default="data/ocr_output", help="Output directory")
    parser.add_argument("--max-files", type=int, help="Maximum files to process")
    parser.add_argument("--max-workers", type=int, help="Maximum workers")
    parser.add_argument("--batch-size", type=int, default=8, help="Batch size")
    parser.add_argument("--multiprocessing", action="store_true", help="Use multiprocessing")
    parser.add_argument("--no-preprocessing", action="store_true", help="Disable preprocessing")
    parser.add_argument("--resume", action="store_true", default=True, help="Resume processing")
    
    args = parser.parse_args()
    
    # Create processor
    processor = OptimizedBatchProcessor(
        data_dir=args.data_dir,
        output_dir=args.output_dir,
        max_workers=args.max_workers,
        batch_size=args.batch_size,
        use_multiprocessing=args.multiprocessing,
        enable_preprocessing=not args.no_preprocessing
    )
    
    # Run processing
    results = processor.run_processing(
        max_files=args.max_files,
        resume=args.resume
    )
    
    print(f"Processing results: {results}")


if __name__ == "__main__":
    main()
