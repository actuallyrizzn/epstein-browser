#!/usr/bin/env python3
"""
LLM Correction Processor

Main script for processing OCR text corrections using LLM APIs.
Handles batch processing, rate limiting, and database updates.
"""

import os
import sys
import time
import sqlite3
from typing import List, Dict, Any, Optional
from datetime import datetime

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv not available, use system environment variables

# Add helpers to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'helpers'))

from helpers.ocr_quality_assessment import OCRQualityAssessment
from helpers.llm_client import LLMClient, RateLimitError, APIError


class LLMCorrectionProcessor:
    """Main processor for LLM-based OCR corrections"""
    
    def __init__(self, db_path: str = "images.db", model: str = "llama-3.3-70b"):
        self.db_path = db_path
        self.model = model
        self.llm_client = LLMClient(model)
        self.ocr_assessor = OCRQualityAssessment(db_path, self.llm_client)
        
        # Ensure database schema is up to date
        conn = sqlite3.connect(db_path)
        self.ocr_assessor.ensure_database_schema(conn)
        conn.close()
    
    def get_images_needing_correction(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get images that need OCR correction"""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute("""
                SELECT id, file_path, file_name, has_ocr_text, has_corrected_text
                FROM images 
                WHERE has_ocr_text = TRUE 
                AND has_corrected_text = FALSE
                ORDER BY id
                LIMIT ?
            """, (limit,))
            
            columns = [description[0] for description in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
        finally:
            conn.close()
    
    def get_ocr_text(self, file_path: str) -> Optional[str]:
        """Get OCR text from file system"""
        try:
            # Convert backslashes to forward slashes for cross-platform compatibility
            file_path = file_path.replace('\\', '/')
            
            # Create the OCR text file path by replacing the extension with .txt
            ocr_file = os.path.join("data", file_path)
            ocr_file = os.path.splitext(ocr_file)[0] + '.txt'
            
            if os.path.exists(ocr_file):
                with open(ocr_file, 'r', encoding='utf-8') as f:
                    return f.read()
            return None
        except Exception as e:
            print(f"Error reading OCR text for {file_path}: {e}")
            return None
    
    def process_image(self, image: Dict[str, Any]) -> bool:
        """Process a single image for OCR correction"""
        image_id = image['id']
        file_path = image['file_path']
        
        print(f"Processing image {image_id}: {image['file_name']}")
        
        # Get original OCR text
        original_text = self.get_ocr_text(file_path)
        if not original_text:
            print(f"No OCR text found for image {image_id}")
            return False
        
        # Check for low-quality OCR and flag for reprocessing if needed
        if self.ocr_assessor.flag_low_quality_for_reprocessing(image_id, original_text):
            print(f"Low-quality OCR detected for image {image_id}, flagged for reprocessing")
            return False
        
        # Skip if text is too short (likely not meaningful)
        if len(original_text.strip()) < 10:
            print(f"OCR text too short for image {image_id}, skipping")
            return False
        
        try:
            start_time = time.time()
            
            # Round 1: Correct OCR text
            print(f"  Round 1: Correcting OCR text...")
            corrected_text = self.ocr_assessor.correct_ocr_text(original_text)
            
            # Validate that correction actually changed something
            if not self.ocr_assessor.validate_correction_changes(original_text, corrected_text):
                print(f"  No changes detected for image {image_id}, skipping")
                return False
            
            # Round 2: Assess correction quality
            print(f"  Round 2: Assessing correction quality...")
            assessment = self.ocr_assessor.assess_correction_quality(original_text, corrected_text)
            
            processing_time = int((time.time() - start_time) * 1000)
            
            # Save correction to database
            print(f"  Saving correction to database...")
            correction_id = self.ocr_assessor.save_correction(
                image_id, original_text, corrected_text, 
                assessment, self.model, processing_time
            )
            
            print(f"  ✓ Correction saved (ID: {correction_id}, Quality: {assessment.get('quality_score', 'N/A')})")
            return True
            
        except RateLimitError:
            print(f"  ⚠ Rate limited - exiting processing loop")
            raise  # Re-raise to exit processing
        except Exception as e:
            print(f"  ✗ Error processing image {image_id}: {e}")
            return False
    
    def process_batch(self, batch_size: int = 10) -> Dict[str, Any]:
        """Process a batch of images for OCR correction"""
        print(f"Starting LLM correction processing (batch size: {batch_size})")
        print(f"Model: {self.model}")
        print("-" * 50)
        
        # Get images needing correction
        images = self.get_images_needing_correction(batch_size)
        
        if not images:
            print("No images need correction")
            return {"processed": 0, "successful": 0, "failed": 0, "rate_limited": False}
        
        print(f"Found {len(images)} images needing correction")
        
        processed = 0
        successful = 0
        failed = 0
        rate_limited = False
        
        for image in images:
            try:
                if self.process_image(image):
                    successful += 1
                else:
                    failed += 1
                processed += 1
                
                # Small delay between images
                time.sleep(0.5)
                
            except RateLimitError:
                print("Rate limited - stopping processing")
                rate_limited = True
                break
            except KeyboardInterrupt:
                print("\nProcessing interrupted by user")
                break
        
        print("-" * 50)
        print(f"Processing complete:")
        print(f"  Processed: {processed}")
        print(f"  Successful: {successful}")
        print(f"  Failed: {failed}")
        print(f"  Rate limited: {rate_limited}")
        
        return {
            "processed": processed,
            "successful": successful,
            "failed": failed,
            "rate_limited": rate_limited
        }


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="LLM Correction Processor")
    parser.add_argument("--db", default="images.db", help="Database path")
    parser.add_argument("--model", default="llama-3.3-70b", help="LLM model to use")
    parser.add_argument("--batch-size", type=int, default=10, help="Batch size")
    
    args = parser.parse_args()
    
    # Check for Venice API key
    if not os.getenv("VENICE_API_KEY"):
        print("Error: VENICE_API_KEY environment variable not set")
        sys.exit(1)
    
    try:
        processor = LLMCorrectionProcessor(args.db, args.model)
        result = processor.process_batch(args.batch_size)
        
        if result["rate_limited"]:
            print("\n⚠ Processing stopped due to rate limiting")
            print("Run again later to continue processing")
            sys.exit(2)
        else:
            print(f"\n✓ Processing completed successfully")
            sys.exit(0)
            
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
