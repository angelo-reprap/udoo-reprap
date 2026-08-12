#!/usr/bin/env bash
# ============================================================
# deploy_softphone_ui.sh — softphone.html + softphone.css deployen
# Aufruf: bash apps/abpe_crm/install/deploy_softphone_ui.sh
# CWD:    /opt/abpe/backend/
# ============================================================
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; NC='\033[0m'
ok()   { echo -e "${GREEN}✓${NC} $*"; }
warn() { echo -e "${YELLOW}⚠${NC}  $*"; }
err()  { echo -e "${RED}✗${NC}  $*"; exit 1; }
info() { echo -e "${BLUE}▶${NC}  $*"; }

BASE="/opt/abpe/backend"
APP="apps/abpe_crm"
ARCHIVE="Archiv/backup_restore.py"
SP_TMPL="${APP}/templates/abpe_crm/softphone/softphone.html"
SP_CSS="${APP}/static/abpe_crm/softphone/css/softphone.css"

[[ "$(pwd)" == "$BASE" ]] || err "Bitte aus $BASE ausführen"
[[ -f "$ARCHIVE" ]] || err "Backup-Script nicht gefunden"

echo "════════════════════════════════════════════════════"
info "Softphone UI Deploy — softphone.html + softphone.css"
echo "════════════════════════════════════════════════════"
echo

# ── Backup ────────────────────────────────────────────────
info "Schritt 1/3 — Backup"
python3 "$ARCHIVE" -save "$SP_TMPL" -m "vor UI deploy: softphone.html" || err "Backup fehlgeschlagen"
python3 "$ARCHIVE" -save "$SP_CSS"  -m "vor UI deploy: softphone.css"  || err "Backup fehlgeschlagen"
ok "Backups OK"
echo

# ── softphone.css schreiben ───────────────────────────────
info "Schritt 2/3 — softphone.css"

cat > "$SP_CSS" << 'CSSEOF'
/* softphone.css — ABpE Softphone PWA
 * Eigenständig nutzbar ohne Django/Portal
 * Spiegelt core-theme.css CSS-Variablen für Light/Dark Mode
 */

/* ── CSS-Variablen Light Mode ────────────────────────── */
:root {
    --abcona-blue:      #163258;
    --abcona-blue-dark: #0f2442;
    --abcona-blue-light:#1e4a7a;
    --bg-primary:       #ffffff;
    --bg-secondary:     #f8f8f8;
    --text-primary:     #1e1e1e;
    --text-muted:       #6c757d;
    --border-color:     #dee2e6;
    --status-green:     #22c55e;
    --status-red:       #ef4444;
    --status-yellow:    #f59e0b;
}

/* ── CSS-Variablen Dark Mode ─────────────────────────── */
[data-theme="dark"] {
    --abcona-blue:      #3a3a3a;
    --abcona-blue-dark: #2a2a2a;
    --bg-primary:       #1a1a1a;
    --bg-secondary:     #252525;
    --text-primary:     #e0e0e0;
    --text-muted:       #a0a0a0;
    --border-color:     #333333;
}

/* ── Reset ───────────────────────────────────────────── */
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

body {
    font-family: 'Segoe UI', Arial, sans-serif;
    background: var(--abcona-blue);
    color: var(--text-primary);
    font-size: 12px;
    min-height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
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
    box-shadow: 0 8px 32px rgba(0,0,0,0.28);
    font-size: 12px;
    overflow: visible;
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
.sp-key:active {
    background: var(--abcona-blue);
    color: #fff;
}
.sp-key small {
    font-size: 8px;
    color: var(--text-muted);
    font-weight: 400;
}

/* ── Tab-Buttons ─────────────────────────────────────── */
.sp-tab-active {
    background: var(--abcona-blue) !important;
    color: #fff !important;
}
.sp-tab-btn {
    transition: background 0.15s;
}

/* ── Panels (Speed/FOP) ──────────────────────────────── */
#sp-speed-panel,
#sp-fop-panel {
    position: fixed !important;
}

/* ── Incoming Call ───────────────────────────────────── */
#sp-incoming {
    z-index: 10000;
}

/* ── FOP Scrollbar ───────────────────────────────────── */
#sp-fop-panel::-webkit-scrollbar { width: 4px; }
#sp-fop-panel::-webkit-scrollbar-thumb {
    background: var(--border-color);
    border-radius: 2px;
}

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

/* ── Mobile ──────────────────────────────────────────── */
@media (max-width: 320px) {
    #sp-modal { width: 100vw; border-radius: 0; }
    body { align-items: flex-start; }
}
CSSEOF
ok "softphone.css geschrieben"
echo

# ── softphone.html schreiben ──────────────────────────────
info "Schritt 3/3 — softphone.html"

cat > "$SP_TMPL" << 'HTMLEOF'
{% load static %}
<!DOCTYPE html>
<html lang="de" data-theme="light">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <meta name="theme-color" content="#163258">
    <meta name="mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
    <meta name="apple-mobile-web-app-title" content="Softphone">
    <title>ABpE Softphone</title>
    <link rel="manifest" href="{% static 'abpe_crm/softphone/manifest.json' %}">
    <link rel="apple-touch-icon" href="{% static 'abpe_crm/softphone/icons/icon-192.png' %}">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.0/font/bootstrap-icons.css">
    <link rel="stylesheet" href="{% static 'abpe_crm/softphone/css/softphone.css' %}">
    <script>
    window.SP_CONFIG = {
        api_base:     '{{ api_base|default:"/crm/api" }}',
        contacts_url: '{{ api_base|default:"/crm/api" }}/softphone/contacts/',
        ws:           '{{ sp_settings.ws|default:"" }}',
        extension:    '{{ sp_settings.extension|default:"" }}',
        display:      '{{ sp_settings.display|default:"" }}',
        vm_ext:       '{{ sp_settings.vm_ext|default:"" }}',
        dnd_ext:      '{{ sp_settings.dnd_ext|default:"" }}',
        status_exts:  '{{ sp_settings.status_exts|default:"" }}',
    };
    window.SP_LANG = '{{ request.LANGUAGE_CODE|default:"de" }}';
    </script>
</head>
<body>

<div id="sp-modal" style="overflow:visible">

    <!-- Header -->
    <div id="sp-drag-handle" style="background:var(--abcona-blue,#163258);color:#fff;padding:8px 12px;display:flex;align-items:center;justify-content:space-between;user-select:none;border-radius:12px 12px 0 0">
        <span style="font-weight:600;font-size:13px"><i class="bi bi-telephone-fill"></i> Softphone</span>
        <div style="display:flex;align-items:center;gap:8px">
            <span id="sp-status-text" style="font-size:10px;color:#8ba8c8">Nicht verbunden</span>
            <span id="sp-status-dot" style="width:8px;height:8px;border-radius:50%;background:#9ca3af"></span>
            <button id="sp-theme-btn" onclick="SP_Theme.toggle()" title="Dark/Light Mode"
                style="background:none;border:none;color:rgba(255,255,255,0.5);cursor:pointer;padding:0;font-size:14px">
                <i class="bi bi-moon"></i>
            </button>
        </div>
    </div>

    <!-- Tabs -->
    <div style="display:flex;border-bottom:1px solid var(--border-color)">
        <button class="sp-tab-btn sp-tab-active" onclick="Softphone.showTab('dial',this)"
            style="flex:1;padding:7px;border:none;background:var(--abcona-blue,#163258);color:#fff;font-size:11px;cursor:pointer">
            <i class="bi bi-grid-3x3-gap"></i> Wählen
        </button>
        <button class="sp-tab-btn" onclick="Softphone.showTab('settings',this)"
            style="flex:1;padding:7px;border:none;background:transparent;color:inherit;font-size:11px;cursor:pointer;border-left:1px solid var(--border-color)">
            <i class="bi bi-gear"></i> Einstellungen
        </button>
    </div>

    <!-- TAB: Wählen -->
    <div id="sp-tab-dial">
        <div style="padding:10px 12px 0">
            <div id="sp-display" style="background:var(--bg-secondary,#f8f8f8);border:1px solid var(--border-color);border-radius:7px;padding:8px 10px;font-size:18px;font-weight:600;min-height:38px;letter-spacing:2px;color:var(--text-primary,#111);margin-bottom:6px">&nbsp;</div>
            <input id="sp-search" type="text" placeholder="Kontakt suchen…" oninput="Softphone.search(this.value)"
                style="width:100%;box-sizing:border-box;padding:5px 8px;border:1px solid var(--border-color);border-radius:7px;font-size:11px;background:var(--bg-secondary,#f8f8f8);margin-bottom:4px;color:var(--text-primary)">
            <div id="sp-search-results" style="display:none;max-height:100px;overflow-y:auto;border:1px solid var(--border-color);border-radius:7px;margin-bottom:6px;background:var(--bg-primary,#fff)"></div>
            <div id="sp-recent" style="margin-bottom:6px"></div>
        </div>

        <div style="padding:0 12px">
            <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:4px;margin-bottom:6px">
                <button class="sp-key" onclick="Softphone.press('1')">1<span>&#8203;</span></button>
                <button class="sp-key" onclick="Softphone.press('2')">2<small>ABC</small></button>
                <button class="sp-key" onclick="Softphone.press('3')">3<small>DEF</small></button>
                <button class="sp-key" onclick="Softphone.press('4')">4<small>GHI</small></button>
                <button class="sp-key" onclick="Softphone.press('5')">5<small>JKL</small></button>
                <button class="sp-key" onclick="Softphone.press('6')">6<small>MNO</small></button>
                <button class="sp-key" onclick="Softphone.press('7')">7<small>PQR</small></button>
                <button class="sp-key" onclick="Softphone.press('8')">8<small>TUV</small></button>
                <button class="sp-key" onclick="Softphone.press('9')">9<small>WXY</small></button>
                <button class="sp-key" onclick="Softphone.press('*')">*</button>
                <button class="sp-key" onclick="Softphone.press('0')">0<small>+</small></button>
                <button class="sp-key" onclick="Softphone.press('#')">#</button>
            </div>

            <div style="display:flex;gap:6px;margin-bottom:10px">
                <button onclick="Softphone.backspace()"
                    style="padding:8px 12px;border:1px solid var(--border-color);border-radius:7px;background:var(--bg-secondary,#f8f8f8);cursor:pointer;font-size:14px;color:var(--text-primary)">
                    <i class="bi bi-backspace"></i></button>
                <button id="sp-call-btn" onclick="Softphone.call()"
                    style="flex:1;padding:8px;border:none;border-radius:7px;background:#22c55e;color:#fff;font-size:16px;cursor:pointer">
                    <i class="bi bi-telephone-fill"></i></button>
                <button onclick="Softphone.clearDisplay()"
                    style="padding:8px 11px;border:1px solid var(--border-color);border-radius:7px;background:var(--bg-secondary,#f8f8f8);cursor:pointer;font-size:13px;font-weight:600;color:var(--text-muted)">C</button>
                <button id="sp-hangup-btn" onclick="Softphone.hangup()"
                    style="display:none;flex:1;padding:8px;border:none;border-radius:7px;background:#ef4444;color:#fff;font-size:16px;cursor:pointer">
                    <i class="bi bi-telephone-x-fill"></i></button>
                <button id="sp-mute-btn" onclick="Softphone.toggleMute()"
                    style="display:none;padding:8px 12px;border:1px solid var(--border-color);border-radius:7px;background:var(--bg-secondary,#f8f8f8);cursor:pointer;font-size:14px">
                    <i class="bi bi-mic-fill"></i></button>
            </div>

            <div id="sp-call-timer" style="display:none;text-align:center;font-size:13px;font-weight:600;color:#22c55e;padding-bottom:8px">0:00</div>
            <div id="sp-transfer-inline" style="display:none;margin:0 0 4px 0;border-radius:6px;overflow:hidden;border:0.5px solid #fcd34d;background:#fef3c7"></div>

            <div style="border-top:1px solid var(--border-color);margin:4px 0"></div>
            <div id="sp-status-bar" style="display:none"></div>
            <div id="sp-fn-bar" style="display:grid;grid-template-columns:repeat(4,1fr);gap:3px;margin:5px 8px 8px">
                <button id="sp-vm-btn" onclick="Softphone.callVoicemail()" title="Voicemail"
                    style="padding:5px 2px;border:0.5px solid #d1d5db;border-radius:6px;background:#f9fafb;color:#374151;font-size:9px;cursor:pointer;text-align:center;line-height:1.3">
                    <i id="sp-vm-icon" class="bi bi-voicemail" style="display:block;font-size:13px"></i><span id="sp-vm-label">VM</span></button>
                <button id="sp-fwd-btn" onclick="Softphone.callForward()" title="Rufweiterleitung"
                    style="padding:5px 2px;border:0.5px solid #d1d5db;border-radius:6px;background:#f9fafb;color:#374151;font-size:9px;cursor:pointer;text-align:center;line-height:1.3">
                    <i class="bi bi-arrow-return-right" style="display:block;font-size:13px"></i>Weiter</button>
                <button id="sp-dnd-btn" onclick="Softphone.toggleDND()" title="Do Not Disturb"
                    style="padding:5px 2px;border:0.5px solid #d1d5db;border-radius:6px;background:#f9fafb;color:#374151;font-size:9px;cursor:pointer;text-align:center;line-height:1.3">
                    <i id="sp-dnd-icon" class="bi bi-bell" style="display:block;font-size:13px"></i><span id="sp-dnd-label">DND</span></button>
                <button onclick="Softphone.pickup()" title="Pickup"
                    style="padding:5px 2px;border:0.5px solid #d1d5db;border-radius:6px;background:#f9fafb;color:#374151;font-size:9px;cursor:pointer;text-align:center;line-height:1.3">
                    <i class="bi bi-telephone-inbound" style="display:block;font-size:13px"></i>Pickup</button>
                <button id="sp-transfer-btn" onclick="Softphone.toggleTransfer()" title="Transfer"
                    style="display:none;padding:5px 2px;border:0.5px solid #d1d5db;border-radius:6px;background:#f9fafb;color:#374151;font-size:9px;cursor:pointer;text-align:center;line-height:1.3">
                    <i class="bi bi-arrow-right-circle" style="display:block;font-size:13px"></i>Transf.</button>
            </div>

            <div style="display:flex;gap:4px;margin:4px 8px 6px">
                <button onclick="Softphone.toggleSpeedDial()" id="sp-speed-toggle"
                    style="flex:1;padding:3px;border:0.5px solid var(--border-color);border-radius:5px;background:var(--bg-secondary,#f8f8f8);font-size:9px;cursor:pointer;color:var(--text-muted)">&#9664; Schnellwahl</button>
                <button onclick="Softphone.showRecent()" id="sp-recent-toggle"
                    style="flex:1;padding:3px;border:0.5px solid var(--border-color);border-radius:5px;background:var(--bg-secondary,#f8f8f8);font-size:9px;cursor:pointer;color:var(--text-muted)">&#9742; Anrufe</button>
                <button onclick="Softphone.toggleFOP()" id="sp-fop-toggle"
                    style="flex:1;padding:3px;border:0.5px solid var(--border-color);border-radius:5px;background:var(--bg-secondary,#f8f8f8);font-size:9px;cursor:pointer;color:var(--text-muted)">Status &#9654;</button>
            </div>
        </div>

        <!-- Panel: Schnellwahl -->
        <div id="sp-speed-panel" style="display:none;position:fixed;width:200px;background:var(--bg-primary,#fff);border:1px solid var(--border-color);border-radius:8px;overflow:visible;z-index:9998">
            <div style="padding:6px 10px;font-size:11px;font-weight:600;border-bottom:1px solid var(--border-color);background:#163258;color:#fff;border-radius:8px 8px 0 0;display:flex;justify-content:space-between;align-items:center">
                <span>Schnellwahl</span>
                <div style="display:flex;align-items:center;gap:8px">
                    <span onclick="Softphone._speedDialAddManual()" style="cursor:pointer;font-size:14px;opacity:.7" title="Manuell hinzufügen">&#43;</span>
                    <span onclick="Softphone._speedDialAddFirma()" style="cursor:pointer;font-size:10px;opacity:.8;background:rgba(255,255,255,.15);padding:1px 5px;border-radius:3px" title="Firma hinzufügen">+Firma</span>
                    <span onclick="Softphone.toggleSpeedDial()" style="cursor:pointer;font-size:14px">&#10005;</span>
                </div>
            </div>
            <div id="sp-speed-list" style="padding:4px 0;max-height:60vh;overflow-y:auto">
                <div style="padding:8px;font-size:10px;color:var(--text-muted)">Keine Einträge</div>
            </div>
            <div id="sp-speed-add-form" style="display:none;padding:6px 8px;border-top:1px solid var(--border-color);flex-direction:column;gap:4px">
                <input id="sp-speed-add-label" placeholder="Bezeichnung"
                    style="font-size:11px;padding:3px 6px;border:1px solid var(--border-color);border-radius:4px;width:100%;box-sizing:border-box;background:var(--bg-secondary,#f8f8f8);color:var(--text-primary)">
                <input id="sp-speed-add-number" placeholder="+49 171 123 4567"
                    style="font-size:11px;padding:3px 6px;border:1px solid var(--border-color);border-radius:4px;width:100%;box-sizing:border-box;background:var(--bg-secondary,#f8f8f8);color:var(--text-primary)">
                <div style="display:flex;gap:4px">
                    <button onclick="Softphone._speedDialCancelManual()"
                        style="flex:1;font-size:10px;padding:3px;border-radius:4px;cursor:pointer;border:1px solid var(--border-color);background:var(--bg-secondary,#f8f8f8);color:var(--text-primary)">Abbrechen</button>
                    <button onclick="Softphone._speedDialConfirmManual()"
                        style="flex:1;font-size:10px;padding:3px;border-radius:4px;cursor:pointer;border:none;background:#163258;color:#fff">Hinzufügen</button>
                </div>
            </div>
        </div>

        <!-- Panel: FOP -->
        <div id="sp-fop-panel" style="display:none;position:fixed;width:220px;background:var(--bg-primary,#fff);border:1px solid var(--border-color);border-radius:8px;z-index:9998;max-height:80vh;overflow-y:auto">
            <div style="padding:6px 10px;font-size:11px;font-weight:600;border-bottom:1px solid #0d2040;background:#163258;color:#fff;border-radius:8px 8px 0 0;display:flex;justify-content:space-between">
                <span>Ext. Status</span>
                <span onclick="Softphone.toggleFOP()" style="cursor:pointer;color:#fff">&#10005;</span>
            </div>
            <div id="sp-status-panel" style="padding:4px 0">
                <div style="padding:8px;font-size:10px;color:var(--text-muted)">Keine Extensions</div>
            </div>
        </div>

    </div>

    <!-- TAB: Einstellungen -->
    <div id="sp-tab-settings" style="display:none;padding:12px">
        <div style="display:flex;flex-direction:column;gap:8px">
            <div>
                <label style="font-size:11px;color:var(--text-muted);display:block;margin-bottom:3px">SIP Benutzer</label>
                <input id="sp-cfg-user" type="text" placeholder="z.B. 22"
                    style="width:100%;box-sizing:border-box;padding:5px 8px;border:1px solid var(--border-color);border-radius:7px;font-size:12px;background:var(--bg-primary);color:var(--text-primary)">
            </div>
            <div>
                <label style="font-size:11px;color:var(--text-muted);display:block;margin-bottom:3px">SIP Passwort</label>
                <div style="display:flex">
                    <input id="sp-cfg-pass" type="password" placeholder="Passwort"
                        style="flex:1;padding:5px 8px;border:1px solid var(--border-color);border-radius:7px 0 0 7px;font-size:12px;box-sizing:border-box;background:var(--bg-primary);color:var(--text-primary)">
                    <button type="button"
                        onclick="const i=document.getElementById('sp-cfg-pass');i.type=i.type==='password'?'text':'password';this.querySelector('i').className=i.type==='password'?'bi bi-eye':'bi bi-eye-slash'"
                        style="padding:5px 8px;border:1px solid var(--border-color);border-left:none;border-radius:0 7px 7px 0;background:var(--bg-secondary,#f8f8f8);cursor:pointer;color:var(--text-primary)">
                        <i class="bi bi-eye"></i></button>
                </div>
            </div>
            <div>
                <label style="font-size:11px;color:var(--text-muted);display:block;margin-bottom:3px">WebSocket URL</label>
                <input id="sp-cfg-ws" type="text" placeholder="wss://pbx.win.abcona.info:8089/ws"
                    style="width:100%;box-sizing:border-box;padding:5px 8px;border:1px solid var(--border-color);border-radius:7px;font-size:12px;background:var(--bg-primary);color:var(--text-primary)">
            </div>
            <div>
                <label style="font-size:11px;color:var(--text-muted);display:block;margin-bottom:3px">Anzeigename</label>
                <input id="sp-cfg-name" type="text" placeholder="z.B. Angelo"
                    style="width:100%;box-sizing:border-box;padding:5px 8px;border:1px solid var(--border-color);border-radius:7px;font-size:12px;background:var(--bg-primary);color:var(--text-primary)">
            </div>
            <div style="border-top:1px solid var(--border-color);margin:4px 0;padding-top:4px">
                <div style="font-size:10px;font-weight:600;color:var(--text-muted);text-transform:uppercase;letter-spacing:.5px;margin-bottom:6px">Voicemail &amp; DND</div>
            </div>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:6px">
                <div>
                    <label style="font-size:11px;color:var(--text-muted);display:block;margin-bottom:3px">VM-Nebenstelle</label>
                    <input id="sp-cfg-vm-ext" type="text" placeholder="z.B. 22"
                        style="width:100%;box-sizing:border-box;padding:5px 8px;border:1px solid var(--border-color);border-radius:7px;font-size:12px;background:var(--bg-primary);color:var(--text-primary)">
                </div>
                <div>
                    <label style="font-size:11px;color:var(--text-muted);display:block;margin-bottom:3px">DND-Nebenstelle</label>
                    <input id="sp-cfg-dnd-ext" type="text" placeholder="z.B. 22"
                        style="width:100%;box-sizing:border-box;padding:5px 8px;border:1px solid var(--border-color);border-radius:7px;font-size:12px;background:var(--bg-primary);color:var(--text-primary)">
                </div>
            </div>
            <div style="border-top:1px solid var(--border-color);margin:4px 0;padding-top:4px">
                <div style="font-size:10px;font-weight:600;color:var(--text-muted);text-transform:uppercase;letter-spacing:.5px;margin-bottom:6px">Extension Status Panel</div>
            </div>
            <div>
                <label style="font-size:11px;color:var(--text-muted);display:block;margin-bottom:3px">Überwachte Extensions (kommagetrennt)</label>
                <input id="sp-cfg-status-exts" type="text" placeholder="z.B. 10,12,14,22,24,26"
                    style="width:100%;box-sizing:border-box;padding:5px 8px;border:1px solid var(--border-color);border-radius:7px;font-size:12px;background:var(--bg-primary);color:var(--text-primary)">
            </div>
            <button onclick="Softphone.saveAndRegister()"
                style="padding:8px;background:var(--abcona-blue,#163258);color:#fff;border:none;border-radius:7px;font-size:12px;font-weight:500;cursor:pointer;margin-top:4px">
                <i class="bi bi-save"></i> Speichern &amp; registrieren
            </button>
            <div id="sp-cfg-msg" style="font-size:11px;text-align:center;color:var(--text-muted)"></div>
        </div>
    </div>

</div>

<!-- Transfer Panel -->
<div id="sp-transfer-panel" style="display:none;position:fixed;z-index:9997;width:260px;background:var(--bg-primary,#fff);border:1px solid var(--border-color);border-radius:8px;box-shadow:0 4px 16px rgba(0,0,0,0.15);overflow:hidden;max-height:70vh;overflow-y:auto">
    <div style="padding:6px 10px;font-size:11px;font-weight:600;border-bottom:1px solid #0d2040;background:#163258;color:#fff;display:flex;justify-content:space-between;align-items:center">
        <span>&#8594; Transfer <span id="sp-transfer-active-num" style="font-size:9px;opacity:.7"></span></span>
        <span onclick="Softphone.toggleTransfer()" style="cursor:pointer">&#10005;</span>
    </div>
    <div style="padding:6px 8px;border-bottom:0.5px solid var(--border-color)">
        <div style="display:flex;gap:4px">
            <input id="sp-transfer-input" type="text" placeholder="Nummer eingeben..."
                style="flex:1;padding:4px 7px;border:0.5px solid var(--border-color);border-radius:5px;font-size:11px;background:var(--bg-primary,#fff);color:var(--text-primary)"
                onkeydown="if(event.key==='Enter')Softphone._confirmTransfer(this.value)">
            <button onclick="Softphone._confirmTransfer(document.getElementById('sp-transfer-input').value)"
                style="padding:4px 8px;background:#163258;color:#fff;border:none;border-radius:5px;font-size:10px;cursor:pointer;white-space:nowrap">&#8594; Transfer</button>
        </div>
    </div>
    <div style="padding:4px 8px;border-bottom:0.5px solid var(--border-color)">
        <input id="sp-transfer-search" type="text" placeholder="Kontakt suchen..."
            style="width:100%;box-sizing:border-box;padding:4px 7px;border:0.5px solid var(--border-color);border-radius:5px;font-size:11px;background:var(--bg-primary,#fff);color:var(--text-primary)"
            oninput="Softphone._transferSearch(this.value)">
        <div id="sp-transfer-search-results"></div>
    </div>
    <div id="sp-transfer-body"></div>
</div>

<!-- Letzte Anrufe Panel -->
<div id="sp-recent-panel" style="display:none;position:fixed;z-index:9997;width:260px;background:var(--bg-primary,#fff);border:1px solid var(--border-color);border-radius:8px;box-shadow:0 4px 16px rgba(0,0,0,0.15);overflow:hidden;max-height:60vh;overflow-y:auto">
    <div style="padding:6px 10px;font-size:11px;font-weight:600;border-bottom:1px solid #0d2040;background:#163258;color:#fff;display:flex;justify-content:space-between;align-items:center">
        <span>Letzte Anrufe</span>
        <span onclick="Softphone.toggleRecent()" style="cursor:pointer">&#10005;</span>
    </div>
    <div id="sp-recent-body"></div>
</div>

<!-- Incoming Call -->
<div id="sp-incoming" style="display:none;position:fixed;top:20px;right:20px;z-index:10000;width:260px;background:var(--bg-primary,#fff);border:2px solid #22c55e;border-radius:12px;box-shadow:0 8px 32px rgba(0,0,0,0.22);overflow:hidden;font-size:12px">
    <div style="background:#22c55e;color:#fff;padding:8px 12px;text-align:center;font-size:11px;font-weight:500">
        <i class="bi bi-telephone-inbound-fill"></i> Eingehender Anruf…
    </div>
    <div style="text-align:center;padding:14px 12px 8px">
        <div id="sp-inc-avatar" style="width:48px;height:48px;border-radius:50%;background:#d1fae5;color:#065f46;display:flex;align-items:center;justify-content:center;font-size:16px;font-weight:600;margin:0 auto 8px"></div>
        <div id="sp-inc-name" style="font-size:14px;font-weight:600;color:var(--text-primary,#111)"></div>
        <div id="sp-inc-num" style="font-size:11px;color:var(--text-muted);margin-top:2px"></div>
    </div>
    <div style="display:flex;gap:8px;padding:8px 12px 12px">
        <button onclick="Softphone.answer()" style="flex:1;background:#22c55e;color:#fff;border:none;border-radius:7px;padding:8px;font-size:12px;font-weight:500;cursor:pointer">
            <i class="bi bi-telephone-fill"></i> Annehmen</button>
        <button onclick="Softphone.reject()" style="flex:1;background:#ef4444;color:#fff;border:none;border-radius:7px;padding:8px;font-size:12px;font-weight:500;cursor:pointer">
            <i class="bi bi-telephone-x-fill"></i> Ablehnen</button>
    </div>
</div>

<!-- PWA Install Banner -->
<div id="sp-install-banner">
    <i class="bi bi-download"></i>
    <span>Als App installieren</span>
    <button onclick="SP_PWA.install()" style="background:rgba(255,255,255,0.2);border:none;color:#fff;padding:3px 10px;border-radius:10px;cursor:pointer;font-size:11px">Installieren</button>
    <button onclick="document.getElementById('sp-install-banner').classList.remove('visible')" style="background:none;border:none;color:rgba(255,255,255,0.6);cursor:pointer;font-size:14px">&#10005;</button>
</div>

<!-- JS -->
<script src="{% static 'abpe_crm/softphone/js/vendor/jssip.min.js' %}"></script>
<script src="{% static 'abpe_crm/softphone/js/2_sp-config.js' %}"></script>
<script src="{% static 'abpe_crm/softphone/js/3_sp-i18n.js' %}"></script>
<script src="{% static 'abpe_crm/softphone/js/4_sp-theme.js' %}"></script>
<script src="{% static 'abpe_crm/softphone/js/5_sp-contacts.js' %}"></script>
<script src="{% static 'abpe_crm/softphone/js/6_sp-core.js' %}"></script>
<script src="{% static 'abpe_crm/softphone/js/7_sp-ui.js' %}"></script>
<script src="{% static 'abpe_crm/softphone/js/8_sp-status.js' %}"></script>
<script src="{% static 'abpe_crm/softphone/js/9_sp-transfer.js' %}"></script>
<script src="{% static 'abpe_crm/softphone/js/10_sp-fop.js' %}"></script>
<script src="{% static 'abpe_crm/softphone/js/11_sp-init.js' %}"></script>

<script>
// Keyboard-Shortcuts
document.addEventListener('keydown', function(e) {
    if (['INPUT','TEXTAREA','SELECT'].includes(document.activeElement?.tagName)) return;
    if (e.ctrlKey || e.altKey || e.metaKey) {
        if (e.ctrlKey && e.key === 'c') {
            var d = document.getElementById('sp-display');
            var num = d ? d.textContent.trim() : '';
            if (num && num !== '\u00a0') navigator.clipboard.writeText(num).catch(function(){});
        }
        return;
    }
    if (e.key === 'Delete' || e.key === 'Escape') { Softphone.clearDisplay(); }
    else if (e.key === 'Backspace') { Softphone.backspace(); }
    else if (e.key === 'Enter') { Softphone.call(); }
    else if (/^[0-9*#+]$/.test(e.key)) { Softphone.press(e.key); }
});
document.addEventListener('paste', function(e) {
    if (['INPUT','TEXTAREA','SELECT'].includes(document.activeElement?.tagName)) return;
    var text = (e.clipboardData || window.clipboardData).getData('text');
    if (!text) return;
    var num = text.replace(/[^0-9+*#]/g, '').trim();
    if (num) { e.preventDefault(); Softphone.setNumber(num); }
});
document.addEventListener('click', function(e) {
    var btn = e.target.closest('[data-sp-call]');
    if (btn) { e.preventDefault(); Softphone.setNumber(btn.dataset.spCall); }
});

// PWA Install
window.SP_PWA = {
    _prompt: null,
    install: function() {
        if (this._prompt) {
            this._prompt.prompt();
            this._prompt.userChoice.then(function() {
                document.getElementById('sp-install-banner').classList.remove('visible');
            });
        }
    }
};
window.addEventListener('beforeinstallprompt', function(e) {
    e.preventDefault();
    window.SP_PWA._prompt = e;
    document.getElementById('sp-install-banner').classList.add('visible');
});
</script>

<!-- PWA Service Worker — Registrierung in 11_sp-init.js -->
</body>
</html>
HTMLEOF

ok "softphone.html geschrieben ($(wc -l < "$SP_TMPL") Zeilen)"
echo

# ── 4_sp-theme.js — toggle() ergänzen ────────────────────
info "4_sp-theme.js — toggle() Methode prüfen/ergänzen"

SP_THEME="apps/abpe_crm/static/abpe_crm/softphone/js/4_sp-theme.js"

if grep -q "function toggle" "$SP_THEME"; then
    ok "toggle() bereits vorhanden"
else
    python3 << 'PYEOF'
with open("apps/abpe_crm/static/abpe_crm/softphone/js/4_sp-theme.js", "r") as f:
    c = f.read()

old = "    return { set, init };"
new = """    function toggle() {
        var current = document.documentElement.getAttribute('data-theme') || 'light';
        var next = current === 'dark' ? 'light' : 'dark';
        set(next);
        var btn = document.getElementById('sp-theme-btn');
        if (btn) btn.querySelector('i').className = next === 'dark' ? 'bi bi-sun' : 'bi bi-moon';
    }
    return { set, init, toggle };"""

assert old in c, "FEHLER: return-Zeile nicht gefunden in 4_sp-theme.js"
c = c.replace(old, new, 1)
assert "toggle" in c

with open("apps/abpe_crm/static/abpe_crm/softphone/js/4_sp-theme.js", "w") as f:
    f.write(c)
print("✓  toggle() in 4_sp-theme.js ergänzt")
PYEOF
    node --check "$SP_THEME" && ok "4_sp-theme.js Syntax OK" || warn "4_sp-theme.js Syntax-Warnung"
fi
echo

# ── mod-softphone.js: toggle() anpassen ──────────────────
info "mod-softphone.js: Softphone.toggle() für Standalone patchen"
info "  Im Standalone ist sp-modal immer display:block — toggle() darf nicht display:none setzen"

MOD_SP="apps/abpe_crm/static/abpe_crm/js/mod-softphone.js"
# NICHT anfassen — mod-softphone.js ist produktiver Code
# Stattdessen: 2_sp-config.js prüft ob wir im Standalone sind
# und überschreibt Softphone.toggle() nach dem Laden

SP_CONFIG="apps/abpe_crm/static/abpe_crm/softphone/js/2_sp-config.js"
if grep -q "standalone" "$SP_CONFIG"; then
    ok "Standalone-Flag bereits in 2_sp-config.js"
else
    python3 << 'PYEOF'
with open("apps/abpe_crm/static/abpe_crm/softphone/js/2_sp-config.js", "r") as f:
    c = f.read()

# Ans Ende anfügen
addition = """
// Standalone-Modus: Diese Seite IST das Softphone — kein Modal-Toggle nötig
window.SP_STANDALONE = true;
"""

assert addition.strip() not in c
c = c.rstrip() + "\n" + addition

with open("apps/abpe_crm/static/abpe_crm/softphone/js/2_sp-config.js", "w") as f:
    f.write(c)
print("✓  SP_STANDALONE Flag in 2_sp-config.js gesetzt")
PYEOF
    node --check "$SP_CONFIG" && ok "2_sp-config.js Syntax OK" || warn "2_sp-config.js Syntax-Warnung"
fi
echo

# ── 11_sp-init.js: Standalone-Init ergänzen ──────────────
info "11_sp-init.js: Standalone-Init (Softphone.init() aufrufen)"

SP_INIT="apps/abpe_crm/static/abpe_crm/softphone/js/11_sp-init.js"

if grep -q "Softphone.init" "$SP_INIT"; then
    ok "Softphone.init() bereits in 11_sp-init.js"
else
    python3 << 'PYEOF'
with open("apps/abpe_crm/static/abpe_crm/softphone/js/11_sp-init.js", "r") as f:
    c = f.read()

old = "    console.log('ABpE Softphone bereit.');"
new = """    // Standalone: Softphone direkt initialisieren (kein toggle() nötig)
    if (window.SP_STANDALONE && typeof Softphone !== 'undefined') {
        // sp-modal ist per CSS immer sichtbar — nur init() aufrufen
        document.addEventListener('DOMContentLoaded', function() {
            if (typeof Softphone !== 'undefined' && Softphone.init) {
                Softphone.init();
            }
            if (typeof Softphone !== 'undefined' && Softphone._loadExtSettings) {
                setTimeout(function() { Softphone._loadExtSettings(); }, 500);
            }
            // Ladeindikator entfernen (falls vorhanden)
            var loading = document.getElementById('sp-loading');
            if (loading) loading.style.display = 'none';
        });
    }
    console.log('ABpE Softphone bereit.');"""

assert old in c, "FEHLER: console.log-Zeile nicht gefunden"
c = c.replace(old, new, 1)

with open("apps/abpe_crm/static/abpe_crm/softphone/js/11_sp-init.js", "w") as f:
    f.write(c)
print("✓  Standalone-Init in 11_sp-init.js ergänzt")
PYEOF
    node --check "$SP_INIT" && ok "11_sp-init.js Syntax OK" || err "11_sp-init.js Syntax FEHLER"
fi
echo

# ── Deploy ────────────────────────────────────────────────
info "Deploy…"
python3 manage.py collectstatic --noinput 2>&1 | tail -3
echo
supervisorctl restart abpe-django
sleep 2
supervisorctl status abpe-django
echo

echo "════════════════════════════════════════════════════"
echo -e "${GREEN}UI Deploy abgeschlossen${NC}"
echo "════════════════════════════════════════════════════"
echo
echo "Testen:"
echo "  https://abpe.win.abcona.info/crm/softphone/"
echo
echo "Erwartet:"
echo "  - Dunkelblaue Seite mit Softphone-Widget zentriert"
echo "  - Tastatur sichtbar, Einstellungen-Tab funktioniert"
echo "  - Kein JS-Fehler in der Console"
echo "  - Moon-Icon oben rechts für Dark/Light Toggle"

