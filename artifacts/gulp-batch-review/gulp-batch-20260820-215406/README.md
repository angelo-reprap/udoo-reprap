# Gulp-Batch Review gulp-batch-20260820-215406

Quelle: `/tmp/gulp-batch-20260820-215406/result.tsv`
DB-TXT: `/tmp/gulp-batch-20260820-215406/source-txt`
Kopiert: 1 Einträge

Pro Person:
- `source/gulp_profil_c.txt` — CRM Rohtext (Quelle)
- `source/AID-*_1.0.0.0.pdf` — Convert-PDF
- `neu/cv/AID-*.pdf` — Pipeline-Ziel
- `extracted/AID-*.txt` — Pipeline-Extrakt
- `extracted/AID-*.pre_json.json` — RAM pre_json (vor DB)
- `extracted/AID-*.db_snapshot.json` — DB nach save (Vergleich)

| Status | Letter/Dir | neu/cv PDF | Quelle TXT |
|--------|------------|------------|------------|
| OK | `bbb/beemers_heiko` | AID-hb_5.2.3.0.pdf | ja |
