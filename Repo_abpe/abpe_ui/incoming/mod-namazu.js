'use strict';

(function () {

    const API_SEARCH   = '/api/namazu/search/';
    const API_STATUS   = '/api/namazu/status/';
    const API_REINDEX  = '/api/namazu/reindex/';
    const API_PROFILE  = '/api/namazu/profile/';
    const API_ES       = '/api/es/search/';
    const API_EMAIL    = '/api/email/view/';
    const API_ACCOUNTS = '/api/namazu/accounts/';

    function t(key) {
        const parts = key.split('.');
        let val = window.i18nData;
        for (const p of parts) {
            if (val && typeof val === 'object' && p in val) val = val[p];
            else return key;
        }
        return (typeof val === 'string') ? val : key;
    }

    function getCsrf() {
        return document.cookie.split(';')
            .map(c => c.trim())
            .find(c => c.startsWith('csrftoken='))
            ?.split('=')[1] || '';
    }

    // ── ES SUCHE ───────────────────────────────────────────
    let _esPage    = 1;
    let _esQuery   = '';
    let _esIndex   = 'consultants';
    let _esMax     = 20;
    let _esExclude = [];
    let _esSort    = [];  // [{field:'date', dir:'desc'}, ...]

    // Sort-Label Keys je Feld:Richtung
    const SORT_LABEL_KEYS = {
        'date:desc':            'namazu.es.sort.date_desc',
        'date:asc':             'namazu.es.sort.date_asc',
        'indexed_at:desc':      'namazu.es.sort.indexed_desc',
        'indexed_at:asc':       'namazu.es.sort.indexed_asc',
        'has_attachments:desc': 'namazu.es.sort.attachments',
        'from_addr:asc':        'namazu.es.sort.from_asc',
        'account:asc':          'namazu.es.sort.account_asc',
        'full_name:asc':        'namazu.es.sort.name_asc',
        'first_name:asc':       'namazu.es.sort.name_asc',
        'status:asc':           'namazu.es.sort.status',
        'verfuegbar_ab:asc':    'namazu.es.sort.available',
        'availability:asc':     'namazu.es.sort.availability',
    };

    // Sortierfelder je Index — Werte sind i18n-Keys
    const SORT_OPTIONS = {
        'emails': [
            ['date:desc',            'namazu.es.sort.date_desc'],
            ['date:asc',             'namazu.es.sort.date_asc'],
            ['has_attachments:desc', 'namazu.es.sort.attachments'],
            ['from_addr:asc',        'namazu.es.sort.from_asc'],
            ['account:asc',          'namazu.es.sort.account_asc'],
            ['folder:asc',          'namazu.es.sort.folder_asc'],
            ['size_bytes:desc',     'namazu.es.sort.size_desc'],
        ],
        'profiles': [
            ['indexed_at:desc',   'namazu.es.sort.indexed_desc'],
            ['indexed_at:asc',    'namazu.es.sort.indexed_asc'],
            ['first_name:asc',    'namazu.es.sort.name_asc'],
            ['status:asc',        'namazu.es.sort.status'],
            ['verfuegbar_ab:asc', 'namazu.es.sort.available'],
        ],
        'consultants': [
            ['full_name:asc',    'namazu.es.sort.name_asc'],
            ['availability:asc', 'namazu.es.sort.availability'],
        ],
    };

    function updateSortDropdown() {
        const idx  = document.getElementById('es-search-index')?.value || 'consultants';
        const sel  = document.getElementById('es-sort-add');
        if (!sel) return;
        const opts = SORT_OPTIONS[idx] || [];
        sel.innerHTML = `<option value="">${t('namazu.es.sort.placeholder')}</option>` +
            opts.map(([val, labelKey]) => `<option value="${val}">${t(labelKey)}</option>`).join('');
        // Ungültige Sort-Tags beim Index-Wechsel entfernen
        const validFields = opts.map(([val]) => val.split(':')[0]);
        _esSort = _esSort.filter(s => validFields.includes(s.field));
        renderSortTags();
    }

    function renderSortTags() {
        const wrap = document.getElementById('es-sort-tags');
        if (!wrap) return;
        wrap.innerHTML = _esSort.map((s, i) => {
            const key      = `${s.field}:${s.dir}`;
            const labelKey = SORT_LABEL_KEYS[key] || key;
            const label    = t(labelKey);
            return `<span style="display:inline-flex;align-items:center;gap:3px;background:var(--abcona-blue);color:white;border-radius:12px;padding:2px 8px;font-size:0.72rem;white-space:nowrap">
                ${label}
                <span onclick="NamazuMod.removeSort(${i})" class="namazu-sort-remove">×</span>
            </span>`;
        }).join('');
    }

    function addSort(val) {
        if (!val) return;
        const [field, dir] = val.split(':');
        _esSort = _esSort.filter(s => s.field !== field);
        _esSort.push({field, dir});
        renderSortTags();
        const sel = document.getElementById('es-sort-add');
        if (sel) sel.value = '';
    }

    function removeSort(idx) {
        _esSort.splice(idx, 1);
        renderSortTags();
        if (_esQuery) doEsSearch(1);
    }

    async function doEsSearch(page) {
        _esPage  = page || 1;
        _esQuery = document.getElementById('es-search-q')?.value?.trim();
        _esIndex = document.getElementById('es-search-index')?.value || 'consultants';
        _esMax   = parseInt(document.getElementById('es-search-max')?.value) || 20;

        if (!_esQuery) return;

        const info = document.getElementById('es-info');
        const list = document.getElementById('es-results');
        if (list) list.innerHTML = `<div style="padding:10px;color:var(--text-secondary)">${t('namazu.admin.loading')}</div>`;

        const from    = (_esPage - 1) * _esMax;
        const exclude = _esExclude.join(',');

        try {
            let url = `${API_ES}?q=${encodeURIComponent(_esQuery)}&index=${_esIndex}&max=${_esMax}&from=${from}`;
            if (exclude) url += `&exclude=${encodeURIComponent(exclude)}`;
            if (_esSort.length) {
                const sortStr = _esSort.map(s => `${s.field}:${s.dir}`).join(',');
                url += `&sort=${encodeURIComponent(sortStr)}`;
            }

            const r    = await fetch(url, {cache: 'no-store'});
            const data = await r.json();

            const total = data.total || 0;
            const pages = Math.ceil(total / _esMax);

            if (info) info.textContent = `${total} ${t('namazu.results.total')} · Seite ${_esPage}/${pages}`;

            renderPagination(pages);

            if (!data.results || data.results.length === 0) {
                if (list) list.innerHTML = `<div style="padding:10px;color:var(--text-secondary)">${t('namazu.results.empty')}</div>`;
                return;
            }

            if (list) list.innerHTML = data.results.map(res => {
                if (res.type === 'profile') {
                    return `
                    <div class="namazu-result-item">
                        <div class="namazu-result-info">
                            <p class="namazu-result-name">${res.first} ${res.last}</p>
                            <p class="namazu-result-snippet">${res.funktion}</p>
                            <p class="namazu-result-snippet"><span class="namazu-badge-${res.status?.includes('aktiv') ? 'on' : 'off'}">${res.status}</span></p>
                        </div>
                        <span class="namazu-score">${t('namazu.results.score')} ${res.score}</span>
                        <a class="namazu-profile-btn" href="${res.profile_url}" target="_blank">
                            <i class="bi bi-person-badge"></i> ${t('namazu.profile.open')}
                        </a>
                    </div>`;
                } else if (res.type === 'email') {
                    const emailUrl = `${API_EMAIL}?account=${encodeURIComponent(res.account)}&folder=${encodeURIComponent(res.folder)}${res.uid ? '&uid=' + encodeURIComponent(res.uid) : '&message_id=' + encodeURIComponent(res.message_id)}`;
                    const alreadyExcluded = _esExclude.includes(res.account);
                    return `
                    <div class="namazu-result-item">
                        <div class="namazu-result-info">
                            <p class="namazu-result-name">${res.subject}</p>
                            <p class="namazu-result-snippet">
                                <i class="bi bi-person"></i> ${res.from} &nbsp;|&nbsp;
                                <i class="bi bi-calendar"></i> ${res.date} &nbsp;|&nbsp;
                                <i class="bi bi-folder"></i> ${res.account}/${res.folder}
                            </p>
                            <p class="namazu-result-snippet">${res.snippet}</p>
                        </div>
                        <span class="namazu-score">${t('namazu.results.score')} ${res.score}</span>
                        ${!alreadyExcluded ? `<button class="namazu-profile-btn"
                            onclick="NamazuMod.addExclude('${res.account}')"
                            title="${t('namazu.es.exclude_account')}">
                            <i class="bi bi-funnel"></i> -${res.account}
                        </button>` : ''}
                        <a class="namazu-profile-btn" href="${emailUrl}" target="_blank">
                            <i class="bi bi-envelope-open"></i> ${t('namazu.profile.open')}
                        </a>
                    </div>`;
                } else {
                    return `
                    <div class="namazu-result-item">
                        <div class="namazu-result-info">
                            <p class="namazu-result-name">${res.first} ${res.last}</p>
                            <p class="namazu-result-snippet">${res.headline}</p>
                            <p class="namazu-result-snippet">${res.location}${res.availability ? ' · ' + res.availability : ''}</p>
                        </div>
                        <span class="namazu-score">${t('namazu.results.score')} ${res.score}</span>
                    </div>`;
                }
            }).join('');

        } catch(e) {
            if (list) list.innerHTML = `<div style="color:var(--status-red);padding:10px">${e.message}</div>`;
        }
    }

    function renderPagination(pages) {
        const pg = document.getElementById('es-pagination');
        if (!pg || pages <= 1) { if (pg) pg.innerHTML = ''; return; }
        let html = `<button class="namazu-page-btn" onclick="NamazuMod.goPage(${_esPage-1})" ${_esPage===1?'disabled':''}>‹</button>`;
        const start = Math.max(1, _esPage-2);
        const end   = Math.min(pages, _esPage+2);
        for (let i = start; i <= end; i++) {
            html += `<button class="namazu-page-btn ${i===_esPage?'active':''}" onclick="NamazuMod.goPage(${i})">${i}</button>`;
        }
        html += `<button class="namazu-page-btn" onclick="NamazuMod.goPage(${_esPage+1})" ${_esPage===pages?'disabled':''}>›</button>`;
        pg.innerHTML = html;
    }

    function goPage(page) {
        if (page < 1) return;
        doEsSearch(page);
    }

    // ── QUERY HELPER CHIPS ─────────────────────────────────
    function initChips() {
        document.querySelectorAll('.namazu-chip').forEach(chip => {
            chip.addEventListener('click', () => {
                const input = document.getElementById('es-search-q');
                if (!input) return;
                const ins  = chip.dataset.insert;
                const set  = chip.dataset.set;
                const wrap = chip.dataset.wrap;
                if (set !== undefined) {
                    input.value = set;
                } else if (ins !== undefined) {
                    const pos = input.selectionStart || input.value.length;
                    input.value = input.value.slice(0, pos) + ins + input.value.slice(pos);
                } else if (wrap !== undefined) {
                    const [before, after] = wrap.split(';');
                    const start = input.selectionStart, end = input.selectionEnd;
                    const sel   = input.value.slice(start, end) || 'Begriff';
                    input.value = input.value.slice(0,start) + before + sel + after + input.value.slice(end);
                }
                input.focus();
            });
        });
    }

    // ── EXCLUDE TAGS ───────────────────────────────────────
    function renderExcludeTags() {
        const wrap = document.getElementById('es-exclude-wrap');
        const tags = document.getElementById('es-exclude-tags');
        if (!wrap || !tags) return;
        if (_esExclude.length === 0) { wrap.style.display = 'none'; return; }
        wrap.style.display = 'block';
        tags.innerHTML = _esExclude.map(acc =>
            `<span class="namazu-exclude-tag" onclick="NamazuMod.removeExclude('${acc}')">
                -${acc} <i class="bi bi-x"></i>
            </span>`
        ).join('');
    }

    function addExclude(acc) {
        if (!_esExclude.includes(acc)) {
            _esExclude.push(acc);
            renderExcludeTags();
            doEsSearch(1);
        }
    }

    function removeExclude(acc) {
        _esExclude = _esExclude.filter(a => a !== acc);
        renderExcludeTags();
        if (_esQuery) doEsSearch(1);
    }

    // ── ACCOUNTS ───────────────────────────────────────────
    async function loadAccounts() {
        const list = document.getElementById('namazu-accounts-list');
        if (!list) return;
        try {
            const r    = await fetch(API_ACCOUNTS, {cache: 'no-store'});
            const data = await r.json();
            if (!data.accounts) return;
            list.innerHTML = Object.entries(data.accounts).map(([user, cfg]) => {
                const badge = cfg.password
                    ? (cfg.enabled
                        ? `<span class="namazu-badge-on">${t('namazu.admin.active')}</span>`
                        : `<span class="namazu-badge-off">${t('namazu.admin.inactive')}</span>`)
                    : `<span class="namazu-badge-err">PW fehlt</span>`;
                const pw = cfg.password ? '••••••••' : '—';
                return `
                <div class="namazu-account-row">
                    <span class="namazu-account-name">${user}</span>
                    <span class="namazu-account-desc">${cfg.description || ''}</span>
                    <span class="namazu-account-pw">${pw}</span>
                    ${badge}
                    <button class="btn btn-sm btn-outline-secondary"
                            onclick="NamazuMod.editAccount('${user}')"
                            class="namazu-account-edit">
                        <i class="bi bi-pencil"></i>
                    </button>
                </div>`;
            }).join('');
        } catch(e) {}
    }

    function editAccount(user) {
        const pw = prompt(`Passwort für "${user}":`, '');
        if (pw === null) return;
        const enabled = confirm(`Account "${user}" aktivieren?`);
        fetch('/api/namazu/accounts/update/', {
            method: 'POST',
            headers: {'Content-Type': 'application/json', 'X-CSRFToken': getCsrf()},
            body: JSON.stringify({user, password: pw, enabled})
        }).then(r => r.json()).then(d => {
            if (d.success) loadAccounts();
        }).catch(() => {});
    }

    // ── NAMAZU STATUS ──────────────────────────────────────
    async function loadStatus() {
        try {
            const r    = await fetch(API_STATUS, {cache: 'no-store'});
            const data = await r.json();
            const set  = (id, val) => { const el = document.getElementById(id); if (el) el.textContent = val; };
            set('namazu-html-count',   data.html_count);
            set('namazu-index-size',   data.index_size_kb + ' KB');
            set('namazu-last-indexed', data.last_indexed);
            set('namazu-log',          data.log);
            set('namazu-err',          data.errors);
        } catch(e) {}
    }

    async function doReindex() {
        const btn = document.getElementById('namazu-reindex-btn');
        if (btn) btn.disabled = true;
        try {
            const r    = await fetch(API_REINDEX, {method:'POST', headers:{'X-CSRFToken':getCsrf()}, cache:'no-store'});
            const data = await r.json();
            const msg  = document.getElementById('namazu-reindex-msg');
            if (msg) {
                msg.textContent = data.started
                    ? `${t('namazu.admin.reindex_ok')} (PID ${data.pid})`
                    : t('namazu.admin.reindex_err');
                msg.style.color = data.started ? 'var(--status-green)' : 'var(--status-red)';
            }
        } catch(e) {} finally {
            if (btn) btn.disabled = false;
        }
    }

    // ── INIT ───────────────────────────────────────────────
    function init() {
        const esBtn = document.getElementById('es-search-btn');
        if (esBtn) esBtn.addEventListener('click', () => doEsSearch(1));

        const sortAdd = document.getElementById('es-sort-add');
        if (sortAdd) sortAdd.addEventListener('change', e => { addSort(e.target.value); doEsSearch(1); });

        const idxSel = document.getElementById('es-search-index');
        if (idxSel) idxSel.addEventListener('change', () => updateSortDropdown());
        updateSortDropdown();

        const esInput = document.getElementById('es-search-q');
        if (esInput) esInput.addEventListener('keydown', e => { if (e.key === 'Enter') doEsSearch(1); });

        const reindexBtn = document.getElementById('namazu-reindex-btn');
        if (reindexBtn) reindexBtn.addEventListener('click', doReindex);

        initChips();
        loadStatus();
        loadAccounts();
    }

    window.NamazuMod = { init, doEsSearch, goPage, addExclude, removeExclude, addSort, removeSort, updateSortDropdown, editAccount, loadStatus, doReindex };

})();
