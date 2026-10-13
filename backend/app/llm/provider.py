"""
LLM Provider abstraction for Tier 2 agentic AI.

Supports structured output generation for Fraud and Skeptic agents.
"""
import json
import logging
from abc import ABC, abstractmethod
from typing import Type, TypeVar, Optional
from pydantic import BaseModel

from app.core.config import settings

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""
    
    @abstractmethod
    async def generate_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        response_schema: Type[T],
        timeout: float
    ) -> T:
        """
        Generate structured output from LLM.
        
        Args:
            system_prompt: System instructions
            user_prompt: User request
            response_schema: Pydantic model for response validation
            timeout: Request timeout in seconds
            
        Returns:
            Validated Pydantic model instance
            
        Raises:
            TimeoutError: Request exceeded timeout
            ValueError: Invalid response or schema validation failed
            RuntimeError: Provider error
        """
        pass


class OpenAIProvider(LLMProvider):
    """OpenAI provider implementation."""
    
    def __init__(self, api_key: str, model: str, max_retries: int = 2):
        """Initialize OpenAI provider."""
        self.api_key = api_key
        self.model = model
        self.max_retries = max_retries
        self._client = None
    
    def _get_client(self):
        """Lazy-load OpenAI client."""
        if self._client is None:
            try:
                import openai
                self._client = openai.AsyncOpenAI(api_key=self.api_key)
            except ImportError:
                raise RuntimeError(
                    "OpenAI package not installed. Install with: pip install openai"
                )
        return self._client
    
    async def generate_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        response_schema: Type[T],
        timeout: float
    ) -> T:
        """Generate structured output using OpenAI JSON mode."""
        client = self._get_client()
        
        # Build schema instructions for JSON mode
        schema_description = self._schema_to_description(response_schema)
        enhanced_system = f"{system_prompt}\n\nYou MUST respond with valid JSON matching this schema:\n{schema_description}"
        
        try:
            response = await client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": enhanced_system},
                    {"role": "user", "content": user_prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.0,  # Deterministic for consistency
                timeout=timeout,
                max_tokens=settings.tier2_max_output_tokens
            )
            
            # Parse and validate
            content = response.choices[0].message.content
            if not content:
                raise ValueError("Empty response from LLM")
            
            data = json.loads(content)
            return response_schema(**data)
            
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON from LLM: {e}")
            raise ValueError(f"LLM returned invalid JSON: {e}")
        except Exception as e:
            logger.error(f"OpenAI provider error: {e}")
            raise RuntimeError(f"LLM request failed: {e}")
    
    def _schema_to_description(self, schema: Type[BaseModel]) -> str:
        """Convert Pydantic schema to JSON schema description."""
        return json.dumps(schema.model_json_schema(), indent=2)


class MockLLMProvider(LLMProvider):
    """Mock provider for testing without real LLM API."""
    
    async def generate_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        response_schema: Type[T],
        timeout: float
    ) -> T:
        """Return empty/minimal valid response for testing."""
        # Create minimal valid instance based on schema
        if "Finding" in response_schema.__name__:
            # Return empty findings list wrapped in expected structure
            return response_schema(findings=[])  # type: ignore
        elif "Challenge" in response_schema.__name__:
            return response_schema(challenges=[])  # type: ignore
        else:
            # Try to instantiate with defaults
            return response_schema()


def get_llm_provider() -> Optional[LLMProvider]:
    """
    Get configured LLM provider instance.
    
    Returns None if Tier 2 is disabled or provider unavailable.
    """
    if not settings.tier2_enabled:
        logger.info("Tier 2 (agentic AI) is disabled")
        return None
    
    if settings.tier2_provider == "openai":
        if not settings.tier2_api_key:
            logger.warning("Tier 2 enabled but no API key configured")
            return None
        
        logger.info(f"Initializing OpenAI provider with model {settings.tier2_model}")
        return OpenAIProvider(
            api_key=settings.tier2_api_key,
            model=settings.tier2_model,
            max_retries=settings.tier2_max_retries
        )
    
    elif settings.tier2_provider == "mock":
        logger.info("Using mock LLM provider for testing")
        return MockLLMProvider()
    
    else:
        logger.error(f"Unknown Tier 2 provider: {settings.tier2_provider}")
        return None
