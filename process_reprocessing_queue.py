#!/usr/bin/env python3
"""
Process Reprocessing Queue

Script to process items in the OCR reprocessing queue.
Handles low-quality OCR that was flagged for higher-quality reprocessing.
"""

import os
import sys
import argparse

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Add helpers to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'helpers'))

from helpers.ocr_quality_assessment import OCRQualityAssessment


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Process OCR Reprocessing Queue")
    parser.add_argument("--db", default="images.db", help="Database path")
    parser.add_argument("--batch-size", type=int, default=10, help="Batch size")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be processed without actually processing")
    
    args = parser.parse_args()
    
    try:
        ocr_assessor = OCRQualityAssessment(args.db)
        
        if args.dry_run:
            print("DRY RUN - Showing items that would be processed:")
            print("=" * 50)
            
            # Get queue items without processing
            queue_items = ocr_assessor.get_reprocessing_queue("queued")
            
            if not queue_items:
                print("No items in reprocessing queue")
                return
            
            for item in queue_items:
                print(f"Image ID: {item['image_id']}")
                print(f"Reason: {item['reprocess_reason']}")
                print(f"Priority: {item['priority']}")
                print(f"Created: {item['created_at']}")
                print("-" * 30)
        else:
            print("Processing OCR reprocessing queue...")
            print("=" * 50)
            ocr_assessor.process_reprocessing_queue(args.batch_size)
            print("Reprocessing queue processing completed!")
            
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
