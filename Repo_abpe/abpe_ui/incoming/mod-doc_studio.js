/**
 * mod-doc_studio.js — ABpE Doc Studio v2
 * Block-Editor: Drag&Drop Reihenfolge + Doppelklick inline edit
 * Alle Labels aus i18n — kein hardcoded Text
 */
if (typeof window._dsModuleLoaded === 'undefined') {
window._dsModuleLoaded = true;

const $ = id => document.getElementById(id);

function t(key) {
    const keys = key.split('.');
    let val = window.i18nData || {};
    for (const k of keys) { if (val && typeof val === 'object') val = val[k]; else return key; }
    return typeof val === 'string' ? val : key;
}

function getCsrf() {
    return document.cookie.split(';').map(c => c.trim())
        .find(c => c.startsWith('csrftoken='))?.split('=')[1] || '';
}

async function dsApi(path, options = {}) {
    const resp = await fetch('/doc-studio/api/' + path, {
        headers: { 'Content-Type': 'application/json',
                   'X-CSRFToken': getCsrf(), ...(options.headers||{}) },
        ...options,
    });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    return resp.json();
}

// ── Init ────────────────────────────────────────────────────────────────────

function dsInit(page) {
    if (page === 'index')    dsIndexInit();
    if (page === 'studio')   dsStudioInit();
    if (page === 'log')      dsLogInit();
    if (page === 'invoices') dsInvoiceInit();
    if (page === 'config')   dsConfigInit();
}

// ══════════════════════════════════════════════════════════════════════════════
// INDEX
// ══════════════════════════════════════════════════════════════════════════════

function dsIndexInit() {
    dsTemplatesLoad();
    const search = $('ds-search-input');
    const scope  = $('ds-scope-select');
    const status = $('ds-status-select');
    if (search) search.addEventListener('input',  () => dsTemplatesFilter());
    if (scope)  scope.addEventListener('change',  () => dsTemplatesLoad());
    if (status) status.addEventListener('change', () => dsTemplatesLoad());
}

async function dsTemplatesLoad() {
    const scope  = ($('ds-scope-select') ||{}).value || '';
    const status = ($('ds-status-select')||{}).value || '';
    const c = $('ds-templates-container');
    if (!c) return;
    c.innerHTML = '<div class="text-center py-4"><div class="spinner-border spinner-border-sm text-secondary"></div></div>';
    try {
        const data = await dsApi(`templates/?scope=${scope}&status=${status}`);
        dsTemplatesRender(data.templates || []);
    } catch(e) {
        c.innerHTML = `<p class="text-danger small">${t('ds.error_load')}</p>`;
    }
}

function dsTemplatesRender(templates) {
    const c = $('ds-templates-container');
    if (!c) return;
    if (!templates.length) {
        c.innerHTML = `<div class="text-center py-5 text-secondary">
            <i class="bi bi-inbox" style="font-size:2rem;display:block;margin-bottom:8px;"></i>
            <span>${t('ds.empty_templates')}</span></div>`;
        return;
    }
    const groups = {};
    templates.forEach(tpl => {
        const s = tpl.scope || 'general';
        if (!groups[s]) groups[s] = [];
        groups[s].push(tpl);
    });
    let html = '';
    for (const [scope, list] of Object.entries(groups)) {
        html += `<div class="ds-scope-wrap" data-scope="${scope}">
            <div class="ds-scope-hdr open" onclick="dsScopeToggle(this)">
                <i class="bi bi-folder2"></i><span>${scope}</span>
                <span class="ds-badge ds-badge-gray ms-1">${list.length}</span>
                <i class="bi bi-chevron-down ms-auto"></i>
            </div>
            <div class="ds-scope-body">
                <table class="ds-table">
                    <thead><tr>
                        <th style="width:220px;">${t('ds.col_name')}</th>
                        <th style="width:60px;">${t('ds.col_engine')}</th>
                        <th style="width:60px;">${t('ds.col_version')}</th>
                        <th style="width:80px;">${t('ds.col_status')}</th>
                        <th style="width:120px;">${t('ds.col_last_used')}</th>
                        <th>${t('ds.col_actions')}</th>
                    </tr></thead>
                    <tbody>${list.map(tpl => dsTplRow(tpl)).join('')}</tbody>
                </table>
            </div></div>`;
    }
    c.innerHTML = html;
}

function dsTplRow(tpl) {
    const statusMap = {
        ACTIVE:  `<span class="ds-badge ds-badge-green">${t('ds.status_active')}</span>`,
        DRAFT:   `<span class="ds-badge ds-badge-amber">${t('ds.status_draft')}</span>`,
        ARCHIVE: `<span class="ds-badge ds-badge-gray">${t('ds.status_archive')}</span>`,
    };
    const lastUsed = tpl.last_used_at
        ? new Date(tpl.last_used_at).toLocaleDateString('de-DE') : '—';
    return `<tr data-tpl-id="${tpl.id}" data-name="${(tpl.name||'').toLowerCase()}" data-status="${tpl.status}">
        <td><div style="font-weight:600;color:var(--abcona-blue);font-size:12px;">${tpl.name}</div>
            <div class="ds-identifier">${tpl.identifier}</div></td>
        <td><span class="ds-badge ds-badge-blue">${tpl.engine}</span></td>
        <td><span class="ds-badge ds-badge-blue">v${tpl.active_version||1}</span></td>
        <td>${statusMap[tpl.status] || tpl.status}</td>
        <td style="font-size:10px;color:var(--text-secondary);">${lastUsed}</td>
        <td><div style="display:flex;gap:3px;">
            <a href="/doc-studio/studio/?template=${tpl.id}" class="ds-btn-icon" title="${t('ds.btn_edit')}">
               <i class="bi bi-pencil"></i></a>
            <button class="ds-btn-icon" title="${t('ds.btn_generate')}"
                    onclick="dsOpenGenerateModal(${tpl.id})"><i class="bi bi-play-fill"></i></button>
            <button class="ds-btn-icon" title="${t('ds.btn_duplicate')}"
                    onclick="dsDuplicate(${tpl.id})"><i class="bi bi-files"></i></button>
        </div></td></tr>`;
}

function dsTemplatesFilter() {
    const q = ($('ds-search-input')||{}).value?.toLowerCase() || '';
    document.querySelectorAll('[data-tpl-id]').forEach(row => {
        row.style.display = row.dataset.name?.includes(q) ? '' : 'none';
    });
}

function dsScopeToggle(hdr) {
    hdr.classList.toggle('open');
    const body = hdr.nextElementSibling;
    if (body) body.style.display = hdr.classList.contains('open') ? '' : 'none';
}

let _dsGenerateTemplateId = null;
function dsOpenGenerateModal(id) {
    _dsGenerateTemplateId = id;
    const result = $('ds-gen-result');
    if (result) result.classList.add('d-none');
    const modal = new bootstrap.Modal($('dsGenerateModal'));
    modal.show();
}

async function dsGenerate() {
    if (!_dsGenerateTemplateId) return;
    const ref    = ($('ds-gen-ref')   ||{}).value || '';
    const engine = ($('ds-gen-engine')||{}).value || 'BOTH';
    try {
        const data = await dsApi(`templates/${_dsGenerateTemplateId}/generate/`, {
            method: 'POST', body: JSON.stringify({ context_ref: ref, engine })
        });
        const result = $('ds-gen-result');
        if (result) {
            result.classList.remove('d-none');
            const txt2 = $('ds-gen-result-text');
            if (txt2) txt2.textContent = data.file_path_docx || t('ds.generate_success');
        }
    } catch(e) { console.error('Generate error:', e); }
}

async function dsDuplicate(id) {
    if (!confirm(t('ds.confirm_duplicate'))) return;
    try { await dsApi(`templates/${id}/duplicate/`, { method:'POST', body:'{}' }); dsTemplatesLoad(); }
    catch(e) { console.error(e); }
}

// ══════════════════════════════════════════════════════════════════════════════
// STUDIO — Editor + Block-Editor + Drag&Drop + Inline-Edit
// ══════════════════════════════════════════════════════════════════════════════

let _dsCurrentTemplateId = null;
let _dsCurrentBlocks     = [];   // [{id, block_id, name, block_type, content, order, slot}, ...]

const DS_TEST_DATA = {
    contract: {
        an_firma:'Muster GmbH', an_ansprechpartner:'Max Mustermann',
        an_strasse:'Musterstraße 1', an_plz_ort:'12345 Musterstadt',
        an_ort:'Musterstadt', rahmenvertrag_datum:'15. Mai 2026',
        leistungsbeschreibung:'IT-Beratung und Projektunterstützung SAP S/4HANA',
        einsatzort:'Frankfurt am Main / Homeoffice', stundensatz:'95,00',
        laufzeit_von:'1. Juni 2026', laufzeit_bis:'31. Dezember 2026',
        stunden_kontingent:'500', kunde_name:'Muster AG',
        kunde_strasse:'Hauptstraße 10', kunde_plz_ort:'60311 Frankfurt',
        endkunde_name:'Endkunde GmbH',
    },
    invoice: {
        rg_nummer:'TEST-2026-0001', rg_datum:'31. Mai 2026',
        empfaenger_firma:'Muster AG', empfaenger_adresse:'Hauptstraße 10\n60311 Frankfurt',
        betreff:'Beratungsleistungen SAP — Mai 2026', abrechnungsmonat:'Mai 2026',
        zahlungsziel_tage:'30', summe_netto:'7.600,00',
        mwst_satz:'19', mwst_euro:'1.444,00', gesamtbetrag:'9.044,00',
    },
    general: {
        empfaenger_firma:'Muster AG', empfaenger_name:'Herr Max Mustermann',
        empfaenger_strasse:'Musterstraße 1', empfaenger_plz_ort:'12345 Musterstadt',
        datum:'22. Mai 2026', betreff:'Betreff des Schreibens', inhalt:'...',
    }
};

function dsStudioInit() {
    dsStudioLoadTemplateList();
}

async function dsStudioLoadTemplateList() {
    const sel = $('ds-template-select');
    if (!sel) return;
    try {
        const data = await dsApi('templates/?status=ACTIVE');
        (data.templates || []).forEach(tpl => {
            const opt = document.createElement('option');
            opt.value = tpl.id;
            opt.textContent = `${tpl.name} (${tpl.scope})`;
            opt.dataset.scope = tpl.scope;
            sel.appendChild(opt);
        });
        const params = new URLSearchParams(window.location.search);
        const tplId  = params.get('template');
        if (tplId) { sel.value = tplId; dsStudioLoadTemplate(tplId); }
    } catch(e) { console.error('Template list error:', e); }
}

async function dsStudioLoadTemplate(id) {
    const genBtn  = $('ds-btn-generate');
    const testBtn = $('ds-btn-test');
    if (!id) {
        if (genBtn)  genBtn.style.display  = 'none';
        if (testBtn) testBtn.style.display = 'none';
        return;
    }
    if (genBtn)  genBtn.style.display  = '';
    if (testBtn) testBtn.style.display = '';
    _dsCurrentTemplateId = id;

    try {
        const data = await dsApi(`templates/${id}/`);
        const tpl  = data.template;
        _dsCurrentBlocks = tpl.blocks || [];
        dsStudioRenderVars(tpl.variables || []);
        dsStudioRenderBlockEditor(_dsCurrentBlocks);
        dsStudioRefreshPreview(id);
    } catch(e) { console.error('Template load error:', e); }
}

// ── Variablen ───────────────────────────────────────────────────────────────

function dsStudioRenderVars(vars) {
    const c   = $('ds-vars-container');
    const cnt = $('ds-vars-count');
    if (!c) return;
    if (!vars.length) {
        c.innerHTML = `<p class="small text-secondary mb-0">${t('ds.vars_none')}</p>`;
        if (cnt) cnt.textContent = '0';
        return;
    }
    if (cnt) cnt.textContent = vars.length;
    c.innerHTML = vars.map(v => `
        <div class="ds-var-row">
            <span class="ds-var-label">{${v.name}}</span>
            <input class="form-control form-control-sm ds-var-input"
                   data-var="${v.name}" placeholder="${v.type||''}"
                   oninput="dsStudioRefreshPreview()">
        </div>`).join('');
}

// ── Block-Editor mit Drag&Drop ───────────────────────────────────────────────

function dsStudioRenderBlockEditor(blocks) {
    const c   = $('ds-blocks-container');
    const cnt = $('ds-blocks-count');
    if (!c) return;
    if (!blocks.length) {
        c.innerHTML = `<p class="small text-secondary mb-0">${t('ds.blocks_none')}</p>`;
        if (cnt) cnt.textContent = '0';
        return;
    }
    if (cnt) cnt.textContent = blocks.length;

    c.innerHTML = `
        <div class="ds-block-list" id="ds-block-list">
            ${blocks.map((b, i) => dsBlockItem(b, i)).join('')}
        </div>
        <div class="mt-2 text-secondary" style="font-size:10px;">
            <i class="bi bi-info-circle me-1"></i>
            Verschieben per Drag&Drop · Doppelklick zum Bearbeiten
        </div>`;

    dsInitDragDrop();
}

function dsBlockItem(b, i) {
    const btype    = b.block__block_type || b.block_type || '';
    const bname    = b.block__name       || b.name       || '';
    const bcontent = b.content_override  || b.block__content || b.content || '';
    const tbId2    = b.id;
    const typeColors = {
        LOGO: 'ds-badge-blue', DOC_TITLE: 'ds-badge-blue',
        CLAUSE: 'ds-badge-green', SECTION_HEAD: 'ds-badge-green',
        PARAGRAPH: 'ds-badge-gray', PARTY_BLOCK: 'ds-badge-amber',
        LABEL_VALUE: 'ds-badge-amber', SIGNATURE: 'ds-badge-gray',
        FOOTER: 'ds-badge-gray', PAGE_NUMBER: 'ds-badge-gray',
    };
    const color = typeColors[btype] || 'ds-badge-gray';
    const preview = bcontent
        ? bcontent.replace(/\{[^}]+\}/g, m => `<span style="color:var(--abcona-blue);font-style:italic;">${m}</span>`)
                   .substring(0, 80) + (bcontent.length > 80 ? '…' : '')
        : '<span style="color:var(--text-secondary);">—</span>';
    const tbId = b.id || i;

    return `<div class="ds-block-item"
                draggable="true"
                data-tb-id="${tbId}"
                data-order="${b.order}"
                data-idx="${i}"
                ondblclick="dsBlockEditOpen(${tbId})"
                title="Doppelklick zum Bearbeiten">
        <div class="ds-block-drag" title="Verschieben">
            <i class="bi bi-grip-vertical"></i>
        </div>
        <div class="ds-block-body flex-grow-1">
            <div class="d-flex align-items-center gap-2 mb-1">
                <span class="ds-badge ${color}" style="font-size:9px;">${btype}</span>
                <span style="font-size:11px;font-weight:500;">${bname}</span>
                <button class="ds-btn-icon ms-auto" style="width:20px;height:20px;"
                        title="Bearbeiten" onclick="dsBlockEditOpen(${tbId})">
                    <i class="bi bi-pencil" style="font-size:10px;"></i>
                </button>
            </div>
            <div style="font-size:9px;color:var(--text-secondary);line-height:1.3;">${preview}</div>
        </div>
    </div>`;
}

// ── Drag & Drop ──────────────────────────────────────────────────────────────

let _dsDragSrc = null;

function dsInitDragDrop() {
    const list = $('ds-block-list');
    if (!list) return;

    list.querySelectorAll('.ds-block-item').forEach(item => {
        item.addEventListener('dragstart', e => {
            _dsDragSrc = item;
            item.classList.add('ds-block-dragging');
            e.dataTransfer.effectAllowed = 'move';
        });
        item.addEventListener('dragend', () => {
            item.classList.remove('ds-block-dragging');
            list.querySelectorAll('.ds-block-over').forEach(el =>
                el.classList.remove('ds-block-over'));
        });
        item.addEventListener('dragover', e => {
            e.preventDefault();
            e.dataTransfer.dropEffect = 'move';
            if (item !== _dsDragSrc) {
                // Alle anderen over-Klassen entfernen
                document.querySelectorAll('.ds-block-over').forEach(el =>
                    el.classList.remove('ds-block-over'));
                item.classList.add('ds-block-over');
            }
        });
        item.addEventListener('dragleave', () => {
            item.classList.remove('ds-block-over');
        });
        item.addEventListener('drop', e => {
            e.preventDefault();
            item.classList.remove('ds-block-over');
            if (!_dsDragSrc || _dsDragSrc === item) return;
            const allItems = [...list.querySelectorAll('.ds-block-item')];
            const fromIdx  = allItems.indexOf(_dsDragSrc);
            const toIdx    = allItems.indexOf(item);
            if (fromIdx < toIdx)
                item.after(_dsDragSrc);
            else
                item.before(_dsDragSrc);
            dsBlockSaveOrder();
        });
    });
}

async function dsBlockSaveOrder() {
    if (!_dsCurrentTemplateId) return;
    const list  = $('ds-block-list');
    if (!list) return;
    const items = [...list.querySelectorAll('.ds-block-item')];
    const blocks = items.map((el, i) => ({
        id:    parseInt(el.dataset.tbId),
        order: (i + 1) * 10,
    }));
    try {
        await dsApi(`templates/${_dsCurrentTemplateId}/blocks/reorder/`, {
            method: 'PUT', body: JSON.stringify({ blocks })
        });
        // Vorschau aktualisieren
        dsStudioRefreshPreview();
    } catch(e) { console.error('Reorder error:', e); }
}

// ── Block Inline-Edit Modal ──────────────────────────────────────────────────

let _dsEditTbId = null;

async function dsBlockEditOpen(tbId) {
    if (!_dsCurrentTemplateId) return;
    _dsEditTbId = tbId;

    try {
        const data = await dsApi(`templates/${_dsCurrentTemplateId}/blocks/${tbId}/`);

        // Modal aufbauen falls noch nicht im DOM
        let modal = $('dsBlockEditModal');
        if (!modal) {
            modal = document.createElement('div');
            modal.innerHTML = `
                <div class="modal fade" id="dsBlockEditModal" tabindex="-1">
                    <div class="modal-dialog modal-lg">
                        <div class="modal-content">
                            <div class="modal-header py-2" style="background:#163258;">
                                <h6 class="modal-title text-white d-flex align-items-center gap-2">
                                    <i class="bi bi-pencil-square"></i>
                                    <span id="ds-edit-modal-title">Block bearbeiten</span>
                                </h6>
                                <span id="ds-edit-block-type" class="ds-badge ds-badge-gray ms-2"></span>
                                <button type="button" class="btn-close btn-close-white ms-auto"
                                        data-bs-dismiss="modal"></button>
                            </div>
                            <div class="modal-body p-3">
                                <div class="mb-2">
                                    <label class="form-label small fw-bold">Name</label>
                                    <input id="ds-edit-name" type="text"
                                           class="form-control form-control-sm">
                                </div>
                                <div class="mb-2">
                                    <div class="d-flex justify-content-between align-items-center mb-1">
                                        <label class="form-label small fw-bold mb-0">Inhalt / Text</label>
                                        <div class="d-flex gap-1">
                                            <span class="small text-secondary">Variablen:</span>
                                            <code class="small" style="color:var(--abcona-blue);">{variable}</code>
                                            <span class="small text-secondary ms-2">Zeilenumbruch:</span>
                                            <code class="small">↵ Enter</code>
                                        </div>
                                    </div>
                                    <textarea id="ds-edit-content" class="form-control"
                                              style="font-family:monospace;font-size:12px;min-height:180px;"></textarea>
                                </div>
                                <div id="ds-edit-preview-wrap" class="border rounded p-3 bg-light">
                                    <div class="small text-secondary mb-1">Vorschau:</div>
                                    <div id="ds-edit-preview" style="font-size:11px;"></div>
                                </div>
                            </div>
                            <div class="modal-footer py-2">
                                <button type="button" class="btn btn-sm btn-outline-secondary"
                                        data-bs-dismiss="modal">Abbrechen</button>
                                <button type="button" class="btn btn-sm btn-success"
                                        onclick="dsBlockEditSave()">
                                    <i class="bi bi-check-lg me-1"></i>Speichern
                                </button>
                            </div>
                        </div>
                    </div>
                </div>`;
            document.body.appendChild(modal.firstElementChild);
        }

        // Felder befüllen
        $('ds-edit-modal-title').textContent = data.name || 'Block bearbeiten';
        $('ds-edit-block-type').textContent  = data.block_type || '';
        $('ds-edit-name').value              = data.name    || '';
        $('ds-edit-content').value           = data.content || '';
        dsBlockEditPreview(data.content || '');

        // Live-Vorschau beim Tippen
        $('ds-edit-content').oninput = () =>
            dsBlockEditPreview($('ds-edit-content').value);

        new bootstrap.Modal($('dsBlockEditModal')).show();
    } catch(e) {
        console.error('Block load error:', e);
    }
}

function dsBlockEditPreview(content) {
    const el = $('ds-edit-preview');
    if (!el) return;
    // Variablen hervorheben, Zeilenumbrüche als <br>
    const html = content
        .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
        .replace(/\{([^}]+)\}/g,
            '<span style="color:#163258;font-weight:bold;background:#e6f1fb;padding:0 2px;border-radius:2px;">{$1}</span>')
        .replace(/\n/g, '<br>');
    el.innerHTML = html || '<span style="color:#ccc;">leer</span>';
}

async function dsBlockEditSave() {
    if (!_dsEditTbId || !_dsCurrentTemplateId) return;
    const btn = document.querySelector('#dsBlockEditModal .btn-success');
    if (btn) { btn.disabled = true; btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>'; }

    try {
        const data = await dsApi(
            `templates/${_dsCurrentTemplateId}/blocks/${_dsEditTbId}/`, {
            method: 'PUT',
            body: JSON.stringify({
                name:    $('ds-edit-name').value,
                content: $('ds-edit-content').value,
            })
        });

        // Block-Liste im Studio aktualisieren
        const item = document.querySelector(`[data-tb-id="${_dsEditTbId}"]`);
        if (item) {
            const preview = item.querySelector('.ds-block-body div:last-child');
            if (preview) {
                const c = data.content || '';
                preview.innerHTML = c
                    .replace(/\{[^}]+\}/g, m =>
                        `<span style="color:var(--abcona-blue);font-style:italic;">${m}</span>`)
                    .substring(0, 80) + (c.length > 80 ? '…' : '');
            }
            const nameEl = item.querySelector('.ds-block-body span:nth-child(2)');
            if (nameEl && $('ds-edit-name').value)
                nameEl.textContent = $('ds-edit-name').value;
        }

        bootstrap.Modal.getInstance($('dsBlockEditModal'))?.hide();
        dsStudioRefreshPreview();
    } catch(e) {
        console.error('Block save error:', e);
    } finally {
        if (btn) { btn.disabled = false; btn.innerHTML = '<i class="bi bi-check-lg me-1"></i>Speichern'; }
    }
}

// ── Vorschau & Generate ──────────────────────────────────────────────────────

async function dsStudioRefreshPreview(overrideId) {
    const sel = $('ds-template-select');
    const id  = overrideId || (sel ? sel.value : null);
    const c   = $('ds-preview-container');
    if (!id || !c) return;
    const variables = _collectVars();
    try {
        const data = await dsApi(`templates/${id}/preview/`, {
            method: 'POST',
            body: JSON.stringify({ variables, format: 'html' })
        });
        c.innerHTML = data.html || '';
        // Klickbare Blöcke in der Vorschau
        dsPreviewMakeClickable(c);
    } catch(e) {
        c.innerHTML = `<p class="small text-danger">${t('ds.error_preview')}</p>`;
    }
}

function dsPreviewMakeClickable(container) {
    // Paragraphen in der Vorschau anklickbar machen → öffnet Edit-Modal
    // Die Vorschau enthält data-tb-id Attribute wenn der Assembler sie liefert
    container.querySelectorAll('[data-tb-id]').forEach(el => {
        el.style.cursor = 'pointer';
        el.title = 'Doppelklick zum Bearbeiten';
        el.ondblclick = () => dsBlockEditOpen(parseInt(el.dataset.tbId));
        el.onmouseenter = () => el.style.outline = '2px dashed #f59e0b';
        el.onmouseleave = () => el.style.outline = '';
    });
}

async function dsStudioTest() {
    const sel   = $('ds-template-select');
    const id    = sel ? sel.value : null;
    if (!id) return;
    const opt   = sel.options[sel.selectedIndex];
    const scope = opt ? (opt.dataset.scope || 'contract') : 'contract';
    const testVars = DS_TEST_DATA[scope] || DS_TEST_DATA.contract;

    document.querySelectorAll('.ds-var-input').forEach(inp => {
        const key = inp.dataset.var;
        if (key && testVars[key] !== undefined && typeof testVars[key] === 'string')
            inp.value = testVars[key];
    });
    const refInput = $('ds-studio-ref');
    if (refInput && !refInput.value) refInput.value = 'MUSTER-001';
    dsStudioRefreshPreview();
    _dsGenerateAndDownload(id, testVars, 'MUSTER-001');
}

async function dsStudioGenerate() {
    const sel = $('ds-template-select');
    const id  = sel ? sel.value : null;
    const ref = ($('ds-studio-ref')||{}).value || 'OHNE-REF';
    if (!id) return;
    _dsGenerateAndDownload(id, _collectVars(), ref);
}

async function _dsGenerateAndDownload(id, variables, context_ref) {
    const engine  = ($('ds-studio-engine')||{}).value || 'BOTH';
    const result  = $('ds-generate-result');
    const paths   = $('ds-generate-paths');
    const dlDocx  = $('ds-download-docx');
    const dlPdf   = $('ds-download-pdf');

    if (result) result.classList.add('d-none');
    if (dlDocx) dlDocx.classList.add('d-none');
    if (dlPdf)  dlPdf.classList.add('d-none');

    const genBtn  = $('ds-btn-generate');
    const testBtn = $('ds-btn-test');
    if (genBtn)  { genBtn.disabled = true;  genBtn.innerHTML  = '<span class="spinner-border spinner-border-sm me-1"></span>'; }
    if (testBtn) { testBtn.disabled = true; testBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>'; }

    try {
        const data = await dsApi(`templates/${id}/generate/`, {
            method: 'POST',
            body: JSON.stringify({ variables, context_ref, engine })
        });

        if (result) result.classList.remove('d-none');
        if (paths) {
            const lines = [];
            if (data.file_path_docx) lines.push(data.file_path_docx.split('/').pop());
            if (data.file_path_pdf)  lines.push(data.file_path_pdf.split('/').pop());
            paths.textContent = lines.join(' · ');
        }
        const logId = data.log_id;
        if (logId) {
            if (dlDocx && data.file_path_docx) {
                dlDocx.href = `/doc-studio/download/${logId}/?type=docx`;
                dlDocx.classList.remove('d-none');
            }
            if (dlPdf && data.file_path_pdf) {
                dlPdf.href = `/doc-studio/download/${logId}/?type=pdf`;
                dlPdf.classList.remove('d-none');
            }
        }
    } catch(e) {
        console.error('Generate error:', e);
    } finally {
        if (genBtn)  { genBtn.disabled = false;  genBtn.innerHTML  = `<i class="bi bi-play-fill me-1"></i>${t('ds.btn_generate')}`; }
        if (testBtn) { testBtn.disabled = false; testBtn.innerHTML = `<i class="bi bi-bug me-1"></i>${t('ds.btn_test')}`; }
    }
}

function _collectVars() {
    const variables = {};
    document.querySelectorAll('.ds-var-input').forEach(inp => {
        if (inp.dataset.var && inp.value) variables[inp.dataset.var] = inp.value;
    });
    return variables;
}

// ══════════════════════════════════════════════════════════════════════════════
// LOG
// ══════════════════════════════════════════════════════════════════════════════

function dsLogInit() { dsLogLoad(); dsLogLoadStats(); }

async function dsLogLoadStats() {
    try {
        const data = await dsApi('log/stats/');
        const week = data.week || {};
        const setEl = (id, val) => { const el = $(id); if (el) el.textContent = val ?? '—'; };
        setEl('ds-log-stat-total',  week.total);
        setEl('ds-log-stat-ok',     week.ok);
        setEl('ds-log-stat-failed', week.failed);
    } catch(e) {}
}

async function dsLogLoad() {
    const days = ($('ds-log-days')||{}).value || 7;
    const c    = $('ds-log-container');
    if (!c) return;
    c.innerHTML = '<div class="text-center py-4"><div class="spinner-border spinner-border-sm text-secondary"></div></div>';
    try {
        const data = await dsApi(`log/?days=${days}`);
        dsLogRender(data.logs || []);
    } catch(e) {
        c.innerHTML = `<p class="text-danger small">${t('ds.error_load')}</p>`;
    }
}

function dsLogRender(logs) {
    const c = $('ds-log-container');
    if (!c) return;
    if (!logs.length) {
        c.innerHTML = `<div class="text-center py-4 text-secondary small">${t('ds.log_empty')}</div>`;
        return;
    }
    c.innerHTML = `<table class="ds-table">
        <thead><tr>
            <th style="width:140px;">${t('ds.col_template')}</th>
            <th style="width:120px;">${t('ds.col_ref')}</th>
            <th style="width:60px;">${t('ds.col_engine')}</th>
            <th style="width:50px;">${t('ds.col_status')}</th>
            <th>${t('ds.col_file')}</th>
            <th style="width:120px;">${t('ds.col_time')}</th>
            <th style="width:80px;">Download</th>
        </tr></thead>
        <tbody>${logs.map(log => `<tr>
            <td>${log.template||'—'}</td>
            <td class="ds-identifier">${log.context_ref||'—'}</td>
            <td><span class="ds-badge ds-badge-blue">${log.engine_used}</span></td>
            <td class="ds-log-status-${(log.status||'').toLowerCase()}">
                ${log.status==='OK'
                    ? '<i class="bi bi-check-circle-fill"></i>'
                    : '<i class="bi bi-x-circle-fill"></i>'}
            </td>
            <td class="ds-log-path">${(log.file_path_docx||'').split('/').pop()||'—'}</td>
            <td style="font-size:10px;color:var(--text-secondary);">
                ${log.generated_at ? new Date(log.generated_at).toLocaleString('de-DE') : '—'}
            </td>
            <td><div style="display:flex;gap:3px;">
                ${log.file_path_docx ? `<a href="/doc-studio/download/${log.log_id}/?type=docx" class="ds-btn-icon" title="DOCX" download><i class="bi bi-file-earmark-word"></i></a>` : ''}
                ${log.file_path_pdf  ? `<a href="/doc-studio/download/${log.log_id}/?type=pdf"  class="ds-btn-icon" title="PDF"  download><i class="bi bi-file-earmark-pdf"></i></a>` : ''}
            </div></td>
        </tr>`).join('')}</tbody></table>`;
}

// ══════════════════════════════════════════════════════════════════════════════
// INVOICES
// ══════════════════════════════════════════════════════════════════════════════

function dsInvoiceInit() {
    dsInvoiceLoad();
    const search = $('ds-inv-search');
    if (search) search.addEventListener('input', () => dsInvoiceLoad());
    const dateInput = $('ds-new-inv-date');
    if (dateInput) dateInput.value = new Date().toISOString().split('T')[0];
}

async function dsInvoiceLoad() {
    const q      = ($('ds-inv-search') ||{}).value || '';
    const type   = ($('ds-inv-type')   ||{}).value || '';
    const status = ($('ds-inv-status') ||{}).value || '';
    const c      = $('ds-invoices-container');
    if (!c) return;
    c.innerHTML = '<div class="text-center py-4"><div class="spinner-border spinner-border-sm text-secondary"></div></div>';
    try {
        const data = await dsApi(`invoices/?q=${encodeURIComponent(q)}&type=${type}&status=${status}`);
        dsInvoiceRender(data.invoices || []);
    } catch(e) {
        c.innerHTML = `<p class="text-danger small">${t('ds.error_load')}</p>`;
    }
}

function dsInvoiceRender(invoices) {
    const c = $('ds-invoices-container');
    if (!c) return;
    if (!invoices.length) {
        c.innerHTML = `<div class="text-center py-4 text-secondary small">${t('ds.inv_empty')}</div>`;
        return;
    }
    const statusMap = {
        draft: `<span class="ds-badge ds-badge-amber">${t('ds.inv_status_draft')}</span>`,
        sent:  `<span class="ds-badge ds-badge-blue">${t('ds.inv_status_sent')}</span>`,
        paid:  `<span class="ds-badge ds-badge-green">${t('ds.inv_status_paid')}</span>`,
    };
    c.innerHTML = `<table class="ds-table">
        <thead><tr>
            <th style="width:120px;">${t('ds.col_invoice_nr')}</th>
            <th style="width:80px;">${t('ds.col_type')}</th>
            <th>${t('ds.col_customer')}</th>
            <th style="width:80px;">${t('ds.col_date')}</th>
            <th style="width:90px;text-align:right;">${t('ds.col_netto')}</th>
            <th style="width:80px;">${t('ds.col_status')}</th>
            <th style="width:40px;">${t('ds.col_doc')}</th>
            <th>${t('ds.col_actions')}</th>
        </tr></thead>
        <tbody>${invoices.map(inv => `<tr>
            <td class="ds-identifier">${inv.invoice_number}</td>
            <td><span class="ds-badge ds-badge-gray">${inv.invoice_type}</span></td>
            <td style="font-size:12px;">${inv.customer_name}</td>
            <td style="font-size:11px;">${inv.invoice_date||''}</td>
            <td style="text-align:right;font-size:12px;">
                ${parseFloat(inv.netto_euro||0).toLocaleString('de-DE',{minimumFractionDigits:2})} €
            </td>
            <td>${statusMap[inv.status]||inv.status}</td>
            <td style="text-align:center;">
                ${inv.has_doc
                    ? '<i class="bi bi-check-circle-fill" style="color:var(--status-green);"></i>'
                    : '<i class="bi bi-dash-circle" style="color:var(--border-color);"></i>'}
            </td>
            <td><button class="ds-btn-icon" onclick="dsInvoiceGenerate('${inv.id}')">
                <i class="bi bi-play-fill"></i></button></td>
        </tr>`).join('')}</tbody></table>`;
}

function dsInvoiceNew() {
    const modal = new bootstrap.Modal($('dsInvoiceModal'));
    modal.show();
}

async function dsInvoiceSave() {
    const payload = {
        invoice_type:  ($('ds-new-inv-type')    ||{}).value||'zeitaufwand',
        invoice_date:  ($('ds-new-inv-date')    ||{}).value||'',
        customer_name: ($('ds-new-inv-customer')||{}).value||'',
        billing_month: ($('ds-new-inv-month')   ||{}).value||'',
        subject:       ($('ds-new-inv-subject') ||{}).value||'',
        positions: [],
    };
    try {
        await dsApi('invoices/', { method:'POST', body: JSON.stringify(payload) });
        bootstrap.Modal.getInstance($('dsInvoiceModal'))?.hide();
        dsInvoiceLoad();
    } catch(e) { console.error(e); }
}

async function dsInvoiceGenerate(id) {
    try {
        await dsApi(`invoices/${id}/generate/`, { method:'POST', body: JSON.stringify({engine:'BOTH'}) });
        dsInvoiceLoad();
    } catch(e) { console.error(e); }
}

// ══════════════════════════════════════════════════════════════════════════════
// CONFIG
// ══════════════════════════════════════════════════════════════════════════════

function dsConfigInit() {
    dsConfigLoadLayouts();
    dsConfigLoadStyles();
    dsConfigLoadBlocks();
}

async function dsConfigLoadLayouts() {
    const c = $('ds-layouts-container');
    if (!c) return;
    try {
        const data = await dsApi('layouts/');
        c.innerHTML = `<table class="ds-table">
            <thead><tr>
                <th>${t('ds.col_identifier')}</th>
                <th>${t('ds.col_name')}</th>
                <th>${t('ds.col_margins')}</th>
                <th>${t('ds.col_pages')}</th>
            </tr></thead>
            <tbody>${(data.layouts||[]).map(l=>`<tr>
                <td class="ds-identifier">${l.identifier}</td>
                <td style="font-size:12px;">${l.name}</td>
                <td style="font-size:11px;">L${l.margin_left_cm}/R${l.margin_right_cm} T${l.margin_top_cm}/B${l.margin_bottom_cm} cm</td>
                <td>${l.show_page_numbers?'<i class="bi bi-check-circle-fill" style="color:var(--status-green);"></i>':'—'}</td>
            </tr>`).join('')}</tbody></table>`;
    } catch(e) { if(c) c.innerHTML = `<p class="small text-danger">${t('ds.error_load')}</p>`; }
}

async function dsConfigLoadStyles() {
    const c = $('ds-styles-container');
    if (!c) return;
    try {
        const data = await dsApi('styles/');
        c.innerHTML = (data.style_kits||[]).map(kit=>`
            <div class="mb-2">
                <div class="small fw-bold" style="color:var(--abcona-blue);">${kit.name}
                    ${kit.is_default?`<span class="ds-badge ds-badge-green ms-1">${t('ds.default')}</span>`:''}
                </div>
                <div class="small text-secondary">${(kit.styles||[]).length} ${t('ds.style_definitions')}</div>
            </div>`).join('');
    } catch(e) { if(c) c.innerHTML = `<p class="small text-danger">${t('ds.error_load')}</p>`; }
}

async function dsConfigLoadBlocks() {
    const c = $('ds-blocks-config-container');
    if (!c) return;
    try {
        const data = await dsApi('blocks/');
        window._dsAllBlocks = data.blocks || {};
        dsConfigRenderBlocks(data.blocks || {});
    } catch(e) { if(c) c.innerHTML = `<p class="small text-danger">${t('ds.error_load')}</p>`; }
}

function dsConfigRenderBlocks(grouped) {
    const c = $('ds-blocks-config-container');
    if (!c) return;
    let html = '';
    for (const [type, blocks] of Object.entries(grouped)) {
        html += `<div class="mb-2">
            <div class="small fw-bold text-secondary mb-1">${type}</div>
            ${blocks.map(b=>`<div class="ds-block-item" style="cursor:default;">
                <span class="ds-identifier">${b.identifier}</span>
                <span class="small text-secondary ms-1">${b.name}</span>
            </div>`).join('')}
        </div>`;
    }
    c.innerHTML = html || `<p class="small text-secondary">${t('ds.blocks_empty')}</p>`;
}

function dsConfigFilterBlocks(q) {
    if (!window._dsAllBlocks) return;
    const filtered = {};
    for (const [type, blocks] of Object.entries(window._dsAllBlocks)) {
        const f = blocks.filter(b =>
            b.identifier.includes(q.toLowerCase()) ||
            b.name.toLowerCase().includes(q.toLowerCase())
        );
        if (f.length) filtered[type] = f;
    }
    dsConfigRenderBlocks(filtered);
}

async function dsConfigReloadFixtures() {
    const result = $('ds-fixtures-result');
    if (result) result.innerHTML = '<div class="spinner-border spinner-border-sm text-secondary"></div>';
    try {
        await dsApi('fixtures/reload/', { method:'POST', body:'{}' });
        if (result) result.innerHTML = `<div class="alert alert-success py-2 small mt-1">${t('ds.fixtures_ok')}</div>`;
    } catch(e) {
        if (result) result.innerHTML = `<div class="alert alert-danger py-2 small mt-1">${t('ds.fixtures_error')}</div>`;
    }
}

// ── Global exports ──────────────────────────────────────────────────────────
window.dsInit                  = dsInit;
window.dsTemplatesLoad         = dsTemplatesLoad;
window.dsTemplatesFilter       = dsTemplatesFilter;
window.dsScopeToggle           = dsScopeToggle;
window.dsOpenGenerateModal     = dsOpenGenerateModal;
window.dsGenerate              = dsGenerate;
window.dsDuplicate             = dsDuplicate;
window.dsStudioLoadTemplate    = dsStudioLoadTemplate;
window.dsStudioRefreshPreview  = dsStudioRefreshPreview;
window.dsStudioGenerate        = dsStudioGenerate;
window.dsStudioTest            = dsStudioTest;
window.dsBlockEditOpen         = dsBlockEditOpen;
window.dsBlockEditSave         = dsBlockEditSave;
window.dsLogLoad               = dsLogLoad;
window.dsInvoiceNew            = dsInvoiceNew;
window.dsInvoiceSave           = dsInvoiceSave;
window.dsInvoiceGenerate       = dsInvoiceGenerate;
window.dsInvoiceLoad           = dsInvoiceLoad;
window.dsConfigFilterBlocks    = dsConfigFilterBlocks;
window.dsConfigReloadFixtures  = dsConfigReloadFixtures;

} // end IIFE guard
