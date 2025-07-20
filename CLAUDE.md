# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

PAR CC Usage is a Python-based CLI tool for tracking and analyzing Claude Code token usage across multiple projects. It monitors JSONL files in Claude's project directories, provides real-time usage statistics with tool usage tracking and pricing display enabled by default, and manages 5-hour billing blocks.

## Quick Start

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

### Testing
```bash
# Run tests
make test
```

## Common Commands

### Monitor Mode
```bash
# Default behavior - tool usage and pricing displayed automatically
uv run pccu monitor

# Disable tool usage display if desired
uv run pccu monitor --no-tools

# Disable pricing display if desired  
uv run pccu monitor --no-pricing

# Disable P90 limits and use absolute maximum values
uv run pccu monitor --no-p90

# Take a single debug snapshot (monitor once and exit)
uv run pccu monitor --snapshot

# Enable debug output
uv run pccu monitor --debug
```

### Debug Commands
```bash
# Debug unified block calculation
uv run pccu debug-unified

# Debug block information
uv run pccu debug-blocks --show-inactive

# Test webhooks (Discord/Slack)
uv run pccu test-webhook
```

### List and Export
```bash
# List usage with costs
uv run pccu list --show-pricing

# Export cost data for analysis
uv run pccu list --format json --output costs.json
uv run pccu list --format csv --output costs.csv
```

## Key Features

### Tool Usage Display (Default Enabled)
- **Always Tracked**: Tool usage data is cached regardless of display settings
- **Zero Performance Impact**: Toggling display on/off processes only new messages
- **Instant Toggle**: Switch between `--show-tools`/`--no-tools` without cache rebuilds
- **Rich Information**: See which tools are used most frequently across projects and sessions

### Cost Analysis (Default Enabled)
- **Real-time Cost Tracking**: 💰 emoji indicators throughout the interface
- **Burn Rate Estimation**: 5-hour block cost projections
- **Individual Project/Session Breakdown**: Cost tracking per project and session
- **Export Support**: JSON and CSV export with cost data

### P90 Progress Bar Limits (Default Enabled)
- **Stable Progress Bars**: Uses 90th percentile (P90) instead of absolute maximum values for more stable progress indicators
- **Outlier Filtering**: Ignores extreme usage spikes that might skew progress bars
- **Realistic Projections**: Shows more typical usage patterns while capturing 90% of historical data
- **Visual Indicator**: Displays "(P90)" next to limits when enabled
- **Optional**: Can be disabled to use absolute maximum values via `--no-p90` or config setting

## Troubleshooting

### Cache Issues
If counts, costs, or tool usage appear incorrect:

```bash
# Clear all cached data and force complete re-processing
uv run pccu clear-cache

# Verify the issue is resolved
uv run pccu monitor --snapshot

# Alternative: disable cache for one-time verification
uv run pccu monitor --no-cache --snapshot
```

**When to clear cache:**
- Token counts don't match expected values
- Tool usage shows incorrect tools or counts
- Cost calculations seem wrong
- Message counts showing as 0 (now fixed)
- Active projects/sessions showing as 0 (now fixed)
- After upgrading PAR CC Usage versions
- When debugging data processing issues

### Performance Notes
- **With cache enabled (default)**: ~0.3s startup
- **With cache disabled**: ~3.9s startup
- **Cache clearing**: Forces re-processing of all JSONL files (3-4 seconds for large datasets)

## Documentation

For detailed information, see:
- [Architecture Documentation](docs/ARCHITECTURE.md) - System architecture, data models, and design decisions
- [Development Guide](docs/DEVELOPMENT.md) - Detailed development workflows and advanced features
- [Troubleshooting Guide](docs/TROUBLESHOOTING.md) - Cache system, debugging, and problem resolution

## Development Guidelines

### Version Management
- **Important**: ONLY bump the project version if the user requests it
- **Config Read-Only Mode**: The `config_ro` option prevents automatic updates to config file while allowing CLI overrides
- **Single Source**: Version is defined only in `src/par_cc_usage/__init__.py`
- **No Sync Required**: `pyproject.toml` uses dynamic versioning - version is defined in one place only

### Version Bumping Process
When bumping the version:
1. Update only `src/par_cc_usage/__init__.py` line 3: `__version__ = "x.y.z"`
2. Update README.md "What's New" section with the new version
3. Update TOC "What's New" section (keep newest 6 versions, 6th entry labeled 'older...')

### Code Quality Standards
- All functions maintain cyclomatic complexity ≤ 10
- Type annotations required for all code
- Use Google style docstrings for functions, classes, and modules
- Run `make checkall` before commits (format, lint, typecheck)

### Unified Block System Guidelines
- **Single Implementation**: Only unified blocks are supported (legacy session-based blocks removed)
- **Standard Compatibility**: Block calculation must follow standard behavior
- **Message Tracking**: Ensure message counts are properly tracked in TokenUsage and UnifiedBlock
- **Display Updates**: All display components must use unified block data, not session-based data
- **Active Counts**: Use `unified_block_projects` and `unified_block_session_count` for header counts

### Tools and Workflow
- Use `json_analyzer.py` tool to read JSON/JSONL files from Claude project directories
- Supports both JSON (.json) and JSONL (.jsonl) formats with automatic detection
- Usage: `uv run python -m par_cc_usage.json_analyzer analyze <file>`

## Architecture Overview

PAR CC Usage is built around a **unified block system** that tracks token usage in 5-hour billing periods using standard behavior. It monitors Claude Code JSONL files, processes token data through a caching system, and provides real-time monitoring with cost tracking.

### Core Components

- **File Monitor**: Watches Claude project directories for JSONL changes using position tracking
- **Unified Block Calculator**: Processes JSONL data and organizes usage into cross-project 5-hour blocks
- **Display System**: Rich terminal UI with emoji-enhanced formatting (🪙💬💰) and real-time updates
- **Pricing Integration**: LiteLLM API integration for cost calculations with fallback logic
- **Configuration**: XDG-compliant configuration with automatic legacy migration

### Key Features

- **Unified Block System**: Cross-project/session billing block detection using standard behavior
- **Message Count Tracking**: Accurate message counts displayed per model and total (💬)
- **Active Project/Session Counts**: Real-time counts of active projects and sessions in current block
- **P90 Progress Limits**: Stable progress bars using 90th percentile values instead of outlier maximums
- **High-Performance Cache**: File position tracking for 12x faster startup (0.3s vs 3.9s)
- **Tool Usage Tracking**: Monitors Claude Code tool usage (Read, Edit, Bash, etc.)
- **Cost Analysis**: Real-time cost tracking with burn rate estimation
- **Export Capabilities**: JSON/CSV export with comprehensive pricing data

### Unified Block System

The system now uses a **single unified block approach** that:
- Aggregates ALL entries across projects and sessions into a unified timeline
- Creates 5-hour billing blocks based on temporal proximity using standard logic
- Tracks projects, sessions, models, tools, and costs within each block
- Provides accurate active project/session counts and message counts
- Eliminates the legacy session-based block calculation (removed as of latest version)

### Data Flow

1. **File Monitoring**: Watches `~/.claude/projects/` for JSONL file changes
2. **Entry Processing**: Parses messages and creates UnifiedEntry objects
3. **Block Aggregation**: Groups entries into 5-hour unified blocks across all projects
4. **Display/Export**: Shows real-time unified block data or exports to various formats

See [Architecture Documentation](docs/ARCHITECTURE.md) for detailed system design.
