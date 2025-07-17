# Features

PAR CC Usage provides comprehensive Claude Code usage monitoring with advanced analytics, cost tracking, and customizable display options.

## 📊 Real-Time Monitoring
- **Live token tracking**: Monitor usage across all Claude Code projects in real-time
- **5-hour billing blocks**: Unified block system that accurately reflects Claude's billing structure
- **Multi-session support**: When multiple sessions are active, they share billing blocks intelligently
- **Visual progress indicators**: Real-time progress bars for current billing period
- **Stable console interface**: Clean, jump-free display with automatic suppression of disruptive output

## 🔥 Advanced Burn Rate Analytics
- **Per-minute tracking**: Granular burn rate display (tokens/minute) for precise monitoring
- **Estimated completion**: Projects total usage for full 5-hour block based on current rate
- **ETA with clock time**: Shows both duration and actual time when limit will be reached
- **Smart color coding**: Visual indicators based on usage levels (green/orange/red)

## ⚙️ Intelligent Block Management
- **Smart strategy**: Intelligent algorithm that automatically selects optimal billing blocks
- **Manual override**: CLI option to set custom block start times for testing or corrections
- **Automatic detection**: Smart detection of session boundaries and billing periods
- **Gap handling**: Proper handling of inactivity periods longer than 5 hours

## 🎯 Smart Features
- **Auto-adjusting limits**: Automatically increases token limits when exceeded and saves to config
- **Deduplication**: Prevents double-counting using message and request IDs
- **Model name simplification**: Clean display names (Opus, Sonnet) for better readability
- **Session sorting**: Newest-first ordering for active sessions
- **Per-model token tracking**: Accurate token attribution with proper multipliers (Opus 5x, others 1x)
- **Compact display mode**: Minimal interface option for reduced screen space usage

## 💰 Cost Tracking & Pricing
- **Real-time cost calculations**: Live cost tracking using LiteLLM pricing data
- **Per-model cost breakdown**: Accurate cost attribution for each Claude model
- **Monitor pricing integration**: Optional cost columns in project and session views with `--show-pricing`
- **List command pricing**: Full cost analysis support in table, JSON, and CSV outputs with `--show-pricing` and intelligent cost hierarchy
- **Burn rate cost estimation**: Real-time 5-hour block cost projection based on current spending rate
- **Configurable pricing display**: Enable/disable cost tracking via configuration or command-line
- **Export with costs**: JSON and CSV exports include cost data and cost source transparency when pricing is enabled
- **Integrated pricing cache**: Efficient pricing lookups with built-in caching
- **Intelligent fallbacks**: When exact model names aren't found, uses pattern matching to find closest pricing
- **Unknown model handling**: Models marked as "Unknown" automatically display $0.00 cost
- **Robust error handling**: Missing pricing data doesn't break functionality or display

## 📁 File System Support
- **Multi-directory monitoring**: Supports both legacy (`~/.claude/projects`) and new paths
- **Efficient caching**: File position tracking to avoid re-processing entire files
- **Cache management**: Optional cache disabling for full file reprocessing
- **JSONL analysis**: Deep analysis of Claude Code data structures
- **XDG Base Directory compliance**: Uses standard Unix/Linux directory conventions
- **Legacy migration**: Automatically migrates existing config files to XDG locations

## 🌐 Configuration & Customization
- **XDG directory compliance**: Config, cache, and data files stored in standard locations
- **Automatic migration**: Legacy config files automatically moved to XDG locations
- **Timezone support**: Full timezone handling with configurable display formats
- **Time formats**: 12-hour or 24-hour time display options
- **Project name cleanup**: Strip common path prefixes for cleaner display
- **Flexible output**: Table, JSON, and CSV export formats

## 🎨 Theme System
- **Multiple built-in themes**: Choose from 5 carefully crafted themes for different preferences
- **Light and dark themes**: Options for both dark terminal and light terminal users
- **Accessibility support**: High contrast theme meeting WCAG AAA standards
- **Session-based overrides**: Temporarily change themes for individual command runs
- **Rich color integration**: Semantic color system with consistent visual language
- **CLI theme management**: Built-in commands for theme configuration and preview

## 🔔 Notification System
- **Discord integration**: Webhook notifications for billing block completion
- **Slack integration**: Webhook notifications for billing block completion
- **Smart filtering**: Only notifies for blocks with actual activity
- **Cooldown protection**: Configurable minimum time between notifications
- **Rich information**: Detailed usage statistics in notifications

## 🛠️ Developer Tools
- **Debug commands**: Comprehensive debugging tools for block calculation and timing
- **Activity analysis**: Historical activity pattern analysis
- **JSONL analyzer**: Built-in `jsonl_analyzer.py` tool for examining Claude Code data files
- **Webhook testing**: Built-in Discord and Slack webhook testing

## Feature Details

### Real-Time Monitoring Features

**Live Token Tracking**
- Monitors all Claude Code projects simultaneously
- Real-time updates with configurable refresh intervals
- Automatic detection of new sessions and projects

**5-Hour Billing Blocks**
- Unified block system reflecting Claude's actual billing structure
- Intelligent block selection based on activity patterns
- Visual progress indicators for current billing period

**Multi-Session Support**
- When multiple sessions are active, they share billing blocks intelligently
- Unified display of token usage across all active sessions
- Session filtering based on billing block time windows

**Stable Console Interface**
- Clean, jump-free display with automatic suppression of disruptive output
- Debug mode for troubleshooting without breaking display
- Exception handling that preserves display integrity

### Advanced Analytics

**Burn Rate Analytics**
- Per-minute token consumption tracking
- Estimated completion projections for full 5-hour blocks
- ETA calculations with actual clock time
- Smart color coding based on usage levels

**Block Management**
- Smart strategy for optimal billing block selection
- Manual override options for testing and corrections
- Automatic detection of session boundaries
- Proper handling of inactivity periods

**Smart Features**
- Auto-adjusting token limits with config file updates
- Deduplication using message and request IDs
- Model name simplification for better readability
- Session sorting by newest activity first

### Cost Tracking System

**Real-Time Cost Calculations**
- Live cost tracking using LiteLLM pricing data
- Per-model cost breakdown for accurate attribution
- Burn rate cost estimation for 5-hour blocks
- Cost display in monitor and list commands

**Intelligent Cost Hierarchy**
- Three-tier cost calculation system for maximum accuracy
- Native cost data from Claude (when available)
- LiteLLM pricing fallback with pattern matching
- Cost source transparency in all outputs

**Export and Analysis**
- JSON and CSV exports with cost data
- Cost source tracking for debugging
- Comprehensive pricing support in all output formats
- Historical cost analysis capabilities

### Theme System

**Built-in Themes**
- **Default**: Original bright color scheme for dark terminals
- **Dark**: Optimized colors for dark terminal backgrounds
- **Light**: Solarized Light inspired palette for light terminals
- **Accessibility**: High contrast theme meeting WCAG AAA standards
- **Minimal**: Grayscale theme for distraction-free use

**Theme Configuration**
- Multiple configuration methods (CLI, config file, environment)
- Session-based overrides for temporary theme changes
- Persistent theme settings with config file storage
- Theme management commands for easy switching

**Rich Integration**
- Full integration with Rich library for optimal terminal rendering
- Semantic color system with consistent visual language
- Responsive design across all display modes
- Uniform application across all UI elements

### Notification System

**Webhook Support**
- Discord webhook integration for block completion notifications
- Slack webhook integration for block completion notifications
- Multiple webhook support (Discord and Slack simultaneously)
- Test commands for webhook configuration validation

**Smart Notifications**
- Activity filtering (only notifies for blocks with actual usage)
- One-time sending (each block completion notification sent only once)
- Cooldown protection with configurable minimum time between notifications
- Rich information including token usage, duration, and limit status

**Configuration Options**
- Flexible webhook URL configuration
- Enable/disable block completion notifications
- Configurable cooldown periods
- Multiple notification channels

### Developer Tools

**Debug Commands**
- Comprehensive debugging tools for block calculation and timing
- Activity pattern analysis with configurable time windows
- Expected time validation for unified block calculations
- Block timing verification and strategy explanation

**JSONL Analysis**
- Built-in analyzer for Claude Code data files
- Field discovery and type information
- Smart truncation for readability
- Streaming processing for large files

**Webhook Testing**
- Built-in Discord and Slack webhook testing
- Configuration validation
- Error handling and debugging support
- Multiple webhook testing simultaneously

### File System Support

**Multi-Directory Monitoring**
- Support for both legacy and new Claude directory structures
- Automatic detection of Claude project directories
- Efficient file system monitoring with position tracking
- Cache management for optimal performance

**XDG Base Directory Compliance**
- Standard Unix/Linux directory conventions
- Automatic legacy config file migration
- Proper separation of config, cache, and data files
- Environment variable support for directory overrides

**Caching System**
- File position tracking to avoid re-processing entire files
- Optional cache disabling for full file reprocessing
- Cache management commands for troubleshooting
- Intelligent cache invalidation
