#!/usr/bin/env python3
"""Good Morning, Vietnam — pre-warm della finestra 5h di Claude (Pro/Max).

Avvia la finestra di utilizzo di 5 ore del piano Claude il prima possibile,
restando sincronizzato con l'orario di reset REALE del tuo account.

Come funziona:
1. Legge da state.json l'orario di reset reale salvato nell'ultimo run.
2. Se il reset e' nel futuro -> finestra ancora attiva -> esce subito,
   zero chiamate API.
3. Se il reset e' passato (o lo stato manca) -> manda il "buongiorno": una
   chiamata minimale (1 token, modello haiku) a /v1/messages con il token
   OAuth di Claude Code. Quella singola chiamata avvia la nuova finestra 5h
   E restituisce negli header di risposta anthropic-ratelimit-unified-5h-*
   l'orario di reset reale.
4. Salva il nuovo orario di reset in state.json (committato dal workflow):
   i run successivi sanno esattamente quando scade la finestra, anche se
   l'hai avviata tu stesso usando Claude prima dell'automazione.

Nota: l'endpoint /api/oauth/usage NON e' utilizzabile qui — il token di
`claude setup-token` non ha lo scope user:profile (risponde 403). Gli header
di rate-limit della risposta messages sono la fonte ufficiale equivalente.

Pensato per girare in GitHub Actions ogni ~5 minuti, con il PC spento
(GitHub puo' comunque ritardare/saltare i run schedulati: vedi README).
Richiede: CLAUDE_CODE_OAUTH_TOKEN (generato con `claude setup-token`).
"""

import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

MESSAGES_ENDPOINT = "https://api.anthropic.com/v1/messages"
STATE_FILE = Path(__file__).parent / "state.json"
WINDOW_HOURS = 5  # stima di riserva, usata solo se l'header di reset sparisse
GREETING = "gooodmorning claudeee!!!  (dont respond to this message)"
CLAUDE_MODEL = "claude-haiku-4-5-20251001"  # il piu' economico: basta 1 token
RESET_HEADER = "anthropic-ratelimit-unified-5h-reset"
UTILIZATION_HEADER = "anthropic-ratelimit-unified-5h-utilization"
HTTP_TIMEOUT_S = 60
# Il token di `claude setup-token` e' accettato da /v1/messages solo
# presentandosi come Claude Code: servono header beta e system prompt dedicati.
OAUTH_BETA = "oauth-2025-04-20"
CLAUDE_CODE_SYSTEM = "You are Claude Code, Anthropic's official CLI for Claude."


def log(msg: str) -> None:
    print(f"[{datetime.now(timezone.utc).isoformat(timespec='seconds')}] {msg}", flush=True)


def get_token() -> str:
    token = os.environ.get("CLAUDE_CODE_OAUTH_TOKEN", "").strip()
    if not token:
        log("ERRORE: variabile CLAUDE_CODE_OAUTH_TOKEN mancante.")
        log("Generala in locale con `claude setup-token` e impostala come secret.")
        sys.exit(1)
    return token


def read_state() -> dict:
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def write_state(state: dict) -> None:
    tmp_path = STATE_FILE.with_suffix(".json.tmp")
    tmp_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    tmp_path.replace(STATE_FILE)


def parse_iso(value) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def parse_reset_header(headers) -> datetime | None:
    """L'header di reset e' un timestamp epoch in secondi."""
    raw = headers.get(RESET_HEADER)
    if raw is None:
        return None
    try:
        return datetime.fromtimestamp(int(raw), tz=timezone.utc)
    except (ValueError, OSError, OverflowError):
        return None


def describe(dt: datetime, now: datetime) -> str:
    delta = str(dt - now).split(".")[0]
    return f"{dt.isoformat(timespec='seconds')} (tra {delta})"


def send_good_morning(token: str) -> datetime | None:
    """Manda il buongiorno e ritorna l'orario di reset reale, o None se fallisce."""
    log(f"Invio {GREETING!r} (1 token, {CLAUDE_MODEL})...")
    payload = json.dumps({
        "model": CLAUDE_MODEL,
        "max_tokens": 1,
        "system": CLAUDE_CODE_SYSTEM,
        "messages": [{"role": "user", "content": GREETING}],
    }).encode("utf-8")
    req = urllib.request.Request(
        MESSAGES_ENDPOINT,
        data=payload,
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "anthropic-beta": OAUTH_BETA,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
            "User-Agent": "claude-cli/2.0.0 (external, cli)",
        },
    )
    now = datetime.now(timezone.utc)
    try:
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT_S) as resp:
            reset = parse_reset_header(resp.headers)
            utilization = resp.headers.get(UTILIZATION_HEADER, "?")
            if reset is None:
                log(f"ATTENZIONE: risposta OK ma senza header {RESET_HEADER} "
                    f"(forse l'API e' cambiata). Uso la stima di {WINDOW_HOURS}h da adesso.")
                return now + timedelta(hours=WINDOW_HOURS)
            log(f"Messaggio inviato. Finestra 5h: utilizzo {utilization}, "
                f"reset reale alle {describe(reset, now)}.")
            return reset
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:300]
        if exc.code == 429:
            # Limite raggiunto = la finestra e' per forza attiva: gli header
            # ci dicono comunque quando si resetta.
            reset = parse_reset_header(exc.headers)
            if reset is not None:
                log(f"Limite 5h gia' esaurito: la finestra e' comunque attiva, "
                    f"reset alle {describe(reset, now)}.")
                return reset
            log(f"ERRORE: limite raggiunto (429) ma senza header di reset. Dettaglio: {body}")
            return None
        if exc.code in (401, 403):
            log(f"ERRORE: il token non e' valido o e' scaduto (HTTP {exc.code}).")
            log("Rigenera il token con `claude setup-token` e aggiorna il secret "
                "CLAUDE_CODE_OAUTH_TOKEN del repo.")
            log(f"Dettaglio API: {body}")
            return None
        log(f"ERRORE: l'API ha risposto HTTP {exc.code}. Dettaglio: {body}")
        log("Riprovera' automaticamente al prossimo run schedulato.")
        return None
    except (urllib.error.URLError, TimeoutError) as exc:
        log(f"ERRORE di rete verso l'API ({exc}). Riprovera' al prossimo run.")
        return None


def main() -> int:
    token = get_token()
    now = datetime.now(timezone.utc)

    resets_at = parse_iso(read_state().get("resets_at"))
    if resets_at is None:
        log("Nessun orario di reset salvato in state.json: invio il buongiorno "
            "per scoprire (ed eventualmente avviare) la finestra corrente.")
    elif now < resets_at:
        log(f"Finestra 5h ancora attiva: reset alle {describe(resets_at, now)}. "
            f"Nessuna chiamata API, esco.")
        return 0
    else:
        log(f"La finestra precedente si e' resettata alle "
            f"{resets_at.isoformat(timespec='seconds')}: ne avvio una nuova.")

    new_reset = send_good_morning(token)
    if new_reset is None:
        return 1

    write_state({
        "resets_at": new_reset.isoformat(timespec="seconds"),
        "checked_at": now.isoformat(timespec="seconds"),
    })
    log(f"Sincronizzato con il limite reale: prossimo reset alle "
        f"{describe(new_reset, datetime.now(timezone.utc))}. Buona giornata!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
