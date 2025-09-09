"""
Model discovery and management for the Venice SDK.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional

from .client import HTTPClient


@dataclass
class ModelCapabilities:
    """Model capabilities."""
    supports_function_calling: bool
    supports_web_search: bool
    available_context_tokens: int


@dataclass
class Model:
    """Model information."""
    id: str
    name: str
    type: str
    capabilities: ModelCapabilities
    description: str


class ModelsAPI:
    """API client for model-related endpoints."""
    
    def __init__(self, client: HTTPClient):
        """
        Initialize the models API client.
        
        Args:
            client: HTTP client for making requests
        """
        self.client = client
    
    def list(self) -> List[Dict]:
        """
        Get a list of available models.
        
        Returns:
            List of model data
            
        Raises:
            VeniceAPIError: If the request fails
        """
        response = self.client.get("models")
        return response.json()["data"]
    
    def get(self, model_id: str) -> Dict:
        """
        Get a specific model by ID.
        
        Args:
            model_id: The ID of the model to get
            
        Returns:
            Model data
            
        Raises:
            VeniceAPIError: If the model is not found or request fails
        """
        models = self.list()
        for model in models:
            if model["id"] == model_id:
                return model
        raise VeniceAPIError(f"Model {model_id} not found", status_code=404)
    
    def validate(self, model_id: str) -> bool:
        """
        Validate that a model exists.
        
        Args:
            model_id: The ID of the model to validate
            
        Returns:
            True if the model exists, False otherwise
        """
        try:
            self.get(model_id)
            return True
        except Exception:
            return False


def get_models(client: Optional[HTTPClient] = None) -> List[Model]:
    """
    Get a list of available models.
    
    Args:
        client: Optional HTTPClient instance. If not provided, a new one will be created.
        
    Returns:
        List of available models.
        
    Raises:
        VeniceAPIError: If the request fails.
    """
    client = client or HTTPClient()
    models_api = ModelsAPI(client)
    models_data = models_api.list()
    
    models = []
    for model_data in models_data:
        capabilities = ModelCapabilities(
            supports_function_calling=model_data["model_spec"]["capabilities"]["supportsFunctionCalling"],
            supports_web_search=model_data["model_spec"]["capabilities"]["supportsWebSearch"],
            available_context_tokens=model_data["model_spec"]["availableContextTokens"]
        )
        
        model = Model(
            id=model_data["id"],
            name=model_data["id"],  # Using ID as name since there's no separate name field
            type=model_data["type"],
            capabilities=capabilities,
            description=model_data.get("description", model_data["model_spec"].get("modelSource", "No description available"))
        )
        models.append(model)
    
    return models


def get_model_by_id(model_id: str, client: Optional[HTTPClient] = None) -> Optional[Model]:
    """
    Get a specific model by ID.
    
    Args:
        model_id: The ID of the model to get
        client: Optional HTTPClient instance. If not provided, a new one will be created.
        
    Returns:
        Model if found, None otherwise.
    """
    client = client or HTTPClient()
    models_api = ModelsAPI(client)
    model_data = models_api.get(model_id)
    
    capabilities = ModelCapabilities(
        supports_function_calling=model_data["model_spec"]["capabilities"]["supportsFunctionCalling"],
        supports_web_search=model_data["model_spec"]["capabilities"]["supportsWebSearch"],
        available_context_tokens=model_data["model_spec"]["availableContextTokens"]
    )
    
    return Model(
        id=model_data["id"],
        name=model_data["id"],  # Using ID as name since there's no separate name field
        type=model_data["type"],
        capabilities=capabilities,
        description=model_data.get("description", model_data["model_spec"].get("modelSource", "No description available"))
    )


def get_text_models(client: Optional[HTTPClient] = None) -> List[Model]:
    """
    Get a list of available text models.
    
    Args:
        client: Optional HTTPClient instance. If not provided, a new one will be created.
        
    Returns:
        List of available text models.
    """
    return [model for model in get_models(client) if model.type == "text"] 