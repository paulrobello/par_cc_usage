"""Test git configuration for status line."""

from pathlib import Path
from unittest.mock import Mock, patch

from par_cc_usage.statusline_manager import StatusLineManager


def test_git_indicators_from_config():
    """Test that git indicators are read from config."""
    config = Mock()
    config.statusline_separator = " - "
    config.statusline_enabled = True
    config.statusline_git_clean_indicator = "OK"
    config.statusline_git_dirty_indicator = "CHANGED"

    manager = StatusLineManager(config)

    # Create a mock git directory structure
    with patch("pathlib.Path.exists") as mock_exists:
        mock_exists.return_value = True  # .git exists

        # Mock subprocess for clean repo
        with patch("subprocess.run") as mock_run:
            # First call: git branch
            # Second call: git status
            mock_run.side_effect = [
                Mock(returncode=0, stdout="main\n"),  # branch
                Mock(returncode=0, stdout=""),  # clean status
            ]

            branch, status = manager._get_git_info(Path("/fake/repo"))
            assert branch == "main"
            assert status == "OK"  # Using configured clean indicator

        # Mock subprocess for dirty repo
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [
                Mock(returncode=0, stdout="develop\n"),  # branch
                Mock(returncode=0, stdout="M file.txt\n"),  # dirty status
            ]

            branch, status = manager._get_git_info(Path("/fake/repo"))
            assert branch == "develop"
            assert status == "CHANGED"  # Using configured dirty indicator


def test_git_emoji_indicators():
    """Test emoji indicators for git status."""
    config = Mock()
    config.statusline_separator = " - "
    config.statusline_enabled = True
    config.statusline_git_clean_indicator = "🟢"
    config.statusline_git_dirty_indicator = "🔴"

    manager = StatusLineManager(config)

    with patch("pathlib.Path.exists") as mock_exists:
        mock_exists.return_value = True

        # Test clean with emoji
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [
                Mock(returncode=0, stdout="main\n"),
                Mock(returncode=0, stdout=""),  # clean
            ]

            branch, status = manager._get_git_info(Path("/fake/repo"))
            assert status == "🟢"

        # Test dirty with emoji
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [
                Mock(returncode=0, stdout="main\n"),
                Mock(returncode=0, stdout="A new_file.txt\n"),  # added file
            ]

            _branch, status = manager._get_git_info(Path("/fake/repo"))
            assert status == "🔴"


def test_git_multichar_indicators():
    """Test multi-character indicators for git status."""
    config = Mock()
    config.statusline_separator = " - "
    config.statusline_enabled = True
    config.statusline_git_clean_indicator = "[CLEAN]"
    config.statusline_git_dirty_indicator = "[DIRTY]"

    manager = StatusLineManager(config)

    with patch("pathlib.Path.exists") as mock_exists:
        mock_exists.return_value = True

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [
                Mock(returncode=0, stdout="feature\n"),
                Mock(returncode=0, stdout="D deleted.txt\n"),  # deleted file
            ]

            branch, status = manager._get_git_info(Path("/fake/repo"))
            assert branch == "feature"
            assert status == "[DIRTY]"
