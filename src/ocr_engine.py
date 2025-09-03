"""
TrOCR OCR Engine for Epstein Documents

High-quality OCR processing using Microsoft's TrOCR (Transformer-based OCR)
optimized for redacted documents.

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

import torch
from transformers import TrOCRProcessor, VisionEncoderDecoderModel
from PIL import Image
import logging
from pathlib import Path
import time
from typing import Optional, Dict, Any
import gc

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TrOCREngine:
    """
    TrOCR-based OCR engine optimized for redacted documents
    """
    
    def __init__(self, model_name: str = "microsoft/trocr-base-printed", 
                 device: Optional[str] = None, max_length: int = 512):
        """
        Initialize TrOCR engine
        
        Args:
            model_name: Hugging Face model name for TrOCR
            device: Device to run on ('cuda', 'cpu', or None for auto-detect)
            max_length: Maximum sequence length for text generation
        """
        self.model_name = model_name
        self.max_length = max_length
        
        # Auto-detect device if not specified
        if device is None:
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self.device = device
            
        logger.info(f"Initializing TrOCR on device: {self.device}")
        
        # Initialize model and processor
        self.processor = None
        self.model = None
        self._load_model()
        
    def _load_model(self):
        """Load TrOCR model and processor"""
        try:
            logger.info(f"Loading TrOCR model: {self.model_name}")
            
            # Load processor and model
            self.processor = TrOCRProcessor.from_pretrained(self.model_name)
            self.model = VisionEncoderDecoderModel.from_pretrained(self.model_name)
            
            # Move model to device
            self.model.to(self.device)
            
            # Set generation parameters for better performance
            self.model.config.decoder_start_token_id = self.processor.tokenizer.cls_token_id
            self.model.config.pad_token_id = self.processor.tokenizer.pad_token_id
            self.model.config.eos_token_id = self.processor.tokenizer.sep_token_id
            
            logger.info("TrOCR model loaded successfully")
            
        except Exception as e:
            logger.error(f"Failed to load TrOCR model: {e}")
            raise
    
    def preprocess_image(self, image_path: Path) -> Image.Image:
        """
        Preprocess image for OCR
        
        Args:
            image_path: Path to image file
            
        Returns:
            Preprocessed PIL Image
        """
        try:
            # Load image
            image = Image.open(image_path).convert('RGB')
            
            # Basic preprocessing for redacted documents
            # TrOCR handles redactions well, but we can optimize slightly
            return image
            
        except Exception as e:
            logger.error(f"Failed to preprocess image {image_path}: {e}")
            raise
    
    def extract_text(self, image_path: Path) -> Dict[str, Any]:
        """
        Extract text from image using TrOCR
        
        Args:
            image_path: Path to image file
            
        Returns:
            Dictionary containing extracted text and metadata
        """
        start_time = time.time()
        
        try:
            # Preprocess image
            image = self.preprocess_image(image_path)
            
            # Process image with TrOCR
            pixel_values = self.processor(images=image, return_tensors="pt").pixel_values
            pixel_values = pixel_values.to(self.device)
            
            # Generate text
            with torch.no_grad():
                generated_ids = self.model.generate(
                    pixel_values,
                    max_length=self.max_length,
                    num_beams=4,
                    early_stopping=True,
                    do_sample=False
                )
            
            # Decode generated text
            generated_text = self.processor.batch_decode(
                generated_ids, skip_special_tokens=True
            )[0]
            
            processing_time = time.time() - start_time
            
            # Clean up GPU memory
            if self.device == "cuda":
                torch.cuda.empty_cache()
                gc.collect()
            
            return {
                'text': generated_text.strip(),
                'processing_time': processing_time,
                'image_path': str(image_path),
                'model_used': self.model_name,
                'device': self.device,
                'success': True,
                'error': None
            }
            
        except Exception as e:
            processing_time = time.time() - start_time
            logger.error(f"OCR failed for {image_path}: {e}")
            
            return {
                'text': '',
                'processing_time': processing_time,
                'image_path': str(image_path),
                'model_used': self.model_name,
                'device': self.device,
                'success': False,
                'error': str(e)
            }
    
    def batch_extract(self, image_paths: list[Path]) -> list[Dict[str, Any]]:
        """
        Extract text from multiple images
        
        Args:
            image_paths: List of image file paths
            
        Returns:
            List of extraction results
        """
        results = []
        
        for image_path in image_paths:
            result = self.extract_text(image_path)
            results.append(result)
            
        return results
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the loaded model"""
        return {
            'model_name': self.model_name,
            'device': self.device,
            'max_length': self.max_length,
            'cuda_available': torch.cuda.is_available(),
            'model_loaded': self.model is not None
        }


def test_ocr_engine():
    """Test the OCR engine with a sample image"""
    try:
        # Initialize engine
        engine = TrOCREngine()
        
        # Print model info
        info = engine.get_model_info()
        print("TrOCR Engine Info:")
        for key, value in info.items():
            print(f"  {key}: {value}")
        
        # Test with a sample image if available
        data_dir = Path("data")
        if data_dir.exists():
            # Find first image file
            image_files = list(data_dir.glob("*.jpg")) + list(data_dir.glob("*.tif"))
            if image_files:
                test_image = image_files[0]
                print(f"\nTesting with: {test_image}")
                
                result = engine.extract_text(test_image)
                print(f"Success: {result['success']}")
                print(f"Processing time: {result['processing_time']:.2f}s")
                print(f"Text preview: {result['text'][:200]}...")
            else:
                print("No test images found in data directory")
        else:
            print("Data directory not found")
            
    except Exception as e:
        print(f"Test failed: {e}")


if __name__ == "__main__":
    test_ocr_engine()
