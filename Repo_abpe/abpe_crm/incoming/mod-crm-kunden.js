/* ============================================================
   ABpE CRM — mod-crm-kunden.js  v2.1
   Kunden Detail-Panel: Stammdaten, Ansprechpartner, Notizen
   ============================================================ */

const CRM_Kunden = {

    _data: null,
    _activeTab: 'stammdaten',

    renderDetail(d) {
        const I = window.CRM_I18N || { t: (k, f) => f || k, status: s => s || '' };
        const panel = document.getElementById('crm-detail-panel');
        if (!panel) return;
        this._data = d;
        this._activeTab = 'stammdaten';
        CRM_Edit._origSave = CRM_Edit._origSave || CRM_Edit.save.bind(CRM_Edit);
        CRM_Edit.save = function(crm_id, payload) {
            return fetch('/crm/api/account/' + crm_id + '/update/', {
                method: 'POST',
                headers: {'Content-Type':'application/json','X-CSRFToken':CRM.getCsrf(),'X-Requested-With':'XMLHttpRequest'},
                body: JSON.stringify(payload),
            }).then(function(r){return r.json();});
        };
        const initials = (d.name || '').substring(0, 2).toUpperCase();
        const status   = d.cstm ? d.cstm.status : 'unbekannt';
        const badgeCls = status === 'aktiv' ? 'crm-badge-aktiv' : status === 'passiv' ? 'crm-badge-passiv' : 'crm-badge-warning';
        const crm_id   = d.crm_id;
        const firstPhone = (d.phones && d.phones.length) ? d.phones[0].raw : '';
        panel.innerHTML =
            '<div class="crm-detail-head">' +
            '<div class="crm-detail-avatar-row">' +
            '<div style="width:46px;height:46px;border-radius:8px;background:#2a4a7a;display:flex;align-items:center;justify-content:center;font-size:14px;font-weight:700;color:#fff;flex-shrink:0">' + initials + '</div>' +
            '<div style="flex:1;min-width:0">' +
            '<div style="display:flex;align-items:center;gap:6px;flex-wrap:wrap">' +
            '<span ondblclick="CRM_Edit.inlineEdit(this,\'' + crm_id + '\',\'name\')" data-value="' + (d.name || '').replace(/"/g, '&quot;') + '" style="font-size:14px;font-weight:700;color:#fff;cursor:pointer;border-bottom:1px dashed rgba(255,255,255,.4)">' + (d.name || '') + '</span>' +
            '<span class="crm-badge ' + badgeCls + '">' + I.status(status) + '</span>' +
            '</div>' +
            '<div class="crm-detail-sub">' + (d.address && d.address.city ? d.address.city : '') + (d.cstm && d.cstm.kunden_nr ? ' · ' + I.t('kd_nummer', 'Kd-Nr.') + ' ' + d.cstm.kunden_nr : '') + '</div>' +
            (d.industry ? '<div class="crm-detail-sub">' + d.industry + '</div>' : '') +
            '</div>' +
            '</div>' +
            '<div class="crm-detail-actions">' +
            '<button class="crm-action-btn crm-action-btn-primary" onclick="CRM_Kunden.call(\'' + firstPhone + '\')"><i class="bi bi-telephone"></i> ' + I.t('anrufen', 'Anrufen') + '</button>' +
            '<button class="crm-action-btn crm-action-btn-secondary" onclick="CRM_Kunden.email(\'' + ((d.emails && d.emails.find(function(e){return e.primary;})) ? d.emails.find(function(e){return e.primary;}).email : (d.emails && d.emails[0] ? d.emails[0].email : '')) + '\')"><i class="bi bi-envelope"></i> ' + I.t('e_mail', 'E-Mail') + '</button>' +
            '<button class="crm-action-btn crm-action-btn-secondary" onclick="crmEmailPopupKunde(CRM_Kunden._data)" title="' + I.t('email_aus_vorlage', 'E-Mail aus Vorlage') + '"><i class="bi bi-envelope-paper"></i> ' + I.t('vorlage', 'Vorlage') + '</button>' +
            (d.website ? '<button class="crm-action-btn crm-action-btn-secondary" onclick="window.open(\'' + d.website + '\',\'_blank\')"><i class="bi bi-globe"></i> ' + I.t('web', 'Web') + '</button>' : '') +
            '<button class="crm-action-btn crm-action-btn-secondary" onclick="CRM_Kunden.newAnfrage(\'' + crm_id + '\')"><i class="bi bi-plus"></i> ' + I.t('anfrage', 'Anfrage') + '</button>' +
            '<button class="crm-action-btn" onclick="CRM_Kunden.confirmDelete(\'' + crm_id + '\')" style="margin-left:auto;background:none;border:1px solid rgba(248,113,113,.5);color:#f87171;border-radius:6px;padding:4px 10px;cursor:pointer;font-size:11px" title="' + I.t('kunde_loeschen', 'Kunde löschen') + '"><i class="bi bi-trash"></i></button>' +
            '</div>' +
            '</div>' +
            '<div class="crm-detail-tabs">' +
            '<div class="crm-detail-tab active" onclick="CRM_Kunden.switchTab(\'stammdaten\',this)">' + I.t('stammdaten', 'Stammdaten') + '</div>' +
            '<div class="crm-detail-tab" onclick="CRM_Kunden.switchTab(\'ansprechpartner\',this)">' + I.t('ansprechpartner', 'Ansprechpartner') + '</div>' +
            '<div class="crm-detail-tab" onclick="CRM_Kunden.switchTab(\'anfragen\',this)">' + I.t('anfragen', 'Anfragen') + '</div>' +
            '<div class="crm-detail-tab" onclick="CRM_Kunden.switchTab(\'notizen\',this)">' + I.t('notizen', 'Notizen') + '</div>' +
            '<div class="crm-detail-tab" onclick="CRM_Kunden.switchTab(\'dokumente\',this)">' + I.t('dokumente', 'Dokumente') + '</div>' +
            '</div>' +
            '<div class="crm-detail-body" id="kunden-tab-body">' +
            this.renderStammdaten(d) +
            '</div>';
    },

    switchTab(tab, el) {
        this._activeTab = tab;
        document.querySelectorAll('.crm-detail-tab').forEach(function(t) { t.classList.remove('active'); });
        if (el) el.classList.add('active');
        const body = document.getElementById('kunden-tab-body');
        if (!body) return;
        const d = this._data;
        if (tab === 'stammdaten')      body.innerHTML = this.renderStammdaten(d);
        if (tab === 'ansprechpartner') body.innerHTML = this.renderAnsprechpartner(d);
        if (tab === 'anfragen')        body.innerHTML = this.renderAnfragen(d);
        if (tab === 'notizen')         body.innerHTML = this.renderNotizen(d);
        if (tab === 'dokumente')       body.innerHTML = this.renderDokumente(d);
        if (typeof CRM_Edit !== 'undefined') CRM_Edit.clearSelection();
    },

    renderStammdaten(d) {
        const I = window.CRM_I18N || { t: (k, f) => f || k, status: s => s || '', statusOpts: () => [], accountTypeOpts: () => [], phoneLabel: f => f };
        const c = d.cstm || {};
        const crm_id = d.crm_id;
        const E = CRM_Edit;

        function row(icon, label, value, field, type, opts) {
            if (!value || value === 'None') return '';
            return '<div class="crm-info-row">' +
                E.renderCheckbox(field, value, label) +
                '<i class="bi ' + icon + '" style="color:var(--abcona-blue);font-size:12px;width:14px;flex-shrink:0"></i>' +
                '<span style="font-size:10px;color:var(--text-muted);min-width:70px;flex-shrink:0">' + label + '</span>' +
                E.editField(crm_id, field, value, type, opts) +
                '<button data-copy="' + value.replace(/"/g, '&quot;') + '" onclick="CRM_Edit.copyText(this)" style="background:none;border:none;cursor:pointer;color:var(--text-muted);padding:0 3px;font-size:11px;opacity:0" class="crm-row-copy"><i class="bi bi-clipboard"></i></button>' +
                '</div>';
        }

        function roRow(icon, label, value) {
            if (!value || value === 'None') return '';
            return '<div class="crm-info-row">' +
                '<i class="bi ' + icon + '" style="color:var(--abcona-blue);font-size:12px;width:14px;flex-shrink:0"></i>' +
                '<span style="font-size:10px;color:var(--text-muted);min-width:70px;flex-shrink:0">' + label + '</span>' +
                '<span style="font-size:10px;color:var(--text-muted);flex:1">' + value + '</span>' +
                '</div>';
        }

        const bil = d.billing_address || {};
        const bilStr = [bil.street, bil.postalcode && bil.city ? bil.postalcode + ' ' + bil.city : bil.city, bil.state, bil.country].filter(Boolean).join(', ');
        const shi = d.shipping_address || {};
        const shiStr = [shi.street, shi.postalcode && shi.city ? shi.postalcode + ' ' + shi.city : shi.city, shi.state, shi.country].filter(Boolean).join(', ');

        let emailsHtml = '';
        (d.emails || []).forEach(function(e) {
            const gesperrt = e.opt_out || e.invalid_email;
            const rowStyle = gesperrt ? 'opacity:.55' : '';
            const textStyle = gesperrt ? 'text-decoration:line-through' : '';
            const primaerBadge = e.primary ? '<span style="font-size:9px;padding:1px 5px;border-radius:10px;background:#dbeafe;color:#1d4ed8;flex-shrink:0">' + I.t('primaer', 'Primär') + '</span>' : '';
            const gesperrtBadge = gesperrt ? '<span style="font-size:9px;padding:1px 5px;border-radius:10px;background:#fee2e2;color:#dc2626;flex-shrink:0">' + I.t('gesperrt', 'Gesperrt') + '</span>' : '';
            const kampagneChecked2 = e.kampagne_ok ? 'checked' : '';
            const kampagneColor2 = e.kampagne_ok ? '#15803d' : '#9ca3af';
            const kampagneHtml2 = gesperrt ? '' :
                '<label style="display:flex;align-items:center;gap:2px;cursor:pointer;flex-shrink:0;margin-left:2px">' +
                '<input type="checkbox" ' + kampagneChecked2 + ' onchange="CRM_Kunden._toggleKampagne(\'' + crm_id + '\',\'' + e.email + '\',this.checked)" style="width:11px;height:11px;cursor:pointer;accent-color:#15803d">' +
                '<span style="font-size:9px;color:' + kampagneColor2 + ';white-space:nowrap">' + I.t('kamp', 'Kamp.') + '</span></label>';
            const gesperrtChecked2 = (e.opt_out || e.invalid_email) ? 'checked' : '';
            const gesperrtColor2 = (e.opt_out || e.invalid_email) ? '#dc2626' : '#9ca3af';
            const gesperrtHtml2 =
                '<label style="display:flex;align-items:center;gap:2px;cursor:pointer;flex-shrink:0;margin-left:2px">' +
                '<input type="checkbox" ' + gesperrtChecked2 + ' onchange="CRM_Kunden._toggleGesperrt(\'' + crm_id + '\',\'' + e.email + '\',this.checked)" style="width:11px;height:11px;cursor:pointer;accent-color:#dc2626">' +
                '<span style="font-size:9px;color:' + gesperrtColor2 + ';white-space:nowrap">' + I.t('gesperrt', 'Gesperrt') + '</span></label>';
            const deleteBtn2 = '<button onclick="CRM_Kunden._deleteEmail(\'' + crm_id + '\',\'' + e.email + '\')" title="' + I.t('loeschen', 'Löschen') + '" style="background:none;border:none;cursor:pointer;color:var(--badge-error-text);padding:0 3px;font-size:11px"><i class="bi bi-trash3"></i></button>';
            const primaryBtn2 = !e.primary && !gesperrt ? '<button onclick="CRM_Kunden._setPrimary(\'' + crm_id + '\',\'' + e.email + '\')" title="' + I.t('als_primaer_setzen', 'Als Primär setzen') + '" style="background:none;border:none;cursor:pointer;color:var(--abcona-blue);padding:0 3px;font-size:11px"><i class="bi bi-star"></i></button>' : '';
            emailsHtml += '<div class="crm-info-row" style="' + rowStyle + '">' +
                (gesperrt ? '<span style="width:12px;flex-shrink:0"></span>' : E.renderCheckbox('email_' + e.email, e.email, I.t('e_mail', 'E-Mail'))) +
                '<i class="bi bi-envelope" style="color:var(--abcona-blue);font-size:12px;width:14px;flex-shrink:0"></i>' +
                '<span style="font-size:10px;color:var(--abcona-blue);flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;cursor:pointer;' + textStyle + '" onclick="CRM_Kunden.email(\'' + e.email + '\')" title="' + I.t('email_oeffnen', 'E-Mail öffnen') + '">' + e.email + '</span>' +
                primaryBtn2 + primaerBadge + gesperrtBadge + kampagneHtml2 + gesperrtHtml2 + deleteBtn2 +
                '<button data-copy="' + e.email + '" onclick="CRM_Edit.copyText(this)" style="background:none;border:none;cursor:pointer;color:var(--text-muted);padding:0 3px;font-size:11px"><i class="bi bi-clipboard"></i></button>' +
                '</div>';
        });
        emailsHtml += E.renderEmailAdd(crm_id);

        const leftHtml =
            E.section(I.t('firma', 'Firma'),
                row('bi-building', I.t('name', 'Name'), d.name, 'name') +
                row('bi-tag', I.t('typ', 'Typ'), d.account_type, 'account_type', 'select', I.accountTypeOpts()) +
                row('bi-briefcase', I.t('branche', 'Branche'), d.industry, 'industry') +
                row('bi-globe', I.t('website', 'Website'), d.website, 'website') +
                row('bi-people', I.t('mitarbeiter', 'Mitarbeiter'), d.employees, 'employees') +
                row('bi-currency-euro', I.t('jahresumsatz', 'Jahresumsatz'), d.annual_revenue, 'annual_revenue') +
                row('bi-star', I.t('einstufung', 'Einstufung'), d.rating, 'rating') +
                (d.description ? '<div class="crm-info-row" style="align-items:flex-start"><i class="bi bi-text-paragraph" style="color:var(--abcona-blue);font-size:12px;width:14px;flex-shrink:0;margin-top:2px"></i><span style="font-size:10px;color:var(--text-muted);min-width:70px;flex-shrink:0">' + I.t('beschreibung', 'Beschreibung') + '</span>' + E.editField(crm_id, 'description', d.description, 'textarea') + '</div>' : ''),
            true) +
            E.section(I.t('crm_info', 'CRM Info'),
                row('bi-circle', I.t('status', 'Status'), c.status, 'account_status_c', 'select', I.statusOpts()) +
                row('bi-hash', I.t('kd_nummer', 'Kd-Nummer'), c.kunden_nr, 'kunden_nummer_c') +
                roRow('bi-clock', I.t('erstellt', 'Erstellt'), d.crm_date_entered) +
                roRow('bi-clock-history', I.t('geaendert', 'Geändert'), d.crm_date_modified),
            false) +
            E.section(I.t('adressen', 'Adressen'),
                '<div style="font-size:10px;font-weight:600;color:var(--abcona-blue);margin-bottom:4px"><i class="bi bi-receipt"></i> ' + I.t('rechnungsadresse', 'Rechnungsadresse') + '</div>' +
                (bilStr ? '<div class="crm-info-row">' + E.renderCheckbox('adr_billing', bilStr, I.t('rechnungsadresse', 'Rechnungsadresse')) + '<span style="font-size:11px;flex:1">' + bilStr + '</span><button onclick="CRM_Kunden.editAdresse(\'' + crm_id + '\',\'billing\')" style="background:none;border:none;cursor:pointer;color:var(--abcona-blue);font-size:11px"><i class="bi bi-pencil"></i></button><button onclick="CRM_Kunden._clearAdresse(\'' + crm_id + '\',\'billing\')" style="background:none;border:none;cursor:pointer;color:var(--badge-error-text);font-size:11px"><i class="bi bi-trash3"></i></button></div>' : '<div style="font-size:10px;color:var(--text-muted);font-style:italic">' + I.t('leer', '— leer') + ' <button onclick="CRM_Kunden.editAdresse(\'' + crm_id + '\',\'billing\')" style="background:none;border:none;cursor:pointer;color:var(--abcona-blue);font-size:11px"><i class="bi bi-plus"></i> ' + I.t('hinzufuegen', 'Hinzufügen') + '</button></div>') +
                '<div style="font-size:10px;font-weight:600;color:var(--abcona-blue);margin:8px 0 4px"><i class="bi bi-truck"></i> ' + I.t('lieferadresse', 'Lieferadresse') + '</div>' +
                (shiStr ? '<div class="crm-info-row">' + E.renderCheckbox('adr_shipping', shiStr, I.t('lieferadresse', 'Lieferadresse')) + '<span style="font-size:11px;flex:1">' + shiStr + '</span><button onclick="CRM_Kunden.editAdresse(\'' + crm_id + '\',\'shipping\')" style="background:none;border:none;cursor:pointer;color:var(--abcona-blue);font-size:11px"><i class="bi bi-pencil"></i></button><button onclick="CRM_Kunden._clearAdresse(\'' + crm_id + '\',\'shipping\')" style="background:none;border:none;cursor:pointer;color:var(--badge-error-text);font-size:11px"><i class="bi bi-trash3"></i></button></div>' : '<div style="font-size:10px;color:var(--text-muted);font-style:italic">' + I.t('leer', '— leer') + ' <button onclick="CRM_Kunden.editAdresse(\'' + crm_id + '\',\'shipping\')" style="background:none;border:none;cursor:pointer;color:var(--abcona-blue);font-size:11px"><i class="bi bi-plus"></i> ' + I.t('hinzufuegen', 'Hinzufügen') + '</button>' + (bilStr ? ' <button onclick="CRM_Kunden.copyBillingToShipping(\'' + crm_id + '\')" style="background:none;border:none;cursor:pointer;color:var(--abcona-blue);font-size:10px"><i class="bi bi-copy"></i> ' + I.t('von_rechnungsadresse', 'Von Rechnungsadresse') + '</button>' : '') + '</div>'),
            false);

        const rightHtml =
            E.section(I.t('telefon', 'Telefon'),
                (function() {
                    const FIELD_META = {
                        phone_office:    {icon:'bi-telephone', field:'phone_office'},
                        phone_alternate: {icon:'bi-telephone', field:'phone_alternate'},
                        phone_fax:       {icon:'bi-printer',   field:'phone_fax'},
                    };
                    let html = '';
                    const phones = d.phones || [];
                    phones.forEach(function(p) {
                        const meta = FIELD_META[p.field_name] || {icon:'bi-telephone', field:p.field_name};
                        const phLabel = I.phoneLabel(meta.field);
                        html += '<div class="crm-info-row">' +
                            E.renderCheckbox('ph_' + p.id, p.raw, phLabel) +
                            '<i class="bi ' + meta.icon + '" style="color:var(--abcona-blue);font-size:12px;width:14px;flex-shrink:0"></i>' +
                            '<span style="font-size:10px;color:var(--text-muted);min-width:65px;flex-shrink:0">' + (p.label || phLabel) + '</span>' +
                            '<span style="font-size:11px;flex:1;cursor:pointer" onclick="CRM_Kunden.call(\'' + p.raw + '\')">' + p.raw + '</span>' +
                            '<button data-copy="' + p.raw + '" onclick="CRM_Edit.copyText(this)" title="' + I.t('kopieren', 'Kopieren') + '" style="background:none;border:none;cursor:pointer;color:var(--text-muted);padding:0 3px;font-size:11px"><i class="bi bi-clipboard"></i></button>' +
                            '<button onclick="CRM_Kunden._deletePhone(\'' + crm_id + '\',' + p.id + ')" title="' + I.t('loeschen', 'Löschen') + '" style="background:none;border:none;cursor:pointer;color:var(--badge-error-text);padding:0 3px;font-size:11px"><i class="bi bi-trash3"></i></button>' +
                            '</div>';
                    });
                    const formId = 'ph_add_form_' + crm_id;
                    html += '<div id="' + formId + '" style="display:none;gap:4px;flex-wrap:wrap;padding:4px 0;align-items:center" class="crm-info-row">' +
                        '<select id="ph_add_typ_' + crm_id + '" style="font-size:11px;padding:3px;border:1px solid var(--border-color);border-radius:5px">' +
                        '<option value="phone_office">' + I.t('buero', 'Büro') + '</option>' +
                        '<option value="phone_alternate">' + I.t('alternativ', 'Alternativ') + '</option>' +
                        '<option value="phone_fax">' + I.t('fax', 'Fax') + '</option>' +
                        '</select>' +
                        '<input id="ph_add_nr_' + crm_id + '" type="tel" placeholder="+49..." style="flex:1;font-size:11px;padding:3px;border:1px solid var(--border-color);border-radius:5px;min-width:100px">' +
                        '<input id="ph_add_lbl_' + crm_id + '" type="text" placeholder="' + I.t('bezeichnung_opt', 'Bezeichnung (opt.)') + '" style="flex:1;font-size:11px;padding:3px;border:1px solid var(--border-color);border-radius:5px;min-width:80px">' +
                        '<button onclick="CRM_Kunden._addPhone(\'' + crm_id + '\')" style="background:var(--status-green);color:#fff;border:none;border-radius:5px;padding:3px 8px;cursor:pointer;font-size:11px"><i class="bi bi-check-lg"></i></button>' +
                        '<button onclick="document.getElementById(\'' + formId + '\').style.display=\'none\'" style="background:var(--abcona-gray-card);border:1px solid var(--border-color);border-radius:5px;padding:3px 6px;cursor:pointer;font-size:11px"><i class="bi bi-x"></i></button>' +
                        '</div>' +
                        '<button onclick="document.getElementById(\'' + formId + '\').style.display=\'flex\'" style="background:none;border:1px dashed var(--border-color);border-radius:5px;padding:2px 8px;font-size:10px;color:var(--abcona-blue);cursor:pointer;margin-top:3px"><i class="bi bi-plus"></i> ' + I.t('telefon_hinzufuegen', 'Telefon hinzufügen') + '</button>';
                    return html;
                })(),
            true) +
            E.section(I.t('e_mail', 'E-Mail'), emailsHtml, true) +
            '';

        return '<div class="crm-two-col-info"><div class="crm-col-left">' + leftHtml + '</div><div class="crm-col-right">' + rightHtml + '</div></div>';
    },

    editAdresse(crm_id, typ) {
        const I = window.CRM_I18N || { t: (k, f) => f || k };
        const d = this._data;
        const prefix = typ === 'billing' ? 'billing_address' : 'shipping_address';
        const existing = typ === 'billing' ? (d.billing_address || {}) : (d.shipping_address || {});
        const title = typ === 'billing' ? I.t('rechnungsadresse_bearbeiten', 'Rechnungsadresse bearbeiten') : I.t('lieferadresse_bearbeiten', 'Lieferadresse bearbeiten');
        const old = document.getElementById('adr-edit-form');
        if (old) old.remove();
        const form = document.createElement('div');
        form.id = 'adr-edit-form';
        form.style.cssText = 'position:fixed;top:50%;left:50%;transform:translate(-50%,-50%);background:var(--abcona-dark-card,#1a2744);color:#fff;border-radius:8px;border:1px solid var(--border-color);padding:16px;z-index:1000;min-width:300px;box-shadow:0 4px 20px rgba(0,0,0,.3)';
        form.innerHTML = '<div style="font-size:13px;font-weight:600;color:var(--abcona-blue-light,#6fa3d8);margin-bottom:12px">' + title + '</div>' +
            [
                ['street', I.t('strasse', 'Straße')],
                ['city', I.t('stadt', 'Stadt')],
                ['postalcode', I.t('plz', 'PLZ')],
                ['state', I.t('bundesland', 'Bundesland')],
                ['country', I.t('land', 'Land')],
            ].map(function(pair) {
                const f = pair[0]; const l = pair[1]; const v = existing[f] || '';
                return '<div style="margin-bottom:6px"><label style="font-size:10px;color:rgba(255,255,255,.6);display:block;margin-bottom:2px">' + l + '</label><input id="adr_' + f + '" type="text" value="' + v.replace(/"/g, '&quot;') + '" style="width:100%;font-size:11px;padding:4px;border:1px solid var(--border-color);border-radius:5px;background:rgba(255,255,255,.1);color:#fff"></div>';
            }).join('') +
            '<div style="display:flex;gap:6px;margin-top:8px"><button onclick="CRM_Kunden.saveAdresse(\'' + crm_id + '\',\'' + prefix + '\')" style="background:var(--status-green);color:#fff;border:none;border-radius:5px;padding:5px 14px;cursor:pointer;font-size:12px"><i class="bi bi-check-lg"></i> ' + I.t('speichern', 'Speichern') + '</button><button onclick="document.getElementById(\'adr-edit-form\').remove()" style="background:rgba(255,255,255,.1);border:1px solid var(--border-color);border-radius:5px;padding:5px 10px;cursor:pointer;font-size:12px;color:#fff"><i class="bi bi-x"></i> ' + I.t('abbrechen', 'Abbrechen') + '</button></div>';
        document.body.appendChild(form);
    },

    async saveAdresse(crm_id, prefix) {
        const payload = {action: 'update'};
        ['street', 'city', 'postalcode', 'state', 'country'].forEach(function(f) {
            const el = document.getElementById('adr_' + f);
            if (el) payload[prefix + '_' + f] = el.value.trim();
        });
        const res = await CRM_Edit.save(crm_id, payload);
        if (res.ok) { const form = document.getElementById('adr-edit-form'); if (form) form.remove(); CRM.loadDetail(crm_id); }
    },

    async _clearAdresse(crm_id, typ) {
        if (!confirm('Adresse l\u00f6schen?')) return;
        const prefix = typ === 'billing' ? 'billing_address' : 'shipping_address';
        const payload = {action: 'update'};
        ['street', 'city', 'postalcode', 'state', 'country'].forEach(function(f) { payload[prefix + '_' + f] = ''; });
        await CRM_Edit.save(crm_id, payload);
        CRM.loadDetail(crm_id);
    },

    async copyBillingToShipping(crm_id) {
        const bil = (this._data && this._data.billing_address) || {};
        const payload = {action: 'update'};
        ['street', 'city', 'postalcode', 'state', 'country'].forEach(function(f) { payload['shipping_address_' + f] = bil[f] || ''; });
        const res = await CRM_Edit.save(crm_id, payload);
        if (res.ok) CRM.loadDetail(crm_id);
    },

    renderAnsprechpartner(d) {
        const I = window.CRM_I18N || { t: (k, f) => f || k };
        const ap = d.ansprechpartner || [];
        const accountId = d.crm_id;
        const addBtn = '<div style="display:flex;justify-content:flex-end;margin-bottom:8px"><button onclick="CRM_Kunden.newAnsprechpartner(\'' + accountId + '\')" style="padding:5px 12px;font-size:11px;background:var(--abcona-blue);color:#fff;border:none;border-radius:6px;cursor:pointer"><i class="bi bi-person-plus"></i> ' + I.t('neuer_ansprechpartner', 'Neuer Ansprechpartner') + '</button></div>';
        if (!ap.length) return addBtn + '<div class="crm-list-loading"><i class="bi bi-people"></i> ' + I.t('keine_ansprechpartner', 'Keine Ansprechpartner') + '</div>';
        return addBtn + ap.map(function(a) {
            const name      = [a.contact__first_name, a.contact__last_name].filter(Boolean).join(' ');
            const initials  = ((a.contact__first_name || '')[0] || '') + ((a.contact__last_name || '')[0] || '');
            const contactId = a.contact__crm_id || '';
            const phones    = a.phones || [];
            const emails    = a.emails || [];
            const primEmail = emails.find(function(e){return e.primary;}) || emails[0] || null;
            const phoneHtml = phones.map(function(p) {
                return '<div style="font-size:11px;margin-top:2px"><i class="bi bi-telephone" style="color:var(--abcona-blue);font-size:11px"></i> <a href="tel:' + p.raw + '" style="color:var(--text-primary);text-decoration:none">' + p.raw + '</a>' + (p.label ? ' <span style="font-size:9px;color:var(--text-muted)">(' + p.label + ')</span>' : '') + '</div>';
            }).join('');
            const emailHtml = emails.map(function(e) {
                return '<div style="font-size:11px;margin-top:2px"><i class="bi bi-envelope" style="color:var(--abcona-blue);font-size:11px"></i> <span style="color:var(--abcona-blue);cursor:pointer" onclick="CRM_Kunden.email(\'' + e.email.replace(/'/g, "\\'") + '\')">' + e.email + '</span>' + (e.primary ? ' <span style="font-size:9px;padding:1px 4px;border-radius:8px;background:#dbeafe;color:#1d4ed8">' + I.t('primaer', 'Primär') + '</span>' : '') + '</div>';
            }).join('');
            return '<div class="crm-hist-item" style="align-items:flex-start;gap:10px;padding:8px 0">' +
                '<div class="crm-avatar" style="width:32px;height:32px;font-size:10px;flex-shrink:0;cursor:pointer;margin-top:2px"' + (contactId ? ' onclick="CRM_Kunden._openContact(\'' + contactId + '\')"' : '') + '>' + initials.toUpperCase() + '</div>' +
                '<div style="flex:1;min-width:0">' +
                '<div style="font-size:12px;font-weight:600;color:var(--abcona-blue);cursor:pointer"' + (contactId ? ' onclick="CRM_Kunden._openContact(\'' + contactId + '\')"' : '') + '>' + name + ' <i class="bi bi-box-arrow-up-right" style="font-size:9px;opacity:.6"></i></div>' +
                (a.contact__title ? '<div style="font-size:10px;color:var(--text-muted)">' + a.contact__title + '</div>' : '') +
                phoneHtml + emailHtml +
                '</div>' +
                '<div style="display:flex;gap:4px;align-items:center;margin-top:2px">' +
                (phones.length ? '<button class="crm-action-btn crm-action-btn-secondary" style="padding:3px 8px;font-size:10px" onclick="CRM_Kunden.call(\'' + phones[0].raw + '\')" title="' + I.t('anrufen', 'Anrufen') + '"><i class="bi bi-telephone"></i></button>' : '') +
                (primEmail ? '<button class="crm-action-btn crm-action-btn-secondary" style="padding:3px 8px;font-size:10px" onclick="CRM_Kunden.email(\'' + primEmail.email.replace(/'/g, "\\'") + '\')" title="' + I.t('e_mail', 'E-Mail') + '"><i class="bi bi-envelope"></i></button>' : '') +
                (contactId ? '<button class="crm-action-btn crm-action-btn-secondary" style="padding:3px 8px;font-size:10px" onclick="CRM_Kunden._openContact(\'' + contactId + '\')" title="' + I.t('kontakt_oeffnen', 'Kontakt öffnen') + '"><i class="bi bi-pencil"></i></button>' : '') +
                '</div></div>';
        }).join('');
    },

    renderAnfragen(d) {
        const I = window.CRM_I18N || { t: (k, f) => f || k };
        const anf = d.anfragen || [];
        if (!anf.length) return '<div class="crm-list-loading"><i class="bi bi-inbox"></i> ' + I.t('keine_anfragen', 'Keine Anfragen') + '</div>';
        return anf.map(function(a) {
            const badgeCls = a.status === 'placed' ? 'crm-badge-aktiv' : a.status === 'cancelled' ? 'crm-badge-error' : 'crm-badge-warning';
            return '<div class="crm-hist-item"><span class="crm-badge ' + badgeCls + '">' + (a.status || '') + '</span><div style="flex:1;min-width:0"><div style="font-size:11px;font-weight:600">' + (a.title || '') + '</div><div style="font-size:10px;color:var(--text-muted)">' + (a.project_number || '') + '</div></div><span style="font-size:10px;color:var(--text-muted);flex-shrink:0">' + (a.created_at || '').substring(0, 10) + '</span></div>';
        }).join('');
    },

    renderNotizen(d) {
        const I = window.CRM_I18N || { t: (k, f) => f || k };
        const crm_id = d.crm_id;
        const notes = (d.notes || []).map(function(n) {
            return '<div class="crm-hist-item"><span class="crm-badge crm-badge-passiv">' + (n.note_type || 'general') + '</span><div style="flex:1;min-width:0"><div style="font-size:11px">' + (n.note_text || '') + '</div><div style="font-size:10px;color:var(--text-muted)">' + (n.created_by || '') + ' \u00b7 ' + (n.created_at || '').substring(0, 10) + '</div></div></div>';
        }).join('') || '<div style="font-size:11px;color:var(--text-muted);padding:8px 0;font-style:italic">' + I.t('keine_notizen', 'Noch keine Notizen') + '</div>';
        return '<div class="crm-section"><div class="crm-section-label">' + I.t('neue_notiz', 'Neue Notiz') + '</div><textarea class="crm-note-area" id="note-text" placeholder="' + I.t('notiz_eingeben', 'Notiz eingeben...') + '"></textarea><select style="width:100%;margin-top:6px;padding:5px;border:1px solid var(--border-color);border-radius:7px;font-size:12px" id="note-type"><option value="phone">' + I.t('telefonnotiz', 'Telefonnotiz') + '</option><option value="email">' + I.t('email_notiz', 'E-Mail Notiz') + '</option><option value="meeting">' + I.t('besprechung', 'Besprechung') + '</option><option value="general">' + I.t('allgemein', 'Allgemein') + '</option></select><button class="crm-save-btn" onclick="CRM_Kunden.saveNote(\'' + crm_id + '\')"><i class="bi bi-save"></i> ' + I.t('notiz_speichern', 'Notiz speichern') + '</button></div><div class="crm-section"><div class="crm-section-label">' + I.t('verlauf', 'Verlauf') + '</div>' + notes + '</div>';
    },

    renderDokumente(d) {
        const I = window.CRM_I18N || { t: (k, f) => f || k };
        const docs = (d.documents || []).map(function(doc) {
            const titleHtml = doc.view_url ? '<a href="' + doc.view_url + '" target="_blank" style="color:inherit;text-decoration:none">' + (doc.title || '') + '</a>' : (doc.title || '');
            return '<div class="crm-hist-item"><i class="bi bi-file-text" style="color:var(--abcona-blue)"></i><div style="flex:1;min-width:0"><div style="font-size:11px;font-weight:600">' + titleHtml + '</div><div style="font-size:10px;color:var(--text-muted)">' + (doc.doc_type || '') + ' \u00b7 ' + (doc.created_at || '').substring(0, 10) + '</div></div>' + (doc.file_path ? '<a href="' + doc.file_path + '" target="_blank" style="font-size:10px;color:var(--abcona-blue)"><i class="bi bi-download"></i></a>' : '') + '</div>';
        }).join('') || '<div style="font-size:11px;color:var(--text-muted);padding:8px 0;font-style:italic">' + I.t('keine_dokumente', 'Keine Dokumente') + '</div>';
        return '<div class="crm-section">' + docs + '</div>';
    },

    call(phone) {
        const I = window.CRM_I18N || { t: (k, f) => f || k };
        if (!phone) return alert(I.t('keine_telefonnummer', 'Keine Telefonnummer hinterlegt'));
        window.location.href = 'tel:' + phone;
    },

    email(addr) {
        const I = window.CRM_I18N || { t: (k, f) => f || k };
        if (!addr) return alert(I.t('keine_email', 'Keine E-Mail hinterlegt'));
        window.location.href = 'mailto:' + addr;
    },

    async _deleteEmail(crm_id, email) {
        if (!confirm('E-Mail ' + email + ' l\u00f6schen?')) return;
        await CRM_Edit.save(crm_id, {action: 'email_delete', email: email});
        CRM.loadDetail(crm_id);
    },

    async _setPrimary(crm_id, email) {
        await CRM_Edit.save(crm_id, {action: 'email_set_primary', email: email});
        CRM.loadDetail(crm_id);
    },

    async _toggleKampagne(crm_id, email, kampagne_ok) {
        const csrf = (document.cookie.match(/csrftoken=([^;]+)/) || [])[1] || '';
        fetch('/crm/api/account/' + crm_id + '/update/', {method:'POST', headers:{'Content-Type':'application/json','X-CSRFToken':csrf}, body:JSON.stringify({action:'email_kampagne_toggle',email:email,kampagne_ok:kampagne_ok})}).then(function(r){return r.json();}).then(function(d){if(!d.ok)console.warn('Kampagne-Toggle fehlgeschlagen',d);});
    },

    async _toggleGesperrt(crm_id, email, gesperrt) {
        const csrf = (document.cookie.match(/csrftoken=([^;]+)/) || [])[1] || '';
        fetch('/crm/api/account/' + crm_id + '/update/', {method:'POST', headers:{'Content-Type':'application/json','X-CSRFToken':csrf}, body:JSON.stringify({action:'email_gesperrt_toggle',email:email,gesperrt:gesperrt})}).then(function(r){return r.json();}).then(function(d){if(d.ok)CRM.loadDetail(crm_id);});
    },

    newAnfrage(crm_id) {
        window.open('/matching/?new=1&crm_account_id=' + crm_id, 'crm_matching_new', 'width=1200,height=800,resizable=yes,scrollbars=yes');
    },

    saveNote(crm_id) {
        const I = window.CRM_I18N || { t: (k, f) => f || k };
        const text = document.getElementById('note-text') ? document.getElementById('note-text').value.trim() : '';
        const type = document.getElementById('note-type') ? document.getElementById('note-type').value : 'general';
        if (!text) return alert(I.t('bitte_notiz_eingeben', 'Bitte Notiz eingeben'));
        fetch('/crm/api/note/save/', {method:'POST', headers:{'Content-Type':'application/json','X-CSRFToken':CRM.getCsrf(),'X-Requested-With':'XMLHttpRequest'}, body:JSON.stringify({account_crm_id:crm_id,note_text:text,note_type:type})}).then(function(r){return r.json();}).then(function(data){if(data.ok)CRM.loadDetail(crm_id);});
    },

    async _addPhone(crm_id) {
        const typ = document.getElementById('ph_add_typ_' + crm_id);
        const nr  = document.getElementById('ph_add_nr_'  + crm_id);
        const lbl = document.getElementById('ph_add_lbl_' + crm_id);
        if (!nr || !nr.value.trim()) return;
        await CRM_Edit.save(crm_id, {action:'phone_add', field_name:typ.value, nummer:nr.value.trim(), label:lbl ? lbl.value.trim() : '', bean_module:'Accounts'});
        CRM.loadDetail(crm_id);
    },

    async _deletePhone(crm_id, rel_id) {
        if (!confirm('Telefonnummer l\u00f6schen?')) return;
        await CRM_Edit.save(crm_id, {action:'phone_delete', id:rel_id, bean_module:'Accounts'});
        CRM.loadDetail(crm_id);
    },
};

window.CRM_Kunden = CRM_Kunden;

CRM_Kunden._openContact = function(crm_id) {
    window.location.href = '/crm/berater/?detail=' + crm_id;
};

function crmNewKunde() {
    const old = document.getElementById('crm-new-kunde-popup');
    if (old) old.remove();
    const popup = document.createElement('div');
    popup.id = 'crm-new-kunde-popup';
    popup.style.cssText = 'position:fixed;top:50%;left:50%;transform:translate(-50%,-50%);background:#1a2744;color:#fff;border-radius:10px;border:1px solid rgba(255,255,255,.15);padding:20px;z-index:2000;min-width:320px;max-width:95vw;box-shadow:0 8px 40px rgba(0,0,0,.5)';
    popup.innerHTML =
        '<div style="font-size:13px;font-weight:600;color:#fff;margin-bottom:14px"><i class="bi bi-building-add"></i> Neuer Kunde</div>' +
        '<div style="margin-bottom:8px"><label style="font-size:10px;color:rgba(255,255,255,.6);display:block;margin-bottom:3px">Firmenname <span style="color:#f87171">*</span></label><input id="nk-name" type="text" placeholder="Firmenname (Pflicht)" style="width:100%;font-size:12px;padding:5px;border:1px solid rgba(255,255,255,.2);border-radius:5px;background:rgba(255,255,255,.1);color:#fff;box-sizing:border-box"></div>' +
        '<div style="margin-bottom:8px"><label style="font-size:10px;color:rgba(255,255,255,.6);display:block;margin-bottom:3px">Stadt</label><input id="nk-city" type="text" placeholder="Stadt (optional)" style="width:100%;font-size:12px;padding:5px;border:1px solid rgba(255,255,255,.2);border-radius:5px;background:rgba(255,255,255,.1);color:#fff;box-sizing:border-box"></div>' +
        '<div id="nk-error" style="color:#f87171;font-size:11px;margin-bottom:8px;display:none"></div>' +
        '<div style="display:flex;gap:8px;margin-top:14px"><button id="nk-save" style="flex:1;background:#10b981;color:#fff;border:none;border-radius:6px;padding:8px;cursor:pointer;font-size:12px;font-weight:600"><i class="bi bi-check-lg"></i> Anlegen</button><button onclick="document.getElementById(\'crm-new-kunde-popup\').remove()" style="background:rgba(255,255,255,.1);color:#fff;border:none;border-radius:6px;padding:8px 14px;cursor:pointer;font-size:12px"><i class="bi bi-x"></i></button></div>';
    document.body.appendChild(popup);
    document.getElementById('nk-name').focus();
    document.getElementById('nk-save').addEventListener('click', async function() {
        const name = document.getElementById('nk-name').value.trim();
        const city = document.getElementById('nk-city').value.trim();
        const errEl = document.getElementById('nk-error');
        if (!name) { errEl.textContent = 'Firmenname ist Pflichtfeld.'; errEl.style.display = 'block'; return; }
        errEl.style.display = 'none'; this.disabled = true;
        try {
            const resp = await fetch('/crm/api/kunden/new/', {method:'POST', headers:{'Content-Type':'application/json','X-CSRFToken':CRM.getCsrf(),'X-Requested-With':'XMLHttpRequest'}, body:JSON.stringify({name:name,city:city})});
            const data = await resp.json();
            if (data.ok) { document.getElementById('crm-new-kunde-popup').remove(); if (typeof crmSearch === 'function') crmSearch(); CRM.loadDetail(data.crm_id); }
            else { errEl.textContent = data.error || 'Fehler beim Anlegen.'; errEl.style.display = 'block'; this.disabled = false; }
        } catch(e) { errEl.textContent = 'Netzwerkfehler.'; errEl.style.display = 'block'; this.disabled = false; }
    });
    document.getElementById('nk-name').addEventListener('keydown', function(e) { if (e.key === 'Enter') document.getElementById('nk-save').click(); });
    setTimeout(function() {
        document.addEventListener('click', function handler(e) {
            const p = document.getElementById('crm-new-kunde-popup');
            if (p && !p.contains(e.target)) { p.remove(); document.removeEventListener('click', handler); }
        });
    }, 200);
}

CRM_Kunden.confirmDelete = function(crm_id) {
    const d = CRM_Kunden._data;
    const name = d ? d.name : crm_id;
    const old = document.getElementById('crm-delete-popup');
    if (old) old.remove();
    const popup = document.createElement('div');
    popup.id = 'crm-delete-popup';
    popup.style.cssText = 'position:fixed;top:50%;left:50%;transform:translate(-50%,-50%);background:#1a2744;color:#fff;border-radius:10px;border:1px solid rgba(248,113,113,.4);padding:22px;z-index:2000;min-width:300px;max-width:95vw;box-shadow:0 8px 40px rgba(0,0,0,.6)';
    popup.innerHTML =
        '<div style="font-size:14px;font-weight:600;color:#f87171;margin-bottom:10px"><i class="bi bi-exclamation-triangle"></i> Kunde l\u00f6schen</div>' +
        '<div style="font-size:12px;color:rgba(255,255,255,.8);margin-bottom:16px;line-height:1.6">Soll <strong>' + name + '</strong> wirklich gel\u00f6scht werden?<br><span style="font-size:11px;color:rgba(255,255,255,.5)">Alle zugeh\u00f6rigen Daten werden ebenfalls entfernt.</span></div>' +
        '<div style="display:flex;gap:8px"><button id="crm-delete-confirm" style="flex:1;background:#dc2626;color:#fff;border:none;border-radius:6px;padding:8px;cursor:pointer;font-size:12px;font-weight:600"><i class="bi bi-trash"></i> Ja, l\u00f6schen</button><button onclick="document.getElementById(\'crm-delete-popup\').remove()" style="background:rgba(255,255,255,.1);color:#fff;border:none;border-radius:6px;padding:8px 14px;cursor:pointer;font-size:12px">Abbrechen</button></div>';
    document.body.appendChild(popup);
    document.getElementById('crm-delete-confirm').addEventListener('click', async function() {
        this.disabled = true; this.innerHTML = '<i class="bi bi-hourglass"></i> L\u00f6schen...';
        try {
            const resp = await fetch('/crm/api/kunden/' + crm_id + '/delete/', {method:'POST', headers:{'Content-Type':'application/json','X-CSRFToken':CRM.getCsrf(),'X-Requested-With':'XMLHttpRequest'}, body:JSON.stringify({confirm:true})});
            const data = await resp.json();
            if (data.ok) {
                document.getElementById('crm-delete-popup').remove();
                const panel = document.getElementById('crm-detail-panel');
                if (panel) panel.innerHTML = '<div style="padding:40px;text-align:center;color:var(--text-muted)"><i class="bi bi-building" style="font-size:32px"></i><div style="margin-top:8px;font-size:12px">Kunde ausw\u00e4hlen</div></div>';
                if (typeof crmSearch === 'function') crmSearch();
            } else { alert('Fehler: ' + (data.error || 'Unbekannter Fehler')); this.disabled = false; }
        } catch(e) { alert('Netzwerkfehler'); this.disabled = false; }
    });
};

function crmEmailPopupKunde(d) {
    const crm_id    = d.crm_id || '';
    const firmaName = d.name   || '';
    const ap        = d.ansprechpartner || [];
    const recipients = [];
    ap.forEach(function(a) {
        const name = [a.contact__first_name, a.contact__last_name].filter(Boolean).join(' ');
        (a.emails || []).forEach(function(e) {
            if (e.email) recipients.push({name:name, email:e.email, first_name:a.contact__first_name||'', last_name:a.contact__last_name||'', crm_id:a.contact__crm_id||'', title:a.contact__title||''});
        });
    });
    (d.emails || []).forEach(function(e) {
        if (e.email) recipients.push({name:firmaName, email:e.email, first_name:'', last_name:firmaName, crm_id:crm_id, title:''});
    });
    const url = '/crm/email/compose/?crm_id=' + encodeURIComponent(crm_id) + '&firma=' + encodeURIComponent(firmaName) + '&recipients=' + encodeURIComponent(JSON.stringify(recipients));
    window.open(url, 'crm_email_compose', 'width=1200,height=800,resizable=yes,scrollbars=yes');
}

CRM_Kunden.newAnsprechpartner = function(accountId) {
    let modal = document.getElementById('crm-new-ap-modal');
    if (modal) modal.remove();
    modal = document.createElement('div');
    modal.id = 'crm-new-ap-modal';
    modal.style.cssText = 'position:fixed;inset:0;z-index:9999;background:rgba(0,0,0,0.5);display:flex;align-items:flex-start;justify-content:center;padding-top:60px';
    modal.innerHTML = '<div style="background:#fff;border-radius:12px;width:460px;overflow:hidden;box-shadow:0 20px 60px rgba(0,0,0,0.25)">'
        + '<div style="background:#163258;padding:14px 18px;display:flex;align-items:center;justify-content:space-between">'
        + '<div style="display:flex;align-items:center;gap:10px;color:#fff"><i class="bi bi-person-plus"></i><span style="font-weight:600;font-size:14px">Neuer Ansprechpartner</span></div>'
        + '<button onclick="document.getElementById(\'crm-new-ap-modal\').remove()" style="background:rgba(255,255,255,0.15);border:none;color:#fff;width:26px;height:26px;border-radius:50%;cursor:pointer;font-size:16px;line-height:1">×</button>'
        + '</div>'
        + '<div style="padding:16px 18px;display:flex;flex-direction:column;gap:10px">'
        + '<div style="display:grid;grid-template-columns:110px 1fr;gap:8px;align-items:center"><label style="font-size:12px;color:#666">Anrede</label>'
        + '<select id="crm-ap-salutation" style="padding:6px 10px;font-size:13px;border:1px solid #ccc;border-radius:7px"><option value="Hr.">Hr.</option><option value="Fr.">Fr.</option><option value="">—</option></select></div>'
        + '<div style="display:grid;grid-template-columns:110px 1fr;gap:8px;align-items:center"><label style="font-size:12px;color:#666">Vorname</label>'
        + '<input id="crm-ap-firstname" type="text" placeholder="Vorname" style="padding:6px 10px;font-size:13px;border:1px solid #ccc;border-radius:7px;width:100%;box-sizing:border-box"></div>'
        + '<div style="display:grid;grid-template-columns:110px 1fr;gap:8px;align-items:center"><label style="font-size:12px;color:#666">Nachname <span style="color:#dc3545">*</span></label>'
        + '<input id="crm-ap-lastname" type="text" placeholder="Nachname (Pflicht)" style="padding:6px 10px;font-size:13px;border:1.5px solid #163258;border-radius:7px;width:100%;box-sizing:border-box"></div>'
        + '<div style="display:grid;grid-template-columns:110px 1fr;gap:8px;align-items:center"><label style="font-size:12px;color:#666">Titel / Funktion</label>'
        + '<input id="crm-ap-title" type="text" placeholder="z.B. Projektleiter" style="padding:6px 10px;font-size:13px;border:1px solid #ccc;border-radius:7px;width:100%;box-sizing:border-box"></div>'
        + '<div style="display:grid;grid-template-columns:110px 1fr;gap:8px;align-items:center"><label style="font-size:12px;color:#666">Telefon</label>'
        + '<input id="crm-ap-phone" type="tel" placeholder="optional" style="padding:6px 10px;font-size:13px;border:1px solid #ccc;border-radius:7px;width:100%;box-sizing:border-box"></div>'
        + '<div style="display:grid;grid-template-columns:110px 1fr;gap:8px;align-items:center"><label style="font-size:12px;color:#666">E-Mail</label>'
        + '<input id="crm-ap-email" type="email" placeholder="optional" style="padding:6px 10px;font-size:13px;border:1px solid #ccc;border-radius:7px;width:100%;box-sizing:border-box"></div>'
        + '<div id="crm-ap-msg" style="font-size:12px;min-height:18px;text-align:center"></div>'
        + '</div>'
        + '<div style="padding:12px 18px;border-top:1px solid #eee;display:flex;justify-content:flex-end;gap:8px">'
        + '<button onclick="document.getElementById(\'crm-new-ap-modal\').remove()" style="padding:7px 16px;border-radius:7px;border:1px solid #ccc;background:transparent;font-size:13px;cursor:pointer">Abbrechen</button>'
        + '<button onclick="CRM_Kunden._saveAnsprechpartner(false,\'' + accountId + '\')" style="padding:7px 16px;border-radius:7px;border:1px solid #163258;background:transparent;color:#163258;font-size:13px;cursor:pointer;font-weight:500"><i class="bi bi-person-check"></i> Anlegen</button>'
        + '<button onclick="CRM_Kunden._saveAnsprechpartner(true,\'' + accountId + '\')" style="padding:7px 16px;border-radius:7px;border:none;background:#163258;color:#fff;font-size:13px;cursor:pointer;font-weight:500"><i class="bi bi-box-arrow-up-right"></i> Anlegen &amp; öffnen</button>'
        + '</div></div>';
    document.body.appendChild(modal);
    modal.addEventListener('click', e => { if (e.target === modal) modal.remove(); });
    setTimeout(() => document.getElementById('crm-ap-lastname')?.focus(), 100);
};

CRM_Kunden._saveAnsprechpartner = async function(openAfter, accountId) {
    const lastname  = document.getElementById('crm-ap-lastname')?.value?.trim();
    const msg       = document.getElementById('crm-ap-msg');
    if (!lastname) {
        if (msg) { msg.style.color='#dc3545'; msg.textContent='Nachname ist Pflichtfeld'; }
        document.getElementById('crm-ap-lastname')?.focus();
        return;
    }
    const salutation = document.getElementById('crm-ap-salutation')?.value || 'Hr.';
    const firstname  = document.getElementById('crm-ap-firstname')?.value?.trim() || '';
    const title      = document.getElementById('crm-ap-title')?.value?.trim() || '';
    const phone      = document.getElementById('crm-ap-phone')?.value?.trim() || '';
    const email      = document.getElementById('crm-ap-email')?.value?.trim() || '';
    if (msg) { msg.style.color='#163258'; msg.textContent='Anlegen...'; }
    const csrf = CRM.getCsrf();
    try {
        const r = await fetch('/crm/api/berater/new/', {
            method:'POST', headers:{'Content-Type':'application/json','X-CSRFToken':csrf},
            body: JSON.stringify({salutation, first_name:firstname, last_name:lastname, title})
        });
        const d = await r.json();
        if (!d.ok) { if(msg){msg.style.color='#dc3545';msg.textContent=d.error||'Fehler';} return; }
        const crm_id = d.crm_id;
        if (phone) {
            await fetch('/crm/api/contact/'+crm_id+'/update/', {
                method:'POST', headers:{'Content-Type':'application/json','X-CSRFToken':csrf},
                body: JSON.stringify({action:'phone_add', nummer:phone, field_name:'phone_office', bean_module:'Contacts'})
            });
        }
        if (email) {
            await fetch('/crm/api/contact/'+crm_id+'/update/', {
                method:'POST', headers:{'Content-Type':'application/json','X-CSRFToken':csrf},
                body: JSON.stringify({action:'email_add', email:email})
            });
        }
        await fetch('/crm/api/contact/'+crm_id+'/link-account/', {
            method:'POST', headers:{'Content-Type':'application/json','X-CSRFToken':csrf},
            body: JSON.stringify({account_crm_id: accountId})
        });
        document.getElementById('crm-new-ap-modal')?.remove();
        if (openAfter) {
            window.location.href = '/crm/berater/?detail=' + crm_id;
        } else {
            CRM.loadDetail(accountId);
        }
    } catch(e) {
        if (msg) { msg.style.color='#dc3545'; msg.textContent='Netzwerkfehler'; }
    }
};

// Auto-open account from URL parameter ?detail=<crm_id>
document.addEventListener('DOMContentLoaded', function() {
    if (!window.location.pathname.includes('/kunden')) return;
    const params = new URLSearchParams(window.location.search);
    const detailId = params.get('detail');
    if (detailId) {
        fetch('/crm/api/kunden/' + detailId + '/', {
            headers: {'X-Requested-With': 'XMLHttpRequest'}
        }).then(function(r) { return r.json(); })
          .then(function(d) {
              if (d.crm_id && typeof CRM_Kunden !== 'undefined') {
                  CRM_Kunden.renderDetail(d);
              }
          });
    }
});
