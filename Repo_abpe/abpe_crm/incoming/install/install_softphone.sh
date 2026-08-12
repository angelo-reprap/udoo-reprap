#!/usr/bin/env bash
# ============================================================
# install_softphone.sh — ABpE Softphone PWA Kapselung
# Ablage:  apps/abpe_crm/install/install_softphone.sh
# Aufruf:  bash apps/abpe_crm/install/install_softphone.sh
# Voraus.: /opt/abpe/backend/ als CWD, venv311 aktiv
# ============================================================
set -euo pipefail

# ── Farben ────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; NC='\033[0m'

ok()   { echo -e "${GREEN}✓${NC} $*"; }
warn() { echo -e "${YELLOW}⚠${NC}  $*"; }
err()  { echo -e "${RED}✗${NC}  $*"; exit 1; }
info() { echo -e "${BLUE}▶${NC}  $*"; }

# ── Pfade ─────────────────────────────────────────────────
BASE="/opt/abpe/backend"
APP="apps/abpe_crm"
STATIC="${APP}/static/abpe_crm"
SP_STATIC="${STATIC}/softphone"
SP_TMPL="${APP}/templates/abpe_crm/softphone"
VIEWS="${APP}/views.py"
ARCHIVE_SCRIPT="Archiv/backup_restore.py"

# ── Sanity checks ─────────────────────────────────────────
info "Starte ABpE Softphone Installation"
echo "────────────────────────────────────────────────────"

[[ "$(pwd)" == "$BASE" ]] || err "Bitte aus $BASE ausführen (aktuell: $(pwd))"
[[ -f "${APP}/views.py" ]] || err "views.py nicht gefunden — falsches Verzeichnis?"
[[ -f "${STATIC}/js/jssip.min.js" ]] || err "jssip.min.js nicht gefunden unter ${STATIC}/js/"
[[ -f "$ARCHIVE_SCRIPT" ]] || err "Backup-Script nicht gefunden: $ARCHIVE_SCRIPT"
python3 -c "import django" 2>/dev/null || err "Django nicht verfügbar — venv311 aktiv?"

ok "Sanity checks bestanden"
echo

# ── Schritt 1: Backup relevanter Dateien ─────────────────
info "Schritt 1/8 — Backup"

python3 "$ARCHIVE_SCRIPT" -save "${SP_TMPL}/softphone.html" \
    -m "vor softphone install: softphone.html Platzhalter" 2>/dev/null || \
    warn "softphone.html Backup übersprungen (Datei evtl. noch nicht vorhanden)"

python3 "$ARCHIVE_SCRIPT" -save "$VIEWS" \
    -m "vor softphone install: views.py" || err "Backup views.py fehlgeschlagen"

ok "Backup abgeschlossen"
echo

# ── Schritt 2: Verzeichnisse ──────────────────────────────
info "Schritt 2/8 — Verzeichnisse anlegen"

mkdir -p "${SP_STATIC}/css"
mkdir -p "${SP_STATIC}/i18n"
mkdir -p "${SP_STATIC}/icons"
mkdir -p "${SP_STATIC}/js"
mkdir -p "${SP_STATIC}/js/vendor"
mkdir -p "${SP_TMPL}"

ok "Verzeichnisse OK"
echo

# ── Schritt 3: jssip.min.js kopieren ─────────────────────
info "Schritt 3/8 — jssip.min.js → vendor/"

JSSIP_SRC="${STATIC}/js/jssip.min.js"
JSSIP_DST="${SP_STATIC}/js/vendor/jssip.min.js"

if [[ -f "$JSSIP_DST" ]]; then
    warn "jssip.min.js bereits vorhanden — überspringe"
else
    cp "$JSSIP_SRC" "$JSSIP_DST"
    ok "jssip.min.js kopiert ($(du -h "$JSSIP_DST" | cut -f1))"
fi
echo

# ── Schritt 4: JS-Stubs anlegen ───────────────────────────
info "Schritt 4/8 — JS-Module anlegen (Stubs)"

declare -A JS_FILES=(
    ["2_sp-config.js"]="// sp-config.js — Config laden (Django API oder config.json)
// Priorität: 1. Django API /crm/api/user-settings/  2. config.json  3. window.SP_CONFIG
window.SP_CONFIG = window.SP_CONFIG || {
    api_base:     '/crm/api',
    contacts_url: '/crm/api/softphone/contacts/',
    ws:           '',
    extension:    '',
    password:     '',
    display:      '',
};
// TODO: Config von API laden und SP_CONFIG befüllen"

    ["3_sp-i18n.js"]="// sp-i18n.js — Internationalisierung
// SP_i18n.t('key'), SP_i18n.load('de')
window.SP_i18n = (function() {
    let _lang = 'de';
    let _data = {};
    async function load(lang) {
        try {
            const r = await fetch('./i18n/' + lang + '_phone.json');
            _data = await r.json();
            _lang = lang;
        } catch(e) { console.warn('SP_i18n: Sprache nicht geladen:', lang, e); }
    }
    function t(key, fallback) {
        return _data[key] || fallback || key;
    }
    return { load, t, get lang() { return _lang; } };
})();
// TODO: Sprachdateien laden und auf DOM anwenden"

    ["4_sp-theme.js"]="// sp-theme.js — Dark/Light Mode
// SP_Theme.set('dark'), SP_Theme.set('light')
window.SP_Theme = (function() {
    function set(mode) {
        document.documentElement.setAttribute('data-theme', mode);
        try { localStorage.setItem('sp_theme', mode); } catch(e) {}
    }
    function init() {
        const saved = (() => { try { return localStorage.getItem('sp_theme'); } catch(e) { return null; } })();
        const preferred = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
        set(saved || preferred);
    }
    return { set, init };
})();
// TODO: CSS-Variablen für beide Modi definieren in softphone.css"

    ["5_sp-contacts.js"]="// sp-contacts.js — Adressbuch
// Lookup-Logik:
//   1. pbx_extensions[X]  → intern (sofort)
//   2. contacts[].phones  → lokal JSON
//   3. api_base/berater/?q=X → CRM lazy
//   4. nur Nummer anzeigen
window.SP_Contacts = (function() {
    let _contacts = [];
    let _extensions = {};
    async function load(url) {
        try {
            const r = await fetch(url || window.SP_CONFIG.contacts_url);
            _contacts = await r.json();
        } catch(e) { console.warn('SP_Contacts: Laden fehlgeschlagen', e); }
    }
    function setExtensions(map) { _extensions = map || {}; }
    async function lookup(num) {
        if (!num) return null;
        if (_extensions[num]) return _extensions[num];
        const c = _contacts.find(function(c) {
            return (c.phones || []).some(function(p) { return p.norm === num || p.raw === num; });
        });
        if (c) return c.full_name || c.name || null;
        if (window.SP_CONFIG.api_base) {
            try {
                const r = await fetch(window.SP_CONFIG.api_base + '/berater/?q=' + encodeURIComponent(num) + '&per_page=1&typ=alle');
                const d = await r.json();
                const first = (d.results || d.berater || [])[0];
                if (first) return (first.first_name || '') + ' ' + (first.last_name || '');
            } catch(e) {}
        }
        return null;
    }
    function search(q, limit) {
        if (!q || q.length < 2) return [];
        q = q.toLowerCase();
        return _contacts.filter(function(c) {
            return (c.full_name || c.name || '').toLowerCase().includes(q) ||
                   (c.phones || []).some(function(p) { return (p.norm || p.raw || '').includes(q); });
        }).slice(0, limit || 8);
    }
    return { load, lookup, search, setExtensions };
})();
// TODO: Kontakte beim Start laden"

    ["6_sp-core.js"]="// sp-core.js — JsSIP Init, Call/Hangup
// Extrahiert aus mod-softphone.js — wird in Schritt 3 des neuen Chats befüllt
// TODO: JsSIP UA init, _register(), call(), hangup(), answer(), reject() hierher"

    ["7_sp-ui.js"]="// sp-ui.js — Display, Tastatur, Buttons
// Extrahiert aus telefon_tab.html + mod-softphone.js
// TODO: press(), backspace(), clearDisplay(), setNumber(), showTab() hierher"

    ["8_sp-status.js"]="// sp-status.js — VM/DND/FWD Indikatoren
// Extrahiert aus mod-softphone-ext.js
// TODO: _updateStatusIndicators(), toggleDND(), callForward() hierher"

    ["9_sp-transfer.js"]="// sp-transfer.js — Transfer/Ankündigung
// Extrahiert aus mod-softphone-ext.js
// TODO: toggleTransfer(), doTransfer(), _confirmTransfer(), _doBlindTransfer(),
//       _doAnnounceTransfer(), _finishAnnounce(), _cancelAnnounce() hierher"

    ["10_sp-fop.js"]="// sp-fop.js — FOP Panel, Schnellwahl, CDR
// Extrahiert aus mod-softphone-ext.js
// TODO: toggleFOP(), _renderFOP(), toggleSpeedDial(), _renderSpeedDials(),
//       showRecent(), _renderRecent() hierher"

    ["11_sp-init.js"]="// sp-init.js — Alles zusammenführen, PWA init
// Dieser Einstiegspunkt lädt alle Module in der richtigen Reihenfolge
(async function() {
    // 1. Theme
    if (window.SP_Theme) SP_Theme.init();

    // 2. Config von Django API laden (wenn eingeloggt)
    // 3. i18n initialisieren
    // 4. Kontakte laden
    // 5. Core (JsSIP) initialisieren
    // 6. PWA Service Worker registrieren
    if ('serviceWorker' in navigator) {
        try {
            await navigator.serviceWorker.register('./service-worker.js');
            console.log('SP: Service Worker registriert');
        } catch(e) { console.warn('SP: Service Worker Fehler', e); }
    }
    console.log('ABpE Softphone bereit.');
})();
// TODO: Vollständige Initialisierung aller Module"
)

for fname in "${!JS_FILES[@]}"; do
    fpath="${SP_STATIC}/js/${fname}"
    if [[ -f "$fpath" ]]; then
        warn "  ${fname} bereits vorhanden — überspringe"
    else
        echo "${JS_FILES[$fname]}" > "$fpath"
        python3 --version > /dev/null 2>&1  # venv check
        node --check "$fpath" 2>/dev/null && ok "  ${fname}" || warn "  ${fname} (JS-Check fehlgeschlagen)"
    fi
done
echo

# ── Schritt 5: CSS-Stub ───────────────────────────────────
info "Schritt 5/8 — softphone.css anlegen"

CSS_FILE="${SP_STATIC}/css/softphone.css"
if [[ -f "$CSS_FILE" ]]; then
    warn "softphone.css bereits vorhanden — überspringe"
else
cat > "$CSS_FILE" << 'CSSEOF'
/* softphone.css — ABpE Softphone PWA
 * CSS-Variablen spiegeln core-theme.css für Light/Dark Mode
 * Eigenständig nutzbar ohne Django-Kontext
 */

/* ── CSS-Variablen Light Mode ────────────────────────── */
:root {
    --abcona-blue:      #163258;
    --abcona-blue-dark: #0f2442;
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

/* ── Reset & Base ────────────────────────────────────── */
* { box-sizing: border-box; margin: 0; padding: 0; }

body {
    font-family: 'Segoe UI', Arial, sans-serif;
    background: var(--bg-secondary);
    color: var(--text-primary);
    font-size: 13px;
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

/* ── Status-Dot ──────────────────────────────────────── */
.sp-status-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: #9ca3af;
    display: inline-block;
}

/* TODO: Vollständiges CSS aus telefon_tab.html <style>-Block
   und allen inline-styles extrahieren (Schritt 2 im neuen Chat) */
CSSEOF
    ok "softphone.css angelegt"
fi
echo

# ── Schritt 6: i18n JSON-Dateien ─────────────────────────
info "Schritt 6/8 — i18n Sprachdateien anlegen"

# Nur DE komplett — andere sind Stubs für Übersetzung
cat > "${SP_STATIC}/i18n/de_phone.json" << 'I18N_DE'
{
    "softphone": "Softphone",
    "dial": "Wählen",
    "settings": "Einstellungen",
    "not_connected": "Nicht verbunden",
    "registered": "Registriert",
    "not_registered": "Nicht registriert",
    "error": "Fehler",
    "pin_position": "Position fixieren",
    "close": "Schließen",
    "search_contact": "Kontakt suchen…",
    "recent": "Zuletzt",
    "backspace": "Löschen",
    "clear": "C",
    "call": "Anrufen",
    "hangup": "Auflegen",
    "answer": "Annehmen",
    "reject": "Ablehnen",
    "mute": "Stummschalten",
    "unmute": "Stummschaltung aufheben",
    "voicemail": "Voicemail",
    "voicemail_listen": "abhören",
    "forward": "Weiterleitung",
    "dnd": "Nicht stören",
    "dnd_active": "Nicht stören aktiv",
    "pickup": "Pickup",
    "transfer": "Transfer",
    "speed_dial": "Schnellwahl",
    "calls": "Anrufe",
    "status": "Status",
    "ext_status": "Ext. Status",
    "incoming_call": "Eingehender Anruf…",
    "sip_user": "SIP Benutzer",
    "sip_password": "SIP Passwort",
    "websocket_url": "WebSocket URL",
    "display_name": "Anzeigename",
    "vm_extension": "VM-Nebenstelle",
    "dnd_extension": "DND-Nebenstelle",
    "status_extensions": "Überwachte Extensions (kommagetrennt)",
    "save_register": "Speichern & registrieren",
    "saved": "Gespeichert.",
    "save_failed": "Speichern fehlgeschlagen.",
    "not_registered_alert": "Softphone nicht registriert. Bitte Einstellungen prüfen.",
    "loading": "Lade…",
    "no_entries": "Keine Einträge",
    "no_speed_dial": "Keine Schnellwahl konfiguriert.",
    "speed_dial_hint": "Kontakt aus Suche hierher ziehen.",
    "add_manual": "Manuell hinzufügen",
    "add_company": "+Firma",
    "cancel": "Abbrechen",
    "add": "Hinzufügen",
    "label": "Bezeichnung",
    "number": "Nummer",
    "no_extensions": "Keine Extensions",
    "missed": "Abwesenheit",
    "answered": "Angenommen",
    "dialed": "Gewählt",
    "no_calls": "Keine Einträge",
    "transfer_to": "Transfer zu",
    "direct": "Direkt",
    "announce": "Ankündigen",
    "transfer_success": "Anruf weitergeleitet an",
    "extensions": "EXTENSIONS",
    "parking": "PARKING 700",
    "conferences": "KONFERENZEN",
    "participants": "Tlnhm.",
    "empty": "leer",
    "pickup_btn": "Abholen",
    "park_btn": "Park",
    "conf_join": "Konf",
    "call_btn": "Anrufen",
    "dnd_on": "DND an",
    "dnd_off": "DND aus",
    "free": "frei",
    "busy": "besetzt",
    "offline": "offline",
    "forwarding": "Weiterleitung",
    "vm_new": "neu",
    "vm_listen": "Abhören",
    "forward_target": "Weiterleitungsziel",
    "transfer_panel_title": "Transfer",
    "search_contact_transfer": "Kontakt suchen...",
    "free_extensions": "Nebenstellen — frei",
    "no_free_extensions": "Keine freien Nebenstellen",
    "last_calls": "Letzte Anrufe",
    "copy_number": "Nummer kopiert",
    "timer_format": "m:ss",
    "new_voicemail": "neue Voicemail-Nachricht",
    "new_voicemails": "neue Voicemail-Nachrichten",
    "company_search": "Firmaname suchen...",
    "no_results": "Keine Treffer",
    "contact_persons": "Ansprechpartner",
    "transfer_active": "Transfer",
    "announce_to": "Ankündigung an",
    "transfer_btn": "Transferieren",
    "back_btn": "Zurück",
    "enter_number": "Nummer eingeben...",
    "pwa_install": "Als App installieren",
    "pwa_install_hint": "Softphone als Desktop-App installieren"
}
I18N_DE
ok "de_phone.json (vollständig)"

# Stubs für andere Sprachen — werden per i18n_translator.py übersetzt
for lang in en fr es it pl; do
    fpath="${SP_STATIC}/i18n/${lang}_phone.json"
    if [[ -f "$fpath" ]]; then
        warn "  ${lang}_phone.json bereits vorhanden — überspringe"
    else
        echo '{}' > "$fpath"
        ok "  ${lang}_phone.json (Stub — TODO: übersetzen)"
    fi
done
echo

# ── Schritt 7: PWA-Dateien ────────────────────────────────
info "Schritt 7/8 — PWA manifest.json + service-worker.js + Icons"

# manifest.json
cat > "${SP_STATIC}/manifest.json" << 'MANIFEST'
{
    "name": "ABpE Softphone",
    "short_name": "Softphone",
    "description": "ABpE CRM Softphone — Browser-basiertes SIP Telefon",
    "start_url": "/crm/softphone/",
    "display": "standalone",
    "background_color": "#163258",
    "theme_color": "#163258",
    "orientation": "portrait-primary",
    "icons": [
        {
            "src": "icons/icon-192.png",
            "sizes": "192x192",
            "type": "image/png",
            "purpose": "any maskable"
        },
        {
            "src": "icons/icon-512.png",
            "sizes": "512x512",
            "type": "image/png",
            "purpose": "any maskable"
        }
    ],
    "shortcuts": [
        {
            "name": "Wählen",
            "url": "/crm/softphone/#dial",
            "description": "Direkt zum Wählen"
        }
    ]
}
MANIFEST
ok "manifest.json"

# service-worker.js
cat > "${SP_STATIC}/js/service-worker.js" << 'SWEOF'
// service-worker.js — ABpE Softphone PWA Service Worker
const CACHE_NAME = 'abpe-softphone-v1';

// Dateien die offline verfügbar sein sollen
const PRECACHE = [
    '/crm/softphone/',
    '/static/abpe_crm/softphone/css/softphone.css',
    '/static/abpe_crm/softphone/js/vendor/jssip.min.js',
    '/static/abpe_crm/softphone/js/2_sp-config.js',
    '/static/abpe_crm/softphone/js/3_sp-i18n.js',
    '/static/abpe_crm/softphone/js/4_sp-theme.js',
    '/static/abpe_crm/softphone/js/5_sp-contacts.js',
    '/static/abpe_crm/softphone/js/6_sp-core.js',
    '/static/abpe_crm/softphone/js/7_sp-ui.js',
    '/static/abpe_crm/softphone/js/8_sp-status.js',
    '/static/abpe_crm/softphone/js/9_sp-transfer.js',
    '/static/abpe_crm/softphone/js/10_sp-fop.js',
    '/static/abpe_crm/softphone/js/11_sp-init.js',
    '/static/abpe_crm/softphone/i18n/de_phone.json',
    '/static/abpe_crm/softphone/manifest.json',
];

self.addEventListener('install', function(e) {
    e.waitUntil(
        caches.open(CACHE_NAME).then(function(cache) {
            // Fehler beim Precache einzelner Dateien nicht fatal machen
            return Promise.allSettled(
                PRECACHE.map(function(url) { return cache.add(url); })
            );
        })
    );
    self.skipWaiting();
});

self.addEventListener('activate', function(e) {
    e.waitUntil(
        caches.keys().then(function(keys) {
            return Promise.all(
                keys.filter(function(k) { return k !== CACHE_NAME; })
                    .map(function(k) { return caches.delete(k); })
            );
        })
    );
    self.clients.claim();
});

self.addEventListener('fetch', function(e) {
    // API-Calls und WS-Verbindungen nie cachen
    const url = e.request.url;
    if (url.includes('/crm/api/') || url.startsWith('wss://') || url.startsWith('ws://')) {
        return;
    }

    e.respondWith(
        caches.match(e.request).then(function(cached) {
            if (cached) return cached;
            return fetch(e.request).catch(function() {
                // Offline-Fallback: Startseite aus Cache
                if (e.request.mode === 'navigate') {
                    return caches.match('/crm/softphone/');
                }
            });
        })
    );
});
SWEOF
node --check "${SP_STATIC}/js/service-worker.js" && ok "service-worker.js" || warn "service-worker.js (JS-Check fehlgeschlagen)"

# Icons per Python generieren (kein PIL nötig — reines Python PNG)
python3 << 'PYEOF'
import struct, zlib, os

def make_png(size, bg_rgb, fg_rgb):
    """Minimales PNG erzeugen ohne externe Libraries."""
    w = h = size
    # Icon: blaues Quadrat mit weißem Telefon-Symbol (vereinfacht: farbiges Quadrat)
    # Pixel-Daten: RGBA
    center = size // 2
    r_outer = int(size * 0.35)
    img = []
    for y in range(h):
        row = []
        for x in range(w):
            dx = x - center
            dy = y - center
            dist = (dx*dx + dy*dy) ** 0.5
            # Weißer Kreis in der Mitte als "Telefon-Symbol"
            if dist < r_outer * 0.6:
                row += [*fg_rgb, 255]
            else:
                row += [*bg_rgb, 255]
        img.append(row)

    def pack_chunk(tag, data):
        c = zlib.crc32(tag + data) & 0xffffffff
        return struct.pack('>I', len(data)) + tag + data + struct.pack('>I', c)

    ihdr = struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0)
    raw  = b''
    for row in img:
        raw += b'\x00' + bytes(row)
    idat = zlib.compress(raw)

    return (
        b'\x89PNG\r\n\x1a\n' +
        pack_chunk(b'IHDR', ihdr) +
        pack_chunk(b'IDAT', idat) +
        pack_chunk(b'IEND', b'')
    )

icon_dir = "apps/abpe_crm/static/abpe_crm/softphone/icons"
os.makedirs(icon_dir, exist_ok=True)

bg = (22, 50, 88)    # #163258 abcona-blue
fg = (255, 255, 255) # weiß

for size in [192, 512]:
    path = f"{icon_dir}/icon-{size}.png"
    if not os.path.exists(path):
        data = make_png(size, bg, fg)
        with open(path, 'wb') as f:
            f.write(data)
        print(f"✓  icon-{size}.png ({len(data)} bytes)")
    else:
        print(f"⚠  icon-{size}.png bereits vorhanden — überspringe")
PYEOF
echo

# ── Schritt 8: softphone.html Template ───────────────────
info "Schritt 8/8 — softphone.html Template (minimal lauffähig)"

TMPL_FILE="${SP_TMPL}/softphone.html"
cat > "$TMPL_FILE" << 'HTMLEOF'
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

    <!-- PWA Manifest -->
    <link rel="manifest" href="{% static 'abpe_crm/softphone/manifest.json' %}">
    <link rel="apple-touch-icon" href="{% static 'abpe_crm/softphone/icons/icon-192.png' %}">

    <!-- Bootstrap Icons (CDN — für Standalone ohne Portal) -->
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.0/font/bootstrap-icons.css">

    <!-- Softphone CSS -->
    <link rel="stylesheet" href="{% static 'abpe_crm/softphone/css/softphone.css' %}">

    <!-- Django-Kontext → JS-Config (wenn eingeloggt) -->
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
        // password wird NICHT im Template ausgegeben — wird per API nachgeladen
    };
    window.SP_LANG = 'de';
    </script>
</head>
<body>

<!-- ═══════════════════════════════════════════════════════ -->
<!-- ABpE Softphone PWA — Inhalt wird per JS aufgebaut      -->
<!-- ═══════════════════════════════════════════════════════ -->

<div id="sp-app">
    <!-- Ladeindikator bis JS bereit -->
    <div id="sp-loading" style="
        display:flex;align-items:center;justify-content:center;
        height:100vh;flex-direction:column;gap:12px;
        background:#163258;color:#fff;font-family:sans-serif">
        <div style="font-size:32px">📞</div>
        <div style="font-size:14px;opacity:.7">ABpE Softphone wird geladen…</div>
    </div>
</div>

<!-- ═══════════════════════════════════════════════════════ -->
<!-- JS — Ladereihenfolge ist fix                           -->
<!-- ═══════════════════════════════════════════════════════ -->

<!-- 1. JsSIP -->
<script src="{% static 'abpe_crm/softphone/js/vendor/jssip.min.js' %}"></script>

<!-- 2–11. Softphone Module -->
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

<!-- PWA Service Worker -->
<script>
if ('serviceWorker' in navigator) {
    window.addEventListener('load', function() {
        navigator.serviceWorker.register(
            '{% static "abpe_crm/softphone/js/service-worker.js" %}'
        ).catch(function(e) { console.warn('SW:', e); });
    });
}
</script>

</body>
</html>
HTMLEOF
ok "softphone.html geschrieben"
echo

# ── @login_required Check ────────────────────────────────
info "Prüfe @login_required auf softphone_app()…"

# Prüfen ob decorator fehlt
if grep -A1 'def softphone_app' "$VIEWS" | grep -q '@login_required'; then
    ok "@login_required bereits vorhanden"
elif grep -B1 'def softphone_app' "$VIEWS" | grep -q '@login_required'; then
    ok "@login_required bereits vorhanden"
else
    warn "@login_required fehlt vor softphone_app() — bitte manuell prüfen!"
    warn "grep -n 'softphone_app' $VIEWS"
fi
echo

# ── collectstatic + restart ───────────────────────────────
info "Deployen…"
echo "────────────────────────────────────────────────────"

python3 manage.py collectstatic --noinput 2>&1 | tail -3
echo
supervisorctl restart abpe-django
sleep 2
supervisorctl status abpe-django
echo

# ── Abschluss-Report ──────────────────────────────────────
echo "════════════════════════════════════════════════════"
echo -e "${GREEN}ABpE Softphone Installation abgeschlossen${NC}"
echo "════════════════════════════════════════════════════"
echo ""
echo "Angelegte Struktur:"
find "${SP_STATIC}" -type f | sort | sed 's|^|  |'
echo ""
echo "Template:"
echo "  ${SP_TMPL}/softphone.html"
echo ""
echo "Erreichbar unter:"
echo "  https://pbx.win.abcona.info/crm/softphone/    (extern)"
echo "  http://172.20.3.160/crm/softphone/             (intern)"
echo ""
echo -e "${YELLOW}TODO — nächste Schritte im neuen Chat:${NC}"
echo "  1. de_phone.json → Labels aus mod-softphone.js extrahieren (Schritt 1)"
echo "  2. softphone.css → Inline-Styles aus telefon_tab.html (Schritt 2)"
echo "  3. JS aufteilen → 6_sp-core.js bis 10_sp-fop.js befüllen (Schritt 3)"
echo "  4. softphone.html → vollständige UI bauen (Schritt 4)"
echo "  5. i18n übersetzen → en/fr/es/it/pl_phone.json (Schritt 5)"
echo "  6. @login_required in views.py prüfen/ergänzen"
echo ""
echo "Backup-Archiv prüfen:"
echo "  ls -lt Archiv/archive/ | head -5"
