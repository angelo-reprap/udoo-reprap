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
            case 'shortlist': _renderShortlistPlaceholder(content, loading); break;
            case 'kanban':    _renderKanbanPlaceholder(content, loading); break;
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
                                 onclick="Matching.openProject('${p.id}','shortlist')">
                                <div class="matching-prio ${prioClass}"></div>
                                <div style="min-width:100px;font-size:10px;color:#888">${p.project_number}</div>
                                <div style="flex:1;font-weight:700;font-size:12px">${p.title}</div>
                                <div style="font-size:11px;color:#666;min-width:100px">${p.customer_name}</div>
                                <span class="matching-pill ${pillClass}">${_statusLabel(p.status)}</span>
                                <div style="font-size:10px;color:#888;min-width:50px;text-align:right">
                                    ${p.match_count ? p.match_count + _t('matching.matches_count') : '—'}
                                </div>
                            </div>
                            <div style="display:flex;gap:4px;margin-top:6px;justify-content:flex-end"
                                 onclick="event.stopPropagation()">
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
                           oninput="Matching.searchAccounts(this.value)">
                    <div id="new-customer-results" style="display:none"></div>
                    <input type="hidden" id="new-crm-account-id">
                </div>
                <div class="matching-form-group">
                    <label class="matching-form-label">${_t('matching.neu_contact')}</label>
                    <input class="matching-form-input" id="new-contact"
                           placeholder="${_t('matching.contact_placeholder')}"
                           oninput="Matching.searchContacts(this.value)">
                    <div id="new-contact-results" style="display:none"></div>
                </div>
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
    }

    // ──────────────────────────────────────────────────
    // PLACEHOLDERS
    // ──────────────────────────────────────────────────

    function _renderShortlistPlaceholder(content, loading) {
        if (loading) loading.style.display = 'none';
        content.innerHTML = `<div style="padding:30px;text-align:center;color:#888">
            <i class="bi bi-funnel" style="font-size:32px;display:block;margin-bottom:8px"></i>
            ${_t('matching.no_shortlist')}
        </div>`;
        content.dataset.loaded = '1';
    }

    function _renderKanbanPlaceholder(content, loading) {
        _loadKanban(content, loading);
    }

    function _loadKanban(content, loading) {
        const projectId = window.MATCHING_CONFIG.activeProject;
        if (!projectId) {
            if (loading) loading.style.display = 'none';
            content.innerHTML = `<div style="padding:30px;text-align:center;color:#888">
                <i class="bi bi-kanban" style="font-size:32px;display:block;margin-bottom:8px"></i>
                ${_t('matching.no_kanban')}
            </div>`;
            content.dataset.loaded = '1';
            return;
        }

        fetch(API + 'requests/' + projectId + '/kanban/', { credentials: 'same-origin' })
            .then(r => r.json())
            .then(d => {
                if (loading) loading.style.display = 'none';
                if (!d.success) {
                    content.innerHTML = '<p>' + _t('matching.err_load') + '</p>';
                    return;
                }

                let html = `
                <div style="margin-bottom:10px;font-size:12px;color:#888">
                    ${d.project_number} · ${d.project_title} · ${d.total} ${_t('matching.matches_count')}
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
                             ondragstart="${isBelowThreshold ? '' : `Matching.kanbanDragStart(event,'${card.id}')`}"
                             onclick="Matching.kanbanCardClick('${card.id}')">
                            <div style="display:flex;justify-content:space-between;align-items:start">
                                <div style="font-weight:700">${card.name}</div>
                                <div style="font-weight:700;color:${scoreColor};font-size:10px">
                                    ${Math.round(card.match_score*100)}%
                                </div>
                            </div>
                            <div style="font-size:10px;color:#888;margin-top:2px">${card.location}</div>
                            ${alertHtml}
                            ${reserveHtml}
                            <div style="display:flex;justify-content:space-between;margin-top:5px">
                                ${daysHtml}
                                <div style="display:flex;gap:3px">
                                    <button class="matching-btn-sm matching-btn-call" style="font-size:9px;padding:2px 5px"
                                            onclick="event.stopPropagation();Matching.call('${card.id}')">
                                        <i class="bi bi-telephone"></i>
                                    </button>
                                    <button class="matching-btn-sm matching-btn-mail" style="font-size:9px;padding:2px 5px"
                                            onclick="event.stopPropagation();Matching.sendEmail('${card.id}')">
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
                let html = `
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
                    <button class="matching-btn-primary" style="margin-left:auto"
                            onclick="Matching.sendAllAboveThreshold()">
                        ${_t('matching.btn_send_all_count')} (${d.above_threshold}) ↗
                    </button>
                </div>`;

                if (d.count === 0) {
                    html += `<div style="padding:30px;text-align:center;color:#888">
                        ${_t('matching.no_results')}<br>
                        <button class="matching-btn-primary" style="margin-top:10px"
                                onclick="Matching.runMatching('${projectId}')">
                            <i class="bi bi-cpu"></i> ${_t('matching.btn_match')}
                        </button>
                    </div>`;
                } else {
                    html += '<div id="shortlist-results">';
                    for (const r of d.results) {
                        const scoreClass = r.overall_score >= 0.7 ? 'score-hi' :
                                           r.overall_score >= 0.5 ? 'score-mid' : 'score-lo';
                        const opacity = r.above_threshold ? '1' : '0.4';
                        html += `
                        <div class="matching-card" style="display:flex;align-items:center;gap:8px;opacity:${opacity}"
                             data-score="${r.overall_score}" data-id="${r.id}">
                            <div class="matching-score-box ${scoreClass}">
                                ${(r.overall_score*100).toFixed(0)}%
                            </div>
                            <div style="flex:1">
                                <div style="font-weight:700;font-size:12px">${r.name}</div>
                                <div style="font-size:10px;color:#888">
                                    ${r.matched_skills?.slice(0,4).join(' · ')} · ${r.location || ''}
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
                                <a href="${r.cv_editor_url}" target="_blank"
                                   class="matching-btn-sm">CV</a>
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

                content.innerHTML = html;
                content.dataset.loaded = '1';
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
                        <label class="matching-form-label">${_kiT('ki_from', 'Äußerer Absender (optional)')}</label>
                        <input class="matching-form-input" id="matching-ki-from" style="width:100%"
                               placeholder="Name &lt;mail@…&gt;">
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
            const lines = [
                (d.success ? '✓' : '⚠') + ' ' + (d.source || '') + (d.prompt_key ? ' · ' + d.prompt_key : ''),
                fields.customer_name ? 'Kunde: ' + fields.customer_name : '',
                fields.contact_name ? 'Ansprechpartner: ' + fields.contact_name : '',
                fields.title ? 'Titel: ' + fields.title : '',
                fields.duration_months != null ? 'Dauer: ' + fields.duration_months + ' Mon.' : '',
                fields.location ? 'Standort: ' + fields.location : '',
                fields.start_date ? 'Start: ' + fields.start_date : (fields.start_asap ? 'Start: asap' : ''),
            ].filter(Boolean);
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
        _activateTab('neu');
        // Formular ggf. neu rendern lassen, dann befüllen
        const fill = () => {
            _setVal('new-customer', fields.customer_name || '');
            _setVal('new-contact', fields.contact_name || '');
            _setVal('new-title', fields.title || '');
            _setVal('new-description', fields.description || '');
            if (fields.start_date) _setVal('new-start', fields.start_date);
            if (fields.duration_months != null) _setVal('new-duration', String(fields.duration_months));
            _setVal('new-location', fields.location || '');
            if (fields.rate_max != null) _setVal('new-rate-max', String(fields.rate_max));
            else _setVal('new-rate-max', '');
            closeKiWizard();
        };
        const content = document.getElementById('content-neu');
        if (content && content.dataset.loaded !== '1') {
            setTimeout(fill, 80);
        } else {
            fill();
        }
    }

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
                // Optional: Mail-Inhalt nachladen wenn nur ID gesetzt
                if (fromMail && !(emailText || (stored && stored.email_text))) {
                    _loadMailIntoKiWizard(fromMail);
                }
            }
        } catch (e) {
            console.warn('Matching deeplink:', e);
        }
    }

    function _loadMailIntoKiWizard(mailId) {
        // Best-effort: Shaduler/EDMS Endpunkte — scheitert still, User kann Text einfügen
        const paths = [
            '/shaduler/api/inbox/' + encodeURIComponent(mailId) + '/',
            '/edms/api/mail/' + encodeURIComponent(mailId) + '/',
        ];
        const tryNext = (i) => {
            if (i >= paths.length) return;
            fetch(paths[i], { credentials: 'same-origin' })
                .then(r => r.ok ? r.json() : Promise.reject())
                .then(d => {
                    const body = d.body || d.text || d.content || d.email_text || '';
                    const sub = d.subject || '';
                    const from = d.from || d.outer_from || d.sender || '';
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

    // ──────────────────────────────────────────────────
    // AKTIONEN
    // ──────────────────────────────────────────────────

    function newRequest() { switchTab('neu'); }

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

    function runMatching(projectId) {
        if (!projectId) projectId = window.MATCHING_CONFIG.activeProject;
        fetch(API + 'requests/' + projectId + '/match/', {
            method: 'POST',
            credentials: 'same-origin',
            headers: { 'X-CSRFToken': csrf(), 'Content-Type': 'application/json' },
        })
        .then(r => r.json())
        .then(d => {
            if (d.success) {
                alert(_t('matching.matching_started'));
                const content = document.getElementById('content-shortlist');
                if (content) content.dataset.loaded = '0';
                setTimeout(() => _loadShortlistForProject(projectId,
                    document.getElementById('content-shortlist')), 3000);
            } else {
                alert(_t('matching.matching_error'));
            }
        });
    }

    function saveNewRequest() {
        const data = {
            title:           _val('new-title'),
            description:     _val('new-description'),
            customer_name:   _val('new-customer'),
            contact_name:    _val('new-contact'),
            crm_account_id:  _val('new-crm-account-id'),
            start_date:      _val('new-start') || null,
            duration_months: parseInt(_val('new-duration')) || 0,
            location:        _val('new-location'),
            rate_max:        parseInt(_val('new-rate-max')) || null,
        };
        if (!data.title || !data.customer_name) {
            alert(_t('matching.err_title_required'));
            return;
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
        document.querySelectorAll('#shortlist-results .matching-card[data-score]').forEach(card => {
            card.style.opacity = parseFloat(card.dataset.score) >= t ? '1' : '0.4';
        });
        const above = [...document.querySelectorAll('#shortlist-results .matching-card[data-score]')]
            .filter(c => parseFloat(c.dataset.score) >= t).length;
        const cnt = document.getElementById('threshold-count');
        if (cnt) cnt.textContent = above + ' ' + _t('matching.above_threshold_full');
    }

    function sendAllAboveThreshold() {
        alert(_t('matching.send_all_phase2'));
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
        if (val.length < 2) return;
        fetch(API + 'crm/accounts/?q=' + encodeURIComponent(val), { credentials: 'same-origin' })
            .then(r => r.json())
            .then(d => {
                const res = document.getElementById('new-customer-results');
                if (!res) return;
                if (!d.results?.length) { res.style.display = 'none'; return; }
                res.style.display = 'block';
                res.style.cssText = 'background:white;border:1px solid #dde3ec;border-radius:6px;padding:4px;max-height:150px;overflow-y:auto;';
                res.innerHTML = d.results.map(r =>
                    `<div style="padding:5px 8px;font-size:12px;cursor:pointer;border-radius:4px"
                          onmouseover="this.style.background='#f0f4fa'"
                          onmouseout="this.style.background=''"
                          onclick="document.getElementById('new-customer').value='${r.name}';document.getElementById('new-crm-account-id').value='${r.id}';document.getElementById('new-customer-results').style.display='none'">
                        <strong>${r.name}</strong> ${r.city ? '· '+r.city : ''}
                    </div>`
                ).join('');
            });
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

    function call(matchId, phoneNumber) {
        // Nummer holen — entweder übergeben oder via Prompt
        let phone = phoneNumber || prompt(_t('matching.err_phone_prompt'));
        if (!phone) return;

        // Nummer bereinigen
        let clean = phone.replace(/[^\d+]/g, '').replace(/^\+/, '00');
        if (clean.length < 6) { alert(_t('matching.call_invalid')); return; }

        // Webdial Config aus MATCHING_CONFIG oder ABPE_CONFIG
        const wdCfg = window.MATCHING_CONFIG?.webdial || window.ABPE_CONFIG?.webdial || {};
        const cgi     = wdCfg.url      || 'http://172.20.3.120/cgi-bin/webdial.cgi';
        const from    = wdCfg.from     || '12';
        const channel = wdCfg.channel  || 'SIP/12';
        const context = wdCfg.context  || 'from-internal';
        const timeout = wdCfg.timeout  || 10;

        // Browser-seitiger Anruf via window.open (Issabel Bookmarklet-Methode)
        const url = `${cgi}?from=${from}&channel=${channel}&context=${context}&timeout=${timeout}&to=${clean}`;
        window.open(url, 'webdial', 'height=100,width=100');

        console.log(`📞 Click-to-Call: ${from} → ${clean}`);
    }

    function sendEmail(matchId) {
        alert(_t('matching.email_phase2'));
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

    function kanbanCardClick(matchId) {
        // Detail-Modal öffnen — später implementieren
        console.log('Kanban card click:', matchId);
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
        openProject, runMatching, saveNewRequest,
        updateThreshold, sendAllAboveThreshold,
        toggleArchiveDetail, searchAnfragen, filterAnfragen,
        searchAccounts, searchContacts, call, sendEmail,
        kanbanDragStart, kanbanDrop, kanbanCardClick,
        closeProject, sendContract, sendPlacementStart, savePlacementDetails,
        openKiWizard, closeKiWizard, runKiExtract, applyKiExtract,
    };

})();
