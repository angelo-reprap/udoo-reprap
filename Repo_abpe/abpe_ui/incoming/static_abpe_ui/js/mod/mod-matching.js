/**
 * ABpE Matching — mod-matching.js
 * Tab-Switching, Stats laden, API-Calls
 * Alle Texte über _t() — kein hardcodierter Text
 */
'use strict';

window.Matching = (function() {

    const API = '/matching/api/';
    const cfg = () => window.MATCHING_CONFIG || {};
    const csrf = () => cfg().csrfToken || '';

    let _i18nReady = false;

    // ──────────────────────────────────────────────────
    // i18n
    // ──────────────────────────────────────────────────

    function _t(key) {
        const parts = key.split('.');
        let obj = window.i18nData || {};
        for (const p of parts) {
            if (!obj) return key;
            obj = obj[p];
        }
        return (typeof obj === 'string' && obj) ? obj : key;
    }

    // ──────────────────────────────────────────────────
    // INIT
    // ──────────────────────────────────────────────────

    function init() {
        console.log('🎯 Matching.init()');
        _i18nReady = true;
        _loadStats();
        _initTabs();
        _injectKiWizardButton();
        _activateTab(cfg().activeTab || 'anfragen');
        _handleDeepLink();
    }

    function applyI18n() {
        document.querySelectorAll('[data-i18n]').forEach(el => {
            const key = el.getAttribute('data-i18n');
            const val = _t(key);
            if (val && val !== key) el.textContent = val;
        });
    }

    // ──────────────────────────────────────────────────
    // STATS
    // ──────────────────────────────────────────────────

    function _loadStats() {
        fetch(API + 'stats/', { credentials: 'same-origin' })
            .then(r => r.json())
            .then(d => {
                if (!d.success) return;
                _setText('stat-open',      d.projects?.active ?? '—');
                _setText('stat-contacted', d.consultants?.contacted ?? '—');
                _setText('stat-progress',  d.consultants?.in_progress ?? '—');
                _setText('stat-placed',    d.projects?.placed ?? '—');
                const fu = d.consultants?.needs_followup;
                if (fu) {
                    _setText('stat-followup', fu);
                    const el = document.getElementById('stat-followup');
                    if (el) el.style.color = '#ef4444';
                }
            })
            .catch(e => console.warn('Stats:', e));
    }

    // ──────────────────────────────────────────────────
    // TABS
    // ──────────────────────────────────────────────────

    function _initTabs() {
        document.querySelectorAll('.matching-tab[data-tab]').forEach(tab => {
            tab.addEventListener('click', function(e) {
                e.preventDefault();
                _activateTab(this.dataset.tab);
                history.pushState({}, '', '/matching/?tab=' + this.dataset.tab);
            });
        });
    }

    function _activateTab(tabId) {
        document.querySelectorAll('.matching-tab-panel').forEach(p => {
            p.style.display = 'none';
        });
        document.querySelectorAll('.matching-tab').forEach(t => {
            t.classList.remove('active');
        });
        const panel = document.getElementById('tab-' + tabId);
        if (panel) panel.style.display = '';
        const tab = document.querySelector('.matching-tab[data-tab="' + tabId + '"]');
        if (tab) tab.classList.add('active');
        _loadTabContent(tabId);
    }

    function _loadTabContent(tabId) {
        const loading = document.getElementById('loading-' + tabId);
        const content = document.getElementById('content-' + tabId);
        if (!content) return;
        if (!_i18nReady) {
            setTimeout(() => _loadTabContent(tabId), 50);
            return;
        }
        if (content.dataset.loaded === '1') return;
        if (loading) loading.style.display = 'flex';
        switch(tabId) {
            case 'anfragen':  _loadAnfragen(content, loading); break;
            case 'neu':       _renderNeu(content, loading); break;
            case 'shortlist': _loadShortlistTab(content, loading); break;
            case 'kanban':    _loadKanbanTab(content, loading); break;
            case 'abschluss': _renderAbschlussPlaceholder(content, loading); break;
            case 'archiv':    _loadArchiv(content, loading); break;
            case 'crm':       _renderCrmPlaceholder(content, loading); break;
            case 'reporting': _loadReporting(content, loading); break;
            default: if (loading) loading.style.display = 'none';
        }
    }

    // ──────────────────────────────────────────────────
    // TAB: ANFRAGEN
    // ──────────────────────────────────────────────────

    function _loadAnfragen(content, loading) {
        const search = document.getElementById('anf-search')?.value || '';
        const status = document.getElementById('anf-status')?.value || '';
        let url = API + 'requests/?page=1&per_page=20';
        if (search) url += '&search=' + encodeURIComponent(search);
        if (status) url += '&status=' + encodeURIComponent(status);

        fetch(url, { credentials: 'same-origin' })
            .then(r => r.json())
            .then(d => {
                if (loading) loading.style.display = 'none';
                if (!d.success) {
                    content.innerHTML = '<p class="text-danger">' + _t('matching.err_load') + '</p>';
                    return;
                }

                let html = `
                <div style="display:flex;gap:8px;margin-bottom:10px;flex-wrap:wrap">
                    <input class="matching-form-input" style="flex:1;max-width:300px"
                           placeholder="${_t('matching.filter_search')}" id="anf-search"
                           oninput="Matching.searchAnfragen(this.value)">
                    <select class="matching-form-input" style="width:140px" id="anf-status"
                            onchange="Matching.filterAnfragen()">
                        <option value="">${_t('matching.filter_all_status')}</option>
                        <option value="draft">${_t('matching.opt_draft')}</option>
                        <option value="active">${_t('matching.opt_active')}</option>
                        <option value="matching">${_t('matching.opt_matching')}</option>
                        <option value="offers_sent">${_t('matching.opt_offers_sent')}</option>
                        <option value="placed">${_t('matching.opt_placed')}</option>
                    </select>
                </div>
                <div id="anf-list">`;

                if (!d.results || d.results.length === 0) {
                    html += `<div style="padding:30px;text-align:center;color:#888">
                        ${_t('matching.no_requests')}
                        <a href="#" onclick="Matching.switchTab('neu')">${_t('matching.first_request')} →</a>
                    </div>`;
                } else {
                    for (const p of d.results) {
                        const prioClass = 'prio-' + (p.priority || 3);
                        const pillClass = _statusPill(p.status);
                        html += `
                        <div class="matching-card" style="cursor:pointer">
                            <div style="display:flex;align-items:center;gap:8px"
                                 onclick="Matching.openRequestEdit('${p.id}')"
                                 title="${_escAttr(_kiT('open_request_edit', 'Anfrage öffnen / bearbeiten'))}">
                                <div class="matching-prio ${prioClass}"></div>
                                <div style="min-width:100px;font-size:10px;color:#888">${_esc(p.project_number || '')}</div>
                                <div style="flex:1;font-weight:700;font-size:12px;color:var(--abcona-blue);text-decoration:underline;text-underline-offset:2px">${_esc(p.title || '—')}</div>
                                <div style="font-size:11px;color:#666;min-width:100px">${_esc(p.customer_name || '')}</div>
                                <span class="matching-pill ${pillClass}">${_statusLabel(p.status)}</span>
                                <div style="font-size:10px;color:#888;min-width:50px;text-align:right">
                                    ${p.match_count ? p.match_count + _t('matching.matches_count') : '—'}
                                </div>
                            </div>
                            <div style="display:flex;gap:4px;margin-top:6px;justify-content:flex-end"
                                 onclick="event.stopPropagation()">
                                <button class="matching-btn-sm" style="font-size:10px"
                                        onclick="event.stopPropagation();Matching.openRequestEdit('${p.id}')">
                                    <i class="bi bi-pencil"></i> ${_esc(_kiT('btn_edit_request', 'Bearbeiten'))}
                                </button>
                                <button class="matching-btn-sm" style="font-size:10px"
                                        onclick="event.stopPropagation();Matching.openProject('${p.id}','shortlist')">
                                    <i class="bi bi-funnel"></i> ${_t('matching.tab_shortlist')}
                                </button>
                                <button class="matching-btn-sm" style="font-size:10px"
                                        onclick="event.stopPropagation();Matching.openProject('${p.id}','kanban')">
                                    <i class="bi bi-kanban"></i> ${_t('matching.tab_kanban')}
                                </button>
                                <button class="matching-btn-sm" style="font-size:10px"
                                        onclick="event.stopPropagation();Matching.openProject('${p.id}','abschluss')">
                                    <i class="bi bi-check2-circle"></i> ${_t('matching.tab_abschluss')}
                                </button>
                            </div>
                        </div>`;
                    }
                }

                html += '</div>';
                content.innerHTML = html;
                content.dataset.loaded = '1';
            })
            .catch(e => {
                if (loading) loading.style.display = 'none';
                content.innerHTML = '<p style="color:#ef4444;padding:20px">' + _t('matching.err_connection') + ': ' + e.message + '</p>';
            });
    }

    // ──────────────────────────────────────────────────
    // TAB: NEUE ANFRAGE
    // ──────────────────────────────────────────────────

    function _renderNeu(content, loading) {
        if (loading) loading.style.display = 'none';
        content.innerHTML = `
        <div class="matching-section-head" onclick="toggleSection(this)">
            ${_t('matching.section_customer')} <i class="bi bi-chevron-down"></i>
        </div>
        <div class="matching-section-body">
            <div class="matching-form-grid">
                <div class="matching-form-group">
                    <label class="matching-form-label">${_t('matching.neu_customer')}</label>
                    <input class="matching-form-input" id="new-customer"
                           placeholder="${_t('matching.customer_placeholder')}"
                           autocomplete="off">
                    <div id="new-customer-results" style="display:none"></div>
                    <input type="hidden" id="new-crm-account-id">
                    <div id="new-customer-linked" style="display:none;font-size:11px;margin-top:4px;color:#059669"></div>
                </div>
                <div class="matching-form-group">
                    <label class="matching-form-label">${_t('matching.neu_contact')}</label>
                    <input class="matching-form-input" id="new-contact"
                           placeholder="${_t('matching.contact_placeholder')}"
                           oninput="Matching.searchContacts(this.value)">
                    <div id="new-contact-results" style="display:none"></div>
                    <input type="hidden" id="new-crm-contact-id">
                </div>
                <div class="matching-form-group">
                    <label class="matching-form-label">${_kiT('contact_email', 'E-Mail Ansprechpartner')}</label>
                    <input class="matching-form-input" id="new-contact-email" type="email"
                           placeholder="name@firma.de">
                </div>
                <div class="matching-form-group">
                    <label class="matching-form-label">${_kiT('contact_phone', 'Telefon Ansprechpartner')}</label>
                    <input class="matching-form-input" id="new-contact-phone" type="tel"
                           placeholder="+49 …">
                </div>
            </div>
            <div id="matching-crm-suggest" style="display:none;margin-top:10px;padding:12px;
                 border-radius:8px;border:1px solid #f59e0b;background:rgba(245,158,11,.08);font-size:13px">
            </div>
        </div>
        <div class="matching-section-head" onclick="toggleSection(this)">
            ${_t('matching.section_details')} <i class="bi bi-chevron-down"></i>
        </div>
        <div class="matching-section-body">
            <div class="matching-form-grid">
                <div class="matching-form-group span2">
                    <label class="matching-form-label">
                        ${_t('matching.neu_text')}
                        <span style="color:#2563eb;margin-left:6px;font-size:10px">
                            <i class="bi bi-cpu"></i> ${_skillHint()}
                        </span>
                    </label>
                    <textarea class="matching-form-textarea" id="new-description"
                              placeholder="${_t('matching.text_placeholder')}"></textarea>
                </div>
                <div class="matching-form-group span2">
                    <label class="matching-form-label">${_t('matching.neu_title')}</label>
                    <input class="matching-form-input" id="new-title"
                           placeholder="${_t('matching.title_placeholder')}">
                </div>
                <div class="matching-form-group span2">
                    <label class="matching-form-label">${_kiT('neu_skills', 'Skills (für Matching)')}</label>
                    <div style="display:flex;gap:6px;align-items:center;flex-wrap:wrap">
                        <input class="matching-form-input" id="new-skills" style="flex:1;min-width:180px"
                               placeholder="${_escAttr(_kiT('skills_placeholder', 'z.B. Fortinet, Firewall, Network Security'))}">
                        <button type="button" class="matching-btn-sm" id="btn-skills-from-text"
                                title="${_escAttr(_kiT('skills_from_text_title', 'Skills aus Anfrage-Text übernehmen (Qualifikationen / Skills-Zeile)'))}"
                                onclick="Matching.fillSkillsFromText()">
                            <i class="bi bi-magic"></i> ${_esc(_kiT('skills_from_text', 'aus Text'))}
                        </button>
                    </div>
                    <div style="font-size:10px;color:#888;margin-top:4px">
                        ${_esc(_kiT('skills_hint', 'Ohne Skills matcht die Engine fast alle Berater mit ähnlichem Score — Mist-Ergebnisse. Muss-Skills zuerst, Nice-to-have danach.'))}
                    </div>
                    <input type="hidden" id="new-skills-json" value="">
                </div>
                <div class="matching-form-group">
                    <label class="matching-form-label">${_t('matching.neu_start_label')}</label>
                    <input class="matching-form-input" type="date" id="new-start">
                </div>
                <div class="matching-form-group">
                    <label class="matching-form-label">${_t('matching.neu_duration_label')}</label>
                    <input class="matching-form-input" type="number" id="new-duration" value="6">
                </div>
                <div class="matching-form-group">
                    <label class="matching-form-label">${_t('matching.neu_location')}</label>
                    <input class="matching-form-input" id="new-location"
                           placeholder="${_t('matching.location_placeholder')}">
                </div>
                <div class="matching-form-group">
                    <label class="matching-form-label">${_t('matching.neu_rate_label')}</label>
                    <input class="matching-form-input" type="number" id="new-rate-max"
                           placeholder="${_t('matching.rate_placeholder')}">
                </div>
            </div>
        </div>
        <div style="display:flex;gap:8px;justify-content:flex-end;margin-top:8px">
            <button class="matching-btn-sm"
                    onclick="Matching.switchTab('anfragen')">${_t('matching.btn_cancel')}</button>
            <button class="matching-btn-primary" onclick="Matching.saveNewRequest()">
                <i class="bi bi-save"></i> ${_t('matching.btn_save')}
            </button>
        </div>`;
        content.dataset.loaded = '1';
        _bindCustomerField();
    }

    function _bindCustomerField() {
        const inp = document.getElementById('new-customer');
        if (!inp || inp.dataset.bound === '1') return;
        inp.dataset.bound = '1';
        let t = null;
        inp.addEventListener('input', function () {
            clearTimeout(t);
            const q = (inp.value || '').trim();
            const curId = _val('new-crm-account-id');
            // Verknüpfung nur lösen wenn Name nicht mehr zum verknüpften passt
            if (curId) {
                const cached = _accountIdByNorm[_normFirmName(q)];
                if (cached && cached === curId) {
                    // Name noch exakt derselbe Account → Link behalten, Liste zu
                    const res = document.getElementById('new-customer-results');
                    if (res) res.style.display = 'none';
                    return;
                }
                clearCustomerLink();
            }
            t = setTimeout(function () {
                if (q.length < 2) return;
                _resolveCustomerField(q);
            }, 280);
        });
        inp.addEventListener('focus', function () {
            const q = (inp.value || '').trim();
            if (_val('new-crm-account-id')) return; // schon verknüpft → keine Liste
            if (q.length >= 2) searchAccounts(q);
        });
    }

    function _resolveCustomerField(q) {
        const n = (q || '').trim();
        if (n.length < 2) return;
        _searchAccountsAny(n).then(hits => {
            const exact = _findExactFirm(hits, n);
            if (exact) {
                _pickCrmAccount(exact);
                return;
            }
            // Mehrere / unklar → Trefferliste (Stadt nur Anzeige)
            searchAccounts(n);
            if (!(hits || []).length) clearCustomerLink();
        }).catch(() => searchAccounts(n));
    }

    function _loadShortlistTab(content, loading) {
        const projectId = window.MATCHING_CONFIG && window.MATCHING_CONFIG.activeProject;
        if (projectId) {
            _loadShortlistForProject(projectId, content);
            return;
        }
        _loadRequestPicker(content, loading, {
            targetTab: 'shortlist',
            hint: _kiT('shortlist_pick_hint', 'Anfrage wählen — Shortlist öffnen'),
            icon: 'bi-funnel',
            listId: 'shortlist-pick-list',
        });
    }

    /** Gemeinsame Anfragen-Liste (Betreff) für Shortlist / Kanban / … */
    function _loadRequestPicker(content, loading, opts) {
        opts = opts || {};
        const targetTab = opts.targetTab || 'shortlist';
        const hint = opts.hint || _kiT('request_pick_hint', 'Anfrage wählen');
        const icon = opts.icon || 'bi-list-ul';
        const listId = opts.listId || 'request-pick-list';
        if (loading) loading.style.display = 'flex';
        fetch(API + 'requests/?page=1&per_page=50', { credentials: 'same-origin' })
            .then(r => r.json())
            .then(d => {
                if (loading) loading.style.display = 'none';
                if (!d.success) {
                    content.innerHTML = '<p class="text-danger">' + _t('matching.err_load') + '</p>';
                    content.dataset.loaded = '1';
                    return;
                }
                let html = `
                <div style="margin-bottom:10px;font-size:12px;color:#888">
                    <i class="bi ${icon}"></i> ${_esc(hint)}
                </div>
                <div id="${listId}">`;

                if (!d.results || d.results.length === 0) {
                    html += `<div style="padding:30px;text-align:center;color:#888">
                        ${_t('matching.no_requests')}
                        <a href="#" onclick="Matching.switchTab('neu');return false;">${_t('matching.first_request')} →</a>
                    </div>`;
                } else {
                    for (const p of d.results) {
                        const prioClass = 'prio-' + (p.priority || 3);
                        const pillClass = _statusPill(p.status);
                        const title = p.title || p.project_number || '—';
                        html += `
                        <div class="matching-card" style="cursor:pointer"
                             onclick="Matching.openProject('${p.id}','${targetTab}')">
                            <div style="display:flex;align-items:center;gap:8px">
                                <div class="matching-prio ${prioClass}"></div>
                                <div style="min-width:90px;font-size:10px;color:#888">${_esc(p.project_number || '')}</div>
                                <div style="flex:1;font-weight:700;font-size:13px">${_esc(title)}</div>
                                <div style="font-size:11px;color:#666;min-width:90px">${_esc(p.customer_name || '')}</div>
                                <span class="matching-pill ${pillClass}">${_statusLabel(p.status)}</span>
                                <i class="bi bi-chevron-right" style="color:#aaa;font-size:12px"></i>
                            </div>
                        </div>`;
                    }
                }
                html += '</div>';
                content.innerHTML = html;
                content.dataset.loaded = '1';
            })
            .catch(e => {
                if (loading) loading.style.display = 'none';
                content.innerHTML = '<p style="color:#ef4444;padding:20px">' +
                    _t('matching.err_connection') + ': ' + _esc(e.message || String(e)) + '</p>';
                content.dataset.loaded = '1';
            });
    }

    function pickShortlistRequest() {
        pickRequestForTab('shortlist');
    }

    function pickKanbanRequest() {
        pickRequestForTab('kanban');
    }

    function pickRequestForTab(tabId) {
        if (window.MATCHING_CONFIG) window.MATCHING_CONFIG.activeProject = null;
        const content = document.getElementById('content-' + tabId);
        const loading = document.getElementById('loading-' + tabId);
        if (content) {
            content.dataset.loaded = '0';
            content.innerHTML = '';
            if (tabId === 'kanban') {
                _loadRequestPicker(content, loading, {
                    targetTab: 'kanban',
                    hint: _kiT('kanban_pick_hint', 'Anfrage wählen — Workflow-Board öffnen'),
                    icon: 'bi-kanban',
                    listId: 'kanban-pick-list',
                });
            } else {
                _loadRequestPicker(content, loading, {
                    targetTab: 'shortlist',
                    hint: _kiT('shortlist_pick_hint', 'Anfrage wählen — Shortlist öffnen'),
                    icon: 'bi-funnel',
                    listId: 'shortlist-pick-list',
                });
            }
        }
        switchTab(tabId);
    }

    function _loadKanbanTab(content, loading) {
        const projectId = window.MATCHING_CONFIG && window.MATCHING_CONFIG.activeProject;
        if (projectId) {
            _loadKanban(content, loading);
            return;
        }
        _loadRequestPicker(content, loading, {
            targetTab: 'kanban',
            hint: _kiT('kanban_pick_hint', 'Anfrage wählen — Workflow-Board öffnen'),
            icon: 'bi-kanban',
            listId: 'kanban-pick-list',
        });
    }

    function _loadKanban(content, loading) {
        const projectId = window.MATCHING_CONFIG.activeProject;
        if (!projectId) {
            _loadRequestPicker(content, loading, {
                targetTab: 'kanban',
                hint: _kiT('kanban_pick_hint', 'Anfrage wählen — Workflow-Board öffnen'),
                icon: 'bi-kanban',
                listId: 'kanban-pick-list',
            });
            return;
        }

        if (loading) loading.style.display = 'flex';
        fetch(API + 'requests/' + projectId + '/kanban/', { credentials: 'same-origin' })
            .then(r => r.json())
            .then(d => {
                if (loading) loading.style.display = 'none';
                if (!d.success) {
                    content.innerHTML = '<p>' + _t('matching.err_load') + '</p>';
                    return;
                }

                const projLabel = [d.project_number, d.project_title].filter(Boolean).join(' · ');
                let html = `
                <div style="display:flex;align-items:center;gap:10px;margin-bottom:10px;flex-wrap:wrap">
                    <button type="button" class="matching-btn-sm" onclick="Matching.pickKanbanRequest()">
                        <i class="bi bi-list-ul"></i> ${_esc(_kiT('kanban_pick_back', 'Anfragen'))}
                    </button>
                    <div style="font-size:12px;color:#888;flex:1;min-width:120px">
                        ${_esc(projLabel)} · ${d.total} ${_t('matching.matches_count')}
                    </div>
                </div>
                <div class="matching-kanban-wrap" id="kanban-board">`;

                for (const col of d.columns) {
                    html += `
                    <div class="matching-kanban-col" data-col-id="${col.id}"
                         ondragover="event.preventDefault()"
                         ondrop="Matching.kanbanDrop(event,'${col.id}')">
                        <div class="matching-kanban-head"
                             style="background:${col.color};color:${col.text_color}">
                            ${col.label}
                            <span class="matching-kanban-cnt">${col.count}</span>
                        </div>
                        <div class="matching-kanban-body" id="col-${col.id}">`;

                    if (col.cards.length === 0) {
                        html += `<div style="text-align:center;font-size:10px;color:#aaa;padding:10px">${_t('matching.kanban_empty')}</div>`;
                    }

                    for (const card of col.cards) {
                        const scoreColor = card.match_score >= 0.7 ? '#155724' :
                                           card.match_score >= 0.5 ? '#856404' : '#666';
                        const alertHtml = card.needs_followup
                            ? `<div style="color:#ef4444;font-size:9px;margin-top:3px">⚠ ${_t('matching.needs_followup')}</div>` : '';
                        const daysHtml = card.days_since !== null
                            ? `<div style="font-size:9px;color:#888">${card.days_since}d</div>` : '';

                        // Unter Schwellwert → Reserve (ausgegraut, kein Drag)
                        const threshold = parseFloat(document.getElementById('threshold-val')?.textContent || '0.45');
                        const isBelowThreshold = col.id === 'shortlist' && card.match_score < threshold;
                        const cardStyle = isBelowThreshold
                            ? 'padding:7px 8px;font-size:11px;opacity:0.4;cursor:not-allowed;border:1px dashed #ccc'
                            : 'padding:7px 8px;font-size:11px;cursor:grab';
                        const draggable = isBelowThreshold ? 'false' : 'true';
                        const reserveHtml = isBelowThreshold
                            ? `<div style="font-size:9px;color:#999;margin-top:2px">⏸ ${_t('matching.reserve')}</div>` : '';

                        html += `
                        <div class="matching-card" style="${cardStyle}"
                             draggable="${draggable}"
                             data-match-id="${card.id}"
                             data-score="${card.match_score}"
                             data-stage="${_escAttr(col.id)}"
                             data-name="${_escAttr(card.name || '')}"
                             data-location="${_escAttr(card.location || '')}"
                             data-phone="${_escAttr(card.phone || card.telefon || card.mobile || '')}"
                             data-email="${_escAttr(card.email || card.mail || '')}"
                             data-crm="${_escAttr(card.crm_contact_id || card.crm_id || card.consultant_crm_id || '')}"
                             ondragstart="${isBelowThreshold ? '' : `Matching.kanbanDragStart(event,'${card.id}')`}"
                             onclick="Matching.kanbanCardClick('${card.id}')">
                            <div style="display:flex;justify-content:space-between;align-items:start">
                                <div style="font-weight:700;color:var(--abcona-blue);text-decoration:underline;text-underline-offset:2px">${_esc(card.name || '')}</div>
                                <div style="font-weight:700;color:${scoreColor};font-size:10px">
                                    ${Math.round(card.match_score*100)}%
                                </div>
                            </div>
                            <div style="font-size:10px;color:#888;margin-top:2px">${_esc(card.location || '')}</div>
                            ${alertHtml}
                            ${reserveHtml}
                            <div style="display:flex;justify-content:space-between;margin-top:5px">
                                ${daysHtml}
                                <div style="display:flex;gap:3px">
                                    <button class="matching-btn-sm matching-btn-call" style="font-size:9px;padding:2px 5px"
                                            title="${_esc(_kiT('btn_call', 'Anrufen'))}"
                                            onclick="event.stopPropagation();Matching.call('${card.id}')">
                                        <i class="bi bi-telephone"></i>
                                    </button>
                                    <button class="matching-btn-sm matching-btn-mail" style="font-size:9px;padding:2px 5px"
                                            title="${_esc(_kiT('btn_email', 'E-Mail'))}"
                                            onclick="event.stopPropagation();Matching.sendEmail('${card.id}','${_escAttr(col.id)}')">
                                        <i class="bi bi-envelope"></i>
                                    </button>
                                </div>
                            </div>
                        </div>`;
                    }

                    html += `</div></div>`;
                }
                html += '</div>';

                content.innerHTML = html;
                content.dataset.loaded = '1';
            })
            .catch(e => {
                if (loading) loading.style.display = 'none';
                content.innerHTML = '<p style="color:#ef4444;padding:20px">' + _t('matching.err_connection') + ': ' + e.message + '</p>';
            });
    }

    function _renderAbschlussPlaceholder(content, loading) {
        _loadAbschluss(content, loading);
    }

    function _loadAbschluss(content, loading) {
        const projectId = window.MATCHING_CONFIG.activeProject;
        if (!projectId) {
            if (loading) loading.style.display = 'none';
            content.innerHTML = `<div style="padding:30px;text-align:center;color:#888">
                <i class="bi bi-check2-circle" style="font-size:32px;display:block;margin-bottom:8px"></i>
                ${_t('matching.no_abschluss')}
            </div>`;
            content.dataset.loaded = '1';
            return;
        }

        fetch(API + 'requests/' + projectId + '/abschluss/', { credentials: 'same-origin' })
            .then(r => r.json())
            .then(d => {
                if (loading) loading.style.display = 'none';
                if (!d.success) {
                    content.innerHTML = '<p>' + _t('matching.err_load') + '</p>';
                    return;
                }

                const p = d.project;
                const filledSlots  = d.placed.length;
                const totalSlots   = p.open_positions;
                const remainSlots  = totalSlots - filledSlots;
                const pctFilled    = totalSlots > 0 ? Math.round(filledSlots / totalSlots * 100) : 0;
                const statusColor  = filledSlots >= totalSlots ? '#155724' :
                                     filledSlots > 0           ? '#856404' : '#163258';

                let html = `
                <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px;margin-bottom:16px">
                    <div class="matching-card" style="text-align:center">
                        <div style="font-size:28px;font-weight:700;color:${statusColor}">${filledSlots}/${totalSlots}</div>
                        <div style="font-size:11px;color:#888">${_t('matching.slots_filled')}</div>
                        <div style="background:#eee;border-radius:4px;height:6px;margin-top:6px">
                            <div style="background:${statusColor};width:${pctFilled}%;height:6px;border-radius:4px"></div>
                        </div>
                    </div>
                    <div class="matching-card" style="text-align:center">
                        <div style="font-size:28px;font-weight:700;color:#163258">${remainSlots}</div>
                        <div style="font-size:11px;color:#888">${_t('matching.slots_open')}</div>
                    </div>
                    <div class="matching-card" style="text-align:center">
                        <div style="font-size:28px;font-weight:700;color:#163258">${d.total_consultants}</div>
                        <div style="font-size:11px;color:#888">${_t('matching.total_consultants')}</div>
                    </div>
                </div>

                <!-- Vermittelte Berater -->
                <div class="matching-section-head open" onclick="toggleSection(this)">
                    <i class="bi bi-check2-circle"></i>
                    ${_t('matching.placed_consultants')} (${filledSlots})
                    <i class="bi bi-chevron-down"></i>
                </div>
                <div class="matching-section-body open">`;

                if (d.placed.length === 0) {
                    html += `<div style="padding:16px;color:#888">${_t('matching.no_placed_yet')}</div>`;
                } else {
                    for (const pc of d.placed) {
                        html += `
                        <div class="matching-section-head open" style="background:var(--abcona-blue)"
                             onclick="toggleSection(this)">
                            <div style="font-size:18px">✅</div>
                            <div style="flex:1">
                                <div style="font-weight:700;font-size:13px">${pc.name}</div>
                                <div style="font-size:10px;opacity:0.8">${pc.aid}</div>
                            </div>
                            <div style="font-size:11px;opacity:0.8;text-align:right;margin-right:8px">
                                ${_t('matching.match_score')}: ${Math.round(pc.match_score*100)}%
                            </div>
                            <div style="display:flex;gap:4px" onclick="event.stopPropagation()">
                                <button class="matching-btn-sm" style="font-size:10px;background:rgba(255,255,255,0.2);color:white;border-color:rgba(255,255,255,0.4)"
                                        onclick="Matching.sendContract('${pc.id}')">
                                    <i class="bi bi-file-earmark-text"></i> ${_t('matching.btn_contract')}
                                </button>
                                <button class="matching-btn-sm" style="font-size:10px;background:rgba(255,255,255,0.2);color:white;border-color:rgba(255,255,255,0.4)"
                                        onclick="Matching.sendPlacementStart('${pc.id}')">
                                    <i class="bi bi-envelope"></i> ${_t('matching.btn_placement_mail')}
                                </button>
                            </div>
                            <i class="bi bi-chevron-down"></i>
                        </div>
                        <div class="matching-section-body open">
                            <div class="matching-form-grid">
                                <div class="matching-form-group">
                                    <label class="matching-form-label">${_t('matching.agreed_rate')}</label>
                                    <div style="display:flex;gap:4px">
                                        <input class="matching-form-input" type="number"
                                               id="rate-${pc.id}"
                                               value="${pc.agreed_rate || ''}"
                                               placeholder="€/h">
                                        <span style="line-height:36px;font-size:11px;color:#888">€/h</span>
                                    </div>
                                </div>
                                <div class="matching-form-group">
                                    <label class="matching-form-label">${_t('matching.agreed_start')}</label>
                                    <input class="matching-form-input" type="date"
                                           id="start-${pc.id}"
                                           value="${pc.agreed_start_date || ''}">
                                </div>
                                <div class="matching-form-group">
                                    <label class="matching-form-label">${_t('matching.agreed_duration')}</label>
                                    <div style="display:flex;gap:4px">
                                        <input class="matching-form-input" type="number"
                                               id="duration-${pc.id}"
                                               value="${pc.agreed_duration || ''}"
                                               placeholder="6">
                                        <span style="line-height:36px;font-size:11px;color:#888">${_t('matching.months')}</span>
                                    </div>
                                </div>
                                <div class="matching-form-group">
                                    <label class="matching-form-label">${_t('matching.placed_since')}</label>
                                    <input class="matching-form-input" type="date"
                                           id="placedat-${pc.id}"
                                           value="${pc.placed_at || ''}">
                                </div>
                                <div class="matching-form-group span2">
                                    <label class="matching-form-label">${_t('matching.placement_notes')}</label>
                                    <textarea class="matching-form-textarea" style="min-height:60px"
                                              id="notes-${pc.id}"
                                              placeholder="${_t('matching.placement_notes_placeholder')}">${pc.placement_notes || ''}</textarea>
                                </div>
                            </div>

                            <!-- Vertragseingang vom Kunden -->
                            <div style="margin-top:12px;padding:10px;background:var(--abcona-gray-card);border-radius:8px;border:1px solid var(--border-color)">
                                <div style="font-weight:700;font-size:11px;margin-bottom:8px;color:var(--abcona-blue)">
                                    <i class="bi bi-file-earmark-check"></i>
                                    ${_t('matching.contract_from_client')}
                                </div>
                                <div class="matching-form-grid">
                                    <div class="matching-form-group" style="display:flex;align-items:center;gap:8px">
                                        <input type="checkbox" id="contract-received-${pc.id}"
                                               ${pc.client_contract_received ? 'checked' : ''}
                                               style="width:16px;height:16px;cursor:pointer"
                                               onchange="document.getElementById('contract-date-row-${pc.id}').style.display=this.checked?'contents':'none'">
                                        <label style="font-size:12px;cursor:pointer" for="contract-received-${pc.id}">
                                            ${_t('matching.contract_received')}
                                        </label>
                                    </div>
                                    <div class="matching-form-group" id="contract-date-row-${pc.id}"
                                         style="display:${pc.client_contract_received ? 'contents' : 'none'}">
                                        <label class="matching-form-label">
                                            ${_t('matching.contract_received_at')}
                                            <span style="color:#999;font-weight:400"> (${_t('matching.optional')})</span>
                                        </label>
                                        <input class="matching-form-input" type="date"
                                               id="contract-date-${pc.id}"
                                               value="${pc.client_contract_received_at || ''}">
                                    </div>
                                    <div class="matching-form-group" id="contract-channel-row-${pc.id}"
                                         style="display:${pc.client_contract_received ? 'contents' : 'none'}">
                                        <label class="matching-form-label">
                                            ${_t('matching.contract_channel')}
                                            <span style="color:#999;font-weight:400"> (${_t('matching.optional')})</span>
                                        </label>
                                        <select class="matching-form-input" id="contract-channel-${pc.id}">
                                            <option value="">— ${_t('matching.not_specified')} —</option>
                                            <option value="email"   ${pc.client_contract_channel==='email'   ?'selected':''}>E-Mail</option>
                                            <option value="post"    ${pc.client_contract_channel==='post'    ?'selected':''}>Post</option>
                                            <option value="fax"     ${pc.client_contract_channel==='fax'     ?'selected':''}>Fax</option>
                                            <option value="portal"  ${pc.client_contract_channel==='portal'  ?'selected':''}>Portal</option>
                                            <option value="other"   ${pc.client_contract_channel==='other'   ?'selected':''}>Sonstiges</option>
                                        </select>
                                    </div>
                                    <div class="matching-form-group" id="contract-sender-row-${pc.id}"
                                         style="display:${pc.client_contract_received ? 'contents' : 'none'}">
                                        <label class="matching-form-label">
                                            ${_t('matching.contract_sender')}
                                            <span style="color:#999;font-weight:400"> (${_t('matching.optional')})</span>
                                        </label>
                                        <input class="matching-form-input" type="text"
                                               id="contract-sender-${pc.id}"
                                               value="${pc.client_contract_sender || ''}"
                                               placeholder="${_t('matching.contract_sender_placeholder')}">
                                    </div>
                                    <div class="matching-form-group span2">
                                        <label class="matching-form-label">${_t('matching.contract_note')}</label>
                                        <input class="matching-form-input" id="contract-note-${pc.id}"
                                               value="${pc.client_contract_note || ''}"
                                               placeholder="${_t('matching.contract_note_placeholder')}">
                                    </div>
                                </div>
                            </div>
                            <div style="display:flex;gap:8px;justify-content:flex-end;margin-top:8px">
                                <button class="matching-btn-primary" style="font-size:11px"
                                        onclick="Matching.savePlacementDetails('${pc.id}','${projectId}')">
                                    <i class="bi bi-save"></i> ${_t('matching.btn_save_details')}
                                </button>
                            </div>
                        </div>`;
                    }
                }
                html += `</div>`;

                // Noch offene Slots
                if (remainSlots > 0) {
                    html += `
                    <div class="matching-section-head" onclick="toggleSection(this)" style="margin-top:8px">
                        <i class="bi bi-search"></i>
                        ${_t('matching.open_slots')} (${remainSlots})
                        <i class="bi bi-chevron-down"></i>
                    </div>
                    <div class="matching-section-body">
                        <div style="padding:12px;color:#888;font-size:12px">
                            ${remainSlots} ${_t('matching.slots_still_open')}
                            <button class="matching-btn-primary" style="margin-left:12px;font-size:10px"
                                    onclick="Matching.openProject('${projectId}','shortlist')">
                                <i class="bi bi-funnel"></i> ${_t('matching.back_to_shortlist')}
                            </button>
                        </div>
                    </div>`;
                }

                // Projektabschluss — Projekt schließen
                html += `
                <div class="matching-section-head" onclick="toggleSection(this)" style="margin-top:8px">
                    <i class="bi bi-folder-check"></i>
                    ${_t('matching.close_project')}
                    <i class="bi bi-chevron-down"></i>
                </div>
                <div class="matching-section-body">
                    <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;padding:4px">
                        <div class="matching-form-group">
                            <label class="matching-form-label">${_t('matching.close_reason_label')}</label>
                            <select class="matching-form-input" id="close-reason">
                                <option value="placed">${_t('matching.close_placed')}</option>
                                <option value="partial">${_t('matching.close_partial')}</option>
                                <option value="cancelled">${_t('matching.close_cancelled')}</option>
                                <option value="not_placed">${_t('matching.close_not_placed')}</option>
                            </select>
                        </div>
                        <div class="matching-form-group">
                            <label class="matching-form-label">${_t('matching.close_note_label')}</label>
                            <input class="matching-form-input" id="close-note"
                                   placeholder="${_t('matching.close_note_placeholder')}">
                        </div>
                    </div>
                    <div style="display:flex;gap:8px;justify-content:flex-end;margin-top:8px">
                        <button class="matching-btn-primary" onclick="Matching.closeProject('${projectId}')">
                            <i class="bi bi-folder-check"></i> ${_t('matching.btn_close_project')}
                        </button>
                    </div>
                </div>`;

                content.innerHTML = html;
                content.dataset.loaded = '1';
            })
            .catch(e => {
                if (loading) loading.style.display = 'none';
                content.innerHTML = '<p style="color:#ef4444;padding:20px">' + e.message + '</p>';
            });
    }

    function _renderCrmPlaceholder(content, loading) {
        if (loading) loading.style.display = 'none';
        content.innerHTML = `<div style="padding:30px;text-align:center;color:#888">
            <i class="bi bi-building" style="font-size:32px;display:block;margin-bottom:8px"></i>
            ${_t('matching.no_crm')}
        </div>`;
        content.dataset.loaded = '1';
    }

    // ──────────────────────────────────────────────────
    // TAB: ARCHIV
    // ──────────────────────────────────────────────────

    function _loadArchiv(content, loading) {
        fetch(API + 'requests/?archived=1&per_page=20', { credentials: 'same-origin' })
            .then(r => r.json())
            .then(d => {
                if (loading) loading.style.display = 'none';
                if (!d.success || !d.results?.length) {
                    content.innerHTML = `<div style="padding:30px;text-align:center;color:#888">
                        ${_t('matching.archiv_no_data')}
                    </div>`;
                    content.dataset.loaded = '1';
                    return;
                }
                let html = '<div id="archiv-list">';
                for (const p of d.results) {
                    const pillClass = p.status === 'placed' ? 'pill-placed' : 'pill-archived';
                    html += `
                    <div class="matching-card" onclick="Matching.toggleArchiveDetail(this)">
                        <div style="display:flex;align-items:center;gap:8px">
                            <span class="matching-pill ${pillClass}">${_statusLabel(p.status)}</span>
                            <div style="flex:1;font-weight:700;font-size:12px">${p.project_number} · ${p.title}</div>
                            <div style="font-size:10px;color:#888">${p.customer_name}</div>
                            <span style="font-size:12px;color:#888">▶</span>
                        </div>
                        <div class="matching-archive-detail">
                            <div style="color:#888">${p.customer_name} · ${p.match_count} ${_t('matching.matches_count')}</div>
                        </div>
                    </div>`;
                }
                html += '</div>';
                content.innerHTML = html;
                content.dataset.loaded = '1';
            })
            .catch(e => {
                if (loading) loading.style.display = 'none';
                content.innerHTML = '<p style="color:#ef4444;padding:20px">' + _t('matching.err_connection') + ': ' + e.message + '</p>';
            });
    }

    // ──────────────────────────────────────────────────
    // TAB: SHORTLIST
    // ──────────────────────────────────────────────────

    function _loadShortlistForProject(projectId, content) {
        const loading = document.getElementById('loading-shortlist');
        if (loading) loading.style.display = 'flex';

        fetch(API + 'requests/' + projectId + '/shortlist/', { credentials: 'same-origin' })
            .then(r => r.json())
            .then(d => {
                if (loading) loading.style.display = 'none';
                if (!d.success) {
                    content.innerHTML = '<p>' + _t('matching.err_load_short') + '</p>';
                    return;
                }

                const threshold = d.threshold || 0.5;
                const srcCounts = d.source_counts || { db: 0, es: 0, gulp: 0, flm: 0 };
                const boList = Array.isArray(d.backoffice) ? d.backoffice : [];
                // Dropdown zählt Shortlist + Backoffice — sonst Gulp/FLM immer (0)
                const boBySrc = { db: 0, es: 0, gulp: 0, flm: 0 };
                boList.forEach(b => {
                    const s = String(b.match_source || '').toLowerCase();
                    if (Object.prototype.hasOwnProperty.call(boBySrc, s)) boBySrc[s] += 1;
                });
                const dropCounts = {
                    db: (srcCounts.db || 0) + boBySrc.db,
                    es: (srcCounts.es || 0) + boBySrc.es,
                    gulp: (srcCounts.gulp || 0) + boBySrc.gulp,
                    flm: (srcCounts.flm || 0) + boBySrc.flm,
                };
                const totalHits = (d.count || 0) + boList.length;
                const projLabel = [d.project_number, d.project_title || d.title].filter(Boolean).join(' · ');
                const _srcBadge = (src, linkStatus) => {
                    const s = String(src || 'db').toLowerCase();
                    const map = {
                        db:   { label: 'DB',   bg: '#e8f0fe', fg: '#163258', bd: '#93c5fd' },
                        es:   { label: 'ES',   bg: '#ecfdf5', fg: '#065f46', bd: '#6ee7b7' },
                        gulp: { label: 'Gulp', bg: '#fff7ed', fg: '#9a3412', bd: '#fdba74' },
                        flm:  { label: 'FLM',  bg: '#f5f3ff', fg: '#5b21b6', bd: '#c4b5fd' },
                    };
                    const m = map[s] || map.db;
                    let html = `<span class="matching-src-badge" title="Quelle: ${m.label}"
                        style="display:inline-block;font-size:9px;font-weight:700;letter-spacing:.03em;
                               padding:1px 6px;border-radius:3px;border:1px solid ${m.bd};
                               background:${m.bg};color:${m.fg};margin-left:6px;vertical-align:middle">${m.label}</span>`;
                    if (linkStatus === 'known' && (s === 'gulp' || s === 'flm')) {
                        html += `<span title="Im Bestand bekannt — Kontakt nutzbar"
                            style="display:inline-block;font-size:9px;font-weight:700;padding:1px 6px;border-radius:3px;
                                   border:1px solid #86efac;background:#f0fdf4;color:#166534;margin-left:4px">bekannt</span>`;
                    }
                    return html;
                };
                let html = `
                <div style="display:flex;align-items:center;gap:10px;margin-bottom:10px;flex-wrap:wrap">
                    <button type="button" class="matching-btn-sm" onclick="Matching.pickShortlistRequest()">
                        <i class="bi bi-list-ul"></i> ${_esc(_kiT('shortlist_pick_back', 'Anfragen'))}
                    </button>
                    <div style="font-size:12px;color:#888;flex:1;min-width:120px">${_esc(projLabel)}</div>
                    ${(d.required_skills || d.skills || []).length
                        ? `<div style="font-size:11px;color:#163258;max-width:420px">
                             <strong>Skills:</strong> ${_esc((d.required_skills || d.skills || []).map(s =>
                               typeof s === 'string' ? s : (s && s.name) || ''
                             ).filter(Boolean).slice(0, 12).join(', '))}
                           </div>`
                        : `<div style="font-size:11px;color:#b45309">⚠ ${_esc(_kiT('no_skills_on_project', 'Keine Skills an der Anfrage — Matching oft Mist. „Erneut matchen“ + Skills eingeben.'))}</div>`
                    }
                </div>
                <div class="matching-threshold-bar">
                    <span class="matching-form-label">${_t('matching.threshold_label')}:</span>
                    <input type="range" min="0" max="100" value="${Math.round(threshold*100)}"
                           id="threshold-slider" step="5" style="width:120px"
                           oninput="Matching.updateThreshold(this.value)">
                    <span id="threshold-val" style="font-size:14px;font-weight:700;color:var(--abcona-blue)">
                        ${threshold.toFixed(2)}
                    </span>
                    <span id="threshold-count" style="font-size:10px;color:#888">
                        ${d.above_threshold} ${_t('matching.above_threshold_full')}
                    </span>
                    <span style="font-size:10px;color:#94a3b8" title="Alle Treffer ≥ Schwellwert (kein festes Top-N)">
                        ${totalHits} Treffer
                    </span>
                    <label style="font-size:11px;color:#555;display:inline-flex;align-items:center;gap:4px;margin-left:8px">
                        ${_esc(_kiT('source_filter_label', 'Quelle'))}:
                        <select id="shortlist-source-filter"
                                onchange="Matching.filterShortlistSource(this.value)"
                                style="font-size:11px;padding:2px 6px;border:1px solid #cbd5e1;border-radius:4px;background:#fff">
                            <option value="all">${_esc(_kiT('source_all', 'Alle'))} (${totalHits})</option>
                            <option value="db">DB (${dropCounts.db})</option>
                            <option value="es">ES (${dropCounts.es})</option>
                            <option value="gulp">Gulp (${dropCounts.gulp})</option>
                            <option value="flm">FLM (${dropCounts.flm})</option>
                        </select>
                    </label>
                    <button type="button" class="matching-btn-sm"
                            title="${_escAttr(_kiT('rematch_title', 'Shortlist löschen und Matching neu starten'))}"
                            onclick="Matching.rematch('${projectId}')">
                        <i class="bi bi-arrow-repeat"></i> ${_esc(_kiT('btn_rematch', 'Erneut matchen'))}
                    </button>
                    <button class="matching-btn-primary" style="margin-left:auto"
                            onclick="Matching.sendAllAboveThreshold()">
                        ${_t('matching.btn_send_all_count')} (${d.above_threshold}) ↗
                    </button>
                </div>`;

                const extSt = d.external_stats || {};
                const boN = d.backoffice_count || boList.length || 0;
                if (d.project_status === 'matching' && !(srcCounts.gulp || srcCounts.flm || boN)) {
                    html += `<div style="font-size:11px;color:#b45309;margin:6px 0 10px;padding:6px 8px;background:#fffbeb;border-radius:4px">
                        Matching läuft noch (Gulp/FLM kann 30–90 s dauern) — Shortlist aktualisiert sich automatisch.
                    </div>`;
                } else if (boN || extSt.gulp_raw || extSt.flm_raw) {
                    html += `<div style="font-size:10px;color:#64748b;margin:4px 0 8px">
                        Extern: gulp=${extSt.gulp_raw || 0} flm=${extSt.flm_raw || 0}
                        · known=${(extSt.gulp_known || 0) + (extSt.flm_known || 0)}
                        · backoffice=${boN}
                        <span style="color:#9a3412"> — Dropdown Gulp/FLM filtert auch Backoffice</span>
                    </div>`;
                }

                if (d.count === 0 && boN === 0) {
                    html += `<div style="padding:30px;text-align:center;color:#888">
                        ${_t('matching.no_results')}<br>
                        <button class="matching-btn-primary" style="margin-top:10px"
                                onclick="Matching.runMatching('${projectId}')">
                            <i class="bi bi-cpu"></i> ${_t('matching.btn_match')}
                        </button>
                    </div>`;
                } else {
                    html += '<div id="shortlist-results">';
                    for (const r of (d.results || [])) {
                        const scoreClass = r.overall_score >= 0.7 ? 'score-hi' :
                                           r.overall_score >= 0.5 ? 'score-mid' : 'score-lo';
                        const opacity = r.above_threshold ? '1' : '0.4';
                        const src = (r.match_source || 'db').toLowerCase();
                        const srcList = (Array.isArray(r.match_sources) && r.match_sources.length)
                            ? r.match_sources.map(s => String(s || '').toLowerCase())
                            : [src];
                        const srcAttr = srcList.filter(Boolean).join(',');
                        const linkSt = r.crm_link_status || '';
                        const pct = (r.overall_score * 100);
                        const pctLabel = (Math.abs(pct - Math.round(pct)) < 0.05)
                            ? pct.toFixed(0)
                            : pct.toFixed(1);
                        const strHint = (r.strength != null && r.strength > 0)
                            ? `<div style="font-size:9px;color:#94a3b8">str ${(Number(r.strength)*100).toFixed(0)}%</div>`
                            : '';
                        const badges = srcList.map(s => _srcBadge(s, linkSt)).join('');
                        const isExtSrc = srcList.includes('gulp') || srcList.includes('flm');
                        const hasDbEs = srcList.includes('db') || srcList.includes('es');
                        const profilUrl = String(r.profil_url || '').trim();
                        const schwerpunkt = String(r.schwerpunkt || '').trim();
                        const subLine = [
                            schwerpunkt,
                            r.location ? String(r.location) : '',
                        ].filter(Boolean).join(' · ');
                        // Gulp/FLM ohne DB/ES → HTML-Profil (kein generiertes CV)
                        const docBtn = (isExtSrc && profilUrl && !hasDbEs)
                            ? `<a href="${_escAttr(profilUrl)}" target="_blank" rel="noopener"
                                  class="matching-btn-sm" title="Externes HTML-Profil">HTML</a>`
                            : (r.cv_editor_url
                                ? `<a href="${_escAttr(r.cv_editor_url)}" target="_blank"
                                      class="matching-btn-sm">CV</a>`
                                : (profilUrl
                                    ? `<a href="${_escAttr(profilUrl)}" target="_blank" rel="noopener"
                                          class="matching-btn-sm" title="Externes HTML-Profil">HTML</a>`
                                    : ''));
                        html += `
                        <div class="matching-card matching-hit" style="display:flex;align-items:center;gap:8px;opacity:${opacity}"
                             data-score="${r.overall_score}" data-id="${r.id}" data-source="${_escAttr(src)}"
                             data-sources="${_escAttr(srcAttr)}" data-kind="shortlist"
                             data-rank="${r.rank || ''}" data-strength="${r.strength || 0}">
                            <div class="matching-score-box ${scoreClass}">
                                ${pctLabel}%${strHint}
                            </div>
                            <div style="flex:1">
                                <div style="font-weight:700;font-size:12px">${r.name}${badges}</div>
                                <div style="font-size:10px;color:#888">
                                    ${_esc(subLine || '—')}
                                </div>
                                ${r.match_reason ? `<div style="font-size:10px;color:#666;font-style:italic;margin-top:2px">"${r.match_reason}"</div>` : ''}
                                <div class="matching-score-bar">
                                    <div class="matching-score-fill" style="width:${r.overall_score*100}%"></div>
                                </div>
                            </div>
                            <div style="display:flex;gap:4px">
                                <button class="matching-btn-sm matching-btn-call"
                                        onclick="Matching.call('${r.id}')">
                                    <i class="bi bi-telephone"></i> ${_t('matching.btn_call')}
                                </button>
                                <button class="matching-btn-sm matching-btn-mail"
                                        onclick="Matching.sendEmail('${r.id}')">
                                    <i class="bi bi-envelope"></i> ${_t('matching.btn_email')}
                                </button>
                                ${docBtn}
                            </div>
                        </div>`;
                        if (r.above_threshold) {
                            const next = d.results[d.results.indexOf(r) + 1];
                            if (next && !next.above_threshold) {
                                html += `<div class="matching-threshold-sep">── ${_t('matching.sep_threshold')} ${threshold.toFixed(2)} ──</div>`;
                            }
                        }
                    }
                    html += '</div>';
                }

                // Backoffice: Gulp/FLM — im Quellen-Dropdown mitgezählt + filterbar
                if (boList.length) {
                    html += `
                    <div id="shortlist-backoffice-wrap" style="margin-top:18px;padding-top:12px;border-top:1px dashed #cbd5e1">
                      <div id="shortlist-backoffice-title" style="font-size:12px;font-weight:700;color:#9a3412;margin-bottom:8px">
                        Backoffice — <span id="shortlist-backoffice-count">${boList.length}</span> Treffer ohne Kontakt / nicht im Bestand
                        <span style="font-weight:500;color:#888;font-size:10px">
                          (kein Auto-CV-Update; manuell nachziehen)
                        </span>
                      </div>
                      <div id="shortlist-backoffice">`;
                    for (const b of boList.slice(0, 200)) {
                        const eh = b.external_hit || {};
                        const src = (b.match_source || '').toLowerCase();
                        const url = eh.profil_url || '';
                        const nm = _esc(b.display_name || eh.name || '—');
                        const sp = String(b.schwerpunkt || eh.title || eh.headline || '').trim();
                        const ov = (b.external_overlap_skills || []).join(', ');
                        const contactBits = [
                            b.email ? _esc(b.email) : '',
                            b.phone ? _esc(b.phone) : '',
                        ].filter(Boolean).join(' · ');
                        const reasonLabel = ({
                            known_crm: 'CRM bekannt (ohne CV)',
                            no_consultant: 'CRM ohne Consultant',
                            no_contact: 'bekannt ohne Kontakt',
                            unknown: 'nicht im Bestand',
                        })[b.reason] || _esc(b.reason || '');
                        const subBo = [
                            sp,
                            reasonLabel,
                            ov,
                            eh.ort ? String(eh.ort) : '',
                        ].filter(Boolean).join(' · ');
                        html += `
                        <div class="matching-card matching-hit" data-kind="backoffice"
                             data-source="${_escAttr(src)}" data-sources="${_escAttr(src)}"
                             data-score="${b.external_overlap || 0}"
                             style="display:flex;align-items:center;gap:8px;opacity:.85;background:#fffbeb">
                          <div style="min-width:52px;text-align:center;font-size:11px;font-weight:700;color:#9a3412">
                            ${b.external_overlap != null ? (b.external_overlap + '∩') : '—'}
                          </div>
                          <div style="flex:1">
                            <div style="font-weight:700;font-size:12px">${nm}${_srcBadge(src)}</div>
                            <div style="font-size:10px;color:#888">${_esc(subBo || '—')}</div>
                            ${contactBits ? `<div style="font-size:10px;color:#166534">${contactBits}</div>` : ''}
                          </div>
                          ${url ? `<a href="${_escAttr(url)}" target="_blank" rel="noopener" class="matching-btn-sm" title="Externes HTML-Profil">HTML</a>` : ''}
                        </div>`;
                    }
                    html += '</div></div>';
                }

                content.innerHTML = html;
                content.dataset.loaded = '1';
                content.dataset.projectId = projectId;
                window._matchingShortlistCache = {
                    projectId: projectId,
                    threshold: threshold,
                    results: d.results || [],
                    backoffice: boList,
                    source_counts: srcCounts,
                    drop_counts: dropCounts,
                    project_number: d.project_number || '',
                    project_title: d.project_title || d.title || '',
                };
                Matching.filterShortlistSource('all');
            })
            .catch(e => {
                if (loading) loading.style.display = 'none';
                content.innerHTML = '<p style="color:#ef4444;padding:20px">' + _t('matching.err_connection') + ': ' + e.message + '</p>';
            });
    }

    // ──────────────────────────────────────────────────
    // TAB: REPORTING
    // ──────────────────────────────────────────────────

    function _loadReporting(content, loading) {
        fetch(API + 'reporting/', { credentials: 'same-origin' })
            .then(r => r.json())
            .then(d => {
                if (loading) loading.style.display = 'none';
                if (!d.success) { content.innerHTML = '<p>' + _t('matching.err_load') + '</p>'; return; }
                content.innerHTML = `
                <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-bottom:14px">
                    <div class="matching-card" style="text-align:center">
                        <div style="font-size:28px;font-weight:700;color:var(--abcona-blue)">${d.placement_rate}%</div>
                        <div style="font-size:11px;color:#888">${_t('matching.rep_quota')}</div>
                    </div>
                    <div class="matching-card" style="text-align:center">
                        <div style="font-size:28px;font-weight:700;color:#155724">${d.total_placed}</div>
                        <div style="font-size:11px;color:#888">${_t('matching.rep_total_placed')}</div>
                    </div>
                    <div class="matching-card" style="text-align:center">
                        <div style="font-size:28px;font-weight:700;color:#856404">${d.total_closed}</div>
                        <div style="font-size:11px;color:#888">${_t('matching.rep_total_closed')}</div>
                    </div>
                </div>`;
                content.dataset.loaded = '1';
            })
            .catch(e => {
                if (loading) loading.style.display = 'none';
                content.innerHTML = '<p style="color:#ef4444;padding:20px">' + _t('matching.err_connection') + ': ' + e.message + '</p>';
            });
    }

    // ──────────────────────────────────────────────────
    // KI-ANFRAGEN-WIZARD (abpe_ki_wiz / DeepSeek)
    // ──────────────────────────────────────────────────

    const KI_API = '/ki-wizard/api/';
    let _kiLastExtract = null;
    let _kiCrmPickList = [];
    let _kiCrmAccountPickList = [];

    function _skillHint() {
        const v = _t('matching.skill_hint');
        if (v && v !== 'matching.skill_hint' && !/ollama/i.test(v)) return v;
        return 'DeepSeek erkennt Skills automatisch';
    }

    function _kiT(key, fallback) {
        const v = _t('matching.' + key);
        if (v && v !== 'matching.' + key) return v;
        return fallback;
    }

    function _injectKiWizardButton() {
        if (document.getElementById('matching-ki-wizard-btn')) return;

        const byOnclick = Array.from(
            document.querySelectorAll('button[onclick], a[onclick], .matching-btn-primary')
        ).find(el => {
            const oc = el.getAttribute('onclick') || '';
            return /Matching\.newRequest/i.test(oc);
        });

        let anchor = byOnclick;
        if (!anchor) {
            anchor = Array.from(document.querySelectorAll('button, a.btn, .btn')).find(el => {
                const txt = (el.textContent || '').replace(/\s+/g, ' ').trim();
                return /\+?\s*Neue Anfrage/i.test(txt) || /New Request/i.test(txt);
            });
        }
        if (!anchor || !anchor.parentNode) {
            console.warn('Matching: + Neue Anfrage Button nicht gefunden — KI-Wizard-Button übersprungen');
            return;
        }

        const btn = document.createElement('button');
        btn.type = 'button';
        btn.id = 'matching-ki-wizard-btn';
        btn.className = anchor.className || 'matching-btn-primary';
        btn.style.marginRight = '8px';
        btn.innerHTML = '<i class="bi bi-magic"></i> ' + _kiT('ki_wizard_btn', 'KI-Anfragen-Wizard');
        btn.addEventListener('click', function(e) {
            e.preventDefault();
            openKiWizard();
        });
        anchor.parentNode.insertBefore(btn, anchor);
    }

    function _ensureKiModal() {
        let modal = document.getElementById('matching-ki-wizard-modal');
        if (modal) return modal;

        modal = document.createElement('div');
        modal.id = 'matching-ki-wizard-modal';
        modal.style.cssText = [
            'display:none', 'position:fixed', 'inset:0', 'z-index:10050',
            'background:rgba(15,23,42,0.45)', 'align-items:center', 'justify-content:center',
            'padding:16px',
        ].join(';');
        modal.innerHTML = `
            <div role="dialog" aria-modal="true" style="
                background:var(--bs-body-bg,#fff);color:var(--bs-body-color,#111);
                width:min(720px,100%);max-height:90vh;overflow:auto;
                border-radius:10px;box-shadow:0 12px 40px rgba(0,0,0,.25);padding:20px 22px;
            ">
                <div style="display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:12px">
                    <h3 style="margin:0;font-size:1.1rem">
                        <i class="bi bi-magic"></i> ${_kiT('ki_wizard_title', 'KI-Anfragen-Wizard')}
                    </h3>
                    <button type="button" class="matching-btn-sm" id="matching-ki-close"
                            aria-label="Schließen">&times;</button>
                </div>
                <p style="margin:0 0 12px;font-size:13px;opacity:.85">
                    ${_kiT('ki_wizard_help', 'E-Mail einfügen — DeepSeek füllt Kundendaten und Anfrage-Details (Prompt aus abpe_ki_wiz).')}
                </p>
                <div style="display:grid;gap:8px;grid-template-columns:1fr 1fr;margin-bottom:8px">
                    <div>
                        <label class="matching-form-label">${_kiT('ki_subject', 'Betreff (optional)')}</label>
                        <input class="matching-form-input" id="matching-ki-subject" style="width:100%">
                    </div>
                    <div>
                        <label class="matching-form-label">${_kiT('ki_from', 'Weiterleitung von (optional)')}</label>
                        <input class="matching-form-input" id="matching-ki-from" style="width:100%"
                               placeholder="Name &lt;mail@…&gt;">
                        <div style="font-size:11px;opacity:.7;margin-top:4px">
                            ${_kiT('ki_from_help', 'Nur der Weiterleitende (z.B. Karsten Bär) — nicht der Auftraggeber/Ansprechpartner.')}
                        </div>
                    </div>
                </div>
                <label class="matching-form-label">${_kiT('ki_email', 'E-Mail-Inhalt')}</label>
                <textarea id="matching-ki-email" class="matching-form-textarea"
                          style="width:100%;min-height:220px;margin-bottom:10px"
                          placeholder="${_kiT('ki_email_ph', 'E-Mail einfügen — Freitext oder Weiterleitung…')}"></textarea>
                <div id="matching-ki-error" style="display:none;color:#ef4444;font-size:13px;margin-bottom:8px"></div>
                <div id="matching-ki-preview" style="display:none;font-size:12px;background:rgba(37,99,235,.06);
                     border:1px solid rgba(37,99,235,.2);border-radius:8px;padding:10px;margin-bottom:10px;
                     white-space:pre-wrap;max-height:160px;overflow:auto"></div>
                <div style="display:flex;gap:8px;justify-content:flex-end;flex-wrap:wrap">
                    <button type="button" class="matching-btn-sm" id="matching-ki-cancel">
                        ${_t('matching.btn_cancel') !== 'matching.btn_cancel' ? _t('matching.btn_cancel') : 'Abbrechen'}
                    </button>
                    <button type="button" class="matching-btn-primary" id="matching-ki-extract">
                        <i class="bi bi-cpu"></i> ${_kiT('ki_extract', 'Extrahieren')}
                    </button>
                    <button type="button" class="matching-btn-primary" id="matching-ki-apply" style="display:none">
                        <i class="bi bi-check2"></i> ${_kiT('ki_apply', 'In Formular übernehmen')}
                    </button>
                </div>
            </div>`;
        document.body.appendChild(modal);

        modal.addEventListener('click', function(e) {
            if (e.target === modal) closeKiWizard();
        });
        modal.querySelector('#matching-ki-close').addEventListener('click', closeKiWizard);
        modal.querySelector('#matching-ki-cancel').addEventListener('click', closeKiWizard);
        modal.querySelector('#matching-ki-extract').addEventListener('click', runKiExtract);
        modal.querySelector('#matching-ki-apply').addEventListener('click', applyKiExtract);
        return modal;
    }

    function openKiWizard(opts) {
        opts = opts || {};
        _activateTab('neu');
        history.pushState({}, '', '/matching/?tab=neu');
        const modal = _ensureKiModal();
        const err = document.getElementById('matching-ki-error');
        const prev = document.getElementById('matching-ki-preview');
        const applyBtn = document.getElementById('matching-ki-apply');
        if (err) { err.style.display = 'none'; err.textContent = ''; }
        if (prev) { prev.style.display = 'none'; prev.textContent = ''; }
        if (applyBtn) applyBtn.style.display = 'none';
        _kiLastExtract = null;

        const emailEl = document.getElementById('matching-ki-email');
        const subEl = document.getElementById('matching-ki-subject');
        const fromEl = document.getElementById('matching-ki-from');
        if (emailEl) emailEl.value = opts.email_text || '';
        if (subEl) subEl.value = opts.subject || '';
        if (fromEl) fromEl.value = opts.outer_from || '';

        modal.style.display = 'flex';
        if (emailEl) emailEl.focus();
    }

    function closeKiWizard() {
        const modal = document.getElementById('matching-ki-wizard-modal');
        if (modal) modal.style.display = 'none';
    }

    function runKiExtract() {
        const email = (document.getElementById('matching-ki-email') || {}).value || '';
        const subject = (document.getElementById('matching-ki-subject') || {}).value || '';
        const outerFrom = (document.getElementById('matching-ki-from') || {}).value || '';
        const err = document.getElementById('matching-ki-error');
        const prev = document.getElementById('matching-ki-preview');
        const applyBtn = document.getElementById('matching-ki-apply');
        const extractBtn = document.getElementById('matching-ki-extract');

        if (email.trim().length < 20) {
            if (err) {
                err.textContent = _kiT('ki_err_short', 'Bitte mehr E-Mail-Text einfügen (min. 20 Zeichen).');
                err.style.display = 'block';
            }
            return;
        }
        if (err) err.style.display = 'none';
        if (extractBtn) {
            extractBtn.disabled = true;
            extractBtn.innerHTML = '<i class="bi bi-hourglass-split"></i> …';
        }

        fetch(KI_API + 'matching-anfrage/extract/', {
            method: 'POST',
            credentials: 'same-origin',
            headers: { 'X-CSRFToken': csrf(), 'Content-Type': 'application/json' },
            body: JSON.stringify({
                email_text: email,
                subject: subject,
                outer_from: outerFrom,
            }),
        })
        .then(async r => {
            const d = await r.json().catch(() => ({}));
            if (!r.ok && !d.fields && !d.extract) {
                throw new Error(d.error || ('HTTP ' + r.status));
            }
            return d;
        })
        .then(d => {
            _kiLastExtract = d;
            const fields = d.fields || {};
            const crm = d.crm || {};
            const lines = [
                (d.success ? '✓' : '⚠') + ' ' + (d.source || '') + (d.prompt_key ? ' · ' + d.prompt_key : ''),
                fields.customer_name ? 'Kunde: ' + fields.customer_name : '',
                fields.contact_name ? 'Ansprechpartner: ' + fields.contact_name : '',
                fields.contact_email ? 'E-Mail: ' + fields.contact_email : '',
                fields.contact_phone ? 'Telefon: ' + fields.contact_phone : '',
                fields.title ? 'Titel: ' + fields.title : '',
                fields.duration_months != null ? 'Dauer: ' + fields.duration_months + ' Mon.' : '',
                fields.location ? 'Standort: ' + fields.location : '',
                fields.start_date
                    ? ('Start: ' + fields.start_date + (fields.start_asap ? ' (asap→sofort)' : ''))
                    : (fields.start_asap ? 'Start: asap' : ''),
            ].filter(Boolean);
            const skReq = Array.isArray(fields.skills_required) ? fields.skills_required : [];
            const skNice = Array.isArray(fields.skills_nice) ? fields.skills_nice : [];
            const skAll = Array.isArray(fields.skills) ? fields.skills : [];
            if (skReq.length || skNice.length || skAll.length) {
                if (skReq.length) {
                    lines.push('Skills (Muss): ' + skReq.map(s => (typeof s === 'string' ? s : (s && s.name) || '')).filter(Boolean).join(', '));
                }
                if (skNice.length) {
                    lines.push('Skills (Nice): ' + skNice.map(s => (typeof s === 'string' ? s : (s && s.name) || '')).filter(Boolean).join(', '));
                }
                if (!skReq.length && !skNice.length && skAll.length) {
                    lines.push('Skills: ' + skAll.map(s => (typeof s === 'string' ? s : (s && s.name) || '')).filter(Boolean).join(', '));
                }
            } else {
                lines.push('⚠ Keine Skills erkannt — bitte manuell oder „aus Text“');
            }
            if (crm.contact_missing) {
                lines.push(crm.suggest_create_contact
                    ? '⚠ Ansprechpartner nicht in CRM — Anlegen vorschlagen'
                    : '⚠ Ansprechpartner nicht in CRM (E-Mail/Telefon ergänzen)');
            } else if ((crm.contact_matches || []).length) {
                lines.push('✓ Ansprechpartner in CRM gefunden');
            }
            if (prev) {
                prev.textContent = lines.join('\n');
                prev.style.display = 'block';
            }
            if (applyBtn) applyBtn.style.display = '';
            if (!d.success && err) {
                err.textContent = d.error || _kiT('ki_err', 'Extraktion mit Einschränkungen');
                err.style.display = 'block';
            }
        })
        .catch(e => {
            if (err) {
                err.textContent = e.message || String(e);
                err.style.display = 'block';
            }
        })
        .finally(() => {
            if (extractBtn) {
                extractBtn.disabled = false;
                extractBtn.innerHTML = '<i class="bi bi-cpu"></i> ' + _kiT('ki_extract', 'Extrahieren');
            }
        });
    }

    function applyKiExtract() {
        const d = _kiLastExtract || {};
        const fields = d.fields || {};
        const crm = d.crm || {};
        _activateTab('neu');
        const fill = () => {
            // Textfelder = KI-Extrakt aus Anfrage-Text (nicht aus CRM-DB).
            // CRM-IDs erst nach Match setzen — gelöschte Firmen bleiben weg.
            // Session-Cache leeren: sonst würden gelöschte IDs aus dem vorherigen
            // Anlegen wiederverwendet, obwohl die Firma in der DB weg ist.
            Object.keys(_accountIdByNorm).forEach(function (k) {
                delete _accountIdByNorm[k];
            });
            _setVal('new-crm-account-id', '');
            _setVal('new-crm-contact-id', '');
            clearCustomerLink();
            _setVal('new-customer', fields.customer_name || '');
            _setVal('new-contact', fields.contact_name || '');
            _setVal('new-contact-email', fields.contact_email || '');
            _setVal('new-contact-phone', fields.contact_phone || '');
            _setVal('new-title', fields.title || '');
            _setVal('new-description', fields.description || '');
            if (fields.start_date) _setVal('new-start', fields.start_date);
            else if (fields.start_asap) _setVal('new-start', _todayISO());
            if (fields.duration_months != null) _setVal('new-duration', String(fields.duration_months));
            _setVal('new-location', fields.location || '');
            if (fields.rate_max != null) _setVal('new-rate-max', String(fields.rate_max));
            else _setVal('new-rate-max', '');

            // Skills aus KI — ohne die matcht die Engine Blindlinge (~70% überall)
            // Reihenfolge: Muss zuerst, Nice-to-have danach; Gewichte in JSON
            const skillsArr = Array.isArray(fields.skills)
                ? fields.skills.map(s => (typeof s === 'string' ? s : (s && s.name) || '')).filter(Boolean)
                : [];
            const weighted = Array.isArray(fields.required_skills) && fields.required_skills.length
                ? fields.required_skills
                : [
                    ...(Array.isArray(fields.skills_required) ? fields.skills_required : []).map(s => ({
                        name: typeof s === 'string' ? s : (s && s.name) || '', weight: 1.0,
                    })),
                    ...(Array.isArray(fields.skills_nice) ? fields.skills_nice : []).map(s => ({
                        name: typeof s === 'string' ? s : (s && s.name) || '', weight: 0.55,
                    })),
                ].filter(x => x.name);
            const names = weighted.length
                ? weighted.map(x => x.name).filter(Boolean)
                : skillsArr;
            _setVal('new-skills', names.join(', '));
            const sj = document.getElementById('new-skills-json');
            if (sj) {
                sj.value = JSON.stringify(
                    weighted.length
                        ? weighted
                        : names.map(name => ({ name: name, weight: 1.0 }))
                );
            }

            // Firma: aus KI, sonst aus Titel; bei mehreren Hays AG → Auswahl
            let customerName = (fields.customer_name || '').trim();
            if (!customerName) {
                customerName = _deriveCustomerFromTitle(fields.title || _val('new-title') || '');
                if (customerName) fields.customer_name = customerName;
            }
            if (customerName) {
                _setVal('new-customer', customerName);
            }
            const accounts = crm.account_matches || [];
            const prefId = crm.preferred_account_crm_id || '';
            if (accounts.length === 1) {
                _pickCrmAccount(accounts[0]);
            } else if (accounts.length > 1) {
                // Kontakt schon an eine Firma gehängt? → vorwählen, trotzdem Liste zeigen
                const pref = prefId
                    ? accounts.find(a => (a.crm_id || a.id) === prefId)
                    : null;
                if (pref) _pickCrmAccount(pref);
                _showCrmAccountPick(accounts, {
                    preferredId: prefId,
                    note: pref
                        ? 'Mehrere „' + customerName + '“ in ABpE CRM — aktuell verknüpft mit Kontakt vorgeschlagen:'
                        : 'Mehrere „' + customerName + '“ in ABpE CRM — bitte Standort wählen:',
                });
            } else if (customerName) {
                _linkCustomerOnApply(customerName);
            } else {
                clearCustomerLink();
            }

            // Kontakt: KI-Werte sind maßgeblich.
            // CRM nur übernehmen bei sicherem Treffer (Backend filtert Fuzzy raus).
            const contacts = crm.contact_matches || [];
            const conf = crm.contact_match_confidence || 'none';
            if (contacts.length === 1 && (conf === 'email' || conf === 'name')) {
                _setVal('new-crm-contact-id', contacts[0].crm_id || '');
                // Name/E-Mail/Tel nur ergänzen wenn KI leer — nie KI mit anderem Kontakt überschreiben
                if (!_val('new-contact') && contacts[0].full_name) {
                    _setVal('new-contact', contacts[0].full_name);
                }
                if (!_val('new-contact-email') && contacts[0].email) {
                    _setVal('new-contact-email', contacts[0].email);
                }
                if (!_val('new-contact-phone') && contacts[0].phone) {
                    _setVal('new-contact-phone', contacts[0].phone);
                }
                _hideCrmSuggest();
            } else if (contacts.length > 1) {
                _showCrmContactPick(contacts);
            } else if (fields.contact_name && (crm.contact_missing || crm.suggest_create_contact || !contacts.length)) {
                _hideCrmSuggest();
                openNewContactPopup(fields, crm);
            } else {
                _hideCrmSuggest();
            }
            closeKiWizard();
        };
        const content = document.getElementById('content-neu');
        if (content && content.dataset.loaded !== '1') {
            setTimeout(fill, 80);
        } else {
            fill();
        }
    }

    function _todayISO() {
        const d = new Date();
        const m = String(d.getMonth() + 1).padStart(2, '0');
        const day = String(d.getDate()).padStart(2, '0');
        return d.getFullYear() + '-' + m + '-' + day;
    }

    function _deriveCustomerFromTitle(title) {
        const t = String(title || '').trim();
        if (!t) return '';
        const seps = [' - ', ' – ', ' — ', ' | ', ': '];
        for (let i = 0; i < seps.length; i++) {
            const sep = seps[i];
            if (t.indexOf(sep) >= 0) {
                const left = t.split(sep)[0].trim();
                if (_looksLikeCompany(left)) return left;
            }
        }
        const m = t.match(/\b([A-ZÄÖÜ][\wÄÖÜäöüß.& -]{1,50}?\b(?:AG|GmbH|SE|KG))\b/);
        return m ? m[1].trim() : '';
    }

    function _looksLikeCompany(name) {
        const s = String(name || '').trim();
        if (s.length < 2 || s.length > 90) return false;
        if (/\b(engineer|berater|consultant|developer|manager|specialist)\b/i.test(s)) return false;
        if (/\b(AG|GmbH|SE|KG|Ltd|Inc|UG)\b/i.test(s)) return true;
        return /^[A-ZÄÖÜ0-9][\wÄÖÜäöüß.&' -]{1,70}$/.test(s);
    }

    function _linkCustomerOnApply(name) {
        const n = String(name || '').trim();
        if (!n) return;
        _setVal('new-customer', n);
        searchAccounts(n);
        if (typeof _searchAccountsAny === 'function') {
            _searchAccountsAny(n).then(hits => {
                const exact = _findExactFirm(hits, n);
                if (exact) {
                    // Bereits vorhandene Duplikate (gleicher Norm-Name) → ersten nehmen, nicht neu
                    _pickCrmAccount(exact);
                    return;
                }
                const pool = hits || [];
                if (pool.length === 1) {
                    _pickCrmAccount(pool[0]);
                    return;
                }
                if (pool.length > 1) {
                    _showCrmAccountPick(pool, {
                        note: 'Mehrere Treffer für „' + n + '“ in ABpE CRM — bitte wählen:',
                    });
                    return;
                }
                // Kein CRM-Treffer (gelöscht / neu) — Text bleibt, Hinweis anzeigen
                _setCustomerExtractHint(n);
            }).catch(() => {
                _setCustomerExtractHint(n);
            });
        } else {
            _setCustomerExtractHint(n);
        }
    }

    function _pickCrmAccount(a) {
        if (!a) return;
        const id = a.crm_id || a.id || '';
        const name = a.name || _val('new-customer') || '';
        const city = a.city || a.billing_address_city || '';
        _setVal('new-customer', name);
        _setVal('new-crm-account-id', id);
        _rememberAccountId(name, id);
        const res = document.getElementById('new-customer-results');
        if (res) res.style.display = 'none';
        _setCustomerLinkedHint(name, city, id);
    }

    function _setCustomerLinkedHint(name, city, id) {
        const el = document.getElementById('new-customer-linked');
        if (!el) return;
        if (!id) {
            el.style.display = 'none';
            el.textContent = '';
            return;
        }
        el.style.display = '';
        el.style.color = '#059669';
        el.innerHTML = '✓ CRM verknüpft: <strong>' + _esc(name || '') + '</strong>'
            + (city ? ' · ' + _esc(city) : '')
            + ' <span style="opacity:.6">(' + _esc(String(id).slice(0, 8)) + '…)</span>';
    }

    function _setCustomerExtractHint(name) {
        const el = document.getElementById('new-customer-linked');
        if (!el) return;
        el.style.display = '';
        el.style.color = '#b45309';
        el.innerHTML = 'ℹ aus Anfrage-Text: <strong>' + _esc(name || '') + '</strong>'
            + ' — noch nicht in CRM (gelöscht oder neu)';
    }

    function clearCustomerLink() {
        _setVal('new-crm-account-id', '');
        _setCustomerLinkedHint('', '', '');
    }

    function _showCrmAccountPick(accounts, opts) {
        opts = opts || {};
        const box = document.getElementById('matching-crm-suggest');
        if (!box) return;
        _kiCrmAccountPickList = accounts || [];
        const pref = opts.preferredId || '';
        box.style.display = 'block';
        box.style.borderColor = '#2563eb';
        box.style.background = 'rgba(37,99,235,.06)';
        box.innerHTML = '<strong><i class="bi bi-building"></i> '
            + _esc(opts.note || 'Firma in ABpE CRM wählen:')
            + '</strong>'
            + '<div style="margin-top:8px;display:grid;gap:4px">'
            + _kiCrmAccountPickList.map((a, i) => {
                const id = a.crm_id || a.id || '';
                const city = a.city || a.billing_address_city || '';
                const isPref = pref && id === pref;
                return `<button type="button" class="matching-btn-sm" style="text-align:left;${isPref ? 'border-color:#2563eb;font-weight:600' : ''}"
                    onclick="Matching.pickCrmAccountIndex(${i})">
                    <strong>${_esc(a.name || '')}</strong>
                    ${city ? ' · ' + _esc(city) : ''}
                    ${isPref ? ' · <span style="color:#2563eb">vom Kontakt</span>' : ''}
                 </button>`;
            }).join('')
            + '</div>'
            + '<div style="margin-top:8px">'
            + '<button type="button" class="matching-btn-sm" onclick="Matching.hideCrmSuggest()">'
            + 'Später wählen</button></div>';
    }

    function pickCrmAccountIndex(i) {
        _pickCrmAccount(_kiCrmAccountPickList[i]);
        _hideCrmSuggest();
    }

    function _hideCrmSuggest() {
        const box = document.getElementById('matching-crm-suggest');
        if (box) {
            box.style.display = 'none';
            box.innerHTML = '';
            box.style.borderColor = '#f59e0b';
            box.style.background = 'rgba(245,158,11,.08)';
        }
    }

    function _showCrmContactPick(contacts) {
        const box = document.getElementById('matching-crm-suggest');
        if (!box) return;
        _kiCrmPickList = contacts || [];
        box.style.display = 'block';
        box.innerHTML = '<strong>' + _kiT('crm_pick', 'Ansprechpartner in CRM — bitte wählen:') + '</strong>'
            + '<div style="margin-top:8px;display:grid;gap:4px">'
            + _kiCrmPickList.map((c, i) =>
                `<button type="button" class="matching-btn-sm" style="text-align:left"
                    onclick="Matching.pickCrmContactIndex(${i})">
                    <strong>${_esc(c.full_name || '')}</strong>
                    · ${_esc(c.email || '—')} · ${_esc(c.phone || '')}
                 </button>`
            ).join('')
            + '</div>';
    }

    function _showCrmContactCreateSuggest(fields, crm) {
        openNewContactPopup(fields, crm);
    }

    function openNewContactPopup(fields, crm) {
        fields = fields || {};
        crm = crm || {};
        closeNewContactPopup();

        const emailPrefill = fields.contact_email || _val('new-contact-email') || '';
        const phonePrefill = fields.contact_phone || _val('new-contact-phone') || '';
        const firmPrefill = fields.customer_name || _val('new-customer') || '';
        const firmIdPrefill = _val('new-crm-account-id') || '';
        const accounts = crm.account_matches || [];
        let firmName = firmPrefill;
        let firmId = firmIdPrefill;
        if (!firmId && accounts.length === 1) {
            firmName = accounts[0].name || firmName;
            firmId = accounts[0].crm_id || '';
        }

        // Person ≠ Firma: wenn Name wie Firma aussieht, aus E-Mail ableiten (bob@bobmichaels.ai)
        let contactRaw = fields.contact_name || _val('new-contact') || '';
        let split = _splitName(contactRaw);
        const fromMail = _nameFromEmail(emailPrefill);
        if (_personNameLooksLikeCompany(contactRaw, firmName) && fromMail.full) {
            split = { first: fromMail.first, last: fromMail.last };
            contactRaw = fromMail.full;
        } else if ((!split.last || _personNameLooksLikeCompany(split.last, firmName)) && fromMail.last) {
            split = { first: fromMail.first || split.first, last: fromMail.last };
        }
        const salutationGuess = _guessSalutation(split.first, fields.contact_salutation || '');

        const modal = document.createElement('div');
        modal.id = 'matching-new-contact-modal';
        modal.style.cssText = [
            'position:fixed', 'inset:0', 'z-index:10060',
            'background:rgba(15,23,42,0.5)', 'display:flex',
            'align-items:flex-start', 'justify-content:center', 'padding:48px 16px 16px',
        ].join(';');

        modal.innerHTML = `
          <div role="dialog" aria-modal="true" style="
              background:var(--bs-body-bg,#fff);color:var(--bs-body-color,#111);
              width:min(480px,100%);border-radius:12px;overflow:hidden;
              box-shadow:0 20px 60px rgba(0,0,0,.28)">
            <div style="background:#163258;padding:14px 18px;display:flex;align-items:center;justify-content:space-between">
              <div style="display:flex;align-items:center;gap:10px;color:#fff;font-weight:600;font-size:14px">
                <i class="bi bi-person-plus"></i> ${_kiT('new_contact_title', 'Neuer Kontakt')}
              </div>
              <button type="button" id="mnc-close" style="background:rgba(255,255,255,.15);border:none;color:#fff;
                width:28px;height:28px;border-radius:50%;cursor:pointer;font-size:16px;line-height:1">&times;</button>
            </div>
            <div style="padding:16px 18px;display:flex;flex-direction:column;gap:10px">
              <p style="margin:0;font-size:12px;opacity:.8">
                ${_kiT('new_contact_help', 'Ansprechpartner nicht in CRM — bitte anlegen (Nachname + E-Mail Pflicht).')}
              </p>
              <div style="display:grid;grid-template-columns:110px 1fr;gap:8px;align-items:center">
                <label style="font-size:12px;opacity:.75">Anrede</label>
                <select id="mnc-salutation" class="matching-form-input" style="width:100%">
                  <option value="Hr."${salutationGuess === 'Hr.' ? ' selected' : ''}>Hr.</option>
                  <option value="Fr."${salutationGuess === 'Fr.' ? ' selected' : ''}>Fr.</option>
                  <option value=""${!salutationGuess ? ' selected' : ''}>—</option>
                </select>
              </div>
              <div style="display:grid;grid-template-columns:110px 1fr;gap:8px;align-items:center">
                <label style="font-size:12px;opacity:.75">Vorname</label>
                <input id="mnc-firstname" class="matching-form-input" style="width:100%"
                       placeholder="optional" value="${_escAttr(split.first)}">
              </div>
              <div style="display:grid;grid-template-columns:110px 1fr;gap:8px;align-items:center">
                <label style="font-size:12px;opacity:.75">Nachname <span style="color:#dc3545">*</span></label>
                <input id="mnc-lastname" class="matching-form-input" style="width:100%;border-color:#163258"
                       placeholder="Pflicht" value="${_escAttr(split.last)}">
              </div>
              <div style="display:grid;grid-template-columns:110px 1fr;gap:8px;align-items:start">
                <label style="font-size:12px;opacity:.75;padding-top:8px">Firma</label>
                <div style="position:relative">
                  <input id="mnc-firma" class="matching-form-input" style="width:100%"
                         placeholder="suchen oder neue Firma…"
                         value="${_escAttr(firmName)}" autocomplete="off">
                  <input type="hidden" id="mnc-firma-id" value="${_escAttr(firmId)}">
                  <div id="mnc-firma-results" style="display:none;position:absolute;left:0;right:0;top:100%;z-index:2;
                       background:#fff;border:1px solid #dde3ec;border-radius:6px;max-height:160px;overflow:auto;
                       box-shadow:0 8px 20px rgba(0,0,0,.12)"></div>
                  <div style="font-size:11px;opacity:.7;margin-top:4px">
                    ${_kiT('firma_help', 'Suche (CRM/Elastic) — Treffer wählen oder „Neue Firma“.')}
                  </div>
                  <div id="mnc-firma-linked" style="display:none;font-size:11px;margin-top:4px;font-weight:500"></div>
                  <button type="button" class="matching-btn-sm" id="mnc-firma-web"
                          style="margin-top:6px;font-size:11px;padding:3px 8px"
                          title="${_escAttr(_kiT('firma_web_title', 'Homepage/Impressum öffentlich auslesen'))}">
                    <i class="bi bi-globe2"></i> ${_kiT('firma_web_btn', 'Aus Web anreichern')}
                  </button>
                  <div id="mnc-firma-web-panel" style="display:none;margin-top:8px;padding:10px;
                       border:1px solid #c7d2fe;border-radius:8px;background:#f8fafc;font-size:12px"></div>
                </div>
              </div>
              <div style="display:grid;grid-template-columns:110px 1fr;gap:8px;align-items:center">
                <label style="font-size:12px;opacity:.75">E-Mail <span style="color:#dc3545">*</span></label>
                <input id="mnc-email" type="email" class="matching-form-input" style="width:100%;border-color:#163258"
                       placeholder="name@firma.de" value="${_escAttr(emailPrefill)}">
              </div>
              <div style="display:grid;grid-template-columns:110px 1fr;gap:8px;align-items:center">
                <label style="font-size:12px;opacity:.75">Telefon</label>
                <input id="mnc-phone" type="tel" class="matching-form-input" style="width:100%"
                       placeholder="optional" value="${_escAttr(phonePrefill)}">
              </div>
              <div id="mnc-msg" style="font-size:12px;min-height:18px;text-align:center"></div>
            </div>
            <div style="padding:12px 18px;border-top:1px solid rgba(0,0,0,.08);display:flex;justify-content:flex-end;gap:8px;flex-wrap:wrap">
              <button type="button" class="matching-btn-sm" id="mnc-cancel">Abbrechen</button>
              <button type="button" class="matching-btn-primary" id="mnc-save">
                <i class="bi bi-person-check"></i> Anlegen
              </button>
            </div>
          </div>`;

        document.body.appendChild(modal);
        modal.addEventListener('click', function(e) {
            if (e.target === modal) closeNewContactPopup();
        });
        modal.querySelector('#mnc-close').addEventListener('click', closeNewContactPopup);
        modal.querySelector('#mnc-cancel').addEventListener('click', closeNewContactPopup);
        modal.querySelector('#mnc-save').addEventListener('click', function() {
            createCrmContactFromSuggest();
        });
        modal.querySelector('#mnc-firma-web')?.addEventListener('click', function() {
            runFirmaWebEnrich();
        });

        const firmaInp = modal.querySelector('#mnc-firma');
        let firmTimer = null;
        if (firmId) _setFirmaLinkedHint(true);
        else if (firmName) _setFirmaLinkedHint(false);
        firmaInp.addEventListener('input', function() {
            clearTimeout(firmTimer);
            const q = firmaInp.value.trim();
            const prevId = (modal.querySelector('#mnc-firma-id').value || '').trim();
            // Verknüpfung nur lösen, wenn der Name sich wirklich ändert
            const stillSame = prevId && _normFirmName(q) === _normFirmName(
                (_val('new-customer') || firmName || q)
            );
            if (!stillSame) {
                modal.querySelector('#mnc-firma-id').value = '';
                _setFirmaLinkedHint(false);
            }
            firmTimer = setTimeout(function() {
                if (q.length < 2) return;
                // Exact/Einzeltreffer automatisch verknüpfen (Stadt nicht nötig)
                _resolveFirmaForPopup(q, { autoSelectExact: true, showList: true });
            }, 280);
        });
        firmaInp.addEventListener('focus', function() {
            const q = firmaInp.value.trim();
            const id = (modal.querySelector('#mnc-firma-id').value || '').trim();
            // Bereits verknüpft → Liste nicht aufdrängen
            if (id) return;
            if (q.length >= 2) _searchFirmaForPopup(q);
        });

        setTimeout(function() {
            (document.getElementById('mnc-lastname') || document.getElementById('mnc-email'))?.focus();
            // Firma automatisch auflösen (Treffer wählen / ID setzen)
            if (firmName && firmName.length >= 2) {
                _resolveFirmaForPopup(firmName, { autoSelectExact: true, showList: !firmId });
            }
        }, 80);
    }

    function closeNewContactPopup() {
        document.getElementById('matching-new-contact-modal')?.remove();
    }

    function _searchFirmaForPopup(q) {
        const box = document.getElementById('mnc-firma-results');
        if (!box) return;
        if (!q || q.length < 2) { box.style.display = 'none'; box.innerHTML = ''; return; }

        const urls = [
            API + 'crm/accounts/?q=' + encodeURIComponent(q),
            '/crm/api/kunden/?q=' + encodeURIComponent(q) + '&limit=10',
        ];

        const render = (hits) => {
            const rows = (hits || []).map(h => {
                const id = h.crm_id || h.id || '';
                const name = h.name || '';
                const city = h.city || h.billing_address_city || '';
                return `<div class="mnc-firm-hit" data-id="${_escAttr(id)}" data-name="${_escAttr(name)}"
                            style="padding:7px 10px;font-size:12px;cursor:pointer"
                            onmouseover="this.style.background='#f0f4fa'"
                            onmouseout="this.style.background=''">
                          <strong>${_esc(name)}</strong>${city ? ' · ' + _esc(city) : ''}
                        </div>`;
            }).join('');
            box.innerHTML = rows
                + `<div class="mnc-firm-new" style="padding:8px 10px;font-size:12px;cursor:pointer;
                      border-top:1px solid #eee;color:#163258;font-weight:500"
                      onmouseover="this.style.background='#f0f4fa'"
                      onmouseout="this.style.background=''">
                     <i class="bi bi-plus-circle"></i> Neue Firma „${_esc(q)}“ anlegen
                   </div>`;
            box.style.display = 'block';
            box.querySelectorAll('.mnc-firm-hit').forEach(el => {
                el.addEventListener('click', function() {
                    document.getElementById('mnc-firma').value = el.dataset.name || '';
                    document.getElementById('mnc-firma-id').value = el.dataset.id || '';
                    _setVal('new-customer', el.dataset.name || '');
                    _setVal('new-crm-account-id', el.dataset.id || '');
                    _setFirmaLinkedHint(!!el.dataset.id);
                    box.style.display = 'none';
                });
            });
            box.querySelector('.mnc-firm-new')?.addEventListener('click', function() {
                _createFirmaForPopup(q);
            });
        };

        fetch(urls[0], { credentials: 'same-origin' })
            .then(r => r.ok ? r.json() : Promise.reject())
            .then(d => {
                const hits = d.results || d.accounts || d.items || [];
                if (hits.length) { render(hits); return null; }
                return fetch(urls[1], { credentials: 'same-origin' })
                    .then(r => r.ok ? r.json() : {})
                    .then(d2 => render(d2.results || d2.accounts || d2.items || []));
            })
            .catch(() => {
                fetch(urls[1], { credentials: 'same-origin' })
                    .then(r => r.ok ? r.json() : {})
                    .then(d => render(d.results || d.accounts || d.items || []))
                    .catch(() => render([]));
            });
    }

    function runFirmaWebEnrich() {
        const name = ((document.getElementById('mnc-firma') || {}).value || '').trim()
            || _val('new-customer') || '';
        const panel = document.getElementById('mnc-firma-web-panel');
        const btn = document.getElementById('mnc-firma-web');
        const msg = document.getElementById('mnc-msg');
        if (!name || name.length < 2) {
            if (msg) { msg.style.color = '#ef4444'; msg.textContent = 'Bitte Firmenname eingeben.'; }
            return;
        }
        if (panel) {
            panel.style.display = 'block';
            panel.innerHTML = '<span style="color:#2563eb"><i class="bi bi-hourglass-split"></i> Suche Homepage / Impressum…</span>';
        }
        if (btn) btn.disabled = true;
        fetch(KI_API + 'firma-web/enrich/', {
            method: 'POST',
            credentials: 'same-origin',
            headers: { 'X-CSRFToken': csrf(), 'Content-Type': 'application/json' },
            body: JSON.stringify({ company_name: name }),
        })
            .then(r => r.json().then(d => ({ ok: r.ok, status: r.status, d })))
            .then(({ ok, d }) => {
                if (btn) btn.disabled = false;
                if (!ok || !d.success) {
                    const err = (d && (d.error || d.warning)) || 'Anreicherung fehlgeschlagen';
                    if (panel) {
                        panel.innerHTML = '<div style="color:#b45309">' + _esc(err) + '</div>'
                            + _firmaWebHitsHtml(d && d.search_hits);
                    }
                    return;
                }
                window._mncFirmaWebLast = d;
                _renderFirmaWebPanel(d);
            })
            .catch(e => {
                if (btn) btn.disabled = false;
                if (panel) {
                    panel.innerHTML = '<div style="color:#ef4444">' + _esc(e.message || String(e)) + '</div>';
                }
            });
    }

    function _firmaWebHitsHtml(hits) {
        const list = hits || [];
        if (!list.length) return '';
        return '<div style="margin-top:6px;opacity:.8">Treffer: '
            + list.slice(0, 3).map(h => '<div>· ' + _esc((h.title || '').slice(0, 50))
                + ' <a href="' + _escAttr(h.url || '#') + '" target="_blank" rel="noopener">Link</a></div>').join('')
            + '</div>';
    }

    function _renderFirmaWebPanel(d) {
        const panel = document.getElementById('mnc-firma-web-panel');
        if (!panel) return;
        const e = (d && d.enrich) || {};
        const accountId = ((document.getElementById('mnc-firma-id') || {}).value || '').trim()
            || _val('new-crm-account-id') || '';
        const addr = [e.street, [e.zip, e.city].filter(Boolean).join(' ')].filter(Boolean).join(', ');
        const emails = (e.emails || []).join(', ');
        const phones = (e.phones || []).join(', ');
        const contacts = (e.contacts || []).filter(c => c && c.name).map(c =>
            _esc(c.name) + (c.role ? ' (' + _esc(c.role) + ')' : '')
        ).join('; ');
        panel.style.display = 'block';
        panel.innerHTML =
            '<div style="font-weight:600;margin-bottom:6px"><i class="bi bi-globe2"></i> Web-Vorschlag'
            + (d.seconds != null ? ' <span style="font-weight:400;opacity:.7">(' + d.seconds + 's)</span>' : '')
            + '</div>'
            + '<div style="display:grid;gap:3px">'
            + '<div><b>Website:</b> ' + (e.website
                ? '<a href="' + _escAttr(e.website) + '" target="_blank" rel="noopener">' + _esc(e.website) + '</a>'
                : '—') + '</div>'
            + '<div><b>Adresse:</b> ' + _esc(addr || '—') + '</div>'
            + '<div><b>E-Mail:</b> ' + _esc(emails || '—') + '</div>'
            + '<div><b>Telefon:</b> ' + _esc(phones || '—') + '</div>'
            + (contacts ? '<div><b>Personen:</b> ' + contacts + '</div>' : '')
            + (e.summary_de ? '<div style="margin-top:4px"><b>Notiz:</b> ' + _esc(e.summary_de) + '</div>' : '')
            + '</div>'
            + '<div style="margin-top:8px;display:flex;gap:6px;flex-wrap:wrap">'
            + '<button type="button" class="matching-btn-primary" id="mnc-firma-web-apply" '
            + (accountId ? '' : 'disabled title="Zuerst Firma verknüpfen"')
            + ' style="font-size:11px;padding:4px 10px">'
            + '<i class="bi bi-cloud-upload"></i> In CRM übernehmen</button>'
            + '<button type="button" class="matching-btn-sm" id="mnc-firma-web-fill-mail" '
            + 'style="font-size:11px;padding:4px 10px"'
            + ((e.emails || [])[0] ? '' : ' disabled') + '>'
            + 'E-Mail ins Formular</button>'
            + '<button type="button" class="matching-btn-sm" id="mnc-firma-web-dismiss" '
            + 'style="font-size:11px;padding:4px 10px">Schließen</button>'
            + '</div>'
            + (accountId ? '' : '<div style="margin-top:4px;color:#b45309;font-size:11px">'
                + 'Firma zuerst verknüpfen/anlegen, dann CRM übernehmen.</div>');
        panel.querySelector('#mnc-firma-web-apply')?.addEventListener('click', function () {
            applyFirmaWebEnrichToCrm();
        });
        panel.querySelector('#mnc-firma-web-fill-mail')?.addEventListener('click', function () {
            const em = (((window._mncFirmaWebLast || {}).enrich || {}).emails || [])[0];
            if (em) {
                const inp = document.getElementById('mnc-email');
                if (inp && !String(inp.value || '').trim()) inp.value = em;
            }
        });
        panel.querySelector('#mnc-firma-web-dismiss')?.addEventListener('click', function () {
            panel.style.display = 'none';
        });
    }

    function applyFirmaWebEnrichToCrm() {
        const d = window._mncFirmaWebLast || {};
        const e = d.enrich || {};
        const accountId = ((document.getElementById('mnc-firma-id') || {}).value || '').trim()
            || _val('new-crm-account-id') || '';
        const msg = document.getElementById('mnc-msg');
        const panel = document.getElementById('mnc-firma-web-panel');
        if (!accountId) {
            if (msg) { msg.style.color = '#b45309'; msg.textContent = 'Firma zuerst verknüpfen.'; }
            return;
        }
        if (msg) { msg.style.color = '#2563eb'; msg.textContent = 'Schreibe Stammdaten ins CRM…'; }
        const body = {
            action: 'update',
            website: e.website || '',
            billing_address_street: e.street || '',
            billing_address_postalcode: e.zip || '',
            billing_address_city: e.city || '',
            billing_address_country: e.country || (e.city ? 'Deutschland' : ''),
            description: e.summary_de || '',
        };
        const chain = fetch('/crm/api/account/' + encodeURIComponent(accountId) + '/update/', {
            method: 'POST',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf() },
            body: JSON.stringify(body),
        }).then(r => r.json().catch(() => ({})));

        const emails = e.emails || [];
        const phones = e.phones || [];
        let p = chain;
        emails.slice(0, 2).forEach(function (em, i) {
            p = p.then(function () {
                return fetch('/crm/api/account/' + encodeURIComponent(accountId) + '/update/', {
                    method: 'POST',
                    credentials: 'same-origin',
                    headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf() },
                    body: JSON.stringify({ action: 'email_add', email: em, primaer: i === 0 }),
                }).then(r => r.json().catch(() => ({})));
            });
        });
        phones.slice(0, 2).forEach(function (ph) {
            p = p.then(function () {
                return fetch('/crm/api/account/' + encodeURIComponent(accountId) + '/update/', {
                    method: 'POST',
                    credentials: 'same-origin',
                    headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf() },
                    body: JSON.stringify({
                        action: 'phone_add',
                        nummer: ph,
                        field_name: 'phone_office',
                    }),
                }).then(r => r.json().catch(() => ({})));
            });
        });
        p.then(function () {
            if (msg) {
                msg.style.color = '#059669';
                msg.textContent = '✓ Firma aus Web in CRM übernommen';
            }
            if (panel) {
                const note = document.createElement('div');
                note.style.cssText = 'margin-top:6px;color:#059669;font-weight:500';
                note.textContent = '✓ In CRM gespeichert';
                panel.appendChild(note);
            }
        }).catch(function (err) {
            if (msg) {
                msg.style.color = '#ef4444';
                msg.textContent = err.message || String(err);
            }
        });
    }

    function _createFirmaForPopup(name) {
        const n = (name || '').trim();
        const msg = document.getElementById('mnc-msg');
        if (!n) return;
        if (_accountCreateInflight[_normFirmName(n)]) {
            if (msg) { msg.style.color = '#2563eb'; msg.textContent = 'Firma wird bereits angelegt…'; }
            return;
        }
        if (msg) { msg.style.color = '#2563eb'; msg.textContent = 'Löse Firma auf…'; }
        const email = ((document.getElementById('mnc-email') || {}).value || '').trim()
            || _val('new-contact-email') || '';
        const city = _guessCityFromLocation(_val('new-location') || '');
        _ensureCrmAccount(n, true, { email: email, city: city }).then(id => {
            if (!id) throw new Error('Firma konnte nicht angelegt/verknüpft werden');
            document.getElementById('mnc-firma').value = n;
            document.getElementById('mnc-firma-id').value = id;
            const res = document.getElementById('mnc-firma-results');
            if (res) res.style.display = 'none';
            _setVal('new-customer', n);
            _setVal('new-crm-account-id', id);
            _setFirmaLinkedHint(true);
            if (msg) {
                msg.style.color = '#059669';
                msg.textContent = email
                    ? '✓ Firma verknüpft (E-Mail gesetzt)'
                    : '✓ Firma verknüpft';
            }
        }).catch(e => {
            if (msg) { msg.style.color = '#ef4444'; msg.textContent = e.message || String(e); }
        });
    }

    function _guessCityFromLocation(loc) {
        const s = String(loc || '').trim();
        if (!s) return '';
        // "Berlin / Remote" → Berlin
        const left = s.split(/[\/|,]/)[0].trim();
        if (/remote|deutschland|germany|home\s*office/i.test(left)) return '';
        return left.length <= 60 ? left : '';
    }

    function pickCrmContactIndex(i) {
        pickCrmContact(_kiCrmPickList[i]);
    }

    function pickCrmContact(c) {
        if (!c) return;
        _setVal('new-contact', c.full_name || '');
        _setVal('new-crm-contact-id', c.crm_id || '');
        if (c.email) _setVal('new-contact-email', c.email);
        if (c.phone) _setVal('new-contact-phone', c.phone);
        _hideCrmSuggest();
        closeNewContactPopup();
    }

    function hideCrmSuggest() { _hideCrmSuggest(); }

    function _splitName(full) {
        const parts = String(full || '').trim().split(/\s+/).filter(Boolean);
        if (!parts.length) return { first: '', last: '' };
        if (parts.length === 1) return { first: '', last: parts[0] };
        return { first: parts.slice(0, -1).join(' '), last: parts[parts.length - 1] };
    }

    function _guessSalutation(firstName, hint) {
        const h = String(hint || '').trim();
        if (h === 'Hr.' || h === 'Fr.') return h;
        const f = String(firstName || '').trim().toLowerCase();
        if (!f) return 'Hr.';
        // häufige DE-Vornamen (kurz, ohne Anspruch auf Vollständigkeit)
        const female = {
            anna:1, anne:1, angela:1, anja:1, birgit:1, britta:1, caroline:1, claudia:1,
            daniela:1, diana:1, eva:1, franziska:1, gabriele:1, heike:1, ina:1, julia:1,
            karin:1, katharina:1, katrin:1, laura:1, lea:1, lena:1, lisa:1, maria:1,
            martina:1, monika:1, nadine:1, nicole:1, petra:1, sabine:1, sandra:1,
            sarah:1, silke:1, stefanie:1, susanne:1, tanja:1, ulrike:1, vanessa:1,
        };
        if (female[f]) return 'Fr.';
        return 'Hr.';
    }

    /** bob@bobmichaels.ai → Bob Michaels; bob.michaels@x.de → Bob Michaels */
    function _nameFromEmail(email) {
        const m = String(email || '').trim().toLowerCase().match(/^([^@]+)@([^@]+)$/);
        if (!m) return { first: '', last: '', full: '' };
        const cap = function (s) {
            s = String(s || '');
            return s ? (s.charAt(0).toUpperCase() + s.slice(1).toLowerCase()) : '';
        };
        const localParts = m[1]
            .replace(/[0-9]+/g, ' ')
            .replace(/[._+\-]+/g, ' ')
            .trim()
            .split(/\s+/)
            .filter(function (p) { return /^[a-zäöüß]{2,}$/i.test(p); });
        if (localParts.length >= 2) {
            const first = localParts.slice(0, -1).map(cap).join(' ');
            const last = cap(localParts[localParts.length - 1]);
            return { first: first, last: last, full: (first + ' ' + last).trim() };
        }
        const domainCore = (m[2].split('.')[0] || '').replace(/[^a-z0-9äöüß]/gi, '');
        if (localParts.length === 1) {
            const firstRaw = localParts[0].toLowerCase();
            if (domainCore.indexOf(firstRaw) === 0 && domainCore.length > firstRaw.length + 1) {
                const rest = domainCore.slice(firstRaw.length);
                if (rest.length >= 2 && /^[a-zäöüß]+$/i.test(rest)) {
                    return {
                        first: cap(firstRaw),
                        last: cap(rest),
                        full: cap(firstRaw) + ' ' + cap(rest),
                    };
                }
            }
            return { first: '', last: cap(firstRaw), full: cap(firstRaw) };
        }
        return { first: '', last: '', full: '' };
    }

    function _personNameLooksLikeCompany(name, firmName) {
        const n = String(name || '').trim();
        if (!n) return false;
        if (_looksLikeCompany(n)) return true;
        const nn = _normFirmName(n);
        const fn = _normFirmName(firmName);
        if (nn && fn && (nn === fn || fn.indexOf(nn) >= 0 || nn.indexOf(fn) >= 0)) return true;
        return false;
    }

    function createCrmContactFromSuggest() {
        const salutation = (document.getElementById('mnc-salutation') || {}).value || 'Hr.';
        let first = ((document.getElementById('mnc-firstname') || {}).value || '').trim();
        let last = ((document.getElementById('mnc-lastname') || {}).value || '').trim();
        const email = ((document.getElementById('mnc-email') || {}).value || '').trim();
        const phone = ((document.getElementById('mnc-phone') || {}).value || '').trim();
        let firmName = ((document.getElementById('mnc-firma') || {}).value || '').trim();
        let accountId = ((document.getElementById('mnc-firma-id') || {}).value || '').trim()
            || _val('new-crm-account-id') || '';
        const msg = document.getElementById('mnc-msg');
        const saveBtn = document.getElementById('mnc-save');

        // Schutz: Firmenname nicht als Person speichern (a2a Experts + bob@…)
        const fullTry = (first + ' ' + last).trim();
        if (_personNameLooksLikeCompany(fullTry, firmName) || _personNameLooksLikeCompany(last, firmName)) {
            const fromMail = _nameFromEmail(email);
            if (fromMail.last) {
                first = fromMail.first;
                last = fromMail.last;
                const fi = document.getElementById('mnc-firstname');
                const la = document.getElementById('mnc-lastname');
                if (fi) fi.value = first;
                if (la) la.value = last;
                if (msg) {
                    msg.style.color = '#b45309';
                    msg.textContent = 'Name wirkte wie Firmenname — aus E-Mail gesetzt: ' + fromMail.full;
                }
            } else {
                if (msg) {
                    msg.style.color = '#ef4444';
                    msg.textContent = 'Nachname sieht nach Firma aus — bitte Personennamen eintragen (nicht „' + firmName + '“).';
                }
                document.getElementById('mnc-lastname')?.focus();
                return;
            }
        }

        if (!last) {
            if (msg) { msg.style.color = '#ef4444'; msg.textContent = 'Nachname ist Pflichtfeld.'; }
            document.getElementById('mnc-lastname')?.focus();
            return;
        }
        if (!email) {
            if (msg) { msg.style.color = '#ef4444'; msg.textContent = 'E-Mail ist Pflichtfeld.'; }
            document.getElementById('mnc-email')?.focus();
            return;
        }
        if (msg) { msg.style.color = '#2563eb'; msg.textContent = 'Lege Kontakt an…'; }
        if (saveBtn) saveBtn.disabled = true;

        // Firma mit Name aber ohne ID → suchen oder anlegen, dann verknüpfen
        const ensureAccount = () => {
            if (accountId) return Promise.resolve(accountId);
            if (!firmName) return Promise.resolve('');
            if (msg) msg.textContent = 'Löse Firma „' + firmName + '“ auf…';
            return _ensureCrmAccount(firmName, true, {
                email: email,
                city: _guessCityFromLocation(_val('new-location') || ''),
            }).then(id => {
                if (!id) {
                    throw new Error(
                        'Firma „' + firmName + '“ konnte nicht verknüpft werden. '
                        + 'Bitte Treffer wählen oder „Neue Firma“ klicken.'
                    );
                }
                accountId = id;
                const el = document.getElementById('mnc-firma-id');
                if (el) el.value = id;
                _setVal('new-customer', firmName);
                _setVal('new-crm-account-id', id);
                _setFirmaLinkedHint(true);
                return id;
            });
        };

        ensureAccount().then(accId => {
            if (msg) msg.textContent = 'Lege Kontakt an…';
            return fetch('/crm/api/berater/new/', {
                method: 'POST',
                credentials: 'same-origin',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf() },
                body: JSON.stringify({
                    salutation: salutation,
                    first_name: first,
                    last_name: last,
                    email: email || undefined,
                    phone: phone || undefined,
                }),
            }).then(r => r.json()).then(d => {
                if (!d.ok || !d.crm_id) throw new Error(d.error || 'Anlegen fehlgeschlagen');
                return d.crm_id;
            }).then(async crmId => {
                // Fallback falls berater/new E-Mail/Tel nicht mitgenommen hat
                async function _contactUpdate(payload) {
                    const r = await fetch('/crm/api/contact/' + crmId + '/update/', {
                        method: 'POST',
                        credentials: 'same-origin',
                        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf() },
                        body: JSON.stringify(payload),
                    });
                    const d = await r.json().catch(() => ({}));
                    if (!r.ok || d.ok === false) {
                        throw new Error(
                            (d && d.error) || ('Kontakt-Update fehlgeschlagen (HTTP ' + r.status + ')')
                        );
                    }
                    return d;
                }
                if (phone) {
                    await _contactUpdate({
                        action: 'phone_add',
                        nummer: phone,
                        field_name: 'phone_mobile',
                    });
                }
                if (email) {
                    await _contactUpdate({
                        action: 'email_add',
                        email: email,
                        primaer: true,
                    });
                }
                if (accId) {
                    const lr = await fetch('/crm/api/contact/' + crmId + '/link-account/', {
                        method: 'POST',
                        credentials: 'same-origin',
                        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf() },
                        body: JSON.stringify({ account_crm_id: accId }),
                    });
                    const ld = await lr.json().catch(() => ({}));
                    if (!lr.ok || ld.ok === false) {
                        throw new Error(
                            (ld && ld.error)
                            || ('Firma-Verknüpfung fehlgeschlagen (HTTP ' + lr.status + ')')
                        );
                    }
                }
                _setVal('new-contact', (first + ' ' + last).trim());
                _setVal('new-crm-contact-id', crmId);
                if (email) _setVal('new-contact-email', email);
                if (phone) _setVal('new-contact-phone', phone);
                if (firmName) _setVal('new-customer', firmName);
                if (accountId) _setVal('new-crm-account-id', accountId);
                if (msg) {
                    msg.style.color = '#059669';
                    msg.innerHTML = '✓ Kontakt angelegt'
                        + (accountId ? ' und Firma verknüpft' : '')
                        + '. <a href="/crm/berater/?detail=' + encodeURIComponent(crmId)
                        + '" target="_blank" rel="noopener">Im CRM öffnen</a>';
                }
                setTimeout(function () {
                    closeNewContactPopup();
                    _hideCrmSuggest();
                }, 1100);
            });
        }).catch(e => {
            if (saveBtn) saveBtn.disabled = false;
            if (msg) { msg.style.color = '#ef4444'; msg.textContent = e.message || String(e); }
        });
    }

    function _setFirmaLinkedHint(ok) {
        const hint = document.getElementById('mnc-firma-linked');
        if (!hint) return;
        if (ok) {
            hint.style.display = '';
            hint.style.color = '#059669';
            hint.textContent = '✓ Firma verknüpft';
        } else {
            hint.style.display = '';
            hint.style.color = '#b45309';
            hint.textContent = '⚠ Firma noch nicht verknüpft — Treffer wählen oder Neue Firma';
        }
    }

    function _normalizeFirmHits(d) {
        if (!d) return [];
        if (Array.isArray(d.results)) return d.results;
        if (Array.isArray(d.accounts)) return d.accounts;
        if (Array.isArray(d.items)) return d.items;
        if (Array.isArray(d)) return d;
        return [];
    }

    function _firmIdOf(h) {
        return (h && (h.crm_id || h.id || h.account_crm_id || '')) + '';
    }

    function _searchAccountsAny(q) {
        const urls = [
            API + 'crm/accounts/?q=' + encodeURIComponent(q),
            '/crm/api/kunden/?q=' + encodeURIComponent(q) + '&limit=10',
        ];
        return fetch(urls[0], { credentials: 'same-origin' })
            .then(r => r.ok ? r.json() : Promise.reject())
            .then(d => {
                const hits = _normalizeFirmHits(d);
                if (hits.length) return hits;
                return fetch(urls[1], { credentials: 'same-origin' })
                    .then(r => r.ok ? r.json() : {})
                    .then(d2 => _normalizeFirmHits(d2));
            })
            .catch(() => fetch(urls[1], { credentials: 'same-origin' })
                .then(r => r.ok ? r.json() : {})
                .then(d => _normalizeFirmHits(d))
                .catch(() => []));
    }

    function _resolveFirmaForPopup(name, opts) {
        opts = opts || {};
        const n = (name || '').trim();
        if (!n) return Promise.resolve('');
        const cached = _accountIdByNorm[_normFirmName(n)];
        if (cached) {
            const firma = document.getElementById('mnc-firma');
            const firmaId = document.getElementById('mnc-firma-id');
            if (firma && !firma.value) firma.value = n;
            if (firmaId) firmaId.value = cached;
            _setVal('new-customer', n);
            _setVal('new-crm-account-id', cached);
            _setFirmaLinkedHint(true);
            return Promise.resolve(cached);
        }
        return _searchAccountsAny(n).then(hits => {
            const exact = _findExactFirm(hits, n);
            if (exact && opts.autoSelectExact !== false) {
                const id = _firmIdOf(exact);
                const nm = exact.name || n;
                const firma = document.getElementById('mnc-firma');
                const firmaId = document.getElementById('mnc-firma-id');
                if (firma) firma.value = nm;
                if (firmaId) firmaId.value = id;
                _setVal('new-customer', nm);
                _setVal('new-crm-account-id', id);
                _rememberAccountId(n, id);
                _setFirmaLinkedHint(!!id);
                const box = document.getElementById('mnc-firma-results');
                if (box) box.style.display = 'none';
                return id;
            }
            if (opts.showList !== false) _searchFirmaForPopup(n);
            _setFirmaLinkedHint(false);
            return '';
        });
    }

    // Dedup: parallele Creates derselben Firma teilen sich ein Promise;
    // Session-Cache verhindert Doppel-Anlagen bei ES-Lag nach dem ersten Create.
    const _accountCreateInflight = {};
    const _accountIdByNorm = {};

    function _normFirmName(name) {
        return String(name || '')
            .toLowerCase()
            .replace(/[.,/&+]/g, ' ')
            .replace(/\b(gmbh|mbh|ag|se|kg|ug|ltd|inc|corp|co|e\.?\s*k\.?)\b/g, ' ')
            .replace(/\s+/g, ' ')
            .trim();
    }

    function _rememberAccountId(name, id) {
        const key = _normFirmName(name);
        if (key && id) _accountIdByNorm[key] = String(id);
    }

    function _findExactFirm(hits, name) {
        const want = _normFirmName(name);
        if (!want) return null;
        const list = hits || [];
        // 1) Exakter Norm-Name (Stadt spielt keine Rolle)
        const exact = list.filter(h => _normFirmName(h.name) === want);
        if (exact.length === 1) return exact[0];
        if (exact.length > 1) {
            // Mehrere mit gleichem Namen → aktiven bevorzugen, sonst ersten
            const active = exact.find(h => {
                const st = String(h.status || h.account_status || '').toLowerCase();
                return st && st !== 'passiv' && st !== 'inactive';
            });
            return active || exact[0];
        }
        // 2) Einziger Treffer insgesamt und Name enthält Query / umgekehrt
        if (list.length === 1) {
            const only = list[0];
            const hn = _normFirmName(only.name);
            if (hn.indexOf(want) >= 0 || want.indexOf(hn) >= 0) return only;
        }
        // 3) Einziger Treffer, dessen Norm-Name mit Query beginnt (z. B. „Constaff“ → Constaff GmbH)
        const starts = list.filter(h => {
            const hn = _normFirmName(h.name);
            return hn === want || hn.indexOf(want) === 0 || want.indexOf(hn) === 0;
        });
        if (starts.length === 1) return starts[0];
        return null;
    }

    function _attachAccountEmail(accountId, email) {
        const em = String(email || '').trim();
        if (!accountId || !em || em.indexOf('@') < 0) return Promise.resolve();
        return fetch('/crm/api/account/' + encodeURIComponent(accountId) + '/update/', {
            method: 'POST',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf() },
            body: JSON.stringify({ action: 'email_add', email: em, primaer: true }),
        }).then(r => r.json().catch(() => ({}))).catch(() => ({}));
    }

    function _writeAccountIdsToForm(name, id) {
        if (!id) return;
        _rememberAccountId(name, id);
        const firmaId = document.getElementById('mnc-firma-id');
        if (firmaId) firmaId.value = id;
        _setVal('new-crm-account-id', id);
        if (name) {
            const firma = document.getElementById('mnc-firma');
            if (firma && !String(firma.value || '').trim()) firma.value = name;
            if (!_val('new-customer')) _setVal('new-customer', name);
        }
    }

    function _ensureCrmAccount(name, createIfMissing, opts) {
        opts = opts || {};
        const n = (name || '').trim();
        if (!n) return Promise.resolve('');
        const existing = (
            ((document.getElementById('mnc-firma-id') || {}).value || '').trim()
            || _val('new-crm-account-id')
            || _accountIdByNorm[_normFirmName(n)]
            || ''
        );
        if (existing) {
            _writeAccountIdsToForm(n, existing);
            if (opts.email) _attachAccountEmail(existing, opts.email);
            return Promise.resolve(existing);
        }

        const key = _normFirmName(n);
        if (!key) return Promise.resolve('');
        if (_accountCreateInflight[key]) return _accountCreateInflight[key];

        const run = _searchAccountsAny(n).then(hits => {
            const hit = _findExactFirm(hits, n);
            if (hit) {
                const id = _firmIdOf(hit);
                _writeAccountIdsToForm(hit.name || n, id);
                if (opts.email) _attachAccountEmail(id, opts.email);
                return id;
            }
            // Mehrere Treffer ohne exakten Match → NICHT blind neu anlegen
            if ((hits || []).length > 1) {
                if (opts.showPick !== false) {
                    _showCrmAccountPick(hits, {
                        note: 'Mehrere Firmen ähnlich „' + n + '“ — bitte wählen (kein Duplikat anlegen):',
                    });
                }
                return '';
            }
            if (!createIfMissing) return '';

            // Nochmal suchen kurz vor Create (Race / ES-Lag)
            return _searchAccountsAny(n).then(hits2 => {
                // Session-Cache kann inzwischen gefüllt sein (paralleler Pfad)
                const cached2 = _accountIdByNorm[key];
                if (cached2) {
                    _writeAccountIdsToForm(n, cached2);
                    if (opts.email) _attachAccountEmail(cached2, opts.email);
                    return cached2;
                }
                const hit2 = _findExactFirm(hits2, n);
                if (hit2) {
                    const id2 = _firmIdOf(hit2);
                    _writeAccountIdsToForm(hit2.name || n, id2);
                    if (opts.email) _attachAccountEmail(id2, opts.email);
                    return id2;
                }
                if ((hits2 || []).length > 1) return '';
                return fetch('/crm/api/kunden/new/', {
                    method: 'POST',
                    credentials: 'same-origin',
                    headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf() },
                    body: JSON.stringify({
                        name: n,
                        city: opts.city || '',
                        email: opts.email || undefined,
                    }),
                }).then(r => r.json()).then(x => {
                    const id = x.crm_id || x.id || '';
                    if (!id) throw new Error(x.error || 'Firma anlegen fehlgeschlagen');
                    _writeAccountIdsToForm(n, id);
                    if (opts.email) {
                        return _attachAccountEmail(id, opts.email).then(() => id);
                    }
                    return id;
                });
            });
        }).finally(() => {
            delete _accountCreateInflight[key];
        });

        _accountCreateInflight[key] = run;
        return run;
    }

    function _esc(s) {
        return String(s == null ? '' : s)
            .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    }
    function _escAttr(s) {
        return _esc(s).replace(/"/g, '&quot;');
    }

    // ──────────────────────────────────────────────────
    // AKTIONEN
    // ──────────────────────────────────────────────────

    function _setVal(id, val) {
        const el = document.getElementById(id);
        if (el) el.value = val == null ? '' : val;
    }

    function _handleDeepLink() {
        try {
            const params = new URLSearchParams(window.location.search || '');
            const fromMail = params.get('from_mail');
            const emailText = params.get('email_text');
            let stored = null;
            try {
                const raw = sessionStorage.getItem('matching_ki_from_mail');
                if (raw) {
                    stored = JSON.parse(raw);
                    sessionStorage.removeItem('matching_ki_from_mail');
                }
            } catch (_) { /* ignore */ }

            if (fromMail || emailText || stored) {
                openKiWizard({
                    email_text: emailText || (stored && stored.email_text) || '',
                    subject: params.get('subject') || (stored && stored.subject) || '',
                    outer_from: params.get('outer_from') || (stored && stored.outer_from) || '',
                    from_mail: fromMail || (stored && stored.from_mail) || '',
                });
                if (fromMail && !(emailText || (stored && stored.email_text))) {
                    _loadMailIntoKiWizard(fromMail);
                }
            }
        } catch (e) {
            console.warn('Matching deeplink:', e);
        }
    }

    function newRequest() { switchTab('neu'); }

    function _loadMailIntoKiWizard(mailId) {
        // Best-effort: Shaduler/EDMS Endpunkte — scheitert still, User kann Text einfügen
        const paths = [
            '/shaduler/api/inbox/' + encodeURIComponent(mailId) + '/view/',
            '/shaduler/api/inbox/' + encodeURIComponent(mailId) + '/',
            '/edms/api/mail/' + encodeURIComponent(mailId) + '/',
        ];
        const pickBody = (d) => {
            const plain = d.body_plain || d.body || d.text || d.content || d.email_text || '';
            const html = d.body_html || d.html || '';
            if (plain && !/<\s*(html|body|div|p|br|table)\b/i.test(plain)) return String(plain).trim();
            if (html) {
                try {
                    const el = document.createElement('div');
                    el.innerHTML = html;
                    return String(el.innerText || el.textContent || '').trim();
                } catch (_) { /* ignore */ }
            }
            return String(plain || '').trim();
        };
        const tryNext = (i) => {
            if (i >= paths.length) return;
            fetch(paths[i], { credentials: 'same-origin' })
                .then(r => r.ok ? r.json() : Promise.reject())
                .then(d => {
                    if (d && d.ok === false) return tryNext(i + 1);
                    const body = pickBody(d || {});
                    const sub = d.subject || d.subj || '';
                    const from = d.from || d.from_ || d.outer_from || d.sender || '';
                    if (!body) return tryNext(i + 1);
                    const emailEl = document.getElementById('matching-ki-email');
                    const subEl = document.getElementById('matching-ki-subject');
                    const fromEl = document.getElementById('matching-ki-from');
                    if (emailEl && !emailEl.value) emailEl.value = body;
                    if (subEl && !subEl.value) subEl.value = sub;
                    if (fromEl && !fromEl.value) fromEl.value = from;
                })
                .catch(() => tryNext(i + 1));
        };
        tryNext(0);
    }

    function switchTab(tabId) {
        _activateTab(tabId);
        history.pushState({}, '', '/matching/?tab=' + tabId);
    }

    function openProject(projectId, targetTab) {
        window.MATCHING_CONFIG.activeProject = projectId;

        if (!targetTab || targetTab === 'shortlist') {
            // Shortlist direkt laden — NICHT über _loadTabContent
            const content = document.getElementById('content-shortlist');
            if (content) {
                content.dataset.loaded = '0';
                content.innerHTML = '';
                _loadShortlistForProject(projectId, content);
            }
            switchTab('shortlist');
        } else {
            // Kanban oder andere Tabs
            const content = document.getElementById('content-' + targetTab);
            if (content) {
                content.dataset.loaded = '0';
                content.innerHTML = '';
            }
            switchTab(targetTab);
        }
    }

    /**
     * Anfrage öffnen / bearbeiten (Klick auf Titel in Anfragen-Liste).
     */
    function openRequestEdit(projectId) {
        if (!projectId) return;
        window.MATCHING_CONFIG.activeProject = projectId;
        const content = document.getElementById('content-neu');
        const loading = document.getElementById('loading-neu');
        if (loading) loading.style.display = 'flex';
        switchTab('neu');

        _jsonGet('/shaduler/api/matching/request/' + encodeURIComponent(projectId) + '/')
            .then(d => {
                if (loading) loading.style.display = 'none';
                if (!d || (!d.ok && !d.success) || !d.request) {
                    throw new Error((d && d.error) || 'Anfrage konnte nicht geladen werden');
                }
                _renderRequestEditForm(content, d.request);
            })
            .catch(e => {
                if (loading) loading.style.display = 'none';
                // Fallback: Matching-API Detail, falls vorhanden
                fetch(API + 'requests/' + encodeURIComponent(projectId) + '/', {
                    credentials: 'same-origin',
                })
                .then(r => r.json().then(d => ({ ok: r.ok, d })))
                .then(({ ok, d }) => {
                    const req = (d && (d.request || d.result || d)) || null;
                    if (ok && req && (req.id || req.title)) {
                        _renderRequestEditForm(content, req);
                        return;
                    }
                    throw e;
                })
                .catch(err => {
                    if (content) {
                        content.innerHTML = '<p style="color:#ef4444;padding:20px">'
                            + _esc(err.message || String(err)) + '</p>';
                        content.dataset.loaded = '1';
                    }
                });
            });
    }

    function _renderRequestEditForm(content, req) {
        if (!content) return;
        const skills = Array.isArray(req.skills)
            ? req.skills
            : (Array.isArray(req.required_skills)
                ? req.required_skills.map(s => (typeof s === 'string' ? s : (s && s.name) || '')).filter(Boolean)
                : []);
        const skillsStr = skills.join(', ');
        const rateMax = (req.rate_max != null && req.rate_max !== '') ? String(req.rate_max) : '';
        const duration = (req.duration_months != null) ? String(req.duration_months) : '';
        const start = req.start_date || '';
        const num = req.project_number || '';

        content.innerHTML = `
        <div style="display:flex;align-items:center;gap:10px;margin-bottom:12px;flex-wrap:wrap">
            <button type="button" class="matching-btn-sm" onclick="Matching.switchTab('anfragen')">
                <i class="bi bi-arrow-left"></i> ${_esc(_kiT('back_to_requests', 'Anfragen'))}
            </button>
            <div style="font-size:13px;font-weight:700;flex:1">
                ${_esc(_kiT('edit_request_title', 'Anfrage bearbeiten'))}
                ${num ? ' · <span style="color:#888;font-weight:500">' + _esc(num) + '</span>' : ''}
            </div>
            <button type="button" class="matching-btn-sm"
                    onclick="Matching.openProject('${req.id}','shortlist')">
                <i class="bi bi-funnel"></i> Shortlist
            </button>
        </div>
        <input type="hidden" id="edit-request-id" value="${_escAttr(req.id || '')}">
        <div class="matching-section-head" onclick="toggleSection(this)">
            ${_t('matching.section_customer')} <i class="bi bi-chevron-down"></i>
        </div>
        <div class="matching-section-body">
            <div class="matching-form-grid">
                <div class="matching-form-group">
                    <label class="matching-form-label">${_t('matching.neu_customer')}</label>
                    <input class="matching-form-input" id="new-customer"
                           value="${_escAttr(req.customer_name || '')}">
                    <input type="hidden" id="new-crm-account-id" value="${_escAttr(req.crm_account_id || '')}">
                </div>
                <div class="matching-form-group">
                    <label class="matching-form-label">${_t('matching.neu_contact')}</label>
                    <input class="matching-form-input" id="new-contact"
                           value="${_escAttr(req.contact_name || '')}">
                    <input type="hidden" id="new-crm-contact-id" value="${_escAttr(req.crm_contact_id || '')}">
                </div>
                <div class="matching-form-group">
                    <label class="matching-form-label">${_kiT('contact_email', 'E-Mail Ansprechpartner')}</label>
                    <input class="matching-form-input" id="new-contact-email" type="email"
                           value="${_escAttr(req.contact_email || '')}">
                </div>
                <div class="matching-form-group">
                    <label class="matching-form-label">${_kiT('contact_phone', 'Telefon Ansprechpartner')}</label>
                    <input class="matching-form-input" id="new-contact-phone" type="tel"
                           value="${_escAttr(req.contact_phone || '')}">
                </div>
            </div>
        </div>
        <div class="matching-section-head" onclick="toggleSection(this)">
            ${_t('matching.section_details')} <i class="bi bi-chevron-down"></i>
        </div>
        <div class="matching-section-body">
            <div class="matching-form-grid">
                <div class="matching-form-group span2">
                    <label class="matching-form-label">${_t('matching.neu_text')}</label>
                    <textarea class="matching-form-textarea" id="new-description">${_esc(req.description || '')}</textarea>
                </div>
                <div class="matching-form-group span2">
                    <label class="matching-form-label">${_t('matching.neu_title')}</label>
                    <input class="matching-form-input" id="new-title" value="${_escAttr(req.title || '')}">
                </div>
                <div class="matching-form-group span2">
                    <label class="matching-form-label">${_kiT('neu_skills', 'Skills (für Matching)')}</label>
                    <div style="display:flex;gap:6px;align-items:center;flex-wrap:wrap">
                        <input class="matching-form-input" id="new-skills" style="flex:1;min-width:180px"
                               value="${_escAttr(skillsStr)}"
                               placeholder="${_escAttr(_kiT('skills_placeholder', 'z.B. Mainframe, Cloud, Architecture'))}">
                        <button type="button" class="matching-btn-sm"
                                title="${_escAttr(_kiT('skills_from_text_title', 'Skills aus Anfrage-Text übernehmen (Qualifikationen / Skills-Zeile)'))}"
                                onclick="Matching.fillSkillsFromText({force:true})">
                            <i class="bi bi-magic"></i> ${_esc(_kiT('skills_from_text', 'aus Text'))}
                        </button>
                    </div>
                    <input type="hidden" id="new-skills-json" value="${_escAttr(JSON.stringify(skills))}">
                    <div style="font-size:10px;color:#888;margin-top:4px">
                        ${_esc(_kiT('skills_hint', 'Ohne Skills matcht die Engine oft Blindlinge (~70%). Muss zuerst, Nice-to-have danach.'))}
                    </div>
                </div>
                <div class="matching-form-group">
                    <label class="matching-form-label">${_t('matching.neu_start_label')}</label>
                    <input class="matching-form-input" type="date" id="new-start" value="${_escAttr(start)}">
                </div>
                <div class="matching-form-group">
                    <label class="matching-form-label">${_t('matching.neu_duration_label')}</label>
                    <input class="matching-form-input" type="number" id="new-duration" value="${_escAttr(duration)}">
                </div>
                <div class="matching-form-group">
                    <label class="matching-form-label">${_t('matching.neu_location')}</label>
                    <input class="matching-form-input" id="new-location" value="${_escAttr(req.location || '')}">
                </div>
                <div class="matching-form-group">
                    <label class="matching-form-label">${_t('matching.neu_rate_label')}</label>
                    <input class="matching-form-input" type="number" id="new-rate-max" value="${_escAttr(rateMax)}">
                </div>
            </div>
        </div>
        <div id="edit-request-msg" style="font-size:12px;min-height:18px;margin-top:6px"></div>
        <div style="display:flex;gap:8px;justify-content:flex-end;margin-top:8px;flex-wrap:wrap">
            <button class="matching-btn-sm" onclick="Matching.switchTab('anfragen')">${_t('matching.btn_cancel')}</button>
            <button class="matching-btn-sm"
                    onclick="Matching.openProject('${req.id}','shortlist')">
                <i class="bi bi-funnel"></i> ${_esc(_kiT('save_then_shortlist', 'Zur Shortlist'))}
            </button>
            <button class="matching-btn-primary" onclick="Matching.saveRequestEdit()">
                <i class="bi bi-save"></i> ${_esc(_kiT('btn_save_request', 'Speichern'))}
            </button>
        </div>`;
        content.dataset.loaded = '1';
        _bindCustomerField();
        // Bestehende Anfragen: Skills oft nur im Text („• Skills:“ / Qualifikationen), Feld leer
        if (!skillsStr) {
            setTimeout(function () { fillSkillsFromText({ silent: true }); }, 0);
        }
    }

    function saveRequestEdit() {
        const id = _val('edit-request-id');
        if (!id) {
            alert(_kiT('edit_no_id', 'Keine Anfrage-ID — bitte neu öffnen.'));
            return;
        }
        const parsed = _parseSkillsInput();
        const skillNames = _skillNamesFromParsed(parsed);
        const payload = {
            title:           _val('new-title'),
            description:     _val('new-description'),
            customer_name:   _val('new-customer'),
            contact_name:    _val('new-contact'),
            contact_email:   _val('new-contact-email'),
            contact_phone:   _val('new-contact-phone'),
            crm_account_id:  _val('new-crm-account-id'),
            crm_contact_id:  _val('new-crm-contact-id'),
            start_date:      _val('new-start') || null,
            duration_months: parseInt(_val('new-duration')) || 0,
            location:        _val('new-location'),
            rate_max:        parseInt(_val('new-rate-max')) || null,
            skills:          skillNames,
            required_skills: parsed,
            extracted_technologies: skillNames,
        };
        if (!payload.title || !payload.customer_name) {
            alert(_t('matching.err_title_required'));
            return;
        }
        const msg = document.getElementById('edit-request-msg');
        if (msg) { msg.style.color = '#2563eb'; msg.textContent = 'Speichere…'; }

        _jsonPost('/shaduler/api/matching/request/' + encodeURIComponent(id) + '/', payload)
            .then(d => {
                if (!d || (!d.ok && !d.success)) {
                    throw new Error((d && d.error) || 'Speichern fehlgeschlagen');
                }
                if (msg) {
                    msg.style.color = '#059669';
                    msg.textContent = '✓ Gespeichert'
                        + (skillNames.length ? (' · ' + skillNames.length + ' Skills') : ' · ⚠ keine Skills');
                }
                const c = document.getElementById('content-anfragen');
                if (c) c.dataset.loaded = '0';
            })
            .catch(e => {
                if (msg) { msg.style.color = '#ef4444'; msg.textContent = e.message || String(e); }
            });
    }

    function runMatching(projectId, opts) {
        opts = opts || {};
        if (!projectId) projectId = window.MATCHING_CONFIG.activeProject;
        const body = {};
        if (opts.reset) {
            body.reset = true;
            body.clear = true;
            body.force = true;
        }
        fetch(API + 'requests/' + projectId + '/match/', {
            method: 'POST',
            credentials: 'same-origin',
            headers: { 'X-CSRFToken': csrf(), 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
        })
        .then(async r => {
            let d = {};
            try { d = await r.json(); } catch (_) {}
            if (!r.ok) {
                if (d && (d.code === 'no_skills' || d.error)) {
                    d.success = false;
                    return d;
                }
                throw new Error(
                    (d && (d.error || d.detail)) || ('Matching HTTP ' + r.status)
                );
            }
            return d;
        })
        .then(d => {
            if (d.success) {
                alert(_t('matching.matching_started'));
                const content = document.getElementById('content-shortlist');
                if (content) content.dataset.loaded = '0';
                // Matching inkl. Gulp/FLM kann 30–90s dauern — länger nachladen
                const delays = opts.reset
                    ? [3000, 8000, 15000, 30000, 45000, 70000, 90000]
                    : [2000, 5000, 10000, 20000];
                delays.forEach(ms => {
                    setTimeout(() => {
                        const el = document.getElementById('content-shortlist');
                        if (el) {
                            el.dataset.loaded = '0';
                            _loadShortlistForProject(projectId, el);
                        }
                    }, ms);
                });
            } else {
                const msg = (d && (d.error || d.message)) || _t('matching.err_match');
                if (d && d.code === 'no_skills') {
                    alert(_kiT('match_no_skills', msg));
                } else {
                    alert(msg);
                }
            }
        })
        .catch(e => {
            console.error(e);
            alert(_t('matching.err_connection') + ': ' + (e.message || e));
        });
    }

    /**
     * Shortlist resetten und Matching neu starten.
     * 1) versucht DELETE/POST clear-Endpoint
     * 2) startet match mit reset=true
     */
    function _cleanSkillToken(raw) {
        let s = String(raw || '').trim();
        s = s.replace(/^[\s•\-\*–—·]+/, '').replace(/[\s.;:]+$/, '').replace(/\s+/g, ' ').trim();
        if (s.length < 2 || s.length > 80) return '';
        if ((s.match(/ /g) || []).length > 8) return '';
        const low = s.toLowerCase();
        if (/^(remote|deutschland|vollzeit|freiberuflich|asap|interessiert|kurzbeschreibung|rahmeninformationen)$/i.test(low)) {
            return '';
        }
        return s;
    }

    function _isNiceSkill(name) {
        return /^(agile(\s+methoden)?|scrum|kanban|coaching|mentoring|knowledge\s*transfer|wissenstransfer|kommunikation|teamarbeit|präsentation|deutsch|englisch|führerschein|reisebereitschaft)$/i.test(
            String(name || '').trim()
        );
    }

    function _splitSkillLine(line) {
        line = String(line || '').trim().replace(/^[\s•\-\*–—·\d.)]+/, '').trim();
        if (!line) return [];
        const out = [];
        const m = line.match(/^(.+?)\s*\(([^)]+)\)\s*$/);
        if (m) {
            const head = _cleanSkillToken(m[1]);
            if (head) out.push(head);
            m[2].split(/[,;]|\s+oder\s+|\s+und\s+|\s+or\s+|\s+and\s+/i).forEach(part => {
                const tok = _cleanSkillToken(part);
                if (tok) out.push(tok);
            });
            return out;
        }
        const parts = /[,;]/.test(line) ? line.split(/[,;]/) : [line];
        parts.forEach(part => {
            const sub = String(part).split(/\s+oder\s+|\s+und\s+|\s+or\s+|\s+and\s+/i);
            if (sub.length > 1 && sub.every(x => (_cleanSkillToken(x) || String(x).trim()).length <= 40)) {
                sub.forEach(s => {
                    const tok = _cleanSkillToken(s);
                    if (tok) out.push(tok);
                });
            } else {
                const tok = _cleanSkillToken(part);
                if (tok) out.push(tok);
            }
        });
        return out;
    }

    /** Skills aus Anfrage-Text: „• Skills:“, Qualifikationen-Liste, Nice-to-have. */
    function _extractSkillsFromText(text) {
        const raw = String(text || '');
        const required = [];
        const nice = [];
        const seen = {};

        function add(token, forceNice) {
            const tok = _cleanSkillToken(token);
            if (!tok) return;
            const key = tok.toLowerCase();
            if (seen[key]) return;
            seen[key] = true;
            if (forceNice || _isNiceSkill(tok)) nice.push(tok);
            else required.push(tok);
        }

        const skillsLineRe = /(?:^|\n)\s*(?:[•\-\*–—]\s*)?Skills\s*:\s*(.+?)(?=\n\s*(?:[•\-\*–—]\s*)?[A-ZÄÖÜ]|\n\n|$)/gi;
        let m;
        while ((m = skillsLineRe.exec(raw)) !== null) {
            const firstLine = m[1].split('\n')[0];
            _splitSkillLine(firstLine.replace(/•/g, ',')).forEach(t => add(t));
        }

        const secRe = /(?:Ihre\s+Qualifikationen|Qualifikationen|Must[- ]?haves?|Anforderungen|Skills\s*\/\s*Tools|Technologien)\s*[:\n]+([\s\S]+?)(?=\n\s*(?:Ihre\s+Aufgaben|Aufgaben|Kurzbeschreibung|Nice[- ]?to[- ]?haves?|Interessiert|Rahmeninformationen|Wir\s+freuen|Ansprechpartner)\b|$)/i;
        const sec = raw.match(secRe);
        if (sec) {
            sec[1].split(/\n/).forEach(line => {
                line = line.trim();
                if (!line || /^(referenz|einsatzort|starttermin|arbeitszeit|dauer|sprachen)\b/i.test(line)) return;
                _splitSkillLine(line).forEach(t => add(t));
            });
        }

        const niceRe = /(?:Nice[- ]?to[- ]?haves?|Wünschenswert|von\s+Vorteil)\s*[:\n]+([\s\S]+?)(?=\n\s*(?:Ihre\s+Aufgaben|Aufgaben|Kurzbeschreibung|Interessiert)\b|$)/i;
        const niceSec = raw.match(niceRe);
        if (niceSec) {
            niceSec[1].split(/\n/).forEach(line => {
                _splitSkillLine(line).forEach(t => add(t, true));
            });
        }

        return {
            skills_required: required.slice(0, 18),
            skills_nice: nice.slice(0, 12),
            skills: required.concat(nice).slice(0, 20),
            required_skills: required.map(name => ({ name: name, weight: 1.0 }))
                .concat(nice.map(name => ({ name: name, weight: 0.55 })))
                .slice(0, 20),
        };
    }

    function fillSkillsFromText(opts) {
        opts = opts || {};
        const cur = (_val('new-skills') || '').trim();
        if (cur && !opts.force) {
            if (!opts.silent) {
                // schon befüllt — nur bei force überschreiben
            }
            return cur.split(/[,;|\n]+/).map(s => s.trim()).filter(Boolean);
        }
        const text = _val('new-description') || '';
        const pack = _extractSkillsFromText(text);
        const names = pack.skills || [];
        if (!names.length) {
            if (!opts.silent) {
                alert(_kiT('skills_from_text_empty', 'Im Anfrage-Text keine Skills/Qualifikationen gefunden.'));
            }
            return [];
        }
        _setVal('new-skills', names.join(', '));
        const sj = document.getElementById('new-skills-json');
        if (sj) sj.value = JSON.stringify(pack.required_skills || names.map(n => ({ name: n, weight: 1.0 })));
        return names;
    }

    function _parseSkillsInput() {
        let fromJson = [];
        try {
            const raw = _val('new-skills-json');
            if (raw) fromJson = JSON.parse(raw);
        } catch (_) {}
        const typed = (_val('new-skills') || '')
            .split(/[,;|\n]+/)
            .map(s => s.trim())
            .filter(Boolean);

        // JSON mit weights, wenn Feldinhalt dazu passt
        if (Array.isArray(fromJson) && fromJson.length) {
            const jsonNames = fromJson.map(s => {
                if (typeof s === 'string') return s.trim();
                return (s && s.name) ? String(s.name).trim() : '';
            }).filter(Boolean);
            const same = typed.length === jsonNames.length
                && typed.every((t, i) => t.toLowerCase() === jsonNames[i].toLowerCase());
            if (same || !typed.length) {
                return fromJson.map(s => {
                    if (typeof s === 'string') return { name: s.trim(), weight: 1.0 };
                    return {
                        name: String((s && s.name) || '').trim(),
                        weight: (s && typeof s.weight === 'number') ? s.weight : 1.0,
                    };
                }).filter(x => x.name);
            }
        }
        // manuell getippt: erste Hälfte / Nicht-Soft = weight 1.0
        return typed.map(name => ({
            name: name,
            weight: _isNiceSkill(name) ? 0.55 : 1.0,
        }));
    }

    function _skillNamesFromParsed(parsed) {
        return (parsed || []).map(s => (typeof s === 'string' ? s : (s && s.name) || '')).filter(Boolean);
    }

    function rematch(projectId) {
        if (!projectId) projectId = window.MATCHING_CONFIG.activeProject;
        if (!projectId) {
            alert(_kiT('rematch_no_project', 'Keine Anfrage gewählt.'));
            return;
        }
        const ok = confirm(
            _kiT(
                'rematch_confirm',
                'Shortlist für diese Anfrage löschen und Matching erneut ausführen?\n'
                + 'Bereits im Workflow-Board weitergeschobene Berater bleiben erhalten.'
            )
        );
        if (!ok) return;

        let skillsHint = (_val('new-skills') || '').trim();
        if (!skillsHint && _kiLastExtract && _kiLastExtract.fields) {
            const sk = _kiLastExtract.fields.skills;
            if (Array.isArray(sk) && sk.length) {
                skillsHint = sk.map(s => (typeof s === 'string' ? s : (s && s.name) || '')).filter(Boolean).join(', ');
            }
        }
        const skillsRaw = window.prompt(
            _kiT(
                'rematch_skills_prompt',
                'Skills für dieses Matching (kommagetrennt).\nLeer = nur Shortlist löschen / vorhandene Skills behalten.\nOhne Skills = oft nutzlose ~70%-Treffer.'
            ),
            skillsHint
        );
        const skills = (skillsRaw == null)
            ? null
            : String(skillsRaw).split(/[,;|\n]+/).map(s => s.trim()).filter(Boolean);

        const headers = { 'X-CSRFToken': csrf(), 'Content-Type': 'application/json' };
        const body = { keep_workflow: true, reset: true };
        if (skills && skills.length) {
            body.skills = skills;
            body.required_skills = skills.map(name => ({ name: name, weight: 1.0 }));
            body.extracted_technologies = skills;
        }

        fetch('/shaduler/api/matching/shortlist/reset/' + encodeURIComponent(projectId) + '/', {
            method: 'POST',
            credentials: 'same-origin',
            headers,
            body: JSON.stringify(body),
        })
        .then(async r => {
            let d = {};
            try { d = await r.json(); } catch (_) {}
            if (!r.ok || d.ok === false) {
                throw new Error((d && d.error) || ('Shortlist-Reset HTTP ' + r.status));
            }
            if (d.warning) console.warn('Shortlist-Reset:', d.warning);
            console.info('Shortlist-Reset:', d);
            return d;
        })
        .then(() => runMatching(projectId, { reset: true }))
        .catch(e => {
            console.error(e);
            alert(_kiT('rematch_reset_fail', 'Shortlist-Reset fehlgeschlagen') + ': ' + (e.message || e));
        });
    }

    function saveNewRequest() {
        const parsed = _parseSkillsInput();
        const skillNames = _skillNamesFromParsed(parsed);
        const data = {
            title:           _val('new-title'),
            description:     _val('new-description'),
            customer_name:   _val('new-customer'),
            contact_name:    _val('new-contact'),
            contact_email:   _val('new-contact-email'),
            contact_phone:   _val('new-contact-phone'),
            crm_account_id:  _val('new-crm-account-id'),
            crm_contact_id:  _val('new-crm-contact-id'),
            start_date:      _val('new-start') || null,
            duration_months: parseInt(_val('new-duration')) || 0,
            location:        _val('new-location'),
            rate_max:        parseInt(_val('new-rate-max')) || null,
            // Matching-Engine: ohne Skills → req_score=1.0 für alle → Mist-Shortlist
            skills:          skillNames,
            required_skills: parsed,
            extracted_technologies: skillNames,
        };
        if (!data.title || !data.customer_name) {
            alert(_t('matching.err_title_required'));
            return;
        }
        if (!skillNames.length) {
            const cont = confirm(
                _kiT(
                    'skills_missing_warn',
                    'Keine Skills gesetzt — Matching liefert dann oft nutzlose Treffer mit ähnlichem Score.\nTrotzdem speichern?'
                )
            );
            if (!cont) {
                document.getElementById('new-skills')?.focus();
                return;
            }
        }
        fetch(API + 'requests/create/', {
            method: 'POST',
            credentials: 'same-origin',
            headers: { 'X-CSRFToken': csrf(), 'Content-Type': 'application/json' },
            body: JSON.stringify(data),
        })
        .then(r => r.json())
        .then(d => {
            if (d.success) {
                const c = document.getElementById('content-anfragen');
                if (c) c.dataset.loaded = '0';
                switchTab('anfragen');
                _loadStats();
            } else {
                alert(_t('matching.save_error') + ': ' + (d.error || ''));
            }
        });
    }

    function updateThreshold(val) {
        const t = val / 100;
        const el = document.getElementById('threshold-val');
        if (el) el.textContent = t.toFixed(2);
        const srcSel = document.getElementById('shortlist-source-filter');
        const src = srcSel ? String(srcSel.value || 'all').toLowerCase() : 'all';

        function _cardSources(card) {
            const primary = String(card.dataset.source || 'db').toLowerCase();
            return String(card.dataset.sources || primary)
                .split(',')
                .map(s => s.trim().toLowerCase())
                .filter(Boolean);
        }
        function _srcOk(card) {
            if (src === 'all') return true;
            const allSrc = _cardSources(card);
            const primary = String(card.dataset.source || 'db').toLowerCase();
            return allSrc.indexOf(src) >= 0 || primary === src;
        }

        const root = document.getElementById('shortlist-results');
        let above = 0;
        if (root) {
            const cards = [...root.querySelectorAll('.matching-card[data-score]')];
            cards.forEach(card => {
                const srcOk = _srcOk(card);
                card.style.display = srcOk ? '' : 'none';
                if (srcOk) {
                    const score = parseFloat(card.dataset.score);
                    card.style.opacity = score >= t ? '1' : '0.4';
                    if (score >= t) above += 1;
                }
            });
            const visible = cards.filter(c => c.style.display !== 'none');
            visible.sort((a, b) => {
                const ds = parseFloat(b.dataset.score) - parseFloat(a.dataset.score);
                if (Math.abs(ds) > 1e-9) return ds;
                return parseFloat(b.dataset.strength || 0) - parseFloat(a.dataset.strength || 0);
            });
            const frag = document.createDocumentFragment();
            visible.forEach(c => frag.appendChild(c));
            cards.filter(c => c.style.display === 'none').forEach(c => frag.appendChild(c));
            root.appendChild(frag);
        }

        // Backoffice mitfiltern (Gulp/FLM Treffer)
        const boRoot = document.getElementById('shortlist-backoffice');
        const boWrap = document.getElementById('shortlist-backoffice-wrap');
        let boVisible = 0;
        if (boRoot) {
            const boCards = [...boRoot.querySelectorAll('.matching-card')];
            boCards.forEach(card => {
                const ok = _srcOk(card);
                card.style.display = ok ? '' : 'none';
                if (ok) boVisible += 1;
            });
            if (boWrap) {
                // Bei Quelle=DB Backoffice ausblenden; bei Gulp/FLM/Alle zeigen wenn Treffer
                const showBo = (src === 'all' || src === 'gulp' || src === 'flm') && boVisible > 0;
                boWrap.style.display = showBo ? '' : 'none';
            }
            const boCnt = document.getElementById('shortlist-backoffice-count');
            if (boCnt) boCnt.textContent = String(boVisible);
        }

        const cnt = document.getElementById('threshold-count');
        if (cnt) cnt.textContent = above + ' ' + _t('matching.above_threshold_full');
        const sendBtn = document.querySelector('.matching-threshold-bar .matching-btn-primary');
        if (sendBtn) {
            sendBtn.textContent = _t('matching.btn_send_all_count') + ' (' + above + ') ↗';
        }
    }

    function filterShortlistSource(src) {
        const srcSel = document.getElementById('shortlist-source-filter');
        if (srcSel && src != null && src !== '') {
            srcSel.value = src;
        }
        const slider = document.getElementById('threshold-slider');
        const val = slider ? slider.value : '45';
        updateThreshold(val);
    }

    function sendAllAboveThreshold() {
        openOutreachWizard();
    }

    // ── Outreach-Wizard („Alle anschreiben“) ───────────────────────────────
    function _outreachCandidates() {
        const cache = window._matchingShortlistCache || {};
        const slider = document.getElementById('threshold-slider');
        const t = slider ? (parseFloat(slider.value) / 100) : (cache.threshold || 0.45);
        const fromDom = [...document.querySelectorAll('#shortlist-results .matching-card[data-score]')]
            .filter(c => c.style.display !== 'none' && parseFloat(c.dataset.score) >= t)
            .map(c => {
                const id = c.dataset.id;
                const hit = (cache.results || []).find(r => r.id === id) || {};
                return {
                    id: id,
                    name: hit.name || (c.querySelector('div[style*="font-weight:700"]') || {}).textContent || id,
                    score: parseFloat(c.dataset.score),
                    email: hit.email || '',
                    match_source: hit.match_source || c.dataset.source || 'db',
                    matched_skills: hit.matched_skills || [],
                    match_reason: hit.match_reason || '',
                    consultant_id: hit.consultant_id || '',
                    project_consultant_id: hit.project_consultant_id || null,
                    cv_editor_url: hit.cv_editor_url || '',
                };
            });
        if (fromDom.length) return { threshold: t, list: fromDom, projectId: cache.projectId };
        const list = (cache.results || [])
            .filter(r => (r.overall_score || 0) >= t)
            .map(r => ({
                id: r.id,
                name: r.name,
                score: r.overall_score,
                email: r.email || '',
                matched_skills: r.matched_skills || [],
                match_reason: r.match_reason || '',
                consultant_id: r.consultant_id || '',
                project_consultant_id: r.project_consultant_id || null,
                cv_editor_url: r.cv_editor_url || '',
            }));
        return { threshold: t, list, projectId: cache.projectId };
    }

    function openOutreachWizard() {
        const pack = _outreachCandidates();
        if (!pack.list.length) {
            alert(_kiT('outreach_none', 'Keine Berater oberhalb des Schwellwerts.'));
            return;
        }
        window._outreachWizard = {
            projectId: pack.projectId || (window.MATCHING_CONFIG && window.MATCHING_CONFIG.activeProject) || null,
            queue: pack.list,
            index: 0,
            skipped: [],
            sent: [],
            deep: null,
            draft: null,
            emails: [],           // CRM-Vorschläge [{email, primary, …}]
            selectedEmail: '',   // aktuell gewählte / übernommene An-Adresse
            ccList: [],          // mehrere, Semikolon-getrennt
            bccList: ['send@abcona.de'],
            mailTarget: 'to',    // to | cc | bcc für kompakte Suche
            crm_contact_id: '',
            loading: false,
            _searchTimers: {},
        };
        _renderOutreachWizard();
        _outreachLoadCurrent();
    }

    function _outreachParseEmails(raw) {
        return String(raw || '')
            .split(/[;,\n]+/)
            .map(s => s.trim())
            .filter(s => s && s.indexOf('@') >= 0);
    }

    function _outreachJoinEmails(list) {
        return (list || []).filter(Boolean).join('; ');
    }

    function _outreachAddEmails(list, addrs) {
        const out = (list || []).slice();
        const seen = {};
        out.forEach(e => { seen[String(e).toLowerCase()] = true; });
        (addrs || []).forEach(a => {
            const e = String(a || '').trim();
            if (!e || e.indexOf('@') < 0) return;
            const k = e.toLowerCase();
            if (seen[k]) return;
            seen[k] = true;
            out.push(e);
        });
        return out;
    }


    /** Shaduler Art-Defaults (gleicher Key wie Regeln-Tab). */
    var _OW_ART_DEFAULTS_BASE = {
        anruf: { weeks: 0, days: 0, hours: 1, minutes: 0, enabled: true },
        sms_messenger: { weeks: 0, days: 0, hours: 1, minutes: 0, enabled: true },
        wiedervorlage: { weeks: 0, days: 1, hours: 0, minutes: 0, enabled: true },
        email: { weeks: 0, days: 0, hours: 2, minutes: 0, enabled: true },
        post: { weeks: 0, days: 2, hours: 0, minutes: 0, enabled: true },
        termin: { weeks: 0, days: 0, hours: 0, minutes: 0, enabled: false },
        dokument: { weeks: 0, days: 1, hours: 0, minutes: 0, enabled: true },
        intern: { weeks: 0, days: 1, hours: 0, minutes: 0, enabled: true },
    };

    function _owNzInt(v, fallback) {
        var n = parseInt(v, 10);
        return isNaN(n) || n < 0 ? (fallback || 0) : n;
    }

    function _owMigrateArtDefault(raw) {
        if (!raw || typeof raw !== 'object') {
            return { weeks: 0, days: 0, hours: 0, minutes: 0, enabled: false };
        }
        if (raw.weeks != null || raw.hours != null || raw.minutes != null || raw.enabled === false || raw.enabled === true) {
            var weeks = _owNzInt(raw.weeks, 0);
            var days = _owNzInt(raw.days, 0);
            var hours = _owNzInt(raw.hours, 0);
            var minutes = _owNzInt(raw.minutes, 0);
            var enabled = raw.enabled !== false && (weeks + days + hours + minutes > 0 || raw.enabled === true);
            if (raw.enabled === false) enabled = false;
            return { weeks: weeks, days: days, hours: hours, minutes: minutes, enabled: enabled };
        }
        var legDays = raw.days != null && raw.days !== '' ? _owNzInt(raw.days, 0) : 0;
        var dur = raw.dauer_min != null && raw.dauer_min !== '' ? _owNzInt(raw.dauer_min, 0) : 0;
        if (raw.days == null && raw.dauer_min == null) {
            return { weeks: 0, days: 0, hours: 0, minutes: 0, enabled: false };
        }
        return {
            weeks: 0,
            days: (raw.days != null && raw.days !== '') ? legDays : 0,
            hours: Math.floor(dur / 60),
            minutes: dur % 60,
            enabled: !!(dur || (raw.days != null && raw.days !== '')),
        };
    }

    function _owGetArtDefaults(art) {
        if (window.Shaduler && typeof window.Shaduler.getArtDefaults === 'function') {
            try { return window.Shaduler.getArtDefaults(art); } catch (e) { /* fall through */ }
        }
        var base = _owMigrateArtDefault(_OW_ART_DEFAULTS_BASE[art]);
        try {
            var raw = localStorage.getItem('sh_task_art_defaults_v2');
            if (!raw) {
                var old = localStorage.getItem('sh_task_art_defaults');
                if (!old) return base;
                var o1 = JSON.parse(old);
                if (o1 && o1[art]) return _owMigrateArtDefault(o1[art]);
                return base;
            }
            var o = JSON.parse(raw);
            if (o && o[art]) return _owMigrateArtDefault(o[art]);
        } catch (e2) { /* ignore */ }
        return base;
    }

    function _owDueFromArt(art) {
        if (window.Shaduler && typeof window.Shaduler.dueDateTimeFromArt === 'function') {
            try {
                var fromSh = window.Shaduler.dueDateTimeFromArt(art);
                if (fromSh) return fromSh;
            } catch (e) { /* fall through */ }
        }
        var def = _owGetArtDefaults(art);
        if (!def || !def.enabled) return null;
        var weeks = _owNzInt(def.weeks, 0);
        var days = _owNzInt(def.days, 0);
        var hours = _owNzInt(def.hours, 0);
        var minutes = _owNzInt(def.minutes, 0);
        if (weeks + days + hours + minutes === 0) return null;
        var d = new Date();
        d.setDate(d.getDate() + weeks * 7 + days);
        d.setHours(d.getHours() + hours);
        d.setMinutes(d.getMinutes() + minutes, 0, 0);
        return {
            date: d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0'),
            time: String(d.getHours()).padStart(2, '0') + ':' + String(d.getMinutes()).padStart(2, '0'),
            def: def,
        };
    }

    function _owWvDueLabel() {
        var def = _owGetArtDefaults('wiedervorlage');
        if (!def || !def.enabled) return '';
        var parts = [];
        if (def.weeks) parts.push(def.weeks + 'W');
        if (def.days) parts.push(def.days + 'T');
        if (def.hours) parts.push(def.hours + 'h');
        if (def.minutes) parts.push(def.minutes + 'm');
        return parts.length ? (' (' + parts.join(' ') + ')') : '';
    }

    function _outreachCaptureForm(st) {
        if (!st) return;
        const to = ((document.getElementById('ow-to') || {}).value || '').trim();
        if (to) st.selectedEmail = to;
        const subj = ((document.getElementById('ow-subj') || {}).value || '');
        const body = ((document.getElementById('ow-body') || {}).value || '');
        const task = document.getElementById('ow-task');
        if (st.draft) {
            if (to) st.draft.to_email = to;
            if (document.getElementById('ow-subj')) st.draft.subject = subj;
            if (document.getElementById('ow-body')) st.draft.body = body;
        }
        if (task) st._taskChecked = !!task.checked;
        var td = document.getElementById('ow-task-date');
        var tt = document.getElementById('ow-task-time');
        if (td) st._taskDate = td.value || '';
        if (tt) st._taskTime = tt.value || '';
        // CC/BCC hidden fields spiegeln Listen
        const ccEl = document.getElementById('ow-cc');
        const bccEl = document.getElementById('ow-bcc');
        if (ccEl) st.ccList = _outreachParseEmails(ccEl.value);
        if (bccEl) st.bccList = _outreachParseEmails(bccEl.value);
    }

    function _outreachEmailList(st, cur, draft) {
        const seen = {};
        const out = [];
        function push(em, primary, src) {
            const e = String(em || '').trim();
            if (!e || e.indexOf('@') < 0) return;
            const key = e.toLowerCase();
            if (seen[key]) {
                if (primary) seen[key].primary = true;
                return;
            }
            const row = { email: e, primary: !!primary, src: src || '' };
            seen[key] = row;
            out.push(row);
        }
        (st.emails || []).forEach(em => {
            if (typeof em === 'string') push(em, false, 'crm');
            else push(em.email || em.value, !!(em && em.primary), 'crm');
        });
        push(draft && draft.to_email, false, 'draft');
        push(cur && cur.email, false, 'aid');
        push(st.selectedEmail, false, 'selected');
        out.sort((a, b) => (b.primary ? 1 : 0) - (a.primary ? 1 : 0));
        return out;
    }

    function _outreachChipsHtml(kind, list, allowEmpty) {
        const items = list || [];
        if (!items.length) {
            return allowEmpty
                ? '<span style="color:#aaa;font-size:11px">—</span>'
                : '';
        }
        return items.map((em, i) =>
            `<span style="display:inline-flex;align-items:center;gap:3px;background:#e8eef7;border-radius:4px;padding:1px 6px;font-size:11px;margin:1px 2px">
               ${_esc(em)}
               <button type="button" style="border:0;background:transparent;cursor:pointer;color:#666;padding:0;line-height:1;font-size:14px"
                       onclick="Matching.outreachRemoveMulti('${kind}',${i})" title="entfernen">×</button>
             </span>`
        ).join('');
    }

    function _outreachEmailBlockHtml(st, cur, draft) {
        const emails = _outreachEmailList(st, cur, draft);
        const current = st.selectedEmail
            || (draft && draft.to_email)
            || (cur && cur.email)
            || _pickEmail(emails, '')
            || '';
        const ccList = Array.isArray(st.ccList) ? st.ccList : [];
        const bccList = Array.isArray(st.bccList) && st.bccList.length
            ? st.bccList
            : ['send@abcona.de'];
        const target = st.mailTarget || 'to';
        // Kompakte An-Vorschläge (nur wenn vorhanden)
        const toSuggest = emails.length
            ? `<div style="display:flex;flex-wrap:wrap;gap:4px;margin-bottom:6px">` +
              emails.slice(0, 6).map(em => {
                  const on = (em.email || '').toLowerCase() === (current || '').toLowerCase();
                  const tag = em.primary ? 'Primär' : (em.src === 'crm' ? 'CRM' : '');
                  return `<button type="button" class="matching-btn-sm"
                            style="font-size:10px;padding:2px 7px;${on ? 'background:#fff8c5;border-color:#e6c200' : ''}"
                            onclick="Matching.outreachPickEmail('${_escAttr(em.email).replace(/'/g, "\\'")}')">
                            ${_esc(em.email)}${tag ? ' · ' + _esc(tag) : ''}
                          </button>`;
              }).join('') + `</div>`
            : '';
        return `
              <div style="font-size:11px;color:#666;border:1px solid #e5e7eb;border-radius:8px;padding:8px;background:#fafbfc">
                <div style="display:flex;gap:6px;align-items:center;flex-wrap:wrap;margin-bottom:6px">
                  <select id="ow-mail-target" class="matching-form-input" style="width:auto;min-width:72px"
                          onchange="Matching.outreachSetMailTarget(this.value)">
                    <option value="to" ${target === 'to' ? 'selected' : ''}>An</option>
                    <option value="cc" ${target === 'cc' ? 'selected' : ''}>CC</option>
                    <option value="bcc" ${target === 'bcc' ? 'selected' : ''}>BCC</option>
                  </select>
                  <input id="ow-mail-q" class="matching-form-input" type="text"
                         placeholder="Suche Name/E-Mail oder manuell a@x.de; b@y.de"
                         style="flex:1;min-width:200px"
                         oninput="Matching.outreachUnifiedSearch(this.value)"
                         onkeydown="if(event.key==='Enter'){event.preventDefault();Matching.outreachUnifiedApply();}">
                  <button type="button" class="matching-btn-sm" onclick="Matching.outreachUnifiedApply()">
                    ${_esc(_kiT('outreach_apply_email', 'Übernehmen'))}
                  </button>
                </div>
                <div id="ow-mail-hits" style="display:none;border:1px solid #e5e7eb;border-radius:6px;background:#fff;max-height:130px;overflow:auto;margin-bottom:6px"></div>
                ${toSuggest}
                <div style="display:grid;gap:4px;font-size:11px">
                  <div><b style="display:inline-block;min-width:36px">An</b>
                    <input id="ow-to" type="hidden" value="${_escAttr(current)}">
                    <span id="ow-to-chip">${current
                      ? `<span style="background:#fff8c5;border-radius:4px;padding:1px 6px;font-weight:600">${_esc(current)}</span>`
                      : '<span style="color:#b45309">keine Adresse</span>'}</span>
                    ${st.crm_contact_id
                      ? ` <a href="/crm/berater/?detail=${_escAttr(st.crm_contact_id)}" target="_blank" style="font-size:10px;color:#888">CRM</a>`
                      : ''}
                  </div>
                  <div><b style="display:inline-block;min-width:36px">CC</b>
                    <input type="hidden" id="ow-cc" value="${_escAttr(_outreachJoinEmails(ccList))}">
                    <span id="ow-cc-chips">${_outreachChipsHtml('cc', ccList, true)}</span>
                  </div>
                  <div><b style="display:inline-block;min-width:36px">BCC</b>
                    <input type="hidden" id="ow-bcc" value="${_escAttr(_outreachJoinEmails(bccList))}">
                    <span id="ow-bcc-chips">${_outreachChipsHtml('bcc', bccList, true)}</span>
                  </div>
                </div>
              </div>`;
    }

    function outreachSetMailTarget(v) {
        const st = window._outreachWizard;
        if (!st) return;
        st.mailTarget = (v === 'cc' || v === 'bcc') ? v : 'to';
    }

    function outreachPickEmail(addr) {
        const st = window._outreachWizard;
        if (!st) return;
        _outreachCaptureForm(st);
        st.selectedEmail = String(addr || '').trim();
        if (st.draft) st.draft.to_email = st.selectedEmail;
        st.mailTarget = st.mailTarget || 'to';
        _renderOutreachWizard();
        const t = document.getElementById('ow-task');
        if (t && st._taskChecked != null) t.checked = st._taskChecked;
    }

    function outreachApplyEmail() {
        outreachUnifiedApply();
    }

    function outreachUnifiedApply() {
        const st = window._outreachWizard;
        if (!st) return;
        _outreachCaptureForm(st);
        const target = ((document.getElementById('ow-mail-target') || {}).value) || st.mailTarget || 'to';
        st.mailTarget = target;
        const raw = ((document.getElementById('ow-mail-q') || {}).value || '').trim();
        const addrs = _outreachParseEmails(raw);
        // Wenn nur Text ohne @ → Suche erzwingen, kein Apply-Fehler
        if (!addrs.length) {
            if (raw.length >= 2 && raw.indexOf('@') < 0) {
                outreachUnifiedSearch(raw);
                const status = document.getElementById('ow-status');
                if (status) {
                    status.style.color = '#666';
                    status.textContent = 'Treffer wählen oder E-Mail mit @ / ; eintragen';
                }
                return;
            }
            const status = document.getElementById('ow-status');
            if (status) {
                status.style.color = '#b91c1c';
                status.textContent = 'Keine gültige E-Mail (mit ; trennen)';
            }
            return;
        }
        if (target === 'to') {
            st.selectedEmail = addrs[0];
            if (st.draft) st.draft.to_email = addrs[0];
            // Rest optional nach CC
            if (addrs.length > 1) {
                st.ccList = _outreachAddEmails(st.ccList || [], addrs.slice(1));
            }
        } else if (target === 'cc') {
            st.ccList = _outreachAddEmails(st.ccList || [], addrs);
        } else {
            st.bccList = _outreachAddEmails(st.bccList || [], addrs);
        }
        _renderOutreachWizard();
        const t = document.getElementById('ow-task');
        if (t && st._taskChecked != null) t.checked = st._taskChecked;
        const qEl = document.getElementById('ow-mail-q');
        if (qEl) qEl.value = '';
        const hits = document.getElementById('ow-mail-hits');
        if (hits) { hits.style.display = 'none'; hits.innerHTML = ''; }
        const status = document.getElementById('ow-status');
        if (status) {
            status.style.color = '#155724';
            status.textContent = target.toUpperCase() + ': ' + addrs.join('; ');
        }
    }

    function outreachApplyMulti(kind) {
        const st = window._outreachWizard;
        if (!st) return;
        st.mailTarget = kind;
        const sel = document.getElementById('ow-mail-target');
        if (sel) sel.value = kind;
        outreachUnifiedApply();
    }

    function outreachRemoveMulti(kind, idx) {
        const st = window._outreachWizard;
        if (!st || (kind !== 'cc' && kind !== 'bcc' && kind !== 'to')) return;
        _outreachCaptureForm(st);
        if (kind === 'to') {
            st.selectedEmail = '';
            if (st.draft) st.draft.to_email = '';
        } else {
            const key = kind + 'List';
            const list = (st[key] || []).slice();
            if (idx < 0 || idx >= list.length) return;
            list.splice(idx, 1);
            if (kind === 'bcc' && !list.length) list.push('send@abcona.de');
            st[key] = list;
        }
        _renderOutreachWizard();
        const t = document.getElementById('ow-task');
        if (t && st._taskChecked != null) t.checked = st._taskChecked;
    }

    function outreachAddMultiEmail(kind, email) {
        const st = window._outreachWizard;
        if (!st) return;
        _outreachCaptureForm(st);
        const e = String(email || '').trim();
        if (!e || e.indexOf('@') < 0) return;
        if (kind === 'to') {
            st.selectedEmail = e;
            if (st.draft) st.draft.to_email = e;
        } else if (kind === 'cc') {
            st.ccList = _outreachAddEmails(st.ccList || [], [e]);
        } else if (kind === 'bcc') {
            st.bccList = _outreachAddEmails(st.bccList || [], [e]);
        }
        _renderOutreachWizard();
        const t = document.getElementById('ow-task');
        if (t && st._taskChecked != null) t.checked = st._taskChecked;
        const hits = document.getElementById('ow-mail-hits');
        if (hits) { hits.style.display = 'none'; hits.innerHTML = ''; }
        const qEl = document.getElementById('ow-mail-q');
        if (qEl) qEl.value = '';
    }

    function _outreachRenderHits(items) {
        const hitsEl = document.getElementById('ow-mail-hits');
        const st = window._outreachWizard;
        if (!hitsEl || !st) return;
        const target = ((document.getElementById('ow-mail-target') || {}).value) || st.mailTarget || 'to';
        if (!items.length) {
            hitsEl.style.display = 'block';
            hitsEl.innerHTML = '<div style="padding:6px 8px;font-size:11px;color:#888">Keine Treffer</div>';
            return;
        }
        hitsEl.style.display = 'block';
        hitsEl.innerHTML = items.slice(0, 12).map(it => {
            const em = _escAttr(it.email).replace(/'/g, "\\'");
            return `<div style="padding:5px 8px;font-size:11px;cursor:pointer;border-bottom:1px solid #f0f0f0"
                      onmouseover="this.style.background='#f0f4fa'" onmouseout="this.style.background=''"
                      onclick="Matching.outreachAddMultiEmail('${target}','${em}')">
                   <b>${_esc(it.email)}</b>
                   <span style="color:#888"> · ${_esc(it.name || '')}${it.company ? ' · ' + _esc(it.company) : ''}</span>
                 </div>`;
        }).join('');
    }

    function _outreachNormalizeSuggestRows(rows) {
        const items = [];
        (rows || []).forEach(r => {
            const name = r.name || r.full_name || [r.first_name, r.last_name].filter(Boolean).join(' ') || '';
            const company = r.company || r.account_name || '';
            let emails = r.emails || [];
            if (typeof emails === 'string') emails = _outreachParseEmails(emails);
            if (!Array.isArray(emails)) emails = [];
            if (!emails.length && r.email) emails = [r.email];
            emails.forEach(em => {
                const e = typeof em === 'string' ? em : (em.email || em.value || '');
                if (!e || e.indexOf('@') < 0) return;
                items.push({ email: e, name: name, company: company, crm_id: r.crm_id || '' });
            });
        });
        return items;
    }

    function outreachUnifiedSearch(q) {
        const st = window._outreachWizard;
        if (!st) return;
        const hitsEl = document.getElementById('ow-mail-hits');
        if (!hitsEl) return;
        const query = String(q || '').trim();
        if (st._searchTimers.unified) clearTimeout(st._searchTimers.unified);
        // Reine E-Mail-Eingabe → keine Suche nötig
        if (query.indexOf('@') >= 0 && _outreachParseEmails(query).length) {
            hitsEl.style.display = 'none';
            hitsEl.innerHTML = '';
            return;
        }
        if (query.length < 2) {
            hitsEl.style.display = 'none';
            hitsEl.innerHTML = '';
            return;
        }
        st._searchTimers.unified = setTimeout(() => {
            hitsEl.style.display = 'block';
            hitsEl.innerHTML = '<div style="padding:6px 8px;font-size:11px;color:#888">Suche…</div>';
            const headers = { 'X-Requested-With': 'XMLHttpRequest' };
            const suggestUrl = '/crm/api/contacts/suggest/?q=' + encodeURIComponent(query) + '&limit=8';
            const beraterUrl = '/crm/api/berater/?q=' + encodeURIComponent(query) + '&per_page=8&typ=alle';

            Promise.all([
                fetch(suggestUrl, { credentials: 'same-origin', headers })
                    .then(r => r.ok ? r.json() : null).catch(() => null),
                fetch(beraterUrl, { credentials: 'same-origin', headers })
                    .then(r => r.ok ? r.json() : null).catch(() => null),
            ]).then(async ([sug, ber]) => {
                let items = _outreachNormalizeSuggestRows((sug && (sug.results || sug.items)) || []);
                // Berater-Fallback / Ergänzung — Detail für E-Mails nachladen wenn nötig
                const berRows = (ber && (ber.results || ber.items || ber.berater)) || [];
                const needDetail = [];
                berRows.forEach(r => {
                    const name = r.full_name || r.name || '';
                    const emails = r.emails || (r.email ? [r.email] : []);
                    if (emails.length) {
                        items = items.concat(_outreachNormalizeSuggestRows([r]));
                    } else if (r.crm_id) {
                        needDetail.push({ crm_id: r.crm_id, name: name, company: r.company || '' });
                    }
                });
                if (needDetail.length && items.length < 6) {
                    const details = await Promise.all(
                        needDetail.slice(0, 5).map(d =>
                            fetch('/crm/api/berater/' + encodeURIComponent(d.crm_id) + '/', {
                                credentials: 'same-origin', headers,
                            }).then(r => r.ok ? r.json() : null)
                              .then(j => j ? Object.assign({ name: d.name, company: d.company }, j) : null)
                              .catch(() => null)
                        )
                    );
                    items = items.concat(_outreachNormalizeSuggestRows(details.filter(Boolean)));
                }
                // Dedup by email
                const seen = {};
                items = items.filter(it => {
                    const k = (it.email || '').toLowerCase();
                    if (!k || seen[k]) return false;
                    seen[k] = true;
                    return true;
                });
                _outreachRenderHits(items);
            });
        }, 280);
    }

    function outreachSearchMulti(kind, q) {
        // Kompatibilität: leitet auf Unified um
        const st = window._outreachWizard;
        if (st) st.mailTarget = kind;
        const sel = document.getElementById('ow-mail-target');
        if (sel) sel.value = kind;
        outreachUnifiedSearch(q);
    }

    function closeOutreachWizard() {
        document.getElementById('matching-outreach-ovl')?.remove();
        window._outreachWizard = null;
        window._outreachDrag = null;
    }

    function _outreachEnableDrag(ov, st) {
        const panel = ov.querySelector('#ow-panel');
        const bar = ov.querySelector('#ow-drag-bar');
        if (!panel || !bar) return;

        // Gespeicherte Position wiederherstellen
        if (st.dragPos && typeof st.dragPos.left === 'number') {
            ov.style.alignItems = 'flex-start';
            ov.style.justifyContent = 'flex-start';
            panel.style.position = 'relative';
            panel.style.left = st.dragPos.left + 'px';
            panel.style.top = st.dragPos.top + 'px';
            panel.style.margin = '0';
        }

        bar.onmousedown = function (e) {
            if (e.button !== 0) return;
            if (e.target && e.target.closest && e.target.closest('button')) return;
            e.preventDefault();
            const rect = panel.getBoundingClientRect();
            const startX = e.clientX;
            const startY = e.clientY;
            const origLeft = rect.left;
            const origTop = rect.top;
            // Von Flex-Zentrierung auf absolute Position umschalten
            ov.style.alignItems = 'flex-start';
            ov.style.justifyContent = 'flex-start';
            panel.style.position = 'relative';
            panel.style.left = origLeft + 'px';
            panel.style.top = origTop + 'px';
            panel.style.margin = '0';
            bar.style.cursor = 'grabbing';
            window._outreachDrag = { startX, startY, origLeft, origTop, panel, bar, ov };

            function onMove(ev) {
                const d = window._outreachDrag;
                if (!d) return;
                const dx = ev.clientX - d.startX;
                const dy = ev.clientY - d.startY;
                let left = d.origLeft + dx;
                let top = d.origTop + dy;
                // Viewport-Grenzen (wenigstens 40px Header sichtbar)
                const maxL = window.innerWidth - 80;
                const maxT = window.innerHeight - 40;
                left = Math.max(-rect.width + 80, Math.min(maxL, left));
                top = Math.max(0, Math.min(maxT, top));
                d.panel.style.left = left + 'px';
                d.panel.style.top = top + 'px';
                if (window._outreachWizard) {
                    window._outreachWizard.dragPos = { left: left, top: top };
                }
            }
            function onUp() {
                const d = window._outreachDrag;
                if (d && d.bar) d.bar.style.cursor = 'move';
                window._outreachDrag = null;
                document.removeEventListener('mousemove', onMove);
                document.removeEventListener('mouseup', onUp);
            }
            document.addEventListener('mousemove', onMove);
            document.addEventListener('mouseup', onUp);
        };
    }

    function _renderOutreachWizard() {
        const st = window._outreachWizard;
        if (!st) return;
        let ov = document.getElementById('matching-outreach-ovl');
        if (!ov) {
            ov = document.createElement('div');
            ov.id = 'matching-outreach-ovl';
            ov.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,.45);z-index:10070;display:flex;align-items:center;justify-content:center;padding:12px';
            ov.onclick = function (e) {
                if (window._outreachDrag) return;
                if (e.target === ov) closeOutreachWizard();
            };
            document.body.appendChild(ov);
        }
        const cur = st.queue[st.index];
        const n = st.queue.length;
        const i = st.index + 1;
        const deep = st.deep || {};
        const draft = st.draft || {};
        const listHtml = st.queue.map((c, idx) => {
            let mark = idx === st.index ? '▶' : (st.sent.includes(c.id) ? '✓' : (st.skipped.includes(c.id) ? '–' : '·'));
            const dim = idx < st.index || st.skipped.includes(c.id) ? 'opacity:.45' : '';
            return `<div style="padding:4px 6px;font-size:11px;cursor:pointer;border-radius:4px;${dim}${idx === st.index ? 'background:#e8eef7;font-weight:700' : ''}"
                        onclick="Matching.outreachGoto(${idx})">${mark} ${_esc(c.name)} · ${Math.round((c.score || 0) * 100)}%</div>`;
        }).join('');

        ov.innerHTML = `
        <div id="ow-panel" style="background:#fff;border-radius:10px;width:min(960px,96vw);max-height:92vh;overflow:hidden;display:flex;flex-direction:column;box-shadow:0 12px 40px rgba(0,0,0,.25)">
          <div id="ow-drag-bar" style="display:flex;align-items:center;gap:8px;padding:12px 14px;background:var(--abcona-blue,#163258);color:#fff;cursor:move;user-select:none;touch-action:none">
            <i class="bi bi-send"></i>
            <b style="flex:1">${_esc(_kiT('outreach_title', 'Outreach-Wizard'))} — ${i}/${n}</b>
            <button type="button" style="background:transparent;border:0;color:#fff;font-size:18px;cursor:pointer"
                    onclick="Matching.closeOutreachWizard()">×</button>
          </div>
          <div style="display:grid;grid-template-columns:220px 1fr;min-height:0;flex:1;overflow:hidden">
            <div style="border-right:1px solid #e5e7eb;overflow:auto;padding:8px;background:#fafbfc">${listHtml}</div>
            <div style="overflow:auto;padding:14px;display:grid;gap:10px">
              ${!cur ? '<p>Fertig.</p>' : `
              <div style="display:flex;align-items:baseline;gap:10px;flex-wrap:wrap">
                <div style="font-size:16px;font-weight:700">${_esc(cur.name)}</div>
                <div style="font-size:12px;color:#666">${Math.round((cur.score || 0) * 100)}% · ${_esc((cur.matched_skills || []).slice(0, 5).join(' · '))}</div>
                ${cur.cv_editor_url ? `<a href="${_escAttr(cur.cv_editor_url)}" target="_blank" class="matching-btn-sm">CV</a>` : ''}
              </div>
              <div id="ow-status" style="font-size:11px;color:#666;min-height:16px">${st.loading ? 'DeepSeek lädt …' : ''}</div>
              <div style="background:#f5f7fa;border-radius:8px;padding:10px">
                <div style="font-size:11px;font-weight:700;color:#163258;margin-bottom:4px">${_esc(_kiT('outreach_why', 'Warum anschreiben'))}</div>
                <div id="ow-why" style="font-size:12px;line-height:1.45">${_esc(deep.why || cur.match_reason || '…')}</div>
                <div style="margin-top:6px;font-size:11px;color:#666">
                  Interesse: <b>${_esc(deep.interest || '—')}</b>
                  · Antwortchance: <b>${deep.reply_likelihood != null ? Math.round(deep.reply_likelihood * 100) + '%' : '—'}</b>
                </div>
              </div>
              ${_outreachEmailBlockHtml(st, cur, draft)}
              <label style="font-size:11px;color:#666">Betreff
                <input id="ow-subj" class="matching-form-input" style="width:100%;margin-top:3px"
                       value="${_escAttr(draft.subject || '')}">
              </label>
              <label style="font-size:11px;color:#666">Anschreiben
                <textarea id="ow-body" class="matching-form-textarea" rows="9"
                          style="width:100%;margin-top:3px;font-family:inherit">${_esc(draft.body || draft.body_text || '')}</textarea>
              </label>
              <div id="ow-task-box" style="display:grid;gap:6px;padding:8px 10px;background:#f8fafc;border-radius:8px;border:1px solid #e5e7eb">
                <label style="font-size:11px;color:#666;display:flex;align-items:center;gap:8px">
                  <input type="checkbox" id="ow-task" checked>
                  ${_esc(_kiT('outreach_task', 'Wiedervorlage anlegen'))}<span id="ow-task-def-hint" style="color:#94a3b8"></span>
                </label>
                <div id="ow-task-fields" style="display:flex;flex-wrap:wrap;gap:10px;align-items:end">
                  <label style="font-size:11px;color:#666">Fällig
                    <input type="date" id="ow-task-date" class="matching-form-input" style="display:block;margin-top:3px;min-width:140px">
                  </label>
                  <label style="font-size:11px;color:#666">Uhrzeit
                    <input type="time" id="ow-task-time" class="matching-form-input" style="display:block;margin-top:3px;min-width:100px">
                  </label>
                </div>
              </div>
              <div style="display:flex;gap:8px;justify-content:flex-end;flex-wrap:wrap">
                <button type="button" class="matching-btn-sm" onclick="Matching.outreachSkip()">${_esc(_kiT('outreach_skip', 'Aussortieren'))}</button>
                <button type="button" class="matching-btn-sm" onclick="Matching.outreachPolish()">${_esc(_kiT('outreach_polish', 'Glätten'))}</button>
                <button type="button" class="matching-btn-sm" onclick="Matching.outreachReloadDraft()">${_esc(_kiT('outreach_redraft', 'Neu entwerfen'))}</button>
                <button type="button" class="matching-btn-primary" id="ow-send" onclick="Matching.outreachSend()">
                  <i class="bi bi-send"></i> ${_esc(_kiT('outreach_send_next', 'Senden & Weiter'))}
                </button>
              </div>`}
            </div>
          </div>
        </div>`;
        _outreachEnableDrag(ov, st);
        if (st._taskChecked != null) {
            const t = document.getElementById('ow-task');
            if (t) t.checked = st._taskChecked;
        }
        (function _fillOwTaskDue() {
            const dateEl = document.getElementById('ow-task-date');
            const timeEl = document.getElementById('ow-task-time');
            const hint = document.getElementById('ow-task-def-hint');
            const taskCb = document.getElementById('ow-task');
            const fields = document.getElementById('ow-task-fields');
            if (hint) hint.textContent = _owWvDueLabel();
            const due = _owDueFromArt('wiedervorlage');
            if (dateEl) {
                dateEl.value = st._taskDate || (due && due.date) || '';
            }
            if (timeEl) {
                timeEl.value = st._taskTime || (due && due.time) || '';
            }
            function syncFields() {
                if (fields) fields.style.opacity = (taskCb && !taskCb.checked) ? '0.45' : '1';
                if (dateEl) dateEl.disabled = !!(taskCb && !taskCb.checked);
                if (timeEl) timeEl.disabled = !!(taskCb && !taskCb.checked);
            }
            if (taskCb && !taskCb._owBound) {
                taskCb._owBound = true;
                taskCb.addEventListener('change', syncFields);
            }
            syncFields();
        })();
    }

    function outreachGoto(idx) {
        const st = window._outreachWizard;
        if (!st || st.loading) return;
        if (idx < 0 || idx >= st.queue.length) return;
        st.index = idx;
        st.deep = null;
        st.draft = null;
        st.emails = [];
        st.selectedEmail = '';
        st.crm_contact_id = '';
        _renderOutreachWizard();
        _outreachLoadCurrent();
    }

    function _outreachLoadCrmFor(cur) {
        const seed = {
            id: cur.id,
            name: cur.name || '',
            email: cur.email || '',
            emails: cur.email ? [{ email: cur.email }] : [],
            phones: [],
            crm_contact_id: cur.crm_contact_id || '',
            gulp_id: cur.gulp_id || '',
            aid: cur.consultant_id || '',
        };
        return _enrichFromCrm(seed).then(enriched => {
            cur.crm_contact_id = enriched.crm_contact_id || cur.crm_contact_id || '';
            cur.email = enriched.email || cur.email || '';
            cur.gulp_id = enriched.gulp_id || cur.gulp_id || '';
            return {
                emails: enriched.emails || [],
                email: enriched.email || '',
                crm_contact_id: enriched.crm_contact_id || '',
            };
        }).catch(() => ({
            emails: cur.email ? [{ email: cur.email }] : [],
            email: cur.email || '',
            crm_contact_id: cur.crm_contact_id || '',
        }));
    }

    function _outreachLoadCurrent() {
        const st = window._outreachWizard;
        if (!st) return;
        const cur = st.queue[st.index];
        if (!cur) {
            _renderOutreachWizard();
            return;
        }
        st.loading = true;
        st.emails = [];
        st.selectedEmail = st.selectedEmail || cur.email || '';
        _renderOutreachWizard();
        const headers = { 'X-CSRFToken': csrf(), 'Content-Type': 'application/json' };

        const draftP = fetch(API + 'outreach/' + encodeURIComponent(cur.id) + '/letter/draft/', {
            method: 'POST',
            credentials: 'same-origin',
            headers,
            body: JSON.stringify({ refresh_reason: true }),
        })
        .then(async r => {
            let d = {};
            try { d = await r.json(); } catch (_) {}
            if (!r.ok || d.ok === false) throw new Error((d && d.error) || ('Draft HTTP ' + r.status));
            return d;
        });

        const crmP = _outreachLoadCrmFor(cur);

        Promise.all([draftP, crmP])
        .then(([d, crm]) => {
            st.deep = d.deep_reason || {
                why: d.why || cur.match_reason,
                interest: d.interest,
                reply_likelihood: d.reply_likelihood,
            };
            st.draft = d;
            if (d.project_consultant_id) cur.project_consultant_id = d.project_consultant_id;
            st.emails = crm.emails || [];
            st.crm_contact_id = crm.crm_contact_id || '';
            // Primär / CRM bevorzugen; Draft-to nur wenn leer
            const primary = _pickEmail(st.emails, crm.email || '');
            st.selectedEmail = primary || d.to_email || cur.email || '';
            if (st.draft) st.draft.to_email = st.selectedEmail;
            st.loading = false;
            _renderOutreachWizard();
        })
        .catch(e => {
            console.error(e);
            st.loading = false;
            st.deep = { why: cur.match_reason || String(e.message || e), interest: '—', reply_likelihood: null };
            const tpl = STAGE_MAIL.shortlist;
            const ctx = Object.assign(_projectContext(), { name: cur.name || '' });
            st.draft = {
                to_email: st.selectedEmail || cur.email || '',
                subject: _fillTpl(tpl.subject, ctx),
                body: _fillTpl(tpl.body, ctx),
            };
            // CRM trotzdem versuchen
            _outreachLoadCrmFor(cur).then(crm => {
                st.emails = crm.emails || [];
                st.crm_contact_id = crm.crm_contact_id || '';
                if (!st.selectedEmail) {
                    st.selectedEmail = _pickEmail(st.emails, crm.email || cur.email || '');
                    if (st.draft) st.draft.to_email = st.selectedEmail;
                }
                _renderOutreachWizard();
                const el = document.getElementById('ow-status');
                if (el) {
                    el.style.color = '#b91c1c';
                    el.textContent = 'KI-Draft fehlgeschlagen — Template genutzt: ' + (e.message || e);
                }
            });
        });
    }

    function outreachSkip() {
        const st = window._outreachWizard;
        if (!st || st.loading) return;
        const cur = st.queue[st.index];
        if (cur) st.skipped.push(cur.id);
        _outreachAdvance();
    }

    function _outreachAdvance() {
        const st = window._outreachWizard;
        if (!st) return;
        const next = st.index + 1;
        if (next >= st.queue.length) {
            const sent = st.sent.length;
            const skipped = st.skipped.length;
            closeOutreachWizard();
            alert(_kiT('outreach_done', 'Outreach fertig') + `: ${sent} gesendet, ${skipped} übersprungen.`);
            const content = document.getElementById('content-shortlist');
            const pid = (window._matchingShortlistCache || {}).projectId;
            if (content && pid) {
                content.dataset.loaded = '0';
                _loadShortlistForProject(pid, content);
            }
            return;
        }
        st.index = next;
        st.deep = null;
        st.draft = null;
        st.emails = [];
        st.selectedEmail = '';
        st.crm_contact_id = '';
        _renderOutreachWizard();
        _outreachLoadCurrent();
    }

    function outreachPolish() {
        const st = window._outreachWizard;
        if (!st || st.loading) return;
        const bodyEl = document.getElementById('ow-body');
        const text = (bodyEl && bodyEl.value) || '';
        if (!text.trim()) return;
        st.loading = true;
        const status = document.getElementById('ow-status');
        if (status) { status.style.color = '#666'; status.textContent = 'Glätten …'; }
        fetch(API + 'outreach/letter/polish/', {
            method: 'POST',
            credentials: 'same-origin',
            headers: { 'X-CSRFToken': csrf(), 'Content-Type': 'application/json' },
            body: JSON.stringify({ draft_text: text, keep_style: true }),
        })
        .then(async r => {
            let d = {};
            try { d = await r.json(); } catch (_) {}
            if (!r.ok || d.ok === false) throw new Error((d && d.error) || 'Polish fehlgeschlagen');
            return d;
        })
        .then(d => {
            st.loading = false;
            if (bodyEl) bodyEl.value = d.body || d.body_text || text;
            if (status) { status.style.color = '#155724'; status.textContent = 'Geglättet.'; }
        })
        .catch(e => {
            st.loading = false;
            if (status) { status.style.color = '#b91c1c'; status.textContent = e.message || String(e); }
        });
    }

    function outreachReloadDraft() {
        const st = window._outreachWizard;
        if (!st || st.loading) return;
        st.deep = null;
        st.draft = null;
        _outreachLoadCurrent();
    }

    function outreachSend() {
        const st = window._outreachWizard;
        if (!st || st.loading) return;
        const cur = st.queue[st.index];
        if (!cur) return;
        const to = ((document.getElementById('ow-to') || {}).value || '').trim();
        const subj = ((document.getElementById('ow-subj') || {}).value || '').trim();
        const body = ((document.getElementById('ow-body') || {}).value || '').trim();
        const wantTask = !!(document.getElementById('ow-task') || {}).checked;
        const taskDate = ((document.getElementById('ow-task-date') || {}).value || '').trim();
        const taskTime = ((document.getElementById('ow-task-time') || {}).value || '').trim();
        _outreachCaptureForm(st);
        const cc = (st.ccList || []).slice();
        const bcc = (st.bccList && st.bccList.length) ? st.bccList.slice() : ['send@abcona.de'];
        const status = document.getElementById('ow-status');
        const sendBtn = document.getElementById('ow-send');
        function show(ok, text) {
            if (!status) return;
            status.style.color = ok ? '#155724' : '#b91c1c';
            status.textContent = text || '';
        }
        if (!to || to.indexOf('@') < 0) { show(false, 'Bitte gültige E-Mail (An)'); return; }
        if (!subj || !body) { show(false, 'Betreff/Text fehlen'); return; }
        st.loading = true;
        if (sendBtn) sendBtn.disabled = true;
        show(true, 'Sende E-Mail …');

        const mailPayload = {
            template_identifier: 'crm_manual_email',
            to_email: to,
            cc: cc,
            bcc: bcc,
            cc_emails: cc,
            bcc_emails: bcc,
            subject: subj,
            body: _bodyTextToHtml(body),
            contact_name: cur.name || '',
            crm_id: st.crm_contact_id || '',
        };

        fetch('/crm/api/email/send/', {
            method: 'POST',
            credentials: 'same-origin',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrf(),
                'X-Requested-With': 'XMLHttpRequest',
            },
            body: JSON.stringify(mailPayload),
        })
        .then(r => r.json().then(j => ({ ok: r.ok, j })))
        .then(pack => {
            const j = pack.j || {};
            if (!(pack.ok && j.ok !== false && j.success !== false && !j.error)) {
                throw new Error(j.error || 'Senden fehlgeschlagen');
            }
            show(true, 'Status aktualisieren …');
            return fetch(API + 'outreach/' + encodeURIComponent(cur.id) + '/complete/', {
                method: 'POST',
                credentials: 'same-origin',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf() },
                body: JSON.stringify({
                    status: 'contacted',
                    create_task: wantTask,
                    faellig_am: taskDate || undefined,
                    faellig_zeit: taskTime || undefined,
                }),
            }).then(r => r.json().then(j2 => ({ ok: r.ok, j: j2 })));
        })
        .then(pack => {
            const j = pack.j || {};
            if (!pack.ok || j.ok === false) throw new Error(j.error || 'Complete fehlgeschlagen');
            if (wantTask && j.task) {
                const taskPayload = Object.assign({}, j.task);
                if (taskDate) taskPayload.faellig_am = taskDate;
                if (taskTime) taskPayload.faellig_zeit = taskTime;
                return fetch('/shaduler/api/aufgaben/create/', {
                    method: 'POST',
                    credentials: 'same-origin',
                    headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf() },
                    body: JSON.stringify(taskPayload),
                }).then(() => j).catch(err => {
                    console.warn('Wiedervorlage:', err);
                    return j;
                });
            }
            return j;
        })
        .then(() => {
            st.loading = false;
            st.sent.push(cur.id);
            _outreachAdvance();
        })
        .catch(err => {
            st.loading = false;
            if (sendBtn) sendBtn.disabled = false;
            show(false, err.message || String(err));
        });
    }

    function toggleArchiveDetail(card) {
        const detail = card.querySelector('.matching-archive-detail');
        const arrow  = card.querySelector('span:last-child');
        if (!detail.style.display || detail.style.display === 'none') {
            detail.style.display = 'block';
            if (arrow) arrow.textContent = '▼';
        } else {
            detail.style.display = 'none';
            if (arrow) arrow.textContent = '▶';
        }
    }

    function searchAnfragen(val) {
        const c = document.getElementById('content-anfragen');
        if (c) c.dataset.loaded = '0';
        clearTimeout(window._anf_search_timer);
        window._anf_search_timer = setTimeout(() => {
            _loadAnfragen(
                document.getElementById('content-anfragen'),
                document.getElementById('loading-anfragen')
            );
        }, 400);
    }

    function filterAnfragen() { searchAnfragen(''); }

    function searchAccounts(val) {
        if ((val || '').length < 2) return;
        fetch(API + 'crm/accounts/?q=' + encodeURIComponent(val), { credentials: 'same-origin' })
            .then(r => r.json())
            .then(d => {
                const res = document.getElementById('new-customer-results');
                if (!res) return;
                const hits = d.results || [];
                // Exact-/Einzeltreffer sofort verknüpfen (Stadt nicht nötig)
                const exact = _findExactFirm(hits, val);
                if (exact) {
                    _pickCrmAccount(exact);
                    return;
                }
                if (!hits.length) { res.style.display = 'none'; return; }
                res.style.display = 'block';
                res.style.cssText = 'background:white;border:1px solid #dde3ec;border-radius:6px;padding:4px;max-height:150px;overflow-y:auto;';
                res.innerHTML = hits.map(r =>
                    `<div style="padding:5px 8px;font-size:12px;cursor:pointer;border-radius:4px"
                          onmouseover="this.style.background='#f0f4fa'"
                          onmouseout="this.style.background=''"
                          onclick="Matching.pickAccountFromSearch('${(r.crm_id||r.id||'').replace(/'/g,"\\'")}','${(r.name||'').replace(/'/g,"\\'")}','${(r.city||'').replace(/'/g,"\\'")}')">
                        <strong>${r.name}</strong> ${r.city ? '· '+r.city : ''}
                    </div>`
                ).join('');
            });
    }

    function pickAccountFromSearch(id, name, city) {
        _pickCrmAccount({ crm_id: id, id: id, name: name, city: city });
    }

    function searchContacts(val) {
        if (val.length < 2) return;
        fetch(API + 'crm/contacts/?q=' + encodeURIComponent(val), { credentials: 'same-origin' })
            .then(r => r.json())
            .then(d => {
                const res = document.getElementById('new-contact-results');
                if (!res) return;
                if (!d.results?.length) { res.style.display = 'none'; return; }
                res.style.display = 'block';
                res.style.cssText = 'background:white;border:1px solid #dde3ec;border-radius:6px;padding:4px;max-height:150px;overflow-y:auto;';
                res.innerHTML = d.results.map(r =>
                    `<div style="padding:5px 8px;font-size:12px;cursor:pointer;border-radius:4px"
                          onmouseover="this.style.background='#f0f4fa'"
                          onmouseout="this.style.background=''"
                          onclick="document.getElementById('new-contact').value='${r.full_name}';document.getElementById('new-contact-results').style.display='none'">
                        <strong>${r.full_name}</strong> · ${r.account_name || ''} · ${r.email || ''}
                    </div>`
                ).join('');
            });
    }

    // ── Stage → Standard-Mail (nächste Aktion laut Workflow) ──────────────
    // shortlist → Anschreiben | angeschrieben → Interesse | interesse → Beim Kunden
    // beim_kunden → Interview | interview → Vermittelt|Absage | vermittelt → Start
    const STAGE_MAIL = {
        shortlist: {
            nextStatus: 'angeschrieben',
            actionKey: 'anschreiben',
            label: 'Anschreiben',
            subject: 'Anfrage {project} — passt das für Sie?',
            body:
                'Guten Tag {name},\n\n' +
                'zu unserer aktuellen Kundenanfrage „{project}“ ({customer}) möchten wir Sie gerne anfragen.\n' +
                'Passt das thematisch zu Ihrem Profil?\n\n' +
                'Viele Grüße',
        },
        angeschrieben: {
            nextStatus: 'interesse',
            actionKey: 'interesse',
            label: 'Interesse / Verfügbarkeit',
            subject: 'Nachfrage Verfügbarkeit — {project}',
            body:
                'Guten Tag {name},\n\n' +
                'kurze Nachfrage zu „{project}“ ({customer}):\n' +
                'Besteht Interesse, und wann wären Sie verfügbar (ab Datum / Stunden pro Woche)?\n\n' +
                'Viele Grüße',
        },
        interesse: {
            nextStatus: 'beim_kunden',
            actionKey: 'vorstellen',
            label: 'Beim Kunden vorstellen',
            subject: 'Vorstellung beim Kunden — {project}',
            body:
                'Guten Tag {name},\n\n' +
                'wir möchten Sie dem Kunden zu „{project}“ ({customer}) vorstellen.\n' +
                'Dürfen wir Ihr Profil (anonymisiert/mit CV) weiterleiten?\n\n' +
                'Viele Grüße',
        },
        beim_kunden: {
            nextStatus: 'interview',
            actionKey: 'interview',
            label: 'Interview koordinieren',
            subject: 'Interview-Koordination — {project}',
            body:
                'Guten Tag {name},\n\n' +
                'der Kunde zu „{project}“ ({customer}) möchte Sie kennenlernen.\n' +
                'Welche Termine passen Ihnen diese Woche (Datum/Uhrzeit, Tel. oder Video)?\n\n' +
                'Viele Grüße',
        },
        interview: {
            nextStatus: 'vermittelt',
            actionKey: 'vermittelt',
            label: 'Vermittlung / Start',
            subject: 'Vermittlung — Startabstimmung {project}',
            body:
                'Guten Tag {name},\n\n' +
                'zur Vermittlung „{project}“ ({customer}):\n' +
                'Bitte teilen Sie uns Ihren Wunsch-Starttermin und den Ansprechpartner vor Ort mit.\n\n' +
                'Viele Grüße',
        },
        vermittelt: {
            nextStatus: null,
            actionKey: 'start',
            label: 'Start-Info',
            subject: 'Startinfo — {project}',
            body:
                'Guten Tag {name},\n\n' +
                'zur Aufnahme bei „{project}“ ({customer}):\n' +
                '• Start: {start}\n' +
                '• Ort / Remote: {location}\n' +
                '• Ansprechpartner Kunde: bitte melden Sie sich bei Bedarf über uns.\n\n' +
                'Viel Erfolg und viele Grüße',
        },
        absage: {
            nextStatus: null,
            actionKey: 'absage',
            label: 'Absage',
            subject: 'Rückmeldung zur Anfrage {project}',
            body:
                'Guten Tag {name},\n\n' +
                'vielen Dank für Ihr Interesse an „{project}“ ({customer}).\n' +
                'Leider hat sich der Kunde anderweitig entschieden. Wir melden uns gerne bei passenden Folgeanfragen.\n\n' +
                'Freundliche Grüße',
        },
    };

    function _normStage(stage) {
        const s = String(stage || '').toLowerCase().trim()
            .replace(/\s+/g, '_').replace(/-/g, '_');
        const aliases = {
            short: 'shortlist',
            contacted: 'angeschrieben',
            written: 'angeschrieben',
            interest: 'interesse',
            interested: 'interesse',
            at_client: 'beim_kunden',
            client: 'beim_kunden',
            placed: 'vermittelt',
            rejected: 'absage',
            decline: 'absage',
        };
        return aliases[s] || s;
    }

    function _phoneFieldLabel(fieldName) {
        const fn = String(fieldName || '').toLowerCase();
        const map = {
            phone_mobile: 'Mobil',
            mobile: 'Mobil',
            handy: 'Mobil',
            phone_work: 'Büro',
            phone_office: 'Büro',
            office: 'Büro',
            buero: 'Büro',
            phone_fax: 'Fax',
            fax: 'Fax',
            phone_home: 'Privat',
            phone_other: 'Tel',
            phone: 'Tel',
            telefon: 'Tel',
        };
        return map[fn] || (fieldName ? String(fieldName) : 'Tel');
    }

    function _fixText(s) {
        // Häufige Mojibake-Korrektur (z.B. "K??ln" / "KÃ¶ln" → "Köln")
        let t = String(s || '');
        if (!t) return '';
        try {
            if (/Ã.|Â./.test(t)) {
                t = decodeURIComponent(escape(t));
            }
        } catch (e) { /* ignore */ }
        return t
            .replace(/K\?\?ln/gi, 'Köln')
            .replace(/M\?\?nchen/gi, 'München')
            .replace(/D\?\?sseldorf/gi, 'Düsseldorf')
            .replace(/N\?\?rnberg/gi, 'Nürnberg');
    }

    function _stageMailTpl(stage, variant) {
        const st = _normStage(stage);
        if (st === 'interview' && variant === 'absage') return STAGE_MAIL.absage;
        return STAGE_MAIL[st] || STAGE_MAIL.shortlist;
    }

    function _projectContext() {
        const cfgP = window.MATCHING_CONFIG || {};
        const labelEl = document.querySelector('#content-kanban [style*="font-size:12px"]');
        const raw = (labelEl && labelEl.textContent) || '';
        const parts = raw.split('·').map(x => x.trim()).filter(Boolean);
        return {
            projectId: cfgP.activeProject || '',
            project: parts[1] || parts[0] || 'Anfrage',
            projectNumber: parts[0] || '',
            customer: cfgP.activeCustomer || '',
            location: '',
            start: '',
        };
    }

    function _fillTpl(str, vars) {
        return String(str || '').replace(/\{(\w+)\}/g, function (_, k) {
            return vars[k] != null && vars[k] !== '' ? String(vars[k]) : '';
        });
    }

    function _cardEl(matchId) {
        return document.querySelector('.matching-card[data-match-id="' + matchId + '"]');
    }

    function _matchFromCard(matchId) {
        const el = _cardEl(matchId);
        if (!el) return { id: matchId };
        return {
            id: matchId,
            name: el.getAttribute('data-name') || '',
            location: el.getAttribute('data-location') || '',
            phone: el.getAttribute('data-phone') || '',
            email: el.getAttribute('data-email') || '',
            crm_contact_id: el.getAttribute('data-crm') || '',
            stage: el.getAttribute('data-stage') || '',
            match_score: parseFloat(el.getAttribute('data-score') || '0') || 0,
            phones: [],
            emails: [],
            skills: [],
        };
    }

    function _pickPhone(list, fallback) {
        if (fallback) return fallback;
        if (!list || !list.length) return '';
        const nonFax = list.filter(p => !/fax/i.test(p.label || ''));
        const pool = nonFax.length ? nonFax : list;
        const pref = pool.find(p => /mobil|mobile|handy/i.test(p.label || ''))
            || pool.find(p => /büro|buero|office|arbeit|work/i.test(p.label || ''))
            || pool[0];
        return (pref && (pref.number || pref.nummer || pref.raw || pref.value || pref.phone)) || '';
    }

    function _pickEmail(list, fallback) {
        if (fallback) return fallback;
        if (!list || !list.length) return '';
        const objs = list.map(e => (typeof e === 'string' ? { email: e } : e));
        const pref = objs.find(e => e && e.primary) || objs[0];
        return (pref && (pref.email || pref.value || pref.address || pref.raw)) || '';
    }

    function _crmIdFrom(c, fallback) {
        // Sugar-crm_id hat Vorrang vor internem DB-id (Detail-URL braucht crm_id)
        const cid = c && (c.crm_id || c.contact_id || c.consultant_crm_id);
        if (cid) return String(cid);
        return fallback ? String(fallback) : '';
    }

    function _normalizeCrmPayload(raw, base) {
        if (!raw || typeof raw !== 'object') return base;
        // Detail-Payload ist flach {crm_id, phones, emails, cstm, ...} — nicht hinter .data verstecken,
        // wenn phones/emails schon top-level liegen.
        let c = raw;
        if (!Array.isArray(raw.phones) && !Array.isArray(raw.emails) && !raw.crm_id) {
            c = raw.contact || raw.berater || raw.item || raw.data || raw.result || raw;
        }
        const cstm = c.cstm || {};
        const eck = c.eckdaten || {};
        const phones = [];
        const seen = {};
        const pushPhone = (num, label) => {
            const n = String(num || '').trim();
            if (!n || n === '—' || n === '-') return;
            const key = n.replace(/[^\d+]/g, '');
            if (key && seen[key]) return;
            if (key) seen[key] = true;
            phones.push({ label: label || 'Tel', number: n });
        };
        if (Array.isArray(c.phones)) {
            c.phones.forEach(p => {
                if (typeof p === 'string') {
                    pushPhone(p, 'Tel');
                    return;
                }
                // Live-CRM: { field_name, raw, norm, label, is_primary }
                const num = p.raw || p.phone_raw || p.norm || p.nummer || p.number
                    || p.phone || p.value || p.display || '';
                pushPhone(num, _phoneFieldLabel(p.field_name || p.label || p.typ || p.type));
            });
        }
        pushPhone(c.phone_mobile || c.mobile || c.handy, 'Mobil');
        pushPhone(c.phone_office || c.phone_work || c.buero || c.office, 'Büro');
        pushPhone(c.phone_fax || c.fax, 'Fax');
        pushPhone(c.phone || c.telefon, 'Tel');

        const emails = [];
        const pushMail = (em, primary) => {
            const e = String(em || '').trim();
            if (!e || e.indexOf('@') < 0) return;
            const existing = emails.find(x => x.email === e);
            if (existing) {
                if (primary) existing.primary = true;
                return;
            }
            emails.push({ email: e, primary: !!primary });
        };
        if (Array.isArray(c.emails)) {
            // Primär zuerst
            const sorted = c.emails.slice().sort((a, b) => {
                if (typeof a === 'object' && a && a.primary) return -1;
                if (typeof b === 'object' && b && b.primary) return 1;
                return 0;
            });
            sorted.forEach(e => {
                if (typeof e === 'string') pushMail(e, false);
                else pushMail(e.email || e.value || e.raw, !!(e && e.primary));
            });
        }
        pushMail(c.email || c.mail || c.email_primary, !emails.length);

        const addr = c.address || c.hauptadresse || c.primary_address || {};
        const city = _fixText(c.city || c.ort || addr.city || addr.ort || addr.town || '');
        const street = _fixText(addr.street || addr.strasse || addr.line1 || c.street || '');
        const zip = addr.zip || addr.plz || addr.postal_code || c.zip || '';
        const country = addr.country || addr.land || c.country || '';
        const addressLine = [street, [zip, city].filter(Boolean).join(' '), country].filter(Boolean).join(', ');

        (base.phones || []).forEach(bp => pushPhone(bp.number || bp.raw, bp.label));
        const mergedEmails = emails.length ? emails : (base.emails || []).map(e =>
            typeof e === 'string' ? { email: e } : e
        );

        const account = c.account || {};
        return Object.assign({}, base, {
            name: c.full_name || c.name || [c.first_name || c.vorname, c.last_name || c.nachname].filter(Boolean).join(' ') || base.name,
            location: city || _fixText(base.location) || '',
            address: addressLine || base.address || '',
            phone: _pickPhone(phones, base.phone),
            email: _pickEmail(mergedEmails, base.email),
            phones: phones.length ? phones : (base.phones || []),
            emails: mergedEmails,
            crm_contact_id: _crmIdFrom(c, base.crm_contact_id),
            gulp_id: c.gulp_id || c.gulpId || cstm.gulp_id || eck.gulp_id || base.gulp_id || '',
            rate: c.rate || c.konditionen || cstm.konditionen || eck.konditionen || c.satz || c.hourly_rate || base.rate || '',
            crm_status: c.status || c.crm_status || cstm.kontakt_status || base.crm_status || '',
            crm_type: c.type || c.typ || c.contact_type || cstm.kontakt_typ || base.crm_type || '',
            company: c.account_name || account.name || c.firma || c.company || base.company || '',
            aid: c.aid || base.aid || '',
            available_from: _normDate(
                c.verfuegbar_ab || c.verfuegbar || c.available_from
                || cstm.verfuegbar_ab || eck.verfuegbar_ab || base.available_from || ''
            ),
            avail_days_per_week: (
                c.verfuegbar_tage_pro_woche != null ? c.verfuegbar_tage_pro_woche
                : (cstm.verfuegbar_tage_pro_woche != null ? cstm.verfuegbar_tage_pro_woche
                    : (base.avail_days_per_week != null ? base.avail_days_per_week : null))
            ),
            avail_note: c.verfuegbar_hinweis || cstm.verfuegbar_hinweis || base.avail_note || '',
            rate_remote: c.satz_remote || cstm.satz_remote || base.rate_remote || '',
            rate_onsite: c.satz_vor_ort || cstm.satz_vor_ort || base.rate_onsite || '',
            freelancermap: c.freelancermap || cstm.freelancermap
                || (Array.isArray(cstm.web_profiles)
                    ? ((cstm.web_profiles.find(w => /freelance/i.test(w.typ || '')) || {}).url || '')
                    : '')
                || base.freelancermap || '',
        });
    }

    function _normDate(v) {
        if (!v) return '';
        if (typeof v === 'object' && v.isoformat) return String(v.isoformat()).slice(0, 10);
        const s = String(v).trim();
        if (!s) return '';
        // ISO oder DE dd.mm.yyyy
        const iso = s.match(/^(\d{4})-(\d{2})-(\d{2})/);
        if (iso) return iso[1] + '-' + iso[2] + '-' + iso[3];
        const de = s.match(/^(\d{1,2})\.(\d{1,2})\.(\d{4})/);
        if (de) {
            return de[3] + '-' + de[2].padStart(2, '0') + '-' + de[1].padStart(2, '0');
        }
        return s.slice(0, 10);
    }

    function _fmtDate(v) {
        const d = _normDate(v);
        if (!d || d.length < 10) return '—';
        const m = d.match(/^(\d{4})-(\d{2})-(\d{2})/);
        if (!m) return d;
        return m[3] + '.' + m[2] + '.' + m[1];
    }

    function _dateTone(crm, other) {
        const a = _normDate(crm);
        const b = _normDate(other);
        if (!b) return { label: 'keine Angabe', color: '#888' };
        if (!a) return { label: 'neu', color: '#0d9488' };
        if (a === b) return { label: 'gleich', color: '#16a34a' };
        if (b > a) return { label: 'später als CRM', color: '#d97706' };
        return { label: 'früher als CRM', color: '#dc2626' };
    }

    function _jsonGet(url) {
        return fetch(url, { credentials: 'same-origin', headers: { 'X-Requested-With': 'XMLHttpRequest' } })
            .then(r => r.ok ? r.json() : null)
            .catch(() => null);
    }

    function _mergeCrmHit(out, d, nameHint) {
        if (!d) return;
        const list = d.results || d.items || d.contacts || d.berater;
        if (Array.isArray(list) && list.length) {
            const q = String(nameHint || out.name || '').toLowerCase();
            const gulp = String(out.gulp_id || '');
            const exact = list.find(x => String(x.full_name || x.name || '').toLowerCase() === q)
                || (gulp && list.find(x => String(x.gulp_id || '') === gulp))
                || list[0];
            Object.assign(out, _normalizeCrmPayload(exact, out));
            return;
        }
        // Detail-Response muss crm_id oder phones/emails haben
        if (d.crm_id || Array.isArray(d.phones) || Array.isArray(d.emails) || d.full_name || d.cstm) {
            Object.assign(out, _normalizeCrmPayload(d, out));
        }
    }

    function _needsCrmContact(out) {
        const hasPhone = !!(out.phone || (out.phones && out.phones.length));
        const hasMail = !!(out.email || (out.emails && out.emails.length));
        return !hasPhone || !hasMail;
    }

    function _fetchBeraterDetail(crmId) {
        if (!crmId) return Promise.resolve(null);
        const url = '/crm/api/berater/' + encodeURIComponent(crmId) + '/';
        return _jsonGet(url);
    }

    function _enrichFromCrm(detail) {
        const out = Object.assign({ phones: [], emails: [] }, detail);
        const name = out.name || '';
        const gulp = out.gulp_id ? String(out.gulp_id) : '';

        // 1) Berater-Detail, falls crm_id schon bekannt
        let chain = _fetchBeraterDetail(out.crm_contact_id).then(d => _mergeCrmHit(out, d, name));

        // 2) Suche nach Name / Gulp — Listenzeile hat Tel, aber oft KEINE E-Mails
        chain = chain.then(() => {
            if (!_needsCrmContact(out) && out.crm_contact_id) return null;
            const searches = [];
            if (name && name.length >= 2) {
                searches.push('/crm/api/berater/?q=' + encodeURIComponent(name) + '&per_page=5');
            }
            if (gulp) {
                searches.push('/crm/api/berater/?q=' + encodeURIComponent(gulp) + '&per_page=5');
            }
            let s = Promise.resolve();
            searches.forEach(u => {
                s = s.then(() => {
                    if (!_needsCrmContact(out) && out.crm_contact_id) return null;
                    return _jsonGet(u).then(d => _mergeCrmHit(out, d, name));
                });
            });
            return s;
        });

        // 3) Nach Listen-Treffer: Detail NACHLADEN (E-Mails nur im Detail)
        chain = chain.then(() => {
            if (!out.crm_contact_id) return null;
            if (!_needsCrmContact(out)) return null;
            return _fetchBeraterDetail(out.crm_contact_id).then(d => _mergeCrmHit(out, d, name));
        });

        return chain.then(() => {
            out.location = _fixText(out.location);
            out.phone = _pickPhone(out.phones, out.phone);
            out.email = _pickEmail(out.emails, out.email);
            // Karte/Cache mit CRM-Daten aktualisieren
            try {
                const el = _cardEl(out.id);
                if (el) {
                    if (out.phone) el.setAttribute('data-phone', out.phone);
                    if (out.email) el.setAttribute('data-email', out.email);
                    if (out.crm_contact_id) el.setAttribute('data-crm', out.crm_contact_id);
                }
            } catch (e) { /* ignore */ }
            return out;
        });
    }

    function _fetchMatchDetail(matchId) {
        const base = _matchFromCard(matchId);
        const urls = [
            API + 'match/' + matchId + '/',
            API + 'match/' + matchId + '/detail/',
            API + 'matches/' + matchId + '/',
        ];
        function tryOne(i) {
            if (i >= urls.length) return Promise.resolve(base);
            return fetch(urls[i], { credentials: 'same-origin' })
                .then(r => r.ok ? r.json() : null)
                .then(d => {
                    if (!d || d.success === false) return tryOne(i + 1);
                    const m = d.match || d.consultant || d.result || d;
                    return {
                        id: matchId,
                        name: m.name || m.full_name || base.name,
                        location: m.location || m.city || base.location,
                        phone: m.phone || m.telefon || m.mobile || m.phone_mobile || base.phone,
                        email: m.email || m.mail || base.email,
                        crm_contact_id: m.crm_contact_id || m.crm_id || m.consultant_crm_id || base.crm_contact_id,
                        // Board-Spalte hat Vorrang vor API-Status (z.B. "interested")
                        stage: base.stage || m.status || m.stage || '',
                        match_score: m.match_score != null ? m.match_score : base.match_score,
                        skills: m.matched_skills || m.skills || [],
                        match_reason: m.match_reason || m.reason || '',
                        aid: m.aid || m.consultant_aid || '',
                        gulp_id: m.gulp_id || '',
                        rate: m.rate || m.satz || '',
                        available_from: _normDate(m.verfuegbar_ab || m.available_from || m.available || ''),
                        freelancermap: m.freelancermap || m.freelancermap_profil || m.fm_url || '',
                        cv_editor_url: m.cv_editor_url || m.cv_url || '',
                        phones: [],
                        emails: [],
                    };
                })
                .catch(() => tryOne(i + 1));
        }
        return tryOne(0).then(_enrichFromCrm).then(_loadMatchTerms).then(d => {
            window._matchingContactCache = window._matchingContactCache || {};
            window._matchingContactCache[matchId] = d;
            return d;
        });
    }

    function _stageLabel(stage) {
        const map = {
            shortlist: 'Shortlist',
            angeschrieben: 'Angeschrieben',
            interesse: 'Interesse',
            beim_kunden: 'Beim Kunden',
            interview: 'Interview',
            vermittelt: 'Vermittelt',
            absage: 'Absage',
        };
        const st = _normStage(stage);
        return map[st] || stage || '—';
    }

    function _closeContactPopup() {
        const ov = document.getElementById('matching-contact-ovl');
        if (ov) ov.remove();
    }

    function _csrfHdr() {
        let t = csrf();
        if (!t) {
            const m = document.cookie.match(/(?:^|; )csrftoken=([^;]+)/);
            t = m ? decodeURIComponent(m[1]) : '';
        }
        if (!t) {
            const meta = document.querySelector('meta[name="csrf-token"],meta[name="csrfmiddlewaretoken"]');
            if (meta) t = meta.getAttribute('content') || '';
        }
        if (!t) {
            const inp = document.querySelector('input[name="csrfmiddlewaretoken"]');
            if (inp) t = inp.value || '';
        }
        return t || '';
    }

    function _jsonPost(url, body) {
        return fetch(url, {
            method: 'POST',
            credentials: 'same-origin',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': _csrfHdr(),
                'X-Requested-With': 'XMLHttpRequest',
            },
            body: JSON.stringify(body || {}),
        }).then(async r => {
            let data = null;
            try { data = await r.json(); } catch (e) { data = null; }
            if (!r.ok) {
                return {
                    ok: false,
                    error: (data && (data.error || data.detail)) || ('HTTP ' + r.status),
                    status: r.status,
                };
            }
            if (data && typeof data === 'object') return data;
            return { ok: true };
        }).catch(e => ({ ok: false, error: String(e && e.message || e) }));
    }

    function _availRowHtml(label, dateVal, tone, adoptBtn) {
        const t = tone || { label: '', color: '#888' };
        return `<div style="display:flex;align-items:center;gap:8px;margin-bottom:3px;flex-wrap:wrap">
          <span style="color:#888;min-width:36px">${_esc(label)}</span>
          <b style="min-width:84px">${_esc(_fmtDate(dateVal))}</b>
          ${t.label ? `<span style="font-size:10px;color:${t.color}">${_esc(t.label)}</span>` : ''}
          ${adoptBtn || ''}
        </div>`;
    }

    function _adoptBtnHtml(matchId, source, dateVal) {
        const d = _normDate(dateVal);
        if (!d) return '';
        return `<button type="button" class="matching-btn-sm" style="font-size:10px;padding:2px 7px"
                  title="Datum ins CRM übernehmen"
                  onclick="Matching.adoptAvailability('${_escAttr(matchId)}','${_escAttr(source)}')">
                  <i class="bi bi-download"></i> Übernehmen
                </button>`;
    }

    function _renderAvailBox(el, detail, live) {
        if (!el) return;
        const matchId = detail.id || '';
        const crm = detail.available_from || '';
        const gulp = (live && live.gulp) || {};
        const fm = (live && live.fm) || {};
        // Live-State merken für Übernehmen-Buttons
        window._matchingAvailLive = window._matchingAvailLive || {};
        window._matchingAvailLive[matchId] = live || {};

        let body = _availRowHtml('CRM', crm, { label: crm ? 'Datenbank' : 'kein Datum', color: '#888' });
        if (detail.gulp_id) {
            if (gulp.loading) {
                body += `<div style="font-size:11px;color:#888;margin:2px 0"><i class="bi bi-hourglass-split"></i> Gulp wird geprüft…</div>`;
            } else if (gulp.error && !gulp.date) {
                body += `<div style="font-size:11px;color:#b45309;margin:2px 0">Gulp: ${_esc(gulp.error)}</div>`;
            } else {
                const tone = _dateTone(crm, gulp.date);
                const showAdopt = gulp.date && _normDate(gulp.date) !== _normDate(crm);
                body += _availRowHtml(
                    'Gulp', gulp.date, tone,
                    showAdopt ? _adoptBtnHtml(matchId, 'gulp', gulp.date) : ''
                );
            }
        } else {
            body += `<div style="font-size:11px;color:#aaa;margin:2px 0">Gulp: keine ID</div>`;
        }
        if (detail.freelancermap) {
            if (fm.loading) {
                body += `<div style="font-size:11px;color:#888;margin:2px 0"><i class="bi bi-hourglass-split"></i> Freelancermap wird geprüft…</div>`;
            } else if (fm.error && !fm.date) {
                body += `<div style="font-size:11px;color:#b45309;margin:2px 0">FM: ${_esc(fm.error)}</div>`;
            } else {
                const tone = _dateTone(crm, fm.date);
                const showAdopt = fm.date && _normDate(fm.date) !== _normDate(crm);
                body += _availRowHtml(
                    'FM', fm.date, tone,
                    showAdopt ? _adoptBtnHtml(matchId, 'fm', fm.date) : ''
                );
            }
        } else {
            body += `<div style="font-size:11px;color:#aaa;margin:2px 0">FM: nicht verknüpft</div>`;
        }
        if (live && live.note) {
            body += `<div style="font-size:10px;color:#666;margin-top:4px">${_esc(live.note)}</div>`;
        }
        el.innerHTML = body;
    }

    function _fetchSourceAvailability(text) {
        return _jsonPost('/shaduler/api/radar/berater/einfuegen/', { text: text })
            .then(d => {
                if (!d || !d.ok) {
                    const err = (d && (d.error || d.fetch_error)) || 'Abfrage fehlgeschlagen';
                    const auth = d && (d.needs_auth || d.gulp_session === false || d.fl_session === false);
                    return {
                        ok: false,
                        error: auth ? (err + ' (Login/Session prüfen)') : err,
                        date: '',
                        source: d && d.source,
                    };
                }
                const item = d.item || {};
                return {
                    ok: true,
                    date: _normDate(item.verfuegbar_ab || ''),
                    source: d.source || item.source || '',
                    name: item.name || '',
                    fetched: !!d.fetched,
                    error: d.fetch_error || '',
                };
            });
    }

    function _startAvailabilityCompare(detail) {
        const box = document.getElementById('matching-avail-box');
        if (!box) return;
        const live = { gulp: null, fm: null, note: '' };
        const jobs = [];

        if (detail.gulp_id) {
            live.gulp = { loading: true };
            _renderAvailBox(box, detail, live);
            jobs.push(
                _fetchSourceAvailability(String(detail.gulp_id)).then(r => {
                    live.gulp = r.ok
                        ? { date: r.date, error: r.fetched ? '' : (r.error || 'ohne Live-Daten') }
                        : { date: '', error: r.error || 'Fehler' };
                    _renderAvailBox(box, detail, live);
                    if (r.ok && r.date) {
                        detail.available_gulp = r.date;
                        const cache = window._matchingContactCache || {};
                        if (cache[detail.id]) cache[detail.id].available_gulp = r.date;
                    }
                    const inp = document.getElementById('matching-avail-input');
                    if (inp && !inp.value && r.ok && r.date) inp.value = r.date;
                })
            );
        }

        if (detail.freelancermap) {
            live.fm = { loading: true };
            _renderAvailBox(box, detail, live);
            jobs.push(
                _fetchSourceAvailability(String(detail.freelancermap)).then(r => {
                    live.fm = r.ok
                        ? { date: r.date, error: r.fetched ? '' : (r.error || 'ohne Live-Daten') }
                        : { date: '', error: r.error || 'Fehler' };
                    _renderAvailBox(box, detail, live);
                    if (r.ok && r.date) {
                        detail.available_fm = r.date;
                        const cache = window._matchingContactCache || {};
                        if (cache[detail.id]) cache[detail.id].available_fm = r.date;
                    }
                })
            );
        }

        if (!jobs.length) {
            live.note = 'Keine externe Quelle (Gulp-ID / FM-Profil) zum Abgleich.';
            _renderAvailBox(box, detail, live);
            return;
        }

        Promise.all(jobs).then(() => {
            const crm = _normDate(detail.available_from);
            const g = live.gulp && live.gulp.date;
            const f = live.fm && live.fm.date;
            const diffs = [];
            if (g && !crm) diffs.push('Gulp neu, CRM leer');
            else if (g && crm && g !== crm) diffs.push('Gulp≠CRM');
            if (f && !crm) diffs.push('FM neu, CRM leer');
            else if (f && crm && f !== crm) diffs.push('FM≠CRM');
            if (g && f && g !== f) diffs.push('Gulp≠FM');
            live.note = diffs.length
                ? ('Abweichung: ' + diffs.join(', ') + ' — „Übernehmen“ oder Datum speichern')
                : 'Quellen stimmen mit CRM überein (soweit geliefert).';
            _renderAvailBox(box, detail, live);
        });
    }

    function _saveCrmFields(detail, fields, msgEl) {
        const crmId = detail && detail.crm_contact_id;
        const msg = msgEl || document.getElementById('matching-avail-msg');
        if (!crmId) {
            if (msg) { msg.style.color = '#dc2626'; msg.textContent = 'Kein CRM-Kontakt — Speichern nicht möglich.'; }
            return Promise.resolve({ ok: false });
        }
        const payload = Object.assign({ action: 'update' }, fields || {});
        if (msg) { msg.style.color = '#666'; msg.textContent = 'Speichere im CRM…'; }
        return _jsonPost('/crm/api/contact/' + encodeURIComponent(crmId) + '/update/', payload)
            .then(res => {
                if (res && res.ok !== false && !res.error) {
                    return { ok: true, res: res };
                }
                if (msg) {
                    msg.style.color = '#dc2626';
                    msg.textContent = 'Speichern fehlgeschlagen: '
                        + ((res && res.error) || (res && res.status === 403 ? 'CSRF/Login' : 'unbekannt'));
                }
                return { ok: false, res: res };
            });
    }

    function _saveAvailabilityToCrm(detail, isoDate) {
        const date = _normDate(isoDate);
        const msg = document.getElementById('matching-avail-msg');
        if (!date || !/^\d{4}-\d{2}-\d{2}$/.test(date)) {
            if (msg) { msg.style.color = '#dc2626'; msg.textContent = 'Bitte Datum wählen oder als TT.MM.JJJJ eingeben.'; }
            return Promise.resolve({ ok: false });
        }
        return _saveCrmFields(detail, { verfuegbar_ab_c: date }, msg).then(r => {
            if (!r.ok) return r;
            detail.available_from = date;
            const cache = window._matchingContactCache || {};
            if (cache[detail.id]) cache[detail.id].available_from = date;
            const inp = document.getElementById('matching-avail-input');
            if (inp) inp.value = date;
            if (msg) {
                msg.style.color = '#16a34a';
                msg.textContent = 'CRM gespeichert: verfügbar ab ' + _fmtDate(date);
            }
            const live = (window._matchingAvailLive || {})[detail.id] || { gulp: null, fm: null, note: '' };
            live.note = 'CRM aktualisiert auf ' + _fmtDate(date);
            _renderAvailBox(document.getElementById('matching-avail-box'), detail, live);
            return { ok: true, date: date };
        });
    }

    function saveAvailability(matchId) {
        return saveMatchTerms(matchId, { focus: 'avail' });
    }

    function saveRate(matchId) {
        return saveMatchTerms(matchId, { focus: 'rate' });
    }

    function saveMatchTerms(matchId, opts) {
        opts = opts || {};
        const detail = (window._matchingContactCache || {})[matchId];
        const msg = document.getElementById('matching-terms-msg')
            || document.getElementById('matching-avail-msg')
            || document.getElementById('matching-rate-msg');
        const alsoCrm = !!(document.getElementById('matching-terms-also-crm') || {}).checked;

        const availInp = document.getElementById('matching-avail-input');
        const availTxt = document.getElementById('matching-avail-text');
        let availRaw = availInp ? availInp.value : '';
        if ((!availRaw || !String(availRaw).trim()) && availTxt && availTxt.value) {
            availRaw = availTxt.value;
        }
        const daysEl = document.getElementById('matching-avail-days');
        const noteEl = document.getElementById('matching-avail-note');
        const remoteEl = document.getElementById('matching-rate-remote');
        const onsiteEl = document.getElementById('matching-rate-onsite');
        const rateNoteEl = document.getElementById('matching-rate-note');

        const payload = {
            crm_contact_id: (detail && detail.crm_contact_id) || '',
            project_id: (window.MATCHING_CONFIG && window.MATCHING_CONFIG.activeProject) || '',
            also_crm: alsoCrm,
            avail_from: _normDate(availRaw) || '',
            avail_days_per_week: daysEl && daysEl.value !== '' ? daysEl.value : '',
            avail_note: noteEl ? noteEl.value.trim() : '',
            rate_remote: remoteEl ? remoteEl.value.trim() : '',
            rate_onsite: onsiteEl ? onsiteEl.value.trim() : '',
            rate_note: rateNoteEl ? rateNoteEl.value.trim() : '',
        };

        if (opts.focus === 'avail' && !payload.avail_from && payload.avail_days_per_week === '' && !payload.avail_note) {
            if (msg) { msg.style.color = '#dc2626'; msg.textContent = 'Bitte Verfügbarkeit (Datum/Tage/Hinweis) setzen.'; }
            return Promise.resolve({ ok: false });
        }
        if (opts.focus === 'rate' && !payload.rate_remote && !payload.rate_onsite && !payload.rate_note) {
            if (msg) { msg.style.color = '#dc2626'; msg.textContent = 'Bitte Remote- und/oder Vor-Ort-Satz eingeben.'; }
            return Promise.resolve({ ok: false });
        }

        const run = function (d) {
            if (!d || !d.id) {
                if (msg) { msg.style.color = '#dc2626'; msg.textContent = 'Kein Match geladen.'; }
                return Promise.resolve({ ok: false });
            }
            payload.crm_contact_id = payload.crm_contact_id || d.crm_contact_id || '';
            if (msg) { msg.style.color = '#666'; msg.textContent = 'Speichere Konditionen…'; }

            // 1) immer Match-Tabelle (Shaduler)
            return _jsonPost('/shaduler/api/matching/terms/' + encodeURIComponent(d.id) + '/', payload)
                .then(res => {
                    if (!res || res.ok === false) {
                        if (msg) {
                            msg.style.color = '#dc2626';
                            msg.textContent = 'Match-Speichern fehlgeschlagen: ' + ((res && res.error) || 'unbekannt');
                        }
                        return { ok: false };
                    }
                    const t = res.terms || payload;
                    d.available_from = _normDate(t.avail_from) || d.available_from;
                    d.avail_days_per_week = t.avail_days_per_week != null && t.avail_days_per_week !== ''
                        ? t.avail_days_per_week : d.avail_days_per_week;
                    d.avail_note = t.avail_note != null ? t.avail_note : d.avail_note;
                    d.rate_remote = t.rate_remote != null ? t.rate_remote : d.rate_remote;
                    d.rate_onsite = t.rate_onsite != null ? t.rate_onsite : d.rate_onsite;
                    d.rate_note = t.rate_note != null ? t.rate_note : d.rate_note;
                    // Anzeige-String
                    const parts = [];
                    if (d.rate_remote) parts.push(d.rate_remote + ' remote');
                    if (d.rate_onsite) parts.push(d.rate_onsite + ' vor Ort');
                    if (parts.length) d.rate = parts.join(' / ') + ' €';
                    const cache = window._matchingContactCache || {};
                    if (cache[d.id]) Object.assign(cache[d.id], d);

                    let crmPart = '';
                    if (alsoCrm && d.crm_contact_id && res.crm_updated !== true) {
                        // Fallback: direkt CRM patchen
                        return _saveCrmFields(d, {
                            verfuegbar_ab_c: d.available_from || '',
                            verfuegbar_tage_pro_woche_c: d.avail_days_per_week != null ? d.avail_days_per_week : '',
                            verfuegbar_hinweis_c: d.avail_note || '',
                            satz_remote_c: d.rate_remote || '',
                            satz_vor_ort_c: d.rate_onsite || '',
                        }, msg).then(crmRes => {
                            crmPart = crmRes.ok ? ' · CRM-Default aktualisiert' : ' · CRM-Default fehlgeschlagen';
                            if (msg) {
                                msg.style.color = crmRes.ok ? '#16a34a' : '#d97706';
                                msg.textContent = 'Match gespeichert' + crmPart;
                            }
                            const live = (window._matchingAvailLive || {})[d.id] || { gulp: null, fm: null, note: '' };
                            live.note = 'Match-Konditionen gespeichert' + crmPart;
                            _renderAvailBox(document.getElementById('matching-avail-box'), d, live);
                            return { ok: true };
                        });
                    }
                    if (msg) {
                        msg.style.color = '#16a34a';
                        msg.textContent = 'Match gespeichert'
                            + (res.crm_updated ? ' · CRM-Default aktualisiert' : (alsoCrm ? '' : ' (nur diese Anfrage)'));
                    }
                    const live = (window._matchingAvailLive || {})[d.id] || { gulp: null, fm: null, note: '' };
                    live.note = msg ? msg.textContent : '';
                    _renderAvailBox(document.getElementById('matching-avail-box'), d, live);
                    return { ok: true };
                });
        };
        if (detail) return run(detail);
        return _fetchMatchDetail(matchId).then(run);
    }

    function _loadMatchTerms(detail) {
        if (!detail || !detail.id) return Promise.resolve(detail);
        return _jsonGet('/shaduler/api/matching/terms/' + encodeURIComponent(detail.id) + '/')
            .then(res => {
                if (!res || !res.ok || !res.terms) return detail;
                const t = res.terms;
                if (t.avail_from) detail.available_from = _normDate(t.avail_from);
                if (t.avail_days_per_week != null && t.avail_days_per_week !== '') {
                    detail.avail_days_per_week = t.avail_days_per_week;
                }
                if (t.avail_note) detail.avail_note = t.avail_note;
                if (t.rate_remote) detail.rate_remote = t.rate_remote;
                if (t.rate_onsite) detail.rate_onsite = t.rate_onsite;
                if (t.rate_note) detail.rate_note = t.rate_note;
                const parts = [];
                if (detail.rate_remote) parts.push(detail.rate_remote + ' remote');
                if (detail.rate_onsite) parts.push(detail.rate_onsite + ' vor Ort');
                if (parts.length) detail.rate = parts.join(' / ') + ' €';
                return detail;
            })
            .catch(() => detail);
    }

    function adoptAvailability(matchId, source) {
        const detail = (window._matchingContactCache || {})[matchId];
        const live = (window._matchingAvailLive || {})[matchId] || {};
        let date = '';
        if (source === 'gulp') date = (live.gulp && live.gulp.date) || (detail && detail.available_gulp) || '';
        else if (source === 'fm') date = (live.fm && live.fm.date) || (detail && detail.available_fm) || '';
        else date = source;
        const run = function (d) {
            const inp = document.getElementById('matching-avail-input');
            if (inp && date) inp.value = _normDate(date);
            const also = document.getElementById('matching-terms-also-crm');
            if (also) also.checked = true;
            return saveMatchTerms(d.id, { focus: 'avail' });
        };
        if (detail) return run(detail);
        return _fetchMatchDetail(matchId).then(run);
    }

    function _cvUrlFor(detail) {
        if (detail.cv_editor_url) return detail.cv_editor_url;
        if (detail.crm_contact_id) {
            return '/crm/api/berater/' + encodeURIComponent(detail.crm_contact_id) + '/cv/';
        }
        return '';
    }

    function openCv(matchId) {
        const detail = (window._matchingContactCache || {})[matchId];
        const go = function (d) {
            const url = _cvUrlFor(d || {});
            if (!url) {
                alert('Kein CV-Link — bitte zuerst im CRM öffnen.');
                return;
            }
            window.open(url, '_blank', 'noopener');
        };
        if (detail) go(detail);
        else _fetchMatchDetail(matchId).then(go);
    }

    function createCvTask(matchId, kind) {
        const detail = (window._matchingContactCache || {})[matchId];
        const run = function (d) {
            const name = (d && d.name) || 'Berater';
            const kinds = {
                pruefen: {
                    titel: 'CV prüfen — ' + name,
                    beschreibung: 'CV gegen Anfrage/Profil prüfen.\n'
                        + (d.gulp_id ? ('Gulp-ID: ' + d.gulp_id + '\n') : '')
                        + (d.freelancermap ? ('FM: ' + d.freelancermap + '\n') : '')
                        + (d.available_from ? ('CRM verfügbar ab: ' + _fmtDate(d.available_from) + '\n') : '')
                        + (d.available_gulp ? ('Gulp verfügbar ab: ' + _fmtDate(d.available_gulp) + '\n') : '')
                        + (d.available_fm ? ('FM verfügbar ab: ' + _fmtDate(d.available_fm) + '\n') : ''),
                },
                aktualisieren: {
                    titel: 'CV aktualisieren — ' + name,
                    beschreibung: 'CV aus Gulp/FM/CRM aktualisieren bzw. neu generieren.\n'
                        + (d.gulp_id ? ('Gulp-ID: ' + d.gulp_id + '\n') : '')
                        + (d.freelancermap ? ('FM: ' + d.freelancermap + '\n') : ''),
                },
                generieren: {
                    titel: 'CV generieren — ' + name,
                    beschreibung: 'CV neu erzeugen (CV-Extractor / CRM).\n'
                        + (d.crm_contact_id ? ('CRM: ' + d.crm_contact_id + '\n') : ''),
                },
            };
            const k = kinds[kind] || kinds.pruefen;
            const statusEl = document.getElementById('matching-cv-task-msg');
            if (statusEl) {
                statusEl.style.color = '#666';
                statusEl.textContent = 'Aufgabe wird angelegt…';
            }
            _jsonPost('/shaduler/api/aufgaben/create/', {
                art: 'dokument',
                titel: k.titel.slice(0, 240),
                beschreibung: k.beschreibung,
                ref_type: 'berater',
                ref_id: String(d.crm_contact_id || d.gulp_id || matchId),
                prioritaet: 3,
            }).then(res => {
                if (!statusEl) return;
                if (res && res.ok) {
                    statusEl.style.color = '#16a34a';
                    statusEl.textContent = 'Aufgabe angelegt: ' + k.titel;
                } else {
                    statusEl.style.color = '#dc2626';
                    statusEl.textContent = 'Aufgabe fehlgeschlagen: ' + ((res && res.error) || 'unbekannt');
                }
            });
        };
        if (detail) run(detail);
        else _fetchMatchDetail(matchId).then(run);
    }

    function _openContactPopup(detail) {
        _closeContactPopup();
        const stage = _normStage(detail.stage);
        const tpl = _stageMailTpl(stage);
        const scorePct = Math.round((detail.match_score || 0) * 100);
        const crmUrl = detail.crm_contact_id
            ? ('/crm/berater/?detail=' + encodeURIComponent(detail.crm_contact_id))
            : '';
        const skills = (detail.skills || []).slice(0, 10).join(' · ');
        const phones = (detail.phones && detail.phones.length)
            ? detail.phones
            : (detail.phone ? [{ label: 'Tel', number: detail.phone }] : []);
        const emails = (detail.emails && detail.emails.length)
            ? detail.emails
            : (detail.email ? [detail.email] : []);
        const cvUrl = _cvUrlFor(detail);

        const phoneHtml = phones.length
            ? phones.map(p => {
                const num = p.number || p.nummer || p.raw || '';
                return `<div style="display:flex;align-items:center;gap:6px;margin-bottom:2px">
                  <span style="color:#888;min-width:48px">${_esc(p.label || 'Tel')}</span>
                  <b style="flex:1">${_esc(num)}</b>
                  <button type="button" class="matching-btn-sm" style="font-size:10px;padding:2px 6px"
                          onclick="Matching.call('${detail.id}','${_escAttr(num)}')">
                    <i class="bi bi-telephone"></i>
                  </button>
                </div>`;
            }).join('')
            : '<span style="color:#aaa">—</span>';

        const mailHtml = emails.length
            ? emails.map(em => {
                const e = typeof em === 'string' ? em : (em.email || '');
                return `<div style="display:flex;align-items:center;gap:6px;margin-bottom:2px">
                  <span style="flex:1;word-break:break-all">${_esc(e)}</span>
                  <button type="button" class="matching-btn-sm" style="font-size:10px;padding:2px 6px"
                          onclick="Matching.sendEmail('${detail.id}','${_escAttr(stage)}')">
                    <i class="bi bi-envelope"></i>
                  </button>
                </div>`;
            }).join('')
            : '<span style="color:#aaa">— keine E-Mail im CRM</span>';

        const ov = document.createElement('div');
        ov.id = 'matching-contact-ovl';
        ov.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,.45);z-index:10050;display:flex;align-items:center;justify-content:center;padding:16px';
        ov.onclick = function (e) { if (e.target === ov) _closeContactPopup(); };
        ov.innerHTML = `
        <div style="background:#fff;border-radius:10px;max-width:520px;width:100%;box-shadow:0 12px 40px rgba(0,0,0,.25);overflow:hidden;max-height:92vh;display:flex;flex-direction:column">
          <div style="display:flex;align-items:center;gap:8px;padding:12px 14px;background:var(--abcona-blue,#163258);color:#fff">
            <i class="bi bi-person-badge"></i>
            <div style="flex:1;min-width:0">
              <b style="display:block;font-size:14px">${_esc(detail.name || 'Kontakt')}</b>
              <span style="font-size:11px;opacity:.85">${_esc(_stageLabel(stage))} · ${scorePct}%</span>
            </div>
            <button type="button" style="background:transparent;border:0;color:#fff;font-size:18px;cursor:pointer"
                    onclick="Matching.closeContactPopup()">×</button>
          </div>
          <div style="padding:14px;font-size:12px;line-height:1.45;overflow:auto">
            <div style="display:grid;grid-template-columns:100px 1fr;gap:7px 12px;margin-bottom:12px">
              <span style="color:#888">Matching</span>
              <span><b>${scorePct}%</b>
                ${detail.match_reason ? ' · <i style="color:#666">' + _esc(detail.match_reason) + '</i>' : ''}
              </span>
              <span style="color:#888">Stand</span><span>${_esc(_stageLabel(stage))}</span>
              ${detail.company ? '<span style="color:#888">Firma</span><span>' + _esc(detail.company) + '</span>' : ''}
              <span style="color:#888">Ort</span><span>${_esc(_fixText(detail.location || detail.address || '—'))}</span>
              ${detail.address && detail.location && detail.address.indexOf(detail.location) < 0
                ? '<span style="color:#888">Adresse</span><span>' + _esc(detail.address) + '</span>' : ''}
              ${detail.gulp_id ? '<span style="color:#888">Gulp-ID</span><span>' + _esc(String(detail.gulp_id)) + '</span>' : ''}
              ${detail.freelancermap ? '<span style="color:#888">FM</span><span style="word-break:break-all">' + _esc(String(detail.freelancermap)) + '</span>' : ''}
              ${detail.aid ? '<span style="color:#888">AID</span><span>' + _esc(String(detail.aid)) + '</span>' : ''}
              <span style="color:#888">Kondition</span>
              <div style="display:grid;gap:4px">
                <div style="display:flex;align-items:center;gap:6px;flex-wrap:wrap">
                  <span style="color:#888;min-width:52px;font-size:10px">Remote</span>
                  <input type="text" id="matching-rate-remote" value="${_escAttr(detail.rate_remote || '')}"
                         placeholder="€" inputmode="decimal"
                         style="font-size:11px;padding:3px 6px;border:1px solid #cbd5e1;border-radius:4px;width:72px"
                         onclick="event.stopPropagation()">
                  <span style="color:#888;min-width:52px;font-size:10px">vor Ort</span>
                  <input type="text" id="matching-rate-onsite" value="${_escAttr(detail.rate_onsite || '')}"
                         placeholder="€" inputmode="decimal"
                         style="font-size:11px;padding:3px 6px;border:1px solid #cbd5e1;border-radius:4px;width:72px"
                         onclick="event.stopPropagation()">
                </div>
                <input type="text" id="matching-rate-note" value="${_escAttr(detail.rate_note || '')}"
                       placeholder="Hinweis Preis (Reise, Spesen…)"
                       style="font-size:11px;padding:3px 6px;border:1px solid #cbd5e1;border-radius:4px;width:100%;box-sizing:border-box"
                       onclick="event.stopPropagation()">
                <div style="font-size:10px;color:#888">${_esc(detail.rate ? ('Anzeige: ' + detail.rate) : '')}</div>
              </div>
              ${detail.crm_type ? '<span style="color:#888">Typ</span><span>' + _esc(detail.crm_type) + '</span>' : ''}
              ${detail.crm_status ? '<span style="color:#888">CRM-Status</span><span>' + _esc(detail.crm_status) + '</span>' : ''}
              ${skills ? '<span style="color:#888">Skills</span><span>' + _esc(skills) + '</span>' : ''}
              <span style="color:#888">Telefon</span><div>${phoneHtml}</div>
              <span style="color:#888">E-Mail</span><div>${mailHtml}</div>
            </div>

            <div style="border:1px solid #e8edf4;border-radius:8px;padding:10px 12px;margin-bottom:12px;background:#f8fafc"
                 onclick="event.stopPropagation()" onmousedown="event.stopPropagation()">
              <div style="display:flex;align-items:center;gap:6px;margin-bottom:6px;font-weight:600;font-size:12px;color:#163258;flex-wrap:wrap">
                <i class="bi bi-calendar2-check"></i> Verfügbarkeit & Konditionen
                <span style="font-weight:400;font-size:10px;color:#888">Match · CRM · Gulp · FM</span>
              </div>
              <div style="display:grid;gap:6px;margin-bottom:8px">
                <div style="display:flex;align-items:center;gap:6px;flex-wrap:wrap">
                  <label style="font-size:10px;color:#888;min-width:70px">Ab</label>
                  <input type="date" id="matching-avail-input" value="${_escAttr(_normDate(detail.available_from) || '')}"
                         style="font-size:11px;padding:3px 6px;border:1px solid #cbd5e1;border-radius:4px">
                  <input type="text" id="matching-avail-text" value="" placeholder="oder TT.MM.JJJJ"
                         style="font-size:11px;padding:3px 6px;border:1px solid #cbd5e1;border-radius:4px;width:110px"
                         onchange="(function(el){var d=Matching._normDatePublic&&Matching._normDatePublic(el.value);var i=document.getElementById('matching-avail-input');if(d&&i)i.value=d;})(this)">
                  <label style="font-size:10px;color:#888">Tage/Wo</label>
                  <input type="number" id="matching-avail-days" min="1" max="7" step="1"
                         value="${_escAttr(detail.avail_days_per_week != null ? detail.avail_days_per_week : '')}"
                         style="font-size:11px;padding:3px 6px;border:1px solid #cbd5e1;border-radius:4px;width:56px">
                </div>
                <input type="text" id="matching-avail-note" value="${_escAttr(detail.avail_note || '')}"
                       placeholder="Hinweis Verfügbarkeit (nur Mo–Mi, keine Reise…)"
                       style="font-size:11px;padding:3px 6px;border:1px solid #cbd5e1;border-radius:4px;width:100%;box-sizing:border-box">
                <label style="font-size:11px;display:flex;align-items:center;gap:6px;color:#334155">
                  <input type="checkbox" id="matching-terms-also-crm" ${detail.crm_contact_id ? '' : 'disabled'}>
                  Auch als CRM-Default speichern
                </label>
                <div style="display:flex;gap:6px;flex-wrap:wrap">
                  <button type="button" class="matching-btn-sm" style="font-size:10px;padding:2px 8px"
                          onclick="Matching.saveMatchTerms('${detail.id}')"
                          ${detail.id ? '' : 'disabled'}>
                    <i class="bi bi-save"></i> Für diese Anfrage speichern
                  </button>
                  <button type="button" class="matching-btn-sm" style="font-size:10px;padding:2px 8px"
                          onclick="Matching.saveAvailability('${detail.id}')">
                    Nur Verfügbarkeit
                  </button>
                  <button type="button" class="matching-btn-sm" style="font-size:10px;padding:2px 8px"
                          onclick="Matching.saveRate('${detail.id}')">
                    Nur Preise
                  </button>
                </div>
              </div>
              <div id="matching-avail-box"></div>
              <div id="matching-terms-msg" style="font-size:10px;min-height:14px;margin-top:4px"></div>
              <div id="matching-avail-msg" style="display:none"></div>
              <div id="matching-rate-msg" style="display:none"></div>
            </div>

            <div style="display:flex;flex-wrap:wrap;gap:6px;border-top:1px solid #e8edf4;padding-top:12px">
              <button type="button" class="matching-btn-primary" style="font-size:11px"
                      ${detail.phone ? '' : 'disabled title="Keine Nummer"'}
                      onclick="Matching.call('${detail.id}')">
                <i class="bi bi-telephone"></i> Anrufen
              </button>
              <button type="button" class="matching-btn-primary" style="font-size:11px"
                      onclick="Matching.sendEmail('${detail.id}','${_escAttr(stage)}')">
                <i class="bi bi-envelope"></i> ${_esc(tpl.label)}
              </button>
              ${stage === 'interview' ? `
              <button type="button" class="matching-btn-sm" style="font-size:11px"
                      onclick="Matching.sendEmail('${detail.id}','interview','absage')">
                <i class="bi bi-x-circle"></i> Absage
              </button>` : ''}
              ${cvUrl ? `
              <button type="button" class="matching-btn-sm" style="font-size:11px"
                      onclick="Matching.openCv('${detail.id}')">
                <i class="bi bi-file-earmark-text"></i> CV öffnen
              </button>` : ''}
              <button type="button" class="matching-btn-sm" style="font-size:11px"
                      onclick="Matching.createCvTask('${detail.id}','pruefen')">
                <i class="bi bi-clipboard-check"></i> Aufgabe: CV prüfen
              </button>
              <button type="button" class="matching-btn-sm" style="font-size:11px"
                      onclick="Matching.createCvTask('${detail.id}','aktualisieren')">
                <i class="bi bi-arrow-repeat"></i> Aufgabe: CV aktualisieren
              </button>
              ${crmUrl ? `
              <a class="matching-btn-sm" style="font-size:11px;text-decoration:none;display:inline-flex;align-items:center;gap:4px"
                 href="${_escAttr(crmUrl)}" target="_blank" rel="noopener">
                <i class="bi bi-box-arrow-up-right"></i> Im CRM öffnen
              </a>` : `
              <span style="font-size:11px;color:#b45309;align-self:center">Kein CRM-Link — Name-Suche ohne Treffer</span>`}
            </div>
            <div id="matching-cv-task-msg" style="font-size:11px;min-height:14px;margin-top:8px"></div>
          </div>
        </div>`;
        document.body.appendChild(ov);
        _renderAvailBox(document.getElementById('matching-avail-box'), detail, {
            gulp: detail.gulp_id ? { loading: true } : null,
            fm: detail.freelancermap ? { loading: true } : null,
        });
        _startAvailabilityCompare(detail);
    }

    function closeContactPopup() { _closeContactPopup(); }

    function kanbanCardClick(matchId) {
        const ov = document.createElement('div');
        ov.id = 'matching-contact-ovl';
        ov.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,.35);z-index:10050;display:flex;align-items:center;justify-content:center';
        ov.innerHTML = '<div style="background:#fff;padding:20px 28px;border-radius:8px;font-size:13px;color:#666"><i class="bi bi-hourglass-split"></i> Kontakt wird geladen…</div>';
        document.body.appendChild(ov);
        _fetchMatchDetail(matchId).then(_openContactPopup);
    }

    function call(matchId, phoneNumber) {
        const cached = (window._matchingContactCache || {})[matchId];
        const run = function (phone) {
            if (!phone) {
                phone = prompt(_kiT('err_phone_prompt', 'Telefonnummer eingeben:'));
            }
            if (!phone) return;
            let clean = String(phone).replace(/[^\d+]/g, '').replace(/^\+/, '00');
            if (clean.length < 6) {
                alert(_t('matching.call_invalid') !== 'matching.call_invalid'
                    ? _t('matching.call_invalid')
                    : 'Ungültige Nummer');
                return;
            }
            const wdCfg = window.MATCHING_CONFIG?.webdial || window.ABPE_CONFIG?.webdial || {};
            const cgi = wdCfg.url || 'http://172.20.3.120/cgi-bin/webdial.cgi';
            const from = wdCfg.from || '12';
            const channel = wdCfg.channel || 'SIP/12';
            const context = wdCfg.context || 'from-internal';
            const timeout = wdCfg.timeout || 10;
            const url = `${cgi}?from=${from}&channel=${channel}&context=${context}&timeout=${timeout}&to=${clean}`;
            window.open(url, 'webdial', 'height=100,width=100');
        };
        if (phoneNumber) { run(phoneNumber); return; }
        if (cached && cached.phone) { run(cached.phone); return; }
        _fetchMatchDetail(matchId).then(d => run(d.phone || ''));
    }

    function sendEmail(matchId, stage, variant) {
        const start = (window._matchingContactCache || {})[matchId]
            ? Promise.resolve(window._matchingContactCache[matchId])
            : _fetchMatchDetail(matchId);
        start.then(detail => {
            const st = _normStage(stage || detail.stage);
            const tpl = _stageMailTpl(st, variant);
            const ctx = Object.assign(_projectContext(), {
                name: detail.name || '',
                location: detail.location || detail.address || '',
                start: '',
            });
            if (!ctx.customer) ctx.customer = detail.company || '';
            const subject = _fillTpl(tpl.subject, ctx);
            const body = _fillTpl(tpl.body, ctx);
            _openStageMailComposer({
                matchId: matchId,
                detail: detail,
                stage: st,
                variant: variant || '',
                nextStatus: variant === 'absage' ? 'absage' : tpl.nextStatus,
                actionLabel: tpl.label,
                to: detail.email || _pickEmail(detail.emails, ''),
                subject: subject,
                body: body,
            });
        });
    }

    function _closeStageMailComposer() {
        const ov = document.getElementById('matching-mail-ovl');
        if (ov) ov.remove();
    }

    function _openStageMailComposer(opts) {
        _closeStageMailComposer();
        const ov = document.createElement('div');
        ov.id = 'matching-mail-ovl';
        ov.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,.45);z-index:10060;display:flex;align-items:center;justify-content:center;padding:16px';
        ov.onclick = function (e) { if (e.target === ov) _closeStageMailComposer(); };
        ov.innerHTML = `
        <div style="background:#fff;border-radius:10px;max-width:560px;width:100%;box-shadow:0 12px 40px rgba(0,0,0,.25);max-height:90vh;overflow:auto">
          <div style="display:flex;align-items:center;gap:8px;padding:12px 14px;background:var(--abcona-blue,#163258);color:#fff">
            <i class="bi bi-envelope"></i>
            <b style="flex:1">${_esc(opts.actionLabel || 'E-Mail')} — ${_esc(opts.detail.name || '')}</b>
            <button type="button" style="background:transparent;border:0;color:#fff;font-size:18px;cursor:pointer"
                    onclick="document.getElementById('matching-mail-ovl')?.remove()">×</button>
          </div>
          <div style="padding:14px;display:grid;gap:8px">
            <label style="font-size:11px;color:#666">An
              <input id="mm-to" class="matching-form-input" style="width:100%;margin-top:3px"
                     type="email" value="${_escAttr(opts.to)}">
            </label>
            <label style="font-size:11px;color:#666">Betreff
              <input id="mm-subj" class="matching-form-input" style="width:100%;margin-top:3px"
                     value="${_escAttr(opts.subject)}">
            </label>
            <label style="font-size:11px;color:#666">Nachricht
              <textarea id="mm-body" class="matching-form-textarea" rows="10"
                        style="width:100%;margin-top:3px;font-family:inherit">${_esc(opts.body)}</textarea>
            </label>
            <div id="mm-msg" style="font-size:11px;min-height:16px"></div>
            <div style="display:flex;gap:8px;justify-content:flex-end;flex-wrap:wrap">
              <button type="button" class="matching-btn-sm"
                      onclick="document.getElementById('matching-mail-ovl')?.remove()">Abbrechen</button>
              <button type="button" class="matching-btn-primary" id="mm-send"
                      onclick="Matching.submitStageMail()">
                <i class="bi bi-send"></i> Senden${opts.nextStatus ? ' & Status' : ''}
              </button>
            </div>
          </div>
        </div>`;
        document.body.appendChild(ov);
        window._matchingMailDraft = opts;
        const toEl = document.getElementById('mm-to');
        if (toEl && !toEl.value) toEl.focus();
    }

    function _bodyTextToHtml(txt) {
        return '<div>' + _esc(txt).replace(/\n/g, '<br>') + '</div>';
    }

    function submitStageMail() {
        const draft = window._matchingMailDraft || {};
        const to = ((document.getElementById('mm-to') || {}).value || '').trim();
        const subj = ((document.getElementById('mm-subj') || {}).value || '').trim();
        const body = ((document.getElementById('mm-body') || {}).value || '').trim();
        const msg = document.getElementById('mm-msg');
        const sendBtn = document.getElementById('mm-send');
        function show(ok, text) {
            if (!msg) return;
            msg.style.color = ok ? '#155724' : '#b91c1c';
            msg.textContent = text || '';
        }
        if (!to || to.indexOf('@') < 0) { show(false, 'Bitte gültige E-Mail (An) angeben'); return; }
        if (!subj) { show(false, 'Betreff fehlt'); return; }
        if (!body) { show(false, 'Nachricht fehlt'); return; }
        if (sendBtn) { sendBtn.disabled = true; sendBtn.innerHTML = '…'; }
        show(true, 'Wird gesendet …');

        const payload = {
            template_identifier: 'crm_manual_email',
            to_email: to,
            subject: subj,
            body: _bodyTextToHtml(body),
            contact_name: (draft.detail && draft.detail.name) || '',
            crm_id: (draft.detail && draft.detail.crm_contact_id) || '',
        };

        fetch('/crm/api/email/send/', {
            method: 'POST',
            credentials: 'same-origin',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrf(),
                'X-Requested-With': 'XMLHttpRequest',
            },
            body: JSON.stringify(payload),
        })
        .then(r => r.json().then(j => ({ ok: r.ok, j: j })))
        .then(pack => {
            const j = pack.j || {};
            if (!(pack.ok && j.ok !== false && j.success !== false && !j.error)) {
                throw new Error(j.error || 'Senden fehlgeschlagen');
            }
            const next = draft.nextStatus;
            if (next && draft.matchId) {
                return fetch(API + 'match/' + draft.matchId + '/move/', {
                    method: 'POST',
                    credentials: 'same-origin',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': csrf(),
                    },
                    body: JSON.stringify({ status: next }),
                }).then(() => next);
            }
            return null;
        })
        .then(moved => {
            _closeStageMailComposer();
            _closeContactPopup();
            if (moved) {
                // Board neu laden
                const content = document.getElementById('content-kanban');
                if (content) {
                    content.dataset.loaded = '0';
                    _loadKanban(content, document.getElementById('loading-kanban'));
                }
            }
            alert(_kiT('mail_sent', 'E-Mail gesendet') + (moved ? (' → ' + moved) : ''));
        })
        .catch(err => {
            if (sendBtn) {
                sendBtn.disabled = false;
                sendBtn.innerHTML = '<i class="bi bi-send"></i> Senden';
            }
            show(false, err.message || String(err));
        });
    }

    function closeProject(projectId) {
        const reason = document.getElementById('close-reason')?.value;
        const note   = document.getElementById('close-note')?.value || '';
        if (!confirm(_t('matching.confirm_close'))) return;
        fetch(API + 'requests/' + projectId + '/close/', {
            method: 'POST',
            credentials: 'same-origin',
            headers: { 'X-CSRFToken': csrf(), 'Content-Type': 'application/json' },
            body: JSON.stringify({ reason, note }),
        })
        .then(r => r.json())
        .then(d => {
            if (d.success) {
                alert(_t('matching.project_closed'));
                const c = document.getElementById('content-anfragen');
                if (c) c.dataset.loaded = '0';
                switchTab('anfragen');
                _loadStats();
            } else {
                alert(_t('matching.err_generic') + ': ' + d.error);
            }
        });
    }

    function sendContract(matchId) {
        alert(_t('matching.contract_phase2'));
    }

    function savePlacementDetails(matchId, projectId) {
        const data = {
            agreed_rate:                parseFloat(document.getElementById('rate-'+matchId)?.value) || null,
            agreed_start_date:          document.getElementById('start-'+matchId)?.value || null,
            agreed_duration:            parseInt(document.getElementById('duration-'+matchId)?.value) || null,
            placed_at:                  document.getElementById('placedat-'+matchId)?.value || null,
            placement_notes:            document.getElementById('notes-'+matchId)?.value || '',
            client_contract_received:   document.getElementById('contract-received-'+matchId)?.checked || false,
            client_contract_received_at:document.getElementById('contract-date-'+matchId)?.value || null,
            client_contract_channel:    document.getElementById('contract-channel-'+matchId)?.value || '',
            client_contract_note:       document.getElementById('contract-note-'+matchId)?.value || '',
            client_contract_sender:     document.getElementById('contract-sender-'+matchId)?.value || '',
        };
        fetch(API + 'match/' + matchId + '/placement/', {
            method: 'POST',
            credentials: 'same-origin',
            headers: { 'X-CSRFToken': csrf(), 'Content-Type': 'application/json' },
            body: JSON.stringify(data),
        })
        .then(r => r.json())
        .then(d => {
            if (d.success) {
                // kurze Bestätigung
                const btn = document.querySelector(`button[onclick*="savePlacementDetails('${matchId}'"]`);
                if (btn) { btn.style.background='#155724'; setTimeout(()=>btn.style.background='',2000); }
            } else {
                alert(_t('matching.err_generic') + ': ' + d.error);
            }
        });
    }

    function sendPlacementStart(matchId) {
        alert(_t('matching.placement_mail_phase2'));
    }

    // ──────────────────────────────────────────────────
    // KANBAN DRAG & DROP
    // ──────────────────────────────────────────────────

    let _dragMatchId = null;

    function kanbanDragStart(event, matchId) {
        _dragMatchId = matchId;
        event.dataTransfer.effectAllowed = 'move';
        event.target.style.opacity = '0.5';
    }

    function kanbanDrop(event, colId) {
        event.preventDefault();
        if (!_dragMatchId) return;

        // Karte visuell verschieben
        const card = document.querySelector(`[data-match-id="${_dragMatchId}"]`);
        const targetCol = document.getElementById('col-' + colId);
        if (card && targetCol) {
            card.style.opacity = '1';
            targetCol.appendChild(card);
            // Leerer-Hinweis entfernen
            const emptyHint = targetCol.querySelector('div[style*="aaa"]');
            if (emptyHint) emptyHint.remove();
            // Zähler aktualisieren
            _updateKanbanCounts();
        }

        // Status via API aktualisieren
        fetch(API + 'match/' + _dragMatchId + '/move/', {
            method: 'POST',
            credentials: 'same-origin',
            headers: { 'X-CSRFToken': csrf(), 'Content-Type': 'application/json' },
            body: JSON.stringify({ status: colId }),
        })
        .then(r => r.json())
        .then(d => {
            if (!d.success) console.error('Kanban move fehlgeschlagen:', d.error);
        });

        _dragMatchId = null;
    }

    function _updateKanbanCounts() {
        document.querySelectorAll('.matching-kanban-col').forEach(col => {
            const colId  = col.dataset.colId;
            const body   = document.getElementById('col-' + colId);
            const head   = col.querySelector('.matching-kanban-head');
            const cnt    = head?.querySelector('.matching-kanban-cnt');
            if (body && cnt) {
                const cards = body.querySelectorAll('.matching-card').length;
                cnt.textContent = cards;
            }
        });
    }

    // ──────────────────────────────────────────────────
    // HILFSFUNKTIONEN
    // ──────────────────────────────────────────────────

    function _val(id) {
        const el = document.getElementById(id);
        return el ? el.value : '';
    }

    function _setText(id, val) {
        const el = document.getElementById(id);
        if (el) el.textContent = val;
    }

    function _statusPill(status) {
        const map = {
            'draft':       'pill-draft',
            'active':      'pill-active',
            'matching':    'pill-matching',
            'offers_sent': 'pill-active',
            'interviews':  'pill-matching',
            'placed':      'pill-placed',
            'not_placed':  'pill-archived',
            'cancelled':   'pill-archived',
            'archived':    'pill-archived',
        };
        return map[status] || 'pill-draft';
    }

    function _statusLabel(status) {
        return _t('matching.status_' + status) || status;
    }

    return {
        init, applyI18n, switchTab, newRequest,
        openProject, openRequestEdit, saveRequestEdit, pickShortlistRequest, pickKanbanRequest, runMatching, rematch, saveNewRequest,
        updateThreshold, filterShortlistSource, sendAllAboveThreshold,
        openOutreachWizard, closeOutreachWizard, outreachGoto, outreachSkip,
        outreachPolish, outreachReloadDraft, outreachSend,
        outreachPickEmail, outreachApplyEmail,
        outreachApplyMulti, outreachRemoveMulti, outreachAddMultiEmail, outreachSearchMulti,
        outreachSetMailTarget, outreachUnifiedSearch, outreachUnifiedApply,
        toggleArchiveDetail, searchAnfragen, filterAnfragen,
        searchAccounts, searchContacts, call, sendEmail,
        kanbanDragStart, kanbanDrop, kanbanCardClick,
        closeContactPopup, submitStageMail, openCv, createCvTask,
        saveAvailability, adoptAvailability, saveRate, saveMatchTerms,
        _normDatePublic: _normDate,
        closeProject, sendContract, sendPlacementStart, savePlacementDetails,
        openKiWizard, closeKiWizard, runKiExtract, applyKiExtract,
        fillSkillsFromText,
        pickCrmContact, pickCrmContactIndex, hideCrmSuggest, createCrmContactFromSuggest,
        openNewContactPopup, closeNewContactPopup,
        runFirmaWebEnrich, applyFirmaWebEnrichToCrm,
        pickCrmAccountIndex, clearCustomerLink, pickAccountFromSearch,
    };

})();
