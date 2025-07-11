"""Webhook notification system for block completion supporting Discord and Slack."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import requests

from .enums import TimeFormat, WebhookType
from .json_models import DiscordWebhookPayload, SlackWebhookPayload
from .models import UsageSnapshot
from .utils import format_time_range

logger = logging.getLogger(__name__)


class WebhookError(Exception):
    """Exception raised when webhook operations fail."""


class WebhookClient:
    """Generic webhook client for sending block completion notifications."""

    def __init__(self, webhook_url: str, webhook_type: WebhookType | None = None, timeout: int = 10) -> None:
        """Initialize webhook client.

        Args:
            webhook_url: Webhook URL
            webhook_type: Type of webhook (Discord or Slack). If None, auto-detected from URL
            timeout: Request timeout in seconds
        """
        self.webhook_url = webhook_url
        self.timeout = timeout
        self.webhook_type = webhook_type or self._detect_webhook_type(webhook_url)

    def _detect_webhook_type(self, webhook_url: str) -> WebhookType:
        """Auto-detect webhook type from URL.

        Args:
            webhook_url: Webhook URL

        Returns:
            Detected webhook type
        """
        if "discord.com" in webhook_url.lower():
            return WebhookType.DISCORD
        elif "hooks.slack.com" in webhook_url.lower():
            return WebhookType.SLACK
        else:
            # Default to Discord for backward compatibility
            return WebhookType.DISCORD

    def _find_most_recent_block(self, snapshot: UsageSnapshot) -> tuple[datetime | None, Any | None]:
        """Find the most recent block in the snapshot.

        Args:
            snapshot: Usage snapshot

        Returns:
            Tuple of (block start time, block) or (None, None) if no blocks
        """
        most_recent_block = None
        total_blocks = 0
        for project in snapshot.projects.values():
            logger.debug(f"Checking project: {project.name}")
            for session in project.sessions.values():
                logger.debug(f"  Session {session.session_id} has {len(session.blocks)} blocks")
                for block in session.blocks:
                    total_blocks += 1
                    logger.debug(f"    Block {block.start_time} active: {block.is_active}")
                    if block.is_active:
                        if most_recent_block is None or block.start_time > most_recent_block.start_time:
                            most_recent_block = block

        logger.debug(f"Found {total_blocks} total blocks, most recent active: {most_recent_block}")
        if most_recent_block:
            return most_recent_block.start_time, most_recent_block
        return None, None

    def send_block_completion_notification(
        self,
        snapshot: UsageSnapshot,
        timezone: str,
        time_format: TimeFormat = TimeFormat.TWENTY_FOUR_HOUR,
    ) -> None:
        """Send block completion notification.

        Args:
            snapshot: Usage snapshot containing block information
            timezone: Timezone for date formatting
            time_format: Time format for display (12h or 24h)

        Raises:
            WebhookError: If webhook delivery fails
        """
        try:
            tz = ZoneInfo(timezone)
            block_start_to_use = self._get_block_start_time(snapshot)

            if not block_start_to_use:
                logger.warning("No block start time available for notification")
                return

            notification_data = self._prepare_notification_data(snapshot, block_start_to_use, tz, time_format)
            if not notification_data:
                logger.warning("No blocks found to notify about")
                return

            payload = self._create_webhook_payload(notification_data, snapshot.total_limit)
            self._send_webhook(payload)
            logger.info(f"Block completion notification sent via {self.webhook_type.value}")

        except Exception as e:
            logger.error(f"Failed to send block completion notification: {e}")
            raise WebhookError(f"Failed to send block completion notification: {e}") from e

    def _get_block_start_time(self, snapshot: UsageSnapshot) -> datetime | None:
        """Get the block start time to use for notification.

        Args:
            snapshot: Usage snapshot

        Returns:
            Block start time or None if not found
        """
        block_start_to_use = snapshot.unified_block_start_time

        if not block_start_to_use:
            # Find the most recent block for testing
            block_start_to_use, _ = self._find_most_recent_block(snapshot)
            if block_start_to_use:
                logger.info(f"No unified block start time, using most recent block at {block_start_to_use}")

        return block_start_to_use

    def _prepare_notification_data(
        self, snapshot: UsageSnapshot, block_start_to_use: datetime, tz: ZoneInfo, time_format: TimeFormat
    ) -> dict[str, Any] | None:
        """Prepare notification data for webhook.

        Args:
            snapshot: Usage snapshot
            block_start_to_use: Block start time
            tz: Timezone info
            time_format: Time format for display (12h or 24h)

        Returns:
            Notification data dict or None if no blocks found
        """
        start_time = block_start_to_use.astimezone(tz)
        logger.debug(f"Looking for blocks with start time: {block_start_to_use}")

        # Use unified block tokens for accurate billing representation
        block_tokens = snapshot.unified_block_tokens()

        # Block end time is always start + 5 hours
        end_time = start_time + timedelta(hours=5)

        logger.info(f"Using unified block tokens: {block_tokens}")

        # If no unified block tokens, fall back to total active tokens
        if not block_tokens:
            block_tokens = snapshot.active_tokens
            logger.info(f"No unified block tokens, using active tokens: {block_tokens}")

        if not block_tokens:
            logger.warning("No token data available for notification")
            return None

        return {
            "start_time": start_time,
            "end_time": end_time,
            "duration_hours": 5.0,
            "block_tokens": block_tokens,
            "time_format": time_format,
        }

    def _create_webhook_payload(
        self, notification_data: dict[str, Any], total_limit: int | None
    ) -> DiscordWebhookPayload | SlackWebhookPayload:
        """Create webhook payload based on type.

        Args:
            notification_data: Prepared notification data
            total_limit: Token limit

        Returns:
            Webhook payload
        """
        # Calculate limit status
        limit_percentage, limit_status = self._calculate_limit_status(notification_data["block_tokens"], total_limit)

        if self.webhook_type == WebhookType.SLACK:
            return self._build_slack_payload(
                start_time=notification_data["start_time"],
                end_time=notification_data["end_time"],
                duration_hours=notification_data["duration_hours"],
                block_tokens=notification_data["block_tokens"],
                total_limit=total_limit,
                limit_percentage=limit_percentage,
                limit_status=limit_status,
                time_format=notification_data["time_format"],
            )
        else:  # Discord
            return self._build_discord_payload(
                start_time=notification_data["start_time"],
                end_time=notification_data["end_time"],
                duration_hours=notification_data["duration_hours"],
                block_tokens=notification_data["block_tokens"],
                total_limit=total_limit,
                limit_percentage=limit_percentage,
                limit_status=limit_status,
                time_format=notification_data["time_format"],
            )

    def _calculate_limit_status(self, block_tokens: int, total_limit: int | None) -> tuple[float, str]:
        """Calculate limit status based on token usage.

        Args:
            block_tokens: Number of tokens used
            total_limit: Token limit

        Returns:
            Tuple of (limit_percentage, limit_status)
        """
        if not total_limit:
            return 0, "N/A"

        limit_percentage = (block_tokens / total_limit) * 100
        if limit_percentage <= 50:
            limit_status = "Good"
        elif limit_percentage <= 80:
            limit_status = "Warning"
        else:
            limit_status = "Critical"

        return limit_percentage, limit_status

    def _build_discord_payload(
        self,
        start_time: datetime,
        end_time: datetime,
        duration_hours: float,
        block_tokens: int,
        total_limit: int | None,
        limit_percentage: float,
        limit_status: str,
        time_format: TimeFormat,
    ) -> DiscordWebhookPayload:
        """Build Discord webhook payload.

        Args:
            start_time: Block start time
            end_time: Block end time
            duration_hours: Block duration in hours
            block_tokens: Total tokens used in block
            total_limit: Token limit
            limit_percentage: Percentage of limit used
            limit_status: Status based on limit usage
            time_format: Time format for display (12h or 24h)

        Returns:
            Discord webhook payload
        """
        # Get embed color based on limit status
        embed_color = self._get_embed_color(limit_percentage)

        # Format limit info
        limit_info = f"{limit_percentage:.1f}%" if total_limit else "No limit set"

        embed = {
            "title": "🔔 Claude Code Block Completed",
            "color": embed_color,
            "timestamp": end_time.isoformat(),
            "fields": [
                {
                    "name": "⏰ Duration",
                    "value": f"{duration_hours:.1f} hours",
                    "inline": True,
                },
                {
                    "name": "🎯 Tokens Used",
                    "value": f"{block_tokens:,}",
                    "inline": True,
                },
                {
                    "name": "📊 Limit Status",
                    "value": f"{limit_info} ({limit_status})",
                    "inline": True,
                },
                {
                    "name": "🕐 Time Range",
                    "value": format_time_range(start_time, end_time, time_format.value),
                    "inline": False,
                },
            ],
        }

        return DiscordWebhookPayload(embeds=[embed])

    def _build_slack_payload(
        self,
        start_time: datetime,
        end_time: datetime,
        duration_hours: float,
        block_tokens: int,
        total_limit: int | None,
        limit_percentage: float,
        limit_status: str,
        time_format: TimeFormat,
    ) -> SlackWebhookPayload:
        """Build Slack webhook payload.

        Args:
            start_time: Block start time
            end_time: Block end time
            duration_hours: Block duration in hours
            block_tokens: Total tokens used in block
            total_limit: Token limit
            limit_percentage: Percentage of limit used
            limit_status: Status based on limit usage
            time_format: Time format for display (12h or 24h)

        Returns:
            Slack webhook payload
        """
        # Get color for Slack (good, warning, danger)
        if limit_percentage <= 50:
            color = "good"
        elif limit_percentage <= 80:
            color = "warning"
        else:
            color = "danger"

        # Format limit info
        limit_info = f"{limit_percentage:.1f}%" if total_limit else "No limit set"

        # Create attachment
        attachment = {
            "color": color,
            "title": "🔔 Claude Code Block Completed",
            "fields": [
                {
                    "title": "⏰ Duration",
                    "value": f"{duration_hours:.1f} hours",
                    "short": True,
                },
                {
                    "title": "🎯 Tokens Used",
                    "value": f"{block_tokens:,}",
                    "short": True,
                },
                {
                    "title": "📊 Limit Status",
                    "value": f"{limit_info} ({limit_status})",
                    "short": True,
                },
                {
                    "title": "🕐 Time Range",
                    "value": format_time_range(start_time, end_time, time_format.value),
                    "short": False,
                },
            ],
            "ts": int(end_time.timestamp()),
        }

        return SlackWebhookPayload(attachments=[attachment])

    def _get_embed_color(self, limit_percentage: float) -> int:
        """Get Discord embed color based on limit percentage.

        Args:
            limit_percentage: Percentage of limit used

        Returns:
            Color as integer for Discord embed
        """
        if limit_percentage <= 50:
            return 0x00FF00  # Green
        elif limit_percentage <= 80:
            return 0xFFA500  # Orange
        else:
            return 0xFF0000  # Red

    def _send_webhook(self, payload: DiscordWebhookPayload | SlackWebhookPayload) -> None:
        """Send webhook payload.

        Args:
            payload: Webhook payload (Discord or Slack)

        Raises:
            WebhookError: If webhook delivery fails
        """
        try:
            # Convert Pydantic model to dict for JSON serialization
            payload_dict = payload.model_dump(exclude_none=True)

            response = requests.post(
                self.webhook_url,
                json=payload_dict,
                timeout=self.timeout,
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()
        except requests.RequestException as e:
            logger.error(f"{self.webhook_type.value.title()} webhook request failed: {e}")
            raise WebhookError(f"{self.webhook_type.value.title()} webhook request failed: {e}") from e

    def test_webhook(
        self,
        snapshot: UsageSnapshot | None = None,
        timezone: str = "UTC",
        time_format: TimeFormat = TimeFormat.TWENTY_FOUR_HOUR,
    ) -> bool:
        """Test webhook functionality.

        Args:
            snapshot: Optional snapshot for test data. If None, creates test data
            timezone: Timezone for formatting
            time_format: Time format for display (12h or 24h)

        Returns:
            True if webhook test succeeded, False otherwise
        """
        try:
            if snapshot and snapshot.unified_block_start_time:
                # Use provided snapshot if it has a unified block
                self.send_block_completion_notification(snapshot, timezone, time_format)
            else:
                # Create test data (either no snapshot or snapshot without unified block)
                test_time = datetime.now(ZoneInfo(timezone))

                if self.webhook_type == WebhookType.SLACK:
                    payload = self._build_slack_payload(
                        start_time=test_time,
                        end_time=test_time + timedelta(hours=5),
                        duration_hours=5.0,
                        block_tokens=123456,
                        total_limit=500000,
                        limit_percentage=24.7,
                        limit_status="Good",
                        time_format=time_format,
                    )
                else:  # Discord
                    payload = self._build_discord_payload(
                        start_time=test_time,
                        end_time=test_time + timedelta(hours=5),
                        duration_hours=5.0,
                        block_tokens=123456,
                        total_limit=500000,
                        limit_percentage=24.7,
                        limit_status="Good",
                        time_format=time_format,
                    )

                self._send_webhook(payload)
                logger.info(f"Test {self.webhook_type.value} webhook sent successfully")

            return True
        except Exception as e:
            logger.error(f"Test webhook failed: {e}")
            return False


# Backward compatibility aliases
DiscordWebhookError = WebhookError
DiscordWebhook = WebhookClient
