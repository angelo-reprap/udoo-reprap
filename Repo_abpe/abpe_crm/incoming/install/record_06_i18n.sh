#!/bin/bash
# ============================================================
# record_06_i18n.sh
# Übersetzt die fehlenden Softphone-i18n-Keys (de_phone.json)
# in die 11 Zielsprachen — nutzt die bestehende _deepseek_translate.
# - nur DIFFERENZ (fehlende Keys), bestehende bleiben unangetastet
# - Platzhalter/HTML-Schutz mit Fallback auf DE bei Bruch
# - pro Sprache einzeln schreiben + validieren (Key-Count 368)
# ============================================================
set -e
cd /opt/abpe/backend
I18N=apps/abpe_crm/static/softphone-electron/renderer/i18n

echo "=== [1/3] Backups aller 11 Ziel-Dateien ==="
for L in en fr es it pl ru ar zh pt ko ja; do
  python3 Archiv/backup_restore.py -save "$I18N/${L}_phone.json" -m "i18n: vor record-keys" >/dev/null
done
echo "  11 Backups ok"

echo "=== [2/3] Übersetzung (Differenz de -> 11 Sprachen) ==="
python3 - << 'PYEOF'
import sys, json, re, os
sys.path.insert(0, '/opt/abpe/backend/apps/abpe_crm/bin')
from i18n_translator import _deepseek_translate, _load_api_key

I18N = '/opt/abpe/backend/apps/abpe_crm/static/softphone-electron/renderer/i18n'
TARGETS = ['en','fr','es','it','pl','ru','ar','zh','pt','ko','ja']

api_key = _load_api_key()
if not api_key:
    print("❌ Kein API-Key — Abbruch.")
    sys.exit(1)

de = json.load(open(f'{I18N}/de_phone.json', encoding='utf-8'))
print(f"  Quelle de_phone.json: {len(de)} Keys")

# Platzhalter aus einem Text extrahieren: {xxx} und HTML-Tags <...>
def placeholders(text):
    if not isinstance(text, str): return set()
    ph = set(re.findall(r'\{[^}]+\}', text))
    tags = set(re.findall(r'<[^>]+>', text))
    return ph | tags

results = {}
for L in TARGETS:
    path = f'{I18N}/{L}_phone.json'
    try:
        tgt = json.load(open(path, encoding='utf-8'))
    except Exception as e:
        print(f"  [{L}] ❌ Laden fehlgeschlagen: {e}")
        results[L] = 'load-error'
        continue

    missing = {k: v for k, v in de.items() if k not in tgt}
    if not missing:
        print(f"  [{L}] keine fehlenden Keys — übersprungen.")
        results[L] = 'complete'
        continue

    print(f"  [{L}] {len(missing)} fehlende Keys -> Deepseek...", flush=True)
    translated = _deepseek_translate(missing, 'de', L, api_key)
    if not isinstance(translated, dict):
        print(f"  [{L}] ❌ Übersetzung fehlgeschlagen (kein dict zurück).")
        results[L] = 'translate-error'
        continue

    # Platzhalter-Schutz + Key-Vollständigkeit
    fixed, broken = 0, 0
    out = {}
    for k, de_val in missing.items():
        tv = translated.get(k)
        if tv is None or not isinstance(tv, str):
            out[k] = de_val; fixed += 1; continue
        if placeholders(de_val) != placeholders(tv):
            out[k] = de_val; broken += 1  # Fallback DE bei Platzhalter-Bruch
        else:
            out[k] = tv

    # Merge: bestehende zuerst, dann die neuen (Reihenfolge stabil)
    merged = dict(tgt)
    merged.update(out)

    # Validierung: Key-Count muss == de sein
    if len(merged) != len(de):
        print(f"  [{L}] ⚠️  Key-Count {len(merged)} != de {len(de)} — trotzdem geschrieben.")

    json.dump(merged, open(path, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    # Reload-Validierung
    json.load(open(path, encoding='utf-8'))
    note = []
    if fixed:  note.append(f"{fixed} leer->DE")
    if broken: note.append(f"{broken} Platzhalter-Fallback->DE")
    print(f"  [{L}] ✓ {len(merged)} Keys" + (f" ({', '.join(note)})" if note else ""), flush=True)
    results[L] = 'ok'

print("\n  === Ergebnis ===")
for L in TARGETS:
    print(f"    {L}: {results.get(L)}")
ok = sum(1 for v in results.values() if v in ('ok','complete'))
print(f"  {ok}/{len(TARGETS)} Sprachen erfolgreich.")
PYEOF

echo "=== [3/3] JSON-Validierung aller Dateien + Key-Count ==="
for L in de en fr es it pl ru ar zh pt ko ja; do
  n=$(python3 -c "import json; print(len(json.load(open('$I18N/${L}_phone.json'))))" 2>/dev/null)
  echo "  ${L}_phone.json: $n Keys"
done

echo ""
echo "============================================================"
echo "✅ record_06 i18n fertig."
echo "Stichprobe (Recording-Keys auf 3 Sprachen):"
echo "  python3 -c \"import json; [print(L, json.load(open('$I18N/'+L+'_phone.json')).get('rec_subject_title','--')) for L in ['en','fr','zh']]\""
echo "============================================================"

