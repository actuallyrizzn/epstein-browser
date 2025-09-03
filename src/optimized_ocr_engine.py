"""
Optimized TrOCR Engine for Epstein Documents

High-performance OCR engine with advanced optimizations for CPU processing:
- Optimized image preprocessing
- Memory-efficient batch processing
- Advanced multithreading
- Model caching and reuse
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
import time
import logging
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
import multiprocessing as mp
from functools import lru_cache

import torch
from transformers import TrOCRProcessor, VisionEncoderDecoderModel
from PIL import Image, ImageOps, ImageEnhance, ImageFilter
import numpy as np
from tqdm import tqdm

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class OptimizedTrOCREngine:
    """
    Optimized TrOCR engine with advanced performance features
    """
    
    def __init__(self, 
                 model_name: str = "microsoft/trocr-base-printed",
                 device: Optional[str] = None,
                 max_workers: int = None,
                 batch_size: int = 4,
                 enable_preprocessing: bool = True,
                 cache_models: bool = True):
        """
        Initialize optimized TrOCR engine
        
        Args:
            model_name: TrOCR model to use
            device: Device to run on ('cpu', 'cuda', or None for auto-detect)
            max_workers: Maximum number of worker threads/processes
            batch_size: Number of images to process in parallel
            enable_preprocessing: Enable advanced image preprocessing
            cache_models: Cache loaded models for reuse
        """
        self.model_name = model_name
        self.device = device or self._detect_best_device()
        self.max_workers = max_workers or min(mp.cpu_count(), 8)
        self.batch_size = batch_size
        self.enable_preprocessing = enable_preprocessing
        self.cache_models = cache_models
        
        # Performance tracking
        self.processing_times = []
        self.total_images_processed = 0
        
        # Initialize models
        self._initialize_models()
        
        logger.info(f"OptimizedTrOCREngine initialized:")
        logger.info(f"  Device: {self.device}")
        logger.info(f"  Max workers: {self.max_workers}")
        logger.info(f"  Batch size: {self.batch_size}")
        logger.info(f"  Preprocessing: {self.enable_preprocessing}")
    
    def _detect_best_device(self) -> str:
        """Detect the best available device"""
        if torch.cuda.is_available():
            return "cuda"
        elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
            return "mps"
        else:
            return "cpu"
    
    def _initialize_models(self):
        """Initialize TrOCR models with optimizations"""
        logger.info(f"Loading TrOCR model: {self.model_name}")
        
        try:
            # Load processor and model
            self.processor = TrOCRProcessor.from_pretrained(self.model_name)
            self.model = VisionEncoderDecoderModel.from_pretrained(self.model_name)
            
            # Move to device
            self.model.to(self.device)
            
            # Optimize for inference
            self.model.eval()
            
            # Enable optimizations
            if self.device == "cpu":
                # CPU optimizations
                torch.set_num_threads(self.max_workers)
                # Note: torch.jit.optimize_for_inference requires a ScriptModule
                # We'll skip this optimization for now
            elif self.device == "cuda":
                # GPU optimizations
                try:
                    self.model = torch.compile(self.model, mode="reduce-overhead")
                except Exception as e:
                    logger.warning(f"Could not compile model: {e}")
            
            logger.info(f"Model loaded successfully on {self.device}")
            
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            raise
    
    @lru_cache(maxsize=128)
    def _preprocess_image_cached(self, image_path: str, enhancement_level: float = 1.2) -> Image.Image:
        """
        Cached image preprocessing for better performance
        """
        try:
            # Load image
            image = Image.open(image_path).convert('RGB')
            
            if not self.enable_preprocessing:
                return image
            
            # Resize if too large (TrOCR works best with reasonable sizes)
            max_size = 1024
            if max(image.size) > max_size:
                ratio = max_size / max(image.size)
                new_size = (int(image.size[0] * ratio), int(image.size[1] * ratio))
                image = image.resize(new_size, Image.Resampling.LANCZOS)
            
            # Enhance contrast and sharpness
            if enhancement_level > 1.0:
                # Contrast enhancement
                enhancer = ImageEnhance.Contrast(image)
                image = enhancer.enhance(enhancement_level)
                
                # Sharpness enhancement
                enhancer = ImageEnhance.Sharpness(image)
                image = enhancer.enhance(1.1)
            
            # Apply slight denoising
            image = image.filter(ImageFilter.MedianFilter(size=3))
            
            return image
            
        except Exception as e:
            logger.error(f"Error preprocessing image {image_path}: {e}")
            # Return original image if preprocessing fails
            return Image.open(image_path).convert('RGB')
    
    def _preprocess_image(self, image_path: str) -> Image.Image:
        """Preprocess a single image"""
        return self._preprocess_image_cached(image_path)
    
    def _process_single_image(self, image_path: str) -> Tuple[str, float, bool]:
        """
        Process a single image with performance tracking
        
        Returns:
            Tuple of (extracted_text, processing_time, success)
        """
        start_time = time.time()
        
        try:
            # Preprocess image
            image = self._preprocess_image(image_path)
            
            # Process with TrOCR
            pixel_values = self.processor(image, return_tensors="pt").pixel_values
            pixel_values = pixel_values.to(self.device)
            
            # Generate text
            with torch.no_grad():
                generated_ids = self.model.generate(pixel_values)
                generated_text = self.processor.batch_decode(generated_ids, skip_special_tokens=True)[0]
            
            processing_time = time.time() - start_time
            self.processing_times.append(processing_time)
            self.total_images_processed += 1
            
            return generated_text.strip(), processing_time, True
            
        except Exception as e:
            processing_time = time.time() - start_time
            logger.error(f"Error processing {image_path}: {e}")
            return "", processing_time, False
    
    def _process_batch_threaded(self, image_paths: List[str]) -> List[Tuple[str, str, float, bool]]:
        """
        Process a batch of images using threading
        """
        results = []
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all tasks
            future_to_path = {
                executor.submit(self._process_single_image, path): path 
                for path in image_paths
            }
            
            # Collect results with progress bar
            for future in tqdm(future_to_path, desc="Processing batch", leave=False):
                path = future_to_path[future]
                try:
                    text, processing_time, success = future.result()
                    results.append((path, text, processing_time, success))
                except Exception as e:
                    logger.error(f"Error in threaded processing for {path}: {e}")
                    results.append((path, "", 0.0, False))
        
        return results
    
    def _process_batch_multiprocess(self, image_paths: List[str]) -> List[Tuple[str, str, float, bool]]:
        """
        Process a batch of images using multiprocessing
        """
        results = []
        
        # Split paths into chunks for each process
        chunk_size = max(1, len(image_paths) // self.max_workers)
        chunks = [image_paths[i:i + chunk_size] for i in range(0, len(image_paths), chunk_size)]
        
        with ProcessPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit chunks to processes
            futures = [executor.submit(self._process_chunk, chunk) for chunk in chunks]
            
            # Collect results
            for future in tqdm(futures, desc="Processing chunks", leave=False):
                try:
                    chunk_results = future.result()
                    results.extend(chunk_results)
                except Exception as e:
                    logger.error(f"Error in multiprocess chunk: {e}")
        
        return results
    
    def process_images(self, 
                      image_paths: List[str], 
                      output_dir: str,
                      use_multiprocessing: bool = False,
                      progress_callback: Optional[callable] = None) -> Dict[str, Any]:
        """
        Process multiple images with optimized performance
        
        Args:
            image_paths: List of image file paths
            output_dir: Directory to save text files
            use_multiprocessing: Use multiprocessing instead of threading
            progress_callback: Optional callback for progress updates
            
        Returns:
            Dictionary with processing statistics
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        total_images = len(image_paths)
        successful = 0
        failed = 0
        total_processing_time = 0
        
        logger.info(f"Processing {total_images} images with {self.max_workers} workers")
        logger.info(f"Using {'multiprocessing' if use_multiprocessing else 'threading'}")
        
        # Process in batches
        for i in range(0, total_images, self.batch_size):
            batch_paths = image_paths[i:i + self.batch_size]
            batch_num = i // self.batch_size + 1
            total_batches = (total_images + self.batch_size - 1) // self.batch_size
            
            logger.info(f"Processing batch {batch_num}/{total_batches} ({len(batch_paths)} images)")
            
            # Process batch
            if use_multiprocessing:
                batch_results = self._process_batch_multiprocess(batch_paths)
            else:
                batch_results = self._process_batch_threaded(batch_paths)
            
            # Save results
            for image_path, text, processing_time, success in batch_results:
                total_processing_time += processing_time
                
                if success and text:
                    # Save text file
                    image_path_obj = Path(image_path)
                    text_file = output_path / f"{image_path_obj.stem}.txt"
                    
                    try:
                        with open(text_file, 'w', encoding='utf-8') as f:
                            f.write(text)
                        successful += 1
                    except Exception as e:
                        logger.error(f"Error saving text file {text_file}: {e}")
                        failed += 1
                else:
                    failed += 1
                
                # Progress callback
                if progress_callback:
                    progress_callback(image_path, success, processing_time, text)
            
            # Log batch progress
            avg_time = total_processing_time / (successful + failed) if (successful + failed) > 0 else 0
            logger.info(f"Batch {batch_num} complete. Avg time: {avg_time:.2f}s, Success: {successful}, Failed: {failed}")
        
        # Calculate final statistics
        avg_processing_time = total_processing_time / total_images if total_images > 0 else 0
        success_rate = (successful / total_images * 100) if total_images > 0 else 0
        
        stats = {
            'total_images': total_images,
            'successful': successful,
            'failed': failed,
            'success_rate': success_rate,
            'total_processing_time': total_processing_time,
            'avg_processing_time': avg_processing_time,
            'images_per_minute': (total_images / (total_processing_time / 60)) if total_processing_time > 0 else 0
        }
        
        logger.info(f"Processing complete:")
        logger.info(f"  Total images: {total_images}")
        logger.info(f"  Successful: {successful}")
        logger.info(f"  Failed: {failed}")
        logger.info(f"  Success rate: {success_rate:.1f}%")
        logger.info(f"  Average processing time: {avg_processing_time:.2f}s")
        logger.info(f"  Images per minute: {stats['images_per_minute']:.1f}")
        
        return stats
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get current performance statistics"""
        if not self.processing_times:
            return {}
        
        return {
            'total_processed': self.total_images_processed,
            'avg_processing_time': np.mean(self.processing_times),
            'min_processing_time': np.min(self.processing_times),
            'max_processing_time': np.max(self.processing_times),
            'std_processing_time': np.std(self.processing_times),
            'images_per_minute': 60 / np.mean(self.processing_times) if self.processing_times else 0
        }
    
    def cleanup(self):
        """Clean up resources"""
        if hasattr(self, 'model'):
            del self.model
        if hasattr(self, 'processor'):
            del self.processor
        torch.cuda.empty_cache() if torch.cuda.is_available() else None


def process_chunk(image_paths: List[str]) -> List[Tuple[str, str, float, bool]]:
    """
    Process a chunk of images in a separate process
    This function needs to be at module level for multiprocessing
    """
    # Create a temporary engine for this process
    engine = OptimizedTrOCREngine(max_workers=1, batch_size=1)
    
    results = []
    for path in image_paths:
        text, processing_time, success = engine._process_single_image(path)
        results.append((path, text, processing_time, success))
    
    engine.cleanup()
    return results


# Make the function available for multiprocessing
if __name__ != "__main__":
    # This allows the function to be pickled for multiprocessing
    import sys
    sys.modules[__name__].process_chunk = process_chunk
