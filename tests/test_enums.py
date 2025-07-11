"""Tests for enum types."""

import pytest

from par_cc_usage.enums import DisplayMode, ModelType, OutputFormat, SortBy, TimeFormat


class TestDisplayMode:
    """Test DisplayMode enum."""

    def test_display_mode_values(self):
        """Test DisplayMode enum values."""
        assert DisplayMode.NORMAL == "normal"
        assert DisplayMode.COMPACT == "compact"

    def test_display_mode_from_string(self):
        """Test creating DisplayMode from string."""
        assert DisplayMode("normal") == DisplayMode.NORMAL
        assert DisplayMode("compact") == DisplayMode.COMPACT

    def test_display_mode_invalid_value(self):
        """Test DisplayMode with invalid value raises ValueError."""
        with pytest.raises(ValueError):
            DisplayMode("invalid")

    def test_display_mode_membership(self):
        """Test DisplayMode membership."""
        assert "normal" in DisplayMode
        assert "compact" in DisplayMode
        assert "invalid" not in DisplayMode

    def test_display_mode_iteration(self):
        """Test DisplayMode iteration."""
        modes = list(DisplayMode)
        assert len(modes) == 2
        assert DisplayMode.NORMAL in modes
        assert DisplayMode.COMPACT in modes

    def test_display_mode_string_representation(self):
        """Test DisplayMode string representation."""
        assert DisplayMode.NORMAL.value == "normal"
        assert DisplayMode.COMPACT.value == "compact"
        # The string representation includes the enum name
        assert str(DisplayMode.NORMAL) == "DisplayMode.NORMAL"
        assert str(DisplayMode.COMPACT) == "DisplayMode.COMPACT"


class TestModelType:
    """Test ModelType enum."""

    def test_model_type_values(self):
        """Test ModelType enum values."""
        assert ModelType.OPUS == "opus"
        assert ModelType.SONNET == "sonnet"
        assert ModelType.HAIKU == "haiku"
        assert ModelType.UNKNOWN == "unknown"

    def test_model_type_from_string(self):
        """Test creating ModelType from string."""
        assert ModelType("opus") == ModelType.OPUS
        assert ModelType("sonnet") == ModelType.SONNET
        assert ModelType("haiku") == ModelType.HAIKU
        assert ModelType("unknown") == ModelType.UNKNOWN


class TestTimeFormat:
    """Test TimeFormat enum."""

    def test_time_format_values(self):
        """Test TimeFormat enum values."""
        assert TimeFormat.TWELVE_HOUR == "12h"
        assert TimeFormat.TWENTY_FOUR_HOUR == "24h"

    def test_time_format_from_string(self):
        """Test creating TimeFormat from string."""
        assert TimeFormat("12h") == TimeFormat.TWELVE_HOUR
        assert TimeFormat("24h") == TimeFormat.TWENTY_FOUR_HOUR


class TestOutputFormat:
    """Test OutputFormat enum."""

    def test_output_format_values(self):
        """Test OutputFormat enum values."""
        assert OutputFormat.TABLE == "table"
        assert OutputFormat.JSON == "json"
        assert OutputFormat.CSV == "csv"

    def test_output_format_from_string(self):
        """Test creating OutputFormat from string."""
        assert OutputFormat("table") == OutputFormat.TABLE
        assert OutputFormat("json") == OutputFormat.JSON
        assert OutputFormat("csv") == OutputFormat.CSV


class TestSortBy:
    """Test SortBy enum."""

    def test_sort_by_values(self):
        """Test SortBy enum values."""
        assert SortBy.TOKENS == "tokens"
        assert SortBy.TIME == "time"
        assert SortBy.PROJECT == "project"
        assert SortBy.SESSION == "session"
        assert SortBy.MODEL == "model"

    def test_sort_by_from_string(self):
        """Test creating SortBy from string."""
        assert SortBy("tokens") == SortBy.TOKENS
        assert SortBy("time") == SortBy.TIME
        assert SortBy("project") == SortBy.PROJECT
        assert SortBy("session") == SortBy.SESSION
        assert SortBy("model") == SortBy.MODEL
