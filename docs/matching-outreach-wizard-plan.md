# Matching Outreach Wizard — Plan

Branch: `cursor/matching-outreach-wizard-1532` (nicht mit CV-Extractor mischen).
CV-Convert auf ucs5 parallel laufen lassen.

## Ziel

Shortlist → Schwellwert → **„Alle anschreiben“** öffnet sequentiellen Wizard:

1. DeepSeek: warum anschreiben / Interesse / Antwortchance  
2. Persönliches Anschreiben (Draft)  
3. Manuell editieren oder aussortieren  
4. Optional glätten  
5. Senden (CRM)  
6. Status `contacted` + optional Wiedervorlage (Shaduler)  
7. Nächster Kandidat  

## MVP Status (2026-08-18)

| Step | Endpoint / UI |
|------|----------------|
| Deep-reason | `POST /matching/api/outreach/<match_result_id>/deep-reason/` |
| Letter draft | `POST /matching/api/outreach/<match_result_id>/letter/draft/` |
| Polish | `POST /matching/api/outreach/letter/polish/` |
| Complete | `POST /matching/api/outreach/<match_result_id>/complete/` |
| Alle anschreiben | Modal in `mod-matching.js` (`openOutreachWizard`) |

Shortlist-ID = **MatchResult.id** → Backend `get_or_create` **ProjectConsultant**.

## Deploy ucs5

```bash
cd /mnt/public/udoo-reprap
git fetch origin cursor/matching-outreach-wizard-1532
bash scripts/SYNC-matching-outreach-wizard.sh
# Browser: Ctrl+F5 auf Matching Shortlist → Alle anschreiben
```

## Dateien

- `Repo_abpe/abpe_matching_workflow/incoming/services/outreach_wizard.py`
- `Repo_abpe/abpe_matching_workflow/incoming/views.py` / `urls.py`
- `Repo_abpe/abpe_ui/incoming/mod-matching.js` (+ static mirror)
