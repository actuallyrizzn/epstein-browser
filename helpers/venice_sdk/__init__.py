"""
Venice SDK for Python.

This module provides a Python interface to the Venice API.
"""

from .client import HTTPClient
from .config import Config, load_config
from .errors import (
    VeniceError,
    VeniceAPIError,
    VeniceConnectionError,
    RateLimitError,
    UnauthorizedError,
    InvalidRequestError,
    ModelNotFoundError,
    CharacterNotFoundError,
)
from .models import (
    Model,
    ModelCapabilities,
    ModelsAPI,
    get_models,
    get_model_by_id,
    get_text_models,
)
from .chat import (
    Message,
    Choice,
    Usage,
    ChatCompletion,
    ChatAPI,
)

__version__ = "0.1.0"

__all__ = [
    "HTTPClient",
    "Config",
    "load_config",
    "VeniceError",
    "VeniceAPIError",
    "VeniceConnectionError",
    "RateLimitError",
    "UnauthorizedError",
    "InvalidRequestError",
    "ModelNotFoundError",
    "CharacterNotFoundError",
    "Model",
    "ModelCapabilities",
    "ModelsAPI",
    "get_models",
    "get_model_by_id",
    "get_text_models",
    "Message",
    "Choice",
    "Usage",
    "ChatCompletion",
    "ChatAPI",
] 