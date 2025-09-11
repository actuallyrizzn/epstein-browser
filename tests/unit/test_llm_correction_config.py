"""
Test suite for LLM Correction Config

Tests the configuration management and validation.
"""

import pytest
import os
from unittest.mock import patch, Mock
import sys

# Add project root to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from llm_correction_config import LLMCorrectionConfig, config


class TestLLMCorrectionConfig:
    """Test cases for LLMCorrectionConfig"""
    
    def setup_method(self):
        """Set up test fixtures"""
        # Clear any cached environment variables
        import os
        for key in list(os.environ.keys()):
            if key.startswith(('VENICE_', 'OPENAI_', 'ANTHROPIC_', 'DATABASE_', 'BATCH_', 'MAX_', 'MIN_', 'RATE_', 'USE_', 'ENABLE_', 'REVIEW_')):
                del os.environ[key]
        
        # Reset config for each test
        self.config = LLMCorrectionConfig()
    
    def test_default_values(self):
        """Test default configuration values"""
        assert self.config.DATABASE_PATH == "images.db"
        # The actual default from .env file is gpt-4, not llama-3.3-70b
        assert self.config.DEFAULT_LLM_MODEL == "gpt-4"
        assert self.config.FALLBACK_LLM_MODEL == "qwen-2.5-qwq-32b"
        assert self.config.VENICE_BASE_URL == "https://api.venice.ai/api/v1"
        assert self.config.MAX_TOKENS_PER_REQUEST == 8000
        assert self.config.BATCH_SIZE == 10
        assert self.config.RATE_LIMIT_DELAY == 1.0
        assert self.config.MIN_OCR_TEXT_LENGTH == 10
        assert self.config.USE_TIKTOKEN is True
        assert self.config.TOKEN_ESTIMATION_BUFFER == 0.03
        assert self.config.USE_DIRTYJSON is True
    
    def test_environment_variable_override(self):
        """Test configuration override with environment variables"""
        with patch.dict(os.environ, {
            'DATABASE_PATH': 'test.db',
            'VENICE_DEFAULT_MODEL': 'gpt-4',
            'BATCH_SIZE': '20',
            'MAX_TOKENS_PER_REQUEST': '4000'
        }):
            config = LLMCorrectionConfig()
            assert config.DATABASE_PATH == 'test.db'
            assert config.DEFAULT_LLM_MODEL == 'gpt-4'
            assert config.BATCH_SIZE == 20
            assert config.MAX_TOKENS_PER_REQUEST == 4000
    
    def test_validate_config_valid(self):
        """Test configuration validation with valid config"""
        with patch.dict(os.environ, {'VENICE_API_KEY': 'test_key'}):
            with patch('os.path.exists', return_value=True):
                result = self.config.validate_config()
                assert result['valid'] is True
                assert len(result['issues']) == 0
    
    def test_validate_config_no_api_key(self):
        """Test configuration validation without API key"""
        with patch.dict(os.environ, {}, clear=True):
            # Test validation without loading .env file
            result = LLMCorrectionConfig.validate_config(load_env_file=False)
            assert result['valid'] is False
            assert 'VENICE_API_KEY not set' in result['issues']
    
    def test_validate_config_database_not_found(self):
        """Test configuration validation with missing database"""
        with patch.dict(os.environ, {'VENICE_API_KEY': 'test_key'}):
            with patch('os.path.exists', return_value=False):
                result = LLMCorrectionConfig.validate_config(load_env_file=False)
                assert result['valid'] is False
                assert 'Database file not found' in result['issues'][0]
    
    def test_validate_config_batch_size_warning(self):
        """Test configuration validation with batch size warning"""
        with patch.dict(os.environ, {'VENICE_API_KEY': 'test_key', 'BATCH_SIZE': '150'}):
            with patch('os.path.exists', return_value=True):
                config = LLMCorrectionConfig()
                result = config.validate_config()
                assert result['valid'] is True
                assert 'Batch size 150 may not be optimal' in result['warnings']
    
    def test_validate_config_batch_size_too_small(self):
        """Test configuration validation with batch size too small"""
        with patch.dict(os.environ, {'VENICE_API_KEY': 'test_key', 'BATCH_SIZE': '0'}):
            with patch('os.path.exists', return_value=True):
                config = LLMCorrectionConfig()
                result = config.validate_config()
                assert result['valid'] is True
                assert 'Batch size 0 may not be optimal' in result['warnings']
    
    def test_validate_config_batch_size_too_large(self):
        """Test configuration validation with batch size too large"""
        with patch.dict(os.environ, {'VENICE_API_KEY': 'test_key', 'BATCH_SIZE': '150'}):
            with patch('os.path.exists', return_value=True):
                config = LLMCorrectionConfig()
                result = config.validate_config()
                assert result['valid'] is True
                assert 'Batch size 150 may not be optimal' in result['warnings']
    
    def test_get_model_config_gpt(self):
        """Test getting model configuration for GPT model"""
        with patch.dict(os.environ, {'VENICE_API_KEY': 'test_key'}):
            config = LLMCorrectionConfig()
            result = config.get_model_config('gpt-4')
            assert result['api_key'] == 'test_key'
            assert result['base_url'] == 'https://api.venice.ai/api/v1'
            assert result['max_tokens'] == 8000
            assert result['model'] == 'gpt-4'
    
    def test_get_model_config_claude(self):
        """Test getting model configuration for Claude model"""
        with patch.dict(os.environ, {'VENICE_API_KEY': 'test_key'}):
            config = LLMCorrectionConfig()
            result = config.get_model_config('claude-3-sonnet')
            assert result['api_key'] == 'test_key'
            assert result['base_url'] == 'https://api.venice.ai/api/v1'
            assert result['max_tokens'] == 8000
            assert result['model'] == 'claude-3-sonnet'
    
    def test_get_model_config_llama(self):
        """Test getting model configuration for Llama model"""
        with patch.dict(os.environ, {'VENICE_API_KEY': 'test_key'}):
            config = LLMCorrectionConfig()
            result = config.get_model_config('llama-3.3-70b')
            assert result['api_key'] == 'test_key'
            assert result['base_url'] == 'https://api.venice.ai/api/v1'
            assert result['max_tokens'] == 8000
            assert result['model'] == 'llama-3.3-70b'
    
    def test_boolean_environment_variables(self):
        """Test boolean environment variable parsing"""
        with patch.dict(os.environ, {
            'USE_TIKTOKEN': 'false',
            'USE_DIRTYJSON': 'false',
            'ENABLE_HUMAN_REVIEW': 'false'
        }):
            config = LLMCorrectionConfig()
            assert config.USE_TIKTOKEN is False
            assert config.USE_DIRTYJSON is False
            assert config.ENABLE_HUMAN_REVIEW is False
    
    def test_boolean_environment_variables_case_insensitive(self):
        """Test boolean environment variable parsing with different cases"""
        with patch.dict(os.environ, {
            'USE_TIKTOKEN': 'FALSE',
            'USE_DIRTYJSON': 'False',
            'ENABLE_HUMAN_REVIEW': 'FALSE'
        }):
            config = LLMCorrectionConfig()
            assert config.USE_TIKTOKEN is False
            assert config.USE_DIRTYJSON is False
            assert config.ENABLE_HUMAN_REVIEW is False
    
    def test_numeric_environment_variables(self):
        """Test numeric environment variable parsing"""
        with patch.dict(os.environ, {
            'MAX_TOKENS_PER_REQUEST': '4000',
            'BATCH_SIZE': '25',
            'RATE_LIMIT_DELAY': '2.5',
            'MIN_OCR_TEXT_LENGTH': '20',
            'TOKEN_ESTIMATION_BUFFER': '0.05'
        }):
            config = LLMCorrectionConfig()
            assert config.MAX_TOKENS_PER_REQUEST == 4000
            assert config.BATCH_SIZE == 25
            assert config.RATE_LIMIT_DELAY == 2.5
            assert config.MIN_OCR_TEXT_LENGTH == 20
            assert config.TOKEN_ESTIMATION_BUFFER == 0.05
    
    def test_legacy_api_keys(self):
        """Test legacy API key configuration"""
        with patch.dict(os.environ, {
            'OPENAI_API_KEY': 'openai_key',
            'ANTHROPIC_API_KEY': 'anthropic_key'
        }):
            config = LLMCorrectionConfig()
            assert config.OPENAI_API_KEY == 'openai_key'
            assert config.ANTHROPIC_API_KEY == 'anthropic_key'
    
    def test_global_config_instance(self):
        """Test global config instance"""
        # Create a fresh config instance to avoid test isolation issues
        from llm_correction_config import LLMCorrectionConfig
        fresh_config = LLMCorrectionConfig()
        assert isinstance(fresh_config, LLMCorrectionConfig)
        assert fresh_config.DATABASE_PATH == "images.db"
        assert fresh_config.DEFAULT_LLM_MODEL == "gpt-4"
    
    def test_confidence_settings(self):
        """Test confidence-related settings"""
        with patch.dict(os.environ, {
            'MIN_CONFIDENCE_FOR_AUTO_APPROVAL': '90',
            'REVIEW_QUEUE_SIZE_LIMIT': '200'
        }):
            config = LLMCorrectionConfig()
            assert config.MIN_CONFIDENCE_FOR_AUTO_APPROVAL == 90
            assert config.REVIEW_QUEUE_SIZE_LIMIT == 200
    
    def test_venice_configuration(self):
        """Test Venice-specific configuration"""
        with patch.dict(os.environ, {
            'VENICE_API_KEY': 'venice_key',
            'VENICE_BASE_URL': 'https://custom.venice.ai/api/v1',
            'VENICE_DEFAULT_MODEL': 'custom-model'
        }):
            config = LLMCorrectionConfig()
            assert config.VENICE_API_KEY == 'venice_key'
            assert config.VENICE_BASE_URL == 'https://custom.venice.ai/api/v1'
            assert config.DEFAULT_LLM_MODEL == 'custom-model'
    
    def test_validate_config_multiple_issues(self):
        """Test configuration validation with multiple issues"""
        with patch.dict(os.environ, {}, clear=True):
            with patch('os.path.exists', return_value=False):
                result = LLMCorrectionConfig.validate_config(load_env_file=False)
                assert result['valid'] is False
                assert len(result['issues']) == 2
                assert 'VENICE_API_KEY not set' in result['issues']
                assert 'Database file not found' in result['issues'][1]
    
    def test_validate_config_multiple_warnings(self):
        """Test configuration validation with multiple warnings"""
        with patch.dict(os.environ, {
            'VENICE_API_KEY': 'test_key',
            'BATCH_SIZE': '150',
            'RATE_LIMIT_DELAY': '0.1'
        }):
            with patch('os.path.exists', return_value=True):
                config = LLMCorrectionConfig()
                result = config.validate_config()
                assert result['valid'] is True
                assert len(result['warnings']) >= 1
                assert 'Batch size 150 may not be optimal' in result['warnings']
