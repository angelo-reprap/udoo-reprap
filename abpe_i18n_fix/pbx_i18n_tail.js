// Ersetzt ab Zeile ~4968 in mod-crm-pbx.js (nach vmHangup / schließender });

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
