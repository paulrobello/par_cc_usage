"""Emoji width configuration for Rich console."""


def configure_emoji_width() -> None:
    """Configure Rich library emoji width handling based on terminal detection.

    Note: This function is currently a no-op as we've resolved emoji width issues
    by ensuring all emojis used in the application have consistent width 2.

    Previously problematic emoji ✉️ (width 1) has been replaced with 💬 (width 2)
    to maintain consistency with other emojis: 🪙💰⚡🔥📊 (all width 2).
    """
    pass


def test_emoji_width_configuration() -> None:
    """Test function to verify emoji width configuration."""
    from rich.console import Console
    from rich.text import Text

    console = Console()
    emojis = ["🪙", "💬", "💰", "⚡", "🔥", "📊"]

    print("Emoji width consistency check:")
    all_width_2 = True
    for emoji in emojis:
        text = Text(emoji)
        width = console.measure(text).maximum
        is_correct = width == 2
        status = "✓" if is_correct else "✗"
        all_width_2 = all_width_2 and is_correct
        print(f"{status} {emoji}: width = {width}")

    print(f"\nAll emojis consistent: {'✓ YES' if all_width_2 else '✗ NO'}")

    # Visual alignment test
    print("\nVisual alignment test:")
    print("Ruler:    12345678901234567890")
    print("Test:     |🪙|💬|💰|⚡|🔥|📊|")
    print("Expected: |xx|xx|xx|xx|xx|xx|")


if __name__ == "__main__":
    configure_emoji_width()
    test_emoji_width_configuration()
