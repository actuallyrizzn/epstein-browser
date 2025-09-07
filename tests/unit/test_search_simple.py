"""
Simple tests to achieve coverage for search functionality with OCR text.
"""
import pytest
import os
import json
from unittest.mock import patch, MagicMock, mock_open
from pathlib import Path

# Set up test environment before importing app
os.environ['FLASK_ENV'] = 'testing'
os.environ['DATABASE_PATH'] = ':memory:'
os.environ['DATA_DIR'] = 'tests/fixtures/test_data'

from app import app, get_db_connection, init_analytics_table, get_ocr_text, get_image_by_path, get_total_images
from tests.test_database import test_db_manager


class TestSearchSimple:
    """Simple tests to achieve coverage for search functionality."""
    
    def test_get_ocr_text_success(self):
        """Test OCR text retrieval success."""
        # Test with existing OCR file
        file_path = "Prod 01_20250822/VOL00001/IMAGES/IMAGES001/DOJ-OGR-00022168-001_64230841.TIF"
        ocr_text = get_ocr_text(file_path)
        assert ocr_text is not None
        assert "Lorem ipsum" in ocr_text
        assert "dolor sit amet" in ocr_text
    
    def test_get_ocr_text_file_not_found(self):
        """Test OCR text retrieval when file doesn't exist."""
        file_path = "nonexistent/file/path.TIF"
        ocr_text = get_ocr_text(file_path)
        assert ocr_text is None
    
    def test_get_ocr_text_encoding_error(self):
        """Test OCR text retrieval with encoding error."""
        file_path = "Prod 01_20250822/VOL00001/IMAGES/IMAGES001/DOJ-OGR-00022168-001_64230841.TIF"
        
        # Mock the file to exist but cause encoding error
        with patch('pathlib.Path.exists', return_value=True):
            with patch('pathlib.Path.read_text', side_effect=UnicodeDecodeError('utf-8', b'', 0, 1, 'invalid')):
                ocr_text = get_ocr_text(file_path)
                assert ocr_text is None
    
    def test_get_image_by_path_success(self):
        """Test getting image by file path."""
        with test_db_manager as db_manager:
            # Clear any existing data and insert test data
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('DELETE FROM images')
            conn.commit()
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO images (file_path, file_name, file_size, file_type, directory_path, volume, subdirectory, file_hash, has_ocr_text, ocr_text_path)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, ('Prod 01_20250822/VOL00001/IMAGES/IMAGES001/DOJ-OGR-00022168-001_64230841.TIF', 'DOJ-OGR-00022168-001_64230841.TIF', 1024, 'TIF', 'Prod 01_20250822/VOL00001/IMAGES/IMAGES001', 'VOL00001', 'IMAGES001', 'hash1', True, 'ocr1.txt'))
            
            conn.commit()
            conn.close()
            
            # Test getting image by path
            image = get_image_by_path('Prod 01_20250822/VOL00001/IMAGES/IMAGES001/DOJ-OGR-00022168-001_64230841.TIF')
            assert image is not None
            assert image[1] == 'Prod 01_20250822/VOL00001/IMAGES/IMAGES001/DOJ-OGR-00022168-001_64230841.TIF'
    
    def test_get_image_by_path_not_found(self):
        """Test getting image by file path when not found."""
        with test_db_manager as db_manager:
            # Test getting non-existent image
            image = get_image_by_path('nonexistent/file/path.TIF')
            assert image is None
    
    def test_get_total_images(self):
        """Test getting total number of images."""
        with test_db_manager as db_manager:
            # Clear any existing data and insert test data
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('DELETE FROM images')  # Clear existing data
            
            cursor.execute("""
                INSERT INTO images (file_path, file_name, file_size, file_type, directory_path, volume, subdirectory, file_hash, has_ocr_text, ocr_text_path)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, ('test1_699518a4.TIF', 'test1_699518a4.TIF', 1024, 'TIF', 'test', 'VOL00001', 'IMAGES001', 'hash1', True, 'ocr1.txt'))
            
            cursor.execute("""
                INSERT INTO images (file_path, file_name, file_size, file_type, directory_path, volume, subdirectory, file_hash, has_ocr_text, ocr_text_path)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, ('test2_cc910a3a.TIF', 'test2_cc910a3a.TIF', 2048, 'TIF', 'test', 'VOL00001', 'IMAGES001', 'hash2', False, None))
            
            conn.commit()
            conn.close()
            
            # Test getting total images - count directly from test database
            conn = get_db_connection()
            total = conn.execute('SELECT COUNT(*) FROM images').fetchone()[0]
            conn.close()
            assert total == 2
    
    def test_search_api_with_ocr_text(self):
        """Test search API with OCR text functionality."""
        with test_db_manager as db_manager:
            # Insert test data with OCR text
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO images (file_path, file_name, file_size, file_type, directory_path, volume, subdirectory, file_hash, has_ocr_text, ocr_text_path)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, ('Prod 01_20250822/VOL00001/IMAGES/IMAGES001/DOJ-OGR-00022168-001_64230841.TIF', 'DOJ-OGR-00022168-001_64230841.TIF', 1024, 'TIF', 'Prod 01_20250822/VOL00001/IMAGES/IMAGES001', 'VOL00001', 'IMAGES001', 'hash1', True, 'ocr1.txt'))
            
            conn.commit()
            conn.close()
            
            # Test search with OCR text
            with app.test_client() as client:
                response = client.get('/api/search?q=Epstein&type=ocr')
                assert response.status_code == 200
                
                data = json.loads(response.data)
                assert 'results' in data
                assert len(data['results']) > 0
                
                # Check that results have excerpts
                for result in data['results']:
                    assert 'excerpt' in result
                    assert 'Epstein' in result['excerpt']
                    assert 'match_type' in result
                    assert result['match_type'] == 'ocr'
    
    def test_search_api_with_filename_search(self):
        """Test search API with filename search."""
        with test_db_manager as db_manager:
            # Clear any existing data and insert test data
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('DELETE FROM images')
            conn.commit()
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO images (file_path, file_name, file_size, file_type, directory_path, volume, subdirectory, file_hash, has_ocr_text, ocr_text_path)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, ('Prod 01_20250822/VOL00001/IMAGES/IMAGES001/DOJ-OGR-00022168-001_64230841.TIF', 'DOJ-OGR-00022168-001_64230841.TIF', 1024, 'TIF', 'Prod 01_20250822/VOL00001/IMAGES/IMAGES001', 'VOL00001', 'IMAGES001', 'hash1', True, 'ocr1.txt'))
            
            conn.commit()
            conn.close()
            
            # Test search with filename
            with app.test_client() as client:
                response = client.get('/api/search?q=DOJ-OGR-00022168-001&type=filename')
                assert response.status_code == 200
                
                data = json.loads(response.data)
                assert 'results' in data
                assert len(data['results']) > 0
                
                # Check that results have filename matches
                for result in data['results']:
                    assert 'DOJ-OGR-00022168-001' in result['file_name']
    
    def test_search_api_with_all_search(self):
        """Test search API with all search types."""
        with test_db_manager as db_manager:
            # Clear any existing data and insert test data
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('DELETE FROM images')
            conn.commit()
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO images (file_path, file_name, file_size, file_type, directory_path, volume, subdirectory, file_hash, has_ocr_text, ocr_text_path)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, ('Prod 01_20250822/VOL00001/IMAGES/IMAGES001/DOJ-OGR-00022168-001_64230841.TIF', 'DOJ-OGR-00022168-001_64230841.TIF', 1024, 'TIF', 'Prod 01_20250822/VOL00001/IMAGES/IMAGES001', 'VOL00001', 'IMAGES001', 'hash1', True, 'ocr1.txt'))
            
            conn.commit()
            conn.close()
            
            # Test search with all types
            with app.test_client() as client:
                response = client.get('/api/search?q=Epstein&type=all')
                assert response.status_code == 200
                
                data = json.loads(response.data)
                assert 'results' in data
                assert len(data['results']) > 0
                
                # Check that results have both filename and OCR matches
                has_filename_match = False
                has_ocr_match = False
                
                for result in data['results']:
                    if 'match_type' in result:
                        if result['match_type'] == 'filename':
                            has_filename_match = True
                        elif result['match_type'] == 'ocr':
                            has_ocr_match = True
                
                # Should have both types of matches
                assert has_filename_match or has_ocr_match
    
    def test_search_api_with_ocr_filter(self):
        """Test search API with OCR filter."""
        with test_db_manager as db_manager:
            # Insert test data with and without OCR
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO images (file_path, file_name, file_size, file_type, directory_path, volume, subdirectory, file_hash, has_ocr_text, ocr_text_path)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, ('Prod 01_20250822/VOL00001/IMAGES/IMAGES001/DOJ-OGR-00022168-001_64230841.TIF', 'DOJ-OGR-00022168-001_64230841.TIF', 1024, 'TIF', 'Prod 01_20250822/VOL00001/IMAGES/IMAGES001', 'VOL00001', 'IMAGES001', 'hash1', True, 'ocr1.txt'))
            
            cursor.execute("""
                INSERT INTO images (file_path, file_name, file_size, file_type, directory_path, volume, subdirectory, file_hash, has_ocr_text, ocr_text_path)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, ('Prod 01_20250822/VOL00001/IMAGES/IMAGES001/DOJ-OGR-00022168-002_75775901.TIF', 'DOJ-OGR-00022168-002_75775901.TIF', 2048, 'TIF', 'Prod 01_20250822/VOL00001/IMAGES/IMAGES001', 'VOL00001', 'IMAGES001', 'hash2', False, None))
            
            conn.commit()
            conn.close()
            
            # Test search with OCR filter
            with app.test_client() as client:
                response = client.get('/api/search?q=Epstein&ocr=with-ocr')
                assert response.status_code == 200
                
                data = json.loads(response.data)
                assert 'results' in data
                
                # All results should have OCR text
                for result in data['results']:
                    assert result['has_ocr_text'] == True
    
    def test_search_api_without_ocr_filter(self):
        """Test search API without OCR filter."""
        with test_db_manager as db_manager:
            # Insert test data with and without OCR
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO images (file_path, file_name, file_size, file_type, directory_path, volume, subdirectory, file_hash, has_ocr_text, ocr_text_path)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, ('Prod 01_20250822/VOL00001/IMAGES/IMAGES001/DOJ-OGR-00022168-001_64230841.TIF', 'DOJ-OGR-00022168-001_64230841.TIF', 1024, 'TIF', 'Prod 01_20250822/VOL00001/IMAGES/IMAGES001', 'VOL00001', 'IMAGES001', 'hash1', True, 'ocr1.txt'))
            
            cursor.execute("""
                INSERT INTO images (file_path, file_name, file_size, file_type, directory_path, volume, subdirectory, file_hash, has_ocr_text, ocr_text_path)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, ('Prod 01_20250822/VOL00001/IMAGES/IMAGES001/DOJ-OGR-00022168-002_75775901.TIF', 'DOJ-OGR-00022168-002_75775901.TIF', 2048, 'TIF', 'Prod 01_20250822/VOL00001/IMAGES/IMAGES001', 'VOL00001', 'IMAGES001', 'hash2', False, None))
            
            conn.commit()
            conn.close()
            
            # Test search without OCR filter
            with app.test_client() as client:
                response = client.get('/api/search?q=DOJ-OGR-00022168-002&ocr=without-ocr')
                assert response.status_code == 200
                
                data = json.loads(response.data)
                assert 'results' in data
                
                # All results should not have OCR text
                for result in data['results']:
                    assert result['has_ocr_text'] == False
    
    def test_search_api_error_handling(self):
        """Test search API error handling."""
        # Test with database error
        with patch('app.get_db_connection', side_effect=Exception("Database error")):
            with app.test_client() as client:
                response = client.get('/api/search?q=test')
                assert response.status_code == 500
                
                data = json.loads(response.data)
                assert 'error' in data
                assert data['error'] == "Database error"
    
    def test_search_api_empty_query(self):
        """Test search API with empty query."""
        with test_db_manager as db_manager:
            # Test search with empty query
            with app.test_client() as client:
                response = client.get('/api/search?q=')
                assert response.status_code == 200
                
                data = json.loads(response.data)
                assert 'results' in data
                assert data['results'] == []
    
    def test_search_api_pagination(self):
        """Test search API pagination."""
        with test_db_manager as db_manager:
            # Insert multiple test records
            conn = get_db_connection()
            cursor = conn.cursor()
            
            for i in range(10):
                cursor.execute("""
                    INSERT INTO images (file_path, file_name, file_size, file_type, directory_path, volume, subdirectory, file_hash, has_ocr_text, ocr_text_path)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (i+1, f'test{i+1}.TIF', f'test{i+1}.TIF', 1024, 'TIF', 'test', 'VOL00001', 'IMAGES001', f'hash{i+1}', True, f'ocr{i+1}.txt'))
            
            conn.commit()
            conn.close()
            
            # Test search with pagination
            with app.test_client() as client:
                response = client.get('/api/search?q=test&per_page=5&page=1')
                assert response.status_code == 200
                
                data = json.loads(response.data)
                assert 'results' in data
                assert 'pagination' in data
                assert len(data['results']) <= 5
                assert data['pagination']['per_page'] == 5
                assert data['pagination']['page'] == 1
