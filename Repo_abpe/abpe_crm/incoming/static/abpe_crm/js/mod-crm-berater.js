/* ============================================================
   ABpE CRM — mod-crm-berater.js  v2.0
   Detail-Panel: Avatar, Stammdaten, Profil, Notizen, Dokumente
   ============================================================ */

const CRM_Berater = {

    _data: null,
    _activeTab: 'stammdaten',

    // ── Avatar SVG ────────────────────────────────────────
    avatarSVG(salutation) {
        const isFemale = salutation && (salutation.toLowerCase().indexOf('fr') !== -1);
        if (isFemale) {
            return '<svg viewBox="0 0 46 46" xmlns="http://www.w3.org/2000/svg" width="46" height="46">' +
                '<circle cx="23" cy="23" r="23" fill="#2a4a7a"/>' +
                '<circle cx="23" cy="15" r="8" fill="rgba(255,255,255,.35)"/>' +
                '<ellipse cx="23" cy="36" rx="12" ry="8" fill="rgba(255,255,255,.25)"/>' +
                '<ellipse cx="16" cy="11" rx="4" ry="2" fill="rgba(255,255,255,.2)" transform="rotate(-20,16,11)"/>' +
                '<ellipse cx="30" cy="11" rx="4" ry="2" fill="rgba(255,255,255,.2)" transform="rotate(20,30,11)"/>' +
                '</svg>';
        }
        return '<svg viewBox="0 0 46 46" xmlns="http://www.w3.org/2000/svg" width="46" height="46">' +
            '<circle cx="23" cy="23" r="23" fill="#2a4a7a"/>' +
            '<circle cx="23" cy="15" r="8" fill="rgba(255,255,255,.35)"/>' +
            '<ellipse cx="23" cy="36" rx="12" ry="8" fill="rgba(255,255,255,.25)"/>' +
            '</svg>';
    },

    // ── Render Detail Panel ───────────────────────────────
    renderDetail(d) {
        const I = window.CRM_I18N || { t: (k, f) => f || k, status: s => s || '', statusOpts: () => [], kontaktTypOpts: () => [], phoneLabel: f => f };
        const panel = document.getElementById('crm-detail-panel');
        if (!panel) return;
        this._data = d;

        // CRM_Edit auf Contact-Endpoint zurücksetzen
        if (CRM_Edit._origSave) {
            CRM_Edit.save = CRM_Edit._origSave;
        }

        const initials = ((d.first_name || '')[0] || '') + ((d.last_name || '')[0] || '');
        const status   = d.cstm ? d.cstm.kontakt_status : 'unbekannt';
        const badgeCls = status === 'aktiv' ? 'crm-badge-aktiv' : status === 'passiv' ? 'crm-badge-passiv' : 'crm-badge-warning';
        const hasPhoto = d.photo && d.photo.trim();
        const crm_id  = d.crm_id;

        const avatarContent = hasPhoto
            ? '<img src="' + d.photo + '" style="width:46px;height:46px;object-fit:cover;border-radius:50%">'
            : this.avatarSVG(d.salutation);

        const whatsappBtn = d.whatsapp
            ? '<button class="crm-action-btn crm-action-btn-secondary" onclick="CRM_Berater.whatsapp(\'' + d.whatsapp + '\')"><i class="bi bi-whatsapp"></i></button>'
            : '';
        const primaryEmail = (d.emails && d.emails.find(function(e){ return e.primary; })) ? d.emails.find(function(e){ return e.primary; }).email : (d.emails && d.emails[0] ? d.emails[0].email : '');
        const statusOptsStr = I.statusOpts().map(function(o) {
            return '{value:\'' + o.value + '\',label:\'' + (o.label || '').replace(/'/g, "\\'") + '\'}';
        }).join(',');

        panel.innerHTML =
            '<div class="crm-detail-head">' +
            '<div class="crm-detail-avatar-row">' +
            '<div class="crm-avatar" style="width:46px;height:46px;cursor:pointer;position:relative;overflow:hidden;border-radius:50%" onclick="CRM_Berater.avatarClick(\'' + crm_id + '\',\'' + (hasPhoto?'1':'0') + '\')" title="' + (hasPhoto ? I.t('foto_aendern', 'Foto ändern oder löschen') : I.t('foto_hochladen', 'Foto hochladen')) + '">' +
            avatarContent +
            '<div style="position:absolute;bottom:0;left:0;right:0;background:rgba(0,0,0,.5);font-size:8px;text-align:center;color:#fff;padding:2px;opacity:0;transition:opacity .2s" class="crm-avatar-hint">' + (hasPhoto ? '✎' : '＋') + '</div>' +
            '</div>' +
            '<div style="flex:1;min-width:0">' +
            '<div style="display:flex;align-items:center;gap:4px;flex-wrap:wrap">' +
            '<span class="crm-detail-name-part" data-field="salutation" data-value="' + (d.salutation || '') + '" ondblclick="CRM_Edit.inlineEdit(this,\'' + crm_id + '\',\'salutation\')" style="cursor:pointer;border-bottom:1px dashed rgba(255,255,255,.4)">' + (d.salutation || I.t('anrede', 'Anrede')) + '</span>' +
            '<span class="crm-detail-name-part" data-field="first_name" data-value="' + (d.first_name || '') + '" ondblclick="CRM_Edit.inlineEdit(this,\'' + crm_id + '\',\'first_name\')" style="cursor:pointer;border-bottom:1px dashed rgba(255,255,255,.4);font-size:14px;font-weight:700;color:#fff">' + (d.first_name || '') + '</span>' +
            '<span class="crm-detail-name-part" data-field="last_name" data-value="' + (d.last_name || '') + '" ondblclick="CRM_Edit.inlineEdit(this,\'' + crm_id + '\',\'last_name\')" style="cursor:pointer;border-bottom:1px dashed rgba(255,255,255,.4);font-size:14px;font-weight:700;color:#fff">' + (d.last_name || '') + '</span>' +
            '<span class="crm-badge ' + badgeCls + '" style="cursor:pointer" ondblclick="CRM_Edit.inlineEdit(this,\'' + crm_id + '\',\'kontakt_status_c\',\'select\',[' + statusOptsStr + '])">' + I.status(status) + '</span>' +
            '</div>' +
            '<div class="crm-detail-sub">' + I.t(d.cstm ? d.cstm.kontakt_typ : 'berater', d.cstm ? d.cstm.kontakt_typ : 'berater') + (d.cstm && d.cstm.gulp_id ? ' · Gulp ' + d.cstm.gulp_id : '') + (d.address && d.address.city ? ' · ' + d.address.city : '') + '</div>' +
            (d.title ? '<div class="crm-detail-sub">' + d.title + '</div>' : '') +
            '</div>' +
            '</div>' +
            '<div class="crm-detail-actions">' +
            '<button class="crm-action-btn crm-action-btn-primary" onclick="CRM_Berater.call((CRM_Berater._data&&CRM_Berater._data.phones&&CRM_Berater._data.phones.length?(CRM_Berater._data.phones.find(function(p){return p.field_name===\'phone_mobile\'})||CRM_Berater._data.phones[0]).raw:\'\'))"><i class="bi bi-telephone"></i> ' + I.t('anrufen', 'Anrufen') + '</button>' +
            '<button class="crm-action-btn crm-action-btn-secondary" onclick="CRM_Berater.email(\'' + primaryEmail + '\')"><i class="bi bi-envelope"></i> ' + I.t('e_mail', 'E-Mail') + '</button>' +
            '<button class="crm-action-btn crm-action-btn-secondary" onclick="crmEmailPopup(\'' + primaryEmail + '\',\'' + (d.first_name||'') + ' ' + (d.last_name||'') + '\',\'' + crm_id + '\')" title="' + I.t('email_aus_vorlage', 'E-Mail aus Vorlage') + '"><i class="bi bi-envelope-paper"></i> ' + I.t('vorlage', 'Vorlage') + '</button>' +
            '<button class="crm-action-btn crm-action-btn-secondary" onclick="CRM_Berater.showCV(\'' + crm_id + '\')"><i class="bi bi-file-text"></i> ' + I.t('cv', 'CV') + '</button>' +
            whatsappBtn +
            '<button class="crm-action-btn" onclick="CRM_Berater.confirmDelete(\'' + crm_id + '\')" style="margin-left:auto;background:none;border:1px solid rgba(248,113,113,.5);color:#f87171;border-radius:6px;padding:4px 10px;cursor:pointer;font-size:11px" title="' + I.t('berater_loeschen', 'Berater löschen') + '"><i class="bi bi-trash"></i></button>' +
            '</div>' +
            '</div>' +

            '<div class="crm-detail-tabs">' +
            '<div class="crm-detail-tab active" onclick="CRM_Berater.switchTab(\'stammdaten\',this)">' + I.t('stammdaten', 'Stammdaten') + '</div>' +
            '<div class="crm-detail-tab" onclick="CRM_Berater.switchTab(\'profil\',this)">' + I.t('profil', 'Profil') + '</div>' +
            '<div class="crm-detail-tab" onclick="CRM_Berater.switchTab(\'notizen\',this)">' + I.t('notizen', 'Notizen') + '</div>' +
            '<div class="crm-detail-tab" onclick="CRM_Berater.switchTab(\'dokumente\',this)">' + I.t('dokumente', 'Dokumente') + '</div>' +
            '</div>' +

            '<div class="crm-detail-body" id="berater-tab-body">' +
            this.renderStammdaten(d) +
            '</div>';

        const av = panel.querySelector('.crm-avatar');
        if (av) {
            av.addEventListener('mouseenter', function() {
                const hint = this.querySelector('.crm-avatar-hint');
                if (hint) hint.style.opacity = '1';
            });
            av.addEventListener('mouseleave', function() {
                const hint = this.querySelector('.crm-avatar-hint');
                if (hint) hint.style.opacity = '0';
            });
        }
    },

    switchTab(tab, el) {
        this._activeTab = tab;
        document.querySelectorAll('.crm-detail-tab').forEach(function(t) { t.classList.remove('active'); });
        if (el) el.classList.add('active');
        const body = document.getElementById('berater-tab-body');
        if (!body) return;
        const d = this._data;
        if (tab === 'stammdaten') body.innerHTML = this.renderStammdaten(d);
        if (tab === 'profil')     body.innerHTML = this.renderProfil(d);
        if (tab === 'notizen')    body.innerHTML = this.renderNotizen(d);
        if (tab === 'dokumente')  body.innerHTML = this.renderDokumente(d);
        CRM_Edit.clearSelection();
    },

    // ── Stammdaten ────────────────────────────────────────
    renderStammdaten(d) {
        const I = window.CRM_I18N || { t: (k, f) => f || k, status: s => s || '', statusOpts: () => [], kontaktTypOpts: () => [], phoneLabel: f => f };
        const c = d.cstm || {};
        const crm_id = d.crm_id;
        const E = CRM_Edit;
        const typOpts = I.kontaktTypOpts();

        function row(icon, label, value, field, type, opts) {
            if (!value || value === 'None' || value === 'undefinded') return '';
            return '<div class="crm-info-row">' +
                E.renderCheckbox(field, value, label) +
                '<i class="bi ' + icon + '" style="color:var(--text-link);font-size:12px;width:14px;flex-shrink:0"></i>' +
                '<span style="font-size:10px;color:var(--text-muted);min-width:65px;flex-shrink:0">' + label + '</span>' +
                E.editField(crm_id, field, value, type, opts) +
                '<button data-copy="' + value.replace(/"/g, '&quot;') + '" onclick="CRM_Edit.copyText(this)" style="background:none;border:none;cursor:pointer;color:var(--text-muted);padding:0 3px;font-size:11px"><i class="bi bi-clipboard"></i></button>' +
                '<button onclick="CRM_Edit.clearCrmField(\'' + crm_id + '\',\'' + field + '\')" title="Löschen" style="background:none;border:none;cursor:pointer;color:var(--badge-error-text);padding:0 3px;font-size:11px"><i class="bi bi-trash3"></i></button>' +
                '</div>';
        }

        function roRow(icon, label, value) {
            if (!value || value === 'None') return '';
            return '<div class="crm-info-row">' +
                '<i class="bi ' + icon + '" style="color:var(--text-link);font-size:12px;width:14px;flex-shrink:0"></i>' +
                '<span style="font-size:10px;color:var(--text-muted);min-width:65px;flex-shrink:0">' + label + '</span>' +
                '<span style="font-size:10px;color:var(--text-muted);flex:1">' + value + '</span>' +
                '</div>';
        }

        // Adressen
        const adr = d.address || {};
        const adrHauptStr = [adr.street, adr.postalcode && adr.city ? adr.postalcode + ' ' + adr.city : adr.city, adr.state, adr.country].filter(Boolean).join(', ');
        const alt = d.alt_address || {};
        const adrAltStr = [alt.street, alt.postalcode && alt.city ? alt.postalcode + ' ' + alt.city : alt.city, alt.state, alt.country].filter(Boolean).join(', ');

        // E-Mails
        let emailsHtml = '';
        (d.emails || []).forEach(function(e) {
            const gesperrt = e.opt_out || e.invalid_email;
            const rowStyle = gesperrt ? 'opacity:.55' : '';
            const textStyle = gesperrt ? 'text-decoration:line-through' : '';
            const typBadge = e.typ === 'privat'
                ? '<span style="font-size:9px;padding:1px 5px;border-radius:10px;background:#f3e8ff;color:#7c3aed;flex-shrink:0">' + I.t('privat_label', 'Privat') + '</span>'
                : '<span style="font-size:9px;padding:1px 5px;border-radius:10px;background:#dcfce7;color:#15803d;flex-shrink:0">' + I.t('geschaeftl', 'Geschäftl.') + '</span>';
            const primaerBadge = e.primary
                ? '<span style="font-size:9px;padding:1px 5px;border-radius:10px;background:var(--badge-info-bg);color:var(--badge-info-text);flex-shrink:0">' + I.t('primaer', 'Primär') + '</span>'
                : '';
            const gesperrtBadge = gesperrt
                ? '<span style="font-size:9px;padding:1px 5px;border-radius:10px;background:#fee2e2;color:#dc2626;flex-shrink:0">' + I.t('gesperrt', 'Gesperrt') + '</span>'
                : '';
            const kampagneChecked = e.kampagne_ok ? 'checked' : '';
            const kampagneTitle = e.kampagne_ok ? I.t('kampagne_erlaubt', 'Kampagne erlaubt – klicken zum Deaktivieren') : I.t('kampagne_gesperrt', 'Kampagne gesperrt – klicken zum Aktivieren');
            const kampagneColor = e.kampagne_ok ? '#15803d' : '#9ca3af';
            const kampagneHtml = gesperrt ? '' :
                '<label title="' + kampagneTitle + '" style="display:flex;align-items:center;gap:2px;cursor:pointer;flex-shrink:0;margin-left:2px">' +
                '<input type="checkbox" ' + kampagneChecked + ' onchange="CRM_Berater._toggleKampagne(\''+crm_id+'\',' + '\''+e.email+'\',this.checked)" style="width:11px;height:11px;cursor:pointer;accent-color:#15803d">' +
                '<span style="font-size:9px;color:' + kampagneColor + ';white-space:nowrap">' + I.t('kamp', 'Kamp.') + '</span>' +
                '</label>';
            const gesperrtChecked = (e.opt_out || e.invalid_email) ? 'checked' : '';
            const gesperrtColor = (e.opt_out || e.invalid_email) ? '#dc2626' : '#9ca3af';
            const gesperrtHtml =
                '<label title="' + I.t('email_sperren', 'E-Mail sperren/entsperren') + '" style="display:flex;align-items:center;gap:2px;cursor:pointer;flex-shrink:0;margin-left:2px">' +
                '<input type="checkbox" ' + gesperrtChecked + ' onchange="CRM_Berater._toggleGesperrt(\''+crm_id+'\',\'' + e.email + '\',this.checked)" style="width:11px;height:11px;cursor:pointer;accent-color:#dc2626">' +
                '<span style="font-size:9px;color:' + gesperrtColor + ';white-space:nowrap">' + I.t('gesperrt', 'Gesperrt') + '</span>' +
                '</label>';
                '</label>';
            const deleteBtn = '<button onclick="CRM_Berater._deleteEmail(\'' + crm_id + '\',\'' + e.email + '\')" title="' + I.t('loeschen', 'Löschen') + '" style="background:none;border:none;cursor:pointer;color:var(--badge-error-text);padding:0 3px;font-size:11px"><i class="bi bi-trash3"></i></button>';
            const primaryBtn = !e.primary && !gesperrt
                ? '<button onclick="CRM_Berater._setPrimary(\'' + crm_id + '\',\'' + e.email + '\')" title="' + I.t('als_primaer_setzen', 'Als Primär setzen') + '" style="background:none;border:none;cursor:pointer;color:var(--text-link);padding:0 3px;font-size:11px"><i class="bi bi-star"></i></button>'
                : '';
            emailsHtml += '<div class="crm-info-row" style="' + rowStyle + '">' +
                (gesperrt ? '<span style="width:12px;flex-shrink:0"></span>' : CRM_Edit.renderCheckbox('email_' + e.email, e.email, I.t('e_mail', 'E-Mail'))) +
                '<i class="bi bi-envelope" style="color:var(--text-link);font-size:12px;width:14px;flex-shrink:0"></i>' +
                '<span style="font-size:10px;color:var(--text-link);flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;cursor:pointer;' + textStyle + '" onclick="CRM_Berater.email(\'' + e.email + '\')" title="' + I.t('email_oeffnen', 'E-Mail öffnen') + '">' + e.email + '</span>' +
                primaryBtn + primaerBadge + gesperrtBadge + kampagneHtml + gesperrtHtml +
                deleteBtn +
                '<button data-copy="' + e.email + '" onclick="CRM_Edit.copyText(this)" style="background:none;border:none;cursor:pointer;color:var(--text-muted);padding:0 3px;font-size:11px"><i class="bi bi-clipboard"></i></button>' +
                '</div>';
        });
        emailsHtml += CRM_Edit.renderEmailAdd(crm_id);

        // Web-Profile
        const webHtml = CRM_Edit.renderWebProfiles(crm_id, c.web_profiles || []);

        // IM
        const imHtml = CRM_Edit.renderIM(crm_id, d.im_contacts || []);

        // Linke Spalte
        const leftHtml =
            E.section(I.t('person', 'Person'),
                row('bi-person-badge', I.t('first_name', 'Vorname'), d.first_name, 'first_name') +
                row('bi-person-badge', I.t('last_name', 'Nachname'), d.last_name, 'last_name') +
                row('bi-briefcase', I.t('funktion', 'Funktion'), d.title, 'title') +
                row('bi-building', I.t('abteilung', 'Abteilung'), d.department, 'department') +
                row('bi-cake', I.t('geburtstag', 'Geburtstag'), d.birthdate, 'birthdate', 'date') +
                (d.account
                    ? '<div class="crm-info-row"><span style="width:12px;flex-shrink:0"></span><i class="bi bi-building" style="color:var(--text-link);font-size:12px;width:14px;flex-shrink:0"></i><span style="font-size:10px;color:var(--text-muted);min-width:65px;flex-shrink:0">' + I.t('firma', 'Firma') + '</span><span style="font-size:11px;color:var(--text-link);flex:1;cursor:pointer" onclick="window.location.href=\'/crm/kunden/?detail=' + d.account.crm_id + '\'" title="' + I.t('kunden_detail_oeffnen', 'Kunden-Detail öffnen') + '">' + d.account.name + ' <i class=\'bi bi-box-arrow-up-right\' style=\'font-size:9px;opacity:.6\'></i></span><button onclick="CRM_Berater.unlinkAccount(\'' + d.crm_id + '\')" style="background:none;border:none;cursor:pointer;color:var(--badge-error-text);font-size:11px;padding:0 3px" title="' + I.t('verknuepfung_loesen', 'Verknüpfung lösen') + '"><i class="bi bi-x-circle"></i></button></div>'
                    : '<div class="crm-info-row"><span style="width:12px;flex-shrink:0"></span><i class="bi bi-building" style="color:var(--text-link);font-size:12px;width:14px;flex-shrink:0"></i><span style="font-size:10px;color:var(--text-muted);min-width:65px;flex-shrink:0">' + I.t('firma', 'Firma') + '</span><span style="font-size:11px;color:var(--text-muted);font-style:italic;flex:1">' + I.t('nicht_verknuepft', '— nicht verknüpft') + '</span><button onclick="CRM_Berater.searchAccount(\'' + d.crm_id + '\')" style="background:none;border:1px dashed var(--border-color);border-radius:4px;cursor:pointer;color:var(--text-link);font-size:10px;padding:1px 6px"><i class="bi bi-search"></i> ' + I.t('firma', 'Firma') + '</button></div>') +
                '<div class="crm-info-row">' +
                '<span style="width:12px;flex-shrink:0"></span>' +
                '<i class="bi bi-telephone-x" style="color:var(--text-link);font-size:12px;width:14px;flex-shrink:0"></i>' +
                '<span style="font-size:10px;color:var(--text-muted);min-width:65px;flex-shrink:0">' + I.t('nicht_anrufen', 'Nicht anrufen') + '</span>' +
                '<input type="checkbox" ' + (d.do_not_call ? 'checked' : '') + ' onchange="CRM_Edit.save(\'' + crm_id + '\',{action:\'update\',do_not_call:this.checked})" style="cursor:pointer">' +
                '</div>',
            true) +

            E.section(I.t('crm_info', 'CRM Info'),
                row('bi-tag', I.t('typ', 'Typ'), c.kontakt_typ, 'kontakt_typ_c', 'select', typOpts) +
                row('bi-circle', I.t('status', 'Status'), c.kontakt_status, 'kontakt_status_c', 'select', I.statusOpts()) +
                row('bi-calendar-check', I.t('verfuegbar', 'Verfügbar'), c.verfuegbar_ab, 'verfuegbar_ab_c', 'date') +
                row('bi-currency-euro', I.t('konditionen', 'Konditionen'), c.konditionen, 'konditionen_c') +
                row('bi-star', I.t('schwerpunkt', 'Schwerpunkt'), c.skill_priority, 'skill_priority_c') +
                row('bi-hash', I.t('gulp_id', 'Gulp-ID'), c.gulp_id, 'gulp_id_c') +
                row('bi-geo-alt', I.t('einsatz_stadt', 'Einsatz Stadt'), c.einsatzort_stadt, 'einsatzort_stadt_c') +
                row('bi-map', I.t('einsatz_region', 'Einsatz Region'), c.einsatzort_region, 'einsatzort_region_c') +
                row('bi-signpost', I.t('einsatz_plz', 'Einsatz PLZ'), c.einsatzort_plz, 'einsatzort_plz_c') +
                roRow('bi-calendar-stats', I.t('gulp_upd', 'Gulp upd.'), c.gulp_updated) +
                CRM_Edit.renderCrmInfoAdd(crm_id, c, d) +
                roRow('bi-calendar-stats', I.t('xing_upd', 'Xing upd.'), c.xing_updated) +
                roRow('bi-calendar-stats', I.t('fm_upd', 'FM upd.'), c.fm_updated) +
                roRow('bi-clock', I.t('erstellt', 'Erstellt'), d.crm_date_entered) +
                roRow('bi-clock-history', I.t('geaendert', 'Geändert'), d.crm_date_modified),
            false) +

            E.section(I.t('adressen', 'Adressen'),
                '<div style="font-size:10px;font-weight:600;color:var(--text-link);margin-bottom:4px"><i class="bi bi-house"></i> ' + I.t('hauptadresse', 'Hauptadresse') + '</div>' +
                (adrHauptStr
                    ? '<div class="crm-info-row">' +
                      CRM_Edit.renderCheckbox('adr_main', adrHauptStr, I.t('adresse', 'Adresse')) +
                      '<span style="font-size:11px;flex:1;white-space:pre-line">' + adrHauptStr + '</span>' +
                      '<button onclick="CRM_Berater.editAdresse(\'' + crm_id + '\',\'primary\')" style="background:none;border:none;cursor:pointer;color:var(--text-link);font-size:11px"><i class="bi bi-pencil"></i></button>' +
                      '</div>'
                    : '<div style="font-size:10px;color:var(--text-muted);font-style:italic">' + I.t('leer', '— leer') + ' <button onclick="CRM_Berater.editAdresse(\'' + crm_id + '\',\'primary\')" style="background:none;border:none;cursor:pointer;color:var(--text-link);font-size:11px"><i class="bi bi-plus"></i> ' + I.t('hinzufuegen', 'Hinzufügen') + '</button></div>') +
                '<div style="font-size:10px;font-weight:600;color:var(--text-link);margin:8px 0 4px"><i class="bi bi-map"></i> ' + I.t('weitere_adresse', 'Weitere Adresse') + '</div>' +
                (adrAltStr
                    ? '<div class="crm-info-row">' +
                      CRM_Edit.renderCheckbox('adr_alt', adrAltStr, I.t('weitere_adresse', 'Weitere Adresse')) +
                      '<span style="font-size:11px;flex:1;white-space:pre-line">' + adrAltStr + '</span>' +
                      '<button onclick="CRM_Berater.editAdresse(\'' + crm_id + '\',\'alt\')" style="background:none;border:none;cursor:pointer;color:var(--text-link);font-size:11px"><i class="bi bi-pencil"></i></button>' +
                      '</div>'
                    : '<div style="font-size:10px;color:var(--text-muted);font-style:italic">' + I.t('leer', '— leer') + ' <button onclick="CRM_Berater.editAdresse(\'' + crm_id + '\',\'alt\')" style="background:none;border:none;cursor:pointer;color:var(--text-link);font-size:11px"><i class="bi bi-plus"></i> ' + I.t('hinzufuegen', 'Hinzufügen') + '</button></div>'),
            false);

        // Rechte Spalte
        const rightHtml =
            E.section(I.t('telefon', 'Telefon'),
                (function() {
                    const FIELD_META = {
                        phone_work:   {icon:'bi-telephone', field:'phone_work'},
                        phone_mobile: {icon:'bi-phone',     field:'phone_mobile'},
                        phone_home:   {icon:'bi-house',     field:'phone_home'},
                        phone_other:  {icon:'bi-telephone', field:'phone_other'},
                        phone_fax:    {icon:'bi-printer',   field:'phone_fax'},
                    };
                    let html = '';
                    const phones = d.phones || [];
                    phones.forEach(function(p) {
                        const meta = FIELD_META[p.field_name] || {icon:'bi-telephone', field:p.field_name};
                        const phLabel = I.phoneLabel(meta.field);
                        html += '<div class="crm-info-row">' +
                            E.renderCheckbox('ph_' + p.id, p.raw, phLabel) +
                            '<i class="bi ' + meta.icon + '" style="color:var(--text-link);font-size:12px;width:14px;flex-shrink:0"></i>' +
                            '<span style="font-size:10px;color:var(--text-muted);min-width:65px;flex-shrink:0">' + (p.label || phLabel) + '</span>' +
                            '<span style="font-size:11px;flex:1;cursor:pointer" onclick="CRM_Berater.call(\'' + p.raw + '\')">' + p.raw + '</span>' +
                            '<button data-copy="' + p.raw + '" onclick="CRM_Edit.copyText(this)" title="' + I.t('kopieren', 'Kopieren') + '" style="background:none;border:none;cursor:pointer;color:var(--text-muted);padding:0 3px;font-size:11px"><i class="bi bi-clipboard"></i></button>' +
                            '<button onclick="CRM_Berater._deletePhone(\'' + crm_id + '\',' + p.id + ')" title="' + I.t('loeschen', 'Löschen') + '" style="background:none;border:none;cursor:pointer;color:var(--badge-error-text);padding:0 3px;font-size:11px"><i class="bi bi-trash3"></i></button>' +
                            '</div>';
                    });
                    const formId = 'ph_add_form_' + crm_id;
                    html += '<div id="' + formId + '" style="display:none;gap:4px;flex-wrap:wrap;padding:4px 0;align-items:center" class="crm-info-row">' +
                        '<select id="ph_add_typ_' + crm_id + '" style="font-size:11px;padding:3px;border:1px solid var(--border-color);border-radius:5px">' +
                        '<option value="phone_mobile">' + I.t('mobil', 'Mobil') + '</option>' +
                        '<option value="phone_work">' + I.t('buero', 'Büro') + '</option>' +
                        '<option value="phone_home">' + I.t('privat_label', 'Privat') + '</option>' +
                        '<option value="phone_other">' + I.t('weiteres', 'Weiteres') + '</option>' +
                        '<option value="phone_fax">' + I.t('fax', 'Fax') + '</option>' +
                        '</select>' +
                        '<input id="ph_add_nr_' + crm_id + '" type="tel" placeholder="+49..." style="flex:1;font-size:11px;padding:3px;border:1px solid var(--border-color);border-radius:5px;min-width:100px">' +
                        '<input id="ph_add_lbl_' + crm_id + '" type="text" placeholder="' + I.t('bezeichnung_opt', 'Bezeichnung (opt.)') + '" style="flex:1;font-size:11px;padding:3px;border:1px solid var(--border-color);border-radius:5px;min-width:80px">' +
                        '<button onclick="CRM_Berater._addPhone(\'' + crm_id + '\')" style="background:var(--status-green);color:#fff;border:none;border-radius:5px;padding:3px 8px;cursor:pointer;font-size:11px"><i class="bi bi-check-lg"></i></button>' +
                        '<button onclick="document.getElementById(\'' + formId + '\').style.display=\'none\'" style="background:var(--abcona-gray-card);border:1px solid var(--border-color);border-radius:5px;padding:3px 6px;cursor:pointer;font-size:11px"><i class="bi bi-x"></i></button>' +
                        '</div>' +
                        '<button onclick="document.getElementById(\'' + formId + '\').style.display=\'flex\'" style="background:none;border:1px dashed var(--border-color);border-radius:5px;padding:2px 8px;font-size:10px;color:var(--text-link);cursor:pointer;margin-top:3px"><i class="bi bi-plus"></i> ' + I.t('telefon_hinzufuegen', 'Telefon hinzufügen') + '</button>';
                    return html;
                })(),
            true) +

            (d.assistant ? E.section(I.t('assistent', 'Assistent'),
                row('bi-person-check', I.t('name', 'Name'), d.assistant, 'assistant') +
                row('bi-telephone', I.t('telefon', 'Telefon'), d.assistant_phone, 'assistant_phone'),
            false) : '') +

            E.section(I.t('e_mail', 'E-Mail'), emailsHtml, true) +

            E.section(I.t('web_profile', 'Web-Profile'), webHtml, true) +

            E.section(I.t('messenger', 'Messenger'), imHtml, true);



        return '<div class="crm-two-col-info">' +
            '<div class="crm-col-left">' + leftHtml + '</div>' +
            '<div class="crm-col-right">' + rightHtml + '</div>' +
            '</div>';
    },

    // ── Adresse Edit Modal ────────────────────────────────
    editAdresse(crm_id, typ) {
        const I = window.CRM_I18N || { t: (k, f) => f || k };
        const d = this._data;
        const prefix = typ === 'primary' ? 'primary_address' : 'alt_address';
        const existing = typ === 'primary' ? (d.address || {}) : (d.alt_address || {});
        const body = document.getElementById('berater-tab-body');
        const old = document.getElementById('adr-edit-form');
        if (old) old.remove();
        const form = document.createElement('div');
        form.id = 'adr-edit-form';
        form.style.cssText = 'position:fixed;top:50%;left:50%;transform:translate(-50%,-50%);background:#fff;border-radius:8px;border:1px solid var(--border-color);padding:16px;z-index:1000;min-width:300px;box-shadow:0 4px 20px rgba(0,0,0,.15)';
        const title = typ === 'primary' ? I.t('hauptadresse_bearbeiten', 'Hauptadresse bearbeiten') : I.t('weitere_adresse_bearbeiten', 'Weitere Adresse bearbeiten');
        form.innerHTML = '<div style="font-size:13px;font-weight:600;color:var(--link-color);margin-bottom:12px">' + title + '</div>' +
            [
                ['street', I.t('strasse', 'Straße')],
                ['city', I.t('stadt', 'Stadt')],
                ['postalcode', I.t('plz', 'PLZ')],
                ['state', I.t('bundesland', 'Bundesland')],
                ['country', I.t('land', 'Land')],
            ].map(function(pair) {
                const f = pair[0]; const l = pair[1];
                const v = existing[f] || '';
                return '<div style="margin-bottom:6px"><label style="font-size:10px;color:var(--text-muted);display:block;margin-bottom:2px">' + l + '</label>' +
                    '<input id="adr_' + f + '" type="text" value="' + v.replace(/"/g, '&quot;') + '" style="width:100%;font-size:11px;padding:4px;border:1px solid var(--border-color);border-radius:5px"></div>';
            }).join('') +
            '<div style="display:flex;gap:6px;margin-top:8px">' +
            '<button onclick="CRM_Berater.saveAdresse(\'' + crm_id + '\',\'' + prefix + '\')" style="background:var(--status-green);color:#fff;border:none;border-radius:5px;padding:5px 14px;cursor:pointer;font-size:12px"><i class="bi bi-check-lg"></i> ' + I.t('speichern', 'Speichern') + '</button>' +
            '<button onclick="document.getElementById(\'adr-edit-form\').remove()" style="background:var(--abcona-gray-card);border:1px solid var(--border-color);border-radius:5px;padding:5px 10px;cursor:pointer;font-size:12px"><i class="bi bi-x"></i> ' + I.t('abbrechen', 'Abbrechen') + '</button>' +
            '</div>';
        document.body.appendChild(form);
    },

    async saveAdresse(crm_id, prefix) {
        const fields = ['street', 'city', 'postalcode', 'state', 'country'];
        const payload = {action: 'update'};
        fields.forEach(function(f) {
            const el = document.getElementById('adr_' + f);
            if (el) payload[prefix + '_' + f] = el.value.trim();
        });
        const res = await CRM_Edit.save(crm_id, payload);
        if (res.ok) {
            const form = document.getElementById('adr-edit-form');
            if (form) form.remove();
            CRM.loadDetail(crm_id);
        }
    },

    // ── Profil ────────────────────────────────────────────
    renderProfil(d) {
        const I = window.CRM_I18N || { t: (k, f) => f || k };
        const c = d.cstm || {};
        const crm_id = d.crm_id;
        const PROFIL_MAP = [
            {key: 'ogo_description', label: I.t('profil_ogo', 'OGO / Abcona'), field: 'ogo_description_c'},
            {key: 'gulp_profil',     label: I.t('profil_gulp', 'Gulp'),          field: 'gulp_profil_c'},
            {key: 'freelancermap',   label: I.t('profil_fm', 'Freelancermap'), field: 'freelancermap_profil_c'},
            {key: 'xing',            label: I.t('profil_xing', 'Xing'),          field: 'xing_profile_c'},
        ];

        // Nur Profile die in DB befüllt sind
        const filled = PROFIL_MAP.filter(function(p) { return c[p.key] && c[p.key].trim(); });
        const empty  = PROFIL_MAP.filter(function(p) { return !c[p.key] || !c[p.key].trim(); });

        if (!filled.length && !empty.length) {
            return '<div class="crm-list-loading">' + I.t('keine_profile', 'Keine Profile vorhanden') + '</div>';
        }

        let tabs = '';
        filled.forEach(function(p, i) {
            tabs += '<div class="crm-profil-subtab' + (i === 0 ? ' active' : '') + '" ' +
                'onclick="CRM_Berater.switchProfilTab(\'' + p.key + '\',this)" ' +
                'data-key="' + p.key + '">' + p.label + '</div>';
        });

        let addOpts = '';
        if (empty.length) {
            addOpts = empty.map(function(p) {
                return '<option value="' + p.field + '" data-label="' + p.label + '">' + p.label + '</option>';
            }).join('');
        }

        const addBtn = empty.length
            ? '<div style="margin-left:auto;display:flex;align-items:center;gap:4px">' +
              '<select id="profil-add-sel" style="font-size:11px;padding:3px;border:1px solid var(--border-color);border-radius:5px">' +
              '<option value="">' + I.t('hinzufuegen', '+ Hinzufügen') + '</option>' + addOpts + '</select>' +
              '<button onclick="CRM_Berater.addProfilTab(\'' + crm_id + '\')" style="background:var(--status-green);color:#fff;border:none;border-radius:5px;padding:3px 7px;cursor:pointer;font-size:12px"><i class="bi bi-plus"></i></button>' +
              '</div>'
            : '';

        let bodies = '';
        filled.forEach(function(p, i) {
            bodies += '<div class="crm-profil-body" data-key="' + p.key + '" id="profil-body-' + p.key + '" style="display:' + (i === 0 ? 'block' : 'none') + '">' +
                '<button class="crm-profil-edit-btn" onclick="CRM_Edit.startProfileEdit(\'' + crm_id + '\',\'' + p.field + '\',\'' + p.label.replace(/'/g, "\\'") + '\')"><i class="bi bi-pencil"></i> ' + I.t('bearbeiten', 'Bearbeiten') + '</button>' +
                '<div class="crm-profil-text" style="font-size:11px;white-space:pre-wrap;line-height:1.6;background:var(--abcona-gray-card);padding:8px;border-radius:7px;border:1px solid var(--border-color);max-height:400px;overflow-y:auto">' + c[p.key] + '</div>' +
                '</div>';
        });

        if (!filled.length) {
            bodies = '<div style="padding:20px;text-align:center;color:var(--text-muted);font-size:11px;font-style:italic">' + I.t('profil_auswaehlen', 'Profil auswählen um es hinzuzufügen') + '</div>';
        }

        return '<div style="display:flex;align-items:center;border-bottom:1px solid var(--border-color);margin-bottom:10px;flex-wrap:wrap;gap:2px">' +
            tabs + addBtn + '</div>' + bodies;
    },

    switchProfilTab(key, el) {
        document.querySelectorAll('.crm-profil-subtab').forEach(function(t) { t.classList.remove('active'); });
        document.querySelectorAll('.crm-profil-body').forEach(function(b) { b.style.display = 'none'; });
        if (el) el.classList.add('active');
        const body = document.getElementById('profil-body-' + key);
        if (body) body.style.display = 'block';
    },

    addProfilTab(crm_id) {
        const sel = document.getElementById('profil-add-sel');
        if (!sel || !sel.value) return;
        const field = sel.value;
        const label = sel.options[sel.selectedIndex].dataset.label || sel.options[sel.selectedIndex].text;
        CRM_Edit.startProfileEdit(crm_id, field, label);
    },

    // ── Notizen ───────────────────────────────────────────
    renderNotizen(d) {
        const I = window.CRM_I18N || { t: (k, f) => f || k };
        const crm_id = d.crm_id;
        const notes = (d.notes || []).map(function(n) {
            const dt = (n.created_at || '').substring(0, 10);
            return '<div class="crm-hist-item">' +
                '<span class="crm-badge crm-badge-passiv">' + (n.note_type || 'phone') + '</span>' +
                '<div style="flex:1;min-width:0">' +
                '<div style="font-size:11px">' + (n.note_text || '') + '</div>' +
                '<div style="font-size:10px;color:var(--text-muted)">' + (n.created_by || '') + ' · ' + dt + '</div>' +
                '</div></div>';
        }).join('') || '<div style="font-size:11px;color:var(--text-muted);padding:8px 0;font-style:italic">' + I.t('keine_notizen', 'Noch keine Notizen') + '</div>';

        return '<div class="crm-section"><div class="crm-section-label">' + I.t('neue_notiz', 'Neue Notiz') + '</div>' +
            '<textarea class="crm-note-area" id="note-text" placeholder="' + I.t('notiz_eingeben', 'Notiz eingeben...') + '"></textarea>' +
            '<select style="width:100%;margin-top:6px;padding:5px;border:1px solid var(--border-color);border-radius:7px;font-size:12px" id="note-type">' +
            '<option value="phone">' + I.t('telefonnotiz', 'Telefonnotiz') + '</option>' +
            '<option value="email">' + I.t('email_notiz', 'E-Mail Notiz') + '</option>' +
            '<option value="meeting">' + I.t('besprechung', 'Besprechung') + '</option>' +
            '<option value="general">' + I.t('allgemein', 'Allgemein') + '</option>' +
            '</select>' +
            '<button class="crm-save-btn" onclick="CRM_Berater.saveNote(\'' + crm_id + '\')"><i class="bi bi-save"></i> ' + I.t('notiz_speichern', 'Notiz speichern') + '</button>' +
            '</div>' +
            '<div class="crm-section"><div class="crm-section-label">' + I.t('verlauf', 'Verlauf') + '</div>' + notes + '</div>';
    },

    // ── Dokumente ─────────────────────────────────────────
    renderDokumente(d) {
        const I = window.CRM_I18N || { t: (k, f) => f || k };
        const docs = (d.documents || []).map(function(doc) {
            const titleHtml = doc.view_url
                ? '<a href="' + doc.view_url + '" target="_blank" style="color:inherit;text-decoration:none">' + (doc.title || '') + '</a>'
                : (doc.title || '');
            return '<div class="crm-hist-item">' +
                '<i class="bi bi-file-text" style="color:var(--text-link)"></i>' +
                '<div style="flex:1;min-width:0">' +
                '<div style="font-size:11px;font-weight:600">' + titleHtml + '</div>' +
                '<div style="font-size:10px;color:var(--text-muted)">' + (doc.doc_type || '') + ' \u00b7 ' + (doc.created_at || '').substring(0, 10) + '</div>' +
                '</div>' +
                (doc.file_path ? '<a href="' + doc.file_path + '" target="_blank" style="font-size:10px;color:var(--text-link)"><i class="bi bi-download"></i></a>' : '') +
                '</div>';
        }).join('') || '<div style="font-size:11px;color:var(--text-muted);padding:8px 0;font-style:italic">' + I.t('keine_dokumente', 'Keine Dokumente') + '</div>';

        return '<div class="crm-section">' + docs + '</div>';
    },



    // ── Aktionen ──────────────────────────────────────────
    call(phone) {
        const I = window.CRM_I18N || { t: (k, f) => f || k };
        if (!phone) return alert(I.t('keine_telefonnummer', 'Keine Telefonnummer hinterlegt'));
        window.location.href = 'tel:' + phone;
    },

    async _deleteEmail(crm_id, email) {
        if (!confirm('E-Mail ' + email + ' löschen?')) return;
        await CRM_Edit.save(crm_id, {action: 'email_delete', email: email});
        CRM.loadDetail(crm_id);
    },

    async _setPrimary(crm_id, email) {
        await CRM_Edit.save(crm_id, {action: 'email_set_primary', email: email});
        CRM.loadDetail(crm_id);
    },

    async _toggleGesperrt(crm_id, email, gesperrt) {
        const csrf = (document.cookie.match(/csrftoken=([^;]+)/) || [])[1] || '';
        fetch('/crm/api/contact/' + crm_id + '/update/', {
            method: 'POST',
            headers: {'Content-Type':'application/json','X-CSRFToken': csrf},
            body: JSON.stringify({action: 'email_gesperrt_toggle', email: email, gesperrt: gesperrt})
        }).then(function(r){ return r.json(); }).then(function(d){
            if (d.ok) CRM.loadDetail(crm_id);
        });
    },

    _toggleKampagne(crm_id, email, kampagne_ok) {
        const csrf = (document.cookie.match(/csrftoken=([^;]+)/) || [])[1] || '';
        fetch('/crm/api/contact/' + crm_id + '/update/', {
            method: 'POST',
            headers: {'Content-Type':'application/json','X-CSRFToken': csrf},
            body: JSON.stringify({action: 'email_kampagne_toggle', email: email, kampagne_ok: kampagne_ok})
        }).then(function(r){ return r.json(); }).then(function(d){
            if (!d.ok) { console.warn('Kampagne-Toggle fehlgeschlagen', d); }
        }).catch(function(e){ console.error('Kampagne-Toggle Fehler', e); });
    },

    async _addPhone(crm_id) {
        const typ   = document.getElementById('ph_add_typ_'   + crm_id);
        const nr    = document.getElementById('ph_add_nr_'    + crm_id);
        const lbl   = document.getElementById('ph_add_lbl_'   + crm_id);
        if (!nr || !nr.value.trim()) return;
        await CRM_Edit.save(crm_id, {
            action:     'phone_add',
            field_name: typ.value,
            nummer:     nr.value.trim(),
            label:      lbl ? lbl.value.trim() : '',
        });
        CRM.loadDetail(crm_id);
    },
    async _deletePhone(crm_id, rel_id) {
        if (!confirm('Telefonnummer l\u00f6schen?')) return;
        await CRM_Edit.save(crm_id, {action: 'phone_delete', id: rel_id});
        CRM.loadDetail(crm_id);
    },

    email(addr) {
        const I = window.CRM_I18N || { t: (k, f) => f || k };
        if (!addr) return alert(I.t('keine_email', 'Keine E-Mail hinterlegt'));
        window.location.href = 'mailto:' + addr;
    },

    whatsapp(phone) {
        const nr = (phone || '').replace(/\D/g, '');
        if (nr) window.open('https://wa.me/' + nr, '_blank');
    },

    showCV(crm_id) {
        window.open('/crm/api/berater/' + crm_id + '/cv/', '_blank');
    },

    saveNote(crm_id) {
        const I = window.CRM_I18N || { t: (k, f) => f || k };
        const text = document.getElementById('note-text') ? document.getElementById('note-text').value.trim() : '';
        const type = document.getElementById('note-type') ? document.getElementById('note-type').value : 'phone';
        if (!text) return alert(I.t('bitte_notiz_eingeben', 'Bitte Notiz eingeben'));
        fetch('/crm/api/note/save/', {
            method: 'POST',
            headers: {'Content-Type': 'application/json', 'X-CSRFToken': CRM.getCsrf(), 'X-Requested-With': 'XMLHttpRequest'},
            body: JSON.stringify({contact_crm_id: crm_id, note_text: text, note_type: type}),
        }).then(function(r) { return r.json(); })
          .then(function(data) { if (data.ok) CRM.loadDetail(crm_id); });
    },
};

window.CRM_Berater = CRM_Berater;

// ── Zuletzt angesehen ────────────────────────────────────
const CRM_RECENT_KEY = 'crm_berater_recent';

function crmSaveRecent(crm_id, full_name) {
    let list = JSON.parse(localStorage.getItem(CRM_RECENT_KEY) || '[]');
    list = list.filter(function(x) { return x.crm_id !== crm_id; });
    list.unshift({crm_id: crm_id, full_name: full_name, ts: Date.now()});
    if (list.length > 50) list = list.slice(0, 50);
    localStorage.setItem(CRM_RECENT_KEY, JSON.stringify(list));
}

function crmTimeAgo(ts) {
    const diff = Math.floor((Date.now() - ts) / 1000);
    if (diff < 60) return 'gerade eben';
    if (diff < 3600) return 'vor ' + Math.floor(diff / 60) + ' Min.';
    if (diff < 86400) return 'vor ' + Math.floor(diff / 3600) + ' Std.';
    return 'vor ' + Math.floor(diff / 86400) + ' Tagen';
}

function crmToggleView(mode) {
    const btnL = document.getElementById('btn-liste');
    const btnZ = document.getElementById('btn-zuletzt');
    const list = document.getElementById('crm-list');
    const pagination = document.getElementById('crm-pagination');
    if (mode === 'liste') {
        if (btnL) { btnL.classList.add('active'); }
        if (btnZ) { btnZ.classList.remove('active'); }
        if (pagination) pagination.style.display = '';
        if (typeof crmSearch === 'function') crmSearch();
    } else {
        if (btnZ) { btnZ.classList.add('active'); }
        if (btnL) { btnL.classList.remove('active'); }
        if (pagination) pagination.style.display = 'none';
        const n = parseInt((document.getElementById('zuletzt-n') || {value: 20}).value || 20);
        const recent = JSON.parse(localStorage.getItem(CRM_RECENT_KEY) || '[]').slice(0, n);
        if (!list) return;
        if (recent.length === 0) {
            list.innerHTML = '<div class="crm-list-loading"><i class="bi bi-clock-history"></i> Noch keine Einträge</div>';
            return;
        }
        list.innerHTML = recent.map(function(r) {
            const initials = (r.full_name || '').split(' ').map(function(w) { return w[0] || ''; }).slice(0, 2).join('').toUpperCase();
            return '<div class="crm-list-item" data-crm-id="' + r.crm_id + '">' +
                '<div class="crm-avatar">' + initials + '</div>' +
                '<div class="crm-item-info">' +
                '<div class="crm-item-name">' + r.full_name + '</div>' +
                '<div class="crm-item-sub"><i class="bi bi-clock"></i> ' + crmTimeAgo(r.ts) + '</div>' +
                '</div></div>';
        }).join('');
    }
}

// ── Foto Upload mit Crop-Popup ────────────────────────────
CRM_Berater.uploadPhoto = function(crm_id) {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = 'image/*';
    input.onchange = function() {
        const file = input.files[0];
        if (!file) return;
        const reader = new FileReader();
        reader.onload = function(e) {
            CRM_Berater._showCropPopup(crm_id, e.target.result, file.type || 'image/jpeg');
        };
        reader.readAsDataURL(file);
    };
    input.click();
};

CRM_Berater._showCropPopup = function(crm_id, dataUrl, mimeType) {
    const old = document.getElementById('crm-crop-popup');
    if (old) old.remove();

    const overlay = document.createElement('div');
    overlay.id = 'crm-crop-popup';
    overlay.style.cssText = 'position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,.7);z-index:2000;display:flex;align-items:center;justify-content:center';

    overlay.innerHTML =
        '<div style="background:#1a2744;border-radius:10px;padding:20px;width:340px;max-width:95vw;box-shadow:0 8px 40px rgba(0,0,0,.5)">' +
        '<div style="font-size:13px;font-weight:600;color:#fff;margin-bottom:12px"><i class="bi bi-crop"></i> Foto zuschneiden</div>' +
        '<div style="position:relative;width:300px;height:300px;overflow:hidden;border-radius:8px;background:#000;margin:0 auto">' +
        '<img id="crop-img" src="' + dataUrl + '" style="position:absolute;cursor:move;max-width:none" draggable="false">' +
        '<div style="position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);width:200px;height:200px;border:2px dashed rgba(255,255,255,.8);border-radius:50%;pointer-events:none;box-shadow:0 0 0 1000px rgba(0,0,0,.4)"></div>' +
        '</div>' +
        '<div style="margin-top:10px;display:flex;align-items:center;gap:8px">' +
        '<i class="bi bi-zoom-out" style="color:#fff;font-size:14px"></i>' +
        '<input type="range" id="crop-zoom" min="50" max="300" value="100" style="flex:1">' +
        '<i class="bi bi-zoom-in" style="color:#fff;font-size:14px"></i>' +
        '</div>' +
        '<div style="margin-top:4px;text-align:center;font-size:10px;color:rgba(255,255,255,.5)">Bild verschieben · Zoom anpassen</div>' +
        '<div style="display:flex;gap:8px;margin-top:14px">' +
        '<button id="crop-save" style="flex:1;background:#10b981;color:#fff;border:none;border-radius:6px;padding:8px;cursor:pointer;font-size:12px;font-weight:600"><i class="bi bi-check-lg"></i> Speichern</button>' +
        '<button id="crop-cancel" style="background:rgba(255,255,255,.15);color:#fff;border:none;border-radius:6px;padding:8px 14px;cursor:pointer;font-size:12px"><i class="bi bi-x"></i></button>' +
        '</div>' +
        '</div>';

    document.body.appendChild(overlay);

    const img = document.getElementById('crop-img');
    const zoom = document.getElementById('crop-zoom');
    const container = img.parentElement;
    const CROP_SIZE = 300;
    const CIRCLE = 200;

    let imgW = 0, imgH = 0;
    let x = 0, y = 0, scale = 1;
    let dragging = false, startX = 0, startY = 0, startImgX = 0, startImgY = 0;

    img.onload = function() {
        imgW = img.naturalWidth;
        imgH = img.naturalHeight;
        scale = Math.max(CIRCLE / imgW, CIRCLE / imgH);
        zoom.value = Math.round(scale * 100);
        clampAndApply();
    };

    function clampAndApply() {
        const w = imgW * scale;
        const h = imgH * scale;
        const minX = CROP_SIZE/2 - w + (CROP_SIZE - CIRCLE)/2;
        const maxX = CROP_SIZE/2 - (CROP_SIZE - CIRCLE)/2;
        const minY = CROP_SIZE/2 - h + (CROP_SIZE - CIRCLE)/2;
        const maxY = CROP_SIZE/2 - (CROP_SIZE - CIRCLE)/2;
        x = Math.min(maxX, Math.max(minX, x));
        y = Math.min(maxY, Math.max(minY, y));
        img.style.width  = w + 'px';
        img.style.height = h + 'px';
        img.style.left   = x + 'px';
        img.style.top    = y + 'px';
    }

    zoom.oninput = function() {
        scale = parseInt(zoom.value) / 100;
        clampAndApply();
    };

    container.addEventListener('mousedown', function(e) {
        dragging = true;
        startX = e.clientX; startY = e.clientY;
        startImgX = x; startImgY = y;
        e.preventDefault();
    });
    document.addEventListener('mousemove', function(e) {
        if (!dragging) return;
        x = startImgX + (e.clientX - startX);
        y = startImgY + (e.clientY - startY);
        clampAndApply();
    });
    document.addEventListener('mouseup', function() { dragging = false; });

    // Touch
    container.addEventListener('touchstart', function(e) {
        dragging = true;
        startX = e.touches[0].clientX; startY = e.touches[0].clientY;
        startImgX = x; startImgY = y;
        e.preventDefault();
    }, {passive:false});
    document.addEventListener('touchmove', function(e) {
        if (!dragging) return;
        x = startImgX + (e.touches[0].clientX - startX);
        y = startImgY + (e.touches[0].clientY - startY);
        clampAndApply();
    });
    document.addEventListener('touchend', function() { dragging = false; });

    document.getElementById('crop-cancel').onclick = function() { overlay.remove(); };

    document.getElementById('crop-save').onclick = function() {
        const canvas = document.createElement('canvas');
        canvas.width = 200; canvas.height = 200;
        const ctx = canvas.getContext('2d');
        ctx.beginPath();
        ctx.arc(100, 100, 100, 0, Math.PI * 2);
        ctx.clip();
        const offsetX = x - (CROP_SIZE - CIRCLE) / 2;
        const offsetY = y - (CROP_SIZE - CIRCLE) / 2;
        ctx.drawImage(img, offsetX, offsetY, imgW * scale, imgH * scale);
        canvas.toBlob(function(blob) {
            const formData = new FormData();
            formData.append('photo', blob, 'photo.jpg');
            fetch('/crm/api/contact/' + crm_id + '/photo/', {
                method: 'POST',
                headers: {'X-CSRFToken': CRM.getCsrf(), 'X-Requested-With': 'XMLHttpRequest'},
                body: formData,
            }).then(function(r) { return r.json(); })
              .then(function(data) {
                  overlay.remove();
                  if (data.ok) CRM.loadDetail(crm_id);
              });
        }, 'image/jpeg', 0.92);
    };
};


CRM_Berater.deletePhoto = async function(crm_id) {
    if (!confirm('Foto löschen und Avatar wiederherstellen?')) return;
    const res = await fetch('/crm/api/contact/' + crm_id + '/photo/', {
        method: 'DELETE',
        headers: {'X-CSRFToken': CRM.getCsrf(), 'X-Requested-With': 'XMLHttpRequest'},
    }).then(function(r) { return r.json(); });
    if (res.ok) CRM.loadDetail(crm_id);
};

CRM_Berater.avatarClick = function(crm_id, hasPhoto) {
    if (hasPhoto !== '1') {
        CRM_Berater.uploadPhoto(crm_id);
        return;
    }
    // Kleines Popup
    const old = document.getElementById('avatar-menu');
    if (old) { old.remove(); return; }
    const av = document.querySelector('.crm-avatar');
    if (!av) return;
    const rect = av.getBoundingClientRect();
    const menu = document.createElement('div');
    menu.id = 'avatar-menu';
    menu.style.cssText = 'position:fixed;top:' + (rect.bottom + 6) + 'px;left:' + rect.left + 'px;background:#1a2744;border:1px solid rgba(255,255,255,.2);border-radius:8px;padding:6px;z-index:1000;box-shadow:0 4px 20px rgba(0,0,0,.4);min-width:160px';
    menu.innerHTML =
        '<div onclick="document.getElementById(\'avatar-menu\').remove();CRM_Berater.uploadPhoto(\'' + crm_id + '\')" style="display:flex;align-items:center;gap:8px;padding:6px 10px;cursor:pointer;border-radius:5px;font-size:12px;color:#fff" onmouseover="this.style.background=\'rgba(255,255,255,.1)\'" onmouseout="this.style.background=\'\'"><i class="bi bi-camera"></i> Neues Foto hochladen</div>' +
        '<div onclick="document.getElementById(\'avatar-menu\').remove();CRM_Berater.deletePhoto(\'' + crm_id + '\')" style="display:flex;align-items:center;gap:8px;padding:6px 10px;cursor:pointer;border-radius:5px;font-size:12px;color:#ff6b6b" onmouseover="this.style.background=\'rgba(255,255,255,.1)\'" onmouseout="this.style.background=\'\'"><i class="bi bi-trash"></i> Foto löschen</div>';
    document.body.appendChild(menu);
    setTimeout(function() {
        document.addEventListener('click', function handler(e) {
            if (!menu.contains(e.target)) { menu.remove(); document.removeEventListener('click', handler); }
        });
    }, 100);
};

// Alten deleteBtn aus avatarContent entfernen — nicht mehr nötig

CRM_Berater.searchAccount = function(crm_id) {
    const old = document.getElementById('account-search-popup');
    if (old) old.remove();
    const popup = document.createElement('div');
    popup.id = 'account-search-popup';
    popup.style.cssText = 'position:fixed;top:50%;left:50%;transform:translate(-50%,-50%);background:var(--abcona-dark-card,#1e2d4a);color:#fff;border-radius:10px;border:1px solid rgba(255,255,255,.15);padding:16px;z-index:2000;min-width:340px;max-width:95vw;box-shadow:0 8px 40px rgba(0,0,0,.5)';
    popup.innerHTML =
        '<div style="font-size:13px;font-weight:600;color:#fff;margin-bottom:10px"><i class="bi bi-building"></i> Firma verknüpfen</div>' +
        '<div style="display:flex;gap:6px;margin-bottom:8px">' +
        '<input id="acc-search-input" type="text" placeholder="Firmenname suchen..." style="flex:1;font-size:11px;padding:6px;border:1px solid rgba(255,255,255,.2);border-radius:5px;background:rgba(255,255,255,.1);color:#fff">' +
        '<button onclick="CRM_Berater._doSearchAccount()" style="background:var(--abcona-blue,#163258);color:#fff;border:none;border-radius:5px;padding:6px 12px;cursor:pointer;font-size:12px"><i class="bi bi-search"></i></button>' +
        '</div>' +
        '<div id="acc-search-results" style="max-height:200px;overflow-y:auto"></div>' +
        '<div style="margin-top:10px;text-align:right">' +
        '<button onclick="document.getElementById(\'account-search-popup\').remove()" style="background:rgba(255,255,255,.1);color:#fff;border:none;border-radius:5px;padding:5px 12px;cursor:pointer;font-size:11px"><i class="bi bi-x"></i> Abbrechen</button>' +
        '</div>';
    popup.dataset.crmid = crm_id;
    document.body.appendChild(popup);
    const inp = document.getElementById('acc-search-input');
    if (inp) {
        inp.focus();
        inp.addEventListener('keydown', function(e) { if (e.key === 'Enter') CRM_Berater._doSearchAccount(); });
    }
};

CRM_Berater._doSearchAccount = function() {
    const inp = document.getElementById('acc-search-input');
    const res = document.getElementById('acc-search-results');
    const popup = document.getElementById('account-search-popup');
    if (!inp || !res || !popup) return;
    const q = inp.value.trim();
    if (!q) return;
    res.innerHTML = '<div style="font-size:11px;color:rgba(255,255,255,.5);padding:8px">Suche...</div>';
    fetch('/crm/api/kunden/?q=' + encodeURIComponent(q) + '&limit=10', {
        headers: {'X-Requested-With': 'XMLHttpRequest'}
    }).then(function(r) { return r.json(); })
      .then(function(data) {
          const items = data.results || data.kunden || [];
          if (!items.length) {
              res.innerHTML = '<div style="font-size:11px;color:rgba(255,255,255,.5);padding:8px">Keine Treffer</div>';
              return;
          }
          res.innerHTML = items.map(function(a) {
              return '<div onclick="CRM_Berater._linkAccount(\'' + popup.dataset.crmid + '\',\'' + a.crm_id + '\',\'' + (a.name || '').replace(/'/g, "\\'") + '\')" ' +
                  'style="padding:6px 8px;cursor:pointer;border-radius:5px;font-size:11px;display:flex;align-items:center;gap:8px" ' +
                  'onmouseover="this.style.background=\'rgba(255,255,255,.1)\'" onmouseout="this.style.background=\'\'">' +
                  '<i class="bi bi-building" style="color:var(--text-link)"></i>' +
                  '<span style="flex:1">' + (a.name || '') + '</span>' +
                  '<span style="font-size:10px;color:rgba(255,255,255,.4)">' + (a.city || '') + '</span>' +
                  '</div>';
          }).join('');
      });
};

CRM_Berater._linkAccount = async function(crm_id, account_crm_id, account_name) {
    const res = await fetch('/crm/api/contact/' + crm_id + '/link-account/', {
        method: 'POST',
        headers: {'Content-Type':'application/json','X-CSRFToken':CRM.getCsrf(),'X-Requested-With':'XMLHttpRequest'},
        body: JSON.stringify({account_crm_id: account_crm_id}),
    }).then(function(r) { return r.json(); });
    const popup = document.getElementById('account-search-popup');
    if (popup) popup.remove();
    if (res.ok) CRM.loadDetail(crm_id);
};

CRM_Berater.unlinkAccount = async function(crm_id) {
    if (!confirm('Verknüpfung zur Firma aufheben?')) return;
    const res = await fetch('/crm/api/contact/' + crm_id + '/link-account/', {
        method: 'DELETE',
        headers: {'X-CSRFToken':CRM.getCsrf(),'X-Requested-With':'XMLHttpRequest'},
    }).then(function(r) { return r.json(); });
    if (res.ok) CRM.loadDetail(crm_id);
};

// Auto-open contact from URL parameter ?detail=<crm_id>
document.addEventListener('DOMContentLoaded', function() {
    const params = new URLSearchParams(window.location.search);
    const detailId = params.get('detail');
    if (detailId) {
        fetch('/crm/api/berater/' + detailId + '/', {
            headers: {'X-Requested-With': 'XMLHttpRequest'}
        }).then(function(r) { return r.json(); })
          .then(function(d) {
              if (d.crm_id && typeof CRM_Berater !== 'undefined') {
                  CRM_Berater.renderDetail(d);
              }
          });
    }
});

// ── Neuer Berater ─────────────────────────────────────────
function crmNewBerater() {
    const old = document.getElementById('crm-new-berater-popup');
    if (old) old.remove();

    const popup = document.createElement('div');
    popup.id = 'crm-new-berater-popup';
    popup.style.cssText = 'position:fixed;top:50%;left:50%;transform:translate(-50%,-50%);background:#1a2744;color:#fff;border-radius:10px;border:1px solid rgba(255,255,255,.15);padding:20px;z-index:2000;min-width:320px;max-width:95vw;box-shadow:0 8px 40px rgba(0,0,0,.5)';
    popup.innerHTML =
        '<div style="font-size:13px;font-weight:600;color:#fff;margin-bottom:14px"><i class="bi bi-person-plus"></i> Neuer Berater</div>' +
        '<div style="margin-bottom:8px">' +
        '<label style="font-size:10px;color:rgba(255,255,255,.6);display:block;margin-bottom:3px">Anrede</label>' +
        '<select id="nb-sal" style="width:100%;font-size:12px;padding:5px;border:1px solid rgba(255,255,255,.2);border-radius:5px;background:rgba(255,255,255,.1);color:#fff">' +
        '<option value="Hr." style="background:#1e2d4a;color:#fff">Hr.</option><option value="Fr." style="background:#1e2d4a;color:#fff">Fr.</option><option value="" style="background:#1e2d4a;color:#fff">— keine Angabe —</option>' +
        '</select></div>' +
        '<div style="margin-bottom:8px">' +
        '<label style="font-size:10px;color:rgba(255,255,255,.6);display:block;margin-bottom:3px">Vorname</label>' +
        '<input id="nb-first" type="text" placeholder="Vorname" style="width:100%;font-size:12px;padding:5px;border:1px solid rgba(255,255,255,.2);border-radius:5px;background:rgba(255,255,255,.1);color:#fff;box-sizing:border-box">' +
        '</div>' +
        '<div style="margin-bottom:8px">' +
        '<label style="font-size:10px;color:rgba(255,255,255,.6);display:block;margin-bottom:3px">Nachname <span style="color:#f87171">*</span></label>' +
        '<input id="nb-last" type="text" placeholder="Nachname (Pflicht)" style="width:100%;font-size:12px;padding:5px;border:1px solid rgba(255,255,255,.2);border-radius:5px;background:rgba(255,255,255,.1);color:#fff;box-sizing:border-box">' +
        '</div>' +
        '<div id="nb-error" style="color:#f87171;font-size:11px;margin-bottom:8px;display:none"></div>' +
        '<div style="display:flex;gap:8px;margin-top:14px">' +
        '<button id="nb-save" style="flex:1;background:#10b981;color:#fff;border:none;border-radius:6px;padding:8px;cursor:pointer;font-size:12px;font-weight:600"><i class="bi bi-check-lg"></i> Anlegen</button>' +
        '<button onclick="document.getElementById(\'crm-new-berater-popup\').remove()" style="background:rgba(255,255,255,.1);color:#fff;border:none;border-radius:6px;padding:8px 14px;cursor:pointer;font-size:12px"><i class="bi bi-x"></i></button>' +
        '</div>';
    document.body.appendChild(popup);

    document.getElementById('nb-last').focus();

    document.getElementById('nb-save').addEventListener('click', async function() {
        const last  = document.getElementById('nb-last').value.trim();
        const first = document.getElementById('nb-first').value.trim();
        const sal   = document.getElementById('nb-sal').value;
        const errEl = document.getElementById('nb-error');
        if (!last) {
            errEl.textContent = 'Nachname ist Pflichtfeld.';
            errEl.style.display = 'block';
            return;
        }
        errEl.style.display = 'none';
        this.disabled = true;
        try {
            const resp = await fetch('/crm/api/berater/new/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': CRM.getCsrf(),
                    'X-Requested-With': 'XMLHttpRequest',
                },
                body: JSON.stringify({salutation: sal, first_name: first, last_name: last}),
            });
            const data = await resp.json();
            if (data.ok) {
                document.getElementById('crm-new-berater-popup').remove();
                // Liste neu laden
                if (typeof crmSearch === 'function') crmSearch();
                // Detail direkt öffnen
                CRM.loadDetail(data.crm_id);
            } else {
                errEl.textContent = data.error || 'Fehler beim Anlegen.';
                errEl.style.display = 'block';
                this.disabled = false;
            }
        } catch(e) {
            errEl.textContent = 'Netzwerkfehler.';
            errEl.style.display = 'block';
            this.disabled = false;
        }
    });

    // Enter im Nachnamen-Feld
    document.getElementById('nb-last').addEventListener('keydown', function(e) {
        if (e.key === 'Enter') document.getElementById('nb-save').click();
    });

    // Klick außerhalb schließt
    setTimeout(function() {
        document.addEventListener('click', function handler(e) {
            const p = document.getElementById('crm-new-berater-popup');
            if (p && !p.contains(e.target)) {
                p.remove();
                document.removeEventListener('click', handler);
            }
        });
    }, 200);
}

// ── Berater löschen ───────────────────────────────────────
CRM_Berater.confirmDelete = function(crm_id) {
    const d = CRM_Berater._data;
    const name = d ? (d.salutation + ' ' + d.first_name + ' ' + d.last_name).trim() : crm_id;

    const old = document.getElementById('crm-delete-popup');
    if (old) old.remove();

    const popup = document.createElement('div');
    popup.id = 'crm-delete-popup';
    popup.style.cssText = 'position:fixed;top:50%;left:50%;transform:translate(-50%,-50%);background:#1a2744;color:#fff;border-radius:10px;border:1px solid rgba(248,113,113,.4);padding:22px;z-index:2000;min-width:300px;max-width:95vw;box-shadow:0 8px 40px rgba(0,0,0,.6)';
    popup.innerHTML =
        '<div style="font-size:14px;font-weight:600;color:#f87171;margin-bottom:10px"><i class="bi bi-exclamation-triangle"></i> Berater löschen</div>' +
        '<div style="font-size:12px;color:rgba(255,255,255,.8);margin-bottom:16px;line-height:1.6">' +
        'Soll <strong>' + name + '</strong> wirklich gelöscht werden?<br>' +
        '<span style="font-size:11px;color:rgba(255,255,255,.5)">Alle zugehörigen Daten (Notizen, Dokumente, Verknüpfungen) werden ebenfalls entfernt.</span>' +
        '</div>' +
        '<div style="display:flex;gap:8px">' +
        '<button id="crm-delete-confirm" style="flex:1;background:#dc2626;color:#fff;border:none;border-radius:6px;padding:8px;cursor:pointer;font-size:12px;font-weight:600"><i class="bi bi-trash"></i> Ja, löschen</button>' +
        '<button onclick="document.getElementById(\'crm-delete-popup\').remove()" style="background:rgba(255,255,255,.1);color:#fff;border:none;border-radius:6px;padding:8px 14px;cursor:pointer;font-size:12px">Abbrechen</button>' +
        '</div>';
    document.body.appendChild(popup);

    document.getElementById('crm-delete-confirm').addEventListener('click', async function() {
        this.disabled = true;
        this.innerHTML = '<i class="bi bi-hourglass"></i> Löschen...';
        try {
            const resp = await fetch('/crm/api/berater/' + crm_id + '/delete/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': CRM.getCsrf(),
                    'X-Requested-With': 'XMLHttpRequest',
                },
                body: JSON.stringify({confirm: true}),
            });
            const data = await resp.json();
            if (data.ok) {
                document.getElementById('crm-delete-popup').remove();
                // Detail-Panel leeren
                const panel = document.getElementById('crm-detail-panel');
                if (panel) panel.innerHTML = '<div style="padding:40px;text-align:center;color:var(--text-muted)"><i class="bi bi-person" style="font-size:32px"></i><div style="margin-top:8px;font-size:12px">Berater ausgewählt</div></div>';
                // Liste neu laden
                if (typeof crmSearch === 'function') crmSearch();
            } else {
                alert('Fehler: ' + (data.error || 'Unbekannter Fehler'));
                this.disabled = false;
            }
        } catch(e) {
            alert('Netzwerkfehler');
            this.disabled = false;
        }
    });
};


// ── E-Mail Compose — gemeinsame Funktion ─────────────────
function crmEmailPopup(toEmail, contactName, crmId) {
    const url = '/crm/email/compose/?to=' + encodeURIComponent(toEmail || '') +
                '&name=' + encodeURIComponent(contactName || '') +
                '&crm_id=' + encodeURIComponent(crmId || '');
    window.open(url, 'crm_email_compose',
        'width=1200,height=800,resizable=yes,scrollbars=yes');
}

function _crmEmailComposePopup(opts) {
    const old = document.getElementById('crm-email-popup');
    if (old) old.remove();

    fetch('/crm/api/email/templates/', {
        headers: {'X-Requested-With': 'XMLHttpRequest'}
    }).then(function(r) { return r.json(); }).then(function(data) {

        const templates  = data.templates  || [];
        const signatures = data.signatures || [];
        const variables  = data.variables  || [];
        const modules    = data.modules    || [];
        const senders    = data.senders    || [];

        const tplOptions = templates.map(function(t) {
            return '<option value="' + t.identifier + '">' + t.name + '</option>';
        }).join('');

        const sigOptions = '<option value="">— Keine Signatur —</option>' +
            signatures.map(function(s) {
                return '<option value="' + s.id + '"' + (s.is_default ? ' selected' : '') + ' style="background:#163258;color:#fff">' + s.name + '</option>';
            }).join('');
        const senderOptions = '<option value="">— User (eingeloggt) —</option>' +
            senders.map(function(s) {
                return '<option value="' + s.id + '"' + (s.is_default ? ' selected' : '') + ' style="background:#163258;color:#fff">' +
                    s.display_name + ' &lt;' + s.email + '&gt;</option>';
            }).join('');

        // Empfänger-Bereich je nach Modus
        let recipientHtml = '';
        if (opts.mode === 'kunden' && opts.recipients && opts.recipients.length) {
            const recipOpts = opts.recipients.map(function(r) {
                return '<option value="' + r.email + '" data-name="' + r.name + '" style="background:#163258;color:#fff">' +
                    r.name + ' &lt;' + r.email + '&gt;</option>';
            }).join('') + '<option value="__manual__" style="background:#163258;color:#fff">— Manuell eingeben —</option>';
            recipientHtml =
                '<div class="cem-row">' +
                '<label class="cem-lbl">Empfänger</label>' +
                '<select id="em-recipient-sel" class="cem-select">' + recipOpts + '</select>' +
                '</div>' +
                '<div id="em-manual-row" class="cem-row" style="display:none">' +
                '<label class="cem-lbl">E-Mail</label>' +
                '<input id="em-to-manual" type="email" class="cem-input" placeholder="name@firma.de">' +
                '</div>';
        } else {
            recipientHtml =
                '<div class="cem-row">' +
                '<label class="cem-lbl">An</label>' +
                '<input id="em-to" type="email" class="cem-input" value="' + (opts.toEmail || '') + '">' +
                '</div>';
        }

        // Variablen-Chips
        const varChips = variables.map(function(v) {
            return '<span class="cem-chip" data-insert="{' + v.name + '}" title="' + v.label + '">{' + v.name + '}</span>';
        }).join('');

        // Modul-Chips gruppiert
        const modTypes = {};
        modules.forEach(function(m) {
            if (!modTypes[m.module_type]) modTypes[m.module_type] = [];
            modTypes[m.module_type].push(m);
        });
        let modHtml = '';
        Object.keys(modTypes).forEach(function(type) {
            modHtml += '<div style="font-size:9px;color:rgba(255,255,255,.4);margin:6px 0 3px;text-transform:uppercase">' + type + '</div>';
            modHtml += modTypes[type].map(function(m) {
                return '<span class="cem-chip cem-chip-mod" data-insert="' + m.syntax + '" title="' + m.syntax + '">' + m.name + '</span>';
            }).join('');
        });

        const title = opts.mode === 'kunden'
            ? 'E-Mail — ' + (opts.firmaName || '')
            : 'E-Mail aus Vorlage';

        const popup = document.createElement('div');
        popup.id = 'crm-email-popup';
        popup.innerHTML =
            '<div class="cem-overlay"></div>' +
            '<div class="cem-dialog">' +
            '<div class="cem-header"><i class="bi bi-envelope-paper"></i> ' + title +
            '<button class="cem-close" onclick="document.getElementById(\'crm-email-popup\').remove()"><i class="bi bi-x-lg"></i></button></div>' +

            '<div class="cem-body">' +
            '<div class="cem-left">' +

            recipientHtml +

            '<div class="cem-row">' +
            '<label class="cem-lbl">Vorlage</label>' +
            '<select id="em-tpl" class="cem-select">' + tplOptions + '</select>' +
            '</div>' +

            '<div class="cem-row">' +
            '<label class="cem-lbl">Signatur</label>' +
            '<select id="em-sig" class="cem-select">' + sigOptions + '</select>' +
            '</div>' +

            '<div class="cem-row">' +
            '<label class="cem-lbl">Absender</label>' +
            '<select id="em-sender" class="cem-select">' + senderOptions + '</select>' +
            '</div>' +

            '<div class="cem-row">' +
            '<label class="cem-lbl">Betreff</label>' +
            '<input id="em-subject" type="text" class="cem-input" placeholder="Betreff" ' +
            'onfocus="window._cemActiveField=\'em-subject\'">' +
            '</div>' +

            '<div class="cem-row" style="flex:1;display:flex;flex-direction:column">' +
            '<label class="cem-lbl">Nachricht</label>' +
            '<textarea id="em-body" class="cem-textarea" placeholder="Nachricht..." ' +
            'onfocus="window._cemActiveField=\'em-body\'"></textarea>' +
            '</div>' +

            '<div id="em-error"   class="cem-msg cem-msg-err"  style="display:none"></div>' +
            '<div id="em-success" class="cem-msg cem-msg-ok"   style="display:none"><i class="bi bi-check-circle"></i> E-Mail gesendet!</div>' +

            '<div class="cem-footer">' +
            '<button id="em-send" class="cem-btn-send"><i class="bi bi-send"></i> Senden</button>' +
            '</div>' +

            '</div>' + // cem-left

            '<div class="cem-right">' +

            '<div class="cem-panel">' +
            '<div class="cem-panel-hdr" onclick="this.parentElement.classList.toggle(\'open\')">' +
            '<i class="bi bi-braces"></i> Variablen <span class="cem-badge">' + variables.length + '</span>' +
            '<i class="bi bi-chevron-down cem-chevron"></i></div>' +
            '<div class="cem-panel-body">' +
            '<div style="font-size:10px;color:rgba(255,255,255,.45);margin-bottom:6px">Klicken zum Einfügen</div>' +
            varChips +
            '</div></div>' +

            '<div class="cem-panel open">' +
            '<div class="cem-panel-hdr" onclick="this.parentElement.classList.toggle(\'open\')">' +
            '<i class="bi bi-puzzle"></i> Module <span class="cem-badge">' + modules.length + '</span>' +
            '<i class="bi bi-chevron-down cem-chevron"></i></div>' +
            '<div class="cem-panel-body">' + modHtml + '</div>' +
            '</div>' +

            '</div>' + // cem-right
            '</div>' + // cem-body
            '</div>'; // cem-dialog

        document.body.appendChild(popup);
        window._cemActiveField = 'em-body';

        // Klick auf Overlay schließt
        popup.querySelector('.cem-overlay').addEventListener('click', function() {
            popup.remove();
        });

        // Empfänger Manuell-Toggle
        const recSel = document.getElementById('em-recipient-sel');
        if (recSel) {
            recSel.addEventListener('change', function() {
                const mRow = document.getElementById('em-manual-row');
                if (mRow) mRow.style.display = this.value === '__manual__' ? 'flex' : 'none';
            });
        }

        // Signatur-Chips → Dropdown setzen + HTML einfügen
        popup.querySelectorAll('.cem-chip-sig').forEach(function(chip) {
            chip.addEventListener('click', function() {
                const sigId = this.dataset.sigId;
                // Signatur-Dropdown umschalten
                const sigSel = document.getElementById('em-sig');
                if (sigSel) sigSel.value = sigId;
                // Signatur-HTML in Nachricht einfügen
                const sig = signatures.find(function(s) { return String(s.id) === String(sigId); });
                if (sig && sig.html_body) {
                    const body = document.getElementById('em-body');
                    if (body) {
                        const token = '\n\n-- \n' + sig.name;
                        const pos = body.value.length;
                        body.value = body.value.trimEnd() + token;
                        body.focus();
                    }
                }
                this.style.background = 'rgba(167,139,250,.4)';
                const self = this;
                setTimeout(function() { self.style.background = ''; }, 400);
            });
        });

        // Variablen + Modul Chips
        popup.querySelectorAll('.cem-chip:not(.cem-chip-sig)').forEach(function(chip) {
            chip.addEventListener('click', function() {
                const token    = this.dataset.insert;
                const fieldId  = window._cemActiveField || 'em-body';
                const field    = document.getElementById(fieldId);
                if (!field) return;
                const start = field.selectionStart || 0;
                const end   = field.selectionEnd   || 0;
                field.value = field.value.slice(0, start) + token + field.value.slice(end);
                field.selectionStart = field.selectionEnd = start + token.length;
                field.focus();
                // Kurzes Highlight
                this.style.background = 'rgba(99,179,237,.4)';
                const self = this;
                setTimeout(function() { self.style.background = ''; }, 400);
            });
        });

        // Vorlage wechseln → Betreff vorbelegen wenn nicht manuell
        document.getElementById('em-tpl').addEventListener('change', function() {
            const sel = templates.find(function(t) { return t.identifier === this.value; }, this);
            const sub = document.getElementById('em-subject');
            if (sel && sel.subject && sel.subject !== '{subject}' && sub && !sub.value) {
                sub.value = sel.subject;
            }
        });

        // Senden
        document.getElementById('em-send').addEventListener('click', async function() {
            const errEl = document.getElementById('em-error');
            const okEl  = document.getElementById('em-success');
            errEl.style.display = 'none';
            okEl.style.display  = 'none';

            // Empfänger ermitteln
            let to = '', contactName = opts.contactName || '';
            if (opts.mode === 'kunden') {
                const sel = document.getElementById('em-recipient-sel');
                if (sel) {
                    if (sel.value === '__manual__') {
                        to = (document.getElementById('em-to-manual') || {}).value.trim();
                    } else {
                        to = sel.value;
                        contactName = sel.options[sel.selectedIndex].dataset.name || '';
                    }
                }
            } else {
                to = (document.getElementById('em-to') || {}).value.trim();
            }

            const tpl     = document.getElementById('em-tpl').value;
            const sig     = document.getElementById('em-sig').value;
            const subject = document.getElementById('em-subject').value.trim();
            const body    = document.getElementById('em-body').value.trim();

            if (!to)      { errEl.textContent = 'Empfänger fehlt.';  errEl.style.display='block'; return; }
            if (!subject) { errEl.textContent = 'Betreff fehlt.';    errEl.style.display='block'; return; }
            if (!body)    { errEl.textContent = 'Nachricht fehlt.';  errEl.style.display='block'; return; }

            this.disabled = true;
            this.innerHTML = '<i class="bi bi-hourglass"></i> Senden...';

            try {
                const resp = await fetch('/crm/api/email/send/', {
                    method: 'POST',
                    headers: {
                        'Content-Type':  'application/json',
                        'X-CSRFToken':   CRM.getCsrf(),
                        'X-Requested-With': 'XMLHttpRequest',
                    },
                    body: JSON.stringify({
                        template_identifier: tpl,
                        to_email:     to,
                        subject:      subject,
                        body:         body,
                        contact_name: contactName,
                        crm_id:       opts.crmId || '',
                        signature_id: sig || '',
                        sender_id:    document.getElementById('em-sender') ? document.getElementById('em-sender').value : '',
                    }),
                });
                const result = await resp.json();
                if (result.success) {
                    okEl.style.display = 'block';
                    this.innerHTML = '<i class="bi bi-check-lg"></i> Gesendet';
                    setTimeout(function() {
                        const p = document.getElementById('crm-email-popup');
                        if (p) p.remove();
                    }, 1500);
                } else {
                    errEl.textContent = result.error || 'Fehler beim Senden.';
                    errEl.style.display = 'block';
                    this.disabled = false;
                    this.innerHTML = '<i class="bi bi-send"></i> Senden';
                }
            } catch(e) {
                errEl.textContent = 'Netzwerkfehler.';
                errEl.style.display = 'block';
                this.disabled = false;
                this.innerHTML = '<i class="bi bi-send"></i> Senden';
            }
        });

        document.getElementById('em-subject').focus();
    });
}