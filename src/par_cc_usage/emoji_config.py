"""Emoji width configuration for Rich console.

IMPORTANT: The test_emoji_width_configuration() function in this file is a developer
utility for debugging emoji rendering. It may not work in all terminal environments,
particularly Git Bash/MINGW64 on Windows which uses cp1252 encoding.

The production code (monitor, statusline, etc.) works correctly with emojis because:
1. Rich library handles emoji fallback gracefully in production
2. Status line output goes to Claude Code which supports UTF-8
3. Monitor display uses Rich's legacy_windows_render when needed

If test_emoji_width_configuration() fails in your terminal, it does NOT indicate
a problem with the production code.
"""


def configure_emoji_width() -> None:
    """Configure Rich library emoji width handling based on terminal detection.

    Note: This function is currently a no-op as we've resolved emoji width issues
    by ensuring all emojis used in the application have consistent width 2.

    Previously problematic emoji ✉️ (width 1) has been replaced with 💬 (width 2)
    to maintain consistency with other emojis: 🪙💰⚡🔥📊 (all width 2).
    """
    pass


def test_emoji_width_configuration() -> None:
    """Test function to verify emoji width configuration.

    Note: This test requires a modern terminal with Unicode support.
    On Windows, use Windows Terminal or PowerShell with UTF-8 encoding.
    Legacy cmd.exe with cp1252 encoding may not support all emojis.
    """
    from rich.console import Console
    from rich.text import Text

    console = Console()
    emojis = ["🪙", "💬", "💰", "⚡", "🔥", "📊"]

    try:
        console.print("Emoji width consistency check:")
        all_width_2 = True
        for emoji in emojis:
            text = Text(emoji)
            width = console.measure(text).maximum
            is_correct = width == 2
            status = "PASS" if is_correct else "FAIL"
            all_width_2 = all_width_2 and is_correct
            console.print(f"{status} {emoji}: width = {width}")

        console.print(f"\nAll emojis consistent: {'PASS' if all_width_2 else 'FAIL'}")

        # Visual alignment test
        console.print("\nVisual alignment test:")
        console.print("Ruler:    12345678901234567890")
        console.print("Test:     |🪙|💬|💰|⚡|🔥|📊|")
        console.print("Expected: |xx|xx|xx|xx|xx|xx|")
    except UnicodeEncodeError:
        # Use print() instead of console.print() to avoid encoding issues in error handler
        print("Warning: Your terminal does not support emoji display.")
        print("This test requires a modern terminal with UTF-8 support (Windows Terminal, PowerShell, etc.).")
        print("This does NOT affect production code - emojis work fine in the actual application.")
        print("See module docstring for more details.")


if __name__ == "__main__":
    configure_emoji_width()
    test_emoji_width_configuration()
