# Gulp-Batch Review gulp-retry-20260821-110440

Quelle: `/tmp/gulp-retry-20260821-110440/result.tsv`
DB-TXT: `/tmp/gulp-batch-20260820-231543/source-txt`
Kopiert: 2 Einträge

Pro Person:
- `source/gulp_profil_c.txt` — CRM Rohtext (Quelle)
- `source/AID-*_1.0.0.0.pdf` — Convert-PDF
- `neu/cv/AID-*.pdf` — Pipeline-Ziel
- `extracted/AID-*.txt` — Pipeline-Extrakt
- `extracted/AID-*.pre_json.json` — RAM pre_json (vor DB)
- `extracted/AID-*.db_snapshot.json` — DB nach save (Vergleich)

| Status | Letter/Dir | neu/cv PDF | Quelle TXT |
|--------|------------|------------|------------|
| OK | `bbb/behling_karsten` | AID-kb_2.5.3.0.pdf | ja |
| OK | `ggg/glas_oliver_fritz` | AID-og_2.3.2.0.pdf | ja |
