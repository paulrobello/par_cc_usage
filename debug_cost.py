#!/usr/bin/env python3
"""Debug script to analyze cost calculations."""

import asyncio
import sys
from pathlib import Path

# Add the src directory to the path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

from par_cc_usage.config import load_config
from par_cc_usage.token_calculator import build_usage_snapshot
from par_cc_usage.pricing import debug_model_pricing, calculate_token_cost


async def main():
    """Debug cost calculations."""
    config = load_config()

    print("=== Building usage snapshot ===")
    snapshot = await build_usage_snapshot(config, progress_callback=None, suppress_output=True)

    # Get current unified block
    from par_cc_usage.token_calculator import get_current_unified_block
    current_block = get_current_unified_block(snapshot.unified_blocks)

    if not current_block:
        print("No current unified block found")
        return

    print(f"=== Current Unified Block ({current_block.id}) ===")
    print(f"Total entries: {len(current_block.entries)}")
    print(f"Total tokens (display): {current_block.total_tokens:,}")
    print(f"Total tokens (actual): {current_block.actual_tokens:,}")
    print(f"Messages processed: {current_block.messages_processed}")
    print(f"Models used: {current_block.full_model_names}")

    # Check a few sample entries
    print(f"\n=== Sample entries (first 5) ===")
    total_manual_cost = 0.0

    for i, entry in enumerate(current_block.entries[:5]):
        usage = entry.token_usage
        print(f"\nEntry {i+1}:")
        print(f"  Model: {entry.full_model_name}")
        print(f"  Display tokens: in={usage.input_tokens:,}, out={usage.output_tokens:,}, cache_create={usage.cache_creation_input_tokens:,}, cache_read={usage.cache_read_input_tokens:,}")
        print(f"  Actual tokens: in={usage.actual_input_tokens:,}, out={usage.actual_output_tokens:,}, cache_create={usage.actual_cache_creation_input_tokens:,}, cache_read={usage.actual_cache_read_input_tokens:,}")

        # Calculate cost for this entry
        cost = await calculate_token_cost(
            entry.full_model_name,
            usage.actual_input_tokens,
            usage.actual_output_tokens,
            usage.actual_cache_creation_input_tokens,
            usage.actual_cache_read_input_tokens,
        )
        print(f"  Cost: ${cost.total_cost:.4f}")
        total_manual_cost += cost.total_cost

    print(f"\n=== Manual cost calculation (first 5 entries): ${total_manual_cost:.4f} ===")

    # Get unified block total cost
    unified_cost = await snapshot.get_unified_block_total_cost()
    print(f"=== Unified block total cost: ${unified_cost:.4f} ===")

    # Debug pricing for the most common model
    if current_block.full_model_names:
        most_common_model = list(current_block.full_model_names)[0]
        print(f"\n=== Pricing debug for {most_common_model} ===")
        pricing_debug = await debug_model_pricing(most_common_model)
        for key, value in pricing_debug.items():
            print(f"  {key}: {value}")


if __name__ == "__main__":
    asyncio.run(main())
