"""Utility functions for par_cc_usage."""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path


def expand_path(path: str | Path) -> Path:
    """Expand ~ and environment variables in path.

    Args:
        path: Path to expand

    Returns:
        Expanded path
    """
    path_str = str(path)
    path_str = os.path.expanduser(path_str)
    path_str = os.path.expandvars(path_str)
    return Path(path_str)


def ensure_directory(path: Path) -> None:
    """Ensure directory exists, create if not.

    Args:
        path: Directory path
    """
    path.mkdir(parents=True, exist_ok=True)


def format_bytes(num_bytes: float) -> str:
    """Format bytes as human-readable string.

    Args:
        num_bytes: Number of bytes

    Returns:
        Formatted string
    """
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if abs(num_bytes) < 1024.0:
            return f"{num_bytes:3.1f} {unit}"
        num_bytes /= 1024.0
    return f"{num_bytes:.1f} PB"


def format_time(dt: datetime, time_format: str = "24h") -> str:
    """Format datetime according to the specified time format.

    Args:
        dt: Datetime object to format
        time_format: Either '12h' for 12-hour format or '24h' for 24-hour format

    Returns:
        Formatted time string
    """
    if time_format == "12h":
        return dt.strftime("%I:%M %p")
    else:  # Default to 24h
        return dt.strftime("%H:%M")


def format_datetime(dt: datetime, time_format: str = "24h") -> str:
    """Format datetime with date and time according to the specified time format.

    Args:
        dt: Datetime object to format
        time_format: Either '12h' for 12-hour format or '24h' for 24-hour format

    Returns:
        Formatted datetime string
    """
    if time_format == "12h":
        return dt.strftime("%Y-%m-%d %I:%M:%S %p %Z")
    else:  # Default to 24h
        return dt.strftime("%Y-%m-%d %H:%M:%S %Z")


def format_time_range(start_dt: datetime, end_dt: datetime, time_format: str = "24h") -> str:
    """Format a time range according to the specified time format.

    Args:
        start_dt: Start datetime
        end_dt: End datetime
        time_format: Either '12h' for 12-hour format or '24h' for 24-hour format

    Returns:
        Formatted time range string
    """
    if time_format == "12h":
        start_str = start_dt.strftime("%I:%M %p")
        end_str = end_dt.strftime("%I:%M %p")
        timezone_str = start_dt.strftime("%Z")
        return f"{start_str} - {end_str} {timezone_str}"
    else:  # Default to 24h
        start_str = start_dt.strftime("%H:%M")
        end_str = end_dt.strftime("%H:%M")
        timezone_str = start_dt.strftime("%Z")
        return f"{start_str} - {end_str} {timezone_str}"


def format_date_time_range(start_dt: datetime, end_dt: datetime, time_format: str = "24h") -> str:
    """Format a date-time range for list display according to the specified time format.

    Args:
        start_dt: Start datetime
        end_dt: End datetime
        time_format: Either '12h' for 12-hour format or '24h' for 24-hour format

    Returns:
        Formatted date-time range string
    """
    if time_format == "12h":
        start_str = start_dt.strftime("%Y-%m-%d %I:%M %p")
        end_str = end_dt.strftime("%I:%M %p")
        return f"{start_str} - {end_str}"
    else:  # Default to 24h
        start_str = start_dt.strftime("%Y-%m-%d %H:%M")
        end_str = end_dt.strftime("%H:%M")
        return f"{start_str} - {end_str}"


def detect_system_timezone() -> str:
    """Detect the system's local timezone.

    Returns:
        IANA timezone name string, or "America/Los_Angeles" as fallback
    """
    try:
        # Get the system's local timezone
        local_tz = datetime.now().astimezone().tzinfo

        # Try to get the IANA timezone name
        if hasattr(local_tz, "zone") and local_tz is not None:
            # pytz timezone objects have a 'zone' attribute
            zone = getattr(local_tz, "zone", None)
            if zone:
                return str(zone)
        elif hasattr(local_tz, "key") and local_tz is not None:
            # Some timezone implementations use 'key'
            key = getattr(local_tz, "key", None)
            if key:
                return str(key)
        elif local_tz is not None and hasattr(local_tz, "tzname"):
            # Try to get timezone name and map common abbreviations
            tz_name = local_tz.tzname(datetime.now())
            if tz_name:
                # Map common timezone abbreviations to IANA names
                tz_mapping = {
                    "PST": "America/Los_Angeles",
                    "PDT": "America/Los_Angeles",
                    "MST": "America/Denver",
                    "MDT": "America/Denver",
                    "CST": "America/Chicago",
                    "CDT": "America/Chicago",
                    "EST": "America/New_York",
                    "EDT": "America/New_York",
                    "UTC": "UTC",
                    "GMT": "UTC",
                }
                return tz_mapping.get(tz_name, "America/Los_Angeles")

        # If we can't determine the timezone name, try using the offset
        # This is a last resort and may not be fully accurate
        offset = datetime.now().astimezone().utcoffset()
        if offset:
            hours = offset.total_seconds() / 3600
            # Map common UTC offsets to likely IANA timezones
            offset_mapping = {
                -8.0: "America/Los_Angeles",  # PST
                -7.0: "America/Denver",  # MST
                -6.0: "America/Chicago",  # CST
                -5.0: "America/New_York",  # EST
                0.0: "UTC",  # UTC
            }
            return offset_mapping.get(hours, "America/Los_Angeles")

    except Exception:
        # If anything fails, fall back to Pacific timezone
        pass

    return "America/Los_Angeles"
