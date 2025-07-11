# Claude Code Data Structure Analysis

## Overview

Claude Code stores session data in JSONL (JSON Lines) format, with each line representing an event in the chat session. PAR CC Usage monitors both legacy and new Claude Code directories for real-time token usage tracking and analysis.

## File Organization

- **Primary directory**: `~/.config/claude/projects/` (new default)
- **Legacy directory**: `~/.claude/projects/` (still supported)
- **Project folders**: Named after the project path with slashes replaced by dashes (e.g., `-Users-probello-Repos-par-cc-usage/`)
- **Session files**: UUID-named JSONL files (e.g., `bfce6d83-61b9-4b35-8467-a3241a104ff1.jsonl`)
- **Configuration**: Can be overridden with `CLAUDE_CONFIG_DIR` environment variable

## JSONL Structure

Each line in the JSONL file is a JSON object with the following common fields:

### Common Fields
- `sessionId`: UUID of the chat session
- `timestamp`: ISO 8601 timestamp (e.g., "2025-07-08T01:01:14.690Z") 
- `type`: Event type ("user" or "assistant")
- `uuid`: Unique ID for this event
- `parentUuid`: UUID of the parent event (null for first event)
- `cwd`: Current working directory
- `version`: Claude Code version (e.g., "1.0.44")
- `userType`: Always "external"
- `isSidechain`: Boolean (usually false)
- `requestId`: Unique request identifier for deduplication
- `costUSD`: Optional cost in USD for the request

### Message Field
The `message` field contains the actual content and varies by type:

#### User Messages
```json
{
  "role": "user",
  "content": "user input text"
}
```

#### Assistant Messages
```json
{
  "id": "msg_...",
  "type": "message",
  "role": "assistant",
  "model": "claude-sonnet-4-20250514",
  "content": [...],
  "stop_reason": null,
  "stop_sequence": null,
  "wasInterrupted": false,
  "usage": {
    "input_tokens": 9,
    "cache_creation_input_tokens": 26314,
    "cache_read_input_tokens": 0,
    "output_tokens": 8,
    "service_tier": "standard"
  }
}
```

## Token Usage Tracking

Token usage information is found in assistant messages within the `message.usage` field:

- `input_tokens`: New input tokens for this request
- `cache_creation_input_tokens`: Tokens used to create cache
- `cache_read_input_tokens`: Tokens read from cache
- `output_tokens`: Tokens generated in the response
- `service_tier`: Service level (e.g., "standard")

### Total Token Calculation
For each assistant message:
- Total input = `input_tokens` + `cache_creation_input_tokens` + `cache_read_input_tokens`
- Total output = `output_tokens`

## Model Types and Normalization

Claude Code uses only **Sonnet** and **Opus** models. Models are identified in the `message.model` field and normalized using the `ModelType` enum:

### Claude Code Supported Models:
- **Sonnet 4**: `claude-sonnet-4-*` → `ModelType.SONNET_4`
- **Sonnet 3.5**: `claude-3-5-sonnet-*` → `ModelType.CLAUDE_3_5_SONNET`
- **Opus 3**: `claude-3-opus-*` → `ModelType.CLAUDE_3_OPUS`
- **Generic Types**: `opus`, `sonnet` → `ModelType.OPUS/SONNET`

### Token Multipliers:
- **Opus models**: 5x multiplier for billing calculations
- **Sonnet models**: 1x multiplier

### Model Name Handling:
- **Blank/Empty models**: Set to `ModelType.UNKNOWN`
- **Unknown model names**: Set to `ModelType.UNKNOWN`
- **Haiku models**: Set to `ModelType.UNKNOWN` (not used by Claude Code)
- **Other models**: Set to `ModelType.UNKNOWN`

**Note**: While the code may handle other model types for future compatibility, Claude Code currently only uses Sonnet and Opus variants. Any unrecognized or blank model names are normalized to `UNKNOWN`.

## Token Blocks

### Block Creation
- Token blocks are 5-hour windows
- Start time: Floor of the first message timestamp to the nearest hour
- End time: Start time + 5 hours
- New blocks are created when:
  - Time since block start > 5 hours OR
  - Time since last activity > 5 hours
- Gap blocks are inserted for periods of inactivity > 5 hours

### Block Tracking
- All blocks for a session are tracked (not just the most recent)
- Active block: Current time < end_time AND time since last activity < 5 hours
- Sessions can have multiple blocks throughout their lifetime

### Unified Block System
The unified billing block calculation uses an optimal approach to identify the current billing period:

- **Current Block Selection**: Selects blocks that contain the current time, preferring those starting at hour boundaries (00:00 UTC)
- **Hour-floored Start Times**: All blocks start at the top of the hour in UTC
- **Manual Override**: CLI `--block-start HOUR` option for testing and corrections (hour 0-23)
- **Automatic Gap Detection**: Identifies inactivity periods > 5 hours
- **Consistent Billing**: Preferring hour boundaries provides stable billing period representation

#### Block Selection Algorithm:
1. **Collect All Blocks**: Gathers all blocks across all projects and sessions
2. **Filter Active Blocks**: Keeps only blocks that are currently active
3. **Find Current Blocks**: Identifies blocks that contain the current time
4. **Prefer Hour Boundaries**: Prioritizes blocks starting at 00:00 UTC
5. **Fallback Selection**: Uses earliest active block if no hour-boundary blocks exist

## Tool Usage Tracking

PAR CC Usage now tracks Claude Code tool usage with comprehensive analysis:

### Tool Detection
- **Content Analysis**: Parses `message.content` arrays to find `tool_use` blocks
- **Tool Name Extraction**: Identifies tools like `Read`, `Edit`, `Bash`, `Write`, etc.
- **Call Count Tracking**: Counts total tool calls per message
- **Per-Message Tracking**: Associates tool usage with individual messages

### Tool Usage Data
- `tools_used`: List of tool names used in the message
- `tool_use_count`: Total number of tool calls
- **Display Integration**: Shows tool usage in monitoring and list views

## Advanced Features

### XDG Base Directory Compliance
- **Config Directory**: `~/.config/par_cc_usage/` (respects `XDG_CONFIG_HOME`)
- **Cache Directory**: `~/.cache/par_cc_usage/` (respects `XDG_CACHE_HOME`)
- **Data Directory**: `~/.local/share/par_cc_usage/` (respects `XDG_DATA_HOME`)
- **Legacy Migration**: Automatic migration from old config locations

### Notification System
- **Discord Integration**: Webhook notifications for block completion
- **Slack Support**: Configurable webhook notifications
- **Cooldown System**: Prevents duplicate notifications
- **Rich Formatting**: Includes project, session, and token details

### Configuration Management
- **Structured Config**: Pydantic-based configuration with validation
- **Environment Variables**: Full environment variable support
- **Timezone Support**: Configurable timezone display with UTC internal storage
- **Type Safety**: Enum-based configuration eliminates string-based errors

## Implementation Notes

1. **Streaming Required**: Files can be very large (1MB+), so line-by-line streaming is essential
2. **Pydantic Validation**: JSON parsing uses structured Pydantic models for type safety
3. **Timestamp Format**: All timestamps are in ISO 8601 format with UTC timezone
4. **Model Multiplier**: Opus models have their tokens multiplied by 5 for billing calculations
5. **Deduplication**: Uses message IDs and request IDs to prevent double-counting when files are re-read
6. **File Position Tracking**: Maintains cache of file positions to only process new lines on subsequent reads
7. **Multi-Directory Support**: Can monitor multiple Claude directories simultaneously via CLAUDE_CONFIG_DIR environment variable
8. **Interruption Detection**: Tracks `wasInterrupted` flag to identify incomplete messages
9. **Cost Tracking**: Supports `costUSD` field for financial analysis
10. **Comprehensive Error Handling**: Graceful handling of malformed JSON and missing fields

## Data Model Architecture

### Core Data Structures

```
UsageSnapshot (aggregates everything)
  ├── unified_block_tokens() → tokens for current billing window only
  ├── unified_block_tokens_by_model() → per-model breakdown for billing window
  └── Projects (by project name)
       └── Sessions (by session ID)
            └── TokenBlocks (5-hour periods)
                 ├── TokenUsage (individual messages)
                 │   ├── input_tokens, output_tokens
                 │   ├── cache_creation_input_tokens, cache_read_input_tokens
                 │   ├── model, timestamp, message_id, request_id
                 │   ├── tools_used, tool_use_count
                 │   └── was_interrupted, cost_usd
                 └── model_tokens (per-model adjusted tokens with multipliers)
```

### Key Components

1. **TokenUsage**: Individual message token data with tool usage tracking
2. **TokenBlock**: 5-hour billing periods with per-model token tracking
3. **Session**: Collection of token blocks for a single conversation
4. **Project**: Collection of sessions for a project directory
5. **UsageSnapshot**: Top-level aggregation with unified billing logic

### Pydantic Models

The project uses structured Pydantic models for type-safe JSON parsing:

- **TokenUsageData**: Top-level JSONL structure with validation
- **MessageData**: Claude API message structure with model normalization
- **UsageData**: Token usage data with non-negative validation
- **ToolUseBlock**: Tool usage content blocks
- **ValidationResult**: Structured validation results with error handling

### File Processing Pipeline

1. **File Monitoring**: Watchdog-based file change detection
2. **Position Tracking**: Cache-based file position management
3. **JSONL Parsing**: Line-by-line streaming with Pydantic validation
4. **Token Calculation**: Block-based aggregation with model multipliers
5. **Unified Blocks**: Optimal billing period calculation
6. **Display Updates**: Real-time terminal UI updates

## Publishing and Release Management

### Version Management
- **Single Source**: Version defined only in `src/par_cc_usage/__init__.py`
- **Dynamic Loading**: `pyproject.toml` uses hatch's dynamic versioning
- **Automatic Detection**: GitHub Actions validate version format and uniqueness

### GitHub Actions Workflows
- **build.yml**: Continuous integration on pushes to main
- **publish-dev.yml**: Manual TestPyPI publishing for testing
- **publish.yml**: Manual PyPI publishing for production
- **release.yml**: GitHub release creation with signed artifacts

### Security Features
- **Trusted Publishing**: OIDC-based PyPI publishing without API keys
- **Sigstore Integration**: Cryptographic signing of release artifacts
- **Environment Protection**: Separate environments for PyPI and TestPyPI