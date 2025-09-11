#!/usr/bin/env python3
"""
Debug script to test the view endpoint and identify the 500 error
"""

import sqlite3
import sys
import traceback

def test_view_image_components():
    """Test the components that make up the view_image function"""
    
    print("=== Testing View Image Components ===")
    
    try:
        # Test database connection
        conn = sqlite3.connect('images.db')
        conn.row_factory = sqlite3.Row
        print("✓ Database connection successful")
        
        # Test get_image_by_id equivalent
        cursor = conn.cursor()
        image = cursor.execute('SELECT * FROM images WHERE id = ?', (1,)).fetchone()
        
        if not image:
            print("❌ No image found with ID 1")
            return False
        
        print(f"✓ Image found: {image['file_name']}")
        
        # Test accessing image as dictionary
        try:
            has_ocr = image['has_ocr_text']
            file_name = image['file_name']
            file_path = image['file_path']
            print(f"✓ Image dictionary access works: has_ocr={has_ocr}, file_name={file_name}")
        except Exception as e:
            print(f"❌ Error accessing image as dictionary: {e}")
            return False
        
        # Test has_corrected_text access
        try:
            has_corrected = image.get('has_corrected_text')
            print(f"✓ has_corrected_text access works: {has_corrected}")
        except Exception as e:
            print(f"❌ Error accessing has_corrected_text: {e}")
            return False
        
        # Test get_total_images equivalent
        total = cursor.execute('SELECT COUNT(*) FROM images').fetchone()[0]
        print(f"✓ Total images: {total}")
        
        # Test all_images query
        all_images = cursor.execute('SELECT id, file_name FROM images ORDER BY file_name').fetchall()
        print(f"✓ All images query works: {len(all_images)} images")
        
        # Test OCR quality assessment import
        try:
            from helpers.ocr_quality_assessment import OCRQualityAssessment
            print("✓ OCRQualityAssessment import successful")
        except Exception as e:
            print(f"❌ OCRQualityAssessment import failed: {e}")
            return False
        
        # Test OCR quality assessment instantiation
        try:
            ocr_assessor = OCRQualityAssessment('images.db')
            print("✓ OCRQualityAssessment instantiation successful")
        except Exception as e:
            print(f"❌ OCRQualityAssessment instantiation failed: {e}")
            return False
        
        conn.close()
        print("✓ All tests passed!")
        return True
        
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        traceback.print_exc()
        return False

def test_view_endpoint_simulation():
    """Simulate the view endpoint to find the exact error"""
    
    print("\n=== Simulating View Endpoint ===")
    
    try:
        # Simulate the view_image function logic
        conn = sqlite3.connect('images.db')
        conn.row_factory = sqlite3.Row
        
        image_id = 1
        
        # Get image by ID
        image = conn.execute('SELECT * FROM images WHERE id = ?', (image_id,)).fetchone()
        if not image:
            print("❌ Image not found")
            return False
        
        print(f"✓ Image found: {image['file_name']}")
        
        # Get total images
        total_images = conn.execute('SELECT COUNT(*) FROM images').fetchone()[0]
        print(f"✓ Total images: {total_images}")
        
        # Get all images for navigation
        all_images = conn.execute('SELECT id, file_name FROM images ORDER BY file_name').fetchall()
        print(f"✓ All images query: {len(all_images)} images")
        
        # Find current position
        current_position = None
        for i, (img_id, filename) in enumerate(all_images):
            if img_id == image_id:
                current_position = i
                break
        
        if current_position is None:
            print("❌ Current position not found")
            return False
        
        print(f"✓ Current position: {current_position}")
        
        # Test OCR text handling
        if image['has_ocr_text']:
            print("✓ Image has OCR text")
            
            # Test get_ocr_text equivalent
            file_path = image['file_path'].replace('\\', '/')
            print(f"✓ File path processed: {file_path}")
            
            # Test has_corrected_text check
            if image.get('has_corrected_text'):
                print("✓ Image has corrected text")
                try:
                    from helpers.ocr_quality_assessment import OCRQualityAssessment
                    ocr_assessor = OCRQualityAssessment('images.db')
                    correction = ocr_assessor.get_correction(image_id)
                    print(f"✓ Correction lookup: {correction is not None}")
                except Exception as e:
                    print(f"❌ Error in correction lookup: {e}")
                    return False
            else:
                print("✓ Image does not have corrected text")
        else:
            print("✓ Image does not have OCR text")
        
        # Test document number extraction
        if image['file_name'].startswith('DOJ-OGR-'):
            try:
                number_part = image['file_name'].split('-')[2].split('.')[0]
                document_number = int(number_part)
                print(f"✓ Document number extracted: {document_number}")
            except (ValueError, IndexError) as e:
                print(f"❌ Error extracting document number: {e}")
                return False
        else:
            document_number = current_position + 1
            print(f"✓ Document number fallback: {document_number}")
        
        conn.close()
        print("✓ View endpoint simulation successful!")
        return True
        
    except Exception as e:
        print(f"❌ Error in view endpoint simulation: {e}")
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("Debugging View Endpoint 500 Error")
    print("=" * 50)
    
    success1 = test_view_image_components()
    success2 = test_view_endpoint_simulation()
    
    if success1 and success2:
        print("\n🎉 All tests passed! The issue might be elsewhere.")
    else:
        print("\n❌ Issues found that could cause 500 errors.")
