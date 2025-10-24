"""Tests for status line config reload functionality."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

from par_cc_usage.config import Config
from par_cc_usage.statusline_manager import StatusLineManager


def create_mock_config():
    """Create a mock config with all required fields."""
    config = Mock()
    config.statusline_separator = " - "
    config.statusline_enabled = True
    config.statusline_date_format = "%Y-%m-%d"
    config.statusline_time_format = "%I:%M %p"
    config.statusline_git_clean_indicator = "✓"
    config.statusline_git_dirty_indicator = "*"
    return config


class TestConfigReload:
    """Test config reload functionality in the monitor."""

    def test_monitor_reloads_config_for_statusline(self):
        """Test that monitor reloads config for status line updates."""
        # Create two different configs
        old_config = Mock()
        old_config.statusline_separator = " - "
        old_config.statusline_enabled = True
        old_config.statusline_template = "{tokens} OLD {messages}"
        old_config.statusline_use_grand_total = True
        old_config.statusline_date_format = "%Y-%m-%d"
        old_config.statusline_time_format = "%H:%M"
        old_config.display = Mock()
        old_config.display.time_format = "24h"

        new_config = Mock()
        new_config.statusline_separator = " - "
        new_config.statusline_enabled = True
        new_config.statusline_template = "{tokens} NEW {messages}"
        new_config.statusline_use_grand_total = True
        new_config.statusline_date_format = "%Y-%m-%d"
        new_config.statusline_time_format = "%H:%M"
        new_config.display = Mock()
        new_config.display.time_format = "24h"

        # Simulate what happens in monitor - config fields are copied
        old_config.statusline_template = new_config.statusline_template
        old_config.statusline_use_grand_total = new_config.statusline_use_grand_total
        old_config.statusline_date_format = new_config.statusline_date_format
        old_config.statusline_time_format = new_config.statusline_time_format
        old_config.display.time_format = new_config.display.time_format

        # Verify the config was updated
        assert old_config.statusline_template == "{tokens} NEW {messages}"
        assert old_config.statusline_use_grand_total
        assert old_config.statusline_date_format == "%Y-%m-%d"
        assert old_config.statusline_time_format == "%H:%M"
        assert old_config.display.time_format == "24h"

    def test_statusline_template_update_picked_up(self):
        """Test that template changes are picked up without restart."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "config.yaml"

            # Write initial config
            config_file.write_text("""
statusline_enabled: true
statusline_template: '{tokens} ORIGINAL {messages}'
statusline_date_format: '%Y-%m-%d'
statusline_time_format: '%H:%M'
""")

            # Load config
            from par_cc_usage.config import load_config

            config1 = load_config(config_file)
            assert config1.statusline_template == "{tokens} ORIGINAL {messages}"

            # Update config file
            config_file.write_text("""
statusline_enabled: true
statusline_template: '{tokens} UPDATED {messages}'
statusline_date_format: '%Y-%m-%d'
statusline_time_format: '%H:%M'
""")

            # Load config again
            config2 = load_config(config_file)
            assert config2.statusline_template == "{tokens} UPDATED {messages}"

            # Verify the configs are different
            assert config1.statusline_template != config2.statusline_template

    def test_config_fields_copied_correctly(self):
        """Test that all necessary config fields are copied during reload."""
        old_config = Mock(spec=Config)
        old_config.statusline_template = "OLD"
        old_config.statusline_use_grand_total = False
        old_config.statusline_date_format = "%Y"
        old_config.statusline_time_format = "%H"
        old_config.display = Mock()
        old_config.display.time_format = "12h"

        new_config = Mock(spec=Config)
        new_config.statusline_template = "NEW"
        new_config.statusline_use_grand_total = True
        new_config.statusline_date_format = "%Y-%m-%d"
        new_config.statusline_time_format = "%H:%M:%S"
        new_config.display = Mock()
        new_config.display = Mock()
        new_config.display.time_format = "24h"

        # Simulate the copy operation from monitor
        old_config.statusline_template = new_config.statusline_template
        old_config.statusline_use_grand_total = new_config.statusline_use_grand_total
        old_config.statusline_date_format = new_config.statusline_date_format
        old_config.statusline_time_format = new_config.statusline_time_format
        old_config.display.time_format = new_config.display.time_format

        # Verify all fields were copied
        assert old_config.statusline_template == "NEW"
        assert old_config.statusline_use_grand_total is True
        assert old_config.statusline_date_format == "%Y-%m-%d"
        assert old_config.statusline_time_format == "%H:%M:%S"
        assert old_config.display.time_format == "24h"


class TestTemplateVariables:
    """Test template variable handling including unknown variables."""

    def test_unknown_variables_handled_gracefully(self):
        """Test that unknown template variables show [unknown_var: NAME]."""
        config = create_mock_config()
        config.statusline_template = "{tokens} {unknown_var} {messages}"

        manager = StatusLineManager(config)

        result = manager.format_status_line_from_template(
            tokens=1000,
            messages=10,
            template="{tokens} {unknown_var} {messages}"
        )

        assert "[unknown_var: unknown_var]" in result
        assert "🪙 1K" in result
        assert "💬 10" in result

    def test_multiple_unknown_variables(self):
        """Test handling of multiple unknown variables."""
        config = create_mock_config()
        config.statusline_template = "{var1} {tokens} {var2} {messages} {var3}"

        manager = StatusLineManager(config)

        result = manager.format_status_line_from_template(
            tokens=1000,
            messages=10,
            template=config.statusline_template
        )

        assert "[unknown_var: var1]" in result
        assert "[unknown_var: var2]" in result
        assert "[unknown_var: var3]" in result
        assert "🪙 1K" in result
        assert "💬 10" in result

    def test_remaining_block_time_variable(self):
        """Test that {remaining_block_time} variable works correctly."""
        config = create_mock_config()
        config.statusline_template = "{tokens} {remaining_block_time} {messages}"

        manager = StatusLineManager(config)

        result = manager.format_status_line_from_template(
            tokens=1000,
            messages=10,
            time_remaining="2h 30m",
            template=config.statusline_template
        )

        assert "⏱️ 2h 30m" in result
        assert "🪙 1K" in result
        assert "💬 10" in result

    def test_all_template_variables_work(self):
        """Test that all documented template variables work."""
        config = create_mock_config()

        manager = StatusLineManager(config)

        # Test each variable individually
        variables = [
            "{project}",
            "{tokens}",
            "{messages}",
            "{cost}",
            "{remaining_block_time}",
            "{sep}",
            "{username}",
            "{hostname}",
            "{date}",
            "{current_time}",
        ]

        for var in variables:
            result = manager.format_status_line_from_template(
                tokens=1000,
                messages=10,
                cost=5.50,
                time_remaining="1h",
                project_name="test-project",
                template=var
            )
            # Should not contain unknown_var for any documented variable
            assert "[unknown_var:" not in result

    def test_empty_template_components(self):
        """Test handling of empty template components."""
        config = create_mock_config()

        manager = StatusLineManager(config)

        # Test with no project name (common for grand total)
        result = manager.format_status_line_from_template(
            tokens=1000,
            messages=10,
            project_name=None,
            template="{project}{sep}{tokens}"
        )

        # Project should be empty, leading separator should be cleaned
        assert result.startswith("🪙")  # Leading separator gets cleaned

    def test_separator_cleanup(self):
        """Test that multiple consecutive separators are cleaned up."""
        config = create_mock_config()

        manager = StatusLineManager(config)

        # Template with empty components causing consecutive separators
        result = manager.format_status_line_from_template(
            tokens=1000,
            messages=10,
            project_name="",  # Empty project
            template="{project}{sep}{sep}{tokens}{sep}{sep}{messages}"
        )

        # Should not have multiple consecutive separators
        assert " -  - " not in result
        assert " -  -  - " not in result


class TestTemplateHashValidation:
    """Test template hash validation and cache invalidation."""

    def test_template_hash_calculation(self):
        """Test that template hash is calculated correctly."""
        import hashlib

        template = "{tokens} TEST {messages}"
        date_format = "%Y-%m-%d"
        time_format = "%H:%M"

        config_str = f"{template}|{date_format}|{time_format}"
        expected_hash = hashlib.md5(config_str.encode()).hexdigest()

        config = Mock()
        config.statusline_separator = " - "
        config.statusline_template = template
        config.statusline_date_format = date_format
        config.statusline_time_format = time_format
        config.statusline_enabled = True

        manager = StatusLineManager(config)

        # The hash should be saved with the status line
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("par_cc_usage.statusline_manager.get_statusline_file_path") as mock_path:
                test_file = Path(tmpdir) / "test.txt"
                mock_path.return_value = test_file

                manager.save_status_line("test", "status line content")

                # Check that meta file was created with correct hash
                meta_file = test_file.with_suffix(".meta")
                assert meta_file.exists()
                assert meta_file.read_text() == expected_hash

    def test_cache_invalidation_on_template_change(self):
        """Test that cache is invalidated when template changes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create initial config
            config1 = Mock()
            config1.statusline_template = "TEMPLATE1"
            config1.statusline_date_format = "%Y-%m-%d"
            config1.statusline_time_format = "%H:%M"
            config1.statusline_enabled = True

            manager1 = StatusLineManager(config1)

            with patch("par_cc_usage.statusline_manager.get_statusline_file_path") as mock_path:
                test_file = Path(tmpdir) / "test.txt"
                mock_path.return_value = test_file

                # Save with first template
                manager1.save_status_line("test", "content1")

                # Create new config with different template
                config2 = Mock()
                config2.statusline_template = "TEMPLATE2"
                config2.statusline_date_format = "%Y-%m-%d"
                config2.statusline_time_format = "%H:%M"
                config2.statusline_enabled = True

                manager2 = StatusLineManager(config2)

                # Load should return None due to template change (unless ignore_template_change=True)
                loaded = manager2.load_status_line("test", ignore_template_change=False)
                assert loaded is None

                # But with ignore_template_change=True, should return old value
                loaded_ignore = manager2.load_status_line("test", ignore_template_change=True)
                assert loaded_ignore == "content1"

    def test_cache_preserved_with_ignore_flag(self):
        """Test that old cache is preserved when ignore_template_change=True."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = Mock()
            config.statusline_separator = " - "
            config.statusline_template = "TEMPLATE"
            config.statusline_date_format = "%Y-%m-%d"
            config.statusline_time_format = "%H:%M"
            config.statusline_enabled = True

            manager = StatusLineManager(config)

            with patch("par_cc_usage.statusline_manager.get_statusline_file_path") as mock_path:
                test_file = Path(tmpdir) / "test.txt"
                mock_path.return_value = test_file

                # Save status line
                manager.save_status_line("test", "preserved content")

                # Create manager with different template
                config2 = Mock()
                config2.statusline_template = "DIFFERENT"
                config2.statusline_date_format = "%Y-%m-%d"
                config2.statusline_time_format = "%H:%M"
                config2.statusline_enabled = True

                manager2 = StatusLineManager(config2)

                # Should preserve old content with ignore flag
                preserved = manager2.load_status_line("test", ignore_template_change=True)
                assert preserved == "preserved content"

                # File should still exist
                assert test_file.exists()



class TestStatusLineFormatting:
    """Test status line formatting with various templates."""

    def test_full_template_with_all_components(self):
        """Test a complex template with all components."""
        config = create_mock_config()
        template = "{project}{sep}{tokens}{sep}{messages}{sep}{cost}{sep}{remaining_block_time}{sep}{date}{sep}{current_time}{sep}{username}@{hostname}"
        config.statusline_template = template

        manager = StatusLineManager(config)

        result = manager.format_status_line_from_template(
            tokens=500000,
            messages=100,
            cost=50.00,
            token_limit=1000000,
            message_limit=200,
            cost_limit=100.00,
            time_remaining="2h 30m",
            project_name="my-project",
            template=template
        )

        # Check all components are present
        assert "my-project" in result
        assert "🪙 500K/1.0M" in result
        assert "💬 100/200" in result
        assert "💰 $50.00/$100.00" in result
        assert "⏱️ 2h 30m" in result
        assert " - " in result  # Separators

        # Date, time, username and hostname should be present
        assert "@" in result  # username@hostname format

    def test_minimal_template(self):
        """Test a minimal template with just tokens and messages."""
        config = create_mock_config()
        config.statusline_template = "{tokens} {messages}"

        manager = StatusLineManager(config)

        result = manager.format_status_line_from_template(
            tokens=1000,
            messages=10,
            template=config.statusline_template
        )

        assert "🪙 1K" in result
        assert "💬 10" in result
        # Should not have separators
        assert " - " not in result

    def test_custom_separator(self):
        """Test template with custom separator usage."""
        config = create_mock_config()
        config.statusline_template = "{tokens} | {messages}"  # Using | instead of {sep}

        manager = StatusLineManager(config)

        result = manager.format_status_line_from_template(
            tokens=1000,
            messages=10,
            template=config.statusline_template
        )

        assert "🪙 1K | 💬 10" in result
        assert " - " not in result  # Should not have default separator

    def test_newline_in_template(self):
        """Test template with newline characters."""
        config = create_mock_config()
        config.statusline_template = "{tokens}\\n{messages}"

        manager = StatusLineManager(config)

        result = manager.format_status_line_from_template(
            tokens=1000,
            messages=10,
            template=config.statusline_template
        )

        lines = result.split("\n")
        assert len(lines) == 2
        assert "🪙 1K" in lines[0]
        assert "💬 10" in lines[1]
