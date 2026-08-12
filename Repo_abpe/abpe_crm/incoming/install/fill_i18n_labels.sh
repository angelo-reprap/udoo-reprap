#!/usr/bin/env bash
# fill_i18n_labels.sh — Alle hardcodierten Labels → SP_i18n.t('key')
# Aufruf: bash apps/abpe_crm/install/fill_i18n_labels.sh
# CWD:    /opt/abpe/backend/
set -euo pipefail
GREEN='\033[0;32m'; BLUE='\033[0;34m'; NC='\033[0m'
ok()   { echo -e "${GREEN}✓${NC} $*"; }
info() { echo -e "${BLUE}▶${NC}  $*"; }

BASE="/opt/abpe/backend"
APP="apps/abpe_crm"
JS6="${APP}/static/abpe_crm/softphone/js/6_sp-core.js"
JS8="${APP}/static/abpe_crm/softphone/js/8_sp-status.js"
JS9="${APP}/static/abpe_crm/softphone/js/9_sp-transfer.js"
JS10="${APP}/static/abpe_crm/softphone/js/10_sp-fop.js"
TMPL="${APP}/templates/abpe_crm/softphone/softphone.html"
I18N="${APP}/static/abpe_crm/softphone/js/3_sp-i18n.js"
DE="${APP}/static/abpe_crm/softphone/i18n/de_phone.json"

[[ "$(pwd)" == "$BASE" ]] || { echo "Falsches Verzeichnis"; exit 1; }

info "Backups"
for f in "$JS6" "$JS8" "$JS9" "$JS10" "$TMPL" "$I18N"; do
    python3 Archiv/backup_restore.py -save "$f" -m "vor i18n labels" || exit 1
done
ok "Backups OK"
echo

# ══════════════════════════════════════════════════════════
# SCHRITT 1: de_phone.json — fehlende Keys ergänzen
# ══════════════════════════════════════════════════════════
info "Schritt 1/7 — de_phone.json: fehlende Keys ergänzen"

python3 << 'PYEOF'
import json

with open("apps/abpe_crm/static/abpe_crm/softphone/i18n/de_phone.json", "r") as f:
    d = json.load(f)

new_keys = {
    "unknown":            "unbekannt",
    "unknown_short":      "?",
    "alert_vm_missing":   "Bitte VM-Nebenstelle in den Einstellungen konfigurieren.",
    "alert_dnd_missing":  "Bitte DND-Nebenstelle in den Einstellungen konfigurieren.",
    "alert_ext_missing":  "Bitte eigene Extension in den Einstellungen konfigurieren.",
    "alert_no_session":   "Kein aktives Gespräch für Transfer.",
    "alert_held_gone":    "Gehaltener Anruf nicht mehr aktiv.",
    "alert_park_failed":  "Parken fehlgeschlagen",
    "alert_conf_failed":  "Konferenz fehlgeschlagen",
    "busy":               "besetzt",
    "offline":            "offline",
    "extensions":         "EXTENSIONS",
    "parking":            "PARKING 700",
    "conferences":        "KONFERENZEN",
    "call_btn":           "Anrufen",
    "dnd_on":             "DND an",
    "dnd_off":            "DND aus",
    "vm_new":             "neu",
    "vm_listen":          "Abhören",
    "pwa_install_btn":    "Installieren",
    "speed_dial_toggle":  "◄ Schnellwahl",
    "calls_toggle":       "✆ Anrufe",
    "status_toggle":      "Status ►",
    "not_connected":      "Nicht verbunden",
    "forward_prompt":     "Weiterleitungsziel:",
}

added = 0
for k, v in new_keys.items():
    if k not in d:
        d[k] = v
        added += 1

with open("apps/abpe_crm/static/abpe_crm/softphone/i18n/de_phone.json", "w", encoding="utf-8") as f:
    json.dump(d, f, ensure_ascii=False, indent=4)
print(f"✓  de_phone.json: {added} neue Keys ergänzt, {len(d)} Keys gesamt")
PYEOF
echo

# ══════════════════════════════════════════════════════════
# SCHRITT 2: 3_sp-i18n.js — t() Funktion vervollständigen
# ══════════════════════════════════════════════════════════
info "Schritt 2/7 — 3_sp-i18n.js: t() mit DOM-Apply ergänzen"

cat > "$I18N" << 'JSEOF'
// 3_sp-i18n.js — Internationalisierung
// SP_i18n.t('key') → übersetzter String oder Fallback
// SP_i18n.load('de') → lädt Sprachdatei
// SP_i18n.apply()   → wendet data-i18n Attribute auf DOM an

window.SP_i18n = (function() {
    var _lang = window.SP_LANG || 'de';
    var _data = {};
    var _loaded = false;

    async function load(lang) {
        try {
            var url = '/static/abpe_crm/softphone/i18n/' + lang + '_phone.json';
            var r = await fetch(url);
            if (r.ok) {
                _data = await r.json();
                _lang = lang;
                _loaded = true;
                apply();
            } else {
                console.warn('SP_i18n: Sprachdatei nicht gefunden:', url);
            }
        } catch(e) {
            console.warn('SP_i18n: Laden fehlgeschlagen:', lang, e);
        }
    }

    function t(key, fallback) {
        return _data[key] || fallback || key;
    }

    // Wendet data-i18n Attribute auf DOM an
    function apply() {
        document.querySelectorAll('[data-i18n]').forEach(function(el) {
            var key = el.getAttribute('data-i18n');
            var val = _data[key];
            if (val) el.textContent = val;
        });
        document.querySelectorAll('[data-i18n-placeholder]').forEach(function(el) {
            var key = el.getAttribute('data-i18n-placeholder');
            var val = _data[key];
            if (val) el.placeholder = val;
        });
        document.querySelectorAll('[data-i18n-title]').forEach(function(el) {
            var key = el.getAttribute('data-i18n-title');
            var val = _data[key];
            if (val) el.title = val;
        });
    }

    function getLang() { return _lang; }
    function isLoaded() { return _loaded; }

    return { load, t, apply, getLang, isLoaded };
})();
JSEOF
node --check "$I18N" && ok "3_sp-i18n.js Syntax OK" || { echo "FEHLER"; exit 1; }
echo

# ══════════════════════════════════════════════════════════
# SCHRITT 3: 11_sp-init.js — i18n beim Start laden
# ══════════════════════════════════════════════════════════
info "Schritt 3/7 — 11_sp-init.js: SP_i18n.load() beim Start aufrufen"

JS11="${APP}/static/abpe_crm/softphone/js/11_sp-init.js"
python3 Archiv/backup_restore.py -save "$JS11" -m "vor i18n init" || exit 1

python3 << 'PYEOF'
with open("apps/abpe_crm/static/abpe_crm/softphone/js/11_sp-init.js", "r") as f:
    c = f.read()

old = "    // 1. Theme\n    if (window.SP_Theme) SP_Theme.init();"
new = """    // 1. Theme
    if (window.SP_Theme) SP_Theme.init();

    // 2. i18n laden
    var lang = window.SP_LANG || 'de';
    if (window.SP_i18n) {
        await SP_i18n.load(lang);
    }"""

assert old in c, "FEHLER: Theme-Init nicht gefunden in 11_sp-init.js"
c = c.replace(old, new, 1)

with open("apps/abpe_crm/static/abpe_crm/softphone/js/11_sp-init.js", "w") as f:
    f.write(c)
print("✓  11_sp-init.js: SP_i18n.load() eingefügt")
PYEOF
node --check "$JS11" && ok "11_sp-init.js Syntax OK" || { echo "FEHLER"; exit 1; }
echo

# ══════════════════════════════════════════════════════════
# SCHRITT 4: 6_sp-core.js Labels → t()
# ══════════════════════════════════════════════════════════
info "Schritt 4/7 — 6_sp-core.js"

python3 << 'PYEOF'
with open("apps/abpe_crm/static/abpe_crm/softphone/js/6_sp-core.js", "r") as f:
    c = f.read()

def t(key, fb=''):
    return "SP_i18n.t('" + key + "'" + (", '" + fb + "'" if fb else '') + ")"

# Status-Texte
c = c.replace(
    "function() { _setStatus('Registriert · ' + cfg.user, '#22c55e'); }",
    "function() { _setStatus(" + t('registered','Registriert') + " + ' \u00b7 ' + cfg.user, '#22c55e'); }"
)
c = c.replace(
    "function() { _setStatus('Nicht registriert', 'var(--dot-offline)'); }",
    "function() { _setStatus(" + t('not_registered','Nicht registriert') + ", 'var(--dot-offline)'); }"
)
c = c.replace(
    "function(e) { _setStatus('Fehler: ' + (e.cause || 'unbekannt'), '#ef4444'); }",
    "function(e) { _setStatus(" + t('error','Fehler') + " + ': ' + (e.cause || " + t('unknown','unbekannt') + "), '#ef4444'); }"
)

# Eingehender Anruf: Unbekannt
c = c.replace(
    "? session.remote_identity.uri.user : 'Unbekannt';",
    "? session.remote_identity.uri.user : " + t('unknown','Unbekannt') + ";"
)

# Alert
c = c.replace(
    "alert('Softphone nicht registriert. Bitte Einstellungen prüfen.');",
    "alert(" + t('not_registered_alert','Softphone nicht registriert.') + ");"
)

# CDR "Zuletzt"
c = c.replace(
    "'<div style=\"font-size:10px;color:var(--text-muted);margin-bottom:3px;font-weight:500\">Zuletzt</div>'",
    "'<div style=\"font-size:10px;color:var(--text-muted);margin-bottom:3px;font-weight:500\">' + " + t('recent','Zuletzt') + " + '</div>'"
)

# Gespeichert / Fehler
c = c.replace(
    "msg.textContent = 'Gespeichert.';",
    "msg.textContent = " + t('saved','Gespeichert.') + ";"
)
c = c.replace(
    "msg.textContent = 'Speichern fehlgeschlagen.';",
    "msg.textContent = " + t('save_failed','Speichern fehlgeschlagen.') + ";"
)

with open("apps/abpe_crm/static/abpe_crm/softphone/js/6_sp-core.js", "w") as f:
    f.write(c)
print("✓  6_sp-core.js")
PYEOF
node --check "$JS6" && ok "6_sp-core.js Syntax OK" || { echo "FEHLER"; exit 1; }
echo

# ══════════════════════════════════════════════════════════
# SCHRITT 5: 8_sp-status.js Labels → t()
# ══════════════════════════════════════════════════════════
info "Schritt 5/7 — 8_sp-status.js"

python3 << 'PYEOF'
with open("apps/abpe_crm/static/abpe_crm/softphone/js/8_sp-status.js", "r") as f:
    c = f.read()

def t(key, fb=''):
    return "SP_i18n.t('" + key + "'" + (", '" + fb + "'" if fb else '') + ")"

# Alerts
c = c.replace(
    "alert('Bitte VM-Nebenstelle in den Einstellungen konfigurieren.');",
    "alert(" + t('alert_vm_missing') + ");"
)
c = c.replace(
    "alert('Bitte DND-Nebenstelle in den Einstellungen konfigurieren.');",
    "alert(" + t('alert_dnd_missing') + ");"
)

# Weiterleitungsziel prompt
c = c.replace(
    "var target = prompt('Weiterleitungsziel:', '');",
    "var target = prompt(" + t('forward_prompt','Weiterleitungsziel:') + ", '');"
)

# Status-Bar Labels
c = c.replace(
    "bar.innerHTML = '<i class=\"bi bi-bell-slash\" style=\"margin-right:4px\"></i>Nicht st\\u00f6ren aktiv';",
    "bar.innerHTML = '<i class=\"bi bi-bell-slash\" style=\"margin-right:4px\"></i>' + " + t('dnd_active','Nicht stören aktiv') + ";"
)
c = c.replace(
    "bar.innerHTML = '<i class=\"bi bi-arrow-return-right\" style=\"margin-right:4px\"></i>Weiterleitung: ' + fwdTarget;",
    "bar.innerHTML = '<i class=\"bi bi-arrow-return-right\" style=\"margin-right:4px\"></i>' + " + t('forwarding','Weiterleitung') + " + ': ' + fwdTarget;"
)
c = c.replace(
    "bar.innerHTML = '<i class=\"bi bi-voicemail\" style=\"margin-right:4px\"></i>' + vmCount\n                + ' neue Voicemail-Nachricht' + (vmCount > 1 ? 'en' : '');",
    "bar.innerHTML = '<i class=\"bi bi-voicemail\" style=\"margin-right:4px\"></i>' + vmCount + ' ' + (vmCount > 1 ? " + t('new_voicemails','neue Voicemail-Nachrichten') + " : " + t('new_voicemail','neue Voicemail-Nachricht') + ");"
)

# DND Label
c = c.replace(
    "if (dndLabel) dndLabel.textContent = 'DND';",
    "if (dndLabel) dndLabel.textContent = " + t('dnd','DND') + ";"
)

with open("apps/abpe_crm/static/abpe_crm/softphone/js/8_sp-status.js", "w") as f:
    f.write(c)
print("✓  8_sp-status.js")
PYEOF
node --check "$JS8" && ok "8_sp-status.js Syntax OK" || { echo "FEHLER"; exit 1; }
echo

# ══════════════════════════════════════════════════════════
# SCHRITT 6: 9_sp-transfer.js + 10_sp-fop.js Labels → t()
# ══════════════════════════════════════════════════════════
info "Schritt 6/7 — 9_sp-transfer.js + 10_sp-fop.js"

python3 << 'PYEOF'
def t(key, fb=''):
    return "SP_i18n.t('" + key + "'" + (", '" + fb + "'" if fb else '') + ")"

# ── 9_sp-transfer.js ─────────────────────────────────────
with open("apps/abpe_crm/static/abpe_crm/softphone/js/9_sp-transfer.js", "r") as f:
    c = f.read()

# Alerts
c = c.replace(
    "alert('Kein aktives Gespräch für Transfer.');",
    "alert(" + t('alert_no_session') + ");"
)
c = c.replace(
    "alert('Gehaltener Anruf nicht mehr aktiv.');",
    "alert(" + t('alert_held_gone') + ");"
)

# Section-Header Labels
c = c.replace(
    "secHead('exts', 'Nebenstellen \\u2014 frei (' + freeExts.length + ')', true);",
    "secHead('exts', " + t('free_extensions','Nebenstellen \u2014 frei') + " + ' (' + freeExts.length + ')', true);"
)
c = c.replace(
    "secHead('speed', 'Schnellwahl (' + dials.length + ')', true);",
    "secHead('speed', " + t('speed_dial','Schnellwahl') + " + ' (' + dials.length + ')', true);"
)
c = c.replace(
    "secHead('recent', 'Letzte Anrufe', false);",
    "secHead('recent', " + t('last_calls','Letzte Anrufe') + ", false);"
)

# subSec Labels
c = c.replace(
    "subSec('missed',   'Abwesenheit', missed,   '#ef4444');",
    "subSec('missed', " + t('missed','Abwesenheit') + ", missed, '#ef4444');"
)
c = c.replace(
    "subSec('answered', 'Angenommen',  answered, '#22c55e');",
    "subSec('answered', " + t('answered','Angenommen') + ", answered, '#22c55e');"
)
c = c.replace(
    "subSec('dialed',   'Gew\\u00e4hlt', dialed,  '#22c55e');",
    "subSec('dialed', " + t('dialed','Gew\u00e4hlt') + ", dialed, '#22c55e');"
)

# Keine Treffer / Keine Einträge / Keine Schnellwahl / Keine freien Nebenstellen
c = c.replace(
    "'<div style=\"font-size:10px;color:var(--text-muted);padding:4px 0\">Keine Treffer</div>'",
    "'<div style=\"font-size:10px;color:var(--text-muted);padding:4px 0\">' + " + t('no_results','Keine Treffer') + " + '</div>'"
)
c = c.replace(
    "'<div style=\"padding:4px 8px;font-size:11px;color:var(--text-muted)\">Keine Eintr\\u00e4ge</div>'",
    "'<div style=\"padding:4px 8px;font-size:11px;color:var(--text-muted)\">' + " + t('no_entries','Keine Einträge') + " + '</div>'"
)
c = c.replace(
    "html += '<div style=\"padding:5px 8px;font-size:11px;color:var(--text-muted)\">Keine Schnellwahl</div>';",
    "html += '<div style=\"padding:5px 8px;font-size:11px;color:var(--text-muted)\">' + " + t('no_speed_dial','Keine Schnellwahl') + " + '</div>';"
)
c = c.replace(
    "html += '<div style=\"padding:5px 8px;font-size:11px;color:var(--text-muted)\">Keine freien Nebenstellen</div>';",
    "html += '<div style=\"padding:5px 8px;font-size:11px;color:var(--text-muted)\">' + " + t('no_free_extensions','Keine freien Nebenstellen') + " + '</div>';"
)

with open("apps/abpe_crm/static/abpe_crm/softphone/js/9_sp-transfer.js", "w") as f:
    f.write(c)
print("✓  9_sp-transfer.js")

# ── 10_sp-fop.js ─────────────────────────────────────────
with open("apps/abpe_crm/static/abpe_crm/softphone/js/10_sp-fop.js", "r") as f:
    c = f.read()

# Extension Status Labels
c = c.replace(
    "free:    { bg: 'var(--ext-free-bg)',    color: 'var(--ext-free-color)',    label: 'frei',    dot: 'var(--ext-free-dot,#22c55e)' },",
    "free:    { bg: 'var(--ext-free-bg)',    color: 'var(--ext-free-color)',    label: " + t('free','frei') + ",    dot: 'var(--ext-free-dot,#22c55e)' },"
)
c = c.replace(
    "busy:    { bg: 'var(--ext-busy-bg)',    color: 'var(--ext-busy-color)',    label: 'besetzt', dot: 'var(--ext-busy-dot,#ef4444)' },",
    "busy:    { bg: 'var(--ext-busy-bg)',    color: 'var(--ext-busy-color)',    label: " + t('busy','besetzt') + ", dot: 'var(--ext-busy-dot,#ef4444)' },"
)
c = c.replace(
    "dnd:     { bg: 'var(--ext-dnd-bg)',     color: 'var(--ext-dnd-color)',     label: 'DND',     dot: 'var(--ext-dnd-dot,#f59e0b)' },",
    "dnd:     { bg: 'var(--ext-dnd-bg)',     color: 'var(--ext-dnd-color)',     label: " + t('dnd','DND') + ",     dot: 'var(--ext-dnd-dot,#f59e0b)' },"
)
c = c.replace(
    "offline: { bg: 'var(--ext-offline-bg)', color: 'var(--ext-offline-color)', label: 'offline', dot: 'var(--ext-offline-dot,#9ca3af)' },",
    "offline: { bg: 'var(--ext-offline-bg)', color: 'var(--ext-offline-color)', label: " + t('offline','offline') + ", dot: 'var(--ext-offline-dot,#9ca3af)' },"
)
c = c.replace(
    "unknown: { bg: 'var(--ext-offline-bg)', color: 'var(--ext-offline-color)', label: '?',       dot: 'var(--ext-offline-dot,#9ca3af)' },",
    "unknown: { bg: 'var(--ext-offline-bg)', color: 'var(--ext-offline-color)', label: " + t('unknown_short','?') + ",       dot: 'var(--ext-offline-dot,#9ca3af)' },"
)

# FOP Section-Header Labels
c = c.replace(
    "secHeader('ext', 'EXTENSIONS',",
    "secHeader('ext', " + t('extensions','EXTENSIONS') + ","
)
c = c.replace(
    "secHeader('park', 'PARKING 700',",
    "secHeader('park', " + t('parking','PARKING 700') + ","
)
c = c.replace(
    "secHeader('conf', 'KONFERENZEN',",
    "secHeader('conf', " + t('conferences','KONFERENZEN') + ","
)
c = c.replace(
    "secHeader('vm', 'VOICEMAIL',",
    "secHeader('vm', " + t('voicemail','VOICEMAIL') + ","
)

# FOP Anrufen-Button
c = c.replace(
    "'>&#9742; Anrufen</span>'",
    "' + " + t('call_btn','Anrufen') + " + '</span>'"
)
# DND an/aus
c = c.replace(
    "(r.dnd ? 'DND aus' : 'DND an')",
    "(r.dnd ? " + t('dnd_off','DND aus') + " : " + t('dnd_on','DND an') + ")"
)
# Abholen
c = c.replace(
    "'>&#9742; Abholen</span>'",
    "' + " + t('pickup_btn','Abholen') + " + '</span>'"
)
# leer
c = c.replace(
    "'<span style=\"flex:1\">leer</span>'",
    "'<span style=\"flex:1\">' + " + t('empty','leer') + " + '</span>'"
)
# Park
c = c.replace(
    "'>&#8659; Park</span>'",
    "' + " + t('park_btn','Park') + " + '</span>'"
)
# Tlnhm.
c = c.replace(
    "count + ' Tlnhm.'",
    "count + ' ' + " + t('participants','Tlnhm.')
)
# leer (Konferenz)
c = c.replace(
    ": 'leer') + '</span>'",
    ": " + t('empty','leer') + ") + '</span>'"
)
# Konf
c = c.replace(
    "'>&#8594; Konf</span>'",
    "' + " + t('conf_join','Konf') + " + '</span>'"
)
# VM neu
c = c.replace(
    "' + count + ' neu</span>'",
    "' + count + ' ' + " + t('vm_new','neu') + " + '</span>'"
)
# Abhören
c = c.replace(
    "'>&#9654; Abh\\u00f6ren</span>'",
    "' + " + t('vm_listen','Abhören') + " + '</span>'"
)

# Alerts
c = c.replace(
    "alert('Bitte eigene Extension in den Einstellungen konfigurieren.');",
    "alert(" + t('alert_ext_missing') + ");"
)
c = c.replace(
    "if (!d.success) alert('Parken fehlgeschlagen: ' + (d.error || 'Unbekannt'));",
    "if (!d.success) alert(" + t('alert_park_failed','Parken fehlgeschlagen') + " + ': ' + (d.error || " + t('unknown','Unbekannt') + "));"
)
c = c.replace(
    "if (!d.success) alert('Konferenz fehlgeschlagen: ' + (d.error || 'Unbekannt'));",
    "if (!d.success) alert(" + t('alert_conf_failed','Konferenz fehlgeschlagen') + " + ': ' + (d.error || " + t('unknown','Unbekannt') + "));"
)

# Schnellwahl Placeholder-Texte
c = c.replace(
    "'<div style=\"padding:8px;font-size:10px;color:var(--text-muted)\">Keine Schnellwahl konfiguriert.<br>Kontakt aus Suche hierher ziehen.</div>'",
    "'<div style=\"padding:8px;font-size:10px;color:var(--text-muted)\">' + " + t('no_speed_dial','Keine Schnellwahl konfiguriert.') + " + '<br>' + " + t('speed_dial_hint','Kontakt aus Suche hierher ziehen.') + " + '</div>'"
)
c = c.replace(
    "'<div style=\"padding:6px 8px;font-size:10px;color:var(--text-muted)\">Lade...</div>'",
    "'<div style=\"padding:6px 8px;font-size:10px;color:var(--text-muted)\">' + " + t('loading','Lade...') + " + '</div>'"
)
# Ansprechpartner
c = c.replace(
    "' Ansprechpartner</div>'",
    "' ' + " + t('contact_persons','Ansprechpartner') + " + '</div>'"
)
# Nummer
c = c.replace(
    "'<span style=\"color:var(--text-muted)\">Nummer</span>'",
    "'<span style=\"color:var(--text-muted)\">' + " + t('number','Nummer') + " + '</span>'"
)
# Keine Einträge (SpeedList)
c = c.replace(
    "'<div style=\"padding:6px 8px;font-size:11px;color:var(--text-muted)\">Keine Eintr\\u00e4ge</div>'",
    "'<div style=\"padding:6px 8px;font-size:11px;color:var(--text-muted)\">' + " + t('no_entries','Keine Einträge') + " + '</div>'"
)
# Keine Treffer (Firma-Suche)
c = c.replace(
    "'<div style=\"font-size:10px;color:var(--text-muted);padding:4px\">Keine Treffer</div>'",
    "'<div style=\"font-size:10px;color:var(--text-muted);padding:4px\">' + " + t('no_results','Keine Treffer') + " + '</div>'"
)
# Lade... (Letzte Anrufe)
c = c.replace(
    "if (body) body.innerHTML = '<div style=\"padding:8px;font-size:11px;color:var(--text-muted)\">Lade...</div>';",
    "if (body) body.innerHTML = '<div style=\"padding:8px;font-size:11px;color:var(--text-muted)\">' + SP_i18n.t('loading','Lade...') + '</div>';"
)
# Keine Einträge (CDR)
c = c.replace(
    "'<div style=\"padding:6px 8px;font-size:11px;color:var(--text-muted)\">Keine Eintr\\u00e4ge</div>'",
    "'<div style=\"padding:6px 8px;font-size:11px;color:var(--text-muted)\">' + " + t('no_entries','Keine Einträge') + " + '</div>'"
)
# CDR Section Labels
c = c.replace(
    "secHtml('missed',   'Abwesenheit', missed.length   > 0 ? '#ef4444' : '#22c55e', missed)",
    "secHtml('missed', " + t('missed','Abwesenheit') + ", missed.length > 0 ? '#ef4444' : '#22c55e', missed)"
)
c = c.replace(
    "secHtml('incoming', 'Angenommen',  '#22c55e', incoming)",
    "secHtml('incoming', " + t('answered','Angenommen') + ", '#22c55e', incoming)"
)
c = c.replace(
    "secHtml('outgoing', 'Gew\\u00e4hlt', '#22c55e', outgoing);",
    "secHtml('outgoing', " + t('dialed','Gew\u00e4hlt') + ", '#22c55e', outgoing);"
)

with open("apps/abpe_crm/static/abpe_crm/softphone/js/10_sp-fop.js", "w") as f:
    f.write(c)
print("✓  10_sp-fop.js")
PYEOF
node --check "$JS9"  && ok "9_sp-transfer.js  Syntax OK" || { echo "FEHLER JS9";  exit 1; }
node --check "$JS10" && ok "10_sp-fop.js      Syntax OK" || { echo "FEHLER JS10"; exit 1; }
echo

# ══════════════════════════════════════════════════════════
# SCHRITT 7: softphone.html — data-i18n Attribute
# ══════════════════════════════════════════════════════════
info "Schritt 7/7 — softphone.html: statische Labels → data-i18n"

python3 << 'PYEOF'
with open("apps/abpe_crm/templates/abpe_crm/softphone/softphone.html", "r") as f:
    c = f.read()

# Header: "Nicht verbunden"
c = c.replace(
    '<span id="sp-status-text" style="font-size:10px;color:var(--header-status-muted)">Nicht verbunden</span>',
    '<span id="sp-status-text" data-i18n="not_connected" style="font-size:10px;color:var(--header-status-muted)">Nicht verbunden</span>'
)

# Tab Wählen
c = c.replace(
    '><i class="bi bi-grid-3x3-gap"></i> Wählen\n        </button>',
    ' data-i18n="dial"><i class="bi bi-grid-3x3-gap"></i> Wählen\n        </button>'
)

# Tab Einstellungen
c = c.replace(
    '><i class="bi bi-gear"></i> Einstellungen\n        </button>',
    ' data-i18n="settings"><i class="bi bi-gear"></i> Einstellungen\n        </button>'
)

# Kontakt suchen Placeholder
c = c.replace(
    'placeholder="Kontakt suchen…" oninput="Softphone.search(this.value)"',
    'placeholder="Kontakt suchen…" data-i18n-placeholder="search_contact" oninput="Softphone.search(this.value)"'
)

# Einstellungen Labels
replacements = [
    ('SIP Benutzer',      'sip_user'),
    ('SIP Passwort',      'sip_password'),
    ('WebSocket URL',     'websocket_url'),
    ('Anzeigename',       'display_name'),
    ('VM-Nebenstelle',    'vm_extension'),
    ('DND-Nebenstelle',   'dnd_extension'),
]
for label, key in replacements:
    c = c.replace(
        f'<label style="font-size:11px;color:var(--text-muted);display:block;margin-bottom:3px">{label}</label>',
        f'<label data-i18n="{key}" style="font-size:11px;color:var(--text-muted);display:block;margin-bottom:3px">{label}</label>'
    )

# Überwachte Extensions Label
c = c.replace(
    '<label style="font-size:11px;color:var(--text-muted);display:block;margin-bottom:3px">\n                    Überwachte Extensions (kommagetrennt)</label>',
    '<label data-i18n="status_extensions" style="font-size:11px;color:var(--text-muted);display:block;margin-bottom:3px">\n                    Überwachte Extensions (kommagetrennt)</label>'
)

# Speichern Button
c = c.replace(
    '><i class="bi bi-save"></i> Speichern &amp; registrieren\n            </button>',
    ' data-i18n="save_register"><i class="bi bi-save"></i> Speichern &amp; registrieren\n            </button>'
)

# Toggle Buttons
c = c.replace(
    '>&#9664; Schnellwahl</button>',
    ' data-i18n="speed_dial_toggle">&#9664; Schnellwahl</button>'
)
c = c.replace(
    '>&#9742; Anrufe</button>',
    ' data-i18n="calls_toggle">&#9742; Anrufe</button>'
)
c = c.replace(
    '>Status &#9654;</button>',
    ' data-i18n="status_toggle">Status &#9654;</button>'
)

# Schnellwahl Panel Header
c = c.replace(
    '<span>Schnellwahl</span>',
    '<span data-i18n="speed_dial">Schnellwahl</span>'
)

# FOP Panel Header
c = c.replace(
    '<span>Ext. Status</span>',
    '<span data-i18n="ext_status">Ext. Status</span>'
)

# Letzte Anrufe Panel Header
c = c.replace(
    '<span>Letzte Anrufe</span>',
    '<span data-i18n="last_calls">Letzte Anrufe</span>'
)

# Incoming Call
c = c.replace(
    '<i class="bi bi-telephone-inbound-fill"></i> Eingehender Anruf…',
    '<i class="bi bi-telephone-inbound-fill"></i> <span data-i18n="incoming_call">Eingehender Anruf…</span>'
)
c = c.replace(
    '><i class="bi bi-telephone-fill"></i> Annehmen</button>',
    ' data-i18n="answer"><i class="bi bi-telephone-fill"></i> Annehmen</button>'
)
c = c.replace(
    '><i class="bi bi-telephone-x-fill"></i> Ablehnen</button>',
    ' data-i18n="reject"><i class="bi bi-telephone-x-fill"></i> Ablehnen</button>'
)

# PWA Install Banner
c = c.replace(
    '<span>Als App installieren</span>',
    '<span data-i18n="pwa_install">Als App installieren</span>'
)
c = c.replace(
    'style="background:rgba(255,255,255,0.2);border:none;color:#fff;padding:3px 10px;border-radius:10px;cursor:pointer;font-size:11px">Installieren</button>',
    'data-i18n="pwa_install_btn" style="background:rgba(255,255,255,0.2);border:none;color:#fff;padding:3px 10px;border-radius:10px;cursor:pointer;font-size:11px">Installieren</button>'
)

with open("apps/abpe_crm/templates/abpe_crm/softphone/softphone.html", "w") as f:
    f.write(c)
print("✓  softphone.html: data-i18n Attribute gesetzt")
PYEOF
echo

# ══════════════════════════════════════════════════════════
# Deploy
# ══════════════════════════════════════════════════════════
info "Deploy"
python3 manage.py collectstatic --noinput 2>&1 | tail -2
supervisorctl restart abpe-django
sleep 2
supervisorctl status abpe-django
echo
ok "Fertig — Hard-Reload (Ctrl+Shift+R)"
echo
echo "Test:"
echo "  1. Seite laden → Labels auf Deutsch"
echo "  2. SP_LANG = 'en' in Browser-Console setzen → SP_i18n.load('en') → noch leer (Stub)"
echo "  3. Dann: en_phone.json mit Claude übersetzen lassen"

