/**
 * ds-vars-renderer.js — Variablen-Formular für Doc Studio
 * Ersetzt _renderVars() in mod-doc_studio-editor.js
 *
 * Typen:
 *   string   → <input type="text">
 *   date     → <input type="date">
 *   currency → <input type="text"> mit Formatierung
 *   list     → dynamische Zeilen-Tabelle + Berechnung
 *
 * Listen:
 *   positionen   → pos_nr, zeitraum, stunden, satz_euro, betrag_euro
 *   arbeitspakete → ap_nr, beschreibung, anzahl, preis_euro, betrag_euro
 *
 * Berechnungen (live):
 *   positionen:    betrag_euro = stunden × satz_euro
 *   arbeitspakete: betrag_euro = anzahl × preis_euro
 *   beide:         summe_netto = Σ betrag_euro
 *                  mwst_euro   = summe_netto × mwst_satz / 100
 *                  gesamtbetrag = summe_netto + mwst_euro
 */

// ── Globaler State für Listen-Daten ───────────────────────────────────────
window._dsListData = {};   // { 'positionen': [{...}, ...], 'arbeitspakete': [...] }

// ── Variablen rendern ─────────────────────────────────────────────────────

function dsRenderVars(vars) {
    const c = document.getElementById('ds-vars-container');
    const n = document.getElementById('ds-vars-count');
    if (!c) return;

    // State zurücksetzen
    window._dsListData = {};

    if (!vars || !vars.length) {
        c.innerHTML = '<p class="small text-secondary mb-0">Keine Variablen</p>';
        if (n) n.textContent = '0';
        return;
    }

    if (n) n.textContent = vars.length;

    // Variablen in Gruppen aufteilen
    const simpleVars = vars.filter(v => v.type !== 'list');
    const listVars   = vars.filter(v => v.type === 'list');

    // Berechnete Variablen (werden von JS gesetzt, nicht manuell eingegeben)
    const computedKeys = new Set(['summe_netto', 'mwst_euro', 'gesamtbetrag']);

    let html = '';

    // ── Einfache Variablen ────────────────────────────────────────────
    if (simpleVars.length) {
        html += '<div class="ds-vars-group">';

        simpleVars.forEach(v => {
            const isComputed = computedKeys.has(v.name);
            const isRequired = v.required;
            const label = v.name.replace(/_/g, ' ');

            if (isComputed) {
                // Berechnete Felder — readonly, werden von JS befüllt
                html += `
                <div class="ds-var-row ds-var-computed">
                    <div class="ds-var-label-wrap">
                        <span class="ds-var-key">{${v.name}}</span>
                        <span class="ds-var-type ds-var-type-calc">⟳ berechnet</span>
                    </div>
                    <input class="ds-var-input ds-var-input-computed"
                           id="dv-${v.name}"
                           data-var="${v.name}"
                           data-type="${v.type}"
                           type="text"
                           readonly
                           placeholder="wird berechnet…">
                </div>`;
            } else {
                const inputType = v.type === 'date' ? 'date' : 'text';
                const placeholder = _varPlaceholder(v);
                const typeBadge = _typeBadge(v.type);

                html += `
                <div class="ds-var-row${isRequired ? ' ds-var-required' : ''}">
                    <div class="ds-var-label-wrap">
                        <span class="ds-var-key" onclick="dsCopyVar('{${v.name}}')"
                              title="Klick → kopieren">{${v.name}}</span>
                        ${typeBadge}
                        ${isRequired ? '<span class="ds-var-req">*</span>' : ''}
                    </div>
                    <input class="ds-var-input"
                           id="dv-${v.name}"
                           data-var="${v.name}"
                           data-type="${v.type}"
                           type="${inputType}"
                           placeholder="${placeholder}"
                           oninput="dsVarChanged(this)">
                </div>`;
            }
        });

        html += '</div>';
    }

    // ── Listen-Variablen ──────────────────────────────────────────────
    listVars.forEach(v => {
        window._dsListData[v.name] = [];
        html += dsRenderListVar(v);
    });

    c.innerHTML = html;

    // MwSt-Satz Feld mit Default befüllen
    const mwstInput = document.getElementById('dv-mwst_satz');
    if (mwstInput && !mwstInput.value) {
        mwstInput.value = '19';
    }
}

// ── Listen-Variable rendern ────────────────────────────────────────────────

function dsRenderListVar(varDef) {
    const name   = varDef.name;
    const schema = varDef.item_schema || {};
    const cols   = Object.entries(schema);

    // Spalten-Konfiguration
    const colConfig = _getColConfig(name, cols);

    let html = `
    <div class="ds-list-var" id="ds-list-${name}">
        <div class="ds-list-header">
            <span class="ds-list-title">
                <i class="bi bi-table me-1"></i>
                {${name}}
                <span class="ds-var-req">*</span>
            </span>
            <button class="ds-list-add-btn" onclick="dsListAddRow('${name}')">
                <i class="bi bi-plus-circle me-1"></i>Zeile
            </button>
        </div>
        <div class="ds-list-table-wrap">
            <table class="ds-list-table" id="ds-list-table-${name}">
                <thead>
                    <tr>
                        ${colConfig.map(c =>
                            `<th style="width:${c.width}">${c.label}</th>`
                        ).join('')}
                        <th style="width:32px;"></th>
                    </tr>
                </thead>
                <tbody id="ds-list-tbody-${name}">
                    <tr class="ds-list-empty-row">
                        <td colspan="${colConfig.length + 1}"
                            style="text-align:center;color:var(--text-secondary);
                                   font-size:10px;padding:8px;">
                            <i class="bi bi-plus-circle me-1"></i>
                            Zeile hinzufügen
                        </td>
                    </tr>
                </tbody>
            </table>
        </div>
        <div class="ds-list-footer" id="ds-list-footer-${name}" style="display:none;">
            <div class="ds-list-sum-row">
                <span>Summe netto:</span>
                <span id="ds-sum-netto-${name}">0,00 €</span>
            </div>
        </div>
    </div>`;

    return html;
}

// ── Zeile hinzufügen ──────────────────────────────────────────────────────

function dsListAddRow(listName) {
    const tbody = document.getElementById(`ds-list-tbody-${listName}`);
    if (!tbody) return;

    // Leere Zeile entfernen
    const emptyRow = tbody.querySelector('.ds-list-empty-row');
    if (emptyRow) emptyRow.remove();

    const schema    = _getSchemaForList(listName);
    const colConfig = _getColConfig(listName, Object.entries(schema));
    const rowIdx    = (window._dsListData[listName] || []).length;

    // Leeres Objekt für neue Zeile
    const newRow = {};
    colConfig.forEach(c => newRow[c.key] = '');

    // Auto-Nummerierung für pos_nr / ap_nr
    if (newRow.hasOwnProperty('pos_nr')) {
        newRow.pos_nr = (rowIdx + 1) + '.';
    }
    if (newRow.hasOwnProperty('ap_nr')) {
        newRow.ap_nr = 'AP-' + (rowIdx + 1);
    }

    if (!window._dsListData[listName]) window._dsListData[listName] = [];
    window._dsListData[listName].push(newRow);

    const tr = document.createElement('tr');
    tr.className = 'ds-list-row';
    tr.dataset.listName = listName;
    tr.dataset.rowIdx   = rowIdx;

    let cellsHtml = colConfig.map(col => {
        const val       = newRow[col.key] || '';
        const inputType = col.inputType || 'text';
        const align     = col.align || 'left';
        return `<td>
            <input class="ds-list-cell-input"
                   data-list="${listName}"
                   data-row="${rowIdx}"
                   data-key="${col.key}"
                   data-coltype="${col.type}"
                   type="${inputType}"
                   value="${val}"
                   placeholder="${col.placeholder || ''}"
                   style="text-align:${align}"
                   oninput="dsListCellChanged(this)">
        </td>`;
    }).join('');

    cellsHtml += `<td>
        <button class="ds-list-del-btn"
                onclick="dsListDeleteRow('${listName}', ${rowIdx})"
                title="Zeile löschen">
            <i class="bi bi-trash3"></i>
        </button>
    </td>`;

    tr.innerHTML = cellsHtml;
    tbody.appendChild(tr);

    // Footer anzeigen
    const footer = document.getElementById(`ds-list-footer-${listName}`);
    if (footer) footer.style.display = '';

    // Ersten Input fokussieren (nicht pos_nr/ap_nr)
    const firstInput = tr.querySelector('.ds-list-cell-input:not([data-key="pos_nr"]):not([data-key="ap_nr"])');
    if (firstInput) firstInput.focus();

    dsListRecalc(listName);
    _varChanged();
}

// ── Zeile löschen ─────────────────────────────────────────────────────────

function dsListDeleteRow(listName, rowIdx) {
    if (!window._dsListData[listName]) return;

    window._dsListData[listName].splice(rowIdx, 1);

    // Tabelle neu rendern
    dsListRebuildTable(listName);
    dsListRecalc(listName);
    _varChanged();
}

// ── Tabelle nach Löschen neu aufbauen ─────────────────────────────────────

function dsListRebuildTable(listName) {
    const tbody = document.getElementById(`ds-list-tbody-${listName}`);
    if (!tbody) return;

    const data      = window._dsListData[listName] || [];
    const schema    = _getSchemaForList(listName);
    const colConfig = _getColConfig(listName, Object.entries(schema));

    tbody.innerHTML = '';

    if (!data.length) {
        tbody.innerHTML = `
            <tr class="ds-list-empty-row">
                <td colspan="${colConfig.length + 1}"
                    style="text-align:center;color:var(--text-secondary);
                           font-size:10px;padding:8px;">
                    <i class="bi bi-plus-circle me-1"></i>Zeile hinzufügen
                </td>
            </tr>`;
        const footer = document.getElementById(`ds-list-footer-${listName}`);
        if (footer) footer.style.display = 'none';
        return;
    }

    data.forEach((rowData, rowIdx) => {
        const tr = document.createElement('tr');
        tr.className = 'ds-list-row';
        tr.dataset.listName = listName;
        tr.dataset.rowIdx   = rowIdx;

        let cellsHtml = colConfig.map(col => {
            const val   = rowData[col.key] || '';
            const align = col.align || 'left';
            return `<td>
                <input class="ds-list-cell-input"
                       data-list="${listName}"
                       data-row="${rowIdx}"
                       data-key="${col.key}"
                       data-coltype="${col.type}"
                       type="${col.inputType || 'text'}"
                       value="${val}"
                       placeholder="${col.placeholder || ''}"
                       style="text-align:${align}"
                       oninput="dsListCellChanged(this)">
            </td>`;
        }).join('');

        cellsHtml += `<td>
            <button class="ds-list-del-btn"
                    onclick="dsListDeleteRow('${listName}', ${rowIdx})"
                    title="Zeile löschen">
                <i class="bi bi-trash3"></i>
            </button>
        </td>`;

        tr.innerHTML = cellsHtml;
        tbody.appendChild(tr);
    });
}

// ── Zelle geändert → Berechnung ───────────────────────────────────────────

function dsListCellChanged(input) {
    const listName = input.dataset.list;
    const rowIdx   = parseInt(input.dataset.row);
    const key      = input.dataset.key;
    const colType  = input.dataset.coltype;

    if (!window._dsListData[listName]) return;
    if (!window._dsListData[listName][rowIdx]) return;

    let val = input.value;

    // Währungs-Parsing: "95,00" → 95.0
    if (colType === 'currency' || colType === 'decimal') {
        val = _parseNumber(val);
        window._dsListData[listName][rowIdx][key] = val;
    } else {
        window._dsListData[listName][rowIdx][key] = val;
    }

    // Zeilen-Berechnung
    dsListCalcRow(listName, rowIdx);

    // Gesamt-Berechnung
    dsListRecalc(listName);

    // Preview aktualisieren (debounced)
    _varChanged();
}

// ── Zeilen-Berechnung ─────────────────────────────────────────────────────

function dsListCalcRow(listName, rowIdx) {
    const row = window._dsListData[listName][rowIdx];
    if (!row) return;

    let betrag = 0;

    if (listName === 'positionen') {
        // betrag_euro = stunden × satz_euro
        const stunden   = _parseNumber(row.stunden   || 0);
        const satz_euro = _parseNumber(row.satz_euro || 0);
        betrag = stunden * satz_euro;
        row.betrag_euro = betrag;
    } else if (listName === 'arbeitspakete') {
        // betrag_euro = anzahl × preis_euro
        const anzahl      = _parseNumber(row.anzahl      || 0);
        const preis_euro  = _parseNumber(row.preis_euro  || 0);
        betrag = anzahl * preis_euro;
        row.betrag_euro = betrag;
    }

    // betrag_euro Input in der Zeile aktualisieren
    const betragInput = document.querySelector(
        `[data-list="${listName}"][data-row="${rowIdx}"][data-key="betrag_euro"]`
    );
    if (betragInput) {
        betragInput.value = betrag > 0 ? _formatEuro(betrag) : '';
    }
}

// ── Gesamt-Berechnung ─────────────────────────────────────────────────────

function dsListRecalc(listName) {
    const data = window._dsListData[listName] || [];

    // Summe netto
    const summeNetto = data.reduce((sum, row) => {
        return sum + _parseNumber(row.betrag_euro || 0);
    }, 0);

    // MwSt-Satz aus Formular lesen
    const mwstSatzInput = document.getElementById('dv-mwst_satz');
    const mwstSatz      = mwstSatzInput ? _parseNumber(mwstSatzInput.value || '19') : 19;

    const mwstEuro    = summeNetto * mwstSatz / 100;
    const gesamtbetrag = summeNetto + mwstEuro;

    // Anzeige in Summen-Footer
    const sumEl = document.getElementById(`ds-sum-netto-${listName}`);
    if (sumEl) sumEl.textContent = _formatEuro(summeNetto) + ' €';

    // Berechnete Felder im Variablen-Formular aktualisieren
    _setComputedVar('summe_netto',  _formatEuroDE(summeNetto));
    _setComputedVar('mwst_euro',    _formatEuroDE(mwstEuro));
    _setComputedVar('gesamtbetrag', _formatEuroDE(gesamtbetrag));

    // Auch im _dsListData speichern für collectVars()
    window._dsCalcResults = {
        summe_netto:   _formatEuroDE(summeNetto),
        mwst_euro:     _formatEuroDE(mwstEuro),
        gesamtbetrag:  _formatEuroDE(gesamtbetrag),
    };
}

// ── Variablen sammeln (ersetzt _collectVars) ──────────────────────────────

function dsCollectAllVars() {
    const vars = {};

    // Einfache Inputs
    document.querySelectorAll('.ds-var-input[data-var]').forEach(inp => {
        const key = inp.dataset.var;
        if (key && inp.value && !inp.readOnly) {
            vars[key] = inp.value;
        }
    });

    // Berechnete Werte
    if (window._dsCalcResults) {
        Object.assign(vars, window._dsCalcResults);
    }

    // Listen-Daten
    Object.entries(window._dsListData || {}).forEach(([listName, rows]) => {
        if (rows.length > 0) {
            // Formatierte Kopie für API
            vars[listName] = rows.map(row => {
                const formatted = {...row};
                // Zahlen als Float für den Assembler
                ['stunden', 'anzahl'].forEach(k => {
                    if (formatted[k] !== undefined && formatted[k] !== '') {
                        formatted[k] = _parseNumber(formatted[k]);
                    }
                });
                ['satz_euro', 'preis_euro', 'betrag_euro'].forEach(k => {
                    if (formatted[k] !== undefined && formatted[k] !== '') {
                        formatted[k] = _parseNumber(formatted[k]);
                    }
                });
                return formatted;
            });
        }
    });

    return vars;
}

// ── Test-Daten einfüllen ──────────────────────────────────────────────────

function dsFillTestData(scope) {
    const testData = {
        contract: {
            ag_firma: 'abcona e.K.',
            ag_tel: '+49 6171 8867 00',
            ag_fax: '+49 6171 8867 00',
            ag_email: 'office@abcona.de',
            ag_web: 'www.abcona.de',
            an_firma: 'Muster GmbH',
            an_ansprechpartner: 'Max Mustermann',
            an_strasse: 'Musterstraße 1',
            an_plz_ort: '60000 Frankfurt',
            an_ort: 'Frankfurt',
            stundensatz: '95,00',
            laufzeit_von: '1. Juni 2026',
            laufzeit_bis: '31. Dezember 2026',
            stunden_kontingent: '500',
            leistungsbeschreibung: 'IT-Beratung und Projektunterstützung SAP S/4HANA',
            einsatzort: 'Frankfurt am Main / Homeoffice',
            kunde_name: 'Muster AG',
            kunde_strasse: 'Hauptstraße 10',
            kunde_plz_ort: '60311 Frankfurt',
            endkunde_name: 'Endkunde GmbH',
            rahmenvertrag_datum: '15. Mai 2026',
            datum_heute: new Date().toISOString().split('T')[0],
        },
        invoice: {
            ag_firma: 'abcona e.K.',
            ag_tel: '+49 6171 8867 00',
            ag_fax: '+49 6171 8867 00',
            ag_email: 'office@abcona.de',
            ag_web: 'www.abcona.de',
            rg_nummer: 'RG-2026-001',
            rg_datum: new Date().toISOString().split('T')[0],
            empfaenger_firma: 'Muster AG',
            empfaenger_name: 'Max Mustermann',
            empfaenger_abteilung: 'IT-Abteilung',
            empfaenger_strasse: 'Hauptstraße 10',
            empfaenger_plz_ort: '60311 Frankfurt',
            empfaenger_land: 'Deutschland',
            betreff: 'Rechnung für IT-Projekt Mai 2026',
            mwst_satz: '19',
            zahlungsziel_tage: '30',
            datum_heute: new Date().toISOString().split('T')[0],
        },
        general: {
            ag_tel: '+49 6171 8867 00',
            empfaenger_firma: 'Muster AG',
            empfaenger_name: 'Max Mustermann',
            empfaenger_strasse: 'Hauptstraße 10',
            empfaenger_plz_ort: '60311 Frankfurt',
            empfaenger_land: 'Deutschland',
            betreff: 'Testschreiben',
            inhalt: 'Sehr geehrte Damen und Herren,\n\nbitte nehmen Sie diesen Testbrief zur Kenntnis.\n\nMit freundlichen Grüßen',
            datum_heute: new Date().toISOString().split('T')[0],
        },
    };

    const data = testData[scope] || testData.general;

    // Einfache Felder befüllen
    document.querySelectorAll('.ds-var-input[data-var]').forEach(inp => {
        const key = inp.dataset.var;
        if (key && data[key] !== undefined && !inp.readOnly) {
            inp.value = data[key];
        }
    });

    // Listen-Testdaten
    if (scope === 'invoice') {
        // positionen Test-Zeilen
        if (window._dsListData.hasOwnProperty('positionen')) {
            window._dsListData['positionen'] = [];
            dsListAddRow('positionen');
            dsListAddRow('positionen');

            // Zeile 1
            _setListCell('positionen', 0, 'pos_nr',     '1.');
            _setListCell('positionen', 0, 'zeitraum',   'Mai 2026');
            _setListCell('positionen', 0, 'stunden',    '80');
            _setListCell('positionen', 0, 'satz_euro',  '95');
            dsListCalcRow('positionen', 0);

            // Zeile 2
            _setListCell('positionen', 1, 'pos_nr',     '2.');
            _setListCell('positionen', 1, 'zeitraum',   'Mai 2026 Reisen');
            _setListCell('positionen', 1, 'stunden',    '4');
            _setListCell('positionen', 1, 'satz_euro',  '0');
            dsListCalcRow('positionen', 1);

            dsListRecalc('positionen');
            dsListRebuildTable('positionen');
        }

        // arbeitspakete Test-Zeilen
        if (window._dsListData.hasOwnProperty('arbeitspakete')) {
            window._dsListData['arbeitspakete'] = [];
            dsListAddRow('arbeitspakete');
            dsListAddRow('arbeitspakete');

            _setListCell('arbeitspakete', 0, 'ap_nr',        'AP-1');
            _setListCell('arbeitspakete', 0, 'beschreibung', 'Konzeption und Analyse');
            _setListCell('arbeitspakete', 0, 'anzahl',       '1');
            _setListCell('arbeitspakete', 0, 'preis_euro',   '3500');
            dsListCalcRow('arbeitspakete', 0);

            _setListCell('arbeitspakete', 1, 'ap_nr',        'AP-2');
            _setListCell('arbeitspakete', 1, 'beschreibung', 'Implementierung');
            _setListCell('arbeitspakete', 1, 'anzahl',       '2');
            _setListCell('arbeitspakete', 1, 'preis_euro',   '4500');
            dsListCalcRow('arbeitspakete', 1);

            dsListRecalc('arbeitspakete');
            dsListRebuildTable('arbeitspakete');
        }
    }
}

// ── Hilfsfunktionen ───────────────────────────────────────────────────────

function _setListCell(listName, rowIdx, key, value) {
    if (!window._dsListData[listName] || !window._dsListData[listName][rowIdx]) return;
    window._dsListData[listName][rowIdx][key] = value;
    const inp = document.querySelector(
        `[data-list="${listName}"][data-row="${rowIdx}"][data-key="${key}"]`
    );
    if (inp) inp.value = value;
}

function _setComputedVar(name, value) {
    const inp = document.getElementById(`dv-${name}`);
    if (inp) inp.value = value;
}

function _parseNumber(val) {
    if (typeof val === 'number') return val;
    if (!val && val !== 0) return 0;
    // "1.234,56" → 1234.56  oder  "1234.56" → 1234.56
    const s = String(val).trim()
        .replace(/\./g, '')   // Tausender-Punkt entfernen
        .replace(',', '.');   // Dezimal-Komma → Punkt
    return parseFloat(s) || 0;
}

function _formatEuro(val) {
    return new Intl.NumberFormat('de-DE', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
    }).format(val);
}

function _formatEuroDE(val) {
    // Format für Assembler: "7.600,00"
    return _formatEuro(val);
}

function _typeBadge(type) {
    const map = {
        string:   ['ds-badge-gray',  'abc'],
        date:     ['ds-badge-blue',  '📅'],
        currency: ['ds-badge-green', '€'],
        list:     ['ds-badge-amber', '≡'],
    };
    const [cls, icon] = map[type] || ['ds-badge-gray', type];
    return `<span class="ds-badge ${cls}" style="font-size:8px;">${icon}</span>`;
}

function _varPlaceholder(v) {
    const map = {
        string:   v.name.replace(/_/g, ' '),
        date:     'TT.MM.JJJJ',
        currency: '0,00',
    };
    return map[v.type] || '';
}

function _getSchemaForList(listName) {
    // Aus aktuellem Template-State lesen
    const varDef = (window._dsAllVars || []).find(v => v.name === listName);
    return varDef?.item_schema || {};
}

function _getColConfig(listName, cols) {
    // Spalten-Konfiguration je Liste
    const configs = {
        positionen: [
            { key: 'pos_nr',     label: 'Pos.',      width: '40px',  type: 'string',   inputType: 'text',   align: 'left',  placeholder: '1.' },
            { key: 'zeitraum',   label: 'Zeitraum',  width: '25%',   type: 'string',   inputType: 'text',   align: 'left',  placeholder: 'April 2026' },
            { key: 'stunden',    label: 'Std.',       width: '50px',  type: 'decimal',  inputType: 'text',   align: 'right', placeholder: '80' },
            { key: 'satz_euro',  label: 'Satz €',    width: '70px',  type: 'currency', inputType: 'text',   align: 'right', placeholder: '95,00' },
            { key: 'betrag_euro',label: 'Betrag €',  width: '80px',  type: 'currency', inputType: 'text',   align: 'right', placeholder: '0,00' },
        ],
        arbeitspakete: [
            { key: 'ap_nr',      label: 'AP',         width: '50px',  type: 'string',   inputType: 'text',   align: 'left',  placeholder: 'AP-1' },
            { key: 'beschreibung',label: 'Beschreibung', width: '35%', type: 'string',  inputType: 'text',   align: 'left',  placeholder: 'Beschreibung' },
            { key: 'anzahl',     label: 'Anz.',       width: '45px',  type: 'decimal',  inputType: 'text',   align: 'right', placeholder: '1' },
            { key: 'preis_euro', label: 'Preis €',   width: '75px',  type: 'currency', inputType: 'text',   align: 'right', placeholder: '0,00' },
            { key: 'betrag_euro',label: 'Betrag €',  width: '80px',  type: 'currency', inputType: 'text',   align: 'right', placeholder: '0,00' },
        ],
    };

    return configs[listName] || cols.map(([key, type]) => ({
        key, label: key, width: 'auto', type, inputType: 'text', align: 'left', placeholder: '',
    }));
}

// ── CSS für Listen-Tabellen ───────────────────────────────────────────────

function dsInjectListStyles() {
    if (document.getElementById('ds-list-styles')) return;
    const style = document.createElement('style');
    style.id = 'ds-list-styles';
    style.textContent = `
        /* Listen-Variable Container */
        .ds-list-var {
            margin-bottom: 10px;
            border: 1px solid var(--border-color, #e5e7eb);
            border-radius: 6px;
            overflow: hidden;
        }
        .ds-list-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 6px 8px;
            background: var(--bg-secondary, #f8fafc);
            border-bottom: 1px solid var(--border-color, #e5e7eb);
        }
        .ds-list-title {
            font-size: 11px;
            font-weight: 600;
            color: var(--abcona-blue, #163258);
            font-family: monospace;
        }
        .ds-list-add-btn {
            font-size: 10px;
            padding: 2px 8px;
            border: 1px solid var(--abcona-blue, #163258);
            border-radius: 3px;
            background: transparent;
            color: var(--abcona-blue, #163258);
            cursor: pointer;
            transition: all 0.15s;
        }
        .ds-list-add-btn:hover {
            background: var(--abcona-blue, #163258);
            color: white;
        }

        /* Tabelle */
        .ds-list-table-wrap {
            overflow-x: auto;
        }
        .ds-list-table {
            width: 100%;
            border-collapse: collapse;
            font-size: 10px;
        }
        .ds-list-table thead th {
            background: #163258;
            color: white;
            font-size: 9px;
            font-weight: 600;
            padding: 4px 5px;
            text-align: left;
            white-space: nowrap;
        }
        .ds-list-row:nth-child(even) {
            background: #f8fafc;
        }
        .ds-list-cell-input {
            width: 100%;
            border: none;
            background: transparent;
            font-size: 10px;
            padding: 3px 4px;
            color: var(--text-primary, #1a1a1a);
            outline: none;
            font-family: inherit;
        }
        .ds-list-cell-input:focus {
            background: #fffbeb;
            box-shadow: inset 0 0 0 1px #f59e0b;
        }
        .ds-list-cell-input[data-key="betrag_euro"] {
            font-weight: 600;
            color: #163258;
        }

        /* Löschen-Button */
        .ds-list-del-btn {
            border: none;
            background: transparent;
            color: #ccc;
            cursor: pointer;
            padding: 2px 4px;
            font-size: 10px;
            border-radius: 3px;
            transition: all 0.15s;
        }
        .ds-list-del-btn:hover {
            color: #ef4444;
            background: #fee2e2;
        }

        /* Footer mit Summe */
        .ds-list-footer {
            padding: 5px 8px;
            border-top: 1px solid var(--border-color, #e5e7eb);
            background: var(--bg-secondary, #f8fafc);
        }
        .ds-list-sum-row {
            display: flex;
            justify-content: space-between;
            font-size: 10px;
            font-weight: 600;
            color: #163258;
        }

        /* Berechnete Variablen */
        .ds-var-computed .ds-var-input-computed {
            background: #f0f9ff;
            color: #163258;
            font-weight: 600;
            border-color: #bae6fd !important;
        }
        .ds-var-type-calc {
            font-size: 8px;
            color: #0ea5e9;
            font-style: italic;
        }
        .ds-var-req {
            color: #ef4444;
            font-weight: 700;
            margin-left: 2px;
        }
        .ds-var-required .ds-var-key {
            color: var(--abcona-blue, #163258);
        }
        .ds-var-label-wrap {
            display: flex;
            align-items: center;
            gap: 4px;
            margin-bottom: 2px;
        }
    `;
    document.head.appendChild(style);
}

// ── Exports ───────────────────────────────────────────────────────────────
window.dsRenderVars        = dsRenderVars;
window.dsCollectAllVars    = dsCollectAllVars;
window.dsFillTestData      = dsFillTestData;
window.dsListAddRow        = dsListAddRow;
window.dsListDeleteRow     = dsListDeleteRow;
window.dsListCellChanged   = dsListCellChanged;
window.dsListRebuildTable  = dsListRebuildTable;
window.dsInjectListStyles  = dsInjectListStyles;

