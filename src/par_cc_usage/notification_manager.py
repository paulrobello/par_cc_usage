"""Notification manager for tracking and sending block completion notifications."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from .config import Config
from .models import UsageSnapshot
from .webhook_client import WebhookClient, WebhookError, WebhookType

logger = logging.getLogger(__name__)


class NotificationState:
    """Tracks notification state to prevent duplicate notifications."""

    def __init__(self) -> None:
        """Initialize notification state."""
        self.last_notified_block_start: datetime | None = None
        self.last_notification_time: datetime | None = None
        self.previous_snapshot: UsageSnapshot | None = None

    def should_notify(
        self,
        snapshot: UsageSnapshot,
        cooldown_minutes: int,
    ) -> bool:
        """Determine if a notification should be sent.

        Args:
            snapshot: Current usage snapshot
            cooldown_minutes: Minimum minutes between notifications

        Returns:
            True if notification should be sent, False otherwise
        """
        # Check if we have a unified block start time
        if not snapshot.unified_block_start_time:
            return False

        # Check if this is a new block compared to previous snapshot
        if self.previous_snapshot is None:
            return False

        # Check if the block has changed (new block started)
        current_block_start = snapshot.unified_block_start_time
        previous_block_start = self.previous_snapshot.unified_block_start_time

        # If block start times are different, a new block has started
        # This means the previous block completed
        if previous_block_start is not None and current_block_start != previous_block_start:
            # Check if we already notified for this block
            if self.last_notified_block_start is None or self.last_notified_block_start != previous_block_start:
                # Check cooldown period
                if self._is_cooldown_expired(cooldown_minutes):
                    # Check if the previous block had activity (tokens > 0)
                    if self.previous_snapshot.active_tokens > 0:
                        return True

        return False

    def _is_cooldown_expired(self, cooldown_minutes: int) -> bool:
        """Check if cooldown period has expired.

        Args:
            cooldown_minutes: Cooldown period in minutes

        Returns:
            True if cooldown has expired, False otherwise
        """
        if self.last_notification_time is None:
            return True

        cooldown_delta = timedelta(minutes=cooldown_minutes)
        return datetime.now() - self.last_notification_time > cooldown_delta

    def mark_notified(self, snapshot: UsageSnapshot) -> None:
        """Mark that a notification was sent for the given snapshot.

        Args:
            snapshot: Snapshot that was notified
        """
        if self.previous_snapshot and self.previous_snapshot.unified_block_start_time:
            self.last_notified_block_start = self.previous_snapshot.unified_block_start_time
            self.last_notification_time = datetime.now()
            logger.info(f"Marked notification sent for block starting at {self.last_notified_block_start}")

    def update_previous_snapshot(self, snapshot: UsageSnapshot) -> None:
        """Update the previous snapshot for comparison.

        Args:
            snapshot: Current snapshot to store as previous
        """
        self.previous_snapshot = snapshot


class NotificationManager:
    """Manages webhook notifications for block completion (Discord and Slack)."""

    def __init__(self, config: Config) -> None:
        """Initialize notification manager.

        Args:
            config: Application configuration
        """
        self.config = config
        self.state = NotificationState()
        self.discord_webhook: WebhookClient | None = None
        self.slack_webhook: WebhookClient | None = None

        # Initialize Discord webhook if configured
        if config.notifications.discord_webhook_url:
            self.discord_webhook = WebhookClient(config.notifications.discord_webhook_url, WebhookType.DISCORD)

        # Initialize Slack webhook if configured
        if config.notifications.slack_webhook_url:
            self.slack_webhook = WebhookClient(config.notifications.slack_webhook_url, WebhookType.SLACK)

    def check_and_send_notifications(self, snapshot: UsageSnapshot) -> None:
        """Check if notifications should be sent and send them.

        Args:
            snapshot: Current usage snapshot
        """
        # Early returns for non-notification cases
        if not self._should_send_notifications():
            self.state.update_previous_snapshot(snapshot)
            return

        # Send notifications if appropriate
        if self.state.should_notify(snapshot, self.config.notifications.cooldown_minutes):
            notifications_sent = self._send_all_notifications()
            if notifications_sent > 0:
                self.state.mark_notified(snapshot)

        # Always update the previous snapshot
        self.state.update_previous_snapshot(snapshot)

    def _should_send_notifications(self) -> bool:
        """Check if notifications should be sent based on configuration.

        Returns:
            True if notifications should be sent
        """
        if not self.config.notifications.notify_on_block_completion:
            return False

        if not self.discord_webhook and not self.slack_webhook:
            return False

        return True

    def _send_all_notifications(self) -> int:
        """Send notifications to all configured webhooks.

        Returns:
            Number of successful notifications sent
        """
        notifications_sent = 0

        # Send Discord notification if configured
        if self.discord_webhook:
            if self._send_discord_notification():
                notifications_sent += 1

        # Send Slack notification if configured
        if self.slack_webhook:
            if self._send_slack_notification():
                notifications_sent += 1

        return notifications_sent

    def _send_discord_notification(self) -> bool:
        """Send Discord notification.

        Returns:
            True if notification was sent successfully
        """
        try:
            if self.state.previous_snapshot and self.discord_webhook:
                self.discord_webhook.send_block_completion_notification(
                    self.state.previous_snapshot,
                    self.config.timezone,
                    self.config.display.time_format,
                )
                logger.info("Discord block completion notification sent successfully")
                return True
        except WebhookError as e:
            logger.error(f"Failed to send Discord notification: {e}")
        return False

    def _send_slack_notification(self) -> bool:
        """Send Slack notification.

        Returns:
            True if notification was sent successfully
        """
        try:
            if self.state.previous_snapshot and self.slack_webhook:
                self.slack_webhook.send_block_completion_notification(
                    self.state.previous_snapshot,
                    self.config.timezone,
                    self.config.display.time_format,
                )
                logger.info("Slack block completion notification sent successfully")
                return True
        except WebhookError as e:
            logger.error(f"Failed to send Slack notification: {e}")
        return False

    def test_webhook(self, snapshot: UsageSnapshot | None = None) -> bool:
        """Test webhook connections.

        Args:
            snapshot: Optional usage snapshot to test with real data

        Returns:
            True if at least one webhook test succeeds, False otherwise
        """
        if not self.discord_webhook and not self.slack_webhook:
            return False

        success = False

        # Test Discord webhook
        if self.discord_webhook:
            try:
                self.discord_webhook.test_webhook(snapshot, self.config.timezone, self.config.display.time_format)
                logger.info("Discord webhook test successful")
                success = True
            except Exception as e:
                logger.error(f"Discord webhook test failed: {e}")

        # Test Slack webhook
        if self.slack_webhook:
            try:
                self.slack_webhook.test_webhook(snapshot, self.config.timezone, self.config.display.time_format)
                logger.info("Slack webhook test successful")
                success = True
            except Exception as e:
                logger.error(f"Slack webhook test failed: {e}")

        return success

    def is_configured(self) -> bool:
        """Check if notifications are configured.

        Returns:
            True if at least one webhook is configured, False otherwise
        """
        return self.discord_webhook is not None or self.slack_webhook is not None
