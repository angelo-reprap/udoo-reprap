#!/usr/bin/env bash
# fix_softphone_darkmode.sh — Dark Mode CSS Variablen vervollständigen
set -euo pipefail
GREEN='\033[0;32m'; BLUE='\033[0;34m'; NC='\033[0m'
ok()   { echo -e "${GREEN}✓${NC} $*"; }
info() { echo -e "${BLUE}▶${NC}  $*"; }

BASE="/opt/abpe/backend"
CSS="apps/abpe_crm/static/abpe_crm/softphone/css/softphone.css"
[[ "$(pwd)" == "$BASE" ]] || { echo "Falsches Verzeichnis"; exit 1; }

python3 Archiv/backup_restore.py -save "$CSS" -m "vor dark mode fix: softphone.css" || exit 1
ok "Backup OK"

info "softphone.css neu schreiben"

cat > "$CSS" << 'CSSEOF'
/* softphone.css — ABpE Softphone PWA
 * Eigenständig nutzbar ohne Django/Portal
 * Light/Dark Mode via [data-theme="dark"] auf <html>
 */

/* ── CSS-Variablen Light Mode ────────────────────────── */
:root {
    --abcona-blue:       #163258;
    --abcona-blue-dark:  #0f2442;
    --abcona-blue-light: #1e4a7a;
    --bg-primary:        #ffffff;
    --bg-secondary:      #f8f8f8;
    --bg-tertiary:       #f1f3f5;
    --text-primary:      #1e1e1e;
    --text-muted:        #6c757d;
    --border-color:      #dee2e6;
    --status-green:      #22c55e;
    --status-red:        #ef4444;
    --status-yellow:     #f59e0b;
    /* Funktions-Buttons (VM, DND, etc.) */
    --fn-btn-bg:         #f9fafb;
    --fn-btn-border:     #d1d5db;
    --fn-btn-color:      #374151;
    /* Inputs */
    --input-bg:          #ffffff;
    --input-border:      #dee2e6;
    /* Panels */
    --panel-header-bg:   #163258;
    --panel-header-text: #ffffff;
    /* Scrollbar */
    --scrollbar-thumb:   #dee2e6;
}

/* ── CSS-Variablen Dark Mode ─────────────────────────── */
[data-theme="dark"] {
    --abcona-blue:       #2a3f5f;
    --abcona-blue-dark:  #1a2f4f;
    --abcona-blue-light: #3a5070;
    --bg-primary:        #1a1a1a;
    --bg-secondary:      #252525;
    --bg-tertiary:       #2e2e2e;
    --text-primary:      #e0e0e0;
    --text-muted:        #a0a0a0;
    --border-color:      #3a3a3a;
    --status-green:      #22c55e;
    --status-red:        #ef4444;
    --status-yellow:     #f59e0b;
    /* Funktions-Buttons */
    --fn-btn-bg:         #2a2a2a;
    --fn-btn-border:     #444444;
    --fn-btn-color:      #c0c0c0;
    /* Inputs */
    --input-bg:          #222222;
    --input-border:      #3a3a3a;
    /* Panels */
    --panel-header-bg:   #1e3a5f;
    --panel-header-text: #e0e0e0;
    /* Scrollbar */
    --scrollbar-thumb:   #444444;
}

/* ── Reset ───────────────────────────────────────────── */
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

body {
    font-family: 'Segoe UI', Arial, sans-serif;
    background: var(--abcona-blue-dark);
    color: var(--text-primary);
    font-size: 12px;
    min-height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: background 0.2s;
}

/* ── Softphone Container ─────────────────────────────── */
#sp-modal {
    position: relative !important;
    top: auto !important;
    right: auto !important;
    left: auto !important;
    display: block !important;
    width: 260px;
    background: var(--bg-primary);
    border: 1px solid var(--border-color);
    border-radius: 12px;
    box-shadow: 0 8px 32px rgba(0,0,0,0.35);
    font-size: 12px;
    overflow: visible;
    transition: background 0.2s, border-color 0.2s;
}

/* ── Display-Feld ────────────────────────────────────── */
#sp-display {
    background: var(--bg-secondary) !important;
    border: 1px solid var(--border-color) !important;
    color: var(--text-primary) !important;
}

/* ── Kontaktsuche Input ──────────────────────────────── */
#sp-search {
    background: var(--bg-secondary) !important;
    border: 1px solid var(--border-color) !important;
    color: var(--text-primary) !important;
}
#sp-search::placeholder { color: var(--text-muted); }

#sp-search-results {
    background: var(--bg-primary) !important;
    border: 1px solid var(--border-color) !important;
}

/* ── Tastatur-Keys ───────────────────────────────────── */
.sp-key {
    padding: 8px 0;
    border: 1px solid var(--border-color);
    border-radius: 7px;
    background: var(--bg-secondary);
    cursor: pointer;
    font-size: 14px;
    font-weight: 500;
    color: var(--text-primary);
    display: flex;
    flex-direction: column;
    align-items: center;
    line-height: 1.2;
    transition: background 0.1s;
    user-select: none;
}
.sp-key:hover  { background: var(--bg-tertiary); }
.sp-key:active { background: var(--abcona-blue); color: #fff; }
.sp-key small  { font-size: 8px; color: var(--text-muted); font-weight: 400; }

/* ── Aktions-Buttons (Backspace, C) ──────────────────── */
#sp-tab-dial button:not(#sp-call-btn):not(#sp-hangup-btn):not(.sp-key):not(#sp-mute-btn) {
    background: var(--bg-secondary);
    border-color: var(--border-color);
    color: var(--text-primary);
}

/* ── Funktions-Buttons (VM, Weiter, DND, Pickup, Transf.) */
#sp-fn-bar button {
    background: var(--fn-btn-bg) !important;
    border-color: var(--fn-btn-border) !important;
    color: var(--fn-btn-color) !important;
}

/* ── Toggle-Buttons (Schnellwahl, Anrufe, Status) ───── */
#sp-speed-toggle,
#sp-recent-toggle,
#sp-fop-toggle {
    background: var(--bg-secondary) !important;
    border-color: var(--border-color) !important;
    color: var(--text-muted) !important;
}

/* ── Tab-Buttons ─────────────────────────────────────── */
.sp-tab-active {
    background: var(--abcona-blue) !important;
    color: #fff !important;
}
.sp-tab-btn {
    transition: background 0.15s;
    color: var(--text-primary);
    background: transparent;
}

/* ── Einstellungen: Inputs ───────────────────────────── */
#sp-tab-settings input[type="text"],
#sp-tab-settings input[type="password"] {
    background: var(--input-bg) !important;
    border-color: var(--input-border) !important;
    color: var(--text-primary) !important;
}
#sp-tab-settings input::placeholder { color: var(--text-muted); }
#sp-tab-settings button:not([onclick*="saveAndRegister"]):not([onclick*="sp-cfg-pass"]) {
    background: var(--bg-secondary);
    border-color: var(--border-color);
    color: var(--text-primary);
}
#sp-tab-settings label { color: var(--text-muted); }

/* ── Speed-Panel ─────────────────────────────────────── */
#sp-speed-panel {
    position: fixed !important;
    background: var(--bg-primary);
    border-color: var(--border-color);
}
#sp-speed-panel input {
    background: var(--input-bg) !important;
    border-color: var(--input-border) !important;
    color: var(--text-primary) !important;
}
#sp-speed-add-form button:first-of-type {
    background: var(--bg-secondary);
    border-color: var(--border-color);
    color: var(--text-primary);
}

/* ── FOP-Panel ───────────────────────────────────────── */
#sp-fop-panel {
    position: fixed !important;
    background: var(--bg-primary);
    border-color: var(--border-color);
    max-height: 80vh;
    overflow-y: auto;
}
#sp-fop-panel::-webkit-scrollbar { width: 4px; }
#sp-fop-panel::-webkit-scrollbar-thumb {
    background: var(--scrollbar-thumb);
    border-radius: 2px;
}

/* ── Transfer Expand (Inline) ────────────────────────── */
#sp-transfer-expand {
    background: var(--bg-primary);
    border-color: var(--border-color) !important;
}
#sp-transfer-expand input {
    background: var(--input-bg) !important;
    border-color: var(--input-border) !important;
    color: var(--text-primary) !important;
}
#sp-transfer-expand input::placeholder { color: var(--text-muted); }

/* ── Transfer Panel (Portal-Fallback) ───────────────── */
#sp-transfer-panel {
    background: var(--bg-primary);
    border-color: var(--border-color);
}
#sp-transfer-panel input {
    background: var(--input-bg) !important;
    border-color: var(--input-border) !important;
    color: var(--text-primary) !important;
}

/* ── Letzte Anrufe Panel ─────────────────────────────── */
#sp-recent-panel {
    background: var(--bg-primary);
    border-color: var(--border-color);
}

/* ── Timer ───────────────────────────────────────────── */
#sp-call-timer { color: var(--status-green); }

/* ── Incoming Call ───────────────────────────────────── */
#sp-incoming {
    background: var(--bg-primary);
    z-index: 10000;
}
#sp-inc-name { color: var(--text-primary); }
#sp-inc-num  { color: var(--text-muted); }

/* ── Status-Bar ──────────────────────────────────────── */
#sp-status-bar { color: var(--text-primary); }

/* ── Recent (Wählen-Tab) ─────────────────────────────── */
#sp-recent { color: var(--text-primary); }

/* ── PWA Install Banner ──────────────────────────────── */
#sp-install-banner {
    position: fixed;
    bottom: 12px;
    left: 50%;
    transform: translateX(-50%);
    background: var(--abcona-blue);
    color: #fff;
    padding: 8px 16px;
    border-radius: 20px;
    font-size: 11px;
    cursor: pointer;
    box-shadow: 0 4px 12px rgba(0,0,0,0.3);
    display: none;
    align-items: center;
    gap: 8px;
    white-space: nowrap;
    z-index: 9990;
}
#sp-install-banner.visible { display: flex; }

/* ── Scrollbars global ───────────────────────────────── */
::-webkit-scrollbar { width: 4px; }
::-webkit-scrollbar-thumb {
    background: var(--scrollbar-thumb);
    border-radius: 2px;
}

/* ── Mobile ──────────────────────────────────────────── */
@media (max-width: 320px) {
    #sp-modal { width: 100vw; border-radius: 0; }
    body { align-items: flex-start; }
}

/* ── Übergänge ───────────────────────────────────────── */
#sp-modal,
#sp-modal * {
    transition: background-color 0.2s ease, border-color 0.2s ease, color 0.2s ease;
}
CSSEOF

ok "softphone.css geschrieben ($(wc -l < "$CSS") Zeilen)"

python3 manage.py collectstatic --noinput 2>&1 | tail -2
supervisorctl restart abpe-django
sleep 2
supervisorctl status abpe-django
ok "Fertig — Hard-Reload (Ctrl+Shift+R)"
echo
echo "Dark Mode testen: Moon-Icon oben rechts im Softphone-Header"

