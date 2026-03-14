# OpenClaw Google Search Logger

Capture your **Google searches and Google Image searches as a personal curiosity log** and make them available to your OpenClaw agents.

This project runs a lightweight Python daemon that reads your local Chrome history and writes searches into **daily Markdown files** inside your OpenClaw workspace.

```text
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

The result is a **continuous log of what you're exploring, learning, researching, and visually ideating** — perfect input for AI assistants.

---

## Why this exists

Search queries are an incredibly high-signal personal dataset.

They reveal:
- what you're trying to learn
- problems you're solving
- rabbit holes you're exploring
- your evolving interests over time
- when you're doing technical research vs visual inspiration hunting

Yet almost nobody captures them in a usable form.

This project turns your search history into a **clean, human-readable dataset** that can power AI agents, reflection tools, and personal knowledge systems.

For OpenClaw users, it becomes a **natural input stream for your agents**.

---

## Features

- Local-first
- No browser extension
- No cloud API
- No external dependencies
- Human-readable Markdown output
- Designed for OpenClaw workspaces
- Runs automatically via launchd
- Deduplicates repeated searches
- Append-only logging
- Distinguishes between regular Google searches and Google Image searches

---

## Example output

```md
# Google Searches
Date: 2026-03-14

10:21:44 — [web] openai realtime api openclaw telegram
10:43:11 — [image] cute pikachu wallpaper
11:02:09 — [web] chrome history sqlite schema
```

Each day gets its own file:

```text
~/.openclaw/workspace/google-searches/

2026-03-14.md
2026-03-15.md
2026-03-16.md
```

These files sync automatically if your OpenClaw workspace is synced with Google Drive.

---

## How Google Image Search detection works

The logger uses the same simple URL-query-string approach as regular Google Search.

It looks for Google URLs like:

```text
https://www.google.com/search?q=...
```

Then:

- extracts the search text from the `q` parameter
- checks whether `tbm=isch` is present
- logs the search as:
  - `[image]` when `tbm=isch`
  - `[web]` otherwise

This is a practical heuristic for personal logging and works well for common Google Images flows.

---

## Installation

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

## Run manually

Start the logger:

```bash
python3 google_search_logger.py
```

You should see startup diagnostics like:

```text
google_search_logger starting
Python executable: /Library/Frameworks/Python.framework/Versions/3.13/bin/python3
Chrome profile: Default
Chrome history file: ~/Library/Application Support/Google/Chrome/Default/History
Output dir: ~/.openclaw/workspace/google-searches
```

When searches are captured:

```text
[logged] 2026-03-14 10:21:44 — [web] openai realtime api openclaw telegram
[logged] 2026-03-14 10:43:11 — [image] cute pikachu wallpaper
```

---

## Testing

1. Run the logger.
2. Make a regular Google search:

```text
pika logger web test 847263
```

3. Make a Google Image search:

```text
cute pikachu wallpaper
```

Then click **Images** in Google, or search directly in Google Images.

4. Wait about 60 seconds.

Check the output file:

```bash
tail ~/.openclaw/workspace/google-searches/$(date +%F).md
```

You should see new lines with `[web]` and `[image]` tags.

---

## Run automatically with launchd

Create a launch agent:

```text
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

## Chrome profile configuration

The logger tries profiles in this order:

1. `GOOGLE_SEARCH_LOGGER_PROFILE` environment variable
2. `Default`
3. First `Profile *` directory

To force a profile:

```bash
export GOOGLE_SEARCH_LOGGER_PROFILE="Profile 1"
```

Find your profile using:

```text
chrome://version
```

Look for **Profile Path**.

---

## Architecture

This project intentionally keeps the architecture **minimal and robust**.

No:
- browser extension
- database
- API server
- webhook
- cloud dependency

Just:

```text
Chrome → Python → Markdown
```

This makes the system extremely reliable and easy to inspect.

---

## OpenClaw integration ideas

Once you have this data, your agents can do interesting things.

### Daily curiosity summaries

```text
Daily Curiosity Summary

Primary themes:
• OpenClaw development
• Chrome automation
• AI agent memory systems

Visual inspiration:
• Pikachu references
• UI inspiration
• brand imagery

Questions explored:
• How to log browser search history
• Launchd background services
• Agent memory pipelines
```

### Knowledge graph generation

Track evolving interests over time.

### Learning loops

Detect repeated searches across days.

### Research trail

Understand how you arrived at ideas.

### Visual ideation tracking

Understand when you were searching for images vs researching on the web.

---

## Design philosophy

This project follows three principles.

### Local-first

Your searches never leave your machine.

### Human-readable

Markdown files you can browse anytime.

### Agent-ready

A clean input stream for AI systems.

---

## Future ideas

Possible extensions:

- Safari support
- Arc browser support
- YouTube search capture
- GitHub repo capture
- Curiosity dashboards
- OpenClaw auto-summaries
- richer Google vertical detection beyond web and image

---

## Contributing

PRs welcome.

Good contributions:
- additional browser support
- improved profile detection
- better deduplication logic
- agent integrations
- broader Google search vertical classification

---

## License

MIT

---

## Final thought

Search queries are a **personal intellectual telemetry stream**.

And image searches add another layer: **visual curiosity**.

This project turns both into a dataset your AI agents can understand.
