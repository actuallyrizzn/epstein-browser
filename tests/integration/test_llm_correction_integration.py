"""
Integration tests for LLM Correction features

Tests the integration between app.py, OCR quality assessment, and the viewer.
"""

import pytest
import sqlite3
import tempfile
import os
import json
from unittest.mock import Mock, patch, MagicMock
import sys

# Add project root to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from app import app


class TestLLMCorrectionIntegration:
    """Integration tests for LLM correction features"""
    
    def setup_method(self):
        """Set up test fixtures"""
        # Create temporary database
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        self.db_path = self.temp_db.name
        
        # Create test database with required tables
        self._create_test_database()
        
        # Set up Flask app for testing
        app.config['TESTING'] = True
        app.config['DATABASE_PATH'] = self.db_path
        self.client = app.test_client()
    
    def teardown_method(self):
        """Clean up test fixtures"""
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)
    
    def _create_test_database(self):
        """Create test database with required schema"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create images table
        cursor.execute("""
            CREATE TABLE images (
                id INTEGER PRIMARY KEY,
                file_path TEXT,
                file_name TEXT,
                has_ocr_text BOOLEAN DEFAULT FALSE,
                has_corrected_text BOOLEAN DEFAULT FALSE,
                correction_confidence INTEGER DEFAULT NULL,
                correction_status TEXT DEFAULT 'none',
                ocr_quality_score INTEGER DEFAULT NULL,
                ocr_quality_status TEXT DEFAULT 'pending',
                reprocess_priority INTEGER DEFAULT 0
            )
        """)
        
        # Create ocr_corrections table
        cursor.execute("""
            CREATE TABLE ocr_corrections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                image_id INTEGER NOT NULL,
                original_text TEXT NOT NULL,
                corrected_text TEXT NOT NULL,
                quality_score INTEGER,
                improvement_level TEXT,
                major_corrections TEXT,
                confidence TEXT,
                needs_review BOOLEAN DEFAULT FALSE,
                assessment_json TEXT,
                llm_model TEXT NOT NULL,
                llm_version TEXT,
                api_cost_usd REAL DEFAULT 0.0,
                processing_time_ms INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (image_id) REFERENCES images (id) ON DELETE CASCADE
            )
        """)
        
        # Insert test data
        cursor.execute("""
            INSERT INTO images (id, file_path, file_name, has_ocr_text, has_corrected_text, correction_confidence)
            VALUES (1, 'test1.jpg', 'test1.jpg', TRUE, FALSE, NULL),
                   (2, 'test2.jpg', 'test2.jpg', TRUE, TRUE, 85),
                   (3, 'test3.jpg', 'test3.jpg', FALSE, FALSE, NULL)
        """)
        
        # Insert test correction
        cursor.execute("""
            INSERT INTO ocr_corrections (image_id, original_text, corrected_text, quality_score, 
                                       improvement_level, major_corrections, confidence, needs_review,
                                       assessment_json, llm_model, processing_time_ms)
            VALUES (2, 'Original OCR text', 'Corrected legal document text', 85, 
                   'significant', '["fixed spacing", "corrected proper names"]', 'high', FALSE,
                   '{"quality_score": 85, "confidence": "high"}', 'llama-3.3-70b', 1500)
        """)
        
        conn.commit()
        conn.close()
    
    def test_view_image_without_correction(self):
        """Test viewing image without correction"""
        with patch('app.get_image_by_id', return_value={
            'id': 1, 'file_path': 'test1.jpg', 'file_name': 'test1.jpg',
            'has_ocr_text': True, 'has_corrected_text': False
        }):
            with patch('app.get_total_images', return_value=3):
                with patch('app.get_db_connection') as mock_conn:
                    mock_cursor = Mock()
                    mock_cursor.execute.return_value.fetchall.return_value = [
                        (1, 'test1.jpg'), (2, 'test2.jpg'), (3, 'test3.jpg')
                    ]
                    mock_conn.return_value.execute.return_value = mock_cursor
                    mock_conn.return_value.close = Mock()
                    
                    with patch('app.get_ocr_text', return_value="Original OCR text"):
                        with patch('app.render_template') as mock_render:
                            mock_render.return_value = "Rendered template"
                            response = self.client.get('/view/1')
                            assert response.status_code == 200
                            # Verify render_template was called with correct variables
                            mock_render.assert_called_once()
                            call_args = mock_render.call_args[1]
                            assert call_args['ocr_text'] == 'Original OCR text'
                            assert call_args['ocr_corrected_text'] is None
    
    def test_view_image_with_correction(self):
        """Test viewing image with correction"""
        with patch('app.get_image_by_id', return_value={
            'id': 2, 'file_path': 'test2.jpg', 'file_name': 'test2.jpg',
            'has_ocr_text': True, 'has_corrected_text': True
        }):
            with patch('app.get_total_images', return_value=3):
                with patch('app.get_db_connection') as mock_conn:
                    mock_cursor = Mock()
                    mock_cursor.execute.return_value.fetchall.return_value = [
                        (1, 'test1.jpg'), (2, 'test2.jpg'), (3, 'test3.jpg')
                    ]
                    mock_conn.return_value.execute.return_value = mock_cursor
                    mock_conn.return_value.close = Mock()
                    
                    with patch('app.get_ocr_text', return_value="Original OCR text"):
                        with patch('helpers.ocr_quality_assessment.OCRQualityAssessment') as mock_assessor_class:
                            mock_assessor = Mock()
                            mock_assessor.get_correction.return_value = {
                                'corrected_text': 'Corrected legal document text',
                                'quality_score': 85,
                                'confidence': 'high'
                            }
                            mock_assessor_class.return_value = mock_assessor
                            
                            response = self.client.get('/view/2')
                            assert response.status_code == 200
                            assert b'Corrected legal document text' in response.data
                            assert b'confidence-badge' in response.data
                            assert b'85' in response.data  # Quality score
                            assert b'View Original' in response.data
    
    def test_view_image_correction_error(self):
        """Test viewing image with correction error"""
        with patch('app.get_image_by_id', return_value={
            'id': 2, 'file_path': 'test2.jpg', 'file_name': 'test2.jpg',
            'has_ocr_text': True, 'has_corrected_text': True
        }):
            with patch('app.get_total_images', return_value=3):
                with patch('app.get_db_connection') as mock_conn:
                    mock_cursor = Mock()
                    mock_cursor.execute.return_value.fetchall.return_value = [
                        (1, 'test1.jpg'), (2, 'test2.jpg'), (3, 'test3.jpg')
                    ]
                    mock_conn.return_value.execute.return_value = mock_cursor
                    mock_conn.return_value.close = Mock()
                    
                    with patch('app.get_ocr_text', return_value="Original OCR text"):
                        with patch('helpers.ocr_quality_assessment.OCRQualityAssessment', side_effect=Exception("OCR assessor error")):
                            with patch('builtins.print') as mock_print:
                                response = self.client.get('/view/2')
                                assert response.status_code == 200
                                assert b'Original OCR text' in response.data  # Fallback to original
                                mock_print.assert_called_with("Error loading correction for image 2: OCR assessor error")
    
    def test_view_image_correction_not_found(self):
        """Test viewing image with correction not found"""
        with patch('app.get_image_by_id', return_value={
            'id': 2, 'file_path': 'test2.jpg', 'file_name': 'test2.jpg',
            'has_ocr_text': True, 'has_corrected_text': True
        }):
            with patch('app.get_total_images', return_value=3):
                with patch('app.get_db_connection') as mock_conn:
                    mock_cursor = Mock()
                    mock_cursor.execute.return_value.fetchall.return_value = [
                        (1, 'test1.jpg'), (2, 'test2.jpg'), (3, 'test3.jpg')
                    ]
                    mock_conn.return_value.execute.return_value = mock_cursor
                    mock_conn.return_value.close = Mock()
                    
                    with patch('app.get_ocr_text', return_value="Original OCR text"):
                        with patch('helpers.ocr_quality_assessment.OCRQualityAssessment') as mock_assessor_class:
                            mock_assessor = Mock()
                            mock_assessor.get_correction.return_value = None  # No correction found
                            mock_assessor_class.return_value = mock_assessor
                            
                            response = self.client.get('/view/2')
                            assert response.status_code == 200
                            assert b'Original OCR text' in response.data  # Fallback to original
                            assert b'confidence-badge' not in response.data
    
    def test_view_image_no_ocr_text(self):
        """Test viewing image without OCR text"""
        with patch('app.get_image_by_id', return_value={
            'id': 3, 'file_path': 'test3.jpg', 'file_name': 'test3.jpg',
            'has_ocr_text': False, 'has_corrected_text': False
        }):
            with patch('app.get_total_images', return_value=3):
                with patch('app.get_db_connection') as mock_conn:
                    mock_cursor = Mock()
                    mock_cursor.execute.return_value.fetchall.return_value = [
                        (1, 'test1.jpg'), (2, 'test2.jpg'), (3, 'test3.jpg')
                    ]
                    mock_conn.return_value.execute.return_value = mock_cursor
                    mock_conn.return_value.close = Mock()
                    
                    response = self.client.get('/view/3')
                    assert response.status_code == 200
                    assert b'OCR processing pending' in response.data
    
    def test_view_image_template_variables(self):
        """Test that all template variables are passed correctly"""
        with patch('app.get_image_by_id', return_value={
            'id': 2, 'file_path': 'test2.jpg', 'file_name': 'test2.jpg',
            'has_ocr_text': True, 'has_corrected_text': True
        }):
            with patch('app.get_total_images', return_value=3):
                with patch('app.get_db_connection') as mock_conn:
                    mock_cursor = Mock()
                    mock_cursor.execute.return_value.fetchall.return_value = [
                        (1, 'test1.jpg'), (2, 'test2.jpg'), (3, 'test3.jpg')
                    ]
                    mock_conn.return_value.execute.return_value = mock_cursor
                    mock_conn.return_value.close = Mock()
                    
                    with patch('app.get_ocr_text', return_value="Original OCR text"):
                        with patch('helpers.ocr_quality_assessment.OCRQualityAssessment') as mock_assessor_class:
                            mock_assessor = Mock()
                            mock_assessor.get_correction.return_value = {
                                'corrected_text': 'Corrected legal document text',
                                'quality_score': 85,
                                'confidence': 'high'
                            }
                            mock_assessor_class.return_value = mock_assessor
                            
                            with patch('app.render_template') as mock_render:
                                mock_render.return_value = "Rendered template"
                                response = self.client.get('/view/2')
                                
                                # Verify render_template was called with correct variables
                                mock_render.assert_called_once()
                                call_args = mock_render.call_args[1]
                                
                                assert call_args['ocr_text'] == 'Corrected legal document text'
                                assert call_args['ocr_original_text'] == 'Original OCR text'
                                assert call_args['ocr_corrected_text'] == 'Corrected legal document text'
                                assert call_args['correction_confidence'] == 85
                                assert call_args['correction_status'] == 'high'
    
    def test_view_image_progress_calculation(self):
        """Test progress calculation in viewer"""
        with patch('app.get_image_by_id', return_value={
            'id': 2, 'file_path': 'test2.jpg', 'file_name': 'test2.jpg',
            'has_ocr_text': True, 'has_corrected_text': False
        }):
            with patch('app.get_total_images', return_value=3):
                with patch('app.get_db_connection') as mock_conn:
                    mock_cursor = Mock()
                    mock_cursor.execute.return_value.fetchall.return_value = [
                        (1, 'test1.jpg'), (2, 'test2.jpg'), (3, 'test3.jpg')
                    ]
                    mock_conn.return_value.execute.return_value = mock_cursor
                    mock_conn.return_value.close = Mock()
                    
                    with patch('app.get_ocr_text', return_value="Original OCR text"):
                        with patch('app.render_template') as mock_render:
                            mock_render.return_value = "Rendered template"
                            response = self.client.get('/view/2')
                            
                            # Verify progress calculation (image 2 is at position 1 out of 3, so 50%)
                            call_args = mock_render.call_args[1]
                            assert call_args['progress_percent'] == 50.0
    
    def test_view_image_single_image(self):
        """Test progress calculation with single image"""
        with patch('app.get_image_by_id', return_value={
            'id': 1, 'file_path': 'test1.jpg', 'file_name': 'test1.jpg',
            'has_ocr_text': True, 'has_corrected_text': False
        }):
            with patch('app.get_total_images', return_value=1):
                with patch('app.get_db_connection') as mock_conn:
                    mock_cursor = Mock()
                    mock_cursor.execute.return_value.fetchall.return_value = [
                        (1, 'test1.jpg')
                    ]
                    mock_conn.return_value.execute.return_value = mock_cursor
                    mock_conn.return_value.close = Mock()
                    
                    with patch('app.get_ocr_text', return_value="Original OCR text"):
                        with patch('app.render_template') as mock_render:
                            mock_render.return_value = "Rendered template"
                            response = self.client.get('/view/1')
                            
                            # Single image should have 100% progress
                            call_args = mock_render.call_args[1]
                            assert call_args['progress_percent'] == 100.0
    
    def test_view_image_not_found(self):
        """Test viewing non-existent image"""
        with patch('app.get_image_by_id', return_value=None):
            response = self.client.get('/view/999')
            assert response.status_code == 404
    
    def test_view_image_database_error(self):
        """Test viewing image with database error"""
        with patch('app.get_image_by_id', side_effect=Exception("Database error")):
            response = self.client.get('/view/1')
            assert response.status_code == 500
