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

The schedule is **dynamic**: the script stays in sync with your **real** reset time — the one Anthropic's API reports — and always restarts from your last session. If a window is already active, it does nothing at all.

## How It Works

The workflow (`.github/workflows/good-morning.yml`) runs every 15 minutes and executes `automation/good_morning.py`, which:

1. Reads the **real reset time** of your 5-hour window from `automation/state.json` (saved by the previous run).
2. **Window still active?** → exits immediately. Zero API calls, zero quota used.
3. **Window expired (or state unknown)?** → sends a minimal 1-token "good morning" directly to the Anthropic API (Haiku model). That single call does double duty: it **starts the new 5-hour window** *and* returns the `anthropic-ratelimit-unified-5h-reset` response header — the true reset time of your account.
4. Saves that reset time back to `state.json` (committed by the workflow). The next runs know *exactly* when the window expires — even if you started it yourself by using Claude before the automation fired.

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
| `CLAUDE_MODEL` | `claude-haiku-4-5-20251001` | Model used (Haiku = minimum cost against quota) |
| `WINDOW_HOURS` | `5` | Fallback estimate, used only if the reset header ever disappears |

You can also narrow the cron in the workflow (e.g. `*/15 5-23 * * *` to skip launching windows at night).

## Notes

- The script reads the window state from the official `anthropic-ratelimit-unified-5h-*` response headers of the API call itself — the same numbers Claude Code sees. (The dedicated usage endpoint can't be used: tokens from `claude setup-token` lack the `user:profile` scope it requires.)
- The pre-warm message costs a negligible fraction of quota: a single 1-token Haiku turn, and only when a new window actually needs starting.
- Even if you hit your limit (HTTP 429), the response headers still carry the reset time, so the script stays in sync instead of failing.
- GitHub Actions may delay cron jobs by a few minutes during peak hours — that's why the check runs every 15 minutes instead of hourly.
