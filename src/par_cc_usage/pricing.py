"""Pricing functionality for Claude models using LiteLLM data."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, NamedTuple

import aiohttp
from pydantic import BaseModel, field_validator

logger = logging.getLogger(__name__)

# LiteLLM pricing data URL
LITELLM_PRICING_URL = "https://raw.githubusercontent.com/BerriAI/litellm/main/model_prices_and_context_window.json"

# Default timeout for HTTP requests
DEFAULT_TIMEOUT = 10


class ModelPricing(BaseModel):
    """Model pricing information."""

    input_cost_per_token: float | None = None
    output_cost_per_token: float | None = None
    cache_creation_input_token_cost: float | None = None
    cache_read_input_token_cost: float | None = None

    @field_validator(
        "input_cost_per_token",
        "output_cost_per_token",
        "cache_creation_input_token_cost",
        "cache_read_input_token_cost",
        mode="before",
    )
    @classmethod
    def validate_costs(cls, v: Any) -> float | None:
        """Validate cost values."""
        if v is None:
            return None
        if isinstance(v, int | float):
            return float(v)
        if isinstance(v, str):
            try:
                return float(v)
            except ValueError:
                return None
        return None


class TokenCost(NamedTuple):
    """Token cost calculation result."""

    input_cost: float = 0.0
    output_cost: float = 0.0
    cache_creation_cost: float = 0.0
    cache_read_cost: float = 0.0
    total_cost: float = 0.0


class PricingCache:
    """Cache for model pricing information."""

    def __init__(self) -> None:
        """Initialize pricing cache."""
        self._cache: dict[str, ModelPricing] = {}
        self._loaded = False
        self._load_task: asyncio.Task[None] | None = None

    async def get_pricing(self, model_name: str) -> ModelPricing | None:
        """Get pricing for a model.

        Args:
            model_name: Model name to get pricing for

        Returns:
            ModelPricing object or None if not found
        """
        if not self._loaded:
            await self._ensure_loaded()

        return self._get_pricing_from_cache(model_name)

    def _get_pricing_from_cache(self, model_name: str) -> ModelPricing | None:
        """Get pricing from cache with fuzzy matching and fallbacks."""
        # Skip pricing for Unknown models
        if model_name.lower() in ("unknown", "none", "", "null"):
            return ModelPricing(
                input_cost_per_token=0.0,
                output_cost_per_token=0.0,
                cache_creation_input_token_cost=0.0,
                cache_read_input_token_cost=0.0,
            )

        # Direct match first
        if model_name in self._cache:
            return self._cache[model_name]

        # Try with various prefixes/suffixes for Claude models
        variations = [
            model_name,
            f"anthropic/{model_name}",
            f"claude-3-5-{model_name}",
            f"claude-3-{model_name}",
            f"claude-{model_name}",
        ]

        for variation in variations:
            if variation in self._cache:
                return self._cache[variation]

        # Try partial matching (case insensitive)
        model_lower = model_name.lower()
        for cached_model, pricing in self._cache.items():
            cached_lower = cached_model.lower()
            # Check if the model names have significant overlap
            if model_lower in cached_lower or cached_lower in model_lower:
                logger.debug(f"Using fuzzy match for {model_name}: {cached_model}")
                return pricing

        # Fallback: try to match based on model family
        fallback_pricing = self._get_fallback_pricing(model_name)
        if fallback_pricing:
            logger.debug(f"Using fallback pricing for {model_name}")
            return fallback_pricing

        return None

    def _get_fallback_pricing(self, model_name: str) -> ModelPricing | None:
        """Get fallback pricing based on model family."""
        model_lower = model_name.lower()

        # Common Claude model patterns and their fallbacks
        claude_fallbacks = [
            # Try common Claude model names as fallbacks
            ("opus", ["claude-3-opus-20240229", "anthropic/claude-3-opus-20240229"]),
            (
                "sonnet",
                ["claude-3-5-sonnet-20241022", "claude-3-sonnet-20240229", "anthropic/claude-3-5-sonnet-20241022"],
            ),
            ("haiku", ["claude-3-haiku-20240307", "anthropic/claude-3-haiku-20240307"]),
        ]

        for pattern, fallback_models in claude_fallbacks:
            if pattern in model_lower:
                for fallback_model in fallback_models:
                    if fallback_model in self._cache:
                        logger.debug(f"Using {pattern} fallback for {model_name}: {fallback_model}")
                        return self._cache[fallback_model]

        # If it's clearly a Claude model but we can't find pricing, use generic Claude pricing
        if any(keyword in model_lower for keyword in ["claude", "anthropic"]):
            # Try to find any Claude model as a fallback
            for cached_model, pricing in self._cache.items():
                if "claude" in cached_model.lower() and "sonnet" in cached_model.lower():
                    logger.debug(f"Using generic Claude fallback for {model_name}: {cached_model}")
                    return pricing

        return None

    async def _ensure_loaded(self) -> None:
        """Ensure pricing data is loaded."""
        if self._load_task is None:
            self._load_task = asyncio.create_task(self._load_pricing_data())
        await self._load_task

    async def _load_pricing_data(self) -> None:
        """Load pricing data from LiteLLM."""
        try:
            timeout = aiohttp.ClientTimeout(total=DEFAULT_TIMEOUT)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(LITELLM_PRICING_URL) as response:
                    if response.status == 200:
                        # Get the text content and manually parse as JSON to handle MIME type issues
                        text_content = await response.text()
                        try:
                            data = json.loads(text_content)
                            await self._parse_pricing_data(data)
                            self._loaded = True
                            logger.info(f"Loaded pricing data for {len(self._cache)} models")
                        except json.JSONDecodeError as e:
                            logger.warning(f"Failed to parse pricing JSON: {e}")
                            self._loaded = True  # Mark as loaded even if failed to prevent retries
                    else:
                        logger.warning(f"Failed to load pricing data: HTTP {response.status}")
                        self._loaded = True  # Mark as loaded even if failed to prevent retries
        except Exception as e:
            logger.warning(f"Failed to load pricing data: {e}")
            self._loaded = True  # Mark as loaded even if failed to prevent retries

    async def _parse_pricing_data(self, data: dict[str, Any]) -> None:
        """Parse pricing data from LiteLLM response."""
        for model_name, model_data in data.items():
            if isinstance(model_data, dict):
                try:
                    pricing = ModelPricing(**model_data)
                    self._cache[model_name] = pricing
                except Exception as e:
                    logger.debug(f"Failed to parse pricing for {model_name}: {e}")
                    continue


# Global pricing cache instance
_global_pricing_cache: PricingCache | None = None


async def get_pricing_cache() -> PricingCache:
    """Get the global pricing cache instance."""
    global _global_pricing_cache
    if _global_pricing_cache is None:
        _global_pricing_cache = PricingCache()
    return _global_pricing_cache


async def calculate_token_cost(
    model_name: str,
    input_tokens: int = 0,
    output_tokens: int = 0,
    cache_creation_tokens: int = 0,
    cache_read_tokens: int = 0,
) -> TokenCost:
    """Calculate cost for token usage.

    Args:
        model_name: Model name
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens
        cache_creation_tokens: Number of cache creation tokens
        cache_read_tokens: Number of cache read tokens

    Returns:
        TokenCost with breakdown of costs
    """
    # Handle edge cases
    if not model_name or model_name.lower() in ("unknown", "none", "", "null"):
        logger.debug(f"Skipping cost calculation for unknown model: {model_name}")
        return TokenCost()

    try:
        cache = await get_pricing_cache()
        pricing = await cache.get_pricing(model_name)

        if pricing is None:
            logger.warning(f"No pricing found for model: {model_name}")
            return TokenCost()

        input_cost = (pricing.input_cost_per_token or 0.0) * input_tokens
        output_cost = (pricing.output_cost_per_token or 0.0) * output_tokens
        cache_creation_cost = (pricing.cache_creation_input_token_cost or 0.0) * cache_creation_tokens
        cache_read_cost = (pricing.cache_read_input_token_cost or 0.0) * cache_read_tokens

        total_cost = input_cost + output_cost + cache_creation_cost + cache_read_cost

        logger.debug(f"Calculated cost for {model_name}: ${total_cost:.4f} (in:{input_tokens}, out:{output_tokens})")

        return TokenCost(
            input_cost=input_cost,
            output_cost=output_cost,
            cache_creation_cost=cache_creation_cost,
            cache_read_cost=cache_read_cost,
            total_cost=total_cost,
        )
    except Exception as e:
        logger.warning(f"Error calculating cost for model {model_name}: {e}")
        return TokenCost()


def format_cost(cost: float) -> str:
    """Format cost for display.

    Args:
        cost: Cost in dollars

    Returns:
        Formatted cost string
    """
    if cost == 0:
        return "$0.00"
    elif cost < 0.01:
        return f"${cost:.4f}"
    elif cost < 1:
        return f"${cost:.3f}"
    else:
        return f"${cost:.2f}"


async def debug_model_pricing(model_name: str) -> dict[str, Any]:
    """Debug pricing information for a model.

    Args:
        model_name: Model name to debug

    Returns:
        Dictionary with debugging information
    """
    cache = await get_pricing_cache()
    pricing = await cache.get_pricing(model_name)

    debug_info = {
        "model_name": model_name,
        "pricing_found": pricing is not None,
        "is_unknown_pattern": model_name.lower() in ("unknown", "none", "", "null"),
        "cache_loaded": cache._loaded,
        "cache_size": len(cache._cache),
    }

    if pricing:
        debug_info.update(
            {
                "input_cost_per_token": pricing.input_cost_per_token,
                "output_cost_per_token": pricing.output_cost_per_token,
                "cache_creation_cost": pricing.cache_creation_input_token_cost,
                "cache_read_cost": pricing.cache_read_input_token_cost,
            }
        )

        # Calculate sample cost for 1000 input/output tokens
        sample_cost = await calculate_token_cost(model_name, 1000, 1000)
        debug_info["sample_cost_1k_tokens"] = sample_cost.total_cost

    return debug_info
