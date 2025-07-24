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
timezone: auto  # Automatically detects system timezone, or use IANA timezone name
auto_detected_timezone: America/New_York  # Automatically populated when timezone=auto
token_limit: 500000
message_limit: 1000  # Optional message limit
cost_limit: 50.00    # Optional cost limit in USD
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
config_ro: false  # Read-only mode: prevents automatic config updates (default: false)
```

## Timezone Configuration

PAR CC Usage supports automatic timezone detection for seamless multi-timezone usage:

### Automatic Detection (Recommended)
Set `timezone: auto` to automatically detect your system's timezone:

```yaml
timezone: auto
```

When set to `auto`:
- The system timezone is automatically detected on startup
- The detected timezone is stored in `auto_detected_timezone` field
- Changes to your system timezone are automatically detected on config reload
- Works across Windows, macOS, and Linux platforms

### Manual Configuration
You can also set an explicit IANA timezone name:

```yaml
timezone: America/New_York  # Or any valid IANA timezone
```

### How It Works
- **Config Setting**: `timezone` stores your preference (`auto` or explicit timezone)
- **Detected Value**: `auto_detected_timezone` stores the system-detected timezone (updated automatically)
- **Effective Timezone**: When `timezone` is `auto`, `auto_detected_timezone` is used for all time displays
- **Dynamic Updates**: System timezone changes are detected when the config is reloaded

### Common IANA Timezone Examples
- `America/New_York` (Eastern Time)
- `America/Chicago` (Central Time)
- `America/Denver` (Mountain Time)
- `America/Los_Angeles` (Pacific Time)
- `Europe/London`, `Europe/Paris`, `Asia/Tokyo`, etc.

## Environment Variables

- `PAR_CC_USAGE_PROJECTS_DIR`: Override projects directory
- `PAR_CC_USAGE_POLLING_INTERVAL`: Set polling interval
- `PAR_CC_USAGE_TIMEZONE`: Set timezone ('auto' for system detection or IANA timezone name)
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
- `PAR_CC_USAGE_CONFIG_RO`: Enable read-only mode ('true', '1', 'yes', 'on' for true)

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

## Read-Only Configuration Mode

Read-only mode (`config_ro: true`) prevents automatic updates to the configuration file while preserving manual control via CLI commands.

### Features

- **🛡️ Automatic Update Protection**: Blocks all automatic config updates including:
  - Maximum token/message/cost tracking (`max_unified_block_*_encountered`)
  - Automatic limit scaling based on usage patterns
  - Auto-detection and adjustment of limits

- **🔧 CLI Override Support**: Manual commands still work normally:
  - `pccu set-limit` commands bypass read-only protection
  - Temporary CLI options (like `--token-limit`) continue to function
  - Manual configuration via `pccu init` and direct file editing

- **⚙️ Flexible Control**: Multiple ways to enable:
  - **Config file**: `config_ro: true`
  - **Environment variable**: `PAR_CC_USAGE_CONFIG_RO=true`
  - **Per-session**: Environment variable override for specific runs

### Usage Examples

```bash
# Enable read-only mode permanently
echo "config_ro: true" >> ~/.config/par_cc_usage/config.yaml

# Enable for single session
PAR_CC_USAGE_CONFIG_RO=true pccu monitor

# Manual limit updates still work with read-only enabled
pccu set-limit cost 100.00  # Works even with config_ro: true

# CLI overrides still work
pccu monitor --token-limit 2000000  # Works even with config_ro: true
```

### Use Cases

- **Production environments**: Prevent accidental config changes
- **Shared systems**: Lock configuration while allowing operation
- **Testing scenarios**: Maintain consistent config across test runs
- **CI/CD pipelines**: Ensure configuration stability in automated environments

## Configuration Management Commands

### Initialize Configuration

```bash
# Initialize configuration file
pccu init

# Use custom config file
pccu init --config my-config.yaml
```

### Set Limits

The `set-limit` command allows you to set three types of limits:

```bash
# Set token limit (integer)
pccu set-limit token 500000

# Set message limit (integer)  
pccu set-limit message 100

# Set cost limit in USD (float)
pccu set-limit cost 25.50
```

**Limit Types:**
- **`token`**: Maximum tokens per 5-hour billing block (integer)
- **`message`**: Maximum messages per 5-hour billing block (integer)
- **`cost`**: Maximum cost per 5-hour billing block in USD (float)

**Features:**
- ✅ **Read-only protection**: Works even when `config_ro: true` is set
- ✅ **Input validation**: Prevents negative values and validates data types
- ✅ **Formatted output**: Shows clear before/after values with proper formatting
- ✅ **Custom config**: Use `--config` option to specify alternative config files

**Examples:**
```bash
# Set a high token limit for large projects
pccu set-limit token 1000000

# Set conservative message limit
pccu set-limit message 50

# Set cost budget for billing period
pccu set-limit cost 100.00

# Use with custom config file
pccu set-limit cost 25.50 --config /path/to/config.yaml
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
