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
