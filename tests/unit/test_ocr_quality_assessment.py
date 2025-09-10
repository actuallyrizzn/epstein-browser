"""
Test suite for OCR Quality Assessment

Tests the OCR correction, quality assessment, and reprocessing queue functionality.
"""

import pytest
import sqlite3
import json
import tempfile
import os
from unittest.mock import Mock, patch, MagicMock
import sys

# Add helpers to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'helpers'))

from helpers.ocr_quality_assessment import OCRQualityAssessment


class TestOCRQualityAssessment:
    """Test cases for OCRQualityAssessment"""
    
    def setup_method(self):
        """Set up test fixtures"""
        # Create temporary database
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        self.db_path = self.temp_db.name
        
        # Create test database with required tables
        self._create_test_database()
        
        # Create OCR assessor instance
        self.ocr_assessor = OCRQualityAssessment(self.db_path)
    
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
            INSERT INTO images (id, file_path, file_name, has_ocr_text)
            VALUES (1, 'test1.jpg', 'test1.jpg', TRUE),
                   (2, 'test2.jpg', 'test2.jpg', TRUE),
                   (3, 'test3.jpg', 'test3.jpg', FALSE)
        """)
        
        conn.commit()
        conn.close()
    
    def test_init(self):
        """Test OCRQualityAssessment initialization"""
        assert self.ocr_assessor.db_path == self.db_path
        assert self.ocr_assessor.llm_client is None
    
    def test_init_with_llm_client(self):
        """Test initialization with LLM client"""
        mock_client = Mock()
        assessor = OCRQualityAssessment(self.db_path, mock_client)
        assert assessor.llm_client == mock_client
    
    def test_ensure_database_schema(self):
        """Test database schema creation"""
        conn = sqlite3.connect(self.db_path)
        try:
            # Should not raise any errors
            self.ocr_assessor.ensure_database_schema(conn)
            
            # Verify tables exist
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            assert 'ocr_corrections' in tables
            assert 'ocr_reprocessing_queue' in tables
        finally:
            conn.close()
    
    def test_calculate_token_estimate(self):
        """Test token calculation"""
        prompt = "Test prompt"
        ocr_text = "Test OCR text"
        
        with patch('tiktoken.encoding_for_model') as mock_encoding:
            mock_encoder = Mock()
            mock_encoder.encode.side_effect = lambda x: list(x.encode('utf-8'))  # Simple mock
            mock_encoding.return_value = mock_encoder
            
            tokens = self.ocr_assessor.calculate_token_estimate(prompt, ocr_text)
            assert tokens > 0
    
    def test_calculate_token_estimate_error(self):
        """Test token calculation with error"""
        with patch('tiktoken.encoding_for_model', side_effect=Exception("Tiktoken error")):
            tokens = self.ocr_assessor.calculate_token_estimate("prompt", "text")
            # Should return fallback calculation
            assert tokens > 0
    
    def test_correct_ocr_text_no_client(self):
        """Test OCR correction without LLM client"""
        with pytest.raises(ValueError, match="LLM client not initialized"):
            self.ocr_assessor.correct_ocr_text("test text")
    
    def test_correct_ocr_text_success(self):
        """Test successful OCR correction"""
        mock_client = Mock()
        mock_client.correct_ocr_text.return_value = "Corrected text"
        self.ocr_assessor.llm_client = mock_client
        
        result = self.ocr_assessor.correct_ocr_text("Original text")
        assert result == "Corrected text"
        mock_client.correct_ocr_text.assert_called_once_with("Original text", "Legal Document")
    
    def test_correct_ocr_text_with_document_type(self):
        """Test OCR correction with document type"""
        mock_client = Mock()
        mock_client.correct_ocr_text.return_value = "Corrected text"
        self.ocr_assessor.llm_client = mock_client
        
        result = self.ocr_assessor.correct_ocr_text("Original text", "Court Filing")
        assert result == "Corrected text"
        mock_client.correct_ocr_text.assert_called_once_with("Original text", "Court Filing")
    
    def test_correct_ocr_text_rate_limit(self):
        """Test OCR correction with rate limit error"""
        from helpers.llm_client import RateLimitError
        
        mock_client = Mock()
        mock_client.correct_ocr_text.side_effect = RateLimitError("Rate limited")
        self.ocr_assessor.llm_client = mock_client
        
        with pytest.raises(RateLimitError):
            self.ocr_assessor.correct_ocr_text("Original text")
    
    def test_correct_ocr_text_api_error(self):
        """Test OCR correction with API error"""
        from helpers.llm_client import APIError
        
        mock_client = Mock()
        mock_client.correct_ocr_text.side_effect = APIError("API error")
        self.ocr_assessor.llm_client = mock_client
        
        with patch('builtins.print') as mock_print:
            result = self.ocr_assessor.correct_ocr_text("Original text")
            assert result == "Original text"  # Should return original on error
            mock_print.assert_called_once()
    
    def test_assess_correction_quality_no_client(self):
        """Test quality assessment without LLM client"""
        with pytest.raises(ValueError, match="LLM client not initialized"):
            self.ocr_assessor.assess_correction_quality("original", "corrected")
    
    def test_assess_correction_quality_success(self):
        """Test successful quality assessment"""
        mock_client = Mock()
        mock_client.assess_correction_quality.return_value = {
            "quality_score": 85,
            "confidence": "high"
        }
        self.ocr_assessor.llm_client = mock_client
        
        result = self.ocr_assessor.assess_correction_quality("original", "corrected")
        assert result["quality_score"] == 85
        assert result["confidence"] == "high"
    
    def test_assess_correction_quality_rate_limit(self):
        """Test quality assessment with rate limit error"""
        from helpers.llm_client import RateLimitError
        
        mock_client = Mock()
        mock_client.assess_correction_quality.side_effect = RateLimitError("Rate limited")
        self.ocr_assessor.llm_client = mock_client
        
        with pytest.raises(RateLimitError):
            self.ocr_assessor.assess_correction_quality("original", "corrected")
    
    def test_assess_correction_quality_api_error(self):
        """Test quality assessment with API error"""
        from helpers.llm_client import APIError
        
        mock_client = Mock()
        mock_client.assess_correction_quality.side_effect = APIError("API error")
        self.ocr_assessor.llm_client = mock_client
        
        with patch('builtins.print') as mock_print:
            result = self.ocr_assessor.assess_correction_quality("original", "corrected")
            assert result["quality_score"] == 50  # Default error response
            assert result["needs_review"] is True
            mock_print.assert_called_once()
    
    def test_parse_assessment_json_success(self):
        """Test successful JSON parsing"""
        json_text = '{"quality_score": 85, "confidence": "high"}'
        result = self.ocr_assessor.parse_assessment_json(json_text)
        assert result["quality_score"] == 85
        assert result["confidence"] == "high"
    
    def test_parse_assessment_json_error(self):
        """Test JSON parsing with error"""
        json_text = "Invalid JSON"
        result = self.ocr_assessor.parse_assessment_json(json_text)
        assert result is None
    
    def test_validate_correction_changes_different(self):
        """Test validation with different texts"""
        result = self.ocr_assessor.validate_correction_changes("Original", "Corrected")
        assert result is True
    
    def test_validate_correction_changes_identical(self):
        """Test validation with identical texts"""
        result = self.ocr_assessor.validate_correction_changes("Same text", "Same text")
        assert result is False
    
    def test_validate_correction_changes_whitespace(self):
        """Test validation with whitespace differences"""
        result = self.ocr_assessor.validate_correction_changes("Text", "  Text  ")
        assert result is False  # Should be considered identical after strip
    
    def test_flag_for_reprocessing(self):
        """Test flagging image for reprocessing"""
        self.ocr_assessor.flag_for_reprocessing(1, "Test reason", 5)
        
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute("SELECT * FROM ocr_reprocessing_queue WHERE image_id = 1")
            row = cursor.fetchone()
            assert row is not None
            assert row[2] == "Test reason"  # reprocess_reason
            assert row[3] == 5  # priority
        finally:
            conn.close()
    
    def test_get_reprocessing_queue_all(self):
        """Test getting all reprocessing queue items"""
        # Add test data
        self.ocr_assessor.flag_for_reprocessing(1, "Reason 1", 5)
        self.ocr_assessor.flag_for_reprocessing(2, "Reason 2", 3)
        
        items = self.ocr_assessor.get_reprocessing_queue()
        assert len(items) == 2
    
    def test_get_reprocessing_queue_filtered(self):
        """Test getting filtered reprocessing queue items"""
        # Add test data
        self.ocr_assessor.flag_for_reprocessing(1, "Reason 1", 5)
        
        # Update one to completed
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("UPDATE ocr_reprocessing_queue SET status = 'completed' WHERE image_id = 1")
            conn.commit()
        finally:
            conn.close()
        
        items = self.ocr_assessor.get_reprocessing_queue("queued")
        assert len(items) == 0
        
        items = self.ocr_assessor.get_reprocessing_queue("completed")
        assert len(items) == 1
    
    def test_detect_low_quality_ocr_too_short(self):
        """Test low-quality detection for too short text"""
        result = self.ocr_assessor.detect_low_quality_ocr("a")
        assert result["is_low_quality"] is True
        assert result["reason"] == "text_too_short"
    
    def test_detect_low_quality_ocr_empty(self):
        """Test low-quality detection for empty text"""
        result = self.ocr_assessor.detect_low_quality_ocr("")
        assert result["is_low_quality"] is True
        assert result["reason"] == "text_too_short"
    
    def test_detect_low_quality_ocr_mostly_non_alphabetic(self):
        """Test low-quality detection for mostly non-alphabetic text"""
        result = self.ocr_assessor.detect_low_quality_ocr("@@@@ #### $$$$ %%%%")
        assert result["is_low_quality"] is True
        assert result["reason"] == "mostly_non_alphabetic"
    
    def test_detect_low_quality_ocr_character_repetition(self):
        """Test low-quality detection for character repetition"""
        result = self.ocr_assessor.detect_low_quality_ocr("qqqqqqqqqqqqqqqqqqqq")
        assert result["is_low_quality"] is True
        assert result["reason"] == "excessive_character_repetition"
    
    def test_detect_low_quality_ocr_gibberish_words(self):
        """Test low-quality detection for gibberish short words"""
        result = self.ocr_assessor.detect_low_quality_ocr("a b c d e f g h i j")
        assert result["is_low_quality"] is True
        assert result["reason"] == "gibberish_short_words"
    
    def test_detect_low_quality_ocr_failure_patterns(self):
        """Test low-quality detection for OCR failure patterns"""
        result = self.ocr_assessor.detect_low_quality_ocr("qqqq wwww eeee")
        assert result["is_low_quality"] is True
        assert result["reason"] == "ocr_failure_pattern"
    
    def test_detect_low_quality_ocr_keyboard_patterns(self):
        """Test low-quality detection for keyboard patterns"""
        result = self.ocr_assessor.detect_low_quality_ocr("asdf qwer zxcv")
        assert result["is_low_quality"] is True
        assert result["reason"] == "ocr_failure_pattern"
    
    def test_detect_low_quality_ocr_excessive_special_chars(self):
        """Test low-quality detection for excessive special characters"""
        result = self.ocr_assessor.detect_low_quality_ocr("!@#$%^&*()!@#$%^&*()")
        assert result["is_low_quality"] is True
        assert result["reason"] == "excessive_special_characters"
    
    def test_detect_low_quality_ocr_normal_text(self):
        """Test low-quality detection for normal text"""
        result = self.ocr_assessor.detect_low_quality_ocr("This is a normal legal document with proper text")
        assert result["is_low_quality"] is False
        assert result["reason"] == "passed_quality_checks"
    
    def test_flag_low_quality_for_reprocessing_high_quality(self):
        """Test flagging high-quality text (should not flag)"""
        result = self.ocr_assessor.flag_low_quality_for_reprocessing(1, "This is normal text")
        assert result is False
    
    def test_flag_low_quality_for_reprocessing_low_quality(self):
        """Test flagging low-quality text (should flag)"""
        result = self.ocr_assessor.flag_low_quality_for_reprocessing(1, "qqqq wwww eeee")
        assert result is True
        
        # Verify it was added to reprocessing queue
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute("SELECT * FROM ocr_reprocessing_queue WHERE image_id = 1")
            row = cursor.fetchone()
            assert row is not None
            assert "ocr_failure_pattern" in row[2]  # reprocess_reason
        finally:
            conn.close()
    
    def test_save_correction(self):
        """Test saving correction to database"""
        assessment = {
            "quality_score": 85,
            "improvement_level": "significant",
            "major_corrections": ["fixed spacing"],
            "confidence": "high",
            "needs_review": False
        }
        
        correction_id = self.ocr_assessor.save_correction(
            1, "Original text", "Corrected text", assessment, "llama-3.3-70b", 1000
        )
        
        assert correction_id is not None
        
        # Verify correction was saved
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute("SELECT * FROM ocr_corrections WHERE id = ?", (correction_id,))
            row = cursor.fetchone()
            assert row is not None
            assert row[2] == "Original text"  # original_text
            assert row[3] == "Corrected text"  # corrected_text
            assert row[4] == 85  # quality_score
        finally:
            conn.close()
    
    def test_get_correction(self):
        """Test getting correction from database"""
        # First save a correction
        assessment = {"quality_score": 85, "confidence": "high"}
        self.ocr_assessor.save_correction(1, "Original", "Corrected", assessment, "llama-3.3-70b", 1000)
        
        # Then retrieve it
        correction = self.ocr_assessor.get_correction(1)
        assert correction is not None
        assert correction["original_text"] == "Original"
        assert correction["corrected_text"] == "Corrected"
        assert correction["quality_score"] == 85
    
    def test_get_correction_not_found(self):
        """Test getting non-existent correction"""
        correction = self.ocr_assessor.get_correction(999)
        assert correction is None
    
    def test_process_reprocessing_queue_empty(self):
        """Test processing empty reprocessing queue"""
        with patch('builtins.print') as mock_print:
            self.ocr_assessor.process_reprocessing_queue()
            mock_print.assert_called_with("No items in reprocessing queue")
    
    def test_process_reprocessing_queue_with_items(self):
        """Test processing reprocessing queue with items"""
        # Add test item to queue
        self.ocr_assessor.flag_for_reprocessing(1, "Test reason", 5)
        
        with patch('builtins.print') as mock_print:
            self.ocr_assessor.process_reprocessing_queue()
            # Should process the item
            assert any("Processing 1 items" in str(call) for call in mock_print.call_args_list)
    
    def test_process_reprocessing_queue_with_error(self):
        """Test processing reprocessing queue with error"""
        # Add test item to queue
        self.ocr_assessor.flag_for_reprocessing(1, "Test reason", 5)
        
        # Mock the processing to raise an error
        with patch.object(self.ocr_assessor, 'flag_for_reprocessing', side_effect=Exception("Processing error")):
            with patch('builtins.print') as mock_print:
                self.ocr_assessor.process_reprocessing_queue()
                # Should handle the error
                assert any("Error reprocessing" in str(call) for call in mock_print.call_args_list)
