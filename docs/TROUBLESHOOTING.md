# Troubleshooting Guide

This document provides comprehensive troubleshooting guidance for cache issues, debugging, and problem resolution in PAR CC Usage.

## Cache System

### Cache System Overview

PAR CC Usage uses a high-performance cache system to track file positions and avoid re-processing entire JSONL files. The cache provides dramatic performance improvements (0.3s vs 3.9s startup) and ensures data consistency.

**Key Cache Features:**
- **Single FileMonitor Instance**: The monitor uses one FileMonitor throughout the entire process to maintain cache consistency
- **Position Tracking**: Stores last read position for each JSONL file to process only new content
- **Smart Deduplication**: Prevents double-counting tokens when files are accessed multiple times
- **Automatic Updates**: Cache is updated in real-time as new data is processed

### Cache Performance

The cache system provides significant performance benefits:

```bash
# With cache enabled (default)
uv run pccu monitor --snapshot    # ~0.3s startup
uv run pccu monitor              # Fast real-time updates

# With cache disabled (for debugging)
uv run pccu monitor --no-cache --snapshot  # ~3.9s startup
```

### Data Inconsistencies

If counts, costs, or tool usage appear incorrect or inconsistent, the most common cause is cached data from a previous version or corrupted cache state.

#### Quick Fix: Clear Cache

```bash
# Clear all cached data and force complete re-processing
uv run pccu clear-cache

# Verify the issue is resolved
uv run pccu monitor --snapshot

# Alternative: disable cache for one-time verification
uv run pccu monitor --no-cache --snapshot
```

#### When to Clear Cache

- Token counts don't match expected values
- Tool usage shows incorrect tools or counts
- Cost calculations seem wrong or show "-" instead of actual costs
- After upgrading PAR CC Usage versions (especially when cost display was fixed)
- When debugging data processing issues
- If display shows stale or missing information
- If monitor shows no data initially then wrong data after delays

**Note**: Cache clearing forces re-processing of all JSONL files, which may take 3-4 seconds for large datasets but ensures data accuracy.

### Cache Location and Manual Management

The cache is stored in XDG-compliant locations:

```bash
# Default cache location
~/.cache/par_cc_usage/file_states.json

# Respects XDG_CACHE_HOME environment variable
$XDG_CACHE_HOME/par_cc_usage/file_states.json
```

#### Manual Cache Management

```bash
# View cache file contents
cat ~/.cache/par_cc_usage/file_states.json

# Delete cache file manually (alternative to clear-cache command)
rm ~/.cache/par_cc_usage/file_states.json

# View cache directory
ls -la ~/.cache/par_cc_usage/
```

### Cache Debugging

#### Check Cache Status

```bash
# Monitor with cache enabled (default)
uv run pccu monitor --snapshot

# Monitor with cache disabled (for comparison)
uv run pccu monitor --no-cache --snapshot

# Compare performance timing
time uv run pccu monitor --snapshot        # With cache
time uv run pccu monitor --no-cache --snapshot  # Without cache
```

#### Cache Validation

```bash
# Force cache rebuild and compare results
uv run pccu clear-cache
uv run pccu monitor --snapshot > /tmp/with_cache.txt

uv run pccu monitor --no-cache --snapshot > /tmp/without_cache.txt

# Compare outputs (should be identical)
diff /tmp/with_cache.txt /tmp/without_cache.txt
```

## Common Issues and Solutions

### 1. Incorrect Token Counts

**Symptoms:**
- Token counts don't match expected values
- Counts appear too high or too low
- Historical data shows unexpected changes

**Solutions:**
```bash
# Clear cache and rebuild
uv run pccu clear-cache
uv run pccu monitor --snapshot

# Verify with cache disabled
uv run pccu monitor --no-cache --snapshot

# Check for duplicate files or sessions
uv run pccu debug-blocks --show-inactive
```

### 2. Tool Usage Issues

**Symptoms:**
- Missing tool usage information
- Incorrect tool names or counts
- Tool usage not updating

**Solutions:**
```bash
# Clear cache (tool usage is cached)
uv run pccu clear-cache

# Verify tool usage is enabled
uv run pccu monitor --show-tools --snapshot

# Check if tools are being parsed correctly
uv run pccu monitor --debug --snapshot
```

### 3. Cost Calculation Problems

**Symptoms:**
- Missing cost information or cost columns showing "-"
- Cost display showing $0.00 instead of actual costs
- Incorrect cost calculations
- Cost source showing wrong method

**Common Issues & Solutions:**

**Issue: Cost columns show "-" instead of actual costs**
- **Cause**: Fixed in recent version - activity tables now use async cost calculation
- **Solution**: Update to latest version or clear cache to ensure proper cost display

**Other Troubleshooting:**
```bash
# Clear cache and test pricing
uv run pccu clear-cache
uv run pccu monitor --show-pricing --snapshot

# Test pricing API connectivity
uv run python -c "
import asyncio
from src.par_cc_usage.pricing import debug_model_pricing

async def test():
    info = await debug_model_pricing('claude-3-opus-20240229')
    print(f'Pricing info: {info}')

asyncio.run(test())
"

# Debug pricing fallbacks
uv run pccu debug-blocks --show-pricing
```

### 4. Display Issues

**Symptoms:**
- Console jumping or flickering
- Missing or garbled text
- Display not updating

**Solutions:**
```bash
# Use snapshot mode to avoid real-time updates
uv run pccu monitor --snapshot

# Enable debug mode to see error messages
uv run pccu monitor --debug --snapshot

# Check terminal compatibility
uv run pccu monitor --no-emoji --snapshot
```

### 5. File Processing Errors

**Symptoms:**
- "File not found" errors
- JSONL parsing errors
- Missing project data

**Solutions:**
```bash
# Check Claude project directories
ls -la ~/.claude/projects/

# Verify JSONL file format
uv run python -m par_cc_usage.json_analyzer analyze ~/.claude/projects/project_name/session_file.jsonl

# Force full file processing
uv run pccu monitor --no-cache --snapshot

# Check file permissions
ls -la ~/.claude/projects/*/session_*.jsonl
```

## Debug Commands

### Core Debug Commands

```bash
# Debug unified block calculation
uv run pccu debug-unified

# Debug block information with inactive blocks
uv run pccu debug-blocks --show-inactive

# Debug session information
uv run pccu debug-sessions

# Debug activity patterns
uv run pccu debug-activity
```

### Debug Output Control

```bash
# Enable debug output (suppressed in continuous monitor mode)
uv run pccu monitor --debug --snapshot

# View debug output in list mode
uv run pccu list --debug

# Combined debug and snapshot mode
uv run pccu debug-blocks --debug --snapshot
```

### Test Commands

```bash
# Test webhook functionality
uv run pccu test-webhook

# Test pricing with different models
uv run python -c "
import asyncio
from src.par_cc_usage.pricing import calculate_token_cost

async def test():
    models = ['claude-3-opus-20240229', 'claude-3-sonnet-20240229', 'claude-3-haiku-20240307']
    for model in models:
        cost = await calculate_token_cost(model, 1000, 500)
        print(f'{model}: \${cost.total_cost:.4f}')

asyncio.run(test())
"

# Test burn rate calculations
uv run pytest tests/test_display.py -k "test_calculate_burn_rate" -v
```

## Performance Troubleshooting

### Startup Performance

**Issue**: Slow startup times

**Diagnosis:**
```bash
# Time with cache enabled
time uv run pccu monitor --snapshot

# Time with cache disabled
time uv run pccu monitor --no-cache --snapshot

# Expected results:
# With cache: ~0.3s
# Without cache: ~3.9s
```

**Solutions:**
```bash
# Ensure cache is enabled (default)
uv run pccu monitor --snapshot

# Clear corrupted cache
uv run pccu clear-cache

# Check cache directory permissions
ls -la ~/.cache/par_cc_usage/
```

### Memory Usage

**Issue**: High memory usage

**Diagnosis:**
```bash
# Monitor memory usage during processing
uv run pccu monitor --snapshot &
PID=$!
ps aux | grep pccu
kill $PID
```

**Solutions:**
```bash
# Use snapshot mode to avoid continuous processing
uv run pccu monitor --snapshot

# Disable features that consume memory
uv run pccu monitor --no-tools --no-pricing --snapshot

# Clear cache to remove old data
uv run pccu clear-cache
```

### File Processing Speed

**Issue**: Slow file processing

**Diagnosis:**
```bash
# Check number of files being processed
find ~/.claude/projects -name "session_*.jsonl" | wc -l

# Check total file sizes
find ~/.claude/projects -name "session_*.jsonl" -exec du -ch {} + | tail -1

# Monitor file processing
uv run pccu monitor --debug --snapshot
```

**Solutions:**
```bash
# Enable cache for faster processing
uv run pccu monitor --snapshot

# Process specific projects only
uv run pccu monitor --projects project_name --snapshot

# Use incremental processing
uv run pccu monitor  # Continuous mode processes only new data
```

## Error Messages and Solutions

### Common Error Messages

#### "No Claude project directories found"
```bash
# Check if Claude projects exist
ls -la ~/.claude/projects/

# Check legacy locations
ls -la ~/.claude/
ls -la ~/Library/Application\ Support/Claude/

# Create test project directory
mkdir -p ~/.claude/projects/test_project
```

#### "Failed to parse JSONL file"
```bash
# Check file format
uv run python -m par_cc_usage.json_analyzer analyze problematic_file.jsonl

# Validate JSON structure
jq . < problematic_file.jsonl | head -10

# Skip problematic files
uv run pccu monitor --ignore-errors --snapshot
```

#### "Pricing API unavailable"
```bash
# Test internet connectivity
curl -s https://api.litellm.ai/pricing | head -10

# Use without pricing
uv run pccu monitor --no-pricing --snapshot

# Check firewall/proxy settings
uv run pccu test-webhook
```

#### "Cache corruption detected"
```bash
# Clear and rebuild cache
uv run pccu clear-cache
uv run pccu monitor --snapshot

# Check cache directory
ls -la ~/.cache/par_cc_usage/

# Verify cache permissions
chmod 755 ~/.cache/par_cc_usage/
```

## Configuration Issues

### Configuration File Problems

```bash
# Check configuration file location
uv run pccu debug-config

# Validate configuration syntax
uv run python -c "
import yaml
with open('~/.config/par_cc_usage/config.yaml') as f:
    config = yaml.safe_load(f)
    print('Configuration is valid')
"

# Reset to defaults
mv ~/.config/par_cc_usage/config.yaml ~/.config/par_cc_usage/config.yaml.backup
uv run pccu init
```

### Environment Variables

```bash
# Check environment variables
env | grep -E "(PAR_CC_USAGE|XDG_)"

# Test with clean environment
env -i uv run pccu monitor --snapshot

# Reset XDG directories
unset XDG_CONFIG_HOME XDG_CACHE_HOME XDG_DATA_HOME
uv run pccu monitor --snapshot
```

## Advanced Troubleshooting

### Log Analysis

```bash
# Enable verbose logging
uv run pccu monitor --debug --snapshot 2>&1 | tee debug.log

# Analyze log patterns
grep -E "(ERROR|WARNING|Exception)" debug.log

# Check for timing issues
grep -E "(took|elapsed|duration)" debug.log
```

### System Integration

```bash
# Check system dependencies
uv run python -c "
import rich
import typer
import pydantic
import litellm
print('Dependencies OK')
"

# Test file system permissions
touch ~/.cache/par_cc_usage/test_file
rm ~/.cache/par_cc_usage/test_file

# Check Python version compatibility
python --version
uv run python --version
```

### Performance Profiling

```bash
# Profile startup time
uv run python -m cProfile -o startup_profile.prof -c "
import par_cc_usage.main
# Run minimal startup
"

# Analyze profile
uv run python -c "
import pstats
p = pstats.Stats('startup_profile.prof')
p.sort_stats('cumulative').print_stats(20)
"
```

## Getting Help

### Information Collection

When reporting issues, collect this information:

```bash
# System information
uv run pccu debug-system

# Configuration details
uv run pccu debug-config

# File system state
ls -la ~/.claude/projects/
ls -la ~/.cache/par_cc_usage/
ls -la ~/.config/par_cc_usage/

# Recent log output
uv run pccu monitor --debug --snapshot 2>&1 | tail -50
```

### Issue Report Template

```
**Environment:**
- OS: [macOS/Linux/Windows]
- Python version: [output of `python --version`]
- PAR CC Usage version: [output of `uv run pccu --version`]

**Problem:**
- Expected behavior: [description]
- Actual behavior: [description]
- Error messages: [if any]

**Steps to reproduce:**
1. [First step]
2. [Second step]
3. [Third step]

**Debugging information:**
- Cache enabled: [yes/no]
- File count: [number of JSONL files]
- Configuration: [relevant config settings]

**Logs:**
```
[paste relevant log output here]
```
```

### Support Resources

- GitHub Issues: Report bugs and request features
- Documentation: Refer to architecture and development guides
- Debug commands: Use built-in debugging tools
- Community: Share solutions and workarounds
