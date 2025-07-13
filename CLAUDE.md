# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

PAR CC Usage is a Python-based CLI tool for tracking and analyzing Claude Code token usage across multiple projects. It monitors JSONL files in Claude's project directories, provides real-time usage statistics, and manages 5-hour billing blocks.

## Development Commands

### Installation and Setup
```bash
# Install dependencies with uv (required)
uv sync
```

### Running the Application
```bash
# Run in development mode with hot reload
make dev

# Run normally
make run
# or
uv run pccu monitor
```

### Code Quality Commands
```bash
# Format, lint, and typecheck (run before commits)
make checkall

# Individual commands
make format      # Fix formatting with ruff
make lint        # Check linting with ruff  
make typecheck   # Type check with pyright
```

### Testing and Debugging

# Run tests
```bash
make test
```

```bash
# Debug unified block calculation
uv run pccu debug-unified

# Debug block information
uv run pccu debug-blocks --show-inactive

# Test webhooks (Discord/Slack)
uv run pccu test-webhook

# Take a single debug snapshot (monitor once and exit)
uv run pccu monitor --snapshot

# Enable debug output to see processing messages
uv run pccu monitor --debug

# Test pricing functionality including burn rate cost estimation
uv run pccu monitor --show-pricing --snapshot
uv run pccu list --show-pricing

# Debug pricing fallbacks (using Python directly)
uv run python -c "
import asyncio
from src.par_cc_usage.pricing import debug_model_pricing, calculate_token_cost

async def test():
    # Test unknown model handling
    info = await debug_model_pricing('Unknown')
    cost = await calculate_token_cost('Unknown', 1000, 500)
    print(f'Unknown model: \${cost.total_cost}, info: {info}')
    
    # Test fallback pricing
    cost = await calculate_token_cost('claude-opus-custom', 1000, 500)
    print(f'Custom opus model cost: \${cost.total_cost}')

asyncio.run(test())
"

# Test burn rate cost estimation specifically
uv run pytest tests/test_display.py -k "test_calculate_burn_rate" -v
```

## Architecture Overview

### Core Components

1. **Data Flow Pipeline**:
   - `file_monitor.py`: Watches Claude project directories for JSONL file changes using file position tracking
   - `token_calculator.py`: Parses JSONL lines and calculates token usage per 5-hour blocks with deduplication
   - `models.py`: Core data structures (TokenUsage, TokenBlock, Session, Project, UsageSnapshot) with timezone support
   - `display.py`: Rich-based terminal UI for real-time monitoring with burn rate analytics and cost tracking
   - `pricing.py`: LiteLLM integration for accurate cost calculations across all Claude models

2. **Unified Block System**:
   The unified billing block calculation uses an optimal approach to identify the current billing period:
   - **Current Block Selection**: Selects blocks that contain the current time, preferring the earliest start time among active blocks
   - **Hour-floored start times**: All blocks start at the top of the hour in UTC
   - **Manual Override**: CLI `--block-start HOUR` option for testing and corrections (hour 0-23)
   - Logic in `token_calculator.py:create_unified_blocks()` function provides accurate billing block identification
   - Debug with `pccu debug-unified` to see block selection details
   - Automatic gap detection for inactivity periods > 5 hours

   #### Unified Block Algorithm
   The `create_unified_blocks()` function implements an optimal block selection approach:

   1. **Collect All Blocks**: Gathers all blocks across all projects and sessions
   2. **Filter Active Blocks**: Keeps only blocks that are currently active
   3. **Find Current Blocks**: Identifies blocks that contain the current time
   4. **Select Earliest**: Among current blocks, selects the one with the earliest start time
   5. **Fallback Selection**: Uses earliest active block if no blocks contain the current time

   **Block Activity Logic**: A block is active if:
   - Time since last activity < 5 hours (session duration)
   - Current time < block end time (start + 5 hours)

   **Key Architectural Decision**: This approach ensures consistent billing period representation by selecting the earliest active block that contains the current time, providing stable and predictable billing block identification.

3. **Enhanced Configuration System**:
   - `config.py`: Pydantic-based configuration with structured environment variable parsing
   - `xdg_dirs.py`: XDG Base Directory specification compliance for proper file organization
   - `enums.py`: Centralized type-safe enums for all string-based configurations
   - `options.py`: Structured dataclasses for command-line option management
   - Config precedence: Environment vars > Config file > Defaults
   - Auto-saves token limit adjustments when exceeded
   - **XDG Compliance**: Config, cache, and data files stored in standard Unix/Linux locations
   - **Legacy Migration**: Automatic migration of existing config files to XDG locations
   - **Timezone Support**: Full timezone handling with configurable display formats via `TimeFormat` enum
   - **Display Customization**: Type-safe configuration options with validation

4. **Comprehensive Command Structure**:
   - `main.py`: Typer CLI app with main commands (monitor, list, init, etc.)
   - `commands.py`: Debug and analysis commands (debug-blocks, debug-unified, debug-activity, etc.)
   - `list_command.py`: Specialized listing and reporting functionality with multiple output formats
   - **Notification System**: Discord and Slack webhook integration for block completion alerts

5. **Advanced Analytics**:
   - **Burn Rate Calculation**: Tokens per minute tracking with ETA estimation
   - **Block Progress Tracking**: Real-time 5-hour block progress with visual indicators
   - **Model Usage Analysis**: Per-model token breakdown (Opus, Sonnet, Haiku)
   - **Tool Usage Tracking**: Track and display Claude Code tool usage (Read, Edit, Bash, etc.) with counts
   - **Activity Pattern Detection**: Historical usage analysis with configurable time windows

### Key Architectural Decisions

1. **Optimal Block Logic**: Billing block selection uses hour-boundary preference for consistent billing period representation
2. **XDG Base Directory Compliance**: Configuration, cache, and data files follow XDG specification for proper system integration
3. **Legacy Migration Support**: Automatic detection and migration of existing config files to XDG locations
4. **Deduplication**: Uses message IDs and request IDs to prevent double-counting tokens when files are re-read
5. **File Monitoring Cache**: Tracks file positions to avoid re-processing entire files (stored in XDG cache directory)
6. **Timezone Handling**: All internal times are UTC, converted to configured timezone for display
7. **Model Normalization**: Maps various Claude model names to simplified display names via `ModelType` enum
8. **Per-Model Token Tracking**: TokenBlocks track adjusted tokens per model with multipliers applied (Opus 5x, others 1x)
9. **Tool Usage Extraction**: Parses JSONL message content arrays to extract tool_use blocks and track tool names and call counts
10. **Structured JSON Validation**: Uses Pydantic models for type-safe JSONL parsing and validation
11. **Type-Safe Configuration**: Centralized enums and structured dataclasses eliminate string-based configurations

### Data Model Relationships

```
UsageSnapshot (aggregates everything)
  ├── unified_block_tokens() → tokens for current billing window only
  ├── unified_block_tokens_by_model() → per-model breakdown for billing window
  └── Projects (by project name)
       └── Sessions (by session ID)
            └── TokenBlocks (5-hour periods)
                 ├── TokenUsage (individual messages)
                 └── model_tokens (per-model adjusted tokens with multipliers)
```

### Pricing System Architecture

The pricing system (`pricing.py`) provides accurate cost calculations with robust fallback handling:

#### Core Components:
- **PricingCache**: Async cache for LiteLLM pricing data with intelligent fallback logic
- **ModelPricing**: Pydantic model for structured pricing data validation
- **TokenCost**: Result structure for cost calculations with detailed breakdown

#### Fallback Logic Hierarchy:
1. **Direct Match**: Exact model name lookup in LiteLLM pricing cache
2. **Variation Matching**: Tests common Claude model name patterns (e.g., `anthropic/claude-*`)
3. **Fuzzy Matching**: Partial string matching for similar model names
4. **Pattern-Based Fallbacks**: 
   - Models containing "opus" → Claude Opus pricing
   - Models containing "sonnet" → Claude Sonnet pricing
   - Models containing "haiku" → Claude Haiku pricing
5. **Generic Claude Fallback**: Any Claude model → Sonnet pricing as safe default
6. **Unknown Model Handling**: Models marked as "Unknown" → $0.00 cost

#### Integration Points:
- **Display Integration**: Cost columns automatically added to activity tables when `show_pricing` enabled
- **Burn Rate Cost Estimation**: Real-time 5-hour block cost projection in burn rate line based on current spending rate
- **Async Architecture**: All pricing operations are async to prevent UI blocking
- **Error Resilience**: Pricing failures don't break functionality, gracefully fall back to no-cost display
- **Debug Support**: `debug_model_pricing()` function for troubleshooting pricing issues

#### Burn Rate Cost Estimation:
The burn rate cost estimation provides intelligent cost projection for 5-hour billing blocks:

1. **Cost Per Minute Calculation**: `current_cost / elapsed_minutes` - calculates spending rate based on actual usage
2. **5-Hour Projection**: `cost_per_minute * 60 * 5.0` - projects cost for full billing block
3. **Display Integration**: Added to burn rate line when `show_pricing` enabled
4. **Async Implementation**: `_calculate_burn_rate()` method made async to support cost calculations
5. **Sync Compatibility**: `_calculate_burn_rate_sync()` method for non-pricing contexts
6. **Graceful Fallback**: Cost estimation failures don't break burn rate display

**Display Format**: `"531K/m Est: 159.3M (90%) Est: $65.51 ETA: 2h 28m"`
- Token burn rate + estimated tokens + estimated cost + ETA

### Critical File Interactions

1. **Monitor Mode Flow**:
   - `main.py:monitor()` → Parses structured `MonitorOptions` via `_parse_monitor_options()`
   - `xdg_dirs.py:get_config_file_path()` → Determines XDG-compliant config file location
   - `config.py:load_config()` → Loads config with automatic legacy migration support
   - `main.py:_apply_command_overrides()` → Applies configuration overrides
   - `file_monitor.py` → Detects changes, reads new lines (cache stored in XDG cache directory)
   - `token_calculator.py:_validate_jsonl_data()` → Validates with Pydantic models
   - `token_calculator.py:process_jsonl_line()` → Processes with extracted helper functions
   - `display.py:MonitorDisplay` → Updates terminal UI

2. **Unified Block Selection**:
   - `token_calculator.py:aggregate_usage()` → Creates UsageSnapshot
   - `token_calculator.py:create_unified_blocks()` → Implements optimal block selection algorithm (earliest active block preference)
   - `models.py:UsageSnapshot.unified_block_start_time` → Returns current billing block start time
   - Logic correctly identifies the current billing block by selecting the earliest active block that contains the current time

## Important Implementation Details

### Token Block Logic
- Blocks are 5 hours long, starting from the hour of first activity (UTC hour-floored)
- New blocks are created when: time since block start > 5 hours OR time since last activity > 5 hours
- Gap blocks are inserted for periods of inactivity > 5 hours
- **Current Block Selection**: Uses optimal block selection that prefers hour boundaries for consistent billing representation
- **Per-Model Token Tracking**: Each block maintains a `model_tokens` dictionary that tracks adjusted tokens per model with multipliers applied during token processing

### File Processing
- Only processes new lines added to JSONL files (uses file position tracking)
- Handles multiple Claude project directories (legacy and new paths)
- Can disable cache with `--no-cache` flag for full reprocessing
- **XDG Cache Storage**: File monitoring cache stored in `~/.cache/par_cc_usage/file_states.json`
- **Legacy Migration**: Automatic detection and migration of config files from current directory to XDG locations

### Display Formatting
- Token counts use abbreviated format (e.g., "1.2M" for millions)
- Time formats are configurable (12h/24h)
- Project name prefixes can be stripped for cleaner display

### Notification System
- Discord and Slack webhooks for block completion notifications
- Tracks sent notifications to avoid duplicates
- Configurable cooldown between notifications

## XDG Base Directory Implementation

### Directory Structure

PAR CC Usage implements the XDG Base Directory Specification for proper file organization:

- **Config Directory**: `~/.config/par_cc_usage/` (respects `XDG_CONFIG_HOME`)
  - `config.yaml` - Main configuration file
- **Cache Directory**: `~/.cache/par_cc_usage/` (respects `XDG_CACHE_HOME`) 
  - `file_states.json` - File monitoring cache
- **Data Directory**: `~/.local/share/par_cc_usage/` (respects `XDG_DATA_HOME`)
  - Reserved for future application data

### XDG Module (`xdg_dirs.py`)

Provides utilities for XDG-compliant directory management:

- `get_config_dir()` - Returns XDG config directory
- `get_cache_dir()` - Returns XDG cache directory  
- `get_data_dir()` - Returns XDG data directory
- `get_config_file_path()` - Returns full path to config file
- `ensure_xdg_directories()` - Creates necessary directories
- `migrate_legacy_config()` - Migrates legacy config files
- `get_legacy_config_paths()` - Returns potential legacy config locations

### Legacy Migration Process

1. **Detection**: Checks for existing config files in legacy locations:
   - `./config.yaml` (current working directory)
   - `~/.par_cc_usage/config.yaml` (home directory)

2. **Migration**: If legacy config exists and XDG config doesn't:
   - Creates XDG config directory if needed
   - Copies legacy config to XDG location
   - Preserves all existing settings
   - Returns `True` if migration performed

3. **Integration**: Migration happens automatically in `config.py:_load_config_file()`:
   - Called during normal config loading process
   - No user intervention required
   - Seamless transition from legacy to XDG locations

### Environment Variable Support

Respects standard XDG environment variables:

- `XDG_CONFIG_HOME` - Override config directory (default: `~/.config`)
- `XDG_CACHE_HOME` - Override cache directory (default: `~/.cache`)
- `XDG_DATA_HOME` - Override data directory (default: `~/.local/share`)

### Benefits

- **System Integration**: Follows Unix/Linux conventions for better system integration
- **User Expectation**: Config files where users expect them (`~/.config/`)
- **Backup Compatibility**: Standard locations are included in most backup solutions
- **Multi-user Support**: Proper isolation of user-specific data
- **Package Manager Friendly**: Standard locations for distribution packaging

## Code Quality Standards

### Complexity Management
All functions maintain cyclomatic complexity ≤ 10 through systematic refactoring:
- Extraction of helper functions for specific responsibilities
- Clear separation of concerns (e.g., data collection vs. processing)
- Use of early returns to reduce nesting
- Functional decomposition of complex operations

### Recent Code Quality Improvements (2024)

**Major Complexity Refactoring**: Successfully reduced cyclomatic complexity across all core modules:

#### Display Module (`display.py`)
- **`_calculate_burn_rate()`** (11 → ≤10): Extracted cost calculation, color determination, and text formatting into separate helper functions
- **`_populate_project_table()`** (17 → ≤10): Split into table setup, data collection, cost calculation, and row formatting functions
- **`_populate_session_table()`** (12 → ≤10): Decomposed into column setup, data collection, and row formatting helpers

#### Command Module (`commands.py`)
- **`debug_session_table()`** (13 → ≤10): Extracted block overlap analysis, statistics collection, and summary display functions

#### Main Module (`main.py`)
- **`list_sessions()`** (19 → ≤10): Separated project scanning, table creation, filtering, and cost calculation
- **`debug_sessions()`** (13 → ≤10): Split into header display, table creation, block analysis, and summary functions
- **`filter_sessions()`** (36 → ≤10): Extensive decomposition into filter logic, display formatting, and output generation functions

#### Benefits of Complexity Reduction
1. **Improved Readability**: Each function has a single, clear responsibility
2. **Better Maintainability**: Changes to specific functionality are isolated
3. **Increased Testability**: Helper functions can be tested independently
4. **Code Reusability**: Common logic extracted into reusable functions
5. **Reduced Cognitive Load**: Functions are easier to understand and debug

### Key Refactored Components
- **XDG Directory Support** (`xdg_dirs.py`): Centralized XDG Base Directory specification implementation
- **Configuration Loading** (`config.py`): Separated file loading, environment parsing, nested config handling, and legacy migration
- **Monitor Function** (`main.py`): Split into initialization, token detection, and file processing helpers
- **Debug Commands** (`commands.py`): Extracted display and data collection logic with complexity-optimized helper functions
- **Block Selection** (`token_calculator.py`): Optimal unified block logic with earliest active block preference for consistent billing representation
- **JSONL Processing** (`token_calculator.py`): Isolated message validation and block creation
- **Display System** (`display.py`): Modular UI components with separated rendering, calculation, and formatting logic
- **Session Management** (`main.py`): Decomposed session listing, filtering, and analysis functions

### Code Quality Metrics
- **Cyclomatic Complexity**: All functions ≤ 10 (enforced by ruff)
- **Test Coverage**: 512+ test cases covering core functionality
- **Type Safety**: Full type annotations with pyright validation
- **Code Formatting**: Consistent style with ruff formatting
- **Documentation**: Comprehensive docstrings following Google style


## Version Management

### Version Management
- **Important** ONLY bump the project version if the user requests it
- **Single Source**: Version is defined only in `src/par_cc_usage/__init__.py`
- **Dynamic Loading**: `pyproject.toml` uses hatch's dynamic versioning to automatically load version from `__init__.py`
- **No Sync Required**: No need to keep multiple files in sync - version is defined in one place only

### Version Bumping Process
When bumping the version of the tool:
1. Update only `src/par_cc_usage/__init__.py` line 3: `__version__ = "x.y.z"`
2. Update the README.md "What's New" section with the new version
3. Make sure you update the TOC "What's New" section with the new version
4. The TOC "What's New" section should have the newest 6 versions, the 6th entry should have a label of 'older...'

## Memory Notes

### Tools and Workflow
- When trying to read JSON/JSONL files from the claude code project folder use the json_analyzer.py tool
- The json_analyzer.py tool supports both JSON (.json) and JSONL (.jsonl) formats with automatic detection
- Use `uv run python -m par_cc_usage.json_analyzer analyze <file>` to analyze JSON/JSONL files
