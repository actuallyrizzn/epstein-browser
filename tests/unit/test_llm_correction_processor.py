"""
Test suite for LLM Correction Processor

Tests the main processing script and batch processing functionality.
"""

import pytest
import sqlite3
import tempfile
import os
from unittest.mock import Mock, patch, MagicMock
import sys

# Add helpers to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'helpers'))

from llm_correction_processor import LLMCorrectionProcessor


class TestLLMCorrectionProcessor:
    """Test cases for LLMCorrectionProcessor"""
    
    def setup_method(self):
        """Set up test fixtures"""
        # Create temporary database
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        self.db_path = self.temp_db.name
        
        # Create test database with required tables
        self._create_test_database()
        
        # Mock the LLM client and OCR assessor
        self.mock_llm_client = Mock()
        self.mock_ocr_assessor = Mock()
        
        with patch('llm_correction_processor.LLMClient', return_value=self.mock_llm_client), \
             patch('llm_correction_processor.OCRQualityAssessment', return_value=self.mock_ocr_assessor):
            self.processor = LLMCorrectionProcessor(self.db_path, "llama-3.3-70b")
    
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
        
        # Create ocr_reprocessing_queue table
        cursor.execute("""
            CREATE TABLE ocr_reprocessing_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                image_id INTEGER NOT NULL,
                reprocess_reason TEXT NOT NULL,
                priority INTEGER DEFAULT 0,
                status TEXT DEFAULT 'queued',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                started_at TIMESTAMP,
                completed_at TIMESTAMP,
                error_message TEXT,
                FOREIGN KEY (image_id) REFERENCES images (id) ON DELETE CASCADE
            )
        """)
        
        # Insert test data
        cursor.execute("""
            INSERT INTO images (id, file_path, file_name, has_ocr_text, has_corrected_text)
            VALUES (1, 'test1.jpg', 'test1.jpg', TRUE, FALSE),
                   (2, 'test2.jpg', 'test2.jpg', TRUE, FALSE),
                   (3, 'test3.jpg', 'test3.jpg', FALSE, FALSE),
                   (4, 'test4.jpg', 'test4.jpg', TRUE, TRUE)
        """)
        
        conn.commit()
        conn.close()
    
    def test_init(self):
        """Test processor initialization"""
        assert self.processor.db_path == self.db_path
        assert self.processor.model == "llama-3.3-70b"
        assert self.processor.llm_client == self.mock_llm_client
        assert self.processor.ocr_assessor == self.mock_ocr_assessor
    
    def test_get_images_needing_correction(self):
        """Test getting images that need correction"""
        images = self.processor.get_images_needing_correction(10)
        
        # Should return images with OCR text but no corrected text
        assert len(images) == 2
        assert images[0]['id'] == 1
        assert images[1]['id'] == 2
    
    def test_get_images_needing_correction_with_limit(self):
        """Test getting images with limit"""
        images = self.processor.get_images_needing_correction(1)
        assert len(images) == 1
    
    def test_get_ocr_text_file_exists(self):
        """Test getting OCR text from existing file"""
        # Create test OCR file
        test_file = "data/test1/test1.txt"
        os.makedirs(os.path.dirname(test_file), exist_ok=True)
        with open(test_file, 'w', encoding='utf-8') as f:
            f.write("Test OCR text")
        
        try:
            result = self.processor.get_ocr_text("test1/test1.jpg")
            assert result == "Test OCR text"
        finally:
            # Clean up
            if os.path.exists(test_file):
                os.remove(test_file)
            if os.path.exists(os.path.dirname(test_file)):
                os.rmdir(os.path.dirname(test_file))
    
    def test_get_ocr_text_file_not_exists(self):
        """Test getting OCR text from non-existent file"""
        result = self.processor.get_ocr_text("nonexistent/file.jpg")
        assert result is None
    
    def test_get_ocr_text_error(self):
        """Test getting OCR text with error"""
        with patch('builtins.open', side_effect=PermissionError("Permission denied")):
            with patch('builtins.print') as mock_print:
                result = self.processor.get_ocr_text("test/file.jpg")
                assert result is None
                mock_print.assert_called_once()
    
    def test_process_image_no_ocr_text(self):
        """Test processing image with no OCR text"""
        result = self.processor.process_image({
            'id': 1,
            'file_path': 'nonexistent/file.jpg',
            'file_name': 'test.jpg'
        })
        assert result is False
    
    def test_process_image_low_quality_flagged(self):
        """Test processing image flagged for reprocessing"""
        self.mock_ocr_assessor.flag_low_quality_for_reprocessing.return_value = True
        
        with patch.object(self.processor, 'get_ocr_text', return_value="qqqq wwww eeee"):
            with patch('builtins.print') as mock_print:
                result = self.processor.process_image({
                    'id': 1,
                    'file_path': 'test1.jpg',
                    'file_name': 'test1.jpg'
                })
                assert result is False
                mock_print.assert_called_with("Low-quality OCR detected for image 1, flagged for reprocessing")
    
    def test_process_image_text_too_short(self):
        """Test processing image with text too short"""
        self.mock_ocr_assessor.flag_low_quality_for_reprocessing.return_value = False
        
        with patch.object(self.processor, 'get_ocr_text', return_value="a"):
            with patch('builtins.print') as mock_print:
                result = self.processor.process_image({
                    'id': 1,
                    'file_path': 'test1.jpg',
                    'file_name': 'test1.jpg'
                })
                assert result is False
                mock_print.assert_called_with("OCR text too short for image 1, skipping")
    
    def test_process_image_success(self):
        """Test successful image processing"""
        self.mock_ocr_assessor.flag_low_quality_for_reprocessing.return_value = False
        self.mock_ocr_assessor.correct_ocr_text.return_value = "Corrected text"
        self.mock_ocr_assessor.assess_correction_quality.return_value = {
            "quality_score": 85,
            "confidence": "high"
        }
        self.mock_ocr_assessor.validate_correction_changes.return_value = True
        self.mock_ocr_assessor.save_correction.return_value = 1
        
        with patch.object(self.processor, 'get_ocr_text', return_value="Original text"):
            with patch('time.time', side_effect=[0, 1.0]):  # Mock processing time
                with patch('builtins.print') as mock_print:
                    result = self.processor.process_image({
                        'id': 1,
                        'file_path': 'test1.jpg',
                        'file_name': 'test1.jpg'
                    })
                    assert result is True
                    assert "✓ Correction saved" in str(mock_print.call_args_list)
    
    def test_process_image_no_changes_detected(self):
        """Test processing image with no changes detected"""
        self.mock_ocr_assessor.flag_low_quality_for_reprocessing.return_value = False
        self.mock_ocr_assessor.correct_ocr_text.return_value = "Same text"
        self.mock_ocr_assessor.validate_correction_changes.return_value = False
        
        with patch.object(self.processor, 'get_ocr_text', return_value="Same text"):
            with patch('builtins.print') as mock_print:
                result = self.processor.process_image({
                    'id': 1,
                    'file_path': 'test1.jpg',
                    'file_name': 'test1.jpg'
                })
                assert result is False
                mock_print.assert_called_with("  No changes detected for image 1, skipping")
    
    def test_process_image_rate_limit_error(self):
        """Test processing image with rate limit error"""
        from helpers.llm_client import RateLimitError
        
        self.mock_ocr_assessor.flag_low_quality_for_reprocessing.return_value = False
        self.mock_ocr_assessor.correct_ocr_text.side_effect = RateLimitError("Rate limited")
        
        with patch.object(self.processor, 'get_ocr_text', return_value="Original text"):
            with patch('builtins.print') as mock_print:
                with pytest.raises(RateLimitError):
                    self.processor.process_image({
                        'id': 1,
                        'file_path': 'test1.jpg',
                        'file_name': 'test1.jpg'
                    })
    
    def test_process_image_general_error(self):
        """Test processing image with general error"""
        self.mock_ocr_assessor.flag_low_quality_for_reprocessing.return_value = False
        self.mock_ocr_assessor.correct_ocr_text.side_effect = Exception("General error")
        
        with patch.object(self.processor, 'get_ocr_text', return_value="Original text"):
            with patch('builtins.print') as mock_print:
                result = self.processor.process_image({
                    'id': 1,
                    'file_path': 'test1.jpg',
                    'file_name': 'test1.jpg'
                })
                assert result is False
                mock_print.assert_called_with("  ✗ Error processing image 1: General error")
    
    def test_process_batch_no_images(self):
        """Test processing batch with no images"""
        with patch.object(self.processor, 'get_images_needing_correction', return_value=[]):
            with patch('builtins.print') as mock_print:
                result = self.processor.process_batch(10)
                assert result["processed"] == 0
                assert result["successful"] == 0
                assert result["failed"] == 0
                assert result["rate_limited"] is False
                mock_print.assert_called_with("No images need correction")
    
    def test_process_batch_success(self):
        """Test successful batch processing"""
        test_images = [
            {'id': 1, 'file_path': 'test1.jpg', 'file_name': 'test1.jpg'},
            {'id': 2, 'file_path': 'test2.jpg', 'file_name': 'test2.jpg'}
        ]
        
        with patch.object(self.processor, 'get_images_needing_correction', return_value=test_images):
            with patch.object(self.processor, 'process_image', return_value=True):
                with patch('time.sleep'):  # Mock sleep to speed up test
                    result = self.processor.process_batch(10)
                    assert result["processed"] == 2
                    assert result["successful"] == 2
                    assert result["failed"] == 0
                    assert result["rate_limited"] is False
    
    def test_process_batch_mixed_results(self):
        """Test batch processing with mixed results"""
        test_images = [
            {'id': 1, 'file_path': 'test1.jpg', 'file_name': 'test1.jpg'},
            {'id': 2, 'file_path': 'test2.jpg', 'file_name': 'test2.jpg'}
        ]
        
        with patch.object(self.processor, 'get_images_needing_correction', return_value=test_images):
            with patch.object(self.processor, 'process_image', side_effect=[True, False]):
                with patch('time.sleep'):
                    result = self.processor.process_batch(10)
                    assert result["processed"] == 2
                    assert result["successful"] == 1
                    assert result["failed"] == 1
                    assert result["rate_limited"] is False
    
    def test_process_batch_rate_limited(self):
        """Test batch processing with rate limiting"""
        from helpers.llm_client import RateLimitError
        
        test_images = [
            {'id': 1, 'file_path': 'test1.jpg', 'file_name': 'test1.jpg'}
        ]
        
        with patch.object(self.processor, 'get_images_needing_correction', return_value=test_images):
            with patch.object(self.processor, 'process_image', side_effect=RateLimitError("Rate limited")):
                with patch('builtins.print') as mock_print:
                    result = self.processor.process_batch(10)
                    assert result["processed"] == 0
                    assert result["successful"] == 0
                    assert result["failed"] == 0
                    assert result["rate_limited"] is True
                    mock_print.assert_called_with("Rate limited - stopping processing")
    
    def test_process_batch_keyboard_interrupt(self):
        """Test batch processing with keyboard interrupt"""
        test_images = [
            {'id': 1, 'file_path': 'test1.jpg', 'file_name': 'test1.jpg'}
        ]
        
        with patch.object(self.processor, 'get_images_needing_correction', return_value=test_images):
            with patch.object(self.processor, 'process_image', side_effect=KeyboardInterrupt()):
                with patch('builtins.print') as mock_print:
                    result = self.processor.process_batch(10)
                    assert result["processed"] == 0
                    assert result["successful"] == 0
                    assert result["failed"] == 0
                    assert result["rate_limited"] is False
                    mock_print.assert_called_with("\nProcessing interrupted by user")


class TestMainFunction:
    """Test the main function and argument parsing"""
    
    def test_main_success(self):
        """Test successful main execution"""
        with patch('sys.argv', ['llm_correction_processor.py', '--batch-size', '5']):
            with patch('os.getenv', return_value='test_key'):
                with patch('llm_correction_processor.LLMCorrectionProcessor') as mock_processor_class:
                    mock_processor = Mock()
                    mock_processor.process_batch.return_value = {
                        "processed": 5,
                        "successful": 5,
                        "failed": 0,
                        "rate_limited": False
                    }
                    mock_processor_class.return_value = mock_processor
                    
                    with patch('builtins.print') as mock_print:
                        with pytest.raises(SystemExit) as exc_info:
                            from llm_correction_processor import main
                            main()
                        assert exc_info.value.code == 0
                        assert "✓ Processing completed successfully" in str(mock_print.call_args_list)
    
    def test_main_rate_limited(self):
        """Test main execution with rate limiting"""
        with patch('sys.argv', ['llm_correction_processor.py']):
            with patch('os.getenv', return_value='test_key'):
                with patch('llm_correction_processor.LLMCorrectionProcessor') as mock_processor_class:
                    mock_processor = Mock()
                    mock_processor.process_batch.return_value = {
                        "processed": 5,
                        "successful": 3,
                        "failed": 2,
                        "rate_limited": True
                    }
                    mock_processor_class.return_value = mock_processor
                    
                    with patch('builtins.print') as mock_print:
                        with pytest.raises(SystemExit) as exc_info:
                            from llm_correction_processor import main
                            main()
                        assert exc_info.value.code == 2
                        assert "⚠ Processing stopped due to rate limiting" in str(mock_print.call_args_list)
    
    def test_main_no_api_key(self):
        """Test main execution without API key"""
        with patch('sys.argv', ['llm_correction_processor.py']):
            with patch('os.getenv', return_value=None):
                with patch('builtins.print') as mock_print:
                    with pytest.raises(SystemExit) as exc_info:
                        from llm_correction_processor import main
                        main()
                    assert exc_info.value.code == 1
                    assert "Error: VENICE_API_KEY environment variable not set" in str(mock_print.call_args_list)
    
    def test_main_general_error(self):
        """Test main execution with general error"""
        with patch('sys.argv', ['llm_correction_processor.py']):
            with patch('os.getenv', return_value='test_key'):
                with patch('llm_correction_processor.LLMCorrectionProcessor', side_effect=Exception("General error")):
                    with patch('builtins.print') as mock_print:
                        with pytest.raises(SystemExit) as exc_info:
                            from llm_correction_processor import main
                            main()
                        assert exc_info.value.code == 1
                        assert "Error: General error" in str(mock_print.call_args_list)
