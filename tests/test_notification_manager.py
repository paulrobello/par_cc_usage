"""
Tests for the notification_manager module.
"""

from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from par_cc_usage.config import Config, NotificationConfig
from par_cc_usage.notification_manager import NotificationManager


class TestNotificationManager:
    """Test the NotificationManager class."""

    def test_initialization_no_webhook(self, mock_config):
        """Test NotificationManager initialization without webhook."""
        # Ensure no webhook URLs are set
        mock_config.notifications.discord_webhook_url = None
        mock_config.notifications.slack_webhook_url = None

        manager = NotificationManager(mock_config)

        assert manager.config == mock_config
        assert manager.discord_webhook is None
        assert manager.slack_webhook is None
        assert manager.state is not None

    def test_initialization_with_webhook(self, mock_config):
        """Test NotificationManager initialization with webhooks."""
        # Set webhook URLs
        mock_config.notifications.discord_webhook_url = "https://discord.com/api/webhooks/123/abc"
        mock_config.notifications.slack_webhook_url = "https://hooks.slack.com/services/123/abc"

        manager = NotificationManager(mock_config)

        assert manager.config == mock_config
        assert manager.discord_webhook is not None
        assert manager.discord_webhook.webhook_url == "https://discord.com/api/webhooks/123/abc"
        assert manager.slack_webhook is not None
        assert manager.slack_webhook.webhook_url == "https://hooks.slack.com/services/123/abc"

    def test_check_and_send_notifications_no_webhook(self, mock_config, sample_timestamp):
        """Test check_and_send_notifications when no webhook is configured."""
        from par_cc_usage.models import UsageSnapshot

        mock_config.notifications.discord_webhook_url = None
        mock_config.notifications.slack_webhook_url = None

        manager = NotificationManager(mock_config)

        # Create a mock snapshot
        snapshot = Mock(spec=UsageSnapshot)

        # Should not attempt to notify
        manager.check_and_send_notifications(snapshot)

        # Should have no webhooks configured
        assert manager.discord_webhook is None
        assert manager.slack_webhook is None

    @patch('par_cc_usage.notification_manager.WebhookClient')
    def test_check_and_send_notifications_disabled(self, mock_webhook_class, mock_config):
        """Test check_and_send_notifications when notifications are disabled."""
        mock_config.notifications.discord_webhook_url = "https://discord.com/test"
        mock_config.notifications.notify_on_block_completion = False

        manager = NotificationManager(mock_config)

        # Create a mock snapshot
        from par_cc_usage.models import UsageSnapshot
        snapshot = Mock(spec=UsageSnapshot)

        # Should update previous snapshot but not send notification
        manager.check_and_send_notifications(snapshot)

        # Should have updated previous snapshot
        assert manager.state.previous_snapshot == snapshot

        # Webhook should be created but not called
        mock_webhook_class.assert_called_once()
        mock_webhook = mock_webhook_class.return_value
        mock_webhook.send_block_completion_notification.assert_not_called()

    @patch('par_cc_usage.notification_manager.WebhookClient')
    def test_check_and_send_notifications_should_not_notify(self, mock_webhook_class, mock_config):
        """Test check_and_send_notifications when should_notify returns False."""
        mock_config.notifications.discord_webhook_url = "https://discord.com/test"
        mock_config.notifications.notify_on_block_completion = True

        manager = NotificationManager(mock_config)

        # Create a mock snapshot (without previous snapshot, so should_notify will be False)
        from par_cc_usage.models import UsageSnapshot
        snapshot = Mock(spec=UsageSnapshot)
        snapshot.unified_block_start_time = datetime.now(timezone.utc)

        # Should not send notification
        manager.check_and_send_notifications(snapshot)

        # Should have updated previous snapshot
        assert manager.state.previous_snapshot == snapshot

        # Webhook should be created but not called
        mock_webhook_class.assert_called_once()
        mock_webhook = mock_webhook_class.return_value
        mock_webhook.send_block_completion_notification.assert_not_called()

    @patch('par_cc_usage.notification_manager.WebhookClient')
    def test_check_and_send_notifications_success(self, mock_webhook_class, mock_config):
        """Test successful notification sending."""
        mock_config.notifications.discord_webhook_url = "https://discord.com/test"
        mock_config.notifications.notify_on_block_completion = True
        mock_config.notifications.cooldown_minutes = 60
        mock_config.timezone = "UTC"

        manager = NotificationManager(mock_config)

        # Set up state to trigger notification
        from par_cc_usage.models import UsageSnapshot

        # Create previous snapshot
        prev_snapshot = Mock(spec=UsageSnapshot)
        prev_snapshot.unified_block_start_time = datetime(2025, 1, 9, 5, 0, 0, tzinfo=timezone.utc)
        prev_snapshot.active_tokens = 1000
        manager.state.previous_snapshot = prev_snapshot

        # Create current snapshot with new block
        snapshot = Mock(spec=UsageSnapshot)
        snapshot.unified_block_start_time = datetime(2025, 1, 9, 10, 0, 0, tzinfo=timezone.utc)

        # Should send notification
        manager.check_and_send_notifications(snapshot)

        # Should have called webhook with Discord type
        from par_cc_usage.webhook_client import WebhookType
        mock_webhook_class.assert_called_once_with("https://discord.com/test", WebhookType.DISCORD)
        mock_webhook = mock_webhook_class.return_value
        from par_cc_usage.enums import TimeFormat
        mock_webhook.send_block_completion_notification.assert_called_once_with(
            prev_snapshot, "UTC", TimeFormat.TWENTY_FOUR_HOUR
        )

        # Should have marked as notified
        assert manager.state.last_notified_block_start == prev_snapshot.unified_block_start_time
        assert manager.state.previous_snapshot == snapshot

    @patch('par_cc_usage.notification_manager.WebhookClient')
    def test_check_and_send_notifications_webhook_error(self, mock_webhook_class, mock_config):
        """Test notification sending with webhook error."""
        from par_cc_usage.webhook_client import WebhookError

        mock_config.notifications.discord_webhook_url = "https://discord.com/test"
        mock_config.notifications.notify_on_block_completion = True
        mock_config.notifications.cooldown_minutes = 60
        mock_config.timezone = "UTC"

        # Set up webhook to raise error
        mock_webhook = Mock()
        mock_webhook.send_block_completion_notification.side_effect = WebhookError("Test error")
        mock_webhook_class.return_value = mock_webhook

        manager = NotificationManager(mock_config)

        # Set up state to trigger notification
        from par_cc_usage.models import UsageSnapshot

        # Create previous snapshot
        prev_snapshot = Mock(spec=UsageSnapshot)
        prev_snapshot.unified_block_start_time = datetime(2025, 1, 9, 5, 0, 0, tzinfo=timezone.utc)
        prev_snapshot.active_tokens = 1000
        manager.state.previous_snapshot = prev_snapshot

        # Create current snapshot with new block
        snapshot = Mock(spec=UsageSnapshot)
        snapshot.unified_block_start_time = datetime(2025, 1, 9, 10, 0, 0, tzinfo=timezone.utc)

        # Should handle error gracefully
        manager.check_and_send_notifications(snapshot)

        # Should have attempted to call webhook
        mock_webhook.send_block_completion_notification.assert_called_once()

        # Should still update previous snapshot
        assert manager.state.previous_snapshot == snapshot

    def test_test_webhook_no_webhook(self, mock_config):
        """Test webhook testing when no webhook configured."""
        mock_config.notifications.discord_webhook_url = None
        mock_config.notifications.slack_webhook_url = None

        manager = NotificationManager(mock_config)

        # Should return False when no webhook
        result = manager.test_webhook()
        assert result is False

    @patch('par_cc_usage.notification_manager.WebhookClient')
    def test_test_webhook_success(self, mock_webhook_class, mock_config):
        """Test successful webhook testing."""
        mock_config.notifications.discord_webhook_url = "https://discord.com/test"
        mock_config.timezone = "UTC"

        # Set up webhook to return success
        mock_webhook = Mock()
        mock_webhook.test_webhook.return_value = True
        mock_webhook_class.return_value = mock_webhook

        manager = NotificationManager(mock_config)

        # Create test snapshot
        from par_cc_usage.models import UsageSnapshot
        snapshot = Mock(spec=UsageSnapshot)

        # Should return True
        result = manager.test_webhook(snapshot)
        assert result is True

        # Should have called webhook test
        from par_cc_usage.enums import TimeFormat
        mock_webhook.test_webhook.assert_called_once_with(snapshot, "UTC", TimeFormat.TWENTY_FOUR_HOUR)

    @patch('par_cc_usage.notification_manager.WebhookClient')
    def test_test_webhook_exception(self, mock_webhook_class, mock_config):
        """Test webhook testing with exception."""
        mock_config.notifications.discord_webhook_url = "https://discord.com/test"
        mock_config.timezone = "UTC"

        # Set up webhook to raise exception
        mock_webhook = Mock()
        mock_webhook.test_webhook.side_effect = Exception("Test error")
        mock_webhook_class.return_value = mock_webhook

        manager = NotificationManager(mock_config)

        # Should return False and handle exception
        result = manager.test_webhook()
        assert result is False

    def test_is_configured_true(self, mock_config):
        """Test is_configured when webhooks are configured."""
        mock_config.notifications.discord_webhook_url = "https://discord.com/test"
        mock_config.notifications.slack_webhook_url = None

        manager = NotificationManager(mock_config)

        assert manager.is_configured() is True

    def test_is_configured_false(self, mock_config):
        """Test is_configured when no webhooks are configured."""
        mock_config.notifications.discord_webhook_url = None
        mock_config.notifications.slack_webhook_url = None

        manager = NotificationManager(mock_config)

        assert manager.is_configured() is False

    def test_notification_state_should_notify(self):
        """Test notification state tracking."""
        from par_cc_usage.notification_manager import NotificationState
        from par_cc_usage.models import UsageSnapshot
        from datetime import datetime, timezone

        state = NotificationState()

        # Create previous snapshot with a different block start time
        prev_snapshot = Mock(spec=UsageSnapshot)
        prev_snapshot.unified_block_start_time = datetime(2025, 1, 9, 5, 0, 0, tzinfo=timezone.utc)
        prev_snapshot.active_tokens = 1000
        state.previous_snapshot = prev_snapshot

        # Create current snapshot with new block start time
        snapshot = Mock(spec=UsageSnapshot)
        snapshot.unified_block_start_time = datetime(2025, 1, 9, 10, 0, 0, tzinfo=timezone.utc)

        # Should notify for block change
        should_notify = state.should_notify(snapshot, cooldown_minutes=60)
        assert should_notify is True

    def test_notification_state_cooldown(self):
        """Test notification cooldown - should not notify if within cooldown."""
        from par_cc_usage.notification_manager import NotificationState
        from par_cc_usage.models import UsageSnapshot

        state = NotificationState()

        # Create previous snapshot
        prev_block_start = datetime(2025, 1, 9, 5, 0, 0, tzinfo=timezone.utc)
        prev_snapshot = Mock(spec=UsageSnapshot)
        prev_snapshot.unified_block_start_time = prev_block_start
        prev_snapshot.active_tokens = 1000
        state.previous_snapshot = prev_snapshot

        # Set last notification to recent time (10 minutes ago)
        state.last_notified_block_start = None  # Haven't notified for this specific block
        state.last_notification_time = datetime.now() - timedelta(minutes=10)  # Use naive datetime

        # Create current snapshot with new block
        snapshot = Mock(spec=UsageSnapshot)
        snapshot.unified_block_start_time = datetime(2025, 1, 9, 10, 0, 0, tzinfo=timezone.utc)

        # Should NOT notify due to cooldown (60 minutes)
        should_notify = state.should_notify(snapshot, cooldown_minutes=60)
        assert should_notify is False

    def test_notification_state_no_unified_block(self):
        """Test notification state when no unified block start time."""
        from par_cc_usage.notification_manager import NotificationState
        from par_cc_usage.models import UsageSnapshot

        state = NotificationState()

        # Create snapshot without unified block start time
        snapshot = Mock(spec=UsageSnapshot)
        snapshot.unified_block_start_time = None

        # Should not notify
        should_notify = state.should_notify(snapshot, cooldown_minutes=60)
        assert should_notify is False

    def test_notification_state_no_previous_snapshot(self):
        """Test notification state when no previous snapshot."""
        from par_cc_usage.notification_manager import NotificationState
        from par_cc_usage.models import UsageSnapshot

        state = NotificationState()

        # Create snapshot with unified block (but no previous snapshot)
        snapshot = Mock(spec=UsageSnapshot)
        snapshot.unified_block_start_time = datetime(2025, 1, 9, 10, 0, 0, tzinfo=timezone.utc)

        # Should not notify when no previous snapshot
        should_notify = state.should_notify(snapshot, cooldown_minutes=60)
        assert should_notify is False

    def test_notification_state_same_block(self):
        """Test notification state when block hasn't changed."""
        from par_cc_usage.notification_manager import NotificationState
        from par_cc_usage.models import UsageSnapshot

        state = NotificationState()

        # Create previous and current snapshots with same block start time
        block_start = datetime(2025, 1, 9, 10, 0, 0, tzinfo=timezone.utc)

        prev_snapshot = Mock(spec=UsageSnapshot)
        prev_snapshot.unified_block_start_time = block_start
        prev_snapshot.active_tokens = 1000
        state.previous_snapshot = prev_snapshot

        snapshot = Mock(spec=UsageSnapshot)
        snapshot.unified_block_start_time = block_start

        # Should not notify when block hasn't changed
        should_notify = state.should_notify(snapshot, cooldown_minutes=60)
        assert should_notify is False

    def test_notification_state_already_notified(self):
        """Test notification state when already notified for this block."""
        from par_cc_usage.notification_manager import NotificationState
        from par_cc_usage.models import UsageSnapshot

        state = NotificationState()

        # Set up previous block
        prev_block_start = datetime(2025, 1, 9, 5, 0, 0, tzinfo=timezone.utc)
        prev_snapshot = Mock(spec=UsageSnapshot)
        prev_snapshot.unified_block_start_time = prev_block_start
        prev_snapshot.active_tokens = 1000
        state.previous_snapshot = prev_snapshot

        # Set that we already notified for this block
        state.last_notified_block_start = prev_block_start

        # Create new block
        snapshot = Mock(spec=UsageSnapshot)
        snapshot.unified_block_start_time = datetime(2025, 1, 9, 10, 0, 0, tzinfo=timezone.utc)

        # Should not notify - already notified for this block
        should_notify = state.should_notify(snapshot, cooldown_minutes=60)
        assert should_notify is False

    def test_notification_state_no_activity(self):
        """Test notification state when previous block had no activity."""
        from par_cc_usage.notification_manager import NotificationState
        from par_cc_usage.models import UsageSnapshot

        state = NotificationState()

        # Create previous snapshot with no tokens
        prev_snapshot = Mock(spec=UsageSnapshot)
        prev_snapshot.unified_block_start_time = datetime(2025, 1, 9, 5, 0, 0, tzinfo=timezone.utc)
        prev_snapshot.active_tokens = 0  # No activity
        state.previous_snapshot = prev_snapshot

        # Create current snapshot with new block
        snapshot = Mock(spec=UsageSnapshot)
        snapshot.unified_block_start_time = datetime(2025, 1, 9, 10, 0, 0, tzinfo=timezone.utc)

        # Should not notify when previous block had no activity
        should_notify = state.should_notify(snapshot, cooldown_minutes=60)
        assert should_notify is False

    def test_notification_state_cooldown_expired(self):
        """Test notification state when cooldown has expired."""
        from par_cc_usage.notification_manager import NotificationState
        from par_cc_usage.models import UsageSnapshot

        state = NotificationState()

        # Create previous snapshot
        prev_block_start = datetime(2025, 1, 9, 5, 0, 0, tzinfo=timezone.utc)
        prev_snapshot = Mock(spec=UsageSnapshot)
        prev_snapshot.unified_block_start_time = prev_block_start
        prev_snapshot.active_tokens = 1000
        state.previous_snapshot = prev_snapshot

        # Set last notification to old time (2 hours ago)
        state.last_notification_time = datetime.now() - timedelta(hours=2)

        # Create current snapshot with new block
        snapshot = Mock(spec=UsageSnapshot)
        snapshot.unified_block_start_time = datetime(2025, 1, 9, 10, 0, 0, tzinfo=timezone.utc)

        # Should notify - cooldown expired
        should_notify = state.should_notify(snapshot, cooldown_minutes=60)
        assert should_notify is True

    def test_notification_state_mark_notified(self):
        """Test marking notification as sent."""
        from par_cc_usage.notification_manager import NotificationState
        from par_cc_usage.models import UsageSnapshot

        state = NotificationState()

        # Create previous snapshot
        prev_block_start = datetime(2025, 1, 9, 5, 0, 0, tzinfo=timezone.utc)
        prev_snapshot = Mock(spec=UsageSnapshot)
        prev_snapshot.unified_block_start_time = prev_block_start
        state.previous_snapshot = prev_snapshot

        # Create current snapshot
        snapshot = Mock(spec=UsageSnapshot)
        snapshot.unified_block_start_time = datetime(2025, 1, 9, 10, 0, 0, tzinfo=timezone.utc)

        # Mark as notified
        state.mark_notified(snapshot)

        assert state.last_notified_block_start == prev_block_start
        assert state.last_notification_time is not None

    def test_notification_state_mark_notified_no_previous(self):
        """Test marking notification when no previous snapshot."""
        from par_cc_usage.notification_manager import NotificationState
        from par_cc_usage.models import UsageSnapshot

        state = NotificationState()

        # Create current snapshot
        snapshot = Mock(spec=UsageSnapshot)
        snapshot.unified_block_start_time = datetime(2025, 1, 9, 10, 0, 0, tzinfo=timezone.utc)

        # Mark as notified (should handle gracefully)
        state.mark_notified(snapshot)

        # Should not have set notification time since no previous snapshot
        assert state.last_notified_block_start is None

    def test_notification_state_update_previous_snapshot(self):
        """Test updating previous snapshot."""
        from par_cc_usage.notification_manager import NotificationState
        from par_cc_usage.models import UsageSnapshot

        state = NotificationState()

        # Create snapshot
        snapshot = Mock(spec=UsageSnapshot)
        snapshot.unified_block_start_time = datetime(2025, 1, 9, 10, 0, 0, tzinfo=timezone.utc)

        # Update previous snapshot
        state.update_previous_snapshot(snapshot)

        assert state.previous_snapshot == snapshot

    def test_notification_state_cooldown_expired_no_previous_time(self):
        """Test cooldown check when no previous notification time."""
        from par_cc_usage.notification_manager import NotificationState

        state = NotificationState()

        # Should return True when no previous notification time
        assert state._is_cooldown_expired(60) is True

    def test_notification_state_cooldown_not_expired(self):
        """Test cooldown check when cooldown has not expired."""
        from par_cc_usage.notification_manager import NotificationState

        state = NotificationState()

        # Set recent notification time (30 minutes ago)
        state.last_notification_time = datetime.now() - timedelta(minutes=30)

        # Should return False when cooldown (60 minutes) has not expired
        assert state._is_cooldown_expired(60) is False

    def test_notification_state_cooldown_just_expired(self):
        """Test cooldown check when cooldown has just expired."""
        from par_cc_usage.notification_manager import NotificationState

        state = NotificationState()

        # Set notification time to exactly 61 minutes ago
        state.last_notification_time = datetime.now() - timedelta(minutes=61)

        # Should return True when cooldown (60 minutes) has expired
        assert state._is_cooldown_expired(60) is True
