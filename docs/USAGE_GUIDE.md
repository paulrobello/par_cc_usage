# Usage Guide

Comprehensive guide to using PAR CC Usage for monitoring Claude Code token usage.

## Monitor Token Usage

Monitor token usage in real-time with comprehensive options:

```bash
# Basic monitoring (default 5-second interval)
pccu monitor

# Compact mode for minimal display
pccu monitor --compact

# Basic monitoring (sessions shown by default)
pccu monitor

# High-frequency monitoring with custom settings
pccu monitor --interval 2 --token-limit 1000000 --show-sessions

# Monitor with custom configuration
pccu monitor --config production-config.yaml

# Testing and debugging scenarios
pccu monitor --no-cache --block-start 18  # Fresh scan + custom block timing
pccu monitor --block-start 14 --show-sessions  # Override block start time
pccu monitor --debug  # Enable debug output to see processing messages

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

### Monitor Display Features
- **Real-time updates**: Live token consumption tracking
- **Burn rate analytics**: Tokens/minute with ETA to limit (e.g., "1.2K/m ETA: 2.3h (10:45 PM)")
- **Cost tracking**: Real-time cost calculations using LiteLLM pricing (when `--show-pricing` is enabled)
- **Burn rate cost estimation**: Intelligent cost projection for 5-hour blocks based on current spending rate (e.g., "531K/m Est: 159.3M (90%) Est: $65.51 ETA: 2h 28m")
- **Block progress**: Visual 5-hour billing block progress with time remaining
- **Model breakdown**: Per-model token usage (Opus, Sonnet) with optional cost breakdown
- **Session details**: Individual session tracking (shown by default)
- **Activity tables**: Project or session aggregation views with optional cost columns

## List Usage Data

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

# Include cost information in output (table format)
pccu list --show-pricing

# Export usage data with costs as JSON
pccu list --show-pricing --format json

# Export usage data with costs as CSV
pccu list --show-pricing --format csv --output usage-with-costs.csv

# Combine sorting and pricing
pccu list --sort-by tokens --show-pricing --format table

# Save detailed report with costs to file
pccu list --show-pricing --output usage-report.json --format json

# Theme customization for list output
pccu list --theme light --show-pricing  # Light theme with pricing
pccu list --theme accessibility --format table  # High contrast theme
pccu list --theme minimal --sort-by tokens  # Minimal theme with token sorting
```

## Webhook Notifications

```bash
# Test webhook configuration (Discord and/or Slack)
pccu test-webhook

# Test with custom config file
pccu test-webhook --config my-config.yaml
```

### Discord Setup

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

### Slack Setup

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

### Multiple Webhooks

You can configure both Discord and Slack webhooks simultaneously:

```yaml
notifications:
  discord_webhook_url: https://discord.com/api/webhooks/your-discord-webhook
  slack_webhook_url: https://hooks.slack.com/services/your-slack-webhook
  notify_on_block_completion: true
  cooldown_minutes: 5
```

### Notification Features

- **Block Completion Alerts**: Notifications sent when a 5-hour block completes
- **Activity Filtering**: Only sends notifications for blocks that had activity (token usage > 0)
- **One-Time Sending**: Each block completion notification is sent only once
- **Cooldown Protection**: Configurable minimum time between notifications (default: 5 minutes)
- **Rich Information**: Includes token usage, duration, limit status, and time ranges
- **Smart Coloring**: Visual indicators based on token limit usage (green/orange/red)

### Notification Content

Each notification includes:
- **Block Duration**: How long the block lasted
- **Token Usage**: Active and total token counts
- **Limit Status**: Percentage of configured limit used
- **Time Range**: Start and end times in your configured timezone
- **Visual Indicators**: Color-coded based on usage levels

### Configuration Options

- `discord_webhook_url`: Discord webhook URL (optional - for Discord notifications)
- `slack_webhook_url`: Slack webhook URL (optional - for Slack notifications)
- `notify_on_block_completion`: Enable/disable block completion notifications (default: true)
- `cooldown_minutes`: Minimum minutes between notifications (default: 5)

## JSONL Analysis

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

### JSONL Analyzer Features:
- **Field discovery**: Automatically identifies all fields present in the JSONL data
- **Type information**: Shows data types for each field (string, number, object, array)
- **Smart truncation**: Long strings and arrays are truncated for readability
- **Streaming processing**: Handles large files efficiently without loading everything into memory
- **Usage analysis**: Helps identify token usage patterns and message structures

## Debug Commands

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

### Debug Output Features
- **Block timing verification**: Confirms correct 5-hour block boundaries
- **Strategy explanation**: Shows why specific blocks were selected
- **Token calculation validation**: Verifies deduplication and aggregation
- **Activity timeline**: Chronological view of session activity
- **Configuration validation**: Confirms settings are applied correctly
- **Expected time validation**: Validates unified block calculations against expected results (24-hour format)

## Common Usage Patterns

### Development Monitoring
```bash
# Basic development monitoring
pccu monitor --debug

# Compact view for small screens
pccu monitor --compact --interval 3

# Monitor with cost tracking
pccu monitor --show-pricing --theme light
```

### Production Monitoring
```bash
# Conservative monitoring
pccu monitor --interval 10 --token-limit 500000

# Team dashboard
pccu monitor --show-sessions --config team-config.yaml

# Cost monitoring with notifications
pccu monitor --show-pricing --config production-config.yaml
```

### Data Analysis
```bash
# Export usage data for analysis
pccu list --format json --output usage-data.json

# Cost analysis
pccu list --show-pricing --format csv --output cost-analysis.csv

# Detailed session breakdown
pccu list --sort-by tokens --show-pricing --format table
```

### Troubleshooting
```bash
# Debug block calculations
pccu debug-unified --expected-hour 14

# Analyze activity patterns
pccu debug-activity --hours 12

# Clear cache and reprocess
pccu clear-cache
pccu monitor --no-cache --snapshot
```

## Tips and Best Practices

### Performance Optimization
- Use `--compact` mode for reduced screen usage
- Increase `--interval` for less frequent updates
- Use `--no-cache` only when troubleshooting
- Clear cache after major version updates

### Cost Management
- Enable `--show-pricing` to track costs
- Set appropriate token limits with `--token-limit`
- Use webhook notifications for block completion alerts
- Export cost data regularly for analysis

### Theme Selection
- Use `light` theme for light terminals
- Use `accessibility` theme for high contrast needs
- Use `minimal` theme for distraction-free monitoring
- Test themes with `--theme` flag before setting as default

### Configuration Management
- Use config files for persistent settings
- Set environment variables for system-wide defaults
- Use custom config files for different environments
- Backup configuration files regularly
