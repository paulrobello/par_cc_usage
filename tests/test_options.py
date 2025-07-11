"""Tests for options module."""


from par_cc_usage.enums import DisplayMode
from par_cc_usage.options import MonitorOptions


class TestMonitorOptions:
    """Test MonitorOptions dataclass."""

    def test_monitor_options_default_values(self):
        """Test MonitorOptions with default values."""
        options = MonitorOptions()

        assert options.display_mode is None  # Default is None, config provides the actual default
        assert options.interval == 5
        assert options.snapshot is False
        assert options.show_sessions is False
        assert options.token_limit is None
        assert options.block_start_override is None
        assert options.no_cache is False

    def test_monitor_options_with_compact_mode(self):
        """Test MonitorOptions with compact display mode."""
        options = MonitorOptions(
            display_mode=DisplayMode.COMPACT,
            interval=3,
            snapshot=True,
            show_sessions=True,
            token_limit=500000,
            block_start_override=14,
            no_cache=True
        )

        assert options.display_mode == DisplayMode.COMPACT
        assert options.interval == 3
        assert options.snapshot is True
        assert options.show_sessions is True
        assert options.token_limit == 500000
        assert options.block_start_override == 14
        assert options.no_cache is True

    def test_monitor_options_with_string_display_mode(self):
        """Test MonitorOptions with string display mode values."""
        # Test normal mode
        options_normal = MonitorOptions(display_mode="normal")
        assert options_normal.display_mode == DisplayMode.NORMAL

        # Test compact mode
        options_compact = MonitorOptions(display_mode="compact")
        assert options_compact.display_mode == DisplayMode.COMPACT

    def test_monitor_options_display_mode_validation(self):
        """Test MonitorOptions display mode validation."""
        # Valid enum values should work
        options1 = MonitorOptions(display_mode=DisplayMode.NORMAL)
        assert options1.display_mode == DisplayMode.NORMAL

        options2 = MonitorOptions(display_mode=DisplayMode.COMPACT)
        assert options2.display_mode == DisplayMode.COMPACT

        # String values should be converted to enum
        options3 = MonitorOptions(display_mode="normal")
        assert options3.display_mode == DisplayMode.NORMAL

        options4 = MonitorOptions(display_mode="compact")
        assert options4.display_mode == DisplayMode.COMPACT

    def test_monitor_options_interval_validation(self):
        """Test MonitorOptions interval validation."""
        # Valid intervals
        options1 = MonitorOptions(interval=1)
        assert options1.interval == 1

        options2 = MonitorOptions(interval=10)
        assert options2.interval == 10

        options3 = MonitorOptions(interval=60)
        assert options3.interval == 60

    def test_monitor_options_block_start_validation(self):
        """Test MonitorOptions block_start_override validation."""
        # Valid hour values (0-23)
        options1 = MonitorOptions(block_start_override=0)
        assert options1.block_start_override == 0

        options2 = MonitorOptions(block_start_override=12)
        assert options2.block_start_override == 12

        options3 = MonitorOptions(block_start_override=23)
        assert options3.block_start_override == 23

        # None should be allowed
        options4 = MonitorOptions(block_start_override=None)
        assert options4.block_start_override is None

    def test_monitor_options_boolean_fields(self):
        """Test MonitorOptions boolean field handling."""
        # Test all boolean combinations
        options = MonitorOptions(
            snapshot=True,
            show_sessions=True,
            no_cache=True
        )

        assert options.snapshot is True
        assert options.show_sessions is True
        assert options.no_cache is True

        # Test false values
        options2 = MonitorOptions(
            snapshot=False,
            show_sessions=False,
            no_cache=False
        )

        assert options2.snapshot is False
        assert options2.show_sessions is False
        assert options2.no_cache is False

    def test_monitor_options_token_limit_types(self):
        """Test MonitorOptions token_limit with different types."""
        # None value
        options1 = MonitorOptions(token_limit=None)
        assert options1.token_limit is None

        # Integer value
        options2 = MonitorOptions(token_limit=500000)
        assert options2.token_limit == 500000

        # Float value should work
        options3 = MonitorOptions(token_limit=500000.0)
        assert options3.token_limit == 500000.0

    def test_monitor_options_repr(self):
        """Test MonitorOptions string representation."""
        options = MonitorOptions(
            display_mode=DisplayMode.COMPACT,
            interval=3,
            snapshot=True,
            show_sessions=False,
            token_limit=500000,
            block_start_override=14,
            no_cache=True
        )

        repr_str = repr(options)

        # Should contain key information
        assert "MonitorOptions" in repr_str
        assert "display_mode=<DisplayMode.COMPACT: 'compact'>" in repr_str
        assert "interval=3" in repr_str
        assert "snapshot=True" in repr_str
        assert "token_limit=500000" in repr_str
        assert "block_start_override=14" in repr_str
        assert "no_cache=True" in repr_str

    def test_monitor_options_equality(self):
        """Test MonitorOptions equality comparison."""
        options1 = MonitorOptions(
            display_mode=DisplayMode.COMPACT,
            interval=5,
            snapshot=False
        )

        options2 = MonitorOptions(
            display_mode=DisplayMode.COMPACT,
            interval=5,
            snapshot=False
        )

        options3 = MonitorOptions(
            display_mode=DisplayMode.NORMAL,
            interval=5,
            snapshot=False
        )

        # Same values should be equal
        assert options1 == options2

        # Different values should not be equal
        assert options1 != options3

    def test_monitor_options_edge_cases(self):
        """Test MonitorOptions edge cases."""
        # Test with minimal values
        options_min = MonitorOptions(
            interval=1,
            block_start_override=0
        )
        assert options_min.interval == 1
        assert options_min.block_start_override == 0

        # Test with maximum values
        options_max = MonitorOptions(
            interval=3600,  # 1 hour
            block_start_override=23,
            token_limit=999999999
        )
        assert options_max.interval == 3600
        assert options_max.block_start_override == 23
        assert options_max.token_limit == 999999999

    def test_monitor_options_immutability(self):
        """Test that MonitorOptions is properly immutable if frozen."""
        options = MonitorOptions(display_mode=DisplayMode.COMPACT)

        # Should be able to access all fields
        assert options.display_mode == DisplayMode.COMPACT
        assert options.interval == 5  # default
        assert options.snapshot is False  # default

        # This test ensures the dataclass is properly structured
        # If it were frozen, modification would raise an error
