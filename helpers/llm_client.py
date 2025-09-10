"""
LLM Client Wrapper for OCR Correction

Handles API calls using Venice SDK for OCR correction.
Implements rate limiting, cost tracking, and error handling.
"""

import os
import time
import json
from typing import Dict, Any, Optional
from datetime import datetime

# Add Venice SDK to path
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), 'venice_sdk'))

from venice_sdk.client import HTTPClient
from venice_sdk.chat import ChatAPI, Message
from venice_sdk.config import load_config


class LLMClient:
    """Unified client for LLM API calls with rate limiting and cost tracking"""
    
    def __init__(self, model: str = "gpt-4"):
        self.model = model
        self.rate_limit_delay = 1.0  # seconds between requests
        self.last_request_time = 0
        
        # Initialize Venice client
        try:
            config = load_config()
            self.client = HTTPClient(config)
            self.chat_api = ChatAPI(self.client)
        except Exception as e:
            raise ValueError(f"Failed to initialize Venice client: {e}")
    
    def _rate_limit(self):
        """Implement rate limiting"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        if time_since_last < self.rate_limit_delay:
            time.sleep(self.rate_limit_delay - time_since_last)
        self.last_request_time = time.time()
    
    def _make_request(self, messages: list, max_tokens: int = 4000) -> Dict[str, Any]:
        """Make API request with error handling using Venice SDK"""
        self._rate_limit()
        
        try:
            # Convert messages to Venice Message objects
            venice_messages = []
            for msg in messages:
                venice_messages.append(Message(role=msg["role"], content=msg["content"]))
            
            # Make request using Venice SDK
            response = self.chat_api.complete(
                messages=[{"role": msg.role, "content": msg.content} for msg in venice_messages],
                model=self.model,
                temperature=0.1  # Low temperature for consistent corrections
            )
            
            # Venice returns raw JSON, so we can use it directly
            return response
            
        except Exception as e:
            error_str = str(e).lower()
            if "rate limit" in error_str or "429" in error_str:
                raise RateLimitError("Rate limited - exiting processing loop")
            else:
                raise APIError(f"API request failed: {str(e)}")
    
    def correct_ocr_text(self, ocr_text: str, document_type: str = "Legal Document") -> str:
        """Round 1: Correct OCR text using LLM"""
        prompt = f"""You are an expert legal document OCR correction specialist. Your task is to correct OCR errors in legal documents while preserving the original meaning and legal terminology.

DOCUMENT CONTEXT:
- Document Type: {document_type}
- Case: United States v. Maxwell (Epstein case)
- Date Range: 2020-2024

CORRECTION GUIDELINES:
1. Fix obvious OCR errors (character recognition mistakes)
2. Correct spacing and punctuation
3. Preserve legal terminology and proper names
4. Maintain original document structure
5. Do not add content not present in the original
6. Flag uncertain corrections with [UNCERTAIN: reason]

CRITICAL RESTRICTIONS - DO NOT:
- Change the meaning or substance of any legal text
- Modify legal arguments, claims, or statements
- Alter dates, numbers, or factual content
- Rewrite or rephrase sentences for clarity
- Add interpretation or commentary
- Change legal citations or references
- Modify signatures, names, or official designations
- Transform the document in any substantive way

REMEMBER: You are correcting OCR/transcription errors ONLY, not improving or modifying the legal content itself.

INPUT TEXT:
{ocr_text}

Provide ONLY the corrected text. Do not include any explanations or scores."""

        messages = [{"role": "user", "content": prompt}]
        
        try:
            response = self._make_request(messages)
            return response["choices"][0]["message"]["content"].strip()
                
        except (RateLimitError, APIError) as e:
            raise e
        except Exception as e:
            raise APIError(f"Unexpected error in OCR correction: {str(e)}")
    
    def assess_correction_quality(self, original_text: str, corrected_text: str) -> Dict[str, Any]:
        """Round 2: Assess correction quality and return JSON"""
        prompt = f"""You are an OCR correction quality assessor. Compare the original OCR text with the corrected version and provide a JSON assessment.

ORIGINAL OCR TEXT:
{original_text}

CORRECTED TEXT:
{corrected_text}

Provide a JSON response with the following structure:
{{
  "quality_score": 85,
  "improvement_level": "significant",
  "major_corrections": ["fixed spacing", "corrected proper names"],
  "confidence": "high",
  "needs_review": false
}}

Valid values:
- quality_score: 1-100 (overall quality of correction)
- improvement_level: "minimal", "moderate", "significant", "substantial"
- major_corrections: array of strings describing key improvements
- confidence: "low", "medium", "high"
- needs_review: boolean (true if human review recommended)"""

        messages = [{"role": "user", "content": prompt}]
        
        try:
            response = self._make_request(messages)
            json_text = response["choices"][0]["message"]["content"].strip()
            
            # Try to extract JSON from response
            try:
                return json.loads(json_text)
            except json.JSONDecodeError:
                # Try to find JSON in the response
                import re
                json_match = re.search(r'\{.*\}', json_text, re.DOTALL)
                if json_match:
                    return json.loads(json_match.group())
                else:
                    raise APIError("Could not parse JSON from quality assessment response")
                    
        except (RateLimitError, APIError) as e:
            raise e
        except Exception as e:
            raise APIError(f"Unexpected error in quality assessment: {str(e)}")


class RateLimitError(Exception):
    """Raised when API rate limit is exceeded"""
    pass


class APIError(Exception):
    """Raised when API request fails"""
    pass
