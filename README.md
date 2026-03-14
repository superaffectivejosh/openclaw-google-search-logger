
# OpenClaw Google Search Logger

Capture your **Google searches as a personal curiosity log** and make them available to your OpenClaw agents.

This project runs a lightweight Python daemon that reads your local Chrome history and writes searches into **daily Markdown files** inside your OpenClaw workspace.

```
Chrome searches
      ↓
Python logger
      ↓
~/.openclaw/workspace/google-searches/YYYY-MM-DD.md
      ↓
Google Drive sync
      ↓
OpenClaw workspace
      ↓
Agents like Pika can read them
```

The result is a **continuous log of what you're exploring, learning, and researching** — perfect input for AI assistants.

---

# Why this exists

Search queries are an incredibly high‑signal personal dataset.

They reveal:

- what you're trying to learn
- problems you're solving
- rabbit holes you're exploring
- your evolving interests over time

Yet almost nobody captures them in a usable form.

This project turns your search history into a **clean, human‑readable dataset** that can power AI agents, reflection tools, and personal knowledge systems.

For OpenClaw users, it becomes a **natural input stream for your agents**.

---

# Features

- Local‑first
- No browser extension
- No cloud API
- No external dependencies
- Human‑readable Markdown output
- Designed for OpenClaw workspaces
- Runs automatically via launchd
- Deduplicates repeated searches
- Append‑only logging

---

# Example output

```md
# Google Searches
Date: 2026-03-14

10:21:44 — openai realtime api openclaw telegram
10:43:11 — chrome history sqlite schema
11:02:09 — supabase edge function webhook tutorial
```

Each day gets its own file:

```
~/.openclaw/workspace/google-searches/

2026-03-14.md
2026-03-15.md
2026-03-16.md
```

These files sync automatically if your OpenClaw workspace is synced with Google Drive.

---

# Installation

Clone the repo:

```bash
git clone https://github.com/YOURNAME/openclaw-google-search-logger.git
cd openclaw-google-search-logger
```

Make the script executable:

```bash
chmod +x google_search_logger.py
```

---

# Run manually

Start the logger:

```bash
python3 google_search_logger.py
```

You should see startup diagnostics like:

```
google_search_logger starting
Python executable: /Library/Frameworks/Python.framework/Versions/3.13/bin/python3
Chrome profile: Default
Chrome history file: ~/Library/Application Support/Google/Chrome/Default/History
Output dir: ~/.openclaw/workspace/google-searches
```

When searches are captured:

```
[logged] 2026-03-14 10:21:44 — openai realtime api openclaw telegram
```

---

# Testing

1. Run the logger
2. Make a Google search:

```
pika logger test 847263
```

3. Wait about 60 seconds

Check the output file:

```bash
tail ~/.openclaw/workspace/google-searches/$(date +%F).md
```

You should see your search logged.

---

# Run automatically (recommended)

Create a launch agent:

```
~/Library/LaunchAgents/com.josh.google-search-logger.plist
```

Example configuration:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<plist version="1.0">
<dict>

<key>Label</key>
<string>com.josh.google-search-logger</string>

<key>ProgramArguments</key>
<array>
<string>/Library/Frameworks/Python.framework/Versions/3.13/bin/python3</string>
<string>/Users/YOURUSERNAME/openclaw-google-search-logger/google_search_logger.py</string>
</array>

<key>RunAtLoad</key>
<true/>

<key>KeepAlive</key>
<true/>

<key>StandardOutPath</key>
<string>/tmp/google-search-logger.out</string>

<key>StandardErrorPath</key>
<string>/tmp/google-search-logger.err</string>

</dict>
</plist>
```

Load it:

```bash
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.josh.google-search-logger.plist
```

---

# Chrome profile configuration

The logger tries profiles in this order:

1. `GOOGLE_SEARCH_LOGGER_PROFILE` environment variable  
2. `Default`  
3. First `Profile *` directory  

To force a profile:

```bash
export GOOGLE_SEARCH_LOGGER_PROFILE="Profile 1"
```

Find your profile using:

```
chrome://version
```

Look for **Profile Path**.

---

# Architecture

This project intentionally keeps the architecture **minimal and robust**.

No:

- browser extension
- database
- API server
- webhook
- cloud dependency

Just:

```
Chrome → Python → Markdown
```

This makes the system extremely reliable and easy to inspect.

---

# OpenClaw integration ideas

Once you have this data, your agents can do interesting things.

### Daily curiosity summaries

```
Daily Curiosity Summary

Primary themes:
• OpenClaw development
• Chrome automation
• AI agent memory systems

Questions explored:
• How to log browser search history
• Launchd background services
• AI agent memory pipelines
```

### Knowledge graph generation

Track evolving interests over time.

### Learning loops

Detect repeated searches across days.

### Research trail

Understand how you arrived at ideas.

---

# Design philosophy

This project follows three principles.

### Local‑first

Your searches never leave your machine.

### Human‑readable

Markdown files you can browse anytime.

### Agent‑ready

A clean input stream for AI systems.

---

# Future ideas

Possible extensions:

- Safari support
- Arc browser support
- YouTube search capture
- GitHub repo capture
- Curiosity dashboards
- OpenClaw auto‑summaries

---

# Contributing

PRs welcome.

Good contributions:

- additional browser support
- improved profile detection
- better deduplication logic
- agent integrations

---

# License

MIT

---

# Final thought

Search queries are a **personal intellectual telemetry stream**.

This project turns them into a dataset your AI agents can understand.
