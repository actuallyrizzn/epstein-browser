#!/usr/bin/env python3
"""
Comprehensive test script for the view endpoint to identify the 500 error
"""

import sys
import os
import traceback
import sqlite3
from pathlib import Path

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_database_connection():
    """Test database connection and basic queries"""
    print("=== Testing Database Connection ===")
    
    try:
        conn = sqlite3.connect('images.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Test basic connection
        cursor.execute("SELECT COUNT(*) FROM images")
        count = cursor.fetchone()[0]
        print(f"✓ Database connected. Total images: {count}")
        
        # Test if image ID 1 exists
        cursor.execute("SELECT * FROM images WHERE id = ?", (1,))
        image = cursor.fetchone()
        
        if not image:
            print("❌ No image found with ID 1")
            return False, None
        
        print(f"✓ Image ID 1 found: {image['file_name']}")
        
        # Test all columns that the view function accesses
        required_columns = ['id', 'file_name', 'file_path', 'has_ocr_text']
        for col in required_columns:
            try:
                value = image[col]
                print(f"✓ Column '{col}': {value}")
            except KeyError as e:
                print(f"❌ Missing column '{col}': {e}")
                return False, None
        
        # Test optional columns
        optional_columns = ['has_corrected_text', 'ocr_quality_score', 'ocr_rescan_attempts']
        for col in optional_columns:
            try:
                value = image.get(col, 'NOT_FOUND')
                print(f"✓ Optional column '{col}': {value}")
            except Exception as e:
                print(f"⚠ Error accessing optional column '{col}': {e}")
        
        conn.close()
        return True, image
        
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        traceback.print_exc()
        return False, None

def test_view_function_components():
    """Test the individual components of the view function"""
    print("\n=== Testing View Function Components ===")
    
    try:
        # Import the app module
        from app import get_image_by_id, get_total_images, get_ocr_text
        
        # Test get_image_by_id
        print("Testing get_image_by_id...")
        image = get_image_by_id(1)
        if not image:
            print("❌ get_image_by_id returned None")
            return False
        print(f"✓ get_image_by_id works: {image['file_name']}")
        
        # Test get_total_images
        print("Testing get_total_images...")
        total = get_total_images()
        print(f"✓ get_total_images works: {total}")
        
        # Test get_ocr_text
        print("Testing get_ocr_text...")
        if image['has_ocr_text']:
            ocr_text = get_ocr_text(image['file_path'])
            print(f"✓ get_ocr_text works: {len(ocr_text) if ocr_text else 0} characters")
        else:
            print("✓ Image has no OCR text (expected)")
        
        return True
        
    except Exception as e:
        print(f"❌ View function components test failed: {e}")
        traceback.print_exc()
        return False

def test_ocr_quality_assessment():
    """Test OCR quality assessment import and usage"""
    print("\n=== Testing OCR Quality Assessment ===")
    
    try:
        from helpers.ocr_quality_assessment import OCRQualityAssessment
        print("✓ OCRQualityAssessment import successful")
        
        # Test instantiation
        ocr_assessor = OCRQualityAssessment('images.db')
        print("✓ OCRQualityAssessment instantiation successful")
        
        # Test get_correction method
        correction = ocr_assessor.get_correction(1)
        print(f"✓ get_correction method works: {correction is not None}")
        
        return True
        
    except Exception as e:
        print(f"❌ OCR Quality Assessment test failed: {e}")
        traceback.print_exc()
        return False

def test_view_endpoint_simulation():
    """Simulate the complete view endpoint logic"""
    print("\n=== Simulating Complete View Endpoint ===")
    
    try:
        from app import get_image_by_id, get_total_images
        
        image_id = 1
        
        # Step 1: Get image by ID
        image = get_image_by_id(image_id)
        if not image:
            print("❌ Image not found")
            return False
        print(f"✓ Step 1: Image found - {image['file_name']}")
        
        # Step 2: Get total images
        total_images = get_total_images()
        print(f"✓ Step 2: Total images - {total_images}")
        
        # Step 3: Get all images for navigation
        import sqlite3
        conn = sqlite3.connect('images.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        all_images = cursor.execute('SELECT id, file_name FROM images ORDER BY file_name').fetchall()
        print(f"✓ Step 3: All images query - {len(all_images)} images")
        
        # Step 4: Find current position
        current_position = None
        for i, (img_id, filename) in enumerate(all_images):
            if img_id == image_id:
                current_position = i
                break
        
        if current_position is None:
            print("❌ Current position not found")
            return False
        print(f"✓ Step 4: Current position - {current_position}")
        
        # Step 5: Test OCR text handling
        if image['has_ocr_text']:
            print("✓ Step 5a: Image has OCR text")
            from app import get_ocr_text
            ocr_original_text = get_ocr_text(image['file_path'])
            print(f"✓ Step 5b: OCR text loaded - {len(ocr_original_text) if ocr_original_text else 0} chars")
            
            # Test corrected text handling
            has_corrected_text = image.get('has_corrected_text', False)
            print(f"✓ Step 5c: has_corrected_text - {has_corrected_text}")
            
            if has_corrected_text:
                from helpers.ocr_quality_assessment import OCRQualityAssessment
                ocr_assessor = OCRQualityAssessment('images.db')
                correction = ocr_assessor.get_correction(image_id)
                print(f"✓ Step 5d: Correction lookup - {correction is not None}")
        else:
            print("✓ Step 5: Image has no OCR text")
        
        # Step 6: Test document number extraction
        if image['file_name'].startswith('DOJ-OGR-'):
            try:
                number_part = image['file_name'].split('-')[2].split('.')[0]
                document_number = int(number_part)
                print(f"✓ Step 6: Document number extracted - {document_number}")
            except (ValueError, IndexError) as e:
                print(f"⚠ Step 6: Document number extraction failed - {e}")
        else:
            document_number = current_position + 1
            print(f"✓ Step 6: Document number fallback - {document_number}")
        
        conn.close()
        print("✓ All steps completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ View endpoint simulation failed: {e}")
        traceback.print_exc()
        return False

def test_flask_app_import():
    """Test if we can import the Flask app"""
    print("\n=== Testing Flask App Import ===")
    
    try:
        from app import app
        print("✓ Flask app import successful")
        
        # Test if we can get the app context
        with app.app_context():
            print("✓ Flask app context works")
        
        return True
        
    except Exception as e:
        print(f"❌ Flask app import failed: {e}")
        traceback.print_exc()
        return False

def main():
    """Run all tests"""
    print("Comprehensive View Endpoint Testing")
    print("=" * 50)
    
    tests = [
        ("Database Connection", test_database_connection),
        ("View Function Components", test_view_function_components),
        ("OCR Quality Assessment", test_ocr_quality_assessment),
        ("Flask App Import", test_flask_app_import),
        ("View Endpoint Simulation", test_view_endpoint_simulation),
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n{'='*20} {test_name} {'='*20}")
        try:
            if test_name == "Database Connection":
                success, image = test_func()
                results.append((test_name, success))
            else:
                success = test_func()
                results.append((test_name, success))
        except Exception as e:
            print(f"❌ {test_name} crashed: {e}")
            results.append((test_name, False))
    
    print("\n" + "="*50)
    print("TEST RESULTS SUMMARY")
    print("="*50)
    
    all_passed = True
    for test_name, success in results:
        status = "✓ PASS" if success else "❌ FAIL"
        print(f"{status}: {test_name}")
        if not success:
            all_passed = False
    
    if all_passed:
        print("\n🎉 All tests passed! The view endpoint should work.")
    else:
        print("\n❌ Some tests failed. Check the errors above.")
    
    return all_passed

if __name__ == "__main__":
    main()
