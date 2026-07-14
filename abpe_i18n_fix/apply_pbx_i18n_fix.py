#!/usr/bin/env python3
"""Bereinigt PBX-i18n-Refresh in mod-crm-pbx.js (doppelte Listener entfernen)."""
from pathlib import Path
import sys

PBX = Path('apps/abpe_crm/static/abpe_crm/js/mod-crm-pbx.js')
MARKER = "document.addEventListener('languageChanged', function() {"

TAIL = """
Object.assign(PBX, {
    refreshI18n() {
        if (!document.getElementById('pbx-root')) return;
        if (typeof window.applyTranslations === 'function') window.applyTranslations();
        if (typeof this.renderHud === 'function') this.renderHud();
        if (typeof this.renderPark === 'function') this.renderPark();
        if (typeof this.renderKonf === 'function') this.renderKonf();
        if (typeof this.renderQueues === 'function') this.renderQueues();
        if (typeof this.updateCount === 'function') this.updateCount();
        const tab = this.tab;
        if (tab === 'cdr' && typeof this.loadCdr === 'function') this.loadCdr();
        else if (tab === 'stats' && typeof this.loadStats === 'function') this.loadStats();
        else if (tab === 'vm' && typeof this.loadVm === 'function') this.loadVm();
        else if (tab === 'wavnotes' && typeof this.loadWavNotes === 'function') this.loadWavNotes();
        else if (tab === 'konf') {
            if (typeof this.meetmeRenderStrip === 'function') this.meetmeRenderStrip();
            const id = this._meetmeState && this._meetmeState.selectedId;
            const cached = id && this._meetmeState.detailCache && this._meetmeState.detailCache[id];
            if (cached && typeof this.meetmeRenderDetail === 'function') this.meetmeRenderDetail(cached);
            else if (id && typeof this.meetmeSelectMeeting === 'function') this.meetmeSelectMeeting(id);
        }
    },
});

function _pbxOnLanguageUpdate() {
    if (document.getElementById('pbx-root') && window.PBX && typeof PBX.refreshI18n === 'function') {
        PBX.refreshI18n();
    }
}

document.addEventListener('languageChanged', _pbxOnLanguageUpdate);
document.addEventListener('languageSelectorReady', _pbxOnLanguageUpdate);
"""


def main() -> int:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else PBX
    if not path.is_file():
        print(f'FEHLER: Datei nicht gefunden: {path}', file=sys.stderr)
        return 1

    text = path.read_text(encoding='utf-8')
    idx = text.find(MARKER)
    if idx < 0:
        if '_pbxOnLanguageUpdate' in text:
            print('OK: Patch scheint bereits angewendet.')
            return 0
        print('FEHLER: Marker nicht gefunden — Datei-Ende manuell prüfen.', file=sys.stderr)
        return 1

    new_text = text[:idx].rstrip() + '\n' + TAIL.strip() + '\n'
    path.write_text(new_text, encoding='utf-8')
    print(f'OK: {path} — doppelte languageChanged-Listener entfernt, refreshI18n + languageSelectorReady gesetzt.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
