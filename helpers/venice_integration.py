#!/usr/bin/env python3
"""
Venice AI Integration for Epstein Documents Browser

This module provides integration with Venice AI for OCR text correction
and enhancement using the Venice SDK.

Copyright (C) 2025 Epstein Documents OCR Project
"""

import os
import logging
from typing import Optional, List, Dict, Any
from pathlib import Path

# Add the venice_sdk to the path
import sys
sys.path.append(str(Path(__file__).parent / "venice_sdk"))

from venice_sdk import ChatAPI, Message, load_config, VeniceError

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class VeniceOCRCorrector:
    """
    Venice AI-powered OCR text corrector for legal documents.
    
    This class uses Venice AI to correct and enhance OCR text with
    contextual understanding of legal documents.
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the Venice OCR corrector.
        
        Args:
            api_key: Optional Venice API key. If not provided, will be loaded from .env
        """
        try:
            # Load configuration from .env file
            self.config = load_config(api_key)
            self.chat_api = ChatAPI(self.config)
            logger.info("Venice AI OCR corrector initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Venice AI: {e}")
            raise
    
    def correct_ocr_text(
        self, 
        raw_text: str, 
        document_type: str = "legal",
        context: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Correct OCR text using Venice AI with legal document context.
        
        Args:
            raw_text: The raw OCR text to correct
            document_type: Type of document (legal, congressional, etc.)
            context: Optional additional context about the document
            
        Returns:
            Dict containing corrected text, confidence score, and metadata
        """
        try:
            # Create a specialized prompt for legal document correction
            system_prompt = self._create_system_prompt(document_type, context)
            
            # Create the correction request
            messages = [
                Message(role="system", content=system_prompt),
                Message(role="user", content=f"Please correct this OCR text:\n\n{raw_text}")
            ]
            
            # Make the API call
            response = self.chat_api.create_completion(
                messages=messages,
                model=self.config.default_model or "gpt-4",
                temperature=0.1,  # Low temperature for consistent corrections
                max_tokens=4000
            )
            
            # Extract the corrected text
            corrected_text = response.choices[0].message.content
            
            # Calculate confidence based on response quality
            confidence = self._calculate_confidence(raw_text, corrected_text)
            
            return {
                "raw_text": raw_text,
                "corrected_text": corrected_text,
                "confidence": confidence,
                "model": response.model,
                "tokens_used": response.usage.total_tokens,
                "document_type": document_type,
                "correction_metadata": {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "finish_reason": response.choices[0].finish_reason
                }
            }
            
        except VeniceError as e:
            logger.error(f"Venice AI API error: {e}")
            return {
                "raw_text": raw_text,
                "corrected_text": raw_text,  # Return original on error
                "confidence": 0.0,
                "error": str(e),
                "success": False
            }
        except Exception as e:
            logger.error(f"Unexpected error in OCR correction: {e}")
            return {
                "raw_text": raw_text,
                "corrected_text": raw_text,
                "confidence": 0.0,
                "error": str(e),
                "success": False
            }
    
    def _create_system_prompt(self, document_type: str, context: Optional[str]) -> str:
        """Create a specialized system prompt for document correction."""
        
        base_prompt = f"""You are an expert at correcting OCR text from {document_type} documents. 
Your task is to fix common OCR errors while preserving the original meaning and legal accuracy.

Common OCR errors to fix:
- Character recognition mistakes (0 vs O, 1 vs l, etc.)
- Spacing issues and word breaks
- Punctuation errors
- Number formatting
- Legal terminology corrections

Guidelines:
1. Preserve the original structure and formatting
2. Maintain legal accuracy and terminology
3. Fix obvious OCR errors but don't change valid content
4. Keep dates, numbers, and proper nouns intact
5. Preserve line breaks and paragraph structure
6. If uncertain, keep the original text

Return only the corrected text, no explanations or metadata."""

        if context:
            base_prompt += f"\n\nAdditional context: {context}"
        
        return base_prompt
    
    def _calculate_confidence(self, raw_text: str, corrected_text: str) -> float:
        """
        Calculate confidence score based on text similarity and quality indicators.
        
        This is a simple heuristic - in production, you might want more sophisticated scoring.
        """
        if not raw_text or not corrected_text:
            return 0.0
        
        # Basic similarity check
        raw_words = raw_text.split()
        corrected_words = corrected_text.split()
        
        if len(raw_words) == 0:
            return 0.0
        
        # Calculate word overlap percentage
        common_words = set(raw_words) & set(corrected_words)
        word_similarity = len(common_words) / len(raw_words)
        
        # Check for length similarity (major changes might indicate issues)
        length_ratio = min(len(corrected_text), len(raw_text)) / max(len(corrected_text), len(raw_text))
        
        # Combine factors for confidence score
        confidence = (word_similarity * 0.7 + length_ratio * 0.3)
        
        return min(1.0, max(0.0, confidence))
    
    def batch_correct_ocr(
        self, 
        text_files: List[Path], 
        output_dir: Optional[Path] = None
    ) -> Dict[str, Any]:
        """
        Process multiple OCR text files in batch.
        
        Args:
            text_files: List of Path objects to OCR text files
            output_dir: Optional directory to save corrected text files
            
        Returns:
            Dict with processing results and statistics
        """
        results = {
            "processed": 0,
            "successful": 0,
            "failed": 0,
            "total_tokens": 0,
            "files": []
        }
        
        for text_file in text_files:
            try:
                # Read the raw text
                raw_text = text_file.read_text(encoding='utf-8', errors='ignore')
                
                # Correct the text
                correction_result = self.correct_ocr_text(raw_text)
                
                # Save corrected text if output directory specified
                if output_dir and correction_result.get("success", True):
                    output_file = output_dir / f"{text_file.stem}_corrected.txt"
                    output_file.write_text(correction_result["corrected_text"], encoding='utf-8')
                
                # Update statistics
                results["processed"] += 1
                if correction_result.get("success", True):
                    results["successful"] += 1
                    results["total_tokens"] += correction_result.get("tokens_used", 0)
                else:
                    results["failed"] += 1
                
                results["files"].append({
                    "file": str(text_file),
                    "success": correction_result.get("success", True),
                    "confidence": correction_result.get("confidence", 0.0),
                    "tokens_used": correction_result.get("tokens_used", 0)
                })
                
                logger.info(f"Processed {text_file.name}: {correction_result.get('confidence', 0.0):.2f} confidence")
                
            except Exception as e:
                logger.error(f"Error processing {text_file}: {e}")
                results["failed"] += 1
                results["files"].append({
                    "file": str(text_file),
                    "success": False,
                    "error": str(e)
                })
        
        return results


def create_venice_corrector() -> Optional[VeniceOCRCorrector]:
    """
    Factory function to create a Venice OCR corrector instance.
    
    Returns:
        VeniceOCRCorrector instance or None if initialization fails
    """
    try:
        return VeniceOCRCorrector()
    except Exception as e:
        logger.error(f"Failed to create Venice OCR corrector: {e}")
        return None


# Example usage
if __name__ == "__main__":
    # Test the integration
    corrector = create_venice_corrector()
    
    if corrector:
        # Example OCR text with common errors
        test_text = """
        Th1s 1s a t3st of OCR corr3ction.
        Th3 qu1ck br0wn f0x jumps 0ver th3 lazy d0g.
        D0J-0GR-00022168-001
        """
        
        result = corrector.correct_ocr_text(test_text, "legal")
        print("Raw text:", result["raw_text"])
        print("Corrected text:", result["corrected_text"])
        print("Confidence:", result["confidence"])
    else:
        print("Failed to initialize Venice AI corrector")
