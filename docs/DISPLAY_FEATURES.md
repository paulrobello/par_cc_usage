# Display Features

PAR CC Usage provides a comprehensive display system with multiple viewing modes, themes, and customization options.

## Unified Block System

When multiple Claude Code sessions are active simultaneously, they all share a single 5-hour billing block. The system intelligently determines which block timing to display based on your work patterns.

**Important**: Token counts and session displays are filtered to show only sessions with activity that overlaps with the unified block time window. This ensures the displayed totals accurately reflect what will be billed for the current 5-hour period. Sessions are included if they have any activity within the billing window, regardless of when they started.

### Current Billing Block Identification

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

### Manual Override

For testing or debugging, you can override the unified block start time:

```bash
# Override unified block to start at 2:00 PM (14:00 in 24-hour format)
pccu monitor --block-start 14

# Override with timezone consideration (hour is interpreted in your configured timezone)
pccu monitor --block-start 18 --show-sessions
```

**Important**: The `--block-start` hour (0-23) is interpreted in your configured timezone and automatically converted to UTC for internal processing.

## Compact Interface

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

## Session Details (Default)

Sessions are shown by default. Set `show_active_sessions: false` in config to hide. Shows:
- Individual session information
- Project and session IDs
- Model types (Opus, Sonnet)
- Token usage per session
- Sessions sorted by newest activity first

**Session Filtering**: The sessions table displays only sessions with activity that overlaps with the current 5-hour billing window. This ensures accurate billing representation - sessions are shown if they have any activity within the unified block time window, regardless of when they started.

## Project Aggregation Mode (Default)

Project aggregation is also enabled by default. When both session display and project aggregation are enabled (the default), you get:
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

## Smart Token Limit Management

- **Auto-adjustment**: When current usage exceeds the configured limit, the limit is automatically increased and saved to the config file
- **Visual indicators**: Progress bars turn red when exceeding the original limit
- **Real-time updates**: Limits update immediately during monitoring

## Token Usage Calculation

PAR CC Usage calculates token consumption using a comprehensive approach that accounts for all token types and applies cost-based multipliers:

### Token Types Included
- **Input tokens**: User prompts and context
- **Output tokens**: AI responses and generated content
- **Cache creation tokens**: Tokens used to create context caches
- **Cache read tokens**: Tokens read from existing context caches

**Total Calculation**: All token types are summed together for accurate billing representation.

### Model-Based Token Multipliers

To reflect the actual cost differences between Claude models, tokens are adjusted using multipliers:

- **Opus models** (`claude-opus-*`): **5x multiplier** - reflects significantly higher cost
- **Sonnet models** (`claude-sonnet-*`): **1x multiplier** - baseline cost
- **Other/Unknown models**: **1x multiplier** - baseline cost

**Multiplier Application**: The multiplier is applied to the total token count (input + output + cache tokens) for each message, then aggregated by model within each billing block.

### Block-Level Aggregation
- **Per-session blocks**: Each 5-hour session maintains separate token counts
- **Per-model tracking**: Token counts are tracked separately for each model within a block
- **Unified billing**: When multiple sessions are active, the system aggregates tokens from all sessions that overlap with the current billing period

### Deduplication
- **Message + Request ID**: Prevents double-counting when JSONL files are re-processed
- **Processed hash tracking**: Maintains a cache of seen message combinations
- **Cross-session deduplication**: Works across all active sessions and projects

### Display Calculations
- **Unified Block Total**: Shows tokens from all sessions overlapping the current 5-hour billing window
- **Per-Model Breakdown**: Displays individual model contributions with multipliers applied
- **Burn Rate**: Calculated as tokens per minute based on activity within the current block
- **Projections**: Estimates total block usage based on current burn rate

## Model Display Names

Model identifiers are simplified for better readability:
- `claude-opus-*` → **Opus**
- `claude-sonnet-*` → **Sonnet**
- Unknown/other models → **Unknown**

**Note**: Claude Code primarily uses Opus and Sonnet models. Any other model names (including Haiku) are normalized to "Unknown".

## Time Format Options

Configure time display format through `display.time_format` setting:
- **24h format** (default): Shows time as `14:30` and `2024-07-08 14:30:45 PDT`
- **12h format**: Shows time as `2:30 PM` and `2024-07-08 2:30:45 PM PDT`

The time format applies to:
- Real-time monitor display (header and block progress)
- List command output (time ranges)
- Block time ranges in all display modes

## Project Name Customization

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

## Cost Tracking & Pricing

PAR CC Usage includes comprehensive cost tracking capabilities using LiteLLM's pricing data for accurate cost calculations across all supported Claude models.

### Enabling Cost Display

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

### Features

- **Real-time cost tracking**: Live cost calculations displayed alongside token usage
- **Per-model accuracy**: Precise cost calculations for each Claude model (Opus, Sonnet, Haiku)
- **Activity table integration**: Optional cost columns in both project and session aggregation views
- **Total cost display**: Overall cost shown in the main token usage summary
- **Burn rate cost estimation**: Intelligent 5-hour block cost projection based on current spending rate
- **LiteLLM integration**: Uses LiteLLM's comprehensive pricing database for accuracy
- **Efficient caching**: Built-in pricing cache for optimal performance

### Cost Display Locations

When `show_pricing` is enabled, cost information appears in:

1. **Main Usage Summary**: Total cost displayed next to token counts (e.g., "84.1M $34.85")
2. **Burn Rate Line**: Estimated total cost for 5-hour block based on current spending rate (e.g., "531K/m Est: 159.3M (90%) Est: $65.51 ETA: 2h 28m")
3. **Activity Tables**:
   - Project aggregation mode: Cost column showing project-level costs
   - Session aggregation mode: Cost column showing session-level costs
4. **List Command Output**: Cost information in table, JSON, and CSV formats with cost source tracking

### Pricing Data

PAR CC Usage uses LiteLLM's comprehensive pricing database for accurate, up-to-date model costs with intelligent fallback handling:

**Core Pricing Features:**
- **Intelligent cost hierarchy**: Three-tier cost calculation system for maximum accuracy
  1. **Native cost data (Priority 1)**: Uses cost data from Claude JSONL files when available
  2. **LiteLLM calculation (Priority 2)**: Falls back to real-time pricing calculations
  3. **Cost source transparency**: All outputs include cost calculation source for debugging
- **Real-time pricing data**: Uses LiteLLM's pricing database for current model costs
- **Comprehensive model support**: Covers all Claude model variants with accurate per-token pricing
- **Token type handling**: Proper pricing for input, output, cache creation, and cache read tokens
- **Automatic model mapping**: Maps Claude Code model names to LiteLLM pricing keys
- **Future-proof design**: Automatically uses native Claude cost data when available

**Intelligent Fallback System:**
- **Unknown model handling**: Models marked as "Unknown" automatically display $0.00 cost
- **Pattern-based fallbacks**: When exact model names aren't found, uses intelligent pattern matching:
  - Models containing "opus" → Falls back to Claude Opus pricing
  - Models containing "sonnet" → Falls back to Claude Sonnet pricing  
  - Models containing "haiku" → Falls back to Claude Haiku pricing
- **Fuzzy matching**: Partial name matching for model variants and prefixes
- **Generic Claude fallbacks**: Unrecognized Claude models fall back to Sonnet pricing as a safe default
- **Graceful error handling**: Missing pricing data doesn't break functionality

**Cost Calculation Hierarchy:**

PAR CC Usage implements an intelligent three-tier cost calculation system for maximum accuracy:

```bash
# Example list output showing cost source transparency
pccu list --show-pricing --format json
[
  {
    "project": "my-app",
    "session": "abc123...",
    "model": "opus",
    "tokens": 150000,
    "active": true,
    "cost": 12.50,
    "cost_source": "block_native"     # Native cost from Claude
  },
  {
    "project": "my-app",
    "session": "def456...",
    "model": "sonnet",
    "tokens": 75000,
    "active": true,
    "cost": 3.25,
    "cost_source": "litellm_calculated"  # Calculated with LiteLLM
  }
]
```

**Cost Source Types:**
- `"block_native"`: Cost from TokenBlock native data (highest priority)
- `"usage_native"`: Cost from TokenUsage native data (medium priority)  
- `"litellm_calculated"`: Cost calculated using LiteLLM pricing (fallback)

**Cost Validation:**
- Native cost data is validated for reasonableness ($0.01-$1000.00)
- Invalid native costs automatically fall back to LiteLLM calculation
- Suspiciously high costs (>$1000) are logged and ignored

**Examples of Fallback Behavior:**
- `"Unknown"` → $0.00 cost (no charges applied)
- `"claude-opus-custom"` → Uses Claude Opus pricing via pattern matching
- `"anthropic/claude-sonnet-experimental"` → Uses Claude Sonnet pricing via fuzzy matching
- `"custom-claude-model"` → Uses Claude Sonnet pricing as generic fallback

## Theme System

PAR CC Usage includes a comprehensive theme system that allows you to customize the visual appearance of the CLI interface to match your preferences, terminal setup, and accessibility needs.

### Available Themes

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

### Theme Configuration

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

### Theme Management Commands

```bash
# List all available themes with descriptions
pccu theme list

# Get current theme setting
pccu theme current

# Set default theme (saves to config)
pccu theme set <theme-name>
```

### Theme Features

- **Semantic Color System**: Uses meaningful color names (success, warning, error, info) for consistency
- **Rich Integration**: Full integration with Rich library for optimal terminal rendering
- **Responsive Design**: Themes work across all display modes (normal, compact, sessions)
- **Consistent Application**: Colors are applied uniformly across all UI elements
- **Configuration Flexibility**: Multiple ways to set themes (CLI, config file, environment)

### Theme Scope

Themes apply to all visual elements:
- **Progress bars**: Token usage and block progress indicators
- **Tables**: Project and session data tables
- **Status indicators**: Active/inactive sessions, success/error states
- **Burn rate displays**: Token consumption metrics
- **Headers and borders**: UI structure elements
- **Cost information**: Pricing and cost calculation displays (when enabled)

### Best Practices

- **Light terminals**: Use `light` or `accessibility` themes
- **Dark terminals**: Use `default` or `dark` themes
- **Accessibility needs**: Use `accessibility` theme for high contrast
- **Professional environments**: Use `minimal` theme for clean appearance
- **Testing themes**: Use `--theme` flag to test before setting as default
