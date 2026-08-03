/* ============================================================
   ABpE CRM — core-gsearch.js
   Globale Suche (Strg+K / Icon-Klick). Nutzt api_search_all
   (bestehende Multi-Index-ES-Suche: Personen/Firmen/Dokumente/Mails),
   keine neue Backend-Logik. Laedt auf JEDER Seite (core-Skript in
   base.html), nicht an ein Modul gebunden.
   ============================================================ */

const GSearch = {
    api: {
        searchAll: '/edms/api/search_all/',
    },
    isOpen: false,
    activeIndex: -1,
    currentFilter: 'all',
    results: [],
    debounceTimer: null,
    _lastQuery: '',

    init() {
        this._buildModal();
        document.addEventListener('keydown', (e) => this._onGlobalKeydown(e));
        const trigger = document.getElementById('gsearch-trigger');
        if (trigger) trigger.addEventListener('click', () => this.open());
    },

    t(key, fb) { return (window.i18nData && window.i18nData[key]) || fb || key; },
    esc(s) { return String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c])); },

    _onGlobalKeydown(e) {
        if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
            e.preventDefault();
            this.open();
            return;
        }
        if (!this.isOpen) return;
        if (e.key === 'Escape') { this.close(); return; }
        if (e.key === 'ArrowDown') { e.preventDefault(); this._moveActive(1); return; }
        if (e.key === 'ArrowUp') { e.preventDefault(); this._moveActive(-1); return; }
        if (e.key === 'Enter') { e.preventDefault(); this._openActive(); return; }
    },

    _buildModal() {
        if (document.getElementById('gsearch-overlay')) return;
        const overlay = document.createElement('div');
        overlay.id = 'gsearch-overlay';
        overlay.className = 'gsearch-overlay';
        overlay.style.display = 'none';
        overlay.innerHTML =
            '<div class="gsearch-modal">' +
                '<div class="gsearch-inputrow">' +
                    '<i class="bi bi-search gsearch-icon"></i>' +
                    '<input type="text" id="gsearch-input" class="gsearch-input" placeholder="' + this.esc(this.t('gsearch_placeholder', 'Personen, Firmen, Dokumente, Mails durchsuchen…')) + '" autocomplete="off">' +
                    '<span class="gsearch-esc">Esc</span>' +
                '</div>' +
                '<div class="gsearch-filterbar" id="gsearch-filterbar"></div>' +
                '<div class="gsearch-results" id="gsearch-results"></div>' +
                '<div class="gsearch-footer">' +
                    '<span><i class="bi bi-arrow-up"></i><i class="bi bi-arrow-down"></i> ' + this.t('gsearch_nav', 'Navigieren') + '</span>' +
                    '<span><i class="bi bi-arrow-return-left"></i> ' + this.t('gsearch_open', 'Öffnen') + '</span>' +
                    '<span class="gsearch-shortcut">Strg+K</span>' +
                '</div>' +
            '</div>';
        overlay.addEventListener('click', (e) => { if (e.target === overlay) this.close(); });
        document.body.appendChild(overlay);
        const input = document.getElementById('gsearch-input');
        input.addEventListener('input', () => this._onInput());
    },

    open() {
        this.isOpen = true;
        const overlay = document.getElementById('gsearch-overlay');
        if (overlay) overlay.style.display = 'flex';
        const input = document.getElementById('gsearch-input');
        if (input) { input.value = ''; input.focus(); }
        this.currentFilter = 'all';
        this.results = [];
        this.activeIndex = -1;
        this._renderFilterbar({});
        this._renderResults([]);
    },

    close() {
        this.isOpen = false;
        const overlay = document.getElementById('gsearch-overlay');
        if (overlay) overlay.style.display = 'none';
    },

    _onInput() {
        clearTimeout(this.debounceTimer);
        const q = (document.getElementById('gsearch-input').value || '').trim();
        if (q.length < 2) { this.results = []; this._renderResults([]); this._renderFilterbar({}); return; }
        this.debounceTimer = setTimeout(() => this._search(q), 250);
    },

    async _search(q) {
        this._lastQuery = q;
        const size = this.currentFilter === 'all' ? 30 : 100;
        try {
            const res = await fetch(this.api.searchAll + '?q=' + encodeURIComponent(q) + '&scope=' + this.currentFilter + '&size=' + size, { headers: {'X-Requested-With':'XMLHttpRequest'} });
            const data = await res.json();
            if (this._lastQuery !== q) return;
            this.results = data.results || [];
            this.activeIndex = this.results.length ? 0 : -1;
            this._counts = data.counts || {};
            this._renderFilterbar(this._counts);
            this._renderResults(this.results);
        } catch (e) {
            this._renderResults([]);
        }
    },

    setFilter(f) {
        this.currentFilter = f;
        if (this._lastQuery) this._search(this._lastQuery);
    },

    _renderFilterbar(counts) {
        const bar = document.getElementById('gsearch-filterbar');
        if (!bar) return;
        const items = [
            ['all', this.t('gsearch_all', 'Alles')],
            ['personen', this.t('gsearch_personen', 'Personen')],
            ['firmen', this.t('gsearch_firmen', 'Firmen')],
            ['dokumente', this.t('gsearch_dokumente', 'Dokumente')],
            ['mails', this.t('gsearch_mails', 'Mails')],
        ];
        bar.innerHTML = items.map(([key, label]) => {
            const active = key === this.currentFilter ? ' gsearch-filt-active' : '';
            const count = counts[key] != null ? ' <span class="gsearch-filt-count">' + counts[key] + '</span>' : '';
            return '<span class="gsearch-filt' + active + '" onclick="GSearch.setFilter(\'' + key + '\')">' + this.esc(label) + count + '</span>';
        }).join('');
    },

    _kindIcon(kind) {
        if (kind === 'person') return 'bi-person';
        if (kind === 'firma') return 'bi-building';
        if (kind === 'dokument') return 'bi-file-earmark-text';
        if (kind === 'mail') return 'bi-envelope';
        return 'bi-question-circle';
    },
    _kindClass(kind) {
        if (kind === 'person') return 'gsearch-badge-person';
        if (kind === 'firma') return 'gsearch-badge-firma';
        if (kind === 'dokument') return 'gsearch-badge-dokument';
        if (kind === 'mail') return 'gsearch-badge-mail';
        return '';
    },
    _kindLabel(kind) {
        if (kind === 'person') return this.t('gsearch_kind_person', 'Person');
        if (kind === 'firma') return this.t('gsearch_kind_firma', 'Firma');
        if (kind === 'dokument') return this.t('gsearch_kind_dokument', 'Dokument');
        if (kind === 'mail') return this.t('gsearch_kind_mail', 'Mail');
        return kind;
    },

    _renderResults(list) {
        const box = document.getElementById('gsearch-results');
        if (!box) return;
        if (!list.length) {
            box.innerHTML = '<div class="gsearch-empty">' + this.t('gsearch_no_hits', 'Keine Treffer') + '</div>';
            return;
        }
        const totalForFilter = this._counts ? this._counts[this.currentFilter] : null;
        const hint = (this.currentFilter !== 'all' && totalForFilter && totalForFilter > list.length)
            ? '<div class="gsearch-hint">' + this.t('gsearch_more_hint', 'Zeige {shown} von {total} Treffern - Suchbegriff genauer fassen, um weniger relevante Treffer auszuschliessen.').replace('{shown}', list.length).replace('{total}', totalForFilter) + '</div>'
            : '';
        box.innerHTML = list.map((r, i) => {
            const active = i === this.activeIndex ? ' gsearch-item-active' : '';
            return '<div class="gsearch-item' + active + '" data-idx="' + i + '" onclick="GSearch._openResult(' + i + ')">' +
                '<div class="gsearch-item-icon"><i class="bi ' + this._kindIcon(r.kind) + '"></i></div>' +
                '<div class="gsearch-item-body">' +
                '<div class="gsearch-item-top"><span class="gsearch-item-title">' + this.esc(r.title) + '</span>' +
                '<span class="gsearch-badge ' + this._kindClass(r.kind) + '">' + this._kindLabel(r.kind) + '</span></div>' +
                (r.meta ? '<div class="gsearch-item-meta">' + this.esc(r.meta) + '</div>' : '') +
                (r.snippet ? '<div class="gsearch-item-snip">' + this.esc(r.snippet) + '</div>' : '') +
                '</div><i class="bi bi-box-arrow-up-right gsearch-item-go"></i></div>';
        }).join('') + hint;
    },

    _moveActive(delta) {
        if (!this.results.length) return;
        this.activeIndex = (this.activeIndex + delta + this.results.length) % this.results.length;
        this._renderResults(this.results);
        const el = document.querySelector('.gsearch-item[data-idx="' + this.activeIndex + '"]');
        if (el) el.scrollIntoView({ block: 'nearest' });
    },

    _openActive() {
        if (this.activeIndex >= 0) this._openResult(this.activeIndex);
    },

    _openResult(i) {
        const r = this.results[i];
        if (!r) return;
        if (r.kind === 'person') { window.location.href = '/crm/berater/?detail=' + encodeURIComponent(r.id); return; }
        if (r.kind === 'firma') { window.location.href = '/crm/kunden/?detail=' + encodeURIComponent(r.id); return; }
        if (r.kind === 'dokument') { window.location.href = '/crm/dms/?doc=' + encodeURIComponent(r.id); return; }
        if (r.kind === 'mail') {
            const p = new URLSearchParams({
                mail_account: r.account || '', mail_folder: r.folder || '',
                mail_uid: r.uid || '', mail_message_id: r.message_id || '',
                mail_subject: r.title || '',
            });
            window.location.href = '/crm/dms/?' + p.toString();
        }
    },
};
document.addEventListener('DOMContentLoaded', () => GSearch.init());
