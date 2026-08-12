#!/usr/bin/env bash
# fix_all_css_vars.sh — ALLE hardcodierten Farben → CSS-Variablen
# Nach diesem Script: kein einziges hardcodiertes CSS in HTML/JS
# Aufruf: bash apps/abpe_crm/install/fix_all_css_vars.sh
set -euo pipefail
GREEN='\033[0;31m'; BLUE='\033[0;34m'; NC='\033[0m'
ok()   { echo -e "\033[0;32m✓${NC} $*"; }
info() { echo -e "${BLUE}▶${NC}  $*"; }

BASE="/opt/abpe/backend"
APP="apps/abpe_crm"
CSS="${APP}/static/abpe_crm/softphone/css/softphone.css"
JS6="${APP}/static/abpe_crm/softphone/js/6_sp-core.js"
JS8="${APP}/static/abpe_crm/softphone/js/8_sp-status.js"
JS9="${APP}/static/abpe_crm/softphone/js/9_sp-transfer.js"
JS10="${APP}/static/abpe_crm/softphone/js/10_sp-fop.js"
TMPL="${APP}/templates/abpe_crm/softphone/softphone.html"

[[ "$(pwd)" == "$BASE" ]] || { echo "Falsches Verzeichnis"; exit 1; }

info "Backups"
for f in "$CSS" "$JS6" "$JS8" "$JS9" "$JS10" "$TMPL"; do
    python3 Archiv/backup_restore.py -save "$f" -m "vor css-vars fix" || exit 1
done
ok "Backups OK"
echo

# ══════════════════════════════════════════════════════════
# SCHRITT 1: CSS-Variablen in softphone.css definieren
# ══════════════════════════════════════════════════════════
info "Schritt 1/6 — CSS-Variablen in softphone.css"

cat >> "$CSS" << 'CSSEOF'

/* ══════════════════════════════════════════════════════════
   Semantische Status-Variablen — Light Mode
   ══════════════════════════════════════════════════════════ */
:root {
    /* DND */
    --status-dnd-border:  #991b1b;
    --status-dnd-bg:      #fff1f2;
    --status-dnd-color:   #991b1b;
    /* Voicemail */
    --status-vm-border:   #b45309;
    --status-vm-bg:       #fffbeb;
    --status-vm-color:    #92400e;
    /* Rufweiterleitung */
    --status-fwd-border:  #1e40af;
    --status-fwd-bg:      #eff6ff;
    --status-fwd-color:   #1e3a8a;
    /* Transfer Erfolg (grün) */
    --status-ok-bg:       #dcfce7;
    --status-ok-border:   #86efac;
    --status-ok-color:    #14532d;
    /* Transfer Confirm (amber) */
    --status-warn-bg:     #fef3c7;
    --status-warn-border: #fcd34d;
    --status-warn-color:  #92400e;
    /* Extension Status */
    --ext-free-bg:        #dcfce7;
    --ext-free-color:     #14532d;
    --ext-free-dot:       #22c55e;
    --ext-busy-bg:        #fef3c7;
    --ext-busy-color:     #92400e;
    --ext-busy-dot:       #ef4444;
    --ext-dnd-bg:         #fee2e2;
    --ext-dnd-color:      #7f1d1d;
    --ext-dnd-dot:        #f59e0b;
    --ext-offline-bg:     #f3f4f6;
    --ext-offline-color:  #6b7280;
    --ext-offline-dot:    #9ca3af;
    /* Aktions-Buttons grün (Abholen, Konf) */
    --action-ok-border:   #86efac;
    --action-ok-bg:       #f0fdf4;
    --action-ok-color:    #14532d;
    /* Aktions-Buttons blau (Park) */
    --action-info-border: #7dd3fc;
    --action-info-bg:     #e0f2fe;
    --action-info-color:  #0c4a6e;
    /* DND-Badge im FOP */
    --badge-dnd-bg:       #fee2e2;
    --badge-dnd-color:    #7f1d1d;
    /* Dots neutral */
    --dot-inactive:       #d1d5db;
    --dot-offline:        #9ca3af;
    /* Avatar (eingehender Anruf) */
    --avatar-inc-bg:      #d1fae5;
    --avatar-inc-color:   #065f46;
    /* Avatar (CDR Zuletzt) */
    --avatar-cdr-bg:      #dbeafe;
    --avatar-cdr-color:   #1e40af;
    /* Pin-Button highlight */
    --pin-active-color:   #fbbf24;
    /* Status-Text (Header) */
    --header-status-text: #8ba8c8;
}

/* ── Dark Mode Overrides ─────────────────────────────────── */
[data-theme="dark"] {
    --status-dnd-border:  #7f1d1d;
    --status-dnd-bg:      #2a0a0a;
    --status-dnd-color:   #fca5a5;
    --status-vm-border:   #92400e;
    --status-vm-bg:       #3a2800;
    --status-vm-color:    #fcd34d;
    --status-fwd-border:  #1e3a8a;
    --status-fwd-bg:      #0a1f3a;
    --status-fwd-color:   #93c5fd;
    --status-ok-bg:       #052e16;
    --status-ok-border:   #166534;
    --status-ok-color:    #86efac;
    --status-warn-bg:     #3a2800;
    --status-warn-border: #92400e;
    --status-warn-color:  #fcd34d;
    --ext-free-bg:        #052e16;
    --ext-free-color:     #86efac;
    --ext-busy-bg:        #3a2800;
    --ext-busy-color:     #fcd34d;
    --ext-dnd-bg:         #2a0a0a;
    --ext-dnd-color:      #fca5a5;
    --ext-offline-bg:     #2a2a2a;
    --ext-offline-color:  #a0a0a0;
    --action-ok-border:   #166534;
    --action-ok-bg:       #052e16;
    --action-ok-color:    #86efac;
    --action-info-border: #1e40af;
    --action-info-bg:     #0a1f3a;
    --action-info-color:  #93c5fd;
    --badge-dnd-bg:       #2a0a0a;
    --badge-dnd-color:    #fca5a5;
    --dot-inactive:       #444444;
    --dot-offline:        #555555;
    --avatar-inc-bg:      #052e16;
    --avatar-inc-color:   #86efac;
    --avatar-cdr-bg:      #0a1f3a;
    --avatar-cdr-color:   #93c5fd;
    --header-status-text: #6b8cb0;
}
CSSEOF
ok "CSS-Variablen definiert"
echo

# ══════════════════════════════════════════════════════════
# SCHRITT 2: 6_sp-core.js
# ══════════════════════════════════════════════════════════
info "Schritt 2/6 — 6_sp-core.js"

python3 << 'PYEOF'
with open("apps/abpe_crm/static/abpe_crm/softphone/js/6_sp-core.js", "r") as f:
    c = f.read()

# Status-Dot: unregistriert grau
c = c.replace(
    "_setStatus('Nicht registriert', '#9ca3af')",
    "_setStatus('Nicht registriert', 'var(--dot-offline)')"
)

# Pin-Kontakt Hover in Suche: #163258/#dbeafe
c = c.replace(
    "onmouseover=\"this.style.opacity='1';this.style.color='#163258';this.style.background='#dbeafe'\"",
    "onmouseover=\"this.style.opacity='1';this.style.color='var(--panel-header-bg,#163258)';this.style.background='var(--avatar-cdr-bg)'\""
)

# CDR Avatar: #dbeafe/#1e40af
c = c.replace(
    "'<div style=\"width:24px;height:24px;border-radius:50%;background:#dbeafe;color:#1e40af;display:flex;align-items:center;justify-content:center;font-size:9px;font-weight:600;flex-shrink:0\">'",
    "'<div style=\"width:24px;height:24px;border-radius:50%;background:var(--avatar-cdr-bg);color:var(--avatar-cdr-color);display:flex;align-items:center;justify-content:center;font-size:9px;font-weight:600;flex-shrink:0\">'"
)

with open("apps/abpe_crm/static/abpe_crm/softphone/js/6_sp-core.js", "w") as f:
    f.write(c)
print("✓  6_sp-core.js")
PYEOF
node --check "$JS6" && ok "6_sp-core.js Syntax OK" || { echo "FEHLER"; exit 1; }
echo

# ══════════════════════════════════════════════════════════
# SCHRITT 3: 8_sp-status.js — Status-Bar cssText
# ══════════════════════════════════════════════════════════
info "Schritt 3/6 — 8_sp-status.js"

python3 << 'PYEOF'
with open("apps/abpe_crm/static/abpe_crm/softphone/js/8_sp-status.js", "r") as f:
    c = f.read()

# DND Status-Bar
c = c.replace(
    "bar.style.cssText = 'display:block;padding:4px 8px;border-left:3px solid #991b1b;font-size:10px;font-weight:500;color:#991b1b;margin:0 0 2px 0';",
    "bar.className = 'sp-status-bar-dnd'; bar.style.cssText = 'display:block;padding:4px 8px;border-left:3px solid var(--status-dnd-border);font-size:10px;font-weight:500;color:var(--status-dnd-color);margin:0 0 2px 0';"
)
# FWD Status-Bar
c = c.replace(
    "bar.style.cssText = 'display:block;padding:4px 8px;border-left:3px solid #1e40af;font-size:10px;font-weight:500;color:#1e3a8a;margin:0 0 2px 0';",
    "bar.style.cssText = 'display:block;padding:4px 8px;border-left:3px solid var(--status-fwd-border);font-size:10px;font-weight:500;color:var(--status-fwd-color);margin:0 0 2px 0';"
)
# VM Status-Bar
c = c.replace(
    "bar.style.cssText = 'display:block;padding:4px 8px;border-left:3px solid #b45309;font-size:10px;font-weight:500;color:#92400e;margin:0 0 2px 0';",
    "bar.style.cssText = 'display:block;padding:4px 8px;border-left:3px solid var(--status-vm-border);font-size:10px;font-weight:500;color:var(--status-vm-color);margin:0 0 2px 0';"
)

with open("apps/abpe_crm/static/abpe_crm/softphone/js/8_sp-status.js", "w") as f:
    f.write(c)
print("✓  8_sp-status.js")
PYEOF
node --check "$JS8" && ok "8_sp-status.js Syntax OK" || { echo "FEHLER"; exit 1; }
echo

# ══════════════════════════════════════════════════════════
# SCHRITT 4: 9_sp-transfer.js
# ══════════════════════════════════════════════════════════
info "Schritt 4/6 — 9_sp-transfer.js"

python3 << 'PYEOF'
with open("apps/abpe_crm/static/abpe_crm/softphone/js/9_sp-transfer.js", "r") as f:
    c = f.read()

# border-top #1e4080
c = c.replace(
    "'border-top:0.5px solid #1e4080\" '",
    "'border-top:0.5px solid var(--border-color)\" '"
)

# tBtn #163258 (Suche Einzelnummer)
c = c.replace(
    "'style=\"font-size:9px;padding:1px 6px;border:none;border-radius:3px;background:#163258;color:#fff;cursor:pointer\">&#8594;</button>'",
    "'class=\"sp-panel-hdr\" style=\"font-size:9px;padding:1px 6px;border:none;border-radius:3px;cursor:pointer\">&#8594;</button>'"
)
# tBtn #163258 (Suche Mehrfachnummer)
c = c.replace(
    "'style=\"font-size:9px;padding:1px 5px;border:none;border-radius:3px;background:#163258;color:#fff;cursor:pointer\">&#8594;</button>'",
    "'class=\"sp-panel-hdr\" style=\"font-size:9px;padding:1px 5px;border:none;border-radius:3px;cursor:pointer\">&#8594;</button>'"
)

# Transfer Erfolg (grün)
c = c.replace(
    "box.style.cssText = 'display:block;margin:0 0 4px 0;border-radius:6px;overflow:hidden;border:0.5px solid #86efac;background:#dcfce7';",
    "box.style.cssText = 'display:block;margin:0 0 4px 0;border-radius:6px;overflow:hidden;border:0.5px solid var(--status-ok-border);background:var(--status-ok-bg)';"
)
c = c.replace(
    "'<div style=\"padding:8px;text-align:center;font-size:11px;font-weight:500;color:#14532d\">'",
    "'<div style=\"padding:8px;text-align:center;font-size:11px;font-weight:500;color:var(--status-ok-color)\">'"
)

# Transfer Confirm (amber) — _confirmTransfer
c = c.replace(
    "box.style.cssText = 'display:block;margin:0 0 4px 0;border-radius:6px;overflow:hidden;border:0.5px solid #fcd34d;background:#fef3c7';\n    box.innerHTML = '<div style=\"padding:5px 8px;font-size:10px;color:#92400e;font-weight:500;border-bottom:0.5px solid #fcd34d\">'",
    "box.style.cssText = 'display:block;margin:0 0 4px 0;border-radius:6px;overflow:hidden;border:0.5px solid var(--status-warn-border);background:var(--status-warn-bg)';\n    box.innerHTML = '<div style=\"padding:5px 8px;font-size:10px;color:var(--status-warn-color);font-weight:500;border-bottom:0.5px solid var(--status-warn-border)\">'"
)
# Direkt-Button #163258
c = c.replace(
    "'style=\"flex:1;padding:5px 4px;background:#163258;color:#fff;border:none;border-radius:5px;font-size:10px;cursor:pointer\">&#8594; Direkt</button>'",
    "'class=\"sp-panel-hdr\" style=\"flex:1;padding:5px 4px;border:none;border-radius:5px;font-size:10px;cursor:pointer\">&#8594; Direkt</button>'"
)
# Schliessen-Button amber
c = c.replace(
    "'style=\"padding:5px 7px;background:var(--bg-secondary,#f3f4f6);border:0.5px solid #fcd34d;border-radius:5px;font-size:10px;cursor:pointer;color:#92400e\">&#10005;</button>'",
    "'style=\"padding:5px 7px;background:var(--bg-secondary);border:0.5px solid var(--status-warn-border);border-radius:5px;font-size:10px;cursor:pointer;color:var(--status-warn-color)\">&#10005;</button>'"
)

# Transfer Ankündigung (amber) — _doAnnounceTransfer
c = c.replace(
    "box.style.cssText = 'display:block;margin:0 0 4px 0;border-radius:6px;overflow:hidden;border:0.5px solid #fcd34d;background:#fef3c7';\n        box.innerHTML = '<div style=\"padding:5px 8px;font-size:10px;color:#92400e;font-weight:500;border-bottom:0.5px solid #fcd34d\">'",
    "box.style.cssText = 'display:block;margin:0 0 4px 0;border-radius:6px;overflow:hidden;border:0.5px solid var(--status-warn-border);background:var(--status-warn-bg)';\n        box.innerHTML = '<div style=\"padding:5px 8px;font-size:10px;color:var(--status-warn-color);font-weight:500;border-bottom:0.5px solid var(--status-warn-border)\">'"
)
# Transferieren-Button #163258
c = c.replace(
    "'style=\"flex:1;padding:5px 4px;background:#163258;color:#fff;border:none;border-radius:5px;font-size:10px;cursor:pointer\">&#8594; Transferieren</button>'",
    "'class=\"sp-panel-hdr\" style=\"flex:1;padding:5px 4px;border:none;border-radius:5px;font-size:10px;cursor:pointer\">&#8594; Transferieren</button>'"
)

# Kontaktsuche Transfer-Button #163258
c = c.replace(
    "'<button onclick=\"Softphone._confirmTransfer(\\'' + num + '\\')\" style=\"font-size:9px;padding:1px 6px;border:none;border-radius:3px;background:#163258;color:#fff;cursor:pointer\">&#8594;</button>'",
    "'<button onclick=\"Softphone._confirmTransfer(\\'' + num + '\\')\" class=\"sp-panel-hdr\" style=\"font-size:9px;padding:1px 6px;border:none;border-radius:3px;cursor:pointer\">&#8594;</button>'"
)

with open("apps/abpe_crm/static/abpe_crm/softphone/js/9_sp-transfer.js", "w") as f:
    f.write(c)
print("✓  9_sp-transfer.js")
PYEOF
node --check "$JS9" && ok "9_sp-transfer.js Syntax OK" || { echo "FEHLER"; exit 1; }
echo

# ══════════════════════════════════════════════════════════
# SCHRITT 5: 10_sp-fop.js
# ══════════════════════════════════════════════════════════
info "Schritt 5/6 — 10_sp-fop.js"

python3 << 'PYEOF'
with open("apps/abpe_crm/static/abpe_crm/softphone/js/10_sp-fop.js", "r") as f:
    c = f.read()

# Extension-Status colors → CSS-Variablen
c = c.replace(
    """    var colors = {
        free:    { bg: '#dcfce7', color: '#14532d', label: 'frei',    dot: '#22c55e' },
        busy:    { bg: '#fef3c7', color: '#92400e', label: 'besetzt', dot: '#ef4444' },
        dnd:     { bg: '#fee2e2', color: '#7f1d1d', label: 'DND',     dot: '#f59e0b' },
        offline: { bg: '#f3f4f6', color: '#6b7280', label: 'offline', dot: '#9ca3af' },
        unknown: { bg: '#f3f4f6', color: '#6b7280', label: '?',       dot: '#9ca3af' },
    };""",
    """    var colors = {
        free:    { bg: 'var(--ext-free-bg)',    color: 'var(--ext-free-color)',    label: 'frei',    dot: 'var(--ext-free-dot,#22c55e)' },
        busy:    { bg: 'var(--ext-busy-bg)',    color: 'var(--ext-busy-color)',    label: 'besetzt', dot: 'var(--ext-busy-dot,#ef4444)' },
        dnd:     { bg: 'var(--ext-dnd-bg)',     color: 'var(--ext-dnd-color)',     label: 'DND',     dot: 'var(--ext-dnd-dot,#f59e0b)' },
        offline: { bg: 'var(--ext-offline-bg)', color: 'var(--ext-offline-color)', label: 'offline', dot: 'var(--ext-offline-dot,#9ca3af)' },
        unknown: { bg: 'var(--ext-offline-bg)', color: 'var(--ext-offline-color)', label: '?',       dot: 'var(--ext-offline-dot,#9ca3af)' },
    };"""
)

# border-top #1e4080 in secHeader
c = c.replace(
    "';border-top:0.5px solid #1e4080;",
    "';border-top:0.5px solid var(--border-color);"
)

# DND-Toggle Button im FOP (mein Extension)
c = c.replace(
    "'style=\"font-size:10px;padding:2px 6px;border:0.5px solid #fca5a5;border-radius:3px;cursor:pointer;background:#fee2e2;color:#7f1d1d\">'",
    "'style=\"font-size:10px;padding:2px 6px;border:0.5px solid var(--status-dnd-border);border-radius:3px;cursor:pointer;background:var(--status-dnd-bg);color:var(--status-dnd-color)\">'"
)

# Abholen-Button (grün)
c = c.replace(
    "'style=\"font-size:10px;padding:1px 5px;border:0.5px solid #86efac;border-radius:3px;cursor:pointer;background:#f0fdf4;color:#14532d\">&#9742; Abholen</span>'",
    "'style=\"font-size:10px;padding:1px 5px;border:0.5px solid var(--action-ok-border);border-radius:3px;cursor:pointer;background:var(--action-ok-bg);color:var(--action-ok-color)\">&#9742; Abholen</span>'"
)

# Leerer Slot Dot: #d1d5db
c = c.replace(
    "'<span style=\"width:7px;height:7px;border-radius:50%;background:#d1d5db;flex-shrink:0\"></span>'",
    "'<span style=\"width:7px;height:7px;border-radius:50%;background:var(--dot-inactive);flex-shrink:0\"></span>'"
)

# Park-Button (blau)
c = c.replace(
    "'style=\"font-size:10px;padding:1px 5px;border:0.5px solid #7dd3fc;border-radius:3px;cursor:pointer;background:#e0f2fe;color:#0c4a6e\">&#8659; Park</span>'",
    "'style=\"font-size:10px;padding:1px 5px;border:0.5px solid var(--action-info-border);border-radius:3px;cursor:pointer;background:var(--action-info-bg);color:var(--action-info-color)\">&#8659; Park</span>'"
)

# Konferenz Dot: count > 0 ? #22c55e : #d1d5db
c = c.replace(
    "';background:' + (count > 0 ? '#22c55e' : '#d1d5db') + ';flex-shrink:0\"></span>'",
    "';background:' + (count > 0 ? 'var(--ext-free-dot,#22c55e)' : 'var(--dot-inactive)') + ';flex-shrink:0\"></span>'"
)

# Konf-Button (grün)
c = c.replace(
    "'style=\"font-size:10px;padding:1px 5px;border:0.5px solid #86efac;border-radius:3px;cursor:pointer;background:#f0fdf4;color:#14532d\">&#8594; Konf</span>'",
    "'style=\"font-size:10px;padding:1px 5px;border:0.5px solid var(--action-ok-border);border-radius:3px;cursor:pointer;background:var(--action-ok-bg);color:var(--action-ok-color)\">&#8594; Konf</span>'"
)

# VM Badge (rot)
c = c.replace(
    "'<span style=\"background:#fee2e2;color:#7f1d1d;padding:1px 5px;border-radius:3px;font-size:10px;font-weight:600;margin-right:4px\">' + count + ' neu</span>'",
    "'<span style=\"background:var(--badge-dnd-bg);color:var(--badge-dnd-color);padding:1px 5px;border-radius:3px;font-size:10px;font-weight:600;margin-right:4px\">' + count + ' neu</span>'"
)

with open("apps/abpe_crm/static/abpe_crm/softphone/js/10_sp-fop.js", "w") as f:
    f.write(c)
print("✓  10_sp-fop.js")
PYEOF
node --check "$JS10" && ok "10_sp-fop.js Syntax OK" || { echo "FEHLER"; exit 1; }
echo

# ══════════════════════════════════════════════════════════
# SCHRITT 6: softphone.html
# ══════════════════════════════════════════════════════════
info "Schritt 6/6 — softphone.html"

python3 << 'PYEOF'
with open("apps/abpe_crm/templates/abpe_crm/softphone/softphone.html", "r") as f:
    c = f.read()

# Status-Dot (Header): #9ca3af → var
c = c.replace(
    '<span id="sp-status-dot" style="width:8px;height:8px;border-radius:50%;background:#9ca3af"></span>',
    '<span id="sp-status-dot" style="width:8px;height:8px;border-radius:50%;background:var(--dot-offline)"></span>'
)

# Transfer-inline: hardcodiertes amber
c = c.replace(
    '<div id="sp-transfer-inline" style="display:none;margin:0 0 4px 0;border-radius:6px;overflow:hidden;border:0.5px solid #fcd34d;background:#fef3c7"></div>',
    '<div id="sp-transfer-inline" style="display:none;margin:0 0 4px 0;border-radius:6px;overflow:hidden;border:0.5px solid var(--status-warn-border);background:var(--status-warn-bg)"></div>'
)

# Transfer-Expand → Button #163258
c = c.replace(
    'style="padding:4px 8px;background:#163258;color:#fff;border:none;border-radius:5px;font-size:10px;cursor:pointer;white-space:nowrap">&#8594;</button>',
    'class="sp-panel-hdr" style="padding:4px 8px;border:none;border-radius:5px;font-size:10px;cursor:pointer;white-space:nowrap">&#8594;</button>'
)

# Transfer-Panel Button #163258
c = c.replace(
    'style="padding:4px 8px;background:#163258;color:#fff;border:none;border-radius:5px;font-size:10px;cursor:pointer;white-space:nowrap">&#8594; Transfer</button>',
    'class="sp-panel-hdr" style="padding:4px 8px;border:none;border-radius:5px;font-size:10px;cursor:pointer;white-space:nowrap">&#8594; Transfer</button>'
)

# Incoming Avatar: #d1fae5/#065f46
c = c.replace(
    'style="width:48px;height:48px;border-radius:50%;background:#d1fae5;color:#065f46;display:flex;align-items:center;justify-content:center;font-size:16px;font-weight:600;margin:0 auto 8px"',
    'style="width:48px;height:48px;border-radius:50%;background:var(--avatar-inc-bg);color:var(--avatar-inc-color);display:flex;align-items:center;justify-content:center;font-size:16px;font-weight:600;margin:0 auto 8px"'
)

with open("apps/abpe_crm/templates/abpe_crm/softphone/softphone.html", "w") as f:
    f.write(c)

# Verifikation: noch hardcodierte Farben?
import re
remaining = re.findall(r'#[0-9a-fA-F]{6}', c)
# Erlaubt: meta theme-color, var(--...,#...) Fallbacks, #22c55e/#ef4444 (Call/Hangup Buttons)
allowed = {'#163258','#22c55e','#ef4444','#fbbf24'}
bad = [x for x in set(remaining) if x.lower() not in {a.lower() for a in allowed}]
if bad:
    print(f"WARNUNG: Noch hardcodierte Farben in HTML: {bad}")
else:
    print("✓  softphone.html — keine unerlaubten hardcodierten Farben")
PYEOF
echo

# ══════════════════════════════════════════════════════════
# Abschluss-Check
# ══════════════════════════════════════════════════════════
info "Abschluss-Check — verbleibende hardcodierte Farben"
echo "--- 6_sp-core.js ---"
grep -c "#[0-9a-fA-F]\{6\}" "$JS6" || echo "0"
echo "--- 8_sp-status.js ---"
grep -c "#[0-9a-fA-F]\{6\}" "$JS8" || echo "0"
echo "--- 9_sp-transfer.js ---"
grep -c "#[0-9a-fA-F]\{6\}" "$JS9" || echo "0"
echo "--- 10_sp-fop.js ---"
grep -c "#[0-9a-fA-F]\{6\}" "$JS10" || echo "0"
echo "--- softphone.html ---"
grep -c "#[0-9a-fA-F]\{6\}" "$TMPL" || echo "0"
echo

info "Deploy"
python3 manage.py collectstatic --noinput 2>&1 | tail -2
supervisorctl restart abpe-django
sleep 2
supervisorctl status abpe-django
echo
ok "Fertig — Hard-Reload (Ctrl+Shift+R)"
echo
echo "Nach Hard-Reload:"
echo "  Light Mode + Dark Mode testen"
echo "  FOP, Transfer, CDR, Schnellwahl durchklicken"
echo "  Dann: Labels-Script (i18n)"

