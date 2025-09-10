"""
LLM Correction Configuration

Configuration settings for the LLM Correction Pass system.
"""

import os
from typing import Dict, Any

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv not available, use system environment variables


class LLMCorrectionConfig:
    """Configuration for LLM correction system"""
    
    # Database settings
    DATABASE_PATH = os.getenv("DATABASE_PATH", "images.db")
    
    # LLM API Configuration (using Venice)
    DEFAULT_LLM_MODEL = os.getenv("VENICE_DEFAULT_MODEL", "llama-3.3-70b")
    FALLBACK_LLM_MODEL = os.getenv("FALLBACK_LLM_MODEL", "qwen-2.5-qwq-32b")
    
    # Venice API Configuration
    VENICE_API_KEY = os.getenv("VENICE_API_KEY")
    VENICE_BASE_URL = os.getenv("VENICE_BASE_URL", "https://api.venice.ai/api/v1")
    
    # Legacy API Keys (for fallback if needed)
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
    
    # API Handling
    MAX_TOKENS_PER_REQUEST = int(os.getenv("MAX_TOKENS_PER_REQUEST", "8000"))
    BATCH_SIZE = int(os.getenv("BATCH_SIZE", "10"))
    
    # Correction Settings
    MIN_CONFIDENCE_FOR_AUTO_APPROVAL = int(os.getenv("MIN_CONFIDENCE_FOR_AUTO_APPROVAL", "80"))
    REVIEW_QUEUE_SIZE_LIMIT = int(os.getenv("REVIEW_QUEUE_SIZE_LIMIT", "100"))
    ENABLE_HUMAN_REVIEW = os.getenv("ENABLE_HUMAN_REVIEW", "true").lower() == "true"
    
    # Token Counting
    USE_TIKTOKEN = os.getenv("USE_TIKTOKEN", "true").lower() == "true"
    TOKEN_ESTIMATION_BUFFER = float(os.getenv("TOKEN_ESTIMATION_BUFFER", "0.03"))
    
    # JSON Parsing
    USE_DIRTYJSON = os.getenv("USE_DIRTYJSON", "true").lower() == "true"
    
    # Processing Settings
    RATE_LIMIT_DELAY = float(os.getenv("RATE_LIMIT_DELAY", "1.0"))  # seconds between requests
    MIN_OCR_TEXT_LENGTH = int(os.getenv("MIN_OCR_TEXT_LENGTH", "10"))
    
    @classmethod
    def validate_config(cls) -> Dict[str, Any]:
        """Validate configuration and return status"""
        issues = []
        warnings = []
        
        # Check Venice API key
        if not cls.VENICE_API_KEY:
            issues.append("VENICE_API_KEY not set")
        
        # Check database
        if not os.path.exists(cls.DATABASE_PATH):
            issues.append(f"Database file not found: {cls.DATABASE_PATH}")
        
        # Check batch size
        if cls.BATCH_SIZE < 1 or cls.BATCH_SIZE > 100:
            warnings.append(f"Batch size {cls.BATCH_SIZE} may not be optimal")
        
        
        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "warnings": warnings
        }
    
    @classmethod
    def get_model_config(cls, model: str) -> Dict[str, Any]:
        """Get configuration for specific model using Venice"""
        return {
            "api_key": cls.VENICE_API_KEY,
            "base_url": cls.VENICE_BASE_URL,
            "max_tokens": cls.MAX_TOKENS_PER_REQUEST,
            "temperature": 0.1,
            "model": model
        }


# Global config instance
config = LLMCorrectionConfig()
