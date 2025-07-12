# PAR CC Usage

Claude Code usage tracking tool with real-time monitoring and analysis.

[![PyPI](https://img.shields.io/pypi/v/par-cc-usage)](https://pypi.org/project/par-cc-usage/)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/par-cc-usage.svg)](https://pypi.org/project/par-cc-usage/)  
![Runs on Linux | MacOS | Windows](https://img.shields.io/badge/runs%20on-Linux%20%7C%20MacOS%20%7C%20Windows-blue)
![Arch x86-63 | ARM | AppleSilicon](https://img.shields.io/badge/arch-x86--64%20%7C%20ARM%20%7C%20AppleSilicon-blue)
![PyPI - Downloads](https://img.shields.io/pypi/dm/par-cc-usage)
![PyPI - License](https://img.shields.io/pypi/l/par-cc-usage)

[!["Buy Me A Coffee"](https://www.buymeacoffee.com/assets/img/custom_images/orange_img.png)](https://buymeacoffee.com/probello3)

![PAR CC Usage Monitor](https://raw.githubusercontent.com/paulrobello/par_cc_usage/main/Screenshot.png)
*Real-time monitoring interface showing token usage, burn rate analytics, tool usage tracking, and project activity*

## Table of Contents

- [Features](#features)
  - [📊 Real-Time Monitoring](#-real-time-monitoring)
  - [🔥 Advanced Burn Rate Analytics](#-advanced-burn-rate-analytics)
  - [⚙️ Intelligent Block Management](#️-intelligent-block-management)
  - [🎯 Smart Features](#-smart-features)
  - [💰 Cost Tracking & Pricing](#-cost-tracking--pricing)
  - [📁 File System Support](#-file-system-support)
  - [🌐 Configuration & Customization](#-configuration--customization)
  - [🎨 Theme System](#-theme-system)
  - [🔔 Notification System](#-notification-system)
  - [🛠️ Developer Tools](#️-developer-tools)
- [Installation](#installation)
- [Usage](#usage)
  - [Monitor Token Usage](#monitor-token-usage)
  - [List Usage Data](#list-usage-data)
  - [Configuration Management](#configuration-management)
  - [Cache Management](#cache-management)
  - [Webhook Notifications](#webhook-notifications)
  - [JSONL Analysis](#jsonl-analysis)
  - [Debug Commands](#debug-commands)
- [Configuration](#configuration)
  - [Directory Structure](#directory-structure)
  - [Legacy Migration](#legacy-migration)
  - [Config File Example](#config-file-example)
  - [Environment Variables](#environment-variables)
- [Display Features](#display-features)
  - [Unified Block System](#unified-block-system)
  - [Current Billing Block Identification](#current-billing-block-identification)
  - [Manual Override](#manual-override)
  - [Compact Interface](#compact-interface)
  - [Optional Session Details](#optional-session-details)
  - [Project Aggregation Mode](#project-aggregation-mode-default)
  - [Smart Token Limit Management](#smart-token-limit-management)
  - [Model Display Names and Token Multipliers](#model-display-names-and-token-multipliers)
  - [Time Format Options](#time-format-options)
  - [Project Name Customization](#project-name-customization)
  - [Cost Tracking & Pricing](#cost-tracking--pricing-1)
  - [Webhook Notifications](#webhook-notifications-1)
- [File Locations](#file-locations)
  - [XDG Base Directory Specification](#xdg-base-directory-specification)
  - [Configuration Files](#configuration-files)
  - [Legacy File Migration](#legacy-file-migration)
  - [Environment Variable Override](#environment-variable-override)
- [Coming Soon](#coming-soon)
- [What's New](#whats-new)
  - [v0.1.4 - Theme System Implementation](#v014---theme-system-implementation)
  - [v0.1.3 - Code Quality Improvements](#v013---code-quality-improvements)
  - [v0.1.2 - Pricing & Cost Tracking](#v012---pricing--cost-tracking)
  - [v0.1.1 - Enhanced Analytics](#v011---enhanced-analytics)
  - [v0.1.0 - Core Features](#v010---core-features)
  - [older...](#older)
- [Development](#development)

## Features

### 📊 Real-Time Monitoring
- **Live token tracking**: Monitor usage across all Claude Code projects in real-time
- **5-hour billing blocks**: Unified block system that accurately reflects Claude's billing structure
- **Multi-session support**: When multiple sessions are active, they share billing blocks intelligently
- **Visual progress indicators**: Real-time progress bars for current billing period

### 🔥 Advanced Burn Rate Analytics
- **Per-minute tracking**: Granular burn rate display (tokens/minute) for precise monitoring
- **Estimated completion**: Projects total usage for full 5-hour block based on current rate
- **ETA with clock time**: Shows both duration and actual time when limit will be reached
- **Smart color coding**: Visual indicators based on usage levels (green/orange/red)

### ⚙️ Intelligent Block Management
- **Smart strategy**: Intelligent algorithm that automatically selects optimal billing blocks
- **Manual override**: CLI option to set custom block start times for testing or corrections
- **Automatic detection**: Smart detection of session boundaries and billing periods
- **Gap handling**: Proper handling of inactivity periods longer than 5 hours

### 🎯 Smart Features
- **Auto-adjusting limits**: Automatically increases token limits when exceeded and saves to config
- **Deduplication**: Prevents double-counting using message and request IDs
- **Model name simplification**: Clean display names (Opus, Sonnet) for better readability
- **Session sorting**: Newest-first ordering for active sessions
- **Per-model token tracking**: Accurate token attribution with proper multipliers (Opus 5x, others 1x)
- **Compact display mode**: Minimal interface option for reduced screen space usage

### 💰 Cost Tracking & Pricing
- **Real-time cost calculations**: Live cost tracking using LiteLLM pricing data
- **Per-model cost breakdown**: Accurate cost attribution for each Claude model
- **Activity table pricing**: Optional cost columns in project and session views
- **Configurable pricing display**: Enable/disable cost tracking via configuration or command-line
- **Integrated pricing cache**: Efficient pricing lookups with built-in caching
- **Intelligent fallbacks**: When exact model names aren't found, uses pattern matching to find closest pricing
- **Unknown model handling**: Models marked as "Unknown" automatically display $0.00 cost
- **Robust error handling**: Missing pricing data doesn't break functionality or display

### 📁 File System Support
- **Multi-directory monitoring**: Supports both legacy (`~/.claude/projects`) and new paths
- **Efficient caching**: File position tracking to avoid re-processing entire files
- **Cache management**: Optional cache disabling for full file reprocessing
- **JSONL analysis**: Deep analysis of Claude Code data structures
- **XDG Base Directory compliance**: Uses standard Unix/Linux directory conventions
- **Legacy migration**: Automatically migrates existing config files to XDG locations

### 🌐 Configuration & Customization
- **XDG directory compliance**: Config, cache, and data files stored in standard locations
- **Automatic migration**: Legacy config files automatically moved to XDG locations
- **Timezone support**: Full timezone handling with configurable display formats
- **Time formats**: 12-hour or 24-hour time display options
- **Project name cleanup**: Strip common path prefixes for cleaner display
- **Flexible output**: Table, JSON, and CSV export formats

### 🎨 Theme System
- **Multiple built-in themes**: Choose from 5 carefully crafted themes for different preferences
- **Light and dark themes**: Options for both dark terminal and light terminal users
- **Accessibility support**: High contrast theme meeting WCAG AAA standards
- **Session-based overrides**: Temporarily change themes for individual command runs
- **Rich color integration**: Semantic color system with consistent visual language
- **CLI theme management**: Built-in commands for theme configuration and preview

### 🔔 Notification System
- **Discord integration**: Webhook notifications for billing block completion
- **Smart filtering**: Only notifies for blocks with actual activity
- **Cooldown protection**: Configurable minimum time between notifications
- **Rich information**: Detailed usage statistics in notifications

### 🛠️ Developer Tools
- **Debug commands**: Comprehensive debugging tools for block calculation and timing
- **Activity analysis**: Historical activity pattern analysis
- **JSONL analyzer**: Built-in `jsonl_analyzer.py` tool for examining Claude Code data files
- **Webhook testing**: Built-in Discord and Slack webhook testing

## Installation

### Option 1: Install from PyPI (Recommended)

Using [uv](https://docs.astral.sh/uv/) (fastest):
```bash
uv tool install par-cc-usage
```

Using pip:
```bash
pip install par-cc-usage
```

After installation, you can run the tool directly:
```bash
pccu monitor
```

### Option 2: Development Installation

Clone the repository and install in development mode:

```bash
# Clone the repository
git clone https://github.com/paulrobello/par_cc_usage.git
cd par_cc_usage

# Install with uv (recommended)
uv sync

# Or install with pip
pip install -e .
```

Run the tool in development mode:
```bash
# Using uv
uv run pccu monitor

# Or using make (if available)
make run

# Or directly with Python
python -m par_cc_usage.main monitor
```

### Prerequisites

- Python 3.12 or higher
- Claude Code must be installed and have generated usage data
- [uv](https://docs.astral.sh/uv/) (recommended) or pip for installation

## Usage

### Monitor Token Usage

Monitor token usage in real-time with comprehensive options:

```bash
# Basic monitoring (default 5-second interval)
pccu monitor

# Compact mode for minimal display
pccu monitor --compact

# Enhanced monitoring with session details
pccu monitor --show-sessions

# High-frequency monitoring with custom settings
pccu monitor --interval 2 --token-limit 1000000 --show-sessions

# Monitor with custom configuration
pccu monitor --config production-config.yaml

# Testing and debugging scenarios
pccu monitor --no-cache --block-start 18  # Fresh scan + custom block timing
pccu monitor --block-start 14 --show-sessions  # Override block start time

# Production monitoring examples
pccu monitor --interval 10 --token-limit 500000  # Conservative monitoring
pccu monitor --show-sessions --config team-config.yaml  # Team dashboard
pccu monitor --compact --interval 3  # Minimal display with frequent updates

# Cost tracking and pricing
pccu monitor --show-pricing  # Enable cost calculations and display
pccu monitor --show-sessions --show-pricing  # Session view with cost breakdown
pccu monitor --show-pricing --config pricing-config.yaml  # Cost monitoring with config

# Theme customization
pccu monitor --theme light  # Use light theme for this session
pccu monitor --theme dark --show-sessions  # Dark theme with session details
pccu monitor --theme accessibility --show-pricing  # High contrast theme with pricing
pccu monitor --theme minimal --compact  # Minimal theme with compact display
```

#### Monitor Display Features
- **Real-time updates**: Live token consumption tracking
- **Burn rate analytics**: Tokens/minute with ETA to limit (e.g., "1.2K/m ETA: 2.3h (10:45 PM)")
- **Cost tracking**: Real-time cost calculations using LiteLLM pricing (when `--show-pricing` is enabled)
- **Burn rate cost estimation**: Intelligent cost projection for 5-hour blocks based on current spending rate (e.g., "531K/m Est: 159.3M (90%) Est: $65.51 ETA: 2h 28m")
- **Block progress**: Visual 5-hour billing block progress with time remaining
- **Model breakdown**: Per-model token usage (Opus, Sonnet) with optional cost breakdown
- **Session details**: Individual session tracking when `--show-sessions` is used
- **Activity tables**: Project or session aggregation views with optional cost columns

### List Usage Data

Generate usage reports:

```bash
# List all usage data (table format)
pccu list

# Output as JSON
pccu list --format json

# Output as CSV
pccu list --format csv

# Sort by different fields
pccu list --sort-by tokens
pccu list --sort-by session
pccu list --sort-by project
pccu list --sort-by time
pccu list --sort-by model

# Include cost information in output
pccu list --show-pricing

# Combine sorting and pricing
pccu list --sort-by tokens --show-pricing --format table

# Save detailed report with costs to file
pccu list --show-pricing --output usage-report.json --format json

# Theme customization for list output
pccu list --theme light --show-pricing  # Light theme with pricing
pccu list --theme accessibility --format table  # High contrast theme
pccu list --theme minimal --sort-by tokens  # Minimal theme with token sorting
```

### Configuration Management

```bash
# Initialize configuration file
pccu init

# Set token limit
pccu set-limit 500000

# Use custom config file
pccu init --config my-config.yaml
```

### Cache Management

```bash
# Clear file monitoring cache
pccu clear-cache

# Clear cache with custom config
pccu clear-cache --config my-config.yaml
```

### Theme Management

```bash
# List all available themes
pccu theme list

# Set default theme (saves to config)
pccu theme set light

# Set theme with custom config file
pccu theme set dark --config my-config.yaml

# Check current theme
pccu theme current

# Use temporary theme overrides (doesn't save to config)
pccu monitor --theme light  # Light theme for this session only
pccu list --theme accessibility  # High contrast theme for this command
pccu list-sessions --theme minimal  # Minimal theme for session list
```

### Webhook Notifications

```bash
# Test webhook configuration (Discord and/or Slack)
pccu test-webhook

# Test with custom config file
pccu test-webhook --config my-config.yaml
```

### JSONL Analysis

The `jsonl_analyzer.py` tool helps analyze Claude Code's JSONL data files, which can be quite large with complex nested structures. This tool is essential for understanding the data format when debugging token counting issues or exploring Claude's usage patterns.

This tool is integrated into the main `pccu` CLI but can also be run standalone:

```bash
# Via the main CLI (recommended)
pccu analyze ~/.claude/projects/-Users-username-project/session-id.jsonl

# Or run standalone
uv run python -m par_cc_usage.jsonl_analyzer ~/.claude/projects/-Users-username-project/session-id.jsonl

# Analyze first N lines (useful for large files)
pccu analyze path/to/file.jsonl --max-lines 10

# Customize string truncation length for better readability
pccu analyze path/to/file.jsonl --max-length 50

# Output as JSON for programmatic processing
pccu analyze path/to/file.jsonl --json

# Example: Analyze current project's most recent session
pccu analyze ~/.claude/projects/-Users-probello-Repos-par-cc-usage/*.jsonl --max-lines 20
```

#### JSONL Analyzer Features:
- **Field discovery**: Automatically identifies all fields present in the JSONL data
- **Type information**: Shows data types for each field (string, number, object, array)
- **Smart truncation**: Long strings and arrays are truncated for readability
- **Streaming processing**: Handles large files efficiently without loading everything into memory
- **Usage analysis**: Helps identify token usage patterns and message structures

### Debug Commands

Comprehensive troubleshooting tools for billing block calculations and session timing:

```bash
# Block Analysis
pccu debug-blocks                    # Show all active billing blocks
pccu debug-blocks --show-inactive    # Include completed/inactive blocks

# Unified Block Calculation
pccu debug-unified                   # Step-by-step unified block selection trace
pccu debug-unified -e 18             # Validate against expected hour (24-hour format)
pccu debug-unified --expected-hour 14 # Alternative syntax for validation

# Activity Pattern Analysis
pccu debug-activity                  # Recent activity patterns (last 6 hours)
pccu debug-activity --hours 12      # Extended activity analysis (12 hours)
pccu debug-activity -e 18 --hours 8 # Validate expected start time with custom window

# Advanced Debugging Scenarios
pccu debug-blocks --show-inactive | grep "2025-07-08"  # Filter by specific date
pccu debug-unified --config debug.yaml -e 13           # Use debug configuration with validation
```

#### Debug Output Features
- **Block timing verification**: Confirms correct 5-hour block boundaries
- **Strategy explanation**: Shows why specific blocks were selected
- **Token calculation validation**: Verifies deduplication and aggregation
- **Activity timeline**: Chronological view of session activity
- **Configuration validation**: Confirms settings are applied correctly
- **Expected time validation**: Validates unified block calculations against expected results (24-hour format)

## Configuration

The tool supports configuration via YAML files and environment variables. Configuration files are stored in XDG Base Directory compliant locations:

### Directory Structure

- **Config**: `~/.config/par_cc_usage/config.yaml` (respects `XDG_CONFIG_HOME`)
- **Cache**: `~/.cache/par_cc_usage/` (respects `XDG_CACHE_HOME`)
- **Data**: `~/.local/share/par_cc_usage/` (respects `XDG_DATA_HOME`)

### Legacy Migration

If you have an existing `./config.yaml` file in your working directory, it will be automatically migrated to the XDG config location (`~/.config/par_cc_usage/config.yaml`) when you first run the tool.

**Migration behavior:**
- Checks for legacy config files in current directory and home directory
- Automatically copies to XDG location if XDG config doesn't exist
- Preserves all existing settings during migration
- No manual intervention required

### Config File Example

The configuration file is located at `~/.config/par_cc_usage/config.yaml`:

```yaml
projects_dir: ~/.claude/projects
polling_interval: 5
timezone: America/Los_Angeles
token_limit: 500000
cache_dir: ~/.cache/par_cc_usage  # XDG cache directory (automatically set)
disable_cache: false  # Set to true to disable file monitoring cache
recent_activity_window_hours: 5  # Hours to consider as 'recent' activity for smart strategy (matches billing cycle)
display:
  show_progress_bars: true
  show_active_sessions: false  # Default: hidden for compact display
  update_in_place: true
  refresh_interval: 1
  time_format: 24h  # Time format: '12h' for 12-hour, '24h' for 24-hour
  display_mode: normal  # Display mode: 'normal' or 'compact'
  show_pricing: false  # Enable cost calculations and display (default: false)
  theme: default  # Theme: 'default', 'dark', 'light', 'accessibility', or 'minimal'
  project_name_prefixes:  # Strip prefixes from project names for cleaner display
    - "-Users-"
    - "-home-"
  aggregate_by_project: true  # Aggregate token usage by project instead of individual sessions (default)
notifications:
  discord_webhook_url: https://discord.com/api/webhooks/your-webhook-url
  slack_webhook_url: https://hooks.slack.com/services/your-webhook-url
  notify_on_block_completion: true  # Send notification when 5-hour block completes
  cooldown_minutes: 5  # Minimum minutes between notifications
```

### Environment Variables

- `PAR_CC_USAGE_PROJECTS_DIR`: Override projects directory
- `PAR_CC_USAGE_POLLING_INTERVAL`: Set polling interval
- `PAR_CC_USAGE_TIMEZONE`: Set timezone
- `PAR_CC_USAGE_TOKEN_LIMIT`: Set token limit
- `PAR_CC_USAGE_CACHE_DIR`: Override cache directory (defaults to XDG cache directory)
- `PAR_CC_USAGE_DISABLE_CACHE`: Disable file monitoring cache ('true', '1', 'yes', 'on' for true)
- `PAR_CC_USAGE_RECENT_ACTIVITY_WINDOW_HOURS`: Hours to consider as 'recent' activity for smart strategy (default: 5)
- `PAR_CC_USAGE_SHOW_PROGRESS_BARS`: Show progress bars
- `PAR_CC_USAGE_SHOW_ACTIVE_SESSIONS`: Show active sessions
- `PAR_CC_USAGE_UPDATE_IN_PLACE`: Update display in place
- `PAR_CC_USAGE_REFRESH_INTERVAL`: Display refresh interval
- `PAR_CC_USAGE_TIME_FORMAT`: Time format ('12h' or '24h')
- `PAR_CC_USAGE_THEME`: Theme name ('default', 'dark', 'light', 'accessibility', or 'minimal')
- `PAR_CC_USAGE_PROJECT_NAME_PREFIXES`: Comma-separated list of prefixes to strip from project names
- `PAR_CC_USAGE_AGGREGATE_BY_PROJECT`: Aggregate token usage by project instead of sessions ('true', '1', 'yes', 'on' for true)
- `PAR_CC_USAGE_DISCORD_WEBHOOK_URL`: Discord webhook URL for notifications
- `PAR_CC_USAGE_SLACK_WEBHOOK_URL`: Slack webhook URL for notifications
- `PAR_CC_USAGE_NOTIFY_ON_BLOCK_COMPLETION`: Send block completion notifications ('true', '1', 'yes', 'on' for true)
- `PAR_CC_USAGE_COOLDOWN_MINUTES`: Minimum minutes between notifications

## Display Features

### Unified Block System
When multiple Claude Code sessions are active simultaneously, they all share a single 5-hour billing block. The system intelligently determines which block timing to display based on your work patterns.

**Important**: Token counts and session displays are filtered to show only sessions with activity that overlaps with the unified block time window. This ensures the displayed totals accurately reflect what will be billed for the current 5-hour period. Sessions are included if they have any activity within the billing window, regardless of when they started.

#### Current Billing Block Identification
The system uses a **simple approach** to identify the current billing block:

**Algorithm:**
1. **Identifies active blocks** across all projects and sessions
2. **Returns the most recent active block** chronologically

**Block Activity Criteria:**
A block is considered "active" if both conditions are met:
- **Recent activity**: Time since last activity < 5 hours
- **Within block window**: Current time < block's theoretical end time (start + 5 hours)

**Key Benefits:**
- **Simple and reliable**: No complex filtering or edge case logic
- **Simple logic**: Uses straightforward rules to identify the current billing block
- **Predictable behavior**: Always selects the most recent block that has recent activity

**Example Scenario:**
- Session A: Started at 2:00 PM, last activity at 3:18 PM ✓ (active - within 5 hours)
- Session B: Started at 3:00 PM, last activity at 5:12 PM ✓ (active - within 5 hours)  
- **Result**: Current billing block starts at 3:00 PM (most recent active block)

#### Manual Override
For testing or debugging, you can override the unified block start time:

```bash
# Override unified block to start at 2:00 PM (14:00 in 24-hour format)
pccu monitor --block-start 14

# Override with timezone consideration (hour is interpreted in your configured timezone)
pccu monitor --block-start 18 --show-sessions
```

**Important**: The `--block-start` hour (0-23) is interpreted in your configured timezone and automatically converted to UTC for internal processing.

### Compact Interface
The monitor now supports compact mode for minimal, focused display:

**Normal Mode (Default)**: Full display with all information:
- **Header**: Active projects and sessions count
- **Block Progress**: 5-hour block progress with time remaining
- **Token Usage**: Per-model token counts with burn rate metrics and progress bars
- **Tool Usage**: Optional tool usage statistics (if enabled)
- **Sessions**: Optional session/project details (if enabled)

**Compact Mode**: Minimal display with essential information only:
- **Header**: Active projects and sessions count
- **Token Usage**: Per-model token counts with burn rate metrics (no progress bars or interruption stats)
  - **Burn Rate**: Displays tokens consumed per minute (e.g., "1.2K/m")
  - **Estimated Total**: Projects total usage for the full 5-hour block based on current burn rate
  - **ETA**: Shows estimated time until token limit is reached with actual clock time (e.g., "2.3h (10:45 PM)" or "45m (08:30 AM)")
  - **Total Usage**: Simple text display instead of progress bar
- **Hidden Elements**: No block progress bar, tool usage information, or session details (even with `--show-sessions`)

**Using Compact Mode**:

```bash
# Start directly in compact mode
pccu monitor --compact

# Compact mode with other options (sessions still hidden in compact mode)
pccu monitor --compact --show-sessions --interval 2

# Use config file for persistent compact mode
pccu monitor  # Uses config setting: display.display_mode: compact

# Environment variable approach
PAR_CC_USAGE_DISPLAY_MODE=compact pccu monitor
```

**Configuration Options**:
- **CLI**: Use `--compact` flag to start in compact mode
- **Config**: Set `display.display_mode: compact` in config file
- **Environment**: Set `PAR_CC_USAGE_DISPLAY_MODE=compact`

### Optional Session Details
Use `--show-sessions` or set `show_active_sessions: true` in config to view:
- Individual session information
- Project and session IDs
- Model types (Opus, Sonnet)
- Token usage per session
- Sessions sorted by newest activity first

**Session Filtering**: The sessions table displays only sessions with activity that overlaps with the current 5-hour billing window. This ensures accurate billing representation - sessions are shown if they have any activity within the unified block time window, regardless of when they started.

### Project Aggregation Mode (Default)
Project aggregation is enabled by default, showing token usage aggregated by project instead of individual sessions:
- **Project View**: Shows token usage aggregated by project instead of individual sessions
- **Simplified Table**: Removes session ID column for cleaner display
- **Same Filtering**: Uses the same unified block time window filtering as session mode
- **Model Tracking**: Shows all models used across all sessions within each project
- **Activity Sorting**: Projects sorted by their most recent activity time

**To disable project aggregation and show individual sessions:**
```yaml
display:
  aggregate_by_project: false  # Show individual sessions instead of projects
```

**Environment Variable:**
```bash
export PAR_CC_USAGE_AGGREGATE_BY_PROJECT=false
```

### Smart Token Limit Management
- **Auto-adjustment**: When current usage exceeds the configured limit, the limit is automatically increased and saved to the config file
- **Visual indicators**: Progress bars turn red when exceeding the original limit
- **Real-time updates**: Limits update immediately during monitoring

### Token Usage Calculation

PAR CC Usage calculates token consumption using a comprehensive approach that accounts for all token types and applies cost-based multipliers:

#### Token Types Included
- **Input tokens**: User prompts and context
- **Output tokens**: AI responses and generated content
- **Cache creation tokens**: Tokens used to create context caches
- **Cache read tokens**: Tokens read from existing context caches

**Total Calculation**: All token types are summed together for accurate billing representation.

#### Model-Based Token Multipliers
To reflect the actual cost differences between Claude models, tokens are adjusted using multipliers:

- **Opus models** (`claude-opus-*`): **5x multiplier** - reflects significantly higher cost
- **Sonnet models** (`claude-sonnet-*`): **1x multiplier** - baseline cost
- **Other/Unknown models**: **1x multiplier** - baseline cost

**Multiplier Application**: The multiplier is applied to the total token count (input + output + cache tokens) for each message, then aggregated by model within each billing block.

#### Block-Level Aggregation
- **Per-session blocks**: Each 5-hour session maintains separate token counts
- **Per-model tracking**: Token counts are tracked separately for each model within a block
- **Unified billing**: When multiple sessions are active, the system aggregates tokens from all sessions that overlap with the current billing period

#### Deduplication
- **Message + Request ID**: Prevents double-counting when JSONL files are re-processed
- **Processed hash tracking**: Maintains a cache of seen message combinations
- **Cross-session deduplication**: Works across all active sessions and projects

#### Display Calculations
- **Unified Block Total**: Shows tokens from all sessions overlapping the current 5-hour billing window
- **Per-Model Breakdown**: Displays individual model contributions with multipliers applied
- **Burn Rate**: Calculated as tokens per minute based on activity within the current block
- **Projections**: Estimates total block usage based on current burn rate

### Model Display Names
Model identifiers are simplified for better readability:
- `claude-opus-*` → **Opus**
- `claude-sonnet-*` → **Sonnet** 
- Unknown/other models → **Unknown**

**Note**: Claude Code primarily uses Opus and Sonnet models. Any other model names (including Haiku) are normalized to "Unknown".

### Time Format Options
Configure time display format through `display.time_format` setting:
- **24h format** (default): Shows time as `14:30` and `2024-07-08 14:30:45 PDT`
- **12h format**: Shows time as `2:30 PM` and `2024-07-08 2:30:45 PM PDT`

The time format applies to:
- Real-time monitor display (header and block progress)
- List command output (time ranges)
- Block time ranges in all display modes

### Project Name Customization
Configure project name display through `display.project_name_prefixes` setting:
- **Strip common prefixes**: Remove repetitive path prefixes from project names
- **Preserve project structure**: Maintains the actual project name including dashes
- **Configurable prefixes**: Customize which prefixes to strip

**Examples:**
- Claude directory: `-Users-probello-Repos-my-awesome-project`
- With prefix `"-Users-probello-Repos-"`: Shows as `my-awesome-project`
- Without prefix stripping: Shows as `-Users-probello-Repos-my-awesome-project`

**Configuration:**
```yaml
display:
  project_name_prefixes:
    - "-Users-probello-Repos-"  # Strip your repos path
    - "-home-user-"             # Strip alternative home paths
```

**Environment Variable:**
```bash
export PAR_CC_USAGE_PROJECT_NAME_PREFIXES="-Users-probello-Repos-,-home-user-"
```

### Cost Tracking & Pricing

PAR CC Usage includes comprehensive cost tracking capabilities using LiteLLM's pricing data for accurate cost calculations across all supported Claude models.

#### Enabling Cost Display

**Via Command Line:**
```bash
# Enable pricing for monitor mode
pccu monitor --show-pricing

# Enable pricing for session view
pccu monitor --show-sessions --show-pricing

# Enable pricing for list output
pccu list --show-pricing
```

**Via Configuration File:**
```yaml
display:
  show_pricing: true  # Enable cost calculations and display
```

**Via Environment Variable:**
```bash
export PAR_CC_USAGE_SHOW_PRICING=true
```

#### Features

- **Real-time cost tracking**: Live cost calculations displayed alongside token usage
- **Per-model accuracy**: Precise cost calculations for each Claude model (Opus, Sonnet, Haiku)
- **Activity table integration**: Optional cost columns in both project and session aggregation views
- **Total cost display**: Overall cost shown in the main token usage summary
- **Burn rate cost estimation**: Intelligent 5-hour block cost projection based on current spending rate
- **LiteLLM integration**: Uses LiteLLM's comprehensive pricing database for accuracy
- **Efficient caching**: Built-in pricing cache for optimal performance

#### Cost Display Locations

When `show_pricing` is enabled, cost information appears in:

1. **Main Usage Summary**: Total cost displayed next to token counts (e.g., "84.1M $34.85")
2. **Burn Rate Line**: Estimated total cost for 5-hour block based on current spending rate (e.g., "531K/m Est: 159.3M (90%) Est: $65.51 ETA: 2h 28m")
3. **Activity Tables**: 
   - Project aggregation mode: Cost column showing project-level costs
   - Session aggregation mode: Cost column showing session-level costs
4. **List Command Output**: Cost information in table, JSON, and CSV formats

#### Pricing Data

PAR CC Usage uses LiteLLM's comprehensive pricing database for accurate, up-to-date model costs with intelligent fallback handling:

**Core Pricing Features:**
- **Real-time pricing data**: Uses LiteLLM's pricing database for current model costs
- **Comprehensive model support**: Covers all Claude model variants with accurate per-token pricing
- **Token type handling**: Proper pricing for input, output, cache creation, and cache read tokens
- **Automatic model mapping**: Maps Claude Code model names to LiteLLM pricing keys

**Intelligent Fallback System:**
- **Unknown model handling**: Models marked as "Unknown" automatically display $0.00 cost
- **Pattern-based fallbacks**: When exact model names aren't found, uses intelligent pattern matching:
  - Models containing "opus" → Falls back to Claude Opus pricing
  - Models containing "sonnet" → Falls back to Claude Sonnet pricing  
  - Models containing "haiku" → Falls back to Claude Haiku pricing
- **Fuzzy matching**: Partial name matching for model variants and prefixes
- **Generic Claude fallbacks**: Unrecognized Claude models fall back to Sonnet pricing as a safe default
- **Graceful error handling**: Missing pricing data doesn't break functionality

**Examples of Fallback Behavior:**
- `"Unknown"` → $0.00 cost (no charges applied)
- `"claude-opus-custom"` → Uses Claude Opus pricing via pattern matching
- `"anthropic/claude-sonnet-experimental"` → Uses Claude Sonnet pricing via fuzzy matching
- `"custom-claude-model"` → Uses Claude Sonnet pricing as generic fallback

### Webhook Notifications

PAR CC Usage can send webhook notifications to Discord and/or Slack when 5-hour billing blocks complete, helping you stay aware of your usage patterns and costs.

#### Discord Setup

1. **Create Discord Webhook**: 
   - Go to your Discord server settings
   - Navigate to Integrations > Webhooks
   - Create a new webhook and copy the URL

2. **Configure Discord Webhook**:
   ```yaml
   notifications:
     discord_webhook_url: https://discord.com/api/webhooks/your-webhook-url
     notify_on_block_completion: true
     cooldown_minutes: 5
   ```

   Or via environment variable:
   ```bash
   export PAR_CC_USAGE_DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/your-webhook-url"
   ```

#### Slack Setup

1. **Create Slack Webhook**:
   - Go to your Slack workspace settings
   - Navigate to Apps > Incoming Webhooks
   - Create a new webhook and copy the URL

2. **Configure Slack Webhook**:
   ```yaml
   notifications:
     slack_webhook_url: https://hooks.slack.com/services/your-webhook-url
     notify_on_block_completion: true
     cooldown_minutes: 5
   ```

   Or via environment variable:
   ```bash
   export PAR_CC_USAGE_SLACK_WEBHOOK_URL="https://hooks.slack.com/services/your-webhook-url"
   ```

#### Multiple Webhooks

You can configure both Discord and Slack webhooks simultaneously:

```yaml
notifications:
  discord_webhook_url: https://discord.com/api/webhooks/your-discord-webhook
  slack_webhook_url: https://hooks.slack.com/services/your-slack-webhook
  notify_on_block_completion: true
  cooldown_minutes: 5
```

#### Test Configuration

```bash
# Test all configured webhooks
pccu test-webhook
```

#### Notification Features

- **Block Completion Alerts**: Notifications sent when a 5-hour block completes
- **Activity Filtering**: Only sends notifications for blocks that had activity (token usage > 0)
- **One-Time Sending**: Each block completion notification is sent only once
- **Cooldown Protection**: Configurable minimum time between notifications (default: 5 minutes)
- **Rich Information**: Includes token usage, duration, limit status, and time ranges
- **Smart Coloring**: Visual indicators based on token limit usage (green/orange/red)

#### Notification Content

Each notification includes:
- **Block Duration**: How long the block lasted
- **Token Usage**: Active and total token counts
- **Limit Status**: Percentage of configured limit used
- **Time Range**: Start and end times in your configured timezone
- **Visual Indicators**: Color-coded based on usage levels

#### Configuration Options

- `discord_webhook_url`: Discord webhook URL (optional - for Discord notifications)
- `slack_webhook_url`: Slack webhook URL (optional - for Slack notifications)
- `notify_on_block_completion`: Enable/disable block completion notifications (default: true)
- `cooldown_minutes`: Minimum minutes between notifications (default: 5)

### Theme System

PAR CC Usage includes a comprehensive theme system that allows you to customize the visual appearance of the CLI interface to match your preferences, terminal setup, and accessibility needs.

#### Available Themes

**Default Theme**: Original bright color scheme with vibrant colors
- **Use case**: General usage with high contrast
- **Colors**: Bright colors (cyan, yellow, green, red, magenta)
- **Best for**: Dark terminals, users who prefer bright colors

**Dark Theme**: Optimized for dark terminal backgrounds
- **Use case**: Dark mode terminals with refined colors
- **Colors**: Softer bright colors with better dark background contrast
- **Best for**: Dark terminals, reduced eye strain

**Light Theme**: Solarized Light inspired color palette
- **Use case**: Light terminal backgrounds
- **Colors**: Solarized Light palette (darker text, warm backgrounds)
- **Best for**: Light terminals, bright environments

**Accessibility Theme**: High contrast theme meeting WCAG AAA standards
- **Use case**: Visual accessibility and screen readers
- **Colors**: High contrast colors (black text on white background)
- **Best for**: Accessibility needs, high contrast requirements

**Minimal Theme**: Grayscale theme with minimal color usage
- **Use case**: Distraction-free, professional environments
- **Colors**: Grayscale palette (white, grays, black)
- **Best for**: Minimal aesthetics, focus on content over colors

#### Theme Configuration

**Set Default Theme (saves to config file):**
```bash
# Set light theme as default
pccu theme set light

# Set accessibility theme as default
pccu theme set accessibility

# Set with custom config file
pccu theme set dark --config my-config.yaml
```

**Temporary Theme Override (session only):**
```bash
# Override theme for single command
pccu monitor --theme light
pccu list --theme accessibility
pccu list-sessions --theme minimal

# Theme persists for the entire command execution
pccu monitor --theme light --show-sessions --show-pricing
```

**Configuration File Setting:**
```yaml
display:
  theme: light  # Options: 'default', 'dark', 'light', 'accessibility', 'minimal'
```

**Environment Variable:**
```bash
export PAR_CC_USAGE_THEME=accessibility
```

#### Theme Management Commands

```bash
# List all available themes with descriptions
pccu theme list

# Get current theme setting
pccu theme current

# Set default theme (saves to config)
pccu theme set <theme-name>
```

#### Theme Features

- **Semantic Color System**: Uses meaningful color names (success, warning, error, info) for consistency
- **Rich Integration**: Full integration with Rich library for optimal terminal rendering
- **Responsive Design**: Themes work across all display modes (normal, compact, sessions)
- **Consistent Application**: Colors are applied uniformly across all UI elements
- **Configuration Flexibility**: Multiple ways to set themes (CLI, config file, environment)

#### Theme Scope

Themes apply to all visual elements:
- **Progress bars**: Token usage and block progress indicators
- **Tables**: Project and session data tables
- **Status indicators**: Active/inactive sessions, success/error states
- **Burn rate displays**: Token consumption metrics
- **Headers and borders**: UI structure elements
- **Cost information**: Pricing and cost calculation displays (when enabled)

#### Best Practices

- **Light terminals**: Use `light` or `accessibility` themes
- **Dark terminals**: Use `default` or `dark` themes
- **Accessibility needs**: Use `accessibility` theme for high contrast
- **Professional environments**: Use `minimal` theme for clean appearance
- **Testing themes**: Use `--theme` flag to test before setting as default

## File Locations

### XDG Base Directory Specification

PAR CC Usage follows the XDG Base Directory Specification for proper file organization:

| Directory | Default Location | Environment Variable | Purpose |
|-----------|------------------|---------------------|----------|
| Config | `~/.config/par_cc_usage/` | `XDG_CONFIG_HOME` | Configuration files |
| Cache | `~/.cache/par_cc_usage/` | `XDG_CACHE_HOME` | File monitoring cache |
| Data | `~/.local/share/par_cc_usage/` | `XDG_DATA_HOME` | Application data |

### Configuration Files

- **Main config**: `~/.config/par_cc_usage/config.yaml`
- **Cache file**: `~/.cache/par_cc_usage/file_states.json`

### Legacy File Migration

The tool automatically migrates configuration files from legacy locations:

- `./config.yaml` (current working directory)
- `~/.par_cc_usage/config.yaml` (home directory)

Migration happens automatically on first run if:
1. Legacy config file exists
2. XDG config file doesn't exist
3. File is copied to `~/.config/par_cc_usage/config.yaml`

### Environment Variable Override

You can override XDG directories using standard environment variables:

```bash
# Override config directory
export XDG_CONFIG_HOME="/custom/config/path"

# Override cache directory  
export XDG_CACHE_HOME="/custom/cache/path"

# Override data directory
export XDG_DATA_HOME="/custom/data/path"
```

## Coming Soon

We're actively working on exciting new features to enhance your Claude Code monitoring experience:

### 💰 Cost Tracking for Non-Subscribers
- **Pay-per-use cost calculation**: Accurate cost estimates for users without Claude Pro subscriptions
- **Real-time cost monitoring**: Live cost tracking alongside token usage
- **Cost projections**: Estimated spending for the current billing block
- **Historical cost analysis**: Track spending patterns over time
- **Budget alerts**: Configurable notifications when approaching cost thresholds

**Want to contribute or request a feature?** Check out our [GitHub repository](https://github.com/paulrobello/par_cc_usage) or open an issue with your suggestions!

## What's New

### v0.1.4 - Theme System Implementation

**Complete Theme System**: Successfully implemented a comprehensive theme system with full Rich library integration and accessibility support:

#### 🎨 Theme Features
- **5 Built-in Themes**: Default, Dark, Light, Accessibility, and Minimal themes
- **Solarized Light Integration**: Professional light theme based on Solarized Light color palette
- **WCAG AAA Compliance**: High contrast accessibility theme meeting accessibility standards
- **Semantic Color System**: Color abstraction with meaningful names (success, warning, error, info)
- **Rich Library Integration**: Full integration with Rich console for optimal terminal rendering

#### 🔧 Configuration Options
- **Multiple Configuration Methods**: CLI flags, config file, environment variables
- **Session-based Overrides**: `--theme` flag for temporary theme changes without saving
- **Persistent Configuration**: Theme settings saved to XDG-compliant config files
- **Theme Management Commands**: Built-in CLI commands for theme listing, setting, and current status

#### 🌈 Theme Varieties
- **Default Theme**: Original bright colors for general dark terminal usage
- **Dark Theme**: Refined colors optimized for dark terminals with reduced eye strain
- **Light Theme**: Solarized Light inspired palette perfect for light terminals
- **Accessibility Theme**: High contrast black/white theme for visual accessibility needs
- **Minimal Theme**: Grayscale palette for distraction-free, professional environments

#### 🎯 Usage Examples
- **Monitor with themes**: `pccu monitor --theme light --show-sessions`
- **List with themes**: `pccu list --theme accessibility --show-pricing`
- **Theme management**: `pccu theme set dark`, `pccu theme list`, `pccu theme current`
- **Configuration**: `display.theme: light` in config file or `PAR_CC_USAGE_THEME=minimal`

### v0.1.3 - Code Quality Improvements

**Major Code Quality Overhaul**: Successfully completed a comprehensive code quality improvement initiative focused on reducing cyclomatic complexity and improving maintainability across all core modules:

#### 🔧 Complexity Reduction
- **9 functions refactored**: Reduced cyclomatic complexity from 11-36 down to ≤10 for all functions
- **40+ helper functions extracted**: Decomposed complex operations into focused, reusable components
- **Improved maintainability**: Each function now has a single, clear responsibility

#### 📊 Key Improvements
- **Display System**: Split complex table population and burn rate calculation functions
- **Session Management**: Decomposed session listing, filtering, and analysis operations
- **Debug Commands**: Extracted analysis and display logic into modular components
- **Cost Tracking**: Separated cost calculation from display formatting

#### 🎯 Benefits
- **Better Code Readability**: Functions are easier to understand and debug
- **Increased Testability**: Helper functions can be tested independently
- **Enhanced Reusability**: Common logic extracted into reusable components
- **Reduced Maintenance Burden**: Changes to specific functionality are now isolated

#### 📈 Quality Metrics
- **512+ test cases**: Comprehensive test coverage maintained
- **All functions ≤10 complexity**: Enforced by automated linting
- **Full type safety**: Complete type annotations with validation
- **Zero linting errors**: Clean, consistent code style

### v0.1.2 - Pricing & Cost Tracking

**Cost Tracking Integration**: Added comprehensive cost tracking and pricing functionality with LiteLLM integration for accurate cost calculations across all Claude models.

### v0.1.1 - Enhanced Analytics

**Advanced Analytics**: Enhanced burn rate calculations, block management improvements, and refined display system with better user experience.

### v0.1.0 - Core Features

**Initial Release**: Core functionality including real-time monitoring, 5-hour billing blocks, multi-session support, and basic analytics.

### older...

Earlier versions focused on foundational architecture, file monitoring, and basic token tracking capabilities.

## Development

```bash
# Format and lint
make checkall

# Run development mode
make dev
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
