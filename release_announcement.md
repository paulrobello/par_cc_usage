**PAR CC Usage v0.8.0 Released - Claude Code Status Line Integration!**

# **What It Does**

Tracks Claude Code usage with real-time token monitoring, pricing analytics, and billing block calculations — now with **live status bar integration** directly in Claude Code!

![Claude Code Status Line](status_line.png)

# **What's New in v0.8.0**

## 🔌 **Claude Code Status Line Integration**
- **One-Command Setup**: Simply run `pccu install-statusline` to enable
- **Real-Time Display**: Live token usage shown directly in Claude Code's status bar
- **Billing Block Timer**: See time remaining in your current 5-hour block (e.g., ⏱️ 2h 8m)
- **Session & Grand Total Modes**: Track current session or aggregate usage
- **Auto-Installation**: Automatically configures Claude Code's settings.json

## 📊 **Status Line Format**
```
🪙 495.7M/510.7M (97%) - 💬 736/1,734 - 💰 $155.27/$166.80 - ⏱️ 2h 8m
```
- Token usage with percentage
- Message count tracking
- Real-time cost in USD
- Time remaining in billing block

## 🚀 **Quick Setup**
```bash
# Install/upgrade PAR CC Usage
uv tool install -U par-cc-usage

# Enable status line with one command
pccu install-statusline

# Start monitoring (required for live updates)
pccu monitor
```

# **Previous Features**
- Real-time pricing and cost tracking (per-model, per-session)
- Burn rate analytics with ETA and 5-hour block projection
- Discord/Slack webhook notifications
- Unified billing block system with smart deduplication
- WCAG AAA-compliant high-contrast themes
- Persistent and per-command theme overrides

# **Key Features**
- 📊 Live token tracking (Opus/5x, Sonnet/1x multipliers)
- 🔥 Burn rate + ETA with billing block visualization
- 💰 Real-time cost estimation using LiteLLM pricing
- 🔔 Discord/Slack notifications on block completion
- 💻 **NEW: Claude Code status bar integration**
- ⏱️ **NEW: Block time remaining display**
- ⚙️ CLI tool with themes, compact mode, session/project views
- 🛠️ Debug and analytics tools for billing anomalies

# **GitHub & PyPI**

- GitHub: [https://github.com/paulrobello/par_cc_usage](https://github.com/paulrobello/par_cc_usage)
- PyPI: [https://pypi.org/project/par-cc-usage/](https://pypi.org/project/par-cc-usage/)

# **Who's This For?**

If you're using Claude Code and want to see your usage without leaving the editor — this update is for you. Perfect for devs who want real-time visibility into their token consumption, costs, and billing block status.

**Note**: Remember that `pccu monitor` must be running for the status line to update in real-time.
