"""
Simple tests for the commands module.
"""



from par_cc_usage.commands import (
    debug_blocks,
    debug_recent_activity,
    debug_unified_block,
)


class TestDebugCommands:
    """Test the debug commands."""

    def test_debug_blocks_runs_without_error(self, capsys):
        """Test that debug_blocks runs without error."""
        # Just ensure it runs - pass None for config file to use defaults
        debug_blocks(config_file=None, show_inactive=False)

        captured = capsys.readouterr()
        # Should have some output
        assert len(captured.out) > 0

    def test_debug_unified_block_runs(self, capsys):
        """Test that debug_unified_block runs without error."""
        debug_unified_block(config_file=None)

        captured = capsys.readouterr()
        assert len(captured.out) > 0

    def test_debug_recent_activity_runs(self, capsys):
        """Test that debug_recent_activity runs without error."""
        debug_recent_activity(config_file=None, hours=24)

        captured = capsys.readouterr()
        assert len(captured.out) > 0
