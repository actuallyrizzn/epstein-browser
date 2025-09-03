"""
Test script for the OCR system

Tests the TrOCR engine, progress tracker, and batch processor
with a small sample of images.
"""

import sys
from pathlib import Path
import logging

# Add src to path
sys.path.append(str(Path(__file__).parent / "src"))

from ocr_engine import TrOCREngine
from progress_tracker import ProgressTracker
from batch_processor import BatchProcessor

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_ocr_engine():
    """Test the OCR engine"""
    print("=== Testing TrOCR Engine ===")
    
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
                
                return True
            else:
                print("No test images found in data directory")
                return False
        else:
            print("Data directory not found")
            return False
            
    except Exception as e:
        print(f"OCR Engine test failed: {e}")
        return False


def test_progress_tracker():
    """Test the progress tracker"""
    print("\n=== Testing Progress Tracker ===")
    
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
        print("Progress Tracker test completed successfully")
        return True
        
    except Exception as e:
        print(f"Progress Tracker test failed: {e}")
        return False


def test_batch_processor():
    """Test the batch processor with a small sample"""
    print("\n=== Testing Batch Processor ===")
    
    try:
        # Create processor
        processor = BatchProcessor(
            data_dir="data",
            db_path="test_batch.db",
            max_workers=1,
            batch_size=5
        )
        
        # Test with a small number of files
        print("Running small batch test (max 10 files)...")
        processor.run_processing(max_files=10)
        
        # Clean up test database
        Path("test_batch.db").unlink(missing_ok=True)
        print("Batch Processor test completed successfully")
        return True
        
    except Exception as e:
        print(f"Batch Processor test failed: {e}")
        return False


def main():
    """Run all tests"""
    print("Starting OCR System Tests...")
    
    tests = [
        ("OCR Engine", test_ocr_engine),
        ("Progress Tracker", test_progress_tracker),
        ("Batch Processor", test_batch_processor)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"{test_name} test crashed: {e}")
            results.append((test_name, False))
    
    # Print summary
    print("\n=== TEST SUMMARY ===")
    for test_name, result in results:
        status = "PASS" if result else "FAIL"
        print(f"{test_name}: {status}")
    
    all_passed = all(result for _, result in results)
    print(f"\nOverall: {'ALL TESTS PASSED' if all_passed else 'SOME TESTS FAILED'}")
    
    return all_passed


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
