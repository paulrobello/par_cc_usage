"""XDG Base Directory utilities for par_cc_usage.

This module provides utilities for determining proper locations for config,
cache, and data directories according to the XDG Base Directory Specification.
"""

from pathlib import Path

from xdg_base_dirs import xdg_cache_home, xdg_config_home, xdg_data_home


def get_config_dir() -> Path:
    """Get the XDG config directory for par_cc_usage.

    Returns:
        Path to the config directory (e.g., ~/.config/par_cc_usage/)
    """
    return xdg_config_home() / "par_cc_usage"


def get_cache_dir() -> Path:
    """Get the XDG cache directory for par_cc_usage.

    Returns:
        Path to the cache directory (e.g., ~/.cache/par_cc_usage/)
    """
    return xdg_cache_home() / "par_cc_usage"


def get_data_dir() -> Path:
    """Get the XDG data directory for par_cc_usage.

    Returns:
        Path to the data directory (e.g., ~/.local/share/par_cc_usage/)
    """
    return xdg_data_home() / "par_cc_usage"


def get_config_file_path() -> Path:
    """Get the default config file path using XDG directories.

    Returns:
        Path to the config file (e.g., ~/.config/par_cc_usage/config.yaml)
    """
    return get_config_dir() / "config.yaml"


def get_cache_file_path(filename: str) -> Path:
    """Get a cache file path using XDG directories.

    Args:
        filename: Name of the cache file

    Returns:
        Path to the cache file
    """
    return get_cache_dir() / filename


def get_data_file_path(filename: str) -> Path:
    """Get a data file path using XDG directories.

    Args:
        filename: Name of the data file

    Returns:
        Path to the data file
    """
    return get_data_dir() / filename


def ensure_xdg_directories() -> None:
    """Ensure XDG directories exist for par_cc_usage."""
    for dir_path in [get_config_dir(), get_cache_dir(), get_data_dir()]:
        dir_path.mkdir(parents=True, exist_ok=True)


def migrate_legacy_config(legacy_config_path: Path) -> bool:
    """Migrate legacy config file to XDG location.

    Args:
        legacy_config_path: Path to the legacy config file

    Returns:
        True if migration was performed, False otherwise
    """
    if not legacy_config_path.exists():
        return False

    xdg_config_path = get_config_file_path()

    # If XDG config already exists, don't migrate
    try:
        if xdg_config_path.exists():
            return False
    except (PermissionError, OSError):
        # If we can't check if XDG config exists due to permissions, don't migrate
        return False

    try:
        # Ensure XDG config directory exists
        xdg_config_path.parent.mkdir(parents=True, exist_ok=True)

        # Copy legacy config to XDG location
        import shutil

        shutil.copy2(legacy_config_path, xdg_config_path)

        return True
    except (PermissionError, OSError):
        # If migration fails due to permissions or other OS errors, return False
        return False


def get_legacy_config_paths() -> list[Path]:
    """Get potential legacy config file paths.

    Returns:
        List of legacy config file paths to check
    """
    return [
        Path.cwd() / "config.yaml",  # Current working directory
        Path.home() / ".par_cc_usage" / "config.yaml",  # Home directory
    ]
