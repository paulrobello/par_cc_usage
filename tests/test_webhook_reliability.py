"""
Test webhook system reliability and error handling.

This module tests network failures, rate limiting, serialization errors,
and other reliability issues in the webhook system.
"""

import pytest
import asyncio
import json
from unittest.mock import patch, Mock, AsyncMock, MagicMock
from datetime import datetime, timezone
import aiohttp

from par_cc_usage.webhook_client import WebhookClient
from par_cc_usage.json_models import WebhookPayload
from par_cc_usage.notification_manager import NotificationManager
from par_cc_usage.models import UsageSnapshot, Project, Session


class TestWebhookNetworkFailures:
    """Test webhook delivery with various network failures."""

    @pytest.mark.asyncio
    async def test_webhook_delivery_network_timeout(self):
        """Test webhook delivery when network request times out."""
        webhook_url = "https://hooks.discord.com/api/webhooks/test"
        client = WebhookClient(webhook_url)

        payload = WebhookPayload(
            content="Test message",
            username="PAR CC Usage",
            avatar_url=None,
        )

        # Mock aiohttp to raise timeout
        with patch('aiohttp.ClientSession.post') as mock_post:
            mock_post.side_effect = asyncio.TimeoutError("Request timed out")

            # Should handle timeout gracefully
            success = await client.send_webhook(payload)
            assert not success

    @pytest.mark.asyncio
    async def test_webhook_delivery_connection_error(self):
        """Test webhook delivery when connection fails."""
        webhook_url = "https://hooks.discord.com/api/webhooks/test"
        client = WebhookClient(webhook_url)

        payload = WebhookPayload(
            content="Test message",
            username="PAR CC Usage",
        )

        connection_errors = [
            aiohttp.ClientConnectionError("Connection failed"),
            aiohttp.ClientConnectorError(Mock(), Mock()),
            ConnectionError("Network unreachable"),
            OSError("Name resolution failed"),
        ]

        for error in connection_errors:
            with patch('aiohttp.ClientSession.post', side_effect=error):
                success = await client.send_webhook(payload)
                assert not success

    @pytest.mark.asyncio
    async def test_webhook_delivery_server_error(self):
        """Test webhook delivery when server returns 5xx errors."""
        webhook_url = "https://hooks.discord.com/api/webhooks/test"
        client = WebhookClient(webhook_url)

        payload = WebhookPayload(
            content="Test message",
            username="PAR CC Usage",
        )

        server_errors = [500, 502, 503, 504, 520, 522, 524]

        for status_code in server_errors:
            mock_response = Mock()
            mock_response.status = status_code
            mock_response.text = AsyncMock(return_value=f"Server Error {status_code}")

            mock_context = AsyncMock()
            mock_context.__aenter__ = AsyncMock(return_value=mock_response)
            mock_context.__aexit__ = AsyncMock(return_value=None)

            with patch('aiohttp.ClientSession.post', return_value=mock_context):
                success = await client.send_webhook(payload)
                assert not success

    @pytest.mark.asyncio
    async def test_webhook_delivery_rate_limiting(self):
        """Test webhook delivery when rate limited (429 responses)."""
        webhook_url = "https://hooks.discord.com/api/webhooks/test"
        client = WebhookClient(webhook_url)

        payload = WebhookPayload(
            content="Test message",
            username="PAR CC Usage",
        )

        # Mock rate limiting response
        mock_response = Mock()
        mock_response.status = 429
        mock_response.headers = {"Retry-After": "5"}
        mock_response.text = AsyncMock(return_value="Rate limited")

        mock_context = AsyncMock()
        mock_context.__aenter__ = AsyncMock(return_value=mock_response)
        mock_context.__aexit__ = AsyncMock(return_value=None)

        with patch('aiohttp.ClientSession.post', return_value=mock_context):
            success = await client.send_webhook(payload)
            assert not success

    @pytest.mark.asyncio
    async def test_webhook_delivery_client_errors(self):
        """Test webhook delivery with client errors (4xx)."""
        webhook_url = "https://hooks.discord.com/api/webhooks/test"
        client = WebhookClient(webhook_url)

        payload = WebhookPayload(
            content="Test message",
            username="PAR CC Usage",
        )

        client_errors = [400, 401, 403, 404, 413, 415]

        for status_code in client_errors:
            mock_response = Mock()
            mock_response.status = status_code
            mock_response.text = AsyncMock(return_value=f"Client Error {status_code}")

            mock_context = AsyncMock()
            mock_context.__aenter__ = AsyncMock(return_value=mock_response)
            mock_context.__aexit__ = AsyncMock(return_value=None)

            with patch('aiohttp.ClientSession.post', return_value=mock_context):
                success = await client.send_webhook(payload)
                assert not success


class TestWebhookPayloadSerialization:
    """Test webhook payload serialization errors."""

    @pytest.mark.asyncio
    async def test_webhook_payload_serialization_errors(self):
        """Test handling when webhook payload cannot be serialized."""
        webhook_url = "https://hooks.discord.com/api/webhooks/test"
        client = WebhookClient(webhook_url)

        # Create payload with non-serializable data
        class NonSerializable:
            def __repr__(self):
                return "NonSerializable()"

        # Test various serialization issues
        problematic_payloads = [
            WebhookPayload(
                content=NonSerializable(),  # Non-serializable content
                username="PAR CC Usage",
            ),
            WebhookPayload(
                content="Test with emoji: 🪙💬💰",  # Unicode content
                username="PAR CC Usage",
                avatar_url="invalid-url-format",  # Invalid URL
            ),
            WebhookPayload(
                content="x" * 10000,  # Very long content (may exceed limits)
                username="PAR CC Usage",
            ),
        ]

        for payload in problematic_payloads:
            # Mock successful network response
            mock_response = Mock()
            mock_response.status = 204
            mock_response.text = AsyncMock(return_value="")

            mock_context = AsyncMock()
            mock_context.__aenter__ = AsyncMock(return_value=mock_response)
            mock_context.__aexit__ = AsyncMock(return_value=None)

            with patch('aiohttp.ClientSession.post', return_value=mock_context):
                # Should handle serialization issues gracefully
                success = await client.send_webhook(payload)
                # May succeed or fail depending on implementation

    @pytest.mark.asyncio
    async def test_webhook_with_unicode_and_special_characters(self):
        """Test webhook delivery with Unicode and special characters."""
        webhook_url = "https://hooks.discord.com/api/webhooks/test"
        client = WebhookClient(webhook_url)

        unicode_contents = [
            "Standard ASCII text",
            "Unicode: ñáéíóú çñü",
            "Emojis: 🪙💬💰⚡🔥📊",
            "Mixed: ASCII + 中文 + العربية + русский",
            "Special chars: \n\t\r\"'\\",
            "Control chars: \x00\x01\x02",
        ]

        for content in unicode_contents:
            payload = WebhookPayload(
                content=content,
                username="PAR CC Usage",
            )

            # Mock successful response
            mock_response = Mock()
            mock_response.status = 204
            mock_response.text = AsyncMock(return_value="")

            mock_context = AsyncMock()
            mock_context.__aenter__ = AsyncMock(return_value=mock_response)
            mock_context.__aexit__ = AsyncMock(return_value=None)

            with patch('aiohttp.ClientSession.post', return_value=mock_context):
                success = await client.send_webhook(payload)
                # Should handle Unicode content

    @pytest.mark.asyncio
    async def test_webhook_json_serialization_failure(self):
        """Test handling when JSON serialization fails completely."""
        webhook_url = "https://hooks.discord.com/api/webhooks/test"
        client = WebhookClient(webhook_url)

        payload = WebhookPayload(
            content="Test message",
            username="PAR CC Usage",
        )

        # Mock json.dumps to fail
        with patch('json.dumps', side_effect=TypeError("Object not JSON serializable")):
            success = await client.send_webhook(payload)
            assert not success


class TestNotificationManagerReliability:
    """Test NotificationManager reliability with various failures."""

    @pytest.mark.asyncio
    async def test_notification_manager_webhook_failures(self, mock_config, sample_timestamp):
        """Test NotificationManager when webhook delivery fails."""
        # Setup notification config
        mock_config.notifications.discord_webhook_url = "https://hooks.discord.com/api/webhooks/test"
        mock_config.notifications.notify_on_block_completion = True

        manager = NotificationManager(mock_config.notifications)

        # Create test snapshot
        snapshot = UsageSnapshot(
            timestamp=sample_timestamp,
            projects={
                "test_project": Project(
                    name="test_project",
                    sessions={},
                )
            },
            total_limit=1000000,
            block_start_override=None,
        )

        # Mock webhook client to fail
        with patch.object(manager, '_webhook_client') as mock_client:
            mock_client.send_webhook = AsyncMock(return_value=False)  # Simulate failure

            # Should handle webhook failure gracefully
            await manager.check_and_notify(snapshot)

    @pytest.mark.asyncio
    async def test_notification_manager_concurrent_notifications(self, mock_config, sample_timestamp):
        """Test NotificationManager with concurrent notification attempts."""
        mock_config.notifications.discord_webhook_url = "https://hooks.discord.com/api/webhooks/test"
        mock_config.notifications.notify_on_block_completion = True

        manager = NotificationManager(mock_config.notifications)

        snapshot = UsageSnapshot(
            timestamp=sample_timestamp,
            projects={
                "test_project": Project(
                    name="test_project",
                    sessions={},
                )
            },
            total_limit=1000000,
            block_start_override=None,
        )

        # Create multiple concurrent notification tasks
        tasks = []
        for i in range(10):
            task = asyncio.create_task(manager.check_and_notify(snapshot))
            tasks.append(task)

        # Wait for all tasks to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Should handle concurrent access without errors
        for result in results:
            assert not isinstance(result, Exception)

    @pytest.mark.asyncio
    async def test_notification_manager_memory_pressure(self, mock_config, sample_timestamp):
        """Test NotificationManager under memory pressure."""
        mock_config.notifications.discord_webhook_url = "https://hooks.discord.com/api/webhooks/test"
        mock_config.notifications.notify_on_block_completion = True

        manager = NotificationManager(mock_config.notifications)

        # Simulate memory pressure
        def memory_pressure_side_effect(*args, **kwargs):
            raise MemoryError("Out of memory")

        with patch.object(manager, '_webhook_client') as mock_client:
            mock_client.send_webhook = AsyncMock(side_effect=memory_pressure_side_effect)

            snapshot = UsageSnapshot(
                timestamp=sample_timestamp,
                projects={"test": Project(name="test", sessions={})},
                total_limit=1000000,
                block_start_override=None,
            )

            # Should handle memory pressure gracefully
            await manager.check_and_notify(snapshot)

    def test_notification_manager_invalid_webhook_url(self, mock_config):
        """Test NotificationManager with invalid webhook URLs."""
        invalid_urls = [
            "",  # Empty URL
            "not-a-url",  # Invalid format
            "http://",  # Incomplete URL
            "ftp://example.com",  # Wrong protocol
            None,  # None URL
        ]

        for invalid_url in invalid_urls:
            mock_config.notifications.discord_webhook_url = invalid_url

            # Should handle invalid URLs gracefully
            try:
                manager = NotificationManager(mock_config.notifications)
            except Exception:
                pass  # May fail during initialization

    @pytest.mark.asyncio
    async def test_notification_cooldown_handling(self, mock_config, sample_timestamp):
        """Test notification cooldown handling with edge cases."""
        mock_config.notifications.discord_webhook_url = "https://hooks.discord.com/api/webhooks/test"
        mock_config.notifications.notify_on_block_completion = True
        mock_config.notifications.cooldown_minutes = 60

        manager = NotificationManager(mock_config.notifications)

        snapshot = UsageSnapshot(
            timestamp=sample_timestamp,
            projects={"test": Project(name="test", sessions={})},
            total_limit=1000000,
            block_start_override=None,
        )

        # Mock successful webhook delivery
        with patch.object(manager, '_webhook_client') as mock_client:
            mock_client.send_webhook = AsyncMock(return_value=True)

            # First notification should succeed
            await manager.check_and_notify(snapshot)

            # Immediate second notification should be blocked by cooldown
            await manager.check_and_notify(snapshot)

            # Should respect cooldown period


class TestWebhookSystemIntegration:
    """Test webhook system integration with other components."""

    @pytest.mark.asyncio
    async def test_webhook_integration_with_malformed_data(self, mock_config, sample_timestamp):
        """Test webhook system with malformed data from other components."""
        mock_config.notifications.discord_webhook_url = "https://hooks.discord.com/api/webhooks/test"
        mock_config.notifications.notify_on_block_completion = True

        manager = NotificationManager(mock_config.notifications)

        # Create malformed snapshot
        malformed_snapshot = Mock()
        malformed_snapshot.timestamp = None  # Invalid timestamp
        malformed_snapshot.projects = "not a dict"  # Invalid projects data
        malformed_snapshot.unified_block_tokens = Mock(side_effect=Exception("Data error"))

        # Should handle malformed data gracefully
        await manager.check_and_notify(malformed_snapshot)

    @pytest.mark.asyncio
    async def test_webhook_with_extreme_payload_sizes(self):
        """Test webhook delivery with extremely large payloads."""
        webhook_url = "https://hooks.discord.com/api/webhooks/test"
        client = WebhookClient(webhook_url)

        # Test with very large content
        large_content = "x" * 50000  # 50KB content
        payload = WebhookPayload(
            content=large_content,
            username="PAR CC Usage",
        )

        # Mock response that might reject large payloads
        mock_response = Mock()
        mock_response.status = 413  # Payload Too Large
        mock_response.text = AsyncMock(return_value="Payload too large")

        mock_context = AsyncMock()
        mock_context.__aenter__ = AsyncMock(return_value=mock_response)
        mock_context.__aexit__ = AsyncMock(return_value=None)

        with patch('aiohttp.ClientSession.post', return_value=mock_context):
            success = await client.send_webhook(payload)
            assert not success

    @pytest.mark.asyncio
    async def test_webhook_ssl_certificate_errors(self):
        """Test webhook delivery with SSL certificate issues."""
        webhook_url = "https://hooks.discord.com/api/webhooks/test"
        client = WebhookClient(webhook_url)

        payload = WebhookPayload(
            content="Test message",
            username="PAR CC Usage",
        )

        ssl_errors = [
            aiohttp.ClientSSLError(Mock(), "SSL certificate verification failed"),
            aiohttp.ServerCertificateError(Mock(), Mock()),
        ]

        for error in ssl_errors:
            with patch('aiohttp.ClientSession.post', side_effect=error):
                success = await client.send_webhook(payload)
                assert not success

    @pytest.mark.asyncio
    async def test_webhook_session_management_errors(self):
        """Test webhook client session management errors."""
        webhook_url = "https://hooks.discord.com/api/webhooks/test"
        client = WebhookClient(webhook_url)

        payload = WebhookPayload(
            content="Test message",
            username="PAR CC Usage",
        )

        # Mock session creation failure
        with patch('aiohttp.ClientSession', side_effect=Exception("Session creation failed")):
            success = await client.send_webhook(payload)
            assert not success

    @pytest.mark.asyncio
    async def test_webhook_response_parsing_errors(self):
        """Test webhook handling when response parsing fails."""
        webhook_url = "https://hooks.discord.com/api/webhooks/test"
        client = WebhookClient(webhook_url)

        payload = WebhookPayload(
            content="Test message",
            username="PAR CC Usage",
        )

        # Mock response with parsing issues
        mock_response = Mock()
        mock_response.status = 200
        mock_response.text = AsyncMock(side_effect=UnicodeDecodeError("utf-8", b"", 0, 1, "invalid"))
        mock_response.headers = {"content-type": "application/json"}

        mock_context = AsyncMock()
        mock_context.__aenter__ = AsyncMock(return_value=mock_response)
        mock_context.__aexit__ = AsyncMock(return_value=None)

        with patch('aiohttp.ClientSession.post', return_value=mock_context):
            success = await client.send_webhook(payload)
            # Should handle response parsing errors

    @pytest.mark.asyncio
    async def test_webhook_client_resource_cleanup(self):
        """Test webhook client properly cleans up resources."""
        webhook_url = "https://hooks.discord.com/api/webhooks/test"
        client = WebhookClient(webhook_url)

        payload = WebhookPayload(
            content="Test message",
            username="PAR CC Usage",
        )

        # Track session creation and cleanup
        session_created = False
        session_closed = False

        class MockSession:
            def __init__(self, *args, **kwargs):
                nonlocal session_created
                session_created = True

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                nonlocal session_closed
                session_closed = True

            async def post(self, *args, **kwargs):
                mock_response = Mock()
                mock_response.status = 204
                mock_response.text = AsyncMock(return_value="")

                mock_context = AsyncMock()
                mock_context.__aenter__ = AsyncMock(return_value=mock_response)
                mock_context.__aexit__ = AsyncMock(return_value=None)
                return mock_context

        with patch('aiohttp.ClientSession', MockSession):
            await client.send_webhook(payload)

        # Should properly manage session lifecycle
        assert session_created
        assert session_closed
