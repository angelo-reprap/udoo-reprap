#!/usr/bin/env bash
# fix_fnbar_classes.sh — fn-bar Buttons: style.cssText → CSS-Klassen
# Aufruf: bash apps/abpe_crm/install/fix_fnbar_classes.sh
set -euo pipefail
GREEN='\033[0;32m'; NC='\033[0m'
ok() { echo -e "${GREEN}✓${NC} $*"; }

BASE="/opt/abpe/backend"
CSS="apps/abpe_crm/static/abpe_crm/softphone/css/softphone.css"
JS8="apps/abpe_crm/static/abpe_crm/softphone/js/8_sp-status.js"

[[ "$(pwd)" == "$BASE" ]] || { echo "Falsches Verzeichnis"; exit 1; }

python3 Archiv/backup_restore.py -save "$CSS" -m "vor fnbar class fix: softphone.css" || exit 1
python3 Archiv/backup_restore.py -save "$JS8" -m "vor fnbar class fix: 8_sp-status.js" || exit 1
ok "Backups OK"

# ── Schritt 1: CSS-Klassen ans Ende von softphone.css anfügen ─────────────
cat >> "$CSS" << 'CSSEOF'

/* ── Funktions-Button Zustände (ersetzen inline style.cssText) ──────────── */
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
    transition: background 0.15s, color 0.15s;
}
.sp-fn-base:hover {
    background: var(--hover-bg) !important;
    color: var(--text-primary) !important;
}
.sp-fn-vm-active {
    border: 0.5px solid #b45309 !important;
    background: #fffbeb !important;
    color: #92400e !important;
    font-weight: 600;
}
.sp-fn-fwd-active {
    border: 0.5px solid #1e40af !important;
    background: #eff6ff !important;
    color: #1e3a8a !important;
    font-weight: 600;
}
.sp-fn-dnd-active {
    border: 0.5px solid #991b1b !important;
    background: #fff1f2 !important;
    color: #991b1b !important;
    font-weight: 600;
}
[data-theme="dark"] .sp-fn-vm-active {
    border-color: #92400e !important;
    background: #3a2800 !important;
    color: #fcd34d !important;
}
[data-theme="dark"] .sp-fn-fwd-active {
    border-color: #1e40af !important;
    background: #0a1f3a !important;
    color: #93c5fd !important;
}
[data-theme="dark"] .sp-fn-dnd-active {
    border-color: #991b1b !important;
    background: #2a0a0a !important;
    color: #fca5a5 !important;
}
CSSEOF
ok "CSS-Klassen in softphone.css eingefügt"

# ── Schritt 2: 8_sp-status.js patchen — style.cssText → className ─────────
python3 << 'PYEOF'
with open("apps/abpe_crm/static/abpe_crm/softphone/js/8_sp-status.js", "r") as f:
    c = f.read()

old = """Softphone._updateStatusIndicators = function() {
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
            if (vmLabel) vmLabel.textContent = 'VM \u00b7 ' + vmCount;
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

assert old in c, "FEHLER: _updateStatusIndicators Block nicht gefunden"

new = """Softphone._updateStatusIndicators = function() {
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

    // CSS-Klassen statt inline style.cssText — Dark Mode kompatibel
    function setClass(el, activeClass) {
        if (!el) return;
        el.style.cssText = '';
        el.className = el.className
            .replace(/sp-fn-(vm|fwd|dnd)-active|sp-fn-base/g, '').trim();
        el.classList.add('sp-fn-base');
        if (activeClass) el.classList.add(activeClass);
    }

    if (vmBtn) {
        setClass(vmBtn, vmCount > 0 ? 'sp-fn-vm-active' : null);
        if (vmLabel) vmLabel.textContent = vmCount > 0 ? 'VM \u00b7 ' + vmCount : 'VM';
    }
    if (fwdBtn) {
        setClass(fwdBtn, fwdActive ? 'sp-fn-fwd-active' : null);
    }
    if (dndBtn) {
        setClass(dndBtn, dndActive ? 'sp-fn-dnd-active' : null);
        if (dndIcon) dndIcon.className = dndActive ? 'bi bi-bell-slash' : 'bi bi-bell';
        if (dndLabel) dndLabel.textContent = 'DND';
    }"""

c = c.replace(old, new, 1)
assert "sp-fn-base" in c, "FEHLER: Replace fehlgeschlagen"

with open("apps/abpe_crm/static/abpe_crm/softphone/js/8_sp-status.js", "w") as f:
    f.write(c)
print("✓  _updateStatusIndicators auf CSS-Klassen umgestellt")
PYEOF

node --check "$JS8" && ok "8_sp-status.js Syntax OK" || { echo "FEHLER: JS Syntax"; exit 1; }

# ── Schritt 3: HTML — Buttons bekommen sp-fn-base Klasse ──────────────────
# Damit die Klasse von Anfang an stimmt (vor erstem _updateStatusIndicators Aufruf)
python3 << 'PYEOF2'
with open("apps/abpe_crm/templates/abpe_crm/softphone/softphone.html", "r") as f:
    c = f.read()

# sp-vm-btn
c = c.replace(
    '<button id="sp-vm-btn" onclick="Softphone.callVoicemail()" title="Voicemail"\n                    style="padding:5px 2px;border:0.5px solid #d1d5db;border-radius:6px;background:#f9fafb;color:#374151;font-size:9px;cursor:pointer;text-align:center;line-height:1.3">',
    '<button id="sp-vm-btn" onclick="Softphone.callVoicemail()" title="Voicemail" class="sp-fn-base">'
)
# sp-fwd-btn
c = c.replace(
    '<button id="sp-fwd-btn" onclick="Softphone.callForward()" title="Rufweiterleitung"\n                    style="padding:5px 2px;border:0.5px solid #d1d5db;border-radius:6px;background:#f9fafb;color:#374151;font-size:9px;cursor:pointer;text-align:center;line-height:1.3">',
    '<button id="sp-fwd-btn" onclick="Softphone.callForward()" title="Rufweiterleitung" class="sp-fn-base">'
)
# sp-dnd-btn
c = c.replace(
    '<button id="sp-dnd-btn" onclick="Softphone.toggleDND()" title="Do Not Disturb"\n                    style="padding:5px 2px;border:0.5px solid #d1d5db;border-radius:6px;background:#f9fafb;color:#374151;font-size:9px;cursor:pointer;text-align:center;line-height:1.3">',
    '<button id="sp-dnd-btn" onclick="Softphone.toggleDND()" title="Do Not Disturb" class="sp-fn-base">'
)
# Pickup
c = c.replace(
    '<button onclick="Softphone.pickup()" title="Pickup"\n                    style="padding:5px 2px;border:0.5px solid #d1d5db;border-radius:6px;background:#f9fafb;color:#374151;font-size:9px;cursor:pointer;text-align:center;line-height:1.3">',
    '<button onclick="Softphone.pickup()" title="Pickup" class="sp-fn-base">'
)
# Transfer-btn
c = c.replace(
    '<button id="sp-transfer-btn" onclick="Softphone.toggleTransfer()" title="Transfer"\n                    style="display:none;padding:5px 2px;border:0.5px solid #d1d5db;border-radius:6px;background:#f9fafb;color:#374151;font-size:9px;cursor:pointer;text-align:center;line-height:1.3">',
    '<button id="sp-transfer-btn" onclick="Softphone.toggleTransfer()" title="Transfer" class="sp-fn-base" style="display:none">'
)

with open("apps/abpe_crm/templates/abpe_crm/softphone/softphone.html", "w") as f:
    f.write(c)

# Zählen wie viele ersetzt wurden
count = c.count('class="sp-fn-base"')
print(f"✓  {count} fn-bar Buttons auf sp-fn-base Klasse umgestellt")
PYEOF2

python3 manage.py collectstatic --noinput 2>&1 | tail -2
supervisorctl restart abpe-django
sleep 2
supervisorctl status abpe-django
ok "Fertig — Hard-Reload (Ctrl+Shift+R)"
echo
echo "Dark Mode: Funktions-Buttons (VM/Weiter/DND/Pickup/Transf.)"
echo "→ Hover: dunkelgrau, kein Blau mehr"
echo "→ DND aktiv: rot, VM aktiv: amber, FWD aktiv: blau (bewusst)"

