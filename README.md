# 🌅 Good Morning, Vietnam

> *"Gooood morning, Vietnam!"* — your Claude Max/Pro 5-hour window starts while you're still asleep.

**Landing page:** https://marcozambrella.github.io/gooodmorning-vietnam/

## The Problem

Claude Max gives you a generous usage window that resets every **5 hours**, but the timer only starts at your **first message**. Start working at 10:00 AM, hit your limit at noon — you're now stuck until 3:00 PM, waiting the full 5 hours.

## The Solution

A tiny automation on **GitHub Actions** (works even when your computer is off) that sends Claude a "good morning" the moment your previous window expires. Example:

- 🌅 Automation sends the greeting at **8:00 AM** → 5-hour window starts immediately.
- 💻 You sit down to work at **10:00 AM**.
- ⏳ If you hit your limit at noon, reset lands at **1:00 PM**: wait 1 hour instead of 3.

The schedule is **dynamic**: the script checks the actual window state and always restarts from your last session. If a session is already active, it sends nothing.

## How It Works

The workflow (`.github/workflows/good-morning.yml`) runs every 15 minutes and executes `automation/good_morning.py`, which:

1. Queries Anthropic's OAuth usage endpoint to read the 5-hour window status.
2. **Window active?** → skip, no message (don't waste credits).
3. **Window expired?** → send a minimal message via `claude -p` with Haiku model (cheapest), starting a new window.
4. If the usage endpoint is down, falls back to local state (`automation/state.json` with last-send timestamp).

## Setup (5 minutes)

### 1. Generate your OAuth token (requires Pro/Max plan)

On your computer where you're already logged into Claude Code:

```bash
claude setup-token
```

Copy the printed token — it's valid for 1 year.

### 2. Set the secret in your repo

```bash
gh secret set CLAUDE_CODE_OAUTH_TOKEN --repo <your-user>/gooodmorning-vietnam
```

(paste the token when prompted), or via GitHub: **Settings → Secrets and variables → Actions → New repository secret**.

### 3. Done!

The workflow runs automatically. Test it instantly from **Actions → Good Morning, Vietnam → Run workflow**.

## Customization

In `automation/good_morning.py`:

| Constant | Default | Description |
|---|---|---|
| `GREETING` | `"gooodmorning claudeee!!!"` | Message sent to Claude |
| `CLAUDE_MODEL` | `haiku` | Model used (Haiku = minimum cost against quota) |
| `WINDOW_HOURS` | `5` | Window duration (for fallback logic) |

You can also narrow the cron in the workflow (e.g. `*/15 5-23 * * *` to skip launching windows at night).

## Notes

- The usage endpoint (`api.anthropic.com/api/oauth/usage`) is undocumented: if it changes, the script automatically falls back to time-based logic.
- The pre-warm message costs a negligible fraction of quota (one Haiku turn, no tools).
- GitHub Actions may delay cron jobs by a few minutes during peak hours — that's why the check runs every 15 minutes instead of hourly.
