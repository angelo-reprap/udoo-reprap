# Matching Outreach Wizard — Plan (Draft)

Parallel zum `bbb`-Batch. Kein Umbau am CV-Extractor.

## Ziel

Nach Shortlist (Schwellwert → N Berater): **sequentiell** pro Kandidat

1. DeepSeek begründet CV↔Anfrage (warum anschreiben / Interesse / Antwortchance)
2. Persönliches Anschreiben draften
3. Manuell editieren oder aussortieren
4. Optional DeepSeek glätten (Stil behalten)
5. Senden
6. Wiedervorlage (Default, editierbar wie „Aufgabe erzeugen“)
7. Nächster Kandidat

Popup-im-Popup: ja (bestehendes Modal-Stacking).

## Inventar (ucs5)

```bash
cd /mnt/public/udoo-reprap
git pull --rebase origin cursor/cv-extractor-7f07
bash scripts/inventory-matching-wizard-apis.sh
cat artifacts/matching-wizard-api-*/wizard-gaps.md
```

## Erwartete Lücken (vor Live-Scan)

| ID | API | Erwartung |
|----|-----|-----------|
| W1–W4, W9–W10, W12–W13 | Match/Shortlist/Skills/Extract/Status/Mail/Aufgabe/UI | OK |
| W5 | deep-reason | MISSING |
| W6 | letter/draft | MISSING/PARTIAL |
| W7 | letter save | MISSING |
| W8 | letter/polish | MISSING |
| W11 | Alle anschreiben | Stub |

## Neue Endpoints (Vorschlag)

```
POST /matching/api/match/<uuid>/deep-reason/
  → {why, interest, reply_likelihood, risks, fit_skills, mismatch_notes}

POST /matching/api/match/<uuid>/letter/draft/
  body: {tone?, greeting_hint?, extra_notes?}
  → {subject, body_html, body_text, greeting}

POST /matching/api/letter/polish/
  body: {draft_html|draft_text, user_edits?, keep_style: true}
  → {body_html, body_text}

POST /matching/api/match/<uuid>/outreach/complete/
  body: {send: true, create_task: true, task: {art: wiedervorlage, faellig_am, …}}
  → send via CRM + Shaduler Aufgabe
```

## UI

Shortlist → Button „Outreach-Wizard“ → Modal:

- links: Kandidatenliste (aktuell markiert, excluded ausgegraut)
- rechts: Begründung + Editor + Glätten / Aussortieren / Senden+WV / Weiter

## Branch

Umsetzung später auf Matching-Branch (`cursor/matching-…` / neu `cursor/matching-outreach-wizard-1532`), nicht auf CV-Extractor-Fixes mischen.
