# Gulp-Batch Review gulp-retry-20260821-105239

Quelle: `/tmp/gulp-retry-20260821-105239/result.tsv`
DB-TXT: `/tmp/gulp-batch-20260820-231543/source-txt`
Kopiert: 3 Einträge

Pro Person:
- `source/gulp_profil_c.txt` — CRM Rohtext (Quelle)
- `source/AID-*_1.0.0.0.pdf` — Convert-PDF
- `neu/cv/AID-*.pdf` — Pipeline-Ziel
- `extracted/AID-*.txt` — Pipeline-Extrakt
- `extracted/AID-*.pre_json.json` — RAM pre_json (vor DB)
- `extracted/AID-*.db_snapshot.json` — DB nach save (Vergleich)

| Status | Letter/Dir | neu/cv PDF | Quelle TXT |
|--------|------------|------------|------------|
| FAIL | `bbb/behling_karsten` | no_neu_cv | ja |
| OK | `sch/schroeder_wolfgang` | AID-ws_2.3.4.0.pdf | — |
| FAIL | `ggg/glas_oliver_fritz` | no_neu_cv | ja |
