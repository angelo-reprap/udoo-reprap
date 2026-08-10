# Matching-Anfrage Extrakt (DeepSeek) — Konzept-Test

Ziel: Bevor UI/API gebaut wird, Prompt + Schema an einer echten
Weiterleitungs-Mail (Hays via Karsten Bär) gegen DeepSeek prüfen.

## Dateien

| Datei | Inhalt |
|-------|--------|
| `PROMPT_SYSTEM.txt` | System-Prompt (JSON-Schema + Fwd-Regeln) |
| `fixture-hays-fwd.txt` | Bereinigter Mail-Body (Beispiel) |
| `fixture-hays-fwd.expected.json` | Soll-Logik für Abgleich |
| `../PROBE-matching-anfrage-extrakt.sh` | Live-Probe gegen DeepSeek |

## Festlegungen

- Wizard im Matching (`?tab=neu`)
- Modi: Formular vorausfüllen **und** Speichern & Matchen
- **Nur DeepSeek** (kein Ollama)

## Soll-Kern (Hays-Fwd)

- Kunde = **Hays AG** (nicht baer consulting)
- Ansprechpartner = **Tristan Treder** / tristan.treder@hays.de
- Weiterleitung = ja (Karsten Bär)
- Titel = IT Network & Security Engineer – Fortinet
- Start asap, Dauer 3, Standort Remote
- stundensatz_max = null
- Endkunde Life-Sciences/MedTech nur als Hinweis

## Ausführen (ucs5)

```bash
cd /mnt/public/udoo-reprap && git fetch origin cursor/abpe-shaduler-scaffold-7f07
bash <(git show origin/cursor/abpe-shaduler-scaffold-7f07:scripts/PROBE-matching-anfrage-extrakt.sh)

# JSON speichern:
SAVE_JSON=/tmp/hays-extrakt.json bash <(git show origin/cursor/abpe-shaduler-scaffold-7f07:scripts/PROBE-matching-anfrage-extrakt.sh)
```

Voraussetzung: `/opt/abpe/backend/settings.json` → `ai_models.deepseek.api_key`.
