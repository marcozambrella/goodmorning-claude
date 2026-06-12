# 🌅 Good Morning, Vietnam

> *"Gooood morning, Vietnam!"* — la tua finestra di 5 ore di Claude Max/Pro parte mentre tu dormi ancora.

**Landing page:** https://marcozambrella.github.io/gooodmorning-vietnam/

## Il problema

Il piano Claude Max ha un limite di utilizzo che si resetta ogni **5 ore**, ma il timer parte solo dal **primo messaggio** che mandi. Se inizi a lavorare alle 10:00 e finisci i crediti alle 12:00, devi aspettare fino alle 15:00.

## La soluzione

Un'automazione su **GitHub Actions** (quindi funziona anche a computer spento) che manda un "buongiorno" a Claude appena la finestra precedente scade. Esempio:

- 🌅 L'automazione manda il buongiorno alle **8:00** → la finestra 5h parte subito.
- 💻 Tu inizi a lavorare alle **10:00**.
- ⏳ Se finisci i crediti, il reset arriva alle **13:00**: aspetti solo 3 ore, non 5.

La cadenza è **dinamica**: lo script controlla lo stato reale della finestra e riparte sempre dall'ultima sessione. Se una sessione è già in corso, **non manda nulla**.

## Come funziona

Il workflow (`.github/workflows/good-morning.yml`) gira ogni 15 minuti e lancia `automation/good_morning.py`, che:

1. Interroga l'endpoint usage OAuth di Anthropic per leggere lo stato della finestra 5h.
2. **Finestra attiva?** → skip, nessun messaggio (non sprechi crediti).
3. **Finestra scaduta?** → manda un messaggio minimo via `claude -p` con il modello Haiku (il più economico), avviando una nuova finestra.
4. Se l'endpoint usage non risponde, usa un fallback locale (`automation/state.json` con il timestamp dell'ultimo invio).

## Setup (5 minuti)

### 1. Genera il token OAuth (richiede piano Pro/Max)

Sul tuo computer, dove hai già fatto login a Claude Code:

```bash
claude setup-token
```

Copia il token che viene stampato (è valido 1 anno).

### 2. Imposta il secret nella repo

```bash
gh secret set CLAUDE_CODE_OAUTH_TOKEN --repo <tuo-user>/gooodmorning-vietnam
```

(incolla il token quando richiesto), oppure da GitHub: **Settings → Secrets and variables → Actions → New repository secret**.

### 3. Fatto!

Il workflow parte da solo. Puoi testarlo subito da **Actions → Good Morning, Vietnam → Run workflow**.

## Personalizzazione

In `automation/good_morning.py`:

| Costante | Default | Descrizione |
|---|---|---|
| `GREETING` | "Buongiorno! ..." | Il messaggio inviato a Claude |
| `CLAUDE_MODEL` | `haiku` | Modello usato (Haiku = costo minimo sulla quota) |
| `WINDOW_HOURS` | `5` | Durata della finestra (per il fallback) |

Nel workflow puoi anche restringere il cron (es. `*/15 5-23 * * *` per non avviare finestre di notte).

## Note

- L'endpoint usage (`api.anthropic.com/api/oauth/usage`) non è documentato ufficialmente: se cambia, lo script ricade automaticamente sul fallback a tempo.
- Il messaggio di pre-warm consuma una quantità trascurabile di quota (un turno Haiku senza tool).
- GitHub Actions può ritardare i cron schedulati di qualche minuto nelle ore di punta: per questo il controllo gira ogni 15 minuti.
