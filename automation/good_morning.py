#!/usr/bin/env python3
"""Good Morning, Vietnam — pre-warm della finestra 5h di Claude Max.

Avvia la finestra di utilizzo di 5 ore del piano Claude il prima possibile
mandando un messaggio minimo a Claude Code in modalita' headless.

Logica:
1. Interroga l'endpoint OAuth usage per capire se una finestra 5h e' gia' attiva.
2. Se attiva -> non fa nulla (nessun messaggio, la sessione e' gia' in corso).
3. Se scaduta/inesistente -> manda "buongiorno" via `claude -p` per avviarne una nuova.
4. Se l'endpoint usage non risponde o cambia formato -> fallback su state.json
   (timestamp dell'ultimo invio: se sono passate meno di 5 ore, skip).

Pensato per girare in GitHub Actions ogni 15 minuti, con il PC spento.
Richiede: CLAUDE_CODE_OAUTH_TOKEN (generato con `claude setup-token`).
"""

import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

USAGE_ENDPOINT = "https://api.anthropic.com/api/oauth/usage"
STATE_FILE = Path(__file__).parent / "state.json"
WINDOW_HOURS = 5
GREETING = "gooodmorning claudeee!!!  (dont respond to this message)"
CLAUDE_MODEL = "haiku"  # il modello piu' economico: basta un turno qualsiasi
CLAUDE_TIMEOUT_S = 120


def log(msg: str) -> None:
    print(f"[{datetime.now(timezone.utc).isoformat(timespec='seconds')}] {msg}", flush=True)


def sanitize_for_log(text: str) -> str:
    """Sostituisce i caratteri non stampabili con '?' per non rovinare i log."""
    return "".join(c if c.isprintable() or c in "\n\t" else "?" for c in text)


def get_token() -> str:
    token = os.environ.get("CLAUDE_CODE_OAUTH_TOKEN", "").strip()
    if not token:
        log("ERRORE: variabile CLAUDE_CODE_OAUTH_TOKEN mancante.")
        log("Generala in locale con `claude setup-token` e impostala come secret.")
        sys.exit(1)
    return token


def fetch_usage(token: str) -> dict | None:
    """Interroga l'endpoint usage. Ritorna il JSON o None se non disponibile."""
    req = urllib.request.Request(
        USAGE_ENDPOINT,
        headers={
            "Authorization": f"Bearer {token}",
            "anthropic-beta": "oauth-2025-04-20",
            "Content-Type": "application/json",
            "User-Agent": "goodmorning-vietnam/1.0",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError) as exc:
        log(f"Non sono riuscito a contattare l'endpoint usage di Anthropic ({exc}): "
            f"controllo lo stato locale (state.json).")
        return None


def parse_reset_time(value) -> datetime | None:
    """Accetta ISO 8601 o epoch (s/ms) e ritorna un datetime UTC."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        if value > 1e12:  # millisecondi
            value /= 1000
        return datetime.fromtimestamp(value, tz=timezone.utc)
    if isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except ValueError:
            return None
    return None


def window_active_from_usage(usage: dict) -> bool | None:
    """True se la finestra 5h risulta gia' attiva, False se no, None se indecidibile."""
    five_hour = usage.get("five_hour")
    if not isinstance(five_hour, dict):
        log("La risposta della API non contiene i dati 'five_hour': "
            "non posso capire da qui se la finestra e' attiva, controllo lo stato locale.")
        return None

    resets_at = parse_reset_time(
        five_hour.get("resets_at") or five_hour.get("reset_at") or five_hour.get("resetsAt")
    )
    utilization = five_hour.get("utilization")

    if resets_at is None:
        # Nessun reset programmato: con utilization nota e a zero, nessuna finestra attiva.
        if isinstance(utilization, (int, float)):
            if utilization > 0:
                log(f"Nessun orario di reset nella risposta, ma l'utilizzo e' {utilization} "
                    f"(> 0): considero la finestra 5h attiva.")
                return True
            log("Nessun orario di reset nella risposta e utilizzo a 0: "
                "considero la finestra 5h non attiva.")
            return False
        log("La risposta della API non ha un orario di reset valido ne' un utilizzo numerico: "
            "controllo lo stato locale.")
        return None

    now = datetime.now(timezone.utc)
    if resets_at <= now:
        log(f"La finestra 5h precedente e' scaduta (reset previsto per "
            f"{resets_at.isoformat(timespec='seconds')}, ora gia' passato): "
            f"considero la finestra non attiva.")
        return False
    if isinstance(utilization, (int, float)) and utilization <= 0:
        log(f"La finestra 5h scadra' alle {resets_at.isoformat(timespec='seconds')} "
            f"ma l'utilizzo e' 0: considero la finestra non attiva.")
        return False
    log(f"Finestra 5h attiva: reset alle {resets_at.isoformat(timespec='seconds')} "
        f"(tra {resets_at - now}).")
    return True


def read_state() -> dict:
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def write_state(state: dict) -> None:
    tmp_path = STATE_FILE.with_suffix(".json.tmp")
    tmp_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    tmp_path.replace(STATE_FILE)


def window_active_from_state() -> bool:
    last_sent = parse_reset_time(read_state().get("last_sent"))
    if last_sent is None:
        log("Stato locale (state.json) assente o senza 'last_sent': "
            "considero la finestra non attiva.")
        return False
    elapsed = datetime.now(timezone.utc) - last_sent
    if elapsed < timedelta(hours=WINDOW_HOURS):
        log(f"Fallback: ultimo invio {elapsed} fa (< {WINDOW_HOURS}h), skip.")
        return True
    log(f"Fallback: ultimo invio {elapsed} fa (>= {WINDOW_HOURS}h): "
        f"la finestra e' considerata scaduta.")
    return False


def send_good_morning(token: str) -> bool:
    log("Nessuna finestra attiva: invio 'gooodmorning claudee!!!' per avviarne una nuova...")
    env = dict(os.environ, CLAUDE_CODE_OAUTH_TOKEN=token)
    try:
        result = subprocess.run(
            ["claude", "-p", GREETING, "--model", CLAUDE_MODEL],
            capture_output=True,
            text=True,
            errors="replace",
            timeout=CLAUDE_TIMEOUT_S,
            env=env,
            shell=(os.name == "nt"),  # su Windows `claude` e' un .cmd
        )
    except FileNotFoundError:
        log("ERRORE: comando `claude` non trovato. Installa @anthropic-ai/claude-code.")
        return False
    except subprocess.TimeoutExpired:
        log("ERRORE: timeout nell'invio del messaggio.")
        return False

    if result.returncode != 0:
        log(f"ERRORE: claude e' uscito con codice {result.returncode}.")
        log(f"stderr: {sanitize_for_log(result.stderr.strip())[:500]}")
        return False

    log(f"Risposta di Claude: {sanitize_for_log(result.stdout.strip())[:200]}")
    return True


def main() -> int:
    token = get_token()

    usage = fetch_usage(token)
    active = window_active_from_usage(usage) if usage is not None else None
    if active is None:
        active = window_active_from_state()

    if active:
        log("Sessione gia' in corso: nessun messaggio inviato.")
        return 0

    if not send_good_morning(token):
        return 1

    write_state({"last_sent": datetime.now(timezone.utc).isoformat(timespec="seconds")})
    log("Finestra 5h avviata. Buona giornata!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
