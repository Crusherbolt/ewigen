"""
OpenRouter API Client
Unified interface to access multiple LLM providers (OpenAI, Anthropic, Google, etc.)
"""
import os
import requests
from typing import Dict, List, Optional, Any
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ModelConfig:
    """Configuration for different models"""
    name: str
    provider: str
    context_length: int
    cost_per_1k_tokens: float
    supports_streaming: bool


class OpenRouterClient:
    """
    Client for OpenRouter API
    Provides unified access to multiple LLM providers
    """
    
    # Available models with their configurations
    MODELS = {
        # OpenAI Models
        "gpt-4-turbo": ModelConfig("openai/gpt-4-turbo", "openai", 128000, 0.01, True),
        "gpt-4": ModelConfig("openai/gpt-4", "openai", 8192, 0.03, True),
        "gpt-3.5-turbo": ModelConfig("openai/gpt-3.5-turbo", "openai", 16385, 0.0015, True),
        
        # Anthropic Models
        "claude-3-opus": ModelConfig("anthropic/claude-3-opus", "anthropic", 200000, 0.015, True),
        "claude-3-sonnet": ModelConfig("anthropic/claude-3-sonnet", "anthropic", 200000, 0.003, True),
        "claude-3-haiku": ModelConfig("anthropic/claude-3-haiku", "anthropic", 200000, 0.00025, True),
        
        # Google Models
        "gemini-pro": ModelConfig("google/gemini-pro", "google", 32768, 0.00025, True),
        "gemini-pro-vision": ModelConfig("google/gemini-pro-vision", "google", 16384, 0.00025, True),
        
        # Meta Models
        "llama-3-70b": ModelConfig("meta-llama/llama-3-70b-instruct", "meta", 8192, 0.0007, True),
        "llama-3-8b": ModelConfig("meta-llama/llama-3-8b-instruct", "meta", 8192, 0.0001, True),
        
        # Mistral Models
        "mixtral-8x7b": ModelConfig("mistralai/mixtral-8x7b-instruct", "mistral", 32768, 0.0006, True),
        "mistral-7b": ModelConfig("mistralai/mistral-7b-instruct", "mistral", 8192, 0.0001, True),
        
        # Free Models (for testing)
        "free-gpt-3.5": ModelConfig("openai/gpt-3.5-turbo", "openai", 4096, 0.0, True),
    }
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        default_model: str = "gpt-3.5-turbo",
        base_url: str = "https://openrouter.ai/api/v1"
    ):
        """
        Initialize OpenRouter client
        
        Args:
            api_key: OpenRouter API key (or set OPENROUTER_API_KEY env var)
            default_model: Default model to use
            base_url: OpenRouter API base URL
        """
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        if not self.api_key:
            logger.warning("No OpenRouter API key provided. Set OPENROUTER_API_KEY environment variable.")
        
        self.default_model = default_model
        self.base_url = base_url
        
        # Site information for OpenRouter
        self.site_url = os.getenv("SITE_URL", "http://localhost:3000")
        self.site_name = os.getenv("SITE_NAME", "Virtual Environment Platform")
        
        logger.info(f"Initialized OpenRouter client with default model: {default_model}")
    
    def get_model_config(self, model_name: str) -> ModelConfig:
        """Get configuration for a model"""
        if model_name in self.MODELS:
            return self.MODELS[model_name]
        raise ValueError(f"Unknown model: {model_name}. Available: {list(self.MODELS.keys())}")
    
    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        stream: bool = False,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Create a chat completion
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            model: Model to use (defaults to default_model)
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            stream: Whether to stream the response
            **kwargs: Additional parameters
            
        Returns:
            Response dictionary
        """
        model = model or self.default_model
        model_config = self.get_model_config(model)
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "HTTP-Referer": self.site_url,
            "X-Title": self.site_name,
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": model_config.name,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": stream,
            **kwargs
        }
        
        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
                stream=stream
            )
            response.raise_for_status()
            
            if stream:
                return self._handle_stream(response)
            else:
                return response.json()
                
        except requests.exceptions.RequestException as e:
            logger.error(f"OpenRouter API error: {e}")
            raise
    
    def _handle_stream(self, response):
        """Handle streaming response"""
        for line in response.iter_lines():
            if line:
                line = line.decode('utf-8')
                if line.startswith('data: '):
                    data = line[6:]
                    if data != '[DONE]':
                        yield data
    
    def generate_text(
        self,
        prompt: str,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        system_prompt: Optional[str] = None
    ) -> str:
        """
        Generate text from a prompt
        
        Args:
            prompt: Input prompt
            model: Model to use
            temperature: Sampling temperature
            max_tokens: Maximum tokens
            system_prompt: Optional system prompt
            
        Returns:
            Generated text
        """
        messages = []
        
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        messages.append({"role": "user", "content": prompt})
        
        response = self.chat_completion(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens
        )
        
        return response['choices'][0]['message']['content']
    
    def list_models(self) -> List[Dict[str, Any]]:
        """
        List available models
        
        Returns:
            List of model information
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
        }
        
        try:
            response = requests.get(
                f"{self.base_url}/models",
                headers=headers
            )
            response.raise_for_status()
            return response.json()['data']
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error listing models: {e}")
            return []
    
    def get_usage_stats(self) -> Dict[str, Any]:
        """
        Get usage statistics
        
        Returns:
            Usage statistics
        """
        # OpenRouter doesn't have a direct usage endpoint
        # This would need to be tracked separately
        return {
            "total_requests": 0,
            "total_tokens": 0,
            "total_cost": 0.0
        }


class MultiProviderLLM:
    """
    Multi-provider LLM client supporting OpenRouter, Azure, GCP, and local models
    """
    
    def __init__(
        self,
        provider: str = "openrouter",
        **kwargs
    ):
        """
        Initialize multi-provider LLM client
        
        Args:
            provider: Provider to use (openrouter, azure, gcp, local)
            **kwargs: Provider-specific configuration
        """
        self.provider = provider
        
        if provider == "openrouter":
            self.client = OpenRouterClient(**kwargs)
        elif provider == "azure":
            self.client = self._init_azure(**kwargs)
        elif provider == "gcp":
            self.client = self._init_gcp(**kwargs)
        elif provider == "local":
            self.client = self._init_local(**kwargs)
        else:
            raise ValueError(f"Unknown provider: {provider}")
        
        logger.info(f"Initialized multi-provider LLM with provider: {provider}")
    
    def _init_azure(self, **kwargs):
        """Initialize Azure OpenAI client"""
        try:
            from openai import AzureOpenAI
            
            return AzureOpenAI(
                api_key=kwargs.get('api_key') or os.getenv("AZURE_OPENAI_API_KEY"),
                api_version=kwargs.get('api_version', "2024-02-15-preview"),
                azure_endpoint=kwargs.get('endpoint') or os.getenv("AZURE_OPENAI_ENDPOINT")
            )
        except ImportError:
            logger.error("openai package not installed. Install with: pip install openai")
            raise
    
    def _init_gcp(self, **kwargs):
        """Initialize GCP Vertex AI client"""
        try:
            from google.cloud import aiplatform
            
            project_id = kwargs.get('project_id') or os.getenv("GCP_PROJECT_ID")
            location = kwargs.get('location', 'us-central1')
            
            aiplatform.init(project=project_id, location=location)
            
            return aiplatform
        except ImportError:
            logger.error("google-cloud-aiplatform not installed. Install with: pip install google-cloud-aiplatform")
            raise
    
    def _init_local(self, **kwargs):
        """Initialize local Ollama client"""
        try:
            import ollama
            
            return ollama.Client(
                host=kwargs.get('host', 'http://localhost:11434')
            )
        except ImportError:
            logger.error("ollama package not installed. Install with: pip install ollama")
            raise
    
    def generate(
        self,
        prompt: str,
        model: Optional[str] = None,
        **kwargs
    ) -> str:
        """
        Generate text (unified interface)
        
        Args:
            prompt: Input prompt
            model: Model to use
            **kwargs: Additional parameters
            
        Returns:
            Generated text
        """
        if self.provider == "openrouter":
            return self.client.generate_text(prompt, model=model, **kwargs)
        
        elif self.provider == "azure":
            response = self.client.chat.completions.create(
                model=model or "gpt-35-turbo",
                messages=[{"role": "user", "content": prompt}],
                **kwargs
            )
            return response.choices[0].message.content
        
        elif self.provider == "gcp":
            from vertexai.preview.generative_models import GenerativeModel
            
            model_obj = GenerativeModel(model or "gemini-pro")
            response = model_obj.generate_content(prompt)
            return response.text
        
        elif self.provider == "local":
            response = self.client.chat(
                model=model or "llama3",
                messages=[{"role": "user", "content": prompt}]
            )
            return response['message']['content']
        
        else:
            raise ValueError(f"Unknown provider: {self.provider}")


# Example usage
if __name__ == "__main__":
    # OpenRouter example
    client = OpenRouterClient()
    
    response = client.generate_text(
        prompt="Explain quantum computing in simple terms",
        model="gpt-3.5-turbo",
        max_tokens=200
    )
    print(response)
    
    # Multi-provider example
    llm = MultiProviderLLM(provider="openrouter")
    response = llm.generate("What is machine learning?")
    print(response)

# Made with Bob
