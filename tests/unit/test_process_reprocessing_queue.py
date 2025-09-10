"""
Test suite for Process Reprocessing Queue Script

Tests the reprocessing queue processing functionality.
"""

import pytest
import sqlite3
import tempfile
import os
from unittest.mock import Mock, patch, MagicMock
import sys

# Add project root to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from process_reprocessing_queue import main


class TestProcessReprocessingQueue:
    """Test cases for process_reprocessing_queue script"""
    
    def setup_method(self):
        """Set up test fixtures"""
        # Create temporary database
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        self.db_path = self.temp_db.name
        
        # Create test database with required tables
        self._create_test_database()
    
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
            INSERT INTO images (id, file_path, file_name)
            VALUES (1, 'test1.jpg', 'test1.jpg'),
                   (2, 'test2.jpg', 'test2.jpg'),
                   (3, 'test3.jpg', 'test3.jpg')
        """)
        
        # Insert test queue items
        cursor.execute("""
            INSERT INTO ocr_reprocessing_queue (image_id, reprocess_reason, priority, status)
            VALUES (1, 'Low quality OCR', 10, 'queued'),
                   (2, 'Handwriting failure', 5, 'queued'),
                   (3, 'Image OCR failure', 8, 'completed')
        """)
        
        conn.commit()
        conn.close()
    
    def test_main_dry_run(self):
        """Test main function with dry run"""
        with patch('sys.argv', ['process_reprocessing_queue.py', '--db', self.db_path, '--dry-run']):
            with patch('builtins.print') as mock_print:
                main()
                
                # Should show items that would be processed
                assert any("DRY RUN" in str(call) for call in mock_print.call_args_list)
                assert any("Image ID: 1" in str(call) for call in mock_print.call_args_list)
                assert any("Image ID: 2" in str(call) for call in mock_print.call_args_list)
    
    def test_main_dry_run_no_items(self):
        """Test main function with dry run and no queued items"""
        # Clear the queue
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM ocr_reprocessing_queue WHERE status = 'queued'")
        conn.commit()
        conn.close()
        
        with patch('sys.argv', ['process_reprocessing_queue.py', '--db', self.db_path, '--dry-run']):
            with patch('builtins.print') as mock_print:
                main()
                assert any("No items in reprocessing queue" in str(call) for call in mock_print.call_args_list)
    
    def test_main_process_queue(self):
        """Test main function processing the queue"""
        with patch('sys.argv', ['process_reprocessing_queue.py', '--db', self.db_path, '--batch-size', '5']):
            with patch('builtins.print') as mock_print:
                main()
                
                # Should process items
                assert any("Processing OCR reprocessing queue" in str(call) for call in mock_print.call_args_list)
                assert any("Processing 2 items" in str(call) for call in mock_print.call_args_list)
                assert any("Reprocessing queue processing completed" in str(call) for call in mock_print.call_args_list)
    
    def test_main_process_queue_no_items(self):
        """Test main function processing empty queue"""
        # Clear the queue
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM ocr_reprocessing_queue WHERE status = 'queued'")
        conn.commit()
        conn.close()
        
        with patch('sys.argv', ['process_reprocessing_queue.py', '--db', self.db_path]):
            with patch('builtins.print') as mock_print:
                main()
                assert any("No items in reprocessing queue" in str(call) for call in mock_print.call_args_list)
    
    def test_main_with_custom_batch_size(self):
        """Test main function with custom batch size"""
        with patch('sys.argv', ['process_reprocessing_queue.py', '--db', self.db_path, '--batch-size', '1']):
            with patch('builtins.print') as mock_print:
                main()
                
                # Should process with batch size 1
                assert any("Processing OCR reprocessing queue" in str(call) for call in mock_print.call_args_list)
    
    def test_main_database_error(self):
        """Test main function with database error"""
        with patch('sys.argv', ['process_reprocessing_queue.py', '--db', 'nonexistent.db']):
            with patch('builtins.print') as mock_print:
                with pytest.raises(SystemExit) as exc_info:
                    main()
                assert exc_info.value.code == 1
                assert any("Error:" in str(call) for call in mock_print.call_args_list)
    
    def test_main_ocr_assessor_error(self):
        """Test main function with OCR assessor error"""
        with patch('sys.argv', ['process_reprocessing_queue.py', '--db', self.db_path]):
            with patch('process_reprocessing_queue.OCRQualityAssessment', side_effect=Exception("OCR assessor error")):
                with patch('builtins.print') as mock_print:
                    with pytest.raises(SystemExit) as exc_info:
                        main()
                    assert exc_info.value.code == 1
                    assert any("Error: OCR assessor error" in str(call) for call in mock_print.call_args_list)
    
    def test_main_default_arguments(self):
        """Test main function with default arguments"""
        with patch('sys.argv', ['process_reprocessing_queue.py']):
            with patch('builtins.print') as mock_print:
                main()
                
                # Should use default database path
                assert any("Processing OCR reprocessing queue" in str(call) for call in mock_print.call_args_list)
    
    def test_main_help_argument(self):
        """Test main function with help argument"""
        with patch('sys.argv', ['process_reprocessing_queue.py', '--help']):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 0  # Help should exit with 0
    
    def test_main_invalid_batch_size(self):
        """Test main function with invalid batch size"""
        with patch('sys.argv', ['process_reprocessing_queue.py', '--batch-size', 'invalid']):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 2  # Argument error
    
    def test_main_negative_batch_size(self):
        """Test main function with negative batch size"""
        with patch('sys.argv', ['process_reprocessing_queue.py', '--batch-size', '-1']):
            with patch('builtins.print') as mock_print:
                main()
                
                # Should still process (batch size validation is in OCRQualityAssessment)
                assert any("Processing OCR reprocessing queue" in str(call) for call in mock_print.call_args_list)
    
    def test_main_large_batch_size(self):
        """Test main function with large batch size"""
        with patch('sys.argv', ['process_reprocessing_queue.py', '--batch-size', '1000']):
            with patch('builtins.print') as mock_print:
                main()
                
                # Should process with large batch size
                assert any("Processing OCR reprocessing queue" in str(call) for call in mock_print.call_args_list)
    
    def test_main_dry_run_with_batch_size(self):
        """Test main function with dry run and batch size"""
        with patch('sys.argv', ['process_reprocessing_queue.py', '--db', self.db_path, '--dry-run', '--batch-size', '1']):
            with patch('builtins.print') as mock_print:
                main()
                
                # Should show dry run results
                assert any("DRY RUN" in str(call) for call in mock_print.call_args_list)
    
    def test_main_process_with_errors(self):
        """Test main function processing with errors in queue items"""
        # Add an item that will cause an error
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO ocr_reprocessing_queue (image_id, reprocess_reason, priority, status)
            VALUES (999, 'Test error', 1, 'queued')
        """)
        conn.commit()
        conn.close()
        
        with patch('sys.argv', ['process_reprocessing_queue.py', '--db', self.db_path]):
            with patch('builtins.print') as mock_print:
                main()
                
                # Should handle errors gracefully
                assert any("Processing OCR reprocessing queue" in str(call) for call in mock_print.call_args_list)
    
    def test_main_environment_variable_loading(self):
        """Test main function loads environment variables"""
        with patch('sys.argv', ['process_reprocessing_queue.py', '--db', self.db_path]):
            with patch('process_reprocessing_queue.load_dotenv') as mock_load_dotenv:
                main()
                mock_load_dotenv.assert_called_once()
    
    def test_main_dotenv_import_error(self):
        """Test main function handles dotenv import error"""
        with patch('sys.argv', ['process_reprocessing_queue.py', '--db', self.db_path]):
            with patch('process_reprocessing_queue.load_dotenv', side_effect=ImportError("No module named 'dotenv'")):
                # Should not raise an error, just continue without dotenv
                with patch('builtins.print') as mock_print:
                    main()
                    assert any("Processing OCR reprocessing queue" in str(call) for call in mock_print.call_args_list)
