#!/bin/bash
# ============================================================
# check_i18n.sh — Prüfskript für Softphone-i18n-Übersetzungen
# Prüft gegen de_phone.json (Referenz):
#  1. JSON valide?
#  2. Key-Count == Referenz (368)?
#  3. Fehlende / überzählige Keys?
#  4. Platzhalter-Integrität ({x}, <tags>) pro Key
#  5. Leere Werte / versehentlich DE geblieben (Heuristik)
#  6. Stichprobe Recording-Keys zum Sichten
# Nur-Lesen, ändert NICHTS.
# ============================================================
cd /opt/abpe/backend
I18N=apps/abpe_crm/static/softphone-electron/renderer/i18n

python3 - << 'PYEOF'
import json, re, os

I18N = '/opt/abpe/backend/apps/abpe_crm/static/softphone-electron/renderer/i18n'
TARGETS = ['en','fr','es','it','pl','ru','ar','zh','pt','ko','ja']

def placeholders(text):
    if not isinstance(text, str): return set()
    return set(re.findall(r'\{[^}]+\}', text)) | set(re.findall(r'<[^>]+>', text))

# Referenz laden
try:
    de = json.load(open(f'{I18N}/de_phone.json', encoding='utf-8'))
except Exception as e:
    print(f"❌ de_phone.json nicht ladbar: {e}"); raise SystemExit(1)
ref_count = len(de)
print(f"Referenz de_phone.json: {ref_count} Keys\n")
print(f"{'Lang':<5}{'JSON':<7}{'Keys':<12}{'Fehlt':<7}{'Extra':<7}{'PH-Bruch':<9}{'DE-Rest':<8}{'Status'}")
print("-" * 70)

summary = {}
for L in TARGETS:
    path = f'{I18N}/{L}_phone.json'
    if not os.path.exists(path):
        print(f"{L:<5}{'FEHLT':<7}"); summary[L]='missing'; continue
    # 1. JSON valide?
    try:
        d = json.load(open(path, encoding='utf-8'))
        json_ok = 'OK'
    except Exception as e:
        print(f"{L:<5}{'KAPUTT':<7}  {e}"); summary[L]='broken-json'; continue

    # 2/3. Keys
    cnt = len(d)
    missing = [k for k in de if k not in d]
    extra   = [k for k in d if k not in de]

    # 4. Platzhalter-Integrität (nur für gemeinsame Keys)
    ph_breaks = []
    for k in de:
        if k in d and placeholders(de[k]) != placeholders(d[k]):
            ph_breaks.append(k)

    # 5. DE-Rest-Heuristik: Wert exakt gleich wie DE (nur bei längeren Texten verdächtig,
    #    kurze Wörter wie "OK", "PIN", Eigennamen sind oft identisch -> erst ab 4 Wörtern werten)
    de_rest = []
    for k in de:
        if k in d and isinstance(d[k], str) and isinstance(de[k], str):
            if d[k] == de[k] and len(de[k].split()) >= 4:
                de_rest.append(k)

    cnt_str = f"{cnt}" + ("" if cnt == ref_count else f"(≠{ref_count})")
    status = "✓ ok"
    if missing or extra: status = "⚠ keys"
    if ph_breaks:        status = "⚠ PH"
    print(f"{L:<5}{json_ok:<7}{cnt_str:<12}{len(missing):<7}{len(extra):<7}{len(ph_breaks):<9}{len(de_rest):<8}{status}")

    summary[L] = {
        'missing': missing, 'extra': extra,
        'ph_breaks': ph_breaks, 'de_rest': de_rest, 'count': cnt,
    }

# Details für Problemfälle
print("\n=== DETAILS (nur bei Auffälligkeiten) ===")
clean = True
for L in TARGETS:
    s = summary.get(L)
    if not isinstance(s, dict): 
        print(f"  {L}: {s}"); clean = False; continue
    issues = []
    if s['missing']:   issues.append(f"fehlende Keys: {s['missing'][:5]}{'...' if len(s['missing'])>5 else ''}")
    if s['extra']:     issues.append(f"überzählige: {s['extra'][:5]}")
    if s['ph_breaks']: issues.append(f"Platzhalter-Bruch: {s['ph_breaks'][:8]}")
    if s['de_rest']:   issues.append(f"evtl. DE geblieben: {s['de_rest'][:8]}")
    if issues:
        clean = False
        print(f"  [{L}]")
        for i in issues: print(f"      - {i}")
if clean:
    print("  Keine Auffälligkeiten — alle 11 Sprachen sauber. ✓")

# Stichprobe: ein paar Recording-Keys zum Sichten
print("\n=== STICHPROBE (Recording-Keys) ===")
sample_keys = ['rec_subject_title', 'rec_assign_me', 'rec_owner_label', 'kontakt_acc_aufnahmen', 'record_synced']
for k in sample_keys:
    print(f"\n  '{k}':")
    print(f"      de: {de.get(k,'--')}")
    for L in ['en','fr','es','zh','ru','ar']:
        try:
            v = json.load(open(f'{I18N}/{L}_phone.json', encoding='utf-8')).get(k,'--')
            print(f"      {L}: {v}")
        except: pass
PYEOF

