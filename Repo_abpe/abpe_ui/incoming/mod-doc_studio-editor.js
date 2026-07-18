/**
 * mod-doc_studio-editor.js — ABpE Doc Studio v4
 * Word-ähnlicher inline Editor — sauber neu geschrieben
 *
 * ARCHITEKTUR:
 *   Server (assembly_preview.py) → liefert fertige ds-preview-page Divs
 *   JS (_buildDocument)          → nimmt diese Divs 1:1, setzt nur Editor-Events
 *   KEIN eigenes Seiten-Splitting mehr im JS
 */
(function () {

'use strict';

let _mode='editor', _tplId=null, _allVars=[], _allBlocks=[];
let _layout={w:21,h:29.7,t:4.2,b:5.2,l:3.0,r:3.0};
let _undoStack=[], _currentEdit=null, _dragging=null, _copiedVar=null, _toastTimer=null;

const TYPE_COLOR={
    LOGO:'ds-badge-blue', DOC_TITLE:'ds-badge-blue',
    CLAUSE:'ds-badge-green', SECTION_HEAD:'ds-badge-green',
    PARAGRAPH:'ds-badge-gray', PARTY_BLOCK:'ds-badge-amber',
    LABEL_VALUE:'ds-badge-amber', SIGNATURE:'ds-badge-gray',
    FOOTER:'ds-badge-gray', INV_HEADER:'ds-badge-blue',
    INV_META:'ds-badge-blue', INV_SUBJECT:'ds-badge-blue',
    TIME_TABLE:'ds-badge-green', AP_TABLE:'ds-badge-green',
    TOTAL_BLOCK:'ds-badge-amber', CLOSING:'ds-badge-gray',
};

// ── Init ──────────────────────────────────────────────────────────────────

window.dsStudioInit = function() {
    console.log('[DocStudio] Init');
    _loadTemplateList();
};

async function _loadTemplateList() {
    const sel = _el('ds-template-select');
    if (!sel) return;
    try {
        const data = await _api('templates/?status=ACTIVE');
        (data.templates||[]).forEach(tpl => {
            const o = document.createElement('option');
            o.value = tpl.id;
            o.textContent = `${tpl.name} (${tpl.scope})`;
            o.dataset.scope = tpl.scope || 'contract';
            sel.appendChild(o);
        });
        const id = new URLSearchParams(location.search).get('template');
        if (id) { sel.value = id; dsStudioLoadTemplate(id); }
    } catch(e) {
        console.error('[DocStudio] Template-Liste Fehler:', e);
    }
}

// ── Template laden ────────────────────────────────────────────────────────

window.dsStudioLoadTemplate = async function(id) {
    const g=_el('ds-btn-generate'), t=_el('ds-btn-test');
    if(g) g.style.display = id ? '' : 'none';
    if(t) t.style.display = id ? '' : 'none';
    if(!id) return;
    _tplId = id;
    console.log('[DocStudio] Lade Template ID:', id);
    try {
        const data = await _api(`templates/${id}/`);
        const tpl  = data.template;
        _allVars   = tpl.variables  || [];
        _allBlocks = tpl.blocks     || [];
        if(tpl.layout_css) {
            _layout = tpl.layout_css;
            console.log('[DocStudio] Layout geladen:', _layout);
        }
        window._dsAllVars = _allVars; if(typeof dsRenderVars==="function"){dsRenderVars(_allVars);if(typeof dsInjectListStyles==="function")dsInjectListStyles();};
        _renderBlocksLeft(_allBlocks);
        await _loadPreview();
    } catch(e) {
        console.error('[DocStudio] Template laden Fehler:', e);
    }
};

// ── Variablen ─────────────────────────────────────────────────────────────

function _renderVars(vars) {
    // Delegiert an ds-vars-renderer.js
    window._dsAllVars = vars;
    if (typeof dsRenderVars === 'function') {
        dsRenderVars(vars);
        if (typeof dsInjectListStyles === 'function') dsInjectListStyles();
    }
}

window.dsCopyVar = function(v) {
    _copiedVar = v;
    document.querySelectorAll('.ds-var-key').forEach(e => e.classList.remove('copied'));
    event.target.classList.add('copied');
    setTimeout(() => event.target.classList.remove('copied'), 1500);
    _toast(`${v} kopiert`, false);
};

function _varChanged() {
    clearTimeout(window._vd);
    window._vd = setTimeout(_loadPreview, 700);
}

function _collectVars() {
    if (typeof dsCollectAllVars === 'function') return dsCollectAllVars();
    const v = {};
    document.querySelectorAll('.ds-var-input').forEach(i => {
        if(i.dataset.var && i.value) v[i.dataset.var] = i.value;
    });
    return v;
}

// ── Blöcke links ──────────────────────────────────────────────────────────

function _renderBlocksLeft(blocks) {
    const c=_el('ds-blocks-container'), n=_el('ds-blocks-count'), p=_el('ds-blocks-panel');
    if(!c) return;
    if(p) p.style.display = blocks.length ? '' : 'none';
    if(n) n.textContent = blocks.length;
    c.innerHTML = blocks.map(b => {
        const bt = b.block__block_type || '';
        const bn = b.block__name || '';
        const bc = (b.content_override || b.block__content || '').replace(/<[^>]+>/g,'').substring(0,35);
        return `<div class="ds-block-item-left" draggable="true" data-tb-id="${b.id}"
            ondragstart="_blkLDragStart(event,${b.id},'${bn.replace(/'/g,"\\'")}','${bt}')"
            ondragend="_blkLDragEnd(event)">
            <i class="bi bi-grip-vertical" style="color:#ccc;font-size:11px;"></i>
            <span class="ds-badge ${TYPE_COLOR[bt]||'ds-badge-gray'}"
                  style="font-size:8px;flex-shrink:0;">${bt}</span>
            <div style="min-width:0;flex:1;">
                <div class="ds-bl-name">${bn}</div>
                ${bc ? `<div class="ds-bl-prev">${bc}…</div>` : ''}
            </div></div>`;
    }).join('');
}

window._blkLDragStart = function(e, tbId, name, type) {
    _dragging = {fromLeft:true, tbId, name, type};
    e.target.classList.add('dragging');
    e.dataTransfer.effectAllowed = 'copy';
};

window._blkLDragEnd = function(e) {
    e.target.classList.remove('dragging');
    _dragging = null;
    document.querySelectorAll('.ds-dz').forEach(z => z.classList.remove('ds-dz-over'));
};

// ── Preview laden ─────────────────────────────────────────────────────────

async function _loadPreview() {
    if(!_tplId) return;
    const canvas = _el('ds-doc-canvas');
    if(!canvas) return;
    console.log('[DocStudio] Lade Preview für Template:', _tplId);
    try {
        const data = await _api(`templates/${_tplId}/preview/`, {
            method: 'POST',
            body:   JSON.stringify({variables: _collectVars(), format: 'html'})
        });
        console.log('[DocStudio] Preview HTML Länge:', (data.html||'').length);
        _buildDocument(data.html || '', canvas);
    } catch(e) {
        console.error('[DocStudio] Preview Fehler:', e);
        canvas.innerHTML = '<div class="ds-doc-hint text-danger">Fehler beim Laden der Vorschau</div>';
    }
}

// ── Dokument aufbauen — Server liefert fertige Seiten ─────────────────────

function _buildDocument(html, canvas) {
    console.log('[DocStudio] _buildDocument Start, Modus:', _mode);

    const tmp  = document.createElement('div');
    tmp.innerHTML = html;
    const wrap = tmp.querySelector('.ds-doc-preview-wrap');

    // Layout-Werte aus data-layout aktualisieren
    if(wrap) {
        try {
            const raw = wrap.getAttribute('data-layout') || '{}';
            const L   = JSON.parse(raw);
            if(L.w) {
                _layout = L;
                console.log('[DocStudio] Layout aus Server:', _layout);
            }
        } catch(e) {
            console.warn('[DocStudio] Layout-JSON Fehler:', e);
        }
    }

    canvas.innerHTML = '';

    // Server-Seiten holen
    const pages = wrap ? [...wrap.querySelectorAll('.ds-preview-page')] : [];
    console.log('[DocStudio] Server-Seiten gefunden:', pages.length);

    if(pages.length === 0) {
        console.error('[DocStudio] KEINE ds-preview-page Divs vom Server!');
        console.log('[DocStudio] HTML Anfang:', html.substring(0,300));
        canvas.innerHTML = '<div class="ds-doc-hint text-warning">' +
            'Keine Seiten erhalten — bitte F5 und erneut versuchen</div>';
        return;
    }

    let dzIdx = 0;

    pages.forEach((page, pageIdx) => {
        // Editor/Preview CSS-Klasse
        page.classList.add(_mode === 'editor' ? 'ds-editor-mode' : 'ds-preview-mode');

        // Seitennummer
        const nr = document.createElement('div');
        nr.style.cssText = 'position:absolute;top:10px;right:16px;' +
                           'font-size:7px;color:#999;pointer-events:none;z-index:1;';
        nr.textContent = 'Seite ' + (pageIdx + 1);
        page.appendChild(nr);

        // Blöcke mit Editor-Funktionen versehen
        const blocks = [...page.querySelectorAll('.ds-preview-block')];
        console.log(`[DocStudio] Seite ${pageIdx+1}: ${blocks.length} Blöcke`);

        // DropZone vor dem ersten Block (nur Editor)
        if(_mode === 'editor' && blocks.length > 0) {
            blocks[0].before(_makeDz(dzIdx++));
        }

        blocks.forEach((blkOrig, i) => {
            const tbId  = blkOrig.dataset.tbId;
            const btype = blkOrig.dataset.blockType || '';

            if(!tbId) {
                console.warn('[DocStudio] Block ohne tbId übersprungen');
                return;
            }

            // Wrapper-Div mit Editor-Events
            const w = document.createElement('div');
            w.className    = 'ds-eb';
            w.dataset.tbId = tbId;
            w.dataset.btype = btype;
            w.dataset.idx  = i;
            w.draggable    = (_mode === 'editor');

            // Inhalt vom Server übernehmen + Doppelklick-Tipp
            w.innerHTML = blkOrig.innerHTML +
                (_mode === 'editor'
                    ? '<span class="ds-eb-tip">✎ Doppelklick</span>'
                    : '');

            // Events
            w.addEventListener('dblclick', () => _openEdit(w, tbId));

            w.addEventListener('dragstart', e => {
                _dragging = {fromLeft: false, tbId, wrapper: w};
                w.style.opacity = '.35';
                e.dataTransfer.effectAllowed = 'move';
            });

            w.addEventListener('dragend', () => {
                w.style.opacity = '1';
                _dragging = null;
                document.querySelectorAll('.ds-dz')
                    .forEach(z => z.classList.remove('ds-dz-over'));
            });

            // Original ersetzen
            blkOrig.replaceWith(w);

            // DropZone nach jedem Block (nur Editor)
            if(_mode === 'editor') {
                w.after(_makeDz(dzIdx++));
            }
        });

        canvas.appendChild(page);
        console.log(`[DocStudio] Seite ${pageIdx+1} eingefügt`);
    });

    console.log('[DocStudio] _buildDocument fertig,', pages.length, 'Seiten gerendert');
}

// ── DropZonen ─────────────────────────────────────────────────────────────

function _makeDz(idx) {
    const dz = document.createElement('div');
    dz.className      = 'ds-dz';
    dz.dataset.idx    = idx;
    dz.textContent    = '+ hier einfügen';
    dz.addEventListener('dragover',  e => { e.preventDefault(); dz.classList.add('ds-dz-over'); });
    dz.addEventListener('dragleave', ()  => dz.classList.remove('ds-dz-over'));
    dz.addEventListener('drop',      e  => _dzDrop(e, idx));
    return dz;
}

async function _dzDrop(e, idx) {
    e.preventDefault();
    document.querySelectorAll('.ds-dz').forEach(z => z.classList.remove('ds-dz-over'));
    if(!_dragging) return;
    console.log('[DocStudio] Drop tbId:', _dragging.tbId, 'auf Index:', idx);
    await _reorderBlock(_dragging.tbId, idx);
    _dragging = null;
}

async function _reorderBlock(tbId, targetIdx) {
    const canvas  = _el('ds-doc-canvas');
    if(!canvas) return;
    const allBlks = [...canvas.querySelectorAll('.ds-eb')];
    const orders  = [];
    let order     = 10;
    let placed    = false;

    allBlks.forEach((b, i) => {
        if(i === targetIdx && !placed) {
            orders.push({id: parseInt(tbId), order});
            order += 10;
            placed = true;
        }
        if(b.dataset.tbId !== String(tbId)) {
            orders.push({id: parseInt(b.dataset.tbId), order});
            order += 10;
        }
    });
    if(!placed) orders.push({id: parseInt(tbId), order});

    console.log('[DocStudio] Reorder:', orders);
    _pushUndo({action: 'reorder', prev: [...orders]});

    try {
        await _api(`templates/${_tplId}/blocks/reorder/`, {
            method: 'PUT',
            body:   JSON.stringify({blocks: orders})
        });
        await _loadPreview();
        _toast('Reihenfolge gespeichert');
    } catch(err) {
        console.error('[DocStudio] Reorder Fehler:', err);
    }
}

// ── Block bearbeiten ──────────────────────────────────────────────────────

async function _openEdit(wrapper, tbId) {
    if(_mode !== 'editor') return;
    if(_currentEdit) _cancelEdit();

    console.log('[DocStudio] Edit Block tbId:', tbId);
    let blockData;
    try {
        blockData = await _api(`templates/${_tplId}/blocks/${tbId}/`);
    } catch(e) {
        console.error('[DocStudio] Block laden Fehler:', e);
        return;
    }

    _currentEdit = {
        tbId,
        wrapper,
        origHtml:    wrapper.innerHTML,
        origContent: blockData.content || '',
    };

    wrapper.classList.add('ds-eb-active');
    wrapper.draggable = false;

    const chips = _allVars.map(v =>
        `<span class="ds-vchip"
               onclick="_insertVar('ds-ta-${tbId}','{${v.name}}')">{${v.name}}</span>`
    ).join('');

    wrapper.innerHTML = `
        <textarea class="ds-eb-textarea" id="ds-ta-${tbId}"
                  rows="5">${blockData.content || ''}</textarea>
        <div class="ds-eb-actions">
            <button class="ds-eb-save" onclick="_saveEdit('${tbId}')">
                <i class="bi bi-check-lg"></i> Speichern
            </button>
            <button class="ds-eb-cancel" onclick="_cancelEdit()">Abbrechen</button>
            <span class="ds-vchip-label">Variablen:</span>
            <div class="ds-var-chips">${chips}</div>
        </div>`;

    const ta = document.getElementById(`ds-ta-${tbId}`);
    if(ta) {
        ta.focus();
        if(_copiedVar) {
            _insertVar(`ds-ta-${tbId}`, _copiedVar);
            _copiedVar = null;
        }
    }
}

window._insertVar = function(taId, v) {
    const ta = document.getElementById(taId);
    if(!ta) { _copiedVar = v; return; }
    const s = ta.selectionStart, e = ta.selectionEnd;
    ta.value = ta.value.slice(0,s) + v + ta.value.slice(e);
    ta.selectionStart = ta.selectionEnd = s + v.length;
    ta.focus();
    ta.style.borderColor = '#163258';
    setTimeout(() => ta.style.borderColor = '#f59e0b', 500);
};

window._saveEdit = async function(tbId) {
    if(!_currentEdit || _currentEdit.tbId !== tbId) return;
    const ta  = document.getElementById(`ds-ta-${tbId}`);
    const newContent = ta ? ta.value : '';
    const btn = document.querySelector('.ds-eb-save');

    if(btn) {
        btn.disabled  = true;
        btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span>';
    }
    try {
        _pushUndo({action: 'edit', tbId, content: _currentEdit.origContent});
        await _api(`templates/${_tplId}/blocks/${tbId}/`, {
            method: 'PUT',
            body:   JSON.stringify({content: newContent})
        });
        _currentEdit = null;
        await _loadPreview();
        _toast('Gespeichert');
        console.log('[DocStudio] Block gespeichert tbId:', tbId);
    } catch(err) {
        console.error('[DocStudio] Speichern Fehler:', err);
        if(btn) {
            btn.disabled  = false;
            btn.innerHTML = '<i class="bi bi-check-lg"></i> Speichern';
        }
    }
};

window._cancelEdit = function() {
    if(!_currentEdit) return;
    const {wrapper, origHtml} = _currentEdit;
    wrapper.innerHTML = origHtml;
    wrapper.classList.remove('ds-eb-active');
    wrapper.draggable = (_mode === 'editor');
    _currentEdit = null;
};

// ── Undo ──────────────────────────────────────────────────────────────────

function _pushUndo(item) {
    _undoStack.push(item);
    if(_undoStack.length > 3) _undoStack.shift();
    const btn = _el('ds-undo-btn'), cnt = _el('ds-undo-cnt');
    if(btn) btn.disabled = false;
    if(cnt) cnt.textContent = `(${_undoStack.length})`;
}

window.dsEditorUndo = async function() {
    if(!_undoStack.length) return;
    const item = _undoStack.pop();
    const btn  = _el('ds-undo-btn'), cnt = _el('ds-undo-cnt');
    if(!_undoStack.length) {
        if(btn) btn.disabled = true;
        if(cnt) cnt.textContent = '';
    } else if(cnt) {
        cnt.textContent = `(${_undoStack.length})`;
    }
    console.log('[DocStudio] Undo:', item.action);
    if(item.action === 'edit') {
        try {
            await _api(`templates/${_tplId}/blocks/${item.tbId}/`, {
                method: 'PUT',
                body:   JSON.stringify({content: item.content})
            });
            await _loadPreview();
            _toast('Rückgängig', false);
        } catch(e) { console.error('[DocStudio] Undo Fehler:', e); }
    } else if(item.action === 'reorder') {
        try {
            await _api(`templates/${_tplId}/blocks/reorder/`, {
                method: 'PUT',
                body:   JSON.stringify({blocks: item.prev})
            });
            await _loadPreview();
            _toast('Rückgängig', false);
        } catch(e) { console.error('[DocStudio] Undo Fehler:', e); }
    }
};

// ── Modus ─────────────────────────────────────────────────────────────────

window.dsSetMode = function(m) {
    console.log('[DocStudio] Modus:', m);
    _mode = m;
    _el('ds-tog-editor')?.classList.toggle('on', m === 'editor');
    _el('ds-tog-preview')?.classList.toggle('on', m === 'preview');
    if(_currentEdit) _cancelEdit();
    _loadPreview();
};

// ── Toast ─────────────────────────────────────────────────────────────────

function _toast(msg, withUndo=true) {
    const t=_el('ds-toast'), m=_el('ds-toast-msg'), u=_el('ds-toast-undo');
    if(!t) return;
    if(m) m.textContent = msg;
    if(u) u.style.display = withUndo ? '' : 'none';
    t.className = 'ds-toast show';
    clearTimeout(_toastTimer);
    _toastTimer = setTimeout(() => t.className = 'ds-toast', 3000);
}

// ── Test-Daten ────────────────────────────────────────────────────────────

const TEST_DATA = {
    contract: {
        an_firma:              'Muster GmbH',
        an_ansprechpartner:    'Max Mustermann',
        an_strasse:            'Musterstraße 1',
        an_plz_ort:            '12345 Musterstadt',
        stundensatz:           '95,00',
        laufzeit_von:          '1. Juni 2026',
        laufzeit_bis:          '31. Dezember 2026',
        stunden_kontingent:    '500',
        rahmenvertrag_datum:   '15. Mai 2026',
        kunde_name:            'Muster AG',
        kunde_strasse:         'Hauptstraße 10',
        kunde_plz_ort:         '60311 Frankfurt',
        endkunde_name:         'Endkunde GmbH',
    },
    invoice: {
        rg_nummer:             '26/05/0001',
        empfaenger_firma:      'Muster AG',
        empfaenger_adresse:    'Hauptstraße 10\n60311 Frankfurt',
        betreff:               'Beratungsleistung Mai 2026',
        abrechnungsmonat:      'Mai 2026',
        summe_netto:           '7.920,00',
        mwst_satz:             '19',
        mwst_euro:             '1.504,80',
        gesamtbetrag:          '9.424,80',
        zahlungsziel_tage:     '30',
        zahlungsziel_text:     '30 Tage netto',
    },
    general: {
        empfaenger_firma:      'Muster AG',
        empfaenger_name:       'Max Mustermann',
        empfaenger_strasse:    'Musterstraße 1',
        empfaenger_plz_ort:    '12345 Musterstadt',
        datum:                 '23. Mai 2026',
        betreff:               'Testschreiben',
    },
};

window.dsStudioTest = async function() {
    const sel = _el('ds-template-select'), id = sel?.value;
    if(!id) return;
    const scope = sel.options[sel.selectedIndex]?.dataset?.scope || 'contract';
    const vars  = TEST_DATA[scope] || TEST_DATA.contract;
    document.querySelectorAll('.ds-var-input').forEach(i => {
        if(i.dataset.var && vars[i.dataset.var]) i.value = vars[i.dataset.var];
    });
    const ref = _el('ds-studio-ref');
    if(ref && !ref.value) ref.value = 'MUSTER-001';
    await _loadPreview();
    await _genDownload(id, vars, 'MUSTER-001');
};

window.dsStudioGenerate = async function() {
    const id  = _el('ds-template-select')?.value;
    const ref = _el('ds-studio-ref')?.value || 'OHNE-REF';
    if(!id) return;
    await _genDownload(id, _collectVars(), ref);
};

async function _genDownload(id, variables, context_ref) {
    const engine = _el('ds-studio-engine')?.value || 'BOTH';
    const gBtn   = _el('ds-btn-generate'), tBtn = _el('ds-btn-test');
    const res    = _el('ds-generate-result'), paths = _el('ds-generate-paths');
    const dDocx  = _el('ds-download-docx'),  dPdf  = _el('ds-download-pdf');

    if(res)   res.classList.add('d-none');
    if(dDocx) dDocx.classList.add('d-none');
    if(dPdf)  dPdf.classList.add('d-none');

    if(gBtn) { gBtn.disabled=true; gBtn.innerHTML='<span class="spinner-border spinner-border-sm me-1"></span>'; }
    if(tBtn) { tBtn.disabled=true; tBtn.innerHTML='<span class="spinner-border spinner-border-sm me-1"></span>'; }

    try {
        const data = await _api(`templates/${id}/generate/`, {
            method: 'POST',
            body:   JSON.stringify({variables, context_ref, engine})
        });
        if(res) res.classList.remove('d-none');
        if(paths) {
            const l = [];
            if(data.file_path_docx) l.push(data.file_path_docx.split('/').pop());
            if(data.file_path_pdf)  l.push(data.file_path_pdf.split('/').pop());
            paths.textContent = l.join(' · ');
        }
        if(data.log_id) {
            if(dDocx && data.file_path_docx) {
                dDocx.href = `/doc-studio/download/${data.log_id}/?type=docx`;
                dDocx.classList.remove('d-none');
            }
            if(dPdf && data.file_path_pdf) {
                dPdf.href = `/doc-studio/download/${data.log_id}/?type=pdf`;
                dPdf.classList.remove('d-none');
            }
        }
        _toast('Dokument generiert!');
        console.log('[DocStudio] Generiert:', data);
    } catch(e) {
        console.error('[DocStudio] Generieren Fehler:', e);
    } finally {
        if(gBtn) { gBtn.disabled=false; gBtn.innerHTML='<i class="bi bi-play-fill me-1"></i>Generieren'; }
        if(tBtn) { tBtn.disabled=false; tBtn.innerHTML='<i class="bi bi-bug me-1"></i>Test'; }
    }
}

// ── Helfer ────────────────────────────────────────────────────────────────

function _el(id) { return document.getElementById(id); }

async function _api(path, opts={}) {
    const csrf = document.cookie.split(';')
        .map(c => c.trim())
        .find(c => c.startsWith('csrftoken='))
        ?.split('=')[1] || '';
    const r = await fetch('/doc-studio/api/' + path, {
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken':  csrf,
            ...(opts.headers || {}),
        },
        ...opts,
    });
    if(!r.ok) {
        console.error('[DocStudio] API Fehler:', r.status, path);
        throw new Error(`HTTP ${r.status}`);
    }
    return r.json();
}

})();
