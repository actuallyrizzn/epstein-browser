"""
Configuration management for the Venice SDK.
"""

import os
from typing import Optional
from dotenv import load_dotenv


class Config:
    """Configuration class for the Venice SDK."""

    def __init__(
        self,
        api_key: str,
        base_url: Optional[str] = None,
        default_model: Optional[str] = None,
        timeout: Optional[int] = None,
        max_retries: Optional[int] = None,
        retry_delay: Optional[int] = None
    ):
        """
        Initialize the configuration.

        Args:
            api_key: API key for authentication
            base_url: Optional base URL for the API
            default_model: Optional default model to use
            timeout: Optional request timeout in seconds
            max_retries: Optional maximum number of retries
            retry_delay: Optional delay between retries in seconds

        Raises:
            ValueError: If api_key is not provided
        """
        if not api_key:
            raise ValueError("API key must be provided")

        self.api_key = api_key
        self.base_url = base_url or "https://api.venice.ai/api/v1"
        self.default_model = default_model
        self.timeout = timeout or 30
        self.max_retries = max_retries or 3
        self.retry_delay = retry_delay or 1

    @property
    def headers(self) -> dict:
        """Get the default headers for API requests."""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }


def load_config(api_key: Optional[str] = None) -> Config:
    """
    Load configuration from environment variables or provided values.
    
    Args:
        api_key: Optional API key. If not provided, will be loaded from environment.
        
    Returns:
        Config: The loaded configuration.
        
    Raises:
        ValueError: If no API key is found.
    """
    # Load environment variables from .env file if it exists
    load_dotenv()
    
    # Get API key from parameter or environment
    api_key = api_key or os.getenv("VENICE_API_KEY")
    if not api_key:
        raise ValueError("API key must be provided")
    
    # Get other configuration values from environment
    base_url = os.getenv("VENICE_BASE_URL")
    default_model = os.getenv("VENICE_DEFAULT_MODEL")
    timeout = int(os.getenv("VENICE_TIMEOUT", "30"))
    max_retries = int(os.getenv("VENICE_MAX_RETRIES", "3"))
    retry_delay = int(os.getenv("VENICE_RETRY_DELAY", "1"))
    
    return Config(
        api_key=api_key,
        base_url=base_url,
        default_model=default_model,
        timeout=timeout,
        max_retries=max_retries,
        retry_delay=retry_delay
    ) 