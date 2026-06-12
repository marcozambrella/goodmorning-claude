#!/usr/bin/env python3
"""Diagnostica TEMPORANEA: capisce perche' /api/oauth/usage risponde 403
e verifica quali header anthropic-ratelimit-* arrivano da una chiamata
minimale a /v1/messages. Non stampa mai il token.
"""

import json
import os
import sys
import urllib.error
import urllib.request

TOKEN = os.environ.get("CLAUDE_CODE_OAUTH_TOKEN", "").strip()
if not TOKEN:
    print("ERRORE: CLAUDE_CODE_OAUTH_TOKEN mancante")
    sys.exit(1)

print(f"Token presente: prefisso {TOKEN[:12]}..., lunghezza {len(TOKEN)}")


def try_get(label: str, url: str, headers: dict) -> None:
    print(f"\n=== GET {label} ===")
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {TOKEN}", **headers})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8")
            print(f"HTTP {resp.status}")
            try:
                data = json.loads(body)
                print(f"chiavi top-level: {sorted(data.keys())}")
                if "five_hour" in data:
                    print(f"five_hour: {json.dumps(data['five_hour'])}")
            except json.JSONDecodeError:
                print(f"body non-JSON: {body[:200]}")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        print(f"HTTP {exc.code}: {body[:400]}")
    except urllib.error.URLError as exc:
        print(f"errore rete: {exc}")


USAGE_URL = "https://api.anthropic.com/api/oauth/usage"

try_get("usage (header attuali dello script)", USAGE_URL, {
    "anthropic-beta": "oauth-2025-04-20",
    "Content-Type": "application/json",
    "User-Agent": "goodmorning-vietnam/1.0",
})

try_get("usage (User-Agent claude-cli)", USAGE_URL, {
    "anthropic-beta": "oauth-2025-04-20",
    "User-Agent": "claude-cli/2.0.0 (external, cli)",
})

try_get("profile", "https://api.anthropic.com/api/oauth/profile", {
    "anthropic-beta": "oauth-2025-04-20",
    "User-Agent": "claude-cli/2.0.0 (external, cli)",
})

# Chiamata minimale a /v1/messages: gli header di risposta anthropic-ratelimit-*
# contengono lo stato reale della finestra (status + reset time).
print("\n=== POST /v1/messages (1 token, haiku) ===")
payload = json.dumps({
    "model": "claude-haiku-4-5-20251001",
    "max_tokens": 1,
    "system": "You are Claude Code, Anthropic's official CLI for Claude.",
    "messages": [{"role": "user", "content": "hi"}],
}).encode("utf-8")
req = urllib.request.Request(
    "https://api.anthropic.com/v1/messages",
    data=payload,
    method="POST",
    headers={
        "Authorization": f"Bearer {TOKEN}",
        "anthropic-beta": "oauth-2025-04-20",
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
        "User-Agent": "claude-cli/2.0.0 (external, cli)",
    },
)
try:
    with urllib.request.urlopen(req, timeout=60) as resp:
        print(f"HTTP {resp.status}")
        for name, value in sorted(resp.getheaders()):
            if name.lower().startswith("anthropic-"):
                print(f"  {name}: {value}")
except urllib.error.HTTPError as exc:
    body = exc.read().decode("utf-8", errors="replace")
    print(f"HTTP {exc.code}: {body[:400]}")
    for name, value in sorted(exc.headers.items()):
        if name.lower().startswith("anthropic-"):
            print(f"  {name}: {value}")
except urllib.error.URLError as exc:
    print(f"errore rete: {exc}")
