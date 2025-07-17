"""Tests for pricing functionality."""

from __future__ import annotations

import pytest

from par_cc_usage.pricing import (
    ModelPricing,
    PricingCache,
    TokenCost,
    calculate_token_cost,
    format_cost,
)


class TestModelPricing:
    """Test ModelPricing class."""

    def test_model_pricing_creation(self):
        """Test creating ModelPricing with various inputs."""
        pricing = ModelPricing(
            input_cost_per_token=0.001,
            output_cost_per_token=0.002,
            cache_creation_input_token_cost=0.0005,
            cache_read_input_token_cost=0.0001,
        )
        assert pricing.input_cost_per_token == 0.001
        assert pricing.output_cost_per_token == 0.002
        assert pricing.cache_creation_input_token_cost == 0.0005
        assert pricing.cache_read_input_token_cost == 0.0001

    def test_model_pricing_validation(self):
        """Test ModelPricing validation with string inputs."""
        pricing = ModelPricing(
            input_cost_per_token="0.001",
            output_cost_per_token="invalid",
            cache_creation_input_token_cost=None,
        )
        assert pricing.input_cost_per_token == 0.001
        assert pricing.output_cost_per_token is None
        assert pricing.cache_creation_input_token_cost is None


class TestPricingCache:
    """Test PricingCache class."""

    def test_unknown_model_fallback(self):
        """Test that unknown models return zero cost pricing."""
        cache = PricingCache()

        # Test various unknown model patterns
        unknown_models = ["unknown", "Unknown", "UNKNOWN", "none", "None", "", "null"]

        for model in unknown_models:
            pricing = cache._get_pricing_from_cache(model)
            assert pricing is not None
            assert pricing.input_cost_per_token == 0.0
            assert pricing.output_cost_per_token == 0.0
            assert pricing.cache_creation_input_token_cost == 0.0
            assert pricing.cache_read_input_token_cost == 0.0

    def test_fallback_pricing_patterns(self):
        """Test fallback pricing for common model patterns."""
        cache = PricingCache()

        # Mock some cache data
        cache._cache = {
            "claude-3-opus-20240229": ModelPricing(
                input_cost_per_token=0.015,
                output_cost_per_token=0.075,
            ),
            "claude-3-5-sonnet-20241022": ModelPricing(
                input_cost_per_token=0.003,
                output_cost_per_token=0.015,
            ),
            "claude-3-haiku-20240307": ModelPricing(
                input_cost_per_token=0.00025,
                output_cost_per_token=0.00125,
            ),
        }

        # Test fallback patterns
        test_cases = [
            ("claude-sonnet-4", "sonnet"),
            ("opus-model", "opus"),
            ("haiku-test", "haiku"),
            ("custom-opus-variant", "opus"),
        ]

        for model_name, expected_pattern in test_cases:
            pricing = cache._get_fallback_pricing(model_name)
            assert pricing is not None, f"Expected fallback pricing for {model_name}"
            assert pricing.input_cost_per_token > 0, f"Expected non-zero cost for {model_name}"


class TestTokenCost:
    """Test TokenCost class."""

    def test_token_cost_creation(self):
        """Test creating TokenCost."""
        cost = TokenCost(
            input_cost=1.0,
            output_cost=2.0,
            cache_creation_cost=0.5,
            cache_read_cost=0.1,
            total_cost=3.6,
        )
        assert cost.input_cost == 1.0
        assert cost.output_cost == 2.0
        assert cost.cache_creation_cost == 0.5
        assert cost.cache_read_cost == 0.1
        assert cost.total_cost == 3.6


@pytest.mark.asyncio
class TestCalculateTokenCost:
    """Test calculate_token_cost function."""

    async def test_unknown_model_calculation(self):
        """Test cost calculation for unknown models."""
        unknown_models = ["unknown", "Unknown", "none", "", "null"]

        for model in unknown_models:
            cost = await calculate_token_cost(model, 1000, 500)
            assert cost.total_cost == 0.0
            assert cost.input_cost == 0.0
            assert cost.output_cost == 0.0

    async def test_empty_model_calculation(self):
        """Test cost calculation for empty model name."""
        cost = await calculate_token_cost("", 1000, 500)
        assert cost.total_cost == 0.0


class TestFormatCost:
    """Test format_cost function."""

    def test_format_cost_various_amounts(self):
        """Test formatting various cost amounts."""
        test_cases = [
            (0, "$0.00"),
            (0.001, "$0.0010"),
            (0.0056, "$0.0056"),
            (0.01, "$0.010"),
            (0.123, "$0.123"),
            (1.0, "$1.00"),
            (12.34, "$12.34"),
            (123.456, "$123.46"),
        ]

        for cost, expected in test_cases:
            result = format_cost(cost)
            assert result == expected, f"Expected {expected} for cost {cost}, got {result}"
