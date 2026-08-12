#!/bin/bash
# ============================================================
# wavnotes_05_resolve.sh
# WAV-Notizen — Etappe 5: Automatische Kontakt-Erkennung beim
# Oeffnen des Notiz-Modals, ueber bestehenden api_cdr_resolve
# (Telefonnummer -> Kontakt/Firma + Konfidenz).
# ============================================================
set -e
cd /opt/abpe/backend

JS="apps/abpe_crm/static/abpe_crm/js/mod-crm-pbx.js"

echo "=== [1/4] Backup ==="
python3 Archiv/backup_restore.py -save "$JS" -m "wavnotes_05: vor auto-resolve"

echo "=== [2/4] api.cdrResolve eintragen ==="
python3 - << 'PYEOF'
p = 'apps/abpe_crm/static/abpe_crm/js/mod-crm-pbx.js'
s = open(p, encoding='utf-8').read()
if 'cdrResolve:' in s:
    print("  api.cdrResolve existiert schon — uebersprungen.")
else:
    OLD = "        wavnoteSave:       '/crm/api/telefon/wavnotes/save/',\n"
    NEW = OLD + "        cdrResolve:        '/crm/api/cdr/resolve/',\n"
    assert s.count(OLD) == 1, f"Anker {s.count(OLD)}x gefunden statt 1"
    s = s.replace(OLD, NEW)
    open(p, 'w', encoding='utf-8').write(s)
    print("  api.cdrResolve eingetragen.")
PYEOF

echo "=== [3/4] wavnoteOpenModal auf Auto-Resolve umstellen + Methode anhaengen ==="
python3 - << 'PYEOF'
p = 'apps/abpe_crm/static/abpe_crm/js/mod-crm-pbx.js'
s = open(p, encoding='utf-8').read()
if 'wavnoteResolveContact(' in s:
    print("  wavnoteResolveContact existiert schon — uebersprungen.")
else:
    OLD_CALL = '''        this.wavnoteTranscribe();
        this._wavnoteRenderContactBox();
    },'''
    NEW_CALL = '''        this.wavnoteTranscribe();
        this.wavnoteResolveContact();
    },

    async wavnoteResolveContact() {
        const n = this._wavCurrent;
        if (!n || !n.callerid) { this._wavnoteRenderContactBox(); return; }
        try {
            const res = await this.get(`${this.api.cdrResolve}?number=${encodeURIComponent(n.callerid)}`);
            if (res.matched && res.crm_id && res.confidence !== 'multi') {
                this._wavContact = { crm_id: res.crm_id, module: res.module, name: res.name };
            }
        } catch (e) { /* still - fallback auf manuelle Suche */ }
        this._wavnoteRenderContactBox();
    },'''
    assert s.count(OLD_CALL) == 1, f"Anker {s.count(OLD_CALL)}x gefunden statt 1"
    s = s.replace(OLD_CALL, NEW_CALL)
    open(p, 'w', encoding='utf-8').write(s)
    print("  wavnoteResolveContact() eingebaut + verkabelt.")
PYEOF

echo "=== [4/4] node --check + collectstatic + restart ==="
node --check "$JS" && echo "  Syntax OK"
python manage.py collectstatic --noinput 2>&1 | tail -3
supervisorctl restart abpe-django

echo ""
echo "============================================================"
echo "✅ wavnotes_05 fertig — Kontakt wird beim Modal-Oeffnen automatisch"
echo "vorgeschlagen (bei mehreren Treffern bleibt es bei manueller Suche)."
echo "============================================================"
