#!/bin/bash
# ============================================================
# patch_record_05_html.sh
# Ersetzt die heuristische app.html-Einfügung in record_05
# durch eine saubere, anker-präzise Version.
# ============================================================
set -e
cd /opt/abpe/backend/apps/abpe_crm/install

TARGET=record_05_betreff_owner_dauer.sh
[ -f "$TARGET" ] || { echo "FEHLER: $TARGET nicht gefunden"; exit 1; }

cp "$TARGET" "${TARGET}.bak_html"
echo "  Backup: ${TARGET}.bak_html"

python3 - << 'PYEOF'
p = 'record_05_betreff_owner_dauer.sh'
s = open(p, encoding='utf-8').read()

# Den heuristischen app.html-Block finden (von "p = 'renderer/app.html'" bis zum zugehörigen PYEOF)
start_marker = "python3 - << 'PYEOF'\np = 'renderer/app.html'"
if start_marker not in s:
    # evtl. ohne doppelten Zeilenumbruch
    start_marker = "p = 'renderer/app.html'"
assert start_marker in s, "app.html-Block nicht gefunden"

idx_p = s.find("p = 'renderer/app.html'")
# Beginn des umschließenden heredocs (das 'python3 - << ...' davor)
idx_start = s.rfind("python3 - << 'PYEOF'", 0, idx_p)
assert idx_start != -1, "heredoc-Start nicht gefunden"
# Ende = nächstes 'PYEOF' nach idx_p, gefolgt vom Zeilenende
idx_pyeof = s.find("\nPYEOF", idx_p)
assert idx_pyeof != -1, "heredoc-Ende nicht gefunden"
idx_end = idx_pyeof + len("\nPYEOF")

new_block = r'''python3 - << 'PYEOF'
p = 'renderer/app.html'
s = open(p, encoding='utf-8').read()
if 'cfgOwnerSearch' in s:
    print("  HTML schon da - uebersprungen.")
else:
    anchor = """          </div>
        </div>
        <!-- ===== GRUPPE 4: SYSTEM ===== -->"""
    owner_block = """          </div>
        </div>
        <div class="settings-section-hdr" onclick="toggleAcc(this)">
          <i class="bi bi-person-vcard settings-section-icon"></i>
          <span class="settings-section-title" data-i18n="rec_owner_label">Mein CRM-Kontakt (Besitzer)</span>
          <span id="cfgOwnerLabel" style="margin-left:auto;margin-right:8px;font-size:12px;color:var(--muted)">nicht gesetzt</span>
          <span class="settings-section-arrow">&#9654;</span>
        </div>
        <div class="settings-section-body">
          <div class="settings-hint" data-i18n="rec_owner_hint">Aufnahmen ohne Zuordnung gehoeren diesem Kontakt.</div>
          <div class="settings-row" style="flex-direction:column;align-items:stretch;gap:6px">
            <input id="cfgOwnerSearch" type="text" placeholder="Kontakt suchen..."
              oninput="ownerContactSearch(this.value)"
              style="width:100%;box-sizing:border-box;padding:8px;font-size:13px;border:1px solid var(--border);border-radius:6px;background:var(--card);color:var(--text)">
            <div id="cfgOwnerResults" style="max-height:160px;overflow:auto;border-radius:6px"></div>
          </div>
        </div>
        <!-- ===== GRUPPE 4: SYSTEM ===== -->"""
    assert s.count(anchor) == 1, f"HTML-Anker {s.count(anchor)}x"
    s = s.replace(anchor, owner_block)
    open(p, 'w', encoding='utf-8').write(s)
    print("  Besitzer-Akkordeon sauber nach ext_names eingefuegt.")
PYEOF'''

s = s[:idx_start] + new_block + s[idx_end:]
open(p, 'w', encoding='utf-8').write(s)
print("  record_05: app.html-Block durch saubere Version ersetzt.")
PYEOF

echo ""
echo "  Verifikation: bash-Syntax des gepatchten Skripts"
bash -n "$TARGET" && echo "  ✅ Syntax OK"
echo ""
echo "  Patch fertig. Jetzt:"
echo "    chmod +x apps/abpe_crm/install/$TARGET"
echo "    bash apps/abpe_crm/install/$TARGET"

