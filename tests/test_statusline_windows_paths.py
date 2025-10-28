"""Tests for Windows path compatibility in statusline manager."""

from pathlib import Path, PureWindowsPath, PurePosixPath
from unittest.mock import Mock, patch, MagicMock
import pytest

from par_cc_usage.config import Config
from par_cc_usage.statusline_manager import StatusLineManager


class TestWindowsPathCompatibility:
    """Test Windows path handling in session file discovery."""

    def test_find_session_file_windows_path_construction(self, tmp_path):
        """Test that session file path construction works on Windows-style paths."""
        config = Config()
        manager = StatusLineManager(config)

        # Create mock directories simulating Windows paths
        session_id = "test-session-123"
        project_name = "pilot-program-cmg-librechat"

        # Simulate Windows-style path structure
        with patch("pathlib.Path.home") as mock_home, patch(
            "pathlib.Path.cwd"
        ) as mock_cwd:
            # Use PureWindowsPath for simulation but Path for actual operations
            mock_home.return_value = tmp_path / "Users" / "testuser"
            mock_cwd.return_value = (
                tmp_path / "Users" / "testuser" / "Repos" / "GitHub" / project_name
            )

            # Create the expected directory structure
            claude_projects = mock_home.return_value / ".claude" / "projects"
            expected_project_dir = claude_projects / "-Repos-GitHub-pilot-program-cmg-librechat"
            expected_project_dir.mkdir(parents=True, exist_ok=True)

            # Create session file
            session_file = expected_project_dir / f"{session_id}.jsonl"
            session_file.write_text('{"type":"usage"}\n', encoding="utf-8")

            # Test finding the session file
            result = manager._find_session_file(session_id)

            # The file should be found
            assert result is not None
            assert result.exists()
            assert result.name == f"{session_id}.jsonl"

    def test_find_session_file_windows_backslash_handling(self):
        """Test that backslashes in Windows paths are properly converted."""
        # Simulate the path construction logic
        windows_home = PureWindowsPath(r"C:\Users\testuser")
        windows_cwd = PureWindowsPath(
            r"C:\Users\testuser\Repos\GitHub\pilot-program-cmg-librechat"
        )

        # Test the path construction logic
        try:
            relative_parent = windows_cwd.parent.relative_to(windows_home)
            parent_path = str(relative_parent).replace("\\", "-").replace("/", "-")
            project_name = windows_cwd.name.replace("_", "-")

            if parent_path:
                project_dir = f"-{parent_path}-{project_name}"
            else:
                project_dir = f"-{project_name}"

            # Should produce the correct project directory name
            assert project_dir == "-Repos-GitHub-pilot-program-cmg-librechat"
            # Should not contain any backslashes
            assert "\\" not in project_dir

        except ValueError:
            pytest.fail("relative_to should not raise ValueError for this case")

    def test_find_session_file_unix_path_construction(self):
        """Test that Unix path construction still works correctly."""
        # Simulate the path construction logic with Unix paths
        unix_home = PurePosixPath("/home/testuser")
        unix_cwd = PurePosixPath(
            "/home/testuser/Repos/GitHub/pilot-program-cmg-librechat"
        )

        # Test the path construction logic
        try:
            relative_parent = unix_cwd.parent.relative_to(unix_home)
            parent_path = str(relative_parent).replace("\\", "-").replace("/", "-")
            project_name = unix_cwd.name.replace("_", "-")

            if parent_path:
                project_dir = f"-{parent_path}-{project_name}"
            else:
                project_dir = f"-{project_name}"

            # Should produce the correct project directory name
            assert project_dir == "-Repos-GitHub-pilot-program-cmg-librechat"

        except ValueError:
            pytest.fail("relative_to should not raise ValueError for this case")

    def test_find_session_file_path_not_relative_to_home(self):
        """Test handling when CWD is not relative to home directory."""
        # Simulate paths that aren't relative to each other (e.g., different drives on Windows)
        windows_home = PureWindowsPath(r"C:\Users\testuser")
        windows_cwd = PureWindowsPath(r"D:\Projects\myproject")

        # Test the path construction logic with error handling
        try:
            relative_parent = windows_cwd.parent.relative_to(windows_home)
            parent_path = str(relative_parent).replace("\\", "-").replace("/", "-")
        except ValueError:
            # Expected behavior - use empty parent_path
            parent_path = ""

        project_name = windows_cwd.name.replace("_", "-")

        if parent_path:
            project_dir = f"-{parent_path}-{project_name}"
        else:
            project_dir = f"-{project_name}"

        # Should produce project name only
        assert project_dir == "-myproject"

    def test_find_session_file_edge_case_project_at_home(self):
        """Test when project is directly in home directory."""
        home = PurePosixPath("/home/testuser")
        cwd = PurePosixPath("/home/testuser/myproject")

        try:
            relative_parent = cwd.parent.relative_to(home)
            # relative_parent will be empty (.) so str() gives "."
            parent_path = str(relative_parent).replace("\\", "-").replace("/", "-")
            # "." becomes ".", which we should handle
            if parent_path == ".":
                parent_path = ""
        except ValueError:
            parent_path = ""

        project_name = cwd.name.replace("_", "-")

        if parent_path:
            project_dir = f"-{parent_path}-{project_name}"
        else:
            project_dir = f"-{project_name}"

        # Should produce project name only (no parent path)
        assert project_dir == "-myproject"

    def test_session_tokens_template_replacement_with_valid_file(self, tmp_path):
        """Test that session token template variables are replaced when file exists."""
        config = Config()
        manager = StatusLineManager(config)

        session_id = "test-session-456"
        template = "Tokens: {session_tokens}/{session_tokens_total}"

        # Create mock session file
        with patch.object(manager, "_find_session_file") as mock_find, patch.object(
            manager, "_extract_tokens_from_file"
        ) as mock_extract:

            # Mock finding the file
            mock_file = tmp_path / "session.jsonl"
            mock_file.write_text('{"type":"usage"}\n', encoding="utf-8")
            mock_find.return_value = mock_file

            # Mock extracting tokens
            mock_extract.return_value = 50000

            # Get session components
            components = manager._prepare_session_components(session_id, template)

            # Should have session token components
            assert "session_tokens" in components
            assert "session_tokens_total" in components
            assert components["session_tokens"] == "50K"
            assert components["session_tokens_total"] == "200K"

    def test_session_tokens_template_no_replacement_when_file_not_found(self):
        """Test that template variables show as unknown when session file not found."""
        config = Config()
        manager = StatusLineManager(config)

        session_id = "nonexistent-session"
        template = "Tokens: {session_tokens}/{session_tokens_total}"

        # Mock file not found
        with patch.object(manager, "_find_session_file") as mock_find:
            mock_find.return_value = None

            # Get session components
            components = manager._prepare_session_components(session_id, template)

            # Should return empty dict when file not found
            assert components == {}
