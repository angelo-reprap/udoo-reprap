// Ersetzt Dateiende in mod-crm-pbx.js (ab Object.assign refreshI18n)

Object.assign(PBX, {
    refreshI18n() {
        if (!document.getElementById('pbx-root')) return;
        if (typeof window.applyTranslations === 'function') window.applyTranslations();
        if (typeof this.renderHud === 'function') this.renderHud();
        if (typeof this.renderPark === 'function') this.renderPark();
        if (typeof this.renderKonf === 'function') this.renderKonf();
        if (typeof this.renderQueues === 'function') this.renderQueues();
        if (typeof this.updateCount === 'function') this.updateCount();
        // MeetMe: immer neu rendern wenn DOM da (nicht nur bei tab==='konf')
        if (this.$('pbx-meetme-strip') && typeof this.meetmeRenderStrip === 'function') {
            this.meetmeRenderStrip();
            const id = this._meetmeState && this._meetmeState.selectedId;
            const cached = id && this._meetmeState.detailCache && this._meetmeState.detailCache[id];
            if (cached && typeof this.meetmeRenderDetail === 'function') {
                this.meetmeRenderDetail(cached);
            } else {
                const detail = this.$('pbx-meetme-detail');
                if (detail && !id) {
                    detail.innerHTML = '<div class="pbx-hint">' + this.t('pbx_meetme_select_hint', 'Termin auswählen oder neuen Termin anlegen') + '</div>';
                }
            }
        }
        const tab = this.tab;
        if (tab === 'cdr' && typeof this.loadCdr === 'function') this.loadCdr();
        else if (tab === 'stats' && typeof this.loadStats === 'function') this.loadStats();
        else if (tab === 'vm' && typeof this.loadVm === 'function') this.loadVm();
        else if (tab === 'wavnotes' && typeof this.loadWavNotes === 'function') this.loadWavNotes();
    },
});

function _pbxOnLanguageUpdate() {
    if (document.getElementById('pbx-root') && window.PBX && typeof PBX.refreshI18n === 'function') {
        PBX.refreshI18n();
    }
}

document.addEventListener('languageChanged', _pbxOnLanguageUpdate);
document.addEventListener('languageSelectorReady', _pbxOnLanguageUpdate);
