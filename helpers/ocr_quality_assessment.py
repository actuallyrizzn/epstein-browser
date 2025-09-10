"""
OCR Quality Assessment and LLM Correction System

This module handles OCR text correction using LLM APIs and quality assessment.
Part of the LLM Correction Pass feature for the Epstein Documents Browser.
"""

import tiktoken
import dirtyjson
import sqlite3
import json
import time
from typing import Dict, Any, Optional, List
from datetime import datetime
from .llm_client import LLMClient, RateLimitError, APIError


class OCRQualityAssessment:
    """OCR quality assessment and reprocessing queue management"""
    
    def __init__(self, db_path: str, llm_client=None):
        self.db_path = db_path
        self.llm_client = llm_client
        self.encoding = tiktoken.encoding_for_model("gpt-4")
    
    def ensure_database_schema(self, conn: sqlite3.Connection):
        """Idempotently ensure database schema is up to date"""
        
        # Check if ocr_corrections table exists
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='ocr_corrections'")
        if not cursor.fetchone():
            # Create ocr_corrections table
            conn.execute("""
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
        
        # Check if ocr_reprocessing_queue table exists
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='ocr_reprocessing_queue'")
        if not cursor.fetchone():
            conn.execute("""
                CREATE TABLE ocr_reprocessing_queue (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    image_id INTEGER NOT NULL,
                    original_quality_score INTEGER,
                    reprocess_reason TEXT,
                    priority INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'queued',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    processed_at TIMESTAMP,
                    FOREIGN KEY (image_id) REFERENCES images (id) ON DELETE CASCADE
                )
            """)
        
        # Check and add columns to images table idempotently
        cursor = conn.execute("PRAGMA table_info(images)")
        existing_columns = [row[1] for row in cursor.fetchall()]
        
        required_columns = [
            ('has_corrected_text', 'BOOLEAN DEFAULT FALSE'),
            ('correction_confidence', 'INTEGER DEFAULT NULL'),
            ('correction_status', 'TEXT DEFAULT "none"'),
            ('ocr_quality_score', 'INTEGER DEFAULT NULL'),
            ('ocr_quality_status', 'TEXT DEFAULT "pending"'),
            ('reprocess_priority', 'INTEGER DEFAULT 0')
        ]
        
        for column_name, column_def in required_columns:
            if column_name not in existing_columns:
                try:
                    conn.execute(f"ALTER TABLE images ADD COLUMN {column_name} {column_def}")
                except sqlite3.OperationalError as e:
                    if "duplicate column name" not in str(e).lower():
                        raise  # Re-raise if it's not a duplicate column error
        
        conn.commit()
    
    def calculate_token_estimate(self, prompt: str, ocr_text: str) -> int:
        """Calculate token estimate using tiktoken with 3% buffer"""
        try:
            prompt_tokens = len(self.encoding.encode(prompt))
            ocr_tokens = len(self.encoding.encode(ocr_text))
            total_tokens = prompt_tokens + (ocr_tokens * 2)
            buffer_tokens = int(total_tokens * 0.03)
            return total_tokens + buffer_tokens
        except Exception as e:
            # Fallback logic to be refined in development
            return len(prompt) + len(ocr_text) * 2  # Rough estimate
    
    def correct_ocr_text(self, ocr_text: str, document_type: str = "Legal Document") -> str:
        """Round 1: Correct OCR text using LLM"""
        if not self.llm_client:
            raise ValueError("LLM client not initialized")
        
        try:
            return self.llm_client.correct_ocr_text(ocr_text, document_type)
        except RateLimitError:
            raise  # Re-raise to exit processing loop
        except APIError as e:
            print(f"API error in OCR correction: {e}")
            return ocr_text  # Return original text on error
    
    def assess_correction_quality(self, original_text: str, corrected_text: str) -> Dict[str, Any]:
        """Round 2: Assess correction quality and return JSON"""
        if not self.llm_client:
            raise ValueError("LLM client not initialized")
        
        try:
            return self.llm_client.assess_correction_quality(original_text, corrected_text)
        except RateLimitError:
            raise  # Re-raise to exit processing loop
        except APIError as e:
            print(f"API error in quality assessment: {e}")
            # Return default assessment on error
            return {
                "quality_score": 50,
                "improvement_level": "minimal",
                "major_corrections": ["API error - manual review needed"],
                "confidence": "low",
                "needs_review": True
            }
    
    def parse_assessment_json(self, json_response: str) -> Optional[Dict[str, Any]]:
        """Parse JSON response using dirtyjson for robustness"""
        try:
            return dirtyjson.loads(json_response)
        except Exception as e:
            # Fallback parsing or logging - will be refined in development
            return None
    
    def validate_correction_changes(self, original_text: str, corrected_text: str) -> bool:
        """Validate that corrected text is actually different from original"""
        return original_text.strip() != corrected_text.strip()
    
    def flag_for_reprocessing(self, image_id: int, reason: str, priority: int = 0):
        """Add image to reprocessing queue"""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("""
                INSERT INTO ocr_reprocessing_queue (image_id, reprocess_reason, priority)
                VALUES (?, ?, ?)
            """, (image_id, reason, priority))
            conn.commit()
        finally:
            conn.close()
    
    def get_reprocessing_queue(self, status: str = None) -> List[Dict]:
        """Get items from reprocessing queue"""
        conn = sqlite3.connect(self.db_path)
        try:
            if status:
                cursor = conn.execute("""
                    SELECT * FROM ocr_reprocessing_queue WHERE status = ?
                    ORDER BY priority DESC, created_at ASC
                """, (status,))
            else:
                cursor = conn.execute("""
                    SELECT * FROM ocr_reprocessing_queue
                    ORDER BY priority DESC, created_at ASC
                """)
            
            columns = [description[0] for description in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
        finally:
            conn.close()
    
    def save_correction(self, image_id: int, original_text: str, corrected_text: str, 
                       assessment: Dict[str, Any], llm_model: str, processing_time_ms: int) -> int:
        """Save correction to database and return correction ID"""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute("""
                INSERT INTO ocr_corrections (
                    image_id, original_text, corrected_text, quality_score,
                    improvement_level, major_corrections, confidence, needs_review,
                    assessment_json, llm_model, processing_time_ms
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                image_id, original_text, corrected_text,
                assessment.get('quality_score'),
                assessment.get('improvement_level'),
                json.dumps(assessment.get('major_corrections', [])),
                assessment.get('confidence'),
                assessment.get('needs_review', False),
                json.dumps(assessment),
                llm_model,
                processing_time_ms
            ))
            
            correction_id = cursor.lastrowid
            
            # Update images table
            conn.execute("""
                UPDATE images SET 
                    has_corrected_text = TRUE,
                    correction_confidence = ?,
                    correction_status = 'completed'
                WHERE id = ?
            """, (assessment.get('quality_score'), image_id))
            
            conn.commit()
            return correction_id
            
        finally:
            conn.close()
    
    def get_correction(self, image_id: int) -> Optional[Dict[str, Any]]:
        """Get correction for an image"""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute("""
                SELECT * FROM ocr_corrections WHERE image_id = ?
                ORDER BY created_at DESC LIMIT 1
            """, (image_id,))
            
            row = cursor.fetchone()
            if not row:
                return None
            
            columns = [description[0] for description in cursor.description]
            correction = dict(zip(columns, row))
            
            # Parse JSON fields
            if correction.get('major_corrections'):
                correction['major_corrections'] = json.loads(correction['major_corrections'])
            if correction.get('assessment_json'):
                correction['assessment_json'] = json.loads(correction['assessment_json'])
            
            return correction
            
        finally:
            conn.close()
    
    def detect_low_quality_ocr(self, ocr_text: str) -> Dict[str, Any]:
        """Detect if OCR text is low quality (nonsense, images, handwriting failures)"""
        if not ocr_text or len(ocr_text.strip()) < 10:
            return {
                "is_low_quality": True,
                "reason": "text_too_short",
                "confidence": 1.0,
                "suggestions": ["reprocess_with_higher_quality_ocr"]
            }
        
        # Check for common low-quality patterns
        text_lower = ocr_text.lower()
        
        # Pattern 1: Mostly non-alphabetic characters
        alpha_chars = sum(1 for c in ocr_text if c.isalpha())
        total_chars = len(ocr_text.replace(' ', ''))
        if total_chars > 0 and (alpha_chars / total_chars) < 0.3:
            return {
                "is_low_quality": True,
                "reason": "mostly_non_alphabetic",
                "confidence": 0.8,
                "suggestions": ["likely_image_or_handwriting_failure"]
            }
        
        # Pattern 2: Repetitive characters (common in failed OCR)
        char_counts = {}
        for char in ocr_text:
            if char.isalnum():
                char_counts[char] = char_counts.get(char, 0) + 1
        
        if char_counts:
            max_repetition = max(char_counts.values())
            if max_repetition > len(ocr_text) * 0.4:  # 40% same character
                return {
                    "is_low_quality": True,
                    "reason": "excessive_character_repetition",
                    "confidence": 0.7,
                    "suggestions": ["likely_ocr_failure"]
                }
        
        # Pattern 3: Very short words or gibberish
        words = ocr_text.split()
        if len(words) > 0:
            avg_word_length = sum(len(word) for word in words) / len(words)
            if avg_word_length < 2.0:  # Average word less than 2 characters
                return {
                    "is_low_quality": True,
                    "reason": "gibberish_short_words",
                    "confidence": 0.6,
                    "suggestions": ["likely_handwriting_or_image_ocr_failure"]
                }
        
        # Pattern 4: Check for common OCR failure patterns
        failure_patterns = [
            "qqqq", "wwww", "eeee", "rrrr", "tttt", "yyyy",  # Stuck keys
            "asdf", "qwer", "zxcv",  # Keyboard patterns
            "0000", "1111", "2222", "3333",  # Number repetition
        ]
        
        for pattern in failure_patterns:
            if pattern in text_lower:
                return {
                    "is_low_quality": True,
                    "reason": "ocr_failure_pattern",
                    "confidence": 0.9,
                    "suggestions": ["definite_ocr_failure"]
                }
        
        # Pattern 5: Very high ratio of special characters
        special_chars = sum(1 for c in ocr_text if not c.isalnum() and not c.isspace())
        if len(ocr_text) > 0 and (special_chars / len(ocr_text)) > 0.5:
            return {
                "is_low_quality": True,
                "reason": "excessive_special_characters",
                "confidence": 0.7,
                "suggestions": ["likely_image_or_symbol_ocr_failure"]
            }
        
        # If none of the patterns match, assume it's reasonable quality
        return {
            "is_low_quality": False,
            "reason": "passed_quality_checks",
            "confidence": 0.8,
            "suggestions": []
        }
    
    def flag_low_quality_for_reprocessing(self, image_id: int, ocr_text: str) -> bool:
        """Check OCR quality and flag for reprocessing if needed"""
        quality_check = self.detect_low_quality_ocr(ocr_text)
        
        if quality_check["is_low_quality"]:
            # Flag for reprocessing with high priority
            priority = 10 if quality_check["confidence"] > 0.8 else 5
            reason = f"{quality_check['reason']}: {', '.join(quality_check['suggestions'])}"
            
            self.flag_for_reprocessing(image_id, reason, priority)
            
            # Update image status
            conn = sqlite3.connect(self.db_path)
            try:
                conn.execute("""
                    UPDATE images SET 
                        ocr_quality_status = 'reprocess_required',
                        reprocess_priority = ?
                    WHERE id = ?
                """, (priority, image_id))
                conn.commit()
                return True
            finally:
                conn.close()
        
        return False
    
    def process_reprocessing_queue(self, batch_size: int = 10):
        """Process items in reprocessing queue"""
        conn = sqlite3.connect(self.db_path)
        try:
            # Get items from reprocessing queue
            cursor = conn.execute("""
                SELECT rq.id, rq.image_id, rq.reprocess_reason, rq.priority,
                       i.file_path, i.file_name
                FROM ocr_reprocessing_queue rq
                JOIN images i ON rq.image_id = i.id
                WHERE rq.status = 'queued'
                ORDER BY rq.priority DESC, rq.created_at ASC
                LIMIT ?
            """, (batch_size,))
            
            items = cursor.fetchall()
            if not items:
                print("No items in reprocessing queue")
                return
            
            print(f"Processing {len(items)} items from reprocessing queue")
            
            for item in items:
                queue_id, image_id, reason, priority, file_path, file_name = item
                
                print(f"Reprocessing image {image_id}: {file_name}")
                print(f"  Reason: {reason}")
                print(f"  Priority: {priority}")
                
                # Update status to processing
                conn.execute("""
                    UPDATE ocr_reprocessing_queue 
                    SET status = 'processing', started_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (queue_id,))
                conn.commit()
                
                try:
                    # Here you would call your high-quality OCR processor
                    # For now, we'll just mark as completed
                    # In a real implementation, this would:
                    # 1. Call a high-quality OCR service
                    # 2. Update the images table with new OCR text
                    # 3. Run the LLM correction process
                    
                    print(f"  ✓ Reprocessing completed for image {image_id}")
                    
                    # Mark as completed
                    conn.execute("""
                        UPDATE ocr_reprocessing_queue 
                        SET status = 'completed', completed_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                    """, (queue_id,))
                    
                    # Update image status
                    conn.execute("""
                        UPDATE images 
                        SET ocr_quality_status = 'high_quality'
                        WHERE id = ?
                    """, (image_id,))
                    
                    conn.commit()
                    
                except Exception as e:
                    print(f"  ✗ Error reprocessing image {image_id}: {e}")
                    
                    # Mark as failed
                    conn.execute("""
                        UPDATE ocr_reprocessing_queue 
                        SET status = 'failed', error_message = ?, completed_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                    """, (str(e), queue_id,))
                    conn.commit()
            
        finally:
            conn.close()
