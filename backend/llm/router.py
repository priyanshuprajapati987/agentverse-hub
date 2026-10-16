"""Multi-Provider LLM Router"""

import os
from typing import Optional, AsyncGenerator
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

@dataclass
class LLMResponse:
    content: str
    model: str
    provider: str
    tokens_used: int = 0
    finish_reason: str = "stop"


class LLMRouter:
    """Route requests to multiple LLM providers"""
    
    def __init__(self):
        self.providers = {}
        self._init_providers()
    
    def _init_providers(self):
        """Initialize available providers"""
        # Only Ollama for now (local models)
        if os.getenv("OLLAMA_URL"):
            from llm.providers.ollama_provider import OllamaProvider
            self.providers["ollama"] = OllamaProvider()
    
    async def generate(
        self,
        model: str,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        """Generate response from specified model"""
        provider_name = self._get_provider(model)
        
        if provider_name not in self.providers:
            # Fallback to first available provider
            if self.providers:
                provider_name = list(self.providers.keys())[0]
            else:
                raise ValueError("No LLM providers available")
        
        provider = self.providers[provider_name]
        return await provider.generate(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
    
    def _get_provider(self, model: str) -> str:
        """Extract provider from model name"""
        model_lower = model.lower()
        
        if model_lower.startswith(("gpt-", "o1", "o3", "chatgpt")):
            return "openai"
        elif model_lower.startswith(("claude", "anthropic")):
            return "anthropic"
        elif model_lower.startswith(("gemini", "palm")):
            return "google"
        elif any(x in model_lower for x in ["llama", "mistral", "qwen", "codellama", "phi", "gemma", "deepseek"]):
            return "ollama"
        elif "ollama" in self.providers:
            return "ollama"
        
        return "openai"
    
    def list_models(self) -> dict:
        """List all available models"""
        models = {
            "openai": ["gpt-4", "gpt-4-turbo", "gpt-3.5-turbo"],
            "anthropic": ["claude-3-opus", "claude-3-sonnet", "claude-3-haiku"],
            "google": ["gemini-pro", "gemini-flash"],
            "ollama": ["llama3.2", "llama3.1", "mistral", "qwen3", "codellama"],
        }
        
        available = {}
        for provider, model_list in models.items():
            if provider in self.providers:
                available[provider] = model_list
        
        return available


_router: Optional[LLMRouter] = None

def get_router() -> LLMRouter:
    global _router
    if _router is None:
        _router = LLMRouter()
    return _router
