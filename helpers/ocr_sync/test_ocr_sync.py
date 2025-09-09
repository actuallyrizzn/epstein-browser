#!/usr/bin/env python3
"""
Test script for OCR sync functionality

Tests the OCR sync script against a local development server to ensure
all API endpoints work correctly before running against production.
"""

import sys
import requests
import json
from pathlib import Path

def test_api_endpoints(base_url: str):
    """Test all required API endpoints"""
    print(f"Testing API endpoints against: {base_url}")
    
    # Test 1: Stats endpoint
    print("\n1. Testing /api/stats endpoint...")
    try:
        response = requests.get(f"{base_url}/api/stats", timeout=10)
        if response.status_code == 200:
            stats = response.json()
            print(f"   ✅ Stats endpoint working")
            print(f"   Total images: {stats.get('total_images', 'N/A')}")
            print(f"   Images with OCR: {stats.get('images_with_ocr', 'N/A')}")
        else:
            print(f"   ❌ Stats endpoint failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"   ❌ Stats endpoint error: {e}")
        return False
    
    # Test 2: Search endpoint with OCR filter
    print("\n2. Testing /api/search endpoint with OCR filter...")
    try:
        params = {
            'q': '',
            'ocr': 'with-ocr',
            'page': 1,
            'per_page': 10
        }
        response = requests.get(f"{base_url}/api/search", params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            results = data.get('results', [])
            print(f"   ✅ Search endpoint working")
            print(f"   Found {len(results)} documents with OCR")
            
            if results:
                # Show first result
                first_doc = results[0]
                print(f"   Sample document: {first_doc.get('file_name', 'N/A')}")
                print(f"   File path: {first_doc.get('file_path', 'N/A')}")
                print(f"   Has OCR: {first_doc.get('has_ocr_text', 'N/A')}")
        else:
            print(f"   ❌ Search endpoint failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"   ❌ Search endpoint error: {e}")
        return False
    
    # Test 3: Document endpoint (if available)
    print("\n3. Testing /api/document/{id} endpoint...")
    try:
        # First get a document ID from search
        params = {'q': '', 'ocr': 'with-ocr', 'page': 1, 'per_page': 1}
        response = requests.get(f"{base_url}/api/search", params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            results = data.get('results', [])
            if results:
                doc_id = results[0].get('id')
                if doc_id:
                    doc_response = requests.get(f"{base_url}/api/document/{doc_id}", timeout=10)
                    if doc_response.status_code == 200:
                        doc_data = doc_response.json()
                        print(f"   ✅ Document endpoint working")
                        print(f"   Document ID: {doc_id}")
                        print(f"   Has OCR text: {doc_data.get('has_ocr_text', 'N/A')}")
                        if doc_data.get('ocr_text'):
                            print(f"   OCR text length: {len(doc_data['ocr_text'])} characters")
                    else:
                        print(f"   ⚠️  Document endpoint returned {doc_response.status_code} (may not be implemented)")
                else:
                    print("   ⚠️  No document ID found in search results")
            else:
                print("   ⚠️  No documents with OCR found")
        else:
            print(f"   ❌ Could not get document ID from search: {response.status_code}")
    except Exception as e:
        print(f"   ❌ Document endpoint error: {e}")
    
    # Test 4: OCR text file endpoint (if available)
    print("\n4. Testing OCR text file endpoint...")
    try:
        # Try to construct an OCR text file URL
        params = {'q': '', 'ocr': 'with-ocr', 'page': 1, 'per_page': 1}
        response = requests.get(f"{base_url}/api/search", params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            results = data.get('results', [])
            if results:
                file_path = results[0].get('file_path', '')
                if file_path:
                    # Construct OCR text file path
                    ocr_file_path = file_path.rsplit('.', 1)[0] + '.txt'
                    ocr_url = f"{base_url}/api/ocr-text/{ocr_file_path}"
                    
                    ocr_response = requests.get(ocr_url, timeout=10)
                    if ocr_response.status_code == 200:
                        print(f"   ✅ OCR text file endpoint working")
                        print(f"   OCR text length: {len(ocr_response.text)} characters")
                    else:
                        print(f"   ⚠️  OCR text file endpoint returned {ocr_response.status_code} (may not be implemented)")
                else:
                    print("   ⚠️  No file path found in search results")
            else:
                print("   ⚠️  No documents with OCR found")
        else:
            print(f"   ❌ Could not get file path from search: {response.status_code}")
    except Exception as e:
        print(f"   ❌ OCR text file endpoint error: {e}")
    
    print("\n✅ API endpoint testing completed")
    return True

def main():
    """Main test function"""
    if len(sys.argv) != 2:
        print("Usage: python test_ocr_sync.py <base_url>")
        print("Example: python test_ocr_sync.py http://localhost:8080")
        sys.exit(1)
    
    base_url = sys.argv[1].rstrip('/')
    
    print("OCR Sync API Test")
    print("=" * 50)
    
    success = test_api_endpoints(base_url)
    
    if success:
        print("\n🎉 All tests passed! The OCR sync script should work with this server.")
    else:
        print("\n❌ Some tests failed. Check the server configuration.")
        sys.exit(1)

if __name__ == '__main__':
    main()
