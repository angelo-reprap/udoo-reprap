#!/usr/bin/env bash
# fix_all_hardcoded_colors.sh — Alle hardcodierten Farben in CSS-Klassen
# Aufruf: bash apps/abpe_crm/install/fix_all_hardcoded_colors.sh
set -euo pipefail
GREEN='\033[0;32m'; BLUE='\033[0;34m'; NC='\033[0m'
ok()   { echo -e "${GREEN}✓${NC} $*"; }
info() { echo -e "${BLUE}▶${NC}  $*"; }

BASE="/opt/abpe/backend"
APP="apps/abpe_crm"
CSS="${APP}/static/abpe_crm/softphone/css/softphone.css"
JS8="${APP}/static/abpe_crm/softphone/js/8_sp-status.js"
JS9="${APP}/static/abpe_crm/softphone/js/9_sp-transfer.js"
JS10="${APP}/static/abpe_crm/softphone/js/10_sp-fop.js"
TMPL="${APP}/templates/abpe_crm/softphone/softphone.html"

[[ "$(pwd)" == "$BASE" ]] || { echo "Falsches Verzeichnis"; exit 1; }

info "Backups"
for f in "$CSS" "$JS8" "$JS9" "$JS10" "$TMPL"; do
    python3 Archiv/backup_restore.py -save "$f" -m "vor hardcoded color fix" || exit 1
done
ok "Backups OK"
echo

# ── 1. CSS: sp-fn-base + Panel-Header-Klassen ────────────
info "1/5 — CSS: sp-fn-base Klassen ergänzen (falls nicht vorhanden)"

# Prüfen ob schon drin
if grep -q "sp-fn-base" "$CSS"; then
    ok "sp-fn-base bereits in CSS — überspringe"
else
cat >> "$CSS" << 'CSSEOF'

/* ── Funktions-Button Zustände ───────────────────────────── */
.sp-fn-base {
    padding: 5px 2px;
    border-radius: 6px;
    font-size: 9px;
    cursor: pointer;
    text-align: center;
    line-height: 1.3;
    border: 0.5px solid var(--fn-btn-border);
    background: var(--fn-btn-bg);
    color: var(--fn-btn-color);
}
.sp-fn-base:hover {
    background: var(--hover-bg) !important;
    color: var(--text-primary) !important;
    border-color: var(--border-color) !important;
}
.sp-fn-vm-active  { border: 0.5px solid #b45309 !important; background: #fffbeb !important; color: #92400e !important; font-weight: 600; }
.sp-fn-fwd-active { border: 0.5px solid #1e40af !important; background: #eff6ff !important; color: #1e3a8a !important; font-weight: 600; }
.sp-fn-dnd-active { border: 0.5px solid #991b1b !important; background: #fff1f2 !important; color: #991b1b !important; font-weight: 600; }
[data-theme="dark"] .sp-fn-vm-active  { border-color: #92400e !important; background: #3a2800 !important; color: #fcd34d !important; }
[data-theme="dark"] .sp-fn-fwd-active { border-color: #1e40af !important; background: #0a1f3a !important; color: #93c5fd !important; }
[data-theme="dark"] .sp-fn-dnd-active { border-color: #991b1b !important; background: #2a0a0a !important; color: #fca5a5 !important; }
CSSEOF
    ok "sp-fn-base in CSS eingefügt"
fi

# Panel-Header Dark Mode Override (falls nicht vorhanden)
if grep -q "sp-panel-hdr" "$CSS"; then
    ok "sp-panel-hdr bereits in CSS"
else
cat >> "$CSS" << 'CSSEOF2'

/* ── Panel-Header Klasse (ersetzt hardcodiertes background:#163258) ── */
.sp-panel-hdr {
    background: var(--panel-header-bg, #163258);
    color: var(--panel-header-text, #ffffff);
}
.sp-panel-hdr:hover {
    background: var(--panel-header-hover, #1e4080) !important;
}
CSSEOF2
    ok "sp-panel-hdr in CSS eingefügt"
fi
echo

# ── 2. softphone.html: fn-bar Buttons → sp-fn-base ───────
info "2/5 — softphone.html: fn-bar inline styles → sp-fn-base"

python3 << 'PYEOF'
with open("apps/abpe_crm/templates/abpe_crm/softphone/softphone.html", "r") as f:
    c = f.read()

import re

# Ersetze alle 5 fn-bar Buttons: style mit #f9fafb/#d1d5db/#374151 → class="sp-fn-base"
# Pattern: button mit diesen inline-styles
FN_STYLE = 'style="padding:5px 2px;border:0.5px solid #d1d5db;border-radius:6px;background:#f9fafb;color:#374151;font-size:9px;cursor:pointer;text-align:center;line-height:1.3"'
FN_CLASS = 'class="sp-fn-base"'

count = c.count(FN_STYLE)
c = c.replace(FN_STYLE, FN_CLASS)
print(f"  {count}x fn-bar style → class ersetzt")

# Transfer-btn hat zusätzlich display:none
FN_STYLE_NONE = 'style="display:none;padding:5px 2px;border:0.5px solid #d1d5db;border-radius:6px;background:#f9fafb;color:#374151;font-size:9px;cursor:pointer;text-align:center;line-height:1.3"'
FN_CLASS_NONE = 'class="sp-fn-base" style="display:none"'
if FN_STYLE_NONE in c:
    c = c.replace(FN_STYLE_NONE, FN_CLASS_NONE)
    print("  transfer-btn display:none erhalten")

# Panel-Header im HTML: #163258 → class sp-panel-hdr
# sp-speed-panel header
c = c.replace(
    'style="padding:6px 10px;font-size:11px;font-weight:600;border-bottom:1px solid var(--border-color);background:#163258;color:#fff;border-radius:8px 8px 0 0;display:flex;justify-content:space-between;align-items:center"',
    'class="sp-panel-hdr" style="padding:6px 10px;font-size:11px;font-weight:600;border-bottom:1px solid var(--border-color);border-radius:8px 8px 0 0;display:flex;justify-content:space-between;align-items:center"'
)
# sp-fop-panel header
c = c.replace(
    'style="padding:6px 10px;font-size:11px;font-weight:600;border-bottom:1px solid #0d2040;background:#163258;color:#fff;border-radius:8px 8px 0 0;display:flex;justify-content:space-between"',
    'class="sp-panel-hdr" style="padding:6px 10px;font-size:11px;font-weight:600;border-bottom:1px solid var(--border-color);border-radius:8px 8px 0 0;display:flex;justify-content:space-between"'
)
# sp-transfer-expand header
c = c.replace(
    'style="padding:5px 8px;background:#163258;color:#fff;font-size:10px;font-weight:600;display:flex;justify-content:space-between;align-items:center"',
    'class="sp-panel-hdr" style="padding:5px 8px;font-size:10px;font-weight:600;display:flex;justify-content:space-between;align-items:center"'
)
# sp-transfer-panel header
c = c.replace(
    'style="padding:6px 10px;font-size:11px;font-weight:600;border-bottom:1px solid #0d2040;background:#163258;color:#fff;display:flex;justify-content:space-between;align-items:center"',
    'class="sp-panel-hdr" style="padding:6px 10px;font-size:11px;font-weight:600;border-bottom:1px solid var(--border-color);display:flex;justify-content:space-between;align-items:center"'
)
# sp-recent-panel header
c = c.replace(
    'style="padding:6px 10px;font-size:11px;font-weight:600;border-bottom:1px solid #0d2040;background:#163258;color:#fff;display:flex;justify-content:space-between;align-items:center"',
    'class="sp-panel-hdr" style="padding:6px 10px;font-size:11px;font-weight:600;border-bottom:1px solid var(--border-color);display:flex;justify-content:space-between;align-items:center"'
)

# Hinzufügen-Button (#163258)
c = c.replace(
    'style="flex:1;font-size:10px;padding:3px;border-radius:4px;cursor:pointer;border:none;background:#163258;color:#fff"',
    'class="sp-panel-hdr" style="flex:1;font-size:10px;padding:3px;border-radius:4px;cursor:pointer;border:none"'
)

with open("apps/abpe_crm/templates/abpe_crm/softphone/softphone.html", "w") as f:
    f.write(c)
print("✓  softphone.html gepatcht")
PYEOF
echo

# ── 3. 8_sp-status.js: style.cssText → CSS-Klassen ───────
info "3/5 — 8_sp-status.js: style.cssText → classList"

cat > /tmp/patch_8.py << 'PYEOF'
with open("apps/abpe_crm/static/abpe_crm/softphone/js/8_sp-status.js", "r") as f:
    c = f.read()

old = """// Status-Indikatoren aktualisieren
Softphone._updateStatusIndicators = function() {
    var vmBtn    = document.getElementById('sp-vm-btn');
    var vmLabel  = document.getElementById('sp-vm-label');
    var fwdBtn   = document.getElementById('sp-fwd-btn');
    var dndBtn   = document.getElementById('sp-dnd-btn');
    var dndIcon  = document.getElementById('sp-dnd-icon');
    var dndLabel = document.getElementById('sp-dnd-label');
    var bar      = document.getElementById('sp-status-bar');
    var NS  = 'padding:5px 2px;border-radius:6px;font-size:9px;cursor:pointer;text-align:center;line-height:1.3;';
    var OFF = NS + 'border:0.5px solid #d1d5db;background:#f9fafb;color:#374151;';
    var vmCount   = Softphone._vmCount || 0;
    var fwdActive = Softphone._ext.fwd_active || false;
    var fwdTarget = Softphone._ext.fwd_target || '';
    var dndActive = Softphone._ext.dnd_active || false;

    if (vmBtn) {
        if (vmCount > 0) {
            vmBtn.style.cssText = NS + 'border:0.5px solid #b45309;background:#fffbeb;color:#92400e;font-weight:600;';
            if (vmLabel) vmLabel.textContent = 'VM \\u00b7 ' + vmCount;
        } else {
            vmBtn.style.cssText = OFF;
            if (vmLabel) vmLabel.textContent = 'VM';
        }
    }
    if (fwdBtn) {
        fwdBtn.style.cssText = fwdActive
            ? NS + 'border:0.5px solid #1e40af;background:#eff6ff;color:#1e3a8a;font-weight:600;'
            : OFF;
    }
    if (dndBtn) {
        if (dndActive) {
            dndBtn.style.cssText = NS + 'border:0.5px solid #991b1b;background:#fff1f2;color:#991b1b;font-weight:600;';
            if (dndIcon) dndIcon.className = 'bi bi-bell-slash';
        } else {
            dndBtn.style.cssText = OFF;
            if (dndIcon) dndIcon.className = 'bi bi-bell';
        }
        if (dndLabel) dndLabel.textContent = 'DND';
    }"""

new = """// Status-Indikatoren aktualisieren
Softphone._updateStatusIndicators = function() {
    var vmBtn    = document.getElementById('sp-vm-btn');
    var vmLabel  = document.getElementById('sp-vm-label');
    var fwdBtn   = document.getElementById('sp-fwd-btn');
    var dndBtn   = document.getElementById('sp-dnd-btn');
    var dndIcon  = document.getElementById('sp-dnd-icon');
    var dndLabel = document.getElementById('sp-dnd-label');
    var bar      = document.getElementById('sp-status-bar');
    var vmCount   = Softphone._vmCount || 0;
    var fwdActive = Softphone._ext.fwd_active || false;
    var fwdTarget = Softphone._ext.fwd_target || '';
    var dndActive = Softphone._ext.dnd_active || false;

    function setFnClass(el, activeClass) {
        if (!el) return;
        el.style.cssText = '';
        el.className = 'sp-fn-base' + (activeClass ? ' ' + activeClass : '');
    }

    if (vmBtn) {
        setFnClass(vmBtn, vmCount > 0 ? 'sp-fn-vm-active' : null);
        if (vmLabel) vmLabel.textContent = vmCount > 0 ? 'VM \\u00b7 ' + vmCount : 'VM';
    }
    if (fwdBtn) {
        setFnClass(fwdBtn, fwdActive ? 'sp-fn-fwd-active' : null);
    }
    if (dndBtn) {
        setFnClass(dndBtn, dndActive ? 'sp-fn-dnd-active' : null);
        if (dndIcon) dndIcon.className = dndActive ? 'bi bi-bell-slash' : 'bi bi-bell';
        if (dndLabel) dndLabel.textContent = 'DND';
    }"""

assert old in c, "FEHLER: Block nicht gefunden in 8_sp-status.js"
c = c.replace(old, new, 1)

# Status-Bar Farben bleiben — die sind semantisch (rot=DND, amber=VM) und kein Hover-Problem
with open("apps/abpe_crm/static/abpe_crm/softphone/js/8_sp-status.js", "w") as f:
    f.write(c)
print("✓  8_sp-status.js: style.cssText → classList")
PYEOF
python3 /tmp/patch_8.py
node --check "$JS8" && ok "8_sp-status.js Syntax OK" || { echo "FEHLER"; exit 1; }
echo

# ── 4. 9_sp-transfer.js: onmouseover/out → CSS-Variablen ─
info "4/5 — 9_sp-transfer.js: hardcodierte Hover-Farben → CSS-Variablen"

python3 << 'PYEOF'
with open("apps/abpe_crm/static/abpe_crm/softphone/js/9_sp-transfer.js", "r") as f:
    c = f.read()

# Section-Header Hover: #163258/#1e4080 → CSS-Klassen
c = c.replace(
    "var BLUE = '#163258';\n\n    function tBtn(num) {",
    "var BLUE = 'var(--panel-header-bg,#163258)';\n\n    function tBtn(num) {"
)
c = c.replace(
    "'onmouseover=\"this.style.background=\\'#1e4080\\'\" '\n            + 'onmouseout=\"this.style.background=\\'' + BLUE + '\\'\">'",
    "'onmouseover=\"this.style.background=\\'var(--panel-header-hover,#1e4080)\\'\" '\n            + 'onmouseout=\"this.style.background=\\'var(--panel-header-bg,#163258)\\'\">'",
)

# tBtn background hardcoded
c = c.replace(
    "'style=\"font-size:9px;padding:1px 6px;border:none;border-radius:3px;background:#163258;color:#fff;cursor:pointer;flex-shrink:0\">&#8594;</button>'",
    "'class=\"sp-panel-hdr\" style=\"font-size:9px;padding:1px 6px;border:none;border-radius:3px;cursor:pointer;flex-shrink:0\">&#8594;</button>'"
)

with open("apps/abpe_crm/static/abpe_crm/softphone/js/9_sp-transfer.js", "w") as f:
    f.write(c)
print("✓  9_sp-transfer.js gepatcht")
PYEOF
node --check "$JS9" && ok "9_sp-transfer.js Syntax OK" || { echo "FEHLER"; exit 1; }
echo

# ── 5. 10_sp-fop.js: BLUE/BLUE_HOV → CSS-Variablen ──────
info "5/5 — 10_sp-fop.js: BLUE/BLUE_HOV → CSS-Variablen"

python3 << 'PYEOF'
with open("apps/abpe_crm/static/abpe_crm/softphone/js/10_sp-fop.js", "r") as f:
    c = f.read()

# _renderFOP: BLUE/BLUE_HOV Konstanten
c = c.replace(
    "    var BLUE = '#163258', BLUE_HOV = '#1e4080';",
    "    var BLUE = 'var(--panel-header-bg,#163258)', BLUE_HOV = 'var(--panel-header-hover,#1e4080)';"
)

# _renderRecent: BLUE/BLUE_HOV
c = c.replace(
    "    var BLUE = '#163258', BLUE_HOV = '#1e4080';\n    var missed",
    "    var BLUE = 'var(--panel-header-bg,#163258)', BLUE_HOV = 'var(--panel-header-hover,#1e4080)';\n    var missed"
)

# toggleFOP: #dbeafe highlight → CSS-Variable
c = c.replace(
    "    if (btn) btn.style.background = open ? '#dbeafe' : 'var(--bg-secondary,#f8f8f8)';",
    "    if (btn) btn.style.background = open ? 'var(--active-highlight,#dbeafe)' : 'var(--bg-secondary,#f8f8f8)';"
)

# toggleSpeedDial: gleich
c = c.replace(
    "    if (btn) btn.style.background = open ? '#dbeafe' : 'var(--bg-secondary,#f8f8f8)';\n    if (open) Softphone._renderSpeedDials();",
    "    if (btn) btn.style.background = open ? 'var(--active-highlight,#dbeafe)' : 'var(--bg-secondary,#f8f8f8)';\n    if (open) Softphone._renderSpeedDials();"
)

with open("apps/abpe_crm/static/abpe_crm/softphone/js/10_sp-fop.js", "w") as f:
    f.write(c)
print("✓  10_sp-fop.js gepatcht")
PYEOF
node --check "$JS10" && ok "10_sp-fop.js Syntax OK" || { echo "FEHLER"; exit 1; }
echo

# ── CSS: active-highlight Variable ergänzen ───────────────
python3 << 'PYEOF'
with open("apps/abpe_crm/static/abpe_crm/softphone/css/softphone.css", "r") as f:
    c = f.read()

# In :root ergänzen
if '--active-highlight' not in c:
    c = c.replace(
        "    /* Hover / Active States */\n    --hover-bg:          #e9ecef;",
        "    /* Hover / Active States */\n    --hover-bg:          #e9ecef;\n    --active-highlight:  #dbeafe;\n    --panel-header-hover:#1e4080;"
    )
    c = c.replace(
        "    /* Hover / Active States — kein Blau im Dark Mode */\n    --hover-bg:          #3a3a3a;",
        "    /* Hover / Active States — kein Blau im Dark Mode */\n    --hover-bg:          #3a3a3a;\n    --active-highlight:  #1e3a5f;\n    --panel-header-hover:#3a3a3a;"
    )
    with open("apps/abpe_crm/static/abpe_crm/softphone/css/softphone.css", "w") as f:
        f.write(c)
    print("✓  --active-highlight + --panel-header-hover in CSS")
else:
    print("INFO: --active-highlight bereits vorhanden")
PYEOF
echo

# ── Deploy ────────────────────────────────────────────────
info "Deploy"
python3 manage.py collectstatic --noinput 2>&1 | tail -2
supervisorctl restart abpe-django
sleep 2
supervisorctl status abpe-django
echo
ok "Fertig — Hard-Reload (Ctrl+Shift+R)"
echo
echo "Erwartet:"
echo "  Dark Mode: alle Hover grau, kein Blau"
echo "  FOP/Speed/Recent/Transfer Panel-Header: dunkelgrau"
echo "  DND aktiv: rot  |  VM aktiv: amber  |  FWD aktiv: blau"

