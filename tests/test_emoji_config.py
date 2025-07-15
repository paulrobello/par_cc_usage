"""Tests for the emoji_config module."""

from par_cc_usage.emoji_config import configure_emoji_width, test_emoji_width_configuration


class TestEmojiConfig:
    """Test emoji configuration functionality."""

    def test_configure_emoji_width(self):
        """Test configure_emoji_width function (no-op)."""
        # This function is currently a no-op, so just test it doesn't raise
        configure_emoji_width()

    def test_emoji_width_configuration(self, capsys):
        """Test emoji width configuration test function."""
        # Test that the test function runs without error
        test_emoji_width_configuration()

        # Capture the output
        captured = capsys.readouterr()

        # Should print emoji width information
        assert "Emoji width consistency check:" in captured.out
        assert "Visual alignment test:" in captured.out
        assert "🪙" in captured.out
        assert "💬" in captured.out
        assert "💰" in captured.out
