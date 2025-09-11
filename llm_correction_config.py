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
    
    def __init__(self, load_env_file=True):
        """Initialize configuration with current environment variables"""
        # Reload environment variables on each instantiation
        if load_env_file:
            load_dotenv()
        
        # Database settings
        self.DATABASE_PATH = os.getenv("DATABASE_PATH", "images.db")
        
        # LLM API Configuration (using Venice)
        self.DEFAULT_LLM_MODEL = os.getenv("VENICE_DEFAULT_MODEL", "llama-3.3-70b")
        self.FALLBACK_LLM_MODEL = os.getenv("FALLBACK_LLM_MODEL", "qwen-2.5-qwq-32b")
        
        # Venice API Configuration
        self.VENICE_API_KEY = os.getenv("VENICE_API_KEY")
        self.VENICE_BASE_URL = os.getenv("VENICE_BASE_URL", "https://api.venice.ai/api/v1")
        
        # Legacy API Keys (for fallback if needed)
        self.OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
        self.ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
        
        # API Handling
        self.MAX_TOKENS_PER_REQUEST = int(os.getenv("MAX_TOKENS_PER_REQUEST", "8000"))
        self.BATCH_SIZE = int(os.getenv("BATCH_SIZE", "10"))
        
        # Correction Settings
        self.MIN_CONFIDENCE_FOR_AUTO_APPROVAL = int(os.getenv("MIN_CONFIDENCE_FOR_AUTO_APPROVAL", "80"))
        self.REVIEW_QUEUE_SIZE_LIMIT = int(os.getenv("REVIEW_QUEUE_SIZE_LIMIT", "100"))
        self.ENABLE_HUMAN_REVIEW = os.getenv("ENABLE_HUMAN_REVIEW", "true").lower() == "true"
        
        # Token Counting
        self.USE_TIKTOKEN = os.getenv("USE_TIKTOKEN", "true").lower() == "true"
        self.TOKEN_ESTIMATION_BUFFER = float(os.getenv("TOKEN_ESTIMATION_BUFFER", "0.03"))
        
        # JSON Parsing
        self.USE_DIRTYJSON = os.getenv("USE_DIRTYJSON", "true").lower() == "true"
        
        # Processing Settings
        self.RATE_LIMIT_DELAY = float(os.getenv("RATE_LIMIT_DELAY", "1.0"))  # seconds between requests
        self.MIN_OCR_TEXT_LENGTH = int(os.getenv("MIN_OCR_TEXT_LENGTH", "10"))
    
    @classmethod
    def validate_config(cls, load_env_file=True) -> Dict[str, Any]:
        """Validate configuration and return validation results"""
        config = cls(load_env_file=load_env_file)
        issues = []
        warnings = []
        
        # Check required settings
        if not config.VENICE_API_KEY:
            issues.append("VENICE_API_KEY not set")
        
        if not os.path.exists(config.DATABASE_PATH):
            issues.append(f"Database file not found: {config.DATABASE_PATH}")
        
        # Check batch size
        if config.BATCH_SIZE < 1 or config.BATCH_SIZE > 100:
            warnings.append(f"Batch size {config.BATCH_SIZE} may not be optimal")
        
        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "warnings": warnings
        }
    
    def get_model_config(self, model: str) -> Dict[str, Any]:
        """Get configuration for a specific model"""
        return {
            "model": model,
            "api_key": self.VENICE_API_KEY,
            "base_url": self.VENICE_BASE_URL,
            "max_tokens": self.MAX_TOKENS_PER_REQUEST
        }


# Global config instance for backward compatibility
config = LLMCorrectionConfig()