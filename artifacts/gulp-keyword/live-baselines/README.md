# Live-Baselines vor Keyword-/AID-PDF-Merge

- `main_labeler.py.before-v1.3-keywords` — vor First-Word-Ergänzung
- `section_label_keywords.py.v1.3-final` — Keyword-Sammlung
- `aid_regex_extractor.py.before-gulp-aid-pdf` — vor Gulp-Personal/Projekttätigkeiten-Alias
- `from-ucs5-*` — bei `SAFE-gulp-keywords.sh prepare`

Pipeline-Logik:
- Echte AID/abcona-PDFs → **aid_regex_extractor** (Fast-Path, ≥3 Signale)
- `main_labeler` läuft immer mit, ist aber für AID nur Fallback/Rest
- Gulp-Preview-PDF wird jetzt im AID-Layout erzeugt (Signale + Format A), damit der Fast-Path greift
