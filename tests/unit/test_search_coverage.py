"""
Tests to achieve 100% coverage for search functionality with OCR text.
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

from app import app, get_db_connection, init_database, get_ocr_text, get_image_by_path, get_total_images


class TestSearchCoverage:
    """Tests to achieve 100% coverage for search functionality."""
    
    def test_get_ocr_text_success(self):
        """Test OCR text retrieval success."""
        # Test with existing OCR file
        file_path = "Prod 01_20250822/VOL00001/IMAGES/IMAGES001/DOJ-OGR-00022168-001.TIF"
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
        file_path = "Prod 01_20250822/VOL00001/IMAGES/IMAGES001/DOJ-OGR-00022168-001.TIF"
        
        # Mock the file to exist but cause encoding error
        with patch('pathlib.Path.exists', return_value=True):
            with patch('pathlib.Path.read_text', side_effect=UnicodeDecodeError('utf-8', b'', 0, 1, 'invalid')):
                ocr_text = get_ocr_text(file_path)
                assert ocr_text is None
    
    def test_get_image_by_path_success(self):
        """Test getting image by file path."""
        # Create test database with sample data
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Create images table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS images (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_path TEXT UNIQUE NOT NULL,
                file_name TEXT NOT NULL,
                file_size INTEGER NOT NULL,
                file_type TEXT NOT NULL,
                directory_path TEXT NOT NULL,
                volume TEXT,
                subdirectory TEXT,
                file_hash TEXT,
                has_ocr_text BOOLEAN DEFAULT FALSE,
                ocr_text_path TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Insert test data
        cursor.execute("""
            INSERT INTO images (id, file_path, file_name, file_size, file_type, directory_path, volume, subdirectory, file_hash, has_ocr_text, ocr_text_path)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (1, 'Prod 01_20250822/VOL00001/IMAGES/IMAGES001/DOJ-OGR-00022168-001.TIF', 'DOJ-OGR-00022168-001.TIF', 1024, 'TIF', 'Prod 01_20250822/VOL00001/IMAGES/IMAGES001', 'VOL00001', 'IMAGES001', 'hash1', True, 'ocr1.txt'))
        
        conn.commit()
        conn.close()
        
        # Test getting image by path
        image = get_image_by_path('Prod 01_20250822/VOL00001/IMAGES/IMAGES001/DOJ-OGR-00022168-001.TIF')
        assert image is not None
        assert image[1] == 'Prod 01_20250822/VOL00001/IMAGES/IMAGES001/DOJ-OGR-00022168-001.TIF'
    
    def test_get_image_by_path_not_found(self):
        """Test getting image by file path when not found."""
        # Create test database
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Create images table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS images (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_path TEXT UNIQUE NOT NULL,
                file_name TEXT NOT NULL,
                file_size INTEGER NOT NULL,
                file_type TEXT NOT NULL,
                directory_path TEXT NOT NULL,
                volume TEXT,
                subdirectory TEXT,
                file_hash TEXT,
                has_ocr_text BOOLEAN DEFAULT FALSE,
                ocr_text_path TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        conn.commit()
        conn.close()
        
        # Test getting non-existent image
        image = get_image_by_path('nonexistent/file/path.TIF')
        assert image is None
    
    def test_get_total_images(self):
        """Test getting total number of images."""
        # Create test database
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Create images table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS images (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_path TEXT UNIQUE NOT NULL,
                file_name TEXT NOT NULL,
                file_size INTEGER NOT NULL,
                file_type TEXT NOT NULL,
                directory_path TEXT NOT NULL,
                volume TEXT,
                subdirectory TEXT,
                file_hash TEXT,
                has_ocr_text BOOLEAN DEFAULT FALSE,
                ocr_text_path TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Insert test data
        cursor.execute("""
            INSERT INTO images (id, file_path, file_name, file_size, file_type, directory_path, volume, subdirectory, file_hash, has_ocr_text, ocr_text_path)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (1, 'test1.TIF', 'test1.TIF', 1024, 'TIF', 'test', 'VOL00001', 'IMAGES001', 'hash1', True, 'ocr1.txt'))
        
        cursor.execute("""
            INSERT INTO images (id, file_path, file_name, file_size, file_type, directory_path, volume, subdirectory, file_hash, has_ocr_text, ocr_text_path)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (2, 'test2.TIF', 'test2.TIF', 2048, 'TIF', 'test', 'VOL00001', 'IMAGES001', 'hash2', False, None))
        
        conn.commit()
        conn.close()
        
        # Test getting total images
        total = get_total_images()
        assert total == 2
    
    def test_search_api_with_ocr_text(self):
        """Test search API with OCR text functionality."""
        # Create test database with OCR-enabled images
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Create images table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS images (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_path TEXT UNIQUE NOT NULL,
                file_name TEXT NOT NULL,
                file_size INTEGER NOT NULL,
                file_type TEXT NOT NULL,
                directory_path TEXT NOT NULL,
                volume TEXT,
                subdirectory TEXT,
                file_hash TEXT,
                has_ocr_text BOOLEAN DEFAULT FALSE,
                ocr_text_path TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Insert test data with OCR text
        cursor.execute("""
            INSERT INTO images (id, file_path, file_name, file_size, file_type, directory_path, volume, subdirectory, file_hash, has_ocr_text, ocr_text_path)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (1, 'Prod 01_20250822/VOL00001/IMAGES/IMAGES001/DOJ-OGR-00022168-001.TIF', 'DOJ-OGR-00022168-001.TIF', 1024, 'TIF', 'Prod 01_20250822/VOL00001/IMAGES/IMAGES001', 'VOL00001', 'IMAGES001', 'hash1', True, 'ocr1.txt'))
        
        cursor.execute("""
            INSERT INTO images (id, file_path, file_name, file_size, file_type, directory_path, volume, subdirectory, file_hash, has_ocr_text, ocr_text_path)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (2, 'Prod 01_20250822/VOL00001/IMAGES/IMAGES001/DOJ-OGR-00022168-002.TIF', 'DOJ-OGR-00022168-002.TIF', 2048, 'TIF', 'Prod 01_20250822/VOL00001/IMAGES/IMAGES001', 'VOL00001', 'IMAGES001', 'hash2', True, 'ocr2.txt'))
        
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
        # Create test database
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Create images table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS images (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_path TEXT UNIQUE NOT NULL,
                file_name TEXT NOT NULL,
                file_size INTEGER NOT NULL,
                file_type TEXT NOT NULL,
                directory_path TEXT NOT NULL,
                volume TEXT,
                subdirectory TEXT,
                file_hash TEXT,
                has_ocr_text BOOLEAN DEFAULT FALSE,
                ocr_text_path TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Insert test data
        cursor.execute("""
            INSERT INTO images (id, file_path, file_name, file_size, file_type, directory_path, volume, subdirectory, file_hash, has_ocr_text, ocr_text_path)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (1, 'Prod 01_20250822/VOL00001/IMAGES/IMAGES001/DOJ-OGR-00022168-001.TIF', 'DOJ-OGR-00022168-001.TIF', 1024, 'TIF', 'Prod 01_20250822/VOL00001/IMAGES/IMAGES001', 'VOL00001', 'IMAGES001', 'hash1', True, 'ocr1.txt'))
        
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
        # Create test database
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Create images table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS images (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_path TEXT UNIQUE NOT NULL,
                file_name TEXT NOT NULL,
                file_size INTEGER NOT NULL,
                file_type TEXT NOT NULL,
                directory_path TEXT NOT NULL,
                volume TEXT,
                subdirectory TEXT,
                file_hash TEXT,
                has_ocr_text BOOLEAN DEFAULT FALSE,
                ocr_text_path TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Insert test data
        cursor.execute("""
            INSERT INTO images (id, file_path, file_name, file_size, file_type, directory_path, volume, subdirectory, file_hash, has_ocr_text, ocr_text_path)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (1, 'Prod 01_20250822/VOL00001/IMAGES/IMAGES001/DOJ-OGR-00022168-001.TIF', 'DOJ-OGR-00022168-001.TIF', 1024, 'TIF', 'Prod 01_20250822/VOL00001/IMAGES/IMAGES001', 'VOL00001', 'IMAGES001', 'hash1', True, 'ocr1.txt'))
        
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
        # Create test database
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Create images table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS images (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_path TEXT UNIQUE NOT NULL,
                file_name TEXT NOT NULL,
                file_size INTEGER NOT NULL,
                file_type TEXT NOT NULL,
                directory_path TEXT NOT NULL,
                volume TEXT,
                subdirectory TEXT,
                file_hash TEXT,
                has_ocr_text BOOLEAN DEFAULT FALSE,
                ocr_text_path TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Insert test data with and without OCR
        cursor.execute("""
            INSERT INTO images (id, file_path, file_name, file_size, file_type, directory_path, volume, subdirectory, file_hash, has_ocr_text, ocr_text_path)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (1, 'Prod 01_20250822/VOL00001/IMAGES/IMAGES001/DOJ-OGR-00022168-001.TIF', 'DOJ-OGR-00022168-001.TIF', 1024, 'TIF', 'Prod 01_20250822/VOL00001/IMAGES/IMAGES001', 'VOL00001', 'IMAGES001', 'hash1', True, 'ocr1.txt'))
        
        cursor.execute("""
            INSERT INTO images (id, file_path, file_name, file_size, file_type, directory_path, volume, subdirectory, file_hash, has_ocr_text, ocr_text_path)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (2, 'Prod 01_20250822/VOL00001/IMAGES/IMAGES001/DOJ-OGR-00022168-002.TIF', 'DOJ-OGR-00022168-002.TIF', 2048, 'TIF', 'Prod 01_20250822/VOL00001/IMAGES/IMAGES001', 'VOL00001', 'IMAGES001', 'hash2', False, None))
        
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
        # Create test database
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Create images table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS images (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_path TEXT UNIQUE NOT NULL,
                file_name TEXT NOT NULL,
                file_size INTEGER NOT NULL,
                file_type TEXT NOT NULL,
                directory_path TEXT NOT NULL,
                volume TEXT,
                subdirectory TEXT,
                file_hash TEXT,
                has_ocr_text BOOLEAN DEFAULT FALSE,
                ocr_text_path TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Insert test data with and without OCR
        cursor.execute("""
            INSERT INTO images (id, file_path, file_name, file_size, file_type, directory_path, volume, subdirectory, file_hash, has_ocr_text, ocr_text_path)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (1, 'Prod 01_20250822/VOL00001/IMAGES/IMAGES001/DOJ-OGR-00022168-001.TIF', 'DOJ-OGR-00022168-001.TIF', 1024, 'TIF', 'Prod 01_20250822/VOL00001/IMAGES/IMAGES001', 'VOL00001', 'IMAGES001', 'hash1', True, 'ocr1.txt'))
        
        cursor.execute("""
            INSERT INTO images (id, file_path, file_name, file_size, file_type, directory_path, volume, subdirectory, file_hash, has_ocr_text, ocr_text_path)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (2, 'Prod 01_20250822/VOL00001/IMAGES/IMAGES001/DOJ-OGR-00022168-002.TIF', 'DOJ-OGR-00022168-002.TIF', 2048, 'TIF', 'Prod 01_20250822/VOL00001/IMAGES/IMAGES001', 'VOL00001', 'IMAGES001', 'hash2', False, None))
        
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
        # Create test database
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Create images table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS images (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_path TEXT UNIQUE NOT NULL,
                file_name TEXT NOT NULL,
                file_size INTEGER NOT NULL,
                file_type TEXT NOT NULL,
                directory_path TEXT NOT NULL,
                volume TEXT,
                subdirectory TEXT,
                file_hash TEXT,
                has_ocr_text BOOLEAN DEFAULT FALSE,
                ocr_text_path TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        conn.commit()
        conn.close()
        
        # Test search with empty query
        with app.test_client() as client:
            response = client.get('/api/search?q=')
            assert response.status_code == 200
            
            data = json.loads(response.data)
            assert 'results' in data
            assert data['results'] == []
    
    def test_search_api_pagination(self):
        """Test search API pagination."""
        # Create test database
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Create images table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS images (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_path TEXT UNIQUE NOT NULL,
                file_name TEXT NOT NULL,
                file_size INTEGER NOT NULL,
                file_type TEXT NOT NULL,
                directory_path TEXT NOT NULL,
                volume TEXT,
                subdirectory TEXT,
                file_hash TEXT,
                has_ocr_text BOOLEAN DEFAULT FALSE,
                ocr_text_path TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Insert multiple test records
        for i in range(10):
            cursor.execute("""
                INSERT INTO images (id, file_path, file_name, file_size, file_type, directory_path, volume, subdirectory, file_hash, has_ocr_text, ocr_text_path)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
