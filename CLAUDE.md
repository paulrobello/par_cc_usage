# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

PAR CC Usage is a Python CLI tool for tracking and analyzing Claude Code token usage. It monitors JSONL files, provides real-time statistics with cost tracking, and manages 5-hour billing blocks.

## Quick Start

```bash
# Setup
uv sync

# Run monitor
make dev          # Development mode with hot reload
make run          # Normal mode
uv run pccu monitor

# Code quality (run before commits)
make checkall     # Format, lint, and typecheck

# Testing
make test
```

## Key Commands

### Status Line Integration
```bash
# Install/uninstall Claude Code status line
uv run pccu install-statusline [--force]
uv run pccu uninstall-statusline [--force]
```

Status line shows: `[project] · 🪙 tokens · 💰 cost · ⏱️ time · SES:model · session_tokens`

### Monitor Options
```bash
uv run pccu monitor                 # Default: tools and pricing enabled
uv run pccu monitor --no-tools      # Disable tool usage display
uv run pccu monitor --no-pricing    # Disable pricing display
uv run pccu monitor --no-p90        # Use absolute max instead of P90
uv run pccu monitor --snapshot      # Single snapshot and exit
```

### Configuration & Export
```bash
# Update config maximums
uv run pccu update-maximums [--dry-run] [--force]

# Export data
uv run pccu list --format json --output costs.json
uv run pccu list --format csv --output costs.csv
```

### Troubleshooting
```bash
# Cache issues
uv run pccu clear-cache              # Clear and rebuild cache
uv run pccu monitor --no-cache       # Run without cache

# Debug commands
uv run pccu debug-unified            # Debug block calculation
uv run pccu test-webhook             # Test notifications
```

## Development Guidelines

### Version Management
- **ONLY bump version when user requests it**
- Version source: `src/par_cc_usage/__init__.py` line 3
- Update README.md "What's New" section when bumping

### Code Standards
- Cyclomatic complexity ≤ 10
- Type annotations required
- Google style docstrings
- Run `make checkall` before commits

### Architecture Notes
- Uses unified block system (5-hour billing periods)
- Caches for performance (~0.3s startup vs 3.9s uncached)
- Tracks tool usage, costs, and message counts
- Status line updates require monitor running

### Key Files
- `src/par_cc_usage/config.py` - Configuration defaults
- `src/par_cc_usage/unified_block_calculator.py` - Block logic
- `src/par_cc_usage/statusline_manager.py` - Status line generation

## Documentation

- [README.md](README.md) - Full feature documentation
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) - System design
- [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) - Development workflows
- [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) - Problem resolution
