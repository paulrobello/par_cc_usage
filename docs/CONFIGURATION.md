# Configuration Guide

PAR CC Usage supports configuration via YAML files and environment variables. Configuration files are stored in XDG Base Directory compliant locations.

## Directory Structure

- **Config**: `~/.config/par_cc_usage/config.yaml` (respects `XDG_CONFIG_HOME`)
- **Cache**: `~/.cache/par_cc_usage/` (respects `XDG_CACHE_HOME`)
- **Data**: `~/.local/share/par_cc_usage/` (respects `XDG_DATA_HOME`)

## Legacy Migration

If you have an existing `./config.yaml` file in your working directory, it will be automatically migrated to the XDG config location (`~/.config/par_cc_usage/config.yaml`) when you first run the tool.

**Migration behavior:**
- Checks for legacy config files in current directory and home directory
- Automatically copies to XDG location if XDG config doesn't exist
- Preserves all existing settings during migration
- No manual intervention required

## Config File Example

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
  show_active_sessions: true  # Default: show session details
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

## Environment Variables

- `PAR_CC_USAGE_PROJECTS_DIR`: Override projects directory
- `PAR_CC_USAGE_POLLING_INTERVAL`: Set polling interval
- `PAR_CC_USAGE_TIMEZONE`: Set timezone
- `PAR_CC_USAGE_TOKEN_LIMIT`: Set token limit
- `PAR_CC_USAGE_CACHE_DIR`: Override cache directory (defaults to XDG cache directory)
- `PAR_CC_USAGE_DISABLE_CACHE`: Disable file monitoring cache ('true', '1', 'yes', 'on' for true)
- `PAR_CC_USAGE_RECENT_ACTIVITY_WINDOW_HOURS`: Hours to consider as 'recent' activity for smart strategy (default: 5)
- `PAR_CC_USAGE_SHOW_PROGRESS_BARS`: Show progress bars
- `PAR_CC_USAGE_SHOW_ACTIVE_SESSIONS`: Show active sessions (default: true)
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

## Configuration Management Commands

```bash
# Initialize configuration file
pccu init

# Set token limit
pccu set-limit 500000

# Use custom config file
pccu init --config my-config.yaml
```

## Cache Management

```bash
# Clear file monitoring cache
pccu clear-cache

# Clear cache with custom config
pccu clear-cache --config my-config.yaml
```

## Theme Management

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
