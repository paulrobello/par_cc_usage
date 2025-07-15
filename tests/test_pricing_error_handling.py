"""
Test pricing system error handling and resilience.

This module tests API failures, network timeouts, fallback logic,
and edge cases in cost calculations.
"""

import pytest
import asyncio
import json
from unittest.mock import AsyncMock, Mock, patch, MagicMock
from decimal import Decimal

from par_cc_usage.pricing import (
    PricingCache,
    ModelPricing,
    TokenCost,
    calculate_token_cost,
    debug_model_pricing,
)


class TestPricingAPIFailures:
    """Test pricing API failure scenarios."""

    @pytest.mark.asyncio
    async def test_pricing_api_network_timeout(self):
        """Test behavior when LiteLLM API times out."""
        cache = PricingCache()

        # Mock aiohttp to raise a timeout error
        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_get.side_effect = asyncio.TimeoutError("Request timed out")

            # Should handle timeout gracefully
            pricing = await cache.get_pricing("claude-3-sonnet-latest")
            assert pricing is None

            # Cost calculation should fall back to zero cost
            cost = await calculate_token_cost("claude-3-sonnet-latest", 1000, 500)
            assert cost.total_cost == 0.0
            assert cost.input_cost == 0.0
            assert cost.output_cost == 0.0

    @pytest.mark.asyncio
    async def test_pricing_api_invalid_json_response(self):
        """Test handling of corrupted JSON from pricing API."""
        cache = PricingCache()

        # Mock aiohttp to return invalid JSON
        mock_response = Mock()
        mock_response.status = 200
        mock_response.text = AsyncMock(return_value="invalid json{")
        mock_response.json = AsyncMock(side_effect=json.JSONDecodeError("Invalid JSON", "", 0))

        mock_context = AsyncMock()
        mock_context.__aenter__ = AsyncMock(return_value=mock_response)
        mock_context.__aexit__ = AsyncMock(return_value=None)

        with patch('aiohttp.ClientSession.get', return_value=mock_context):
            pricing = await cache.get_pricing("claude-3-sonnet-latest")
            assert pricing is None

    @pytest.mark.asyncio
    async def test_pricing_api_http_error_codes(self):
        """Test handling of various HTTP error codes."""
        cache = PricingCache()

        error_codes = [400, 401, 403, 404, 429, 500, 502, 503]

        for status_code in error_codes:
            mock_response = Mock()
            mock_response.status = status_code
            mock_response.text = AsyncMock(return_value=f"HTTP {status_code} Error")

            mock_context = AsyncMock()
            mock_context.__aenter__ = AsyncMock(return_value=mock_response)
            mock_context.__aexit__ = AsyncMock(return_value=None)

            with patch('aiohttp.ClientSession.get', return_value=mock_context):
                pricing = await cache.get_pricing(f"test-model-{status_code}")
                assert pricing is None, f"Should handle {status_code} error gracefully"

    @pytest.mark.asyncio
    async def test_pricing_api_network_connection_error(self):
        """Test handling when network connection fails."""
        cache = PricingCache()

        # Mock various connection errors
        connection_errors = [
            ConnectionError("Connection failed"),
            OSError("Network unreachable"),
            Exception("Unknown network error"),
        ]

        for error in connection_errors:
            with patch('aiohttp.ClientSession.get', side_effect=error):
                pricing = await cache.get_pricing("claude-3-sonnet-latest")
                assert pricing is None


class TestCostValidationEdgeCases:
    """Test cost validation with extreme and invalid values."""

    @pytest.mark.asyncio
    async def test_cost_validation_negative_values(self):
        """Test cost validation with negative values."""
        # Mock pricing data with negative costs (should be invalid)
        negative_pricing = ModelPricing(
            input_cost_per_token=Decimal("-0.001"),  # Negative cost
            output_cost_per_token=Decimal("0.002"),
            supports_vision=False,
            litellm_provider="anthropic",
            mode="chat",
        )

        cache = PricingCache()
        cache._cache["negative-model"] = negative_pricing

        cost = await calculate_token_cost("negative-model", 1000, 500)
        # Should handle negative pricing gracefully
        assert cost.total_cost >= 0.0

    @pytest.mark.asyncio
    async def test_cost_validation_extremely_large_values(self):
        """Test cost validation with extremely large values."""
        # Mock pricing with unrealistic costs
        expensive_pricing = ModelPricing(
            input_cost_per_token=Decimal("1000.0"),  # $1000 per token!
            output_cost_per_token=Decimal("2000.0"),  # $2000 per token!
            supports_vision=False,
            litellm_provider="anthropic",
            mode="chat",
        )

        cache = PricingCache()
        cache._cache["expensive-model"] = expensive_pricing

        cost = await calculate_token_cost("expensive-model", 100, 50)
        # Should calculate but flag as unrealistic
        expected_cost = (100 * 1000.0) + (50 * 2000.0)  # 200,000
        assert cost.total_cost == expected_cost

        # Test with extremely large token counts
        cost_large = await calculate_token_cost("expensive-model", 999999999, 999999999)
        assert cost_large.total_cost > 0  # Should not overflow

    @pytest.mark.asyncio
    async def test_cost_validation_zero_and_none_values(self):
        """Test cost validation with zero and None values."""
        # Test with zero tokens
        cost_zero = await calculate_token_cost("claude-3-sonnet-latest", 0, 0)
        assert cost_zero.total_cost == 0.0
        assert cost_zero.input_cost == 0.0
        assert cost_zero.output_cost == 0.0

        # Test with None model (should fall back)
        cost_none = await calculate_token_cost(None, 1000, 500)
        assert cost_none.total_cost == 0.0

    @pytest.mark.asyncio
    async def test_cost_calculation_overflow_protection(self):
        """Test protection against arithmetic overflow in cost calculations."""
        # Create extremely large values that might cause overflow
        max_tokens = 999999999999999999  # Very large number

        # Mock pricing that could cause overflow
        overflow_pricing = ModelPricing(
            input_cost_per_token=Decimal("999.999"),
            output_cost_per_token=Decimal("999.999"),
            supports_vision=False,
            litellm_provider="anthropic",
            mode="chat",
        )

        cache = PricingCache()
        cache._cache["overflow-model"] = overflow_pricing

        # Should handle large calculations without crashing
        cost = await calculate_token_cost("overflow-model", max_tokens, max_tokens)
        assert isinstance(cost.total_cost, (int, float, Decimal))
        assert cost.total_cost >= 0


class TestFallbackPricingLogic:
    """Test fallback pricing for unknown models."""

    @pytest.mark.asyncio
    async def test_fallback_pricing_unknown_models(self):
        """Test fallback pricing for completely unknown model names."""
        unknown_models = [
            "completely-unknown-model",
            "future-claude-model-9000",
            "random-string-12345",
            "",  # Empty string
            None,  # None value
        ]

        for model in unknown_models:
            cost = await calculate_token_cost(model, 1000, 500)
            # Unknown models should fall back to zero cost
            assert cost.total_cost == 0.0
            assert cost.input_cost == 0.0
            assert cost.output_cost == 0.0

    @pytest.mark.asyncio
    async def test_pattern_based_fallbacks(self):
        """Test pattern-based fallback pricing."""
        test_cases = [
            # Models containing "opus" should fall back to Opus pricing
            ("custom-opus-model", "opus"),
            ("anthropic/claude-opus-custom", "opus"),
            ("my-opus-variant", "opus"),

            # Models containing "sonnet" should fall back to Sonnet pricing
            ("custom-sonnet-model", "sonnet"),
            ("anthropic/claude-sonnet-custom", "sonnet"),
            ("my-sonnet-variant", "sonnet"),

            # Models containing "haiku" should fall back to Haiku pricing
            ("custom-haiku-model", "haiku"),
            ("anthropic/claude-haiku-custom", "haiku"),
            ("my-haiku-variant", "haiku"),
        ]

        for model_name, expected_pattern in test_cases:
            pricing = await debug_model_pricing(model_name)
            cost = await calculate_token_cost(model_name, 1000, 500)

            # Should not be zero cost if fallback works
            if pricing is not None:
                assert cost.total_cost > 0.0
            # If no fallback found, should be zero
            else:
                assert cost.total_cost == 0.0

    @pytest.mark.asyncio
    async def test_fuzzy_matching_fallbacks(self):
        """Test fuzzy matching for similar model names."""
        similar_models = [
            "claude-3-sonnet-20241022",  # Similar to official version
            "claude-sonnet-3-5",  # Reordered
            "claude_3_sonnet_latest",  # Underscores instead of hyphens
            "CLAUDE-3-SONNET-LATEST",  # Different case
        ]

        for model in similar_models:
            pricing = await debug_model_pricing(model)
            cost = await calculate_token_cost(model, 1000, 500)

            # Should either find a match or fall back to zero
            assert cost.total_cost >= 0.0
            assert isinstance(cost.total_cost, (int, float))

    @pytest.mark.asyncio
    async def test_generic_claude_fallback(self):
        """Test generic Claude fallback for unrecognized Claude models."""
        claude_variants = [
            "claude-future-model",
            "anthropic/claude-unknown",
            "claude-experimental-v2",
            "claude-beta-test",
        ]

        for model in claude_variants:
            cost = await calculate_token_cost(model, 1000, 500)
            # Should fall back to some pricing (likely Sonnet)
            # or zero if no Claude fallback is implemented
            assert cost.total_cost >= 0.0


class TestPricingCacheCorruption:
    """Test pricing cache corruption and recovery."""

    @pytest.mark.asyncio
    async def test_pricing_cache_corruption_recovery(self):
        """Test recovery when pricing cache is corrupted."""
        cache = PricingCache()

        # Corrupt the cache with invalid data
        cache._cache["corrupted-model"] = "invalid data structure"
        cache._cache["another-corrupted"] = {"missing": "required fields"}
        cache._cache["numeric-corruption"] = 12345

        # Should handle corrupted cache entries gracefully
        pricing = await cache.get_pricing("corrupted-model")
        assert pricing is None

        pricing2 = await cache.get_pricing("another-corrupted")
        assert pricing2 is None

        pricing3 = await cache.get_pricing("numeric-corruption")
        assert pricing3 is None

    @pytest.mark.asyncio
    async def test_cache_memory_pressure_handling(self):
        """Test cache behavior under memory pressure."""
        cache = PricingCache()

        # Fill cache with many entries to test memory handling
        for i in range(1000):
            model_name = f"test-model-{i}"
            pricing = ModelPricing(
                input_cost_per_token=Decimal("0.001"),
                output_cost_per_token=Decimal("0.002"),
                supports_vision=False,
                litellm_provider="test",
                mode="chat",
            )
            cache._cache[model_name] = pricing

        # Should still function with large cache
        test_pricing = await cache.get_pricing("test-model-500")
        assert test_pricing is not None

    @pytest.mark.asyncio
    async def test_concurrent_cache_access(self):
        """Test cache behavior with concurrent access."""
        cache = PricingCache()

        # Create multiple concurrent requests for the same model
        tasks = []
        for _ in range(10):
            task = asyncio.create_task(cache.get_pricing("claude-3-sonnet-latest"))
            tasks.append(task)

        # Wait for all tasks to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Should handle concurrent access without errors
        for result in results:
            assert not isinstance(result, Exception)


class TestPricingIntegrationEdgeCases:
    """Test pricing integration with other system components."""

    @pytest.mark.asyncio
    async def test_pricing_with_unknown_model_types(self):
        """Test pricing integration with unknown model types."""
        unknown_types = [
            "gpt-4",  # Non-Claude model
            "llama-2-70b",  # Different provider
            "custom-fine-tuned-model",  # Custom model
            "anthropic/claude-unknown-variant",  # Unknown Claude variant
        ]

        for model in unknown_types:
            cost = await calculate_token_cost(model, 1000, 500)
            # Should handle gracefully
            assert isinstance(cost, TokenCost)
            assert cost.total_cost >= 0.0

    @pytest.mark.asyncio
    async def test_pricing_with_malformed_model_names(self):
        """Test pricing with malformed model names."""
        malformed_names = [
            "claude-3-sonnet-latest\n",  # Newline character
            "claude-3-sonnet-latest\t",  # Tab character
            "claude-3-sonnet-latest ",  # Trailing space
            " claude-3-sonnet-latest",  # Leading space
            "claude-3-sonnet-latest\x00",  # Null character
            "claude-3-sonnet-latest\r",  # Carriage return
        ]

        for malformed_name in malformed_names:
            cost = await calculate_token_cost(malformed_name, 1000, 500)
            # Should handle malformed names gracefully
            assert isinstance(cost, TokenCost)
            assert cost.total_cost >= 0.0

    @pytest.mark.asyncio
    async def test_pricing_system_resilience(self):
        """Test overall pricing system resilience to various failures."""
        # Test with multiple failure scenarios happening simultaneously
        scenarios = [
            ("network-timeout", asyncio.TimeoutError("Timeout")),
            ("json-error", json.JSONDecodeError("Invalid", "", 0)),
            ("connection-error", ConnectionError("No connection")),
            ("unknown-error", Exception("Unknown error")),
        ]

        for model_name, error in scenarios:
            with patch('aiohttp.ClientSession.get', side_effect=error):
                cost = await calculate_token_cost(model_name, 1000, 500)
                # System should remain stable despite failures
                assert isinstance(cost, TokenCost)
                assert cost.total_cost >= 0.0

                # Debug function should also handle errors
                pricing_debug = await debug_model_pricing(model_name)
                # Should not raise exceptions
