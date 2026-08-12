#!/bin/bash
# ============================================================
# patch_record_05_html_fix.sh
# Fügt das Besitzer-Akkordeon in app.html ein — mit echtem Anker
# (inkl. Leerzeile vor GRUPPE 4, die der erste Versuch verfehlte).
# ============================================================
set -e
cd /opt/abpe/backend
SP=apps/abpe_crm/static/softphone-electron

echo "=== Backup app.html ==="
python3 Archiv/backup_restore.py -save "$SP/renderer/app.html" -m "html-fix: besitzer-feld" >/dev/null
echo "  ok"

cd "$SP"
python3 - << 'PYEOF'
p = 'renderer/app.html'
s = open(p, encoding='utf-8').read()
if 'cfgOwnerSearch' in s:
    print("  schon vorhanden — übersprungen.")
else:
    # Echter Anker: schließendes </div></div> + LEERZEILE + GRUPPE 4 Kommentar
    anchor = "          </div>\n        </div>\n\n        <!-- ===== GRUPPE 4: SYSTEM ===== -->"
    owner_block = """          </div>
        </div>

        <div class="settings-section-hdr" onclick="toggleAcc(this)">
          <i class="bi bi-person-vcard settings-section-icon"></i>
          <span class="settings-section-title" data-i18n="rec_owner_label">Mein CRM-Kontakt (Besitzer)</span>
          <span id="cfgOwnerLabel" style="margin-left:auto;margin-right:8px;font-size:12px;color:var(--muted)">nicht gesetzt</span>
          <span class="settings-section-arrow">&#9654;</span>
        </div>
        <div class="settings-section-body">
          <div class="settings-hint" data-i18n="rec_owner_hint">Aufnahmen ohne Zuordnung gehören diesem Kontakt.</div>
          <div class="settings-row" style="flex-direction:column;align-items:stretch;gap:6px">
            <input id="cfgOwnerSearch" type="text" placeholder="Kontakt suchen..."
              oninput="ownerContactSearch(this.value)"
              style="width:100%;box-sizing:border-box;padding:8px;font-size:13px;border:1px solid var(--border);border-radius:6px;background:var(--card);color:var(--text)">
            <div id="cfgOwnerResults" style="max-height:160px;overflow:auto;border-radius:6px"></div>
          </div>
        </div>

        <!-- ===== GRUPPE 4: SYSTEM ===== -->"""
    cnt = s.count(anchor)
    assert cnt == 1, f"Anker {cnt}x (erwartet 1)"
    s = s.replace(anchor, owner_block)
    open(p, 'w', encoding='utf-8').write(s)
    print("  Besitzer-Akkordeon eingefügt.")
PYEOF

echo "=== div-Balance-Check (öffnende vs schließende divs) ==="
python3 - << 'PYEOF'
s = open('renderer/app.html', encoding='utf-8').read()
o = s.count('<div'); c = s.count('</div>')
print(f"  <div: {o} | </div>: {c} | Differenz: {o-c}")
PYEOF

echo "=== Besitzer-Elemente da? ==="
grep -c "cfgOwnerSearch\|cfgOwnerLabel\|cfgOwnerResults" renderer/app.html

echo ""
echo "✅ HTML-Fix fertig. div-Differenz sollte unverändert sein (Block ist balanciert)."

