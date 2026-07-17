// mod-cv_editor.js — CV Editor Portal Modul
// Strikte Trennung: kein hardcoded Text, alles über t()

const cveEditor = (() => {

    // ── State ─────────────────────────────────────────────────
    let _aid          = null;
    let _consultantId = null;
    let _dir          = null;
    let _isDirty      = false;
    let _currentName  = '';
    let _allData      = [];

    // ── Helpers ───────────────────────────────────────────────
    const $ = id => document.getElementById(id);
    const csrf = () => $('cve-csrf')?.value || '';

    function t(key) {
        const keys = key.split('.');
        let val = window.i18nData || {};
        for (const k of keys) {
            if (val && typeof val === 'object') val = val[k];
            else return key;
        }
        return typeof val === 'string' ? val : key;
    }

    function fmtDate(iso) {
        if (!iso) return '–';
        const d = new Date(iso);
        return d.toLocaleDateString() + ' ' + d.toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'});
    }

    function esc(s) {
        return (s || '').replace(/[&<>]/g, m => ({'&':'&amp;','<':'&lt;','>':'&gt;'}[m]));
    }

    // ── Dirty-Check ───────────────────────────────────────────
    function dirty() { _isDirty = true; }

    function tryOpenList() {
        // Popup immer zeigen wenn Editor offen — egal ob dirty oder nicht
        if ($('toggle-editor').style.display !== 'none') {
            $('cve-dirty-name').textContent = _currentName;
            $('cve-dirty-overlay').style.display = 'flex';
            return;
        }
        doOpenList();
    }

    function doOpenList() {
        $('cve-dirty-overlay').style.display = 'none';
        $('toggle-editor').style.display = 'none';
        _setToggle('list', true);
        _isDirty = false;
    }

    function popupSave() {
        saveSection('personal');
        _isDirty = false;
        doOpenList();
    }

    function popupDiscard() { _isDirty = false; doOpenList(); }
    function popupCancel()  { $('cve-dirty-overlay').style.display = 'none'; }

    // ── Haupt-Toggle Helpers ──────────────────────────────────
    function _setToggle(id, open) {
        const body = $('body-' + id);
        const hdr  = $('hdr-' + id);
        if (!body) return;
        body.classList.toggle('open', open);
        hdr?.classList.toggle('open', open);
    }

    function toggleEditorMain() {
        const body = $('body-editor');
        const open = body.classList.contains('open');
        _setToggle('editor', !open);
    }

    // ── Sektion Toggle ────────────────────────────────────────
    // Logik:
    //   Klick Header (zu)     → aufklappen + Vorschau zeigen
    //   Klick Header (auf)    → zuklappen
    //   Klick Bearbeiten      → Vorschau→Formular (kein toggle)
    //   Klick Vorschau-Btn    → Formular→Vorschau (kein toggle)
    //   Klick Speichern       → kein toggle

    function toggleSec(headerEl, event) {
        if (event && (
            event.target.closest('.cve-edit-btn') ||
            event.target.closest('.cve-save-btn') ||
            event.target.closest('.cve-sec-right')
        )) return;

        const sec = headerEl.parentElement; // .toggle-section
        if (!sec) return;

        if (sec.classList.contains('cve-open')) {
            // Zuklappen
            sec.classList.remove('cve-open', 'cve-view-mode', 'cve-edit-mode');
            headerEl.classList.remove('open');
        } else {
            // Aufklappen → Vorschau
            sec.classList.add('cve-open', 'cve-view-mode');
            sec.classList.remove('cve-edit-mode');
            headerEl.classList.add('open');
            _renderSectionView(sec);
        }
    }

    // Sektion in Edit-Mode schalten
    function _secToEdit(sec) {
        sec.classList.remove('cve-view-mode');
        sec.classList.add('cve-edit-mode');
        const btn = sec.querySelector('.cve-edit-btn');
        if (btn) btn.innerHTML = `<i class="bi bi-eye"></i> ${t('cv_editor.btn_preview')}`;
    }

    // Sektion in View-Mode schalten
    function _secToView(sec) {
        sec.classList.add('cve-view-mode');
        sec.classList.remove('cve-edit-mode');
        const btn = sec.querySelector('.cve-edit-btn');
        if (btn) btn.innerHTML = `<i class="bi bi-pencil"></i> ${t('cv_editor.btn_edit')}`;
        _renderSectionView(sec);
    }

    // View-Inhalt aufbauen
    function _renderSectionView(sec) {
        const viewEl = sec.querySelector(':scope > .cve-section-view');
        if (!viewEl) return;
        const secId  = sec.dataset.secId;
        if (!secId) return;

        const inner = viewEl.querySelector('.cve-view-inner');
        if (inner) inner.remove();

        const div = document.createElement('div');
        div.className = 'cve-view-inner';
        div.innerHTML = _buildView(secId);
        viewEl.appendChild(div);
    }

    function _buildView(secId) {
        switch(secId) {
            case 'sec-personal':    return _buildPersonalView();
            case 'sec-branchen':    return _buildTagsView('branchen-tags',    t('cv_editor.empty_branchen'));
            case 'sec-fachbereiche':return _buildTagsView('fachbereiche-tags',t('cv_editor.empty_fachbereiche'));
            case 'sec-schulungen':  return _buildListView('schulungen-tags',  t('cv_editor.empty_schulungen'));
            case 'sec-zertifikate': return _buildListView('zertifikate-tags', t('cv_editor.empty_zertifikate'));
            case 'sec-produkte':    return _buildTagsView('produkte-tags',    t('cv_editor.empty_produkte'));
            case 'sec-skills':      return _buildSkillsView();
            default: return '';
        }
    }

    // View/Edit Buttons zu Sektionen hinzufügen
    function _initSectionViewModes() {
        const secIds = [
            'sec-personal','sec-branchen','sec-fachbereiche',
            'sec-schulungen','sec-zertifikate','sec-produkte','sec-skills'
        ];

        secIds.forEach(secId => {
            const secContent = $(secId);
            if (!secContent) return;
            const sec    = secContent.parentElement; // .toggle-section
            const header = sec?.querySelector(':scope > .section-header');
            if (!sec || !header) return;

            // secId auf toggle-section merken
            sec.dataset.secId = secId;

            // Alten View-Container entfernen
            sec.querySelector(':scope > .cve-section-view')?.remove();

            // View-Container nach section-header einfügen
            const viewEl = document.createElement('div');
            viewEl.className = 'cve-section-view';

            // Bearbeiten/Vorschau Button
            const editBtn = document.createElement('button');
            editBtn.className = 'cve-edit-btn';
            editBtn.innerHTML = `<i class="bi bi-pencil"></i> ${t('cv_editor.btn_edit')}`;
            editBtn.addEventListener('click', e => {
                e.stopPropagation();
                e.preventDefault();
                if (sec.classList.contains('cve-view-mode')) {
                    _secToEdit(sec);
                } else {
                    _secToView(sec);
                }
            });

            // Bubbling stoppen damit Header-Toggle nicht feuert
            viewEl.addEventListener('click', e => e.stopPropagation());

            viewEl.appendChild(editBtn);
            header.after(viewEl);
        });
    }

    // ── Consultant Liste ──────────────────────────────────────
    async function loadConsultants() {
        const tbody = $('cve-tbody');
        if (!tbody) return;
        tbody.innerHTML = `<tr><td colspan="8" class="cve-loading"><i class="bi bi-hourglass-split"></i></td></tr>`;
        try {
            const r = await fetch('/cv-extractor/api/uploads/?limit=500');
            const d = await r.json();
            if (d.success) {
                _allData = d.uploads || [];
                const count = $('cve-count');
                if (count) count.textContent = _allData.length;
                filterTable('');
            }
        } catch(e) {
            tbody.innerHTML = `<tr><td colspan="8" class="cve-loading">${t('cv_editor.err_load')}</td></tr>`;
        }
    }

    function filterTable(term) {
        const status = $('cve-status-f')?.value || '';
        const sort   = $('cve-sort')?.value || 'newest';
        const q      = term.toLowerCase();

        let rows = _allData.filter(u => {
            const matchQ = !q ||
                (u.last_name  || '').toLowerCase().includes(q) ||
                (u.first_name || '').toLowerCase().includes(q) ||
                (u.aid        || '').toLowerCase().includes(q);
            const matchS = !status || u.status === status;
            return matchQ && matchS;
        });

        rows.sort((a, b) => {
            if (sort === 'newest') return new Date(b.created_at) - new Date(a.created_at);
            if (sort === 'oldest') return new Date(a.created_at) - new Date(b.created_at);
            if (sort === 'ln_asc') return (a.last_name||'').localeCompare(b.last_name||'');
            if (sort === 'ln_desc') return (b.last_name||'').localeCompare(a.last_name||'');
            return 0;
        });

        renderTable(rows);
    }

    function renderTable(rows) {
        const tbody = $('cve-tbody');
        if (!tbody) return;

        const sm = {
            completed:     { dot: 'cve-dot-ok',   pill: 'cve-pill-ok',   label: t('cv_editor.status_done') },
            profile_ready: { dot: 'cve-dot-ok',   pill: 'cve-pill-ok',   label: t('cv_editor.status_done') },
            processing:    { dot: 'cve-dot-proc',  pill: 'cve-pill-proc', label: t('cv_editor.status_proc') },
            failed:        { dot: 'cve-dot-fail',  pill: 'cve-pill-fail', label: t('cv_editor.status_fail') },
            uploaded:      { dot: 'cve-dot-wait',   pill: 'cve-pill-wait',    label: t('cv_editor.status_wait') },
            archived:      { dot: 'cve-dot-archive', pill: 'cve-pill-archive', label: t('cv_editor.status_archived') },
        };

        if (!rows.length) {
            tbody.innerHTML = `<tr><td colspan="8" class="cve-loading">${t('cv_editor.no_entries')}</td></tr>`;
            return;
        }

        tbody.innerHTML = rows.map(u => {
            const s = sm[u.status] || sm.uploaded;
            const isArchived = u.status === 'archived';
            const canEdit = !!u.aid && !isArchived;
            const editBtn = canEdit
                ? `<button style="font-size:11px;padding:3px 9px;"
                    onclick="cveEditor.openEditor('${esc(u.aid)}','${esc(u.first_name)}','${esc(u.last_name)}','${esc(u.consultant_dir||'')}')">
                    <i class="bi bi-pencil-square"></i> ${t('cv_editor.btn_editor')}
                   </button>`
                : isArchived
                ? `<button style="font-size:11px;padding:4px 10px;border:1.5px solid #163258;color:#163258;background:white;border-radius:6px;cursor:pointer;display:inline-flex;align-items:center;gap:5px;font-weight:500;transition:all .15s;"
                    onmouseover="this.style.background='#163258';this.style.color='white'"
                    onmouseout="this.style.background='white';this.style.color='#163258'"
                    onclick="cveEditor.reactivateConsultant('${esc(u.aid)}','${esc(u.first_name)}','${esc(u.last_name)}')">
                    <i class="bi bi-arrow-counterclockwise"></i> ${t('cv_editor.btn_reactivate')}
                   </button>`
                : `<button style="font-size:11px;padding:3px 9px;" disabled>
                    <i class="bi bi-pencil-square"></i> ${t('cv_editor.btn_editor')}
                   </button>`;
            return `<tr>
                <td><strong>${esc(u.last_name||'–')}</strong></td>
                <td>${esc(u.first_name||'–')}</td>
                <td style="font-family:monospace;font-size:11px;color:var(--color-text-info,#163258)">${esc(u.aid||'–')}</td>
                <td style="font-size:11px">${esc(u.version||'–')}</td>
                <td><span class="cve-dot ${s.dot}"></span><span class="cve-pill ${s.pill}">${s.label}</span></td>
                <td style="font-size:11px;color:#6c757d">${fmtDate(u.updated_at||u.created_at)}</td>
                <td style="text-align:center">
                    ${u.aid ? `<span class="cve-valid-circle ${u.pipeline_step==='validated'?'cve-valid-ok':'cve-valid-fail'}">${u.pipeline_step==='validated'?'✓':'✗'}</span>` : '–'}
                </td>
                <td>${editBtn}</td>
            </tr>`;
        }).join('');
    }

    // ── Editor öffnen ─────────────────────────────────────────
    async function openEditor(aid, fn, ln, dir) {
        _aid         = aid;
        _dir         = dir;
        _currentName = `${ln}, ${fn}`;
        _isDirty     = false;

        $('cve-ed-label').textContent = `${ln}, ${fn} — ${aid}`;

        _setToggle('list', false);
        $('toggle-editor').style.display = 'block';
        _setToggle('editor', true);

        // Alle Sektionen zurücksetzen
        document.querySelectorAll('#body-editor .toggle-section').forEach(sec => {
            sec.classList.remove('cve-open', 'cve-view-mode', 'cve-edit-mode');
            sec.querySelector(':scope > .section-header')?.classList.remove('open');
        });

        await loadConsultantData(aid);

        const upload = _allData.find(u => u.aid === aid);
        _updateValidateBtn(upload?.pipeline_step === 'validated');
        _updateAnonBtn(false);
    }

    async function loadConsultantData(aid) {
        try {
            const r = await fetch(`/api/cv-editor/consultant/${aid}/`);
            const d = await r.json();
            if (d.success) fillEditor(d);
        } catch(e) {
            const u = _allData.find(x => x.aid === aid);
            if (u) {
                $('cv-first_name').value = u.first_name || '';
                $('cv-last_name').value  = u.last_name  || '';
            }
        }
    }

    function fillEditor(c) {
        const setVal = (id, val) => { const el = $(id); if (el) el.value = val || ''; };

        // Kopf
        setVal('cv-first_name',   c.first_name);
        setVal('cv-last_name',    c.last_name);
        setVal('cv-headline',     c.headline);
        setVal('cv-email',        c.email);
        setVal('cv-phone',        c.phone);
        setVal('cv-location',     c.location);
        setVal('cv-company',      c.company);
        setVal('cv-address',      c.address);
        setVal('cv-website',      c.website);

        // Persönliche Daten
        setVal('cv-birth_year',   c.birth_year);
        setVal('cv-nationality',  c.nationality);
        setVal('cv-edv_since',    c.edv_experience_since);
        setVal('cv-availability', c.availability);
        setVal('cv-stand',        c.stand);

        _consultantId = c.id;
        _dir = c.consultant_dir || _dir;

        // Sprachen
        _fillTags('languages-tags', c.languages || []);

        // Ausbildung
        const eduCont = $('education-container');
        if (eduCont) {
            eduCont.innerHTML = '';
            (c.education || []).filter(e => e.type !== 'course').forEach(e => {
                const row = document.createElement('div');
                row.className = 'cve-edu-item';
                row.innerHTML = `
                    <input type="text" value="${esc(e.degree)}" placeholder="${t('cv_editor.edu_degree')}" oninput="cveEditor.dirty()">
                    <input type="text" value="${esc(e.institution)}" placeholder="${t('cv_editor.edu_institution')}" oninput="cveEditor.dirty()">
                    <input type="text" value="${esc(e.period)}" placeholder="${t('cv_editor.edu_period')}" oninput="cveEditor.dirty()">
                    <button class="cve-btn-remove" onclick="this.closest('.cve-edu-item').remove();cveEditor.dirty()">✗</button>`;
                eduCont.appendChild(row);
            });
        }

        // Tag-Sektionen
        _fillTags('branchen-tags',    c.industries   || []);
        _fillTags('fachbereiche-tags', c.focus_areas  || []);
        _fillTags('schulungen-tags',  (c.education||[]).filter(e=>e.type==='course').map(e=>e.degree));
        _fillTags('zertifikate-tags', c.certifications || []);
        _fillTags('produkte-tags',    c.produkte     || []);

        // Skills
        const skillsCont = $('skills-container');
        if (skillsCont) {
            skillsCont.innerHTML = '';
            Object.entries(c.skills_by_cat || {}).forEach(([cat, skills]) => _addSkillCatDOM(cat, skills));
        }

        // Skills-Kategorie-Dropdown
        const catSel = $('new-cat-select');
        if (catSel && c.skill_categories) {
            const first = catSel.options[0];
            catSel.innerHTML = '';
            catSel.appendChild(first);
            c.skill_categories.forEach(name => {
                const opt = document.createElement('option');
                opt.value = name; opt.textContent = name;
                catSel.appendChild(opt);
            });
        }

        // Kategorien in hidden input speichern für Skill-Move Overlay
        const catHidden = $('cve-skill-cats');
        if (catHidden && c.skill_categories) {
            catHidden.value = c.skill_categories.join('|');
        }

        // Badges
        const allSkills = Object.values(c.skills_by_cat || {}).reduce((s,a)=>s+a.length,0);
        const allCats   = Object.keys(c.skills_by_cat || {}).length;
        const sBadge = $('skills-badge');
        if (sBadge) sBadge.textContent = `${allCats} ${t('cv_editor.cat_label')} · ${allSkills} Skills`;

        // Projekte
        const projCont = $('projects-container');
        if (projCont) {
            projCont.innerHTML = '';
            (c.projects || []).forEach(p => _addProjectDOM(p));
        }
        _updateProjectsBadge();

        // Anon-Status
        $('cve-show-name').value = c.show_name ? 'true' : 'false';

        // View-Mode Buttons initialisieren (einmalig)
        _initSectionViewModes();

        // Kopf-Sektion direkt aufklappen (kein view-mode)
        const kopfSec = $('sec-kopf')?.parentElement;
        if (kopfSec) {
            kopfSec.classList.add('cve-open');
            kopfSec.querySelector(':scope > .section-header')?.classList.add('open');
        }

        // Projekte direkt aufklappen (kein view-mode, zeigt project-view cards)
        const projSec = $('sec-projects')?.parentElement;
        if (projSec) {
            projSec.classList.add('cve-open');
            projSec.querySelector(':scope > .section-header')?.classList.add('open');
        }

        // Projekte View-Mode
        document.querySelectorAll('.cve-project').forEach(p => {
            if (!p.querySelector('.cve-project-view')) _initProjectView(p);
        });

        // Tag-Inputs neu initialisieren (nach DOM-Aufbau)
        [
            ['languages-container', 'languages-tags'],
            ['branchen-container',  'branchen-tags'],
            ['fachbereiche-container', 'fachbereiche-tags'],
            ['schulungen-container', 'schulungen-tags'],
            ['zertifikate-container', 'zertifikate-tags'],
            ['produkte-container',  'produkte-tags'],
        ].forEach(([c, tg]) => _initTagInput(c, tg));
    }

    // ── View-Inhalte aufbauen ─────────────────────────────────

    function _buildTagsView(tagsId, emptyMsg) {
        const tags = Array.from(document.querySelectorAll(`#${tagsId} .cve-tag span:first-child`))
            .map(el => el.textContent.trim()).filter(Boolean);
        if (!tags.length) return `<span class="cve-view-empty">${emptyMsg}</span>`;
        return `<div class="cve-view-tags">${tags.map(tg => `<span class="cve-view-tag">${esc(tg)}</span>`).join('')}</div>`;
    }

    function _buildListView(tagsId, emptyMsg) {
        const items = Array.from(document.querySelectorAll(`#${tagsId} .cve-tag span:first-child`))
            .map(el => el.textContent.trim()).filter(Boolean);
        if (!items.length) return `<span class="cve-view-empty">${emptyMsg}</span>`;
        return `<ul class="cve-view-list">${items.map(i => `<li>${esc(i)}</li>`).join('')}</ul>`;
    }

    function _buildSkillsView() {
        const cats = Array.from(document.querySelectorAll('.cve-skill-cat'));
        if (!cats.length) return `<span class="cve-view-empty">${t('cv_editor.empty_skills')}</span>`;
        return cats.map(cat => {
            const name   = cat.dataset.categoryName || '';
            const skills = Array.from(cat.querySelectorAll('.cve-skill-tags .cve-skill-tag span:first-child'))
                .map(el => el.textContent.trim()).filter(Boolean);
            if (!skills.length) return '';
            return `<div class="cve-view-skill-cat">
                <div class="cve-view-skill-cat-name">${esc(name)} (${skills.length})</div>
                <div class="cve-view-tags">${skills.map(s => `<span class="cve-view-tag">${esc(s)}</span>`).join('')}</div>
            </div>`;
        }).filter(Boolean).join('');
    }

    function _buildPersonalView() {
        const get = id => $(id)?.value?.trim() || '';
        const fields = [
            [t('cv_editor.field_birth_year'),  get('cv-birth_year')],
            [t('cv_editor.field_nationality'), get('cv-nationality')],
            [t('cv_editor.field_edv_since'),   get('cv-edv_since')],
            [t('cv_editor.field_availability'),get('cv-availability')],
            [t('cv_editor.field_stand'),       get('cv-stand')],
        ].filter(([,v]) => v);

        const sprachen = Array.from(document.querySelectorAll('#languages-tags .cve-tag span:first-child'))
            .map(el => el.textContent.trim()).filter(Boolean);

        const ausbildung = Array.from(document.querySelectorAll('#education-container .cve-edu-item'))
            .map(row => {
                const inputs = row.querySelectorAll('input');
                return [inputs[0]?.value, inputs[1]?.value, inputs[2]?.value].filter(Boolean).join(' · ');
            }).filter(Boolean);

        let html = '';
        if (fields.length) {
            html += '<div class="cve-view-grid">';
            fields.forEach(([l,v]) => html += `<div class="cve-view-grid-label">${esc(l)}</div><div class="cve-view-grid-value">${esc(v)}</div>`);
            html += '</div>';
        }
        if (sprachen.length) {
            html += `<div style="margin-top:8px"><strong style="font-size:.78em;color:#163258;text-transform:uppercase">${t('cv_editor.field_languages')}</strong>
                <div class="cve-view-tags" style="margin-top:4px">${sprachen.map(s=>`<span class="cve-view-tag">${esc(s)}</span>`).join('')}</div></div>`;
        }
        if (ausbildung.length) {
            html += `<div style="margin-top:8px"><strong style="font-size:.78em;color:#163258;text-transform:uppercase">${t('cv_editor.field_education')}</strong>
                <ul class="cve-view-list" style="margin-top:4px">${ausbildung.map(a=>`<li>${esc(a)}</li>`).join('')}</ul></div>`;
        }
        return html || `<span class="cve-view-empty">${t('cv_editor.empty_personal')}</span>`;
    }

    // ── Validate / Anon ───────────────────────────────────────
    function _updateValidateBtn(validated) {
        const btn  = $('cve-btn-validate');
        const icon = $('cve-val-icon');
        if (!btn) return;
        if (validated) {
            btn.classList.add('validated');
            if (icon) { icon.classList.remove('bi-square'); icon.classList.add('bi-check-square-fill'); }
        } else {
            btn.classList.remove('validated');
            if (icon) { icon.classList.remove('bi-check-square-fill'); icon.classList.add('bi-square'); }
        }
    }

    function _updateAnonBtn(anon) {
        const inp = $('cve-show-name');
        if (inp) inp.value = anon ? 'false' : 'true';
    }

    async function toggleValidate() {
        if (!_aid) return;
        const btn = $('cve-btn-validate');
        const isVal = btn.classList.contains('validated');
        try {
            const r = await fetch(`/cv-extractor/api/cv-editor/${_aid}/validate/`, {
                method: 'POST',
                headers: {'Content-Type':'application/json','X-CSRFToken':csrf()},
                body: JSON.stringify({validated: !isVal})
            });
            const d = await r.json();
            if (d.success) _updateValidateBtn(!isVal);
        } catch(e) {}
    }

    function toggleAnon() {
        const inp  = $('cve-show-name');
        const btn  = $('cve-btn-anon');
        const icon = btn?.querySelector('i');
        const isAnon = inp?.value === 'false';
        if (inp) inp.value = isAnon ? 'true' : 'false';
        if (icon) icon.className = isAnon ? 'bi bi-eye' : 'bi bi-eye-slash';
        dirty();
    }

    // ── Speichern ─────────────────────────────────────────────
    async function saveSection(section) {
        if (!_aid) return;
        let data = {};

        if (section === 'personal') {
            data = {
                first_name:           $('cv-first_name')?.value  || '',
                last_name:            $('cv-last_name')?.value   || '',
                headline:             $('cv-headline')?.value    || '',
                email:                $('cv-email')?.value       || '',
                phone:                $('cv-phone')?.value       || '',
                location:             $('cv-location')?.value    || '',
                company:              $('cv-company')?.value     || '',
                address:              $('cv-address')?.value     || '',
                website:              $('cv-website')?.value     || '',
                birth_year:           $('cv-birth_year')?.value  || null,
                nationality:          $('cv-nationality')?.value || '',
                edv_experience_since: $('cv-edv_since')?.value   || null,
                availability:         $('cv-availability')?.value || '',
                stand:                $('cv-stand')?.value       || '',
                show_name:            $('cve-show-name')?.value === 'true',
            };
        } else if (['branchen','fachbereiche','schulungen','zertifikate','produkte'].includes(section)) {
            const map = {
                branchen:'branchen-tags', fachbereiche:'fachbereiche-tags',
                schulungen:'schulungen-tags', zertifikate:'zertifikate-tags', produkte:'produkte-tags'
            };
            data = Array.from(document.querySelectorAll(`#${map[section]} .cve-tag span:first-child`))
                .map(el => el.textContent.trim()).filter(Boolean);
        } else if (section === 'skills') {
            data = {};
            document.querySelectorAll('.cve-skill-cat').forEach(cat => {
                const skills = Array.from(cat.querySelectorAll('.cve-skill-tags .cve-skill-tag span:first-child'))
                    .map(el => el.textContent.trim()).filter(Boolean);
                if (cat.dataset.categoryName && skills.length) data[cat.dataset.categoryName] = skills;
            });
        } else if (section === 'projects') {
            data = Array.from(document.querySelectorAll('.cve-project')).map(proj => ({
                period:       proj.querySelector('.cve-project-period-input')?.value  || '',
                company:      proj.querySelector('.cve-project-company-input')?.value || '',
                role:         proj.querySelector('.cve-project-role-input')?.value    || '',
                activities:   Array.from(proj.querySelectorAll('.cve-activity-item input')).map(el=>el.value.trim()).filter(Boolean),
                technologies: Array.from(proj.querySelectorAll('.cve-project-tech-tags .cve-tag span:first-child')).map(el=>el.textContent.trim()).filter(Boolean),
            }));
        }

        try {
            const r = await fetch(`/cv-extractor/api/cv-editor/${_aid}/update/`, {
                method: 'POST',
                headers: {'Content-Type':'application/json','X-CSRFToken':csrf()},
                body: JSON.stringify({section, data})
            });
            const d = await r.json();
            if (d.status === 'success') { _isDirty = false; showToast(t('cv_editor.saved_ok'), 'success'); }
            else showToast(t('cv_editor.saved_err'), 'error');
        } catch(e) { showToast(t('cv_editor.saved_err'), 'error'); }
    }

    // ── Viewer Buttons ────────────────────────────────────────
    function viewPdf()  { if (_aid) window.open(`/data/pdf/${_aid}.pdf`, '_blank'); }
    function viewTxt()  { if (_aid && _dir) window.open(`/data/extracted/${_dir}/`, '_blank'); }
    function viewHtml(lang) {
        if (!_aid || !_dir) return;
        window.open(`/data/html_out/${_dir}/${_aid}${lang==='en'?'-en':''}.html`, '_blank');
    }

    async function generateWord() {
        if (!_aid) return;
        const tpl = $('cve-word-tpl')?.value || 'aid-word';
        try {
            const r = await fetch(`/cv-extractor/api/cv-editor/${_aid}/generate-word/`, {
                method:'POST', headers:{'Content-Type':'application/json','X-CSRFToken':csrf()},
                body: JSON.stringify({template_key: tpl})
            });
            const d = await r.json();
            if (d.success && d.url) window.open(d.url, '_blank');
            else showToast(t('cv_editor.word_err'), 'error');
        } catch(e) { showToast(t('cv_editor.word_err'), 'error'); }
    }

    // ── Delete ────────────────────────────────────────────────
    function deleteConsultant() {
        if (!_aid) return;
        const fn = $('cv-first_name')?.value || '';
        const ln = $('cv-last_name')?.value  || '';
        _showDeleteDialog(fn, ln);
    }

    function _showDeleteDialog(fn, ln) {
        // Alten Dialog entfernen
        document.getElementById('cve-delete-dialog')?.remove();

        const dlg = document.createElement('dialog');
        dlg.id = 'cve-delete-dialog';
        dlg.style.cssText = [
            'border:none', 'padding:0', 'border-radius:12px',
            'max-width:460px', 'width:90%',
            'box-shadow:0 20px 60px rgba(0,0,0,.3)',
        ].join(';');

        dlg.innerHTML = `
            <div style="padding:28px 24px 20px;font-family:inherit;">

                <!-- Icon + Titel -->
                <div style="text-align:center;margin-bottom:16px">
                    <svg width="52" height="52" viewBox="0 0 52 52" fill="none" xmlns="http://www.w3.org/2000/svg" style="margin-bottom:10px">
                        <circle cx="26" cy="26" r="26" fill="#FEE2E2"/>
                        <path d="M26 12L44 42H8L26 12Z" fill="#EF4444" opacity=".1"/>
                        <path stroke="#DC2626" stroke-width="2.5" stroke-linejoin="round" fill="none"
                            d="M26 14L43 42H9L26 14Z"/>
                        <rect x="24" y="22" width="4" height="10" rx="2" fill="#DC2626"/>
                        <rect x="24" y="34" width="4" height="4" rx="2" fill="#DC2626"/>
                    </svg>
                    <h3 style="margin:0 0 4px;font-size:1.15rem;font-weight:700;color:#163258;"
                        id="cve-del-title"></h3>
                    <p style="margin:0;font-size:.82rem;color:#dc3545;font-weight:500;"
                        id="cve-del-warning"></p>
                </div>

                <!-- Berater-Name -->
                <div style="background:#f8f9fa;border:1px solid #dee2e6;border-radius:8px;padding:10px 16px;margin-bottom:12px;display:flex;align-items:center;gap:10px;">
                    <i class="bi bi-person-circle" style="font-size:1.2rem;color:#163258;flex-shrink:0"></i>
                    <div>
                        <div style="font-size:.75rem;color:#6c757d;font-weight:500;" id="cve-del-name-label"></div>
                        <div style="font-size:.95rem;font-weight:700;color:#163258;">${fn} ${ln}</div>
                        <div style="font-size:.75rem;color:#6c757d;font-family:monospace;">${_aid}</div>
                    </div>
                </div>

                <!-- Wirklich löschen -->
                <p style="text-align:center;font-size:.88rem;font-weight:600;color:#163258;margin:0 0 8px"
                    id="cve-del-really"></p>

                <!-- Archivieren Hinweis -->
                <div style="background:#fffbeb;border:1px solid #fcd34d;border-radius:8px;padding:8px 14px;margin-bottom:20px;display:flex;align-items:flex-start;gap:8px;">
                    <i class="bi bi-lightbulb" style="color:#d97706;font-size:1rem;flex-shrink:0;margin-top:1px"></i>
                    <p style="margin:0;font-size:.78rem;color:#92400e;" id="cve-del-hint"></p>
                </div>

                <!-- Buttons -->
                <div style="display:flex;flex-direction:column;gap:8px;">
                    <button id="cve-del-btn-archive"
                        style="display:inline-flex;align-items:center;justify-content:center;gap:8px;
                               padding:10px 20px;border-radius:8px;border:none;cursor:pointer;
                               background:#163258;color:white;font-size:.88rem;font-weight:600;width:100%;">
                        <i class="bi bi-archive"></i>
                        <span id="cve-del-archive-label"></span>
                    </button>
                    <button id="cve-del-btn-confirm"
                        style="display:inline-flex;align-items:center;justify-content:center;gap:8px;
                               padding:9px 20px;border-radius:8px;cursor:pointer;width:100%;
                               background:transparent;border:1.5px solid #dc3545;
                               color:#dc3545;font-size:.88rem;font-weight:500;">
                        <i class="bi bi-trash"></i>
                        <span id="cve-del-confirm-label"></span>
                    </button>
                    <button id="cve-del-btn-cancel"
                        style="display:inline-flex;align-items:center;justify-content:center;gap:8px;
                               padding:9px 20px;border-radius:8px;cursor:pointer;width:100%;
                               background:#f8f9fa;border:1px solid #dee2e6;
                               color:#6c757d;font-size:.88rem;">
                        <i class="bi bi-x-circle"></i>
                        <span id="cve-del-cancel-label"></span>
                    </button>
                </div>
            </div>`;

        document.body.appendChild(dlg);

        // Labels setzen
        document.getElementById('cve-del-title').textContent         = t('cv_editor.delete_title');
        document.getElementById('cve-del-warning').textContent        = t('cv_editor.delete_warning');
        document.getElementById('cve-del-name-label').textContent     = t('cv_editor.delete_name');
        document.getElementById('cve-del-really').textContent         = t('cv_editor.delete_really');
        document.getElementById('cve-del-hint').textContent           = t('cv_editor.delete_hint');
        document.getElementById('cve-del-archive-label').textContent  = t('cv_editor.btn_archive');
        document.getElementById('cve-del-confirm-label').textContent  = t('cv_editor.btn_delete_confirm');
        document.getElementById('cve-del-cancel-label').textContent   = t('cv_editor.btn_cancel_del');

        // Archivieren → Toast + schließen (Archivierung noch nicht implementiert)
        document.getElementById('cve-del-btn-archive').onclick = () => {
            dlg.close(); dlg.remove();
            showToast(t('cv_editor.archive_todo'), 'info');
        };

        // Wirklich löschen
        document.getElementById('cve-del-btn-confirm').onclick = async () => {
            dlg.close(); dlg.remove();
            try {
                const r = await fetch(`/cv-extractor/api/cv-editor/${_aid}/delete/`, {
                    method: 'DELETE',
                    headers: {'Content-Type':'application/json','X-CSRFToken':csrf()},
                    body: JSON.stringify({confirm_name: `${fn} ${ln}`})
                });
                const d = await r.json();
                if (d.success) {
                    showToast(`${fn} ${ln} ${t('cv_editor.deleted')}`, 'success');
                    _isDirty = false;
                    doOpenList();
                    loadConsultants();
                } else {
                    showToast(d.error || t('cv_editor.err_delete'), 'error');
                }
            } catch(e) {
                showToast(t('cv_editor.err_delete'), 'error');
            }
        };

        // Abbrechen
        document.getElementById('cve-del-btn-cancel').onclick = () => {
            dlg.close(); dlg.remove();
        };

        // Außerhalb klicken
        dlg.addEventListener('click', e => {
            if (e.target === dlg) { dlg.close(); dlg.remove(); }
        });

        dlg.showModal();
    }

    // ── Tags ──────────────────────────────────────────────────
    function _initTagInput(containerId, tagsId) {
        const container = $(containerId);
        if (!container) return;
        const input = container.querySelector('.cve-tag-input');
        const btn   = container.querySelector('.cve-add-tag-btn');
        const tags  = $(tagsId);

        function addTag(val) {
            if (!val.trim()) return;
            const tag = document.createElement('div');
            tag.className = 'cve-tag';
            tag.innerHTML = `<span>${esc(val.trim())}</span><span class="cve-remove" onclick="this.closest('.cve-tag').remove();cveEditor.dirty()">×</span>`;
            tags.appendChild(tag);
            if (input) input.value = '';
            dirty();
        }

        if (btn) btn.onclick = () => addTag(input?.value || '');
        if (input) input.addEventListener('keypress', e => { if (e.key==='Enter') { e.preventDefault(); addTag(input.value); } });
    }

    function _fillTags(tagsId, items) {
        const container = $(tagsId);
        if (!container) return;
        container.innerHTML = items.map(item =>
            `<div class="cve-tag"><span>${esc(item)}</span><span class="cve-remove" onclick="this.closest('.cve-tag').remove();cveEditor.dirty()">×</span></div>`
        ).join('');
    }

    // ── Ausbildung ────────────────────────────────────────────
    function addEducation() {
        const container = $('education-container');
        if (!container) return;
        const row = document.createElement('div');
        row.className = 'cve-edu-item';
        row.innerHTML = `
            <input type="text" placeholder="${t('cv_editor.edu_degree')}" oninput="cveEditor.dirty()">
            <input type="text" placeholder="${t('cv_editor.edu_institution')}" oninput="cveEditor.dirty()">
            <input type="text" placeholder="${t('cv_editor.edu_period')}" oninput="cveEditor.dirty()">
            <button class="cve-btn-remove" onclick="this.closest('.cve-edu-item').remove();cveEditor.dirty()">✗</button>`;
        container.appendChild(row);
        dirty();
    }

    // ── Skills ────────────────────────────────────────────────
    async function loadSkillCategories() {}

    function addCategory() {
        const sel = $('new-cat-select');
        const catName = sel?.value;
        if (!catName) return;
        if (document.querySelector(`.cve-skill-cat[data-category-name="${catName}"]`)) return;
        _addSkillCatDOM(catName, []);
        sel.value = '';
        dirty();
    }

    function _addSkillCatDOM(catName, skills) {
        const container = $('skills-container');
        if (!container) return;
        const cat = document.createElement('div');
        cat.className = 'cve-skill-cat';
        cat.dataset.categoryName = catName;
        cat.innerHTML = `
            <div class="cve-skill-cat-hdr" onclick="this.nextElementSibling.classList.toggle('open');this.querySelector('.cve-chv').classList.toggle('open')">
                <span><i class="bi bi-folder" style="margin-right:6px"></i>${esc(catName)}
                    <span class="cve-skill-count">${skills.length}</span>
                </span>
                <i class="bi bi-chevron-down cve-chv"></i>
            </div>
            <div class="cve-skill-cat-body">
                <div class="cve-skill-tags">${skills.map(s =>
                    `<div class="cve-skill-tag">
                        <span onclick="cveEditor._openSkillMove(this.closest('.cve-skill-tag'),'${esc(s)}','${esc(catName)}')">${esc(s)}</span>
                        <span class="cve-remove" onclick="event.stopPropagation();this.closest('.cve-skill-tag').remove();cveEditor._updateSkillBadge(this.closest('.cve-skill-cat'));cveEditor.dirty()">×</span>
                    </div>`).join('')}
                </div>
                <div class="cve-add-skill-row">
                    <input class="cve-add-skill-input" placeholder="${t('cv_editor.add_skill')}">
                    <button class="cve-add-skill-btn" onclick="cveEditor._addSkill(this)">+ ${t('cv_editor.btn_add')}</button>
                </div>
            </div>`;
        container.appendChild(cat);
        _updateSkillBadge(cat);
    }

    function _addSkill(btn) {
        const row   = btn.closest('.cve-add-skill-row');
        const input = row.querySelector('.cve-add-skill-input');
        const val   = input?.value.trim();
        if (!val) return;
        const tags    = row.closest('.cve-skill-cat-body').querySelector('.cve-skill-tags');
        const cat     = btn.closest('.cve-skill-cat');
        const catName = cat.dataset.categoryName;
        const tag = document.createElement('div');
        tag.className = 'cve-skill-tag';
        tag.innerHTML = `<span onclick="cveEditor._openSkillMove(this.closest('.cve-skill-tag'),'${esc(val)}','${esc(catName)}')">${esc(val)}</span><span class="cve-remove" onclick="event.stopPropagation();this.closest('.cve-skill-tag').remove();cveEditor._updateSkillBadge(this.closest('.cve-skill-cat'));cveEditor.dirty()">×</span>`;
        tags.appendChild(tag);
        input.value = '';
        _updateSkillBadge(cat);
        dirty();
    }

    function _updateSkillBadge(catEl) {
        if (!catEl) return;
        const badge = catEl.querySelector('.cve-skill-count');
        if (badge) badge.textContent = catEl.querySelectorAll('.cve-skill-tag').length;
        const allSkills = document.querySelectorAll('.cve-skill-tag').length;
        const allCats   = document.querySelectorAll('.cve-skill-cat').length;
        const badge2 = $('skills-badge');
        if (badge2) badge2.textContent = `${allCats} ${t('cv_editor.cat_label')} · ${allSkills} Skills`;
    }

    // ── Skill Move ────────────────────────────────────────────
    let _moveTag = null, _moveFrom = '';

    function _createSkillOverlay() {
        // Altes Overlay entfernen — immer neu erstellen mit aktuellen Kategorien
        const old = document.getElementById('cve-skill-overlay');
        if (old) old.remove();

        // Kategorien: erst aus skill-cats im DOM, dann aus skill-container
        const catsRaw = document.getElementById('cve-skill-cats')?.value || '';
        let cats = catsRaw.split('|').map(c=>c.trim()).filter(Boolean);

        // Fallback: aus bestehendem new-cat-select
        if (!cats.length) {
            const catSel = document.getElementById('new-cat-select');
            if (catSel) cats = Array.from(catSel.options).map(o=>o.value).filter(Boolean);
        }

        // Fallback: aus Skill-Kategorien im DOM
        if (!cats.length) {
            cats = Array.from(document.querySelectorAll('.cve-skill-cat'))
                .map(c=>c.dataset.categoryName).filter(Boolean);
        }

        // <dialog> bricht aus jedem overflow/transform Container aus
        overlay = document.createElement('dialog');
        overlay.id = 'cve-skill-overlay';
        overlay.style.cssText = [
            'border:none',
            'padding:0',
            'background:transparent',
            'max-width:100vw',
            'max-height:100vh',
            'width:100vw',
            'height:100vh',
            'position:fixed',
            'top:0',
            'left:0',
            'margin:0',
            'display:flex',
            'align-items:center',
            'justify-content:center',
            'z-index:999999',
        ].join(';');

        // Backdrop styling
        const backdropStyle = document.createElement('style');
        backdropStyle.textContent = '#cve-skill-overlay::backdrop { background: rgba(0,0,0,0.65); }';
        document.head.appendChild(backdropStyle);

        overlay.innerHTML = `
            <div style="background:#1e2a3a;border:1px solid rgba(255,255,255,0.2);border-radius:12px;padding:28px;min-width:380px;max-width:480px;color:white;box-shadow:0 20px 60px rgba(0,0,0,0.5);">
                <h3 style="margin:0 0 6px;font-size:1.1rem;" id="cve-move-title"></h3>
                <p style="margin:0 0 18px;color:rgba(255,255,255,0.6);font-size:.85rem;">
                    <span id="cve-move-skill-label"></span> <strong id="cve-move-name" style="color:#4fc3f7;"></strong><br>
                    <span id="cve-move-from-label"></span> <strong id="cve-move-from" style="color:#ffb74d;"></strong>
                </p>
                <label id="cve-move-to-label" style="font-size:.85rem;color:rgba(255,255,255,0.7);display:block;margin-bottom:8px;"></label>
                <select id="cve-move-target" style="width:100%;margin:0 0 20px;padding:10px;border-radius:6px;border:1px solid rgba(255,255,255,0.2);background:#2a3a4a;color:white;font-size:.9rem;">
                    ${cats.map(c => `<option value="${c}">${c}</option>`).join('')}
                </select>
                <div style="display:flex;gap:10px;margin-bottom:10px;">
                    <button id="cve-move-btn-consultant"
                        style="flex:1;padding:10px;border-radius:6px;border:none;background:#27ae60;color:white;cursor:pointer;font-size:.85rem;font-weight:600;"></button>
                    <button id="cve-move-btn-global"
                        style="flex:1;padding:10px;border-radius:6px;border:none;background:#e67e22;color:white;cursor:pointer;font-size:.85rem;font-weight:600;"></button>
                </div>
                <button id="cve-move-btn-cancel"
                    style="width:100%;padding:8px;border-radius:6px;border:1px solid rgba(255,255,255,0.2);background:transparent;color:rgba(255,255,255,0.6);cursor:pointer;font-size:.85rem;"></button>
            </div>`;

        document.body.appendChild(overlay);

        // Buttons
        overlay.querySelector('#cve-move-btn-consultant').onclick = () => cveEditor.moveSkill('consultant');
        overlay.querySelector('#cve-move-btn-global').onclick     = () => cveEditor.moveSkill('both');
        overlay.querySelector('#cve-move-btn-cancel').onclick     = () => cveEditor.closeSkillPopup();
        overlay.addEventListener('click', e => { if (e.target === overlay) cveEditor.closeSkillPopup(); });

        return overlay;
    }

    function _updateOverlayLabels() {
        const el = (id, key) => { const e = document.getElementById(id); if (e) e.textContent = t(key); };
        el('cve-move-title',        'cv_editor.skill_move_title');
        el('cve-move-skill-label',  'cv_editor.skill_label');
        el('cve-move-from-label',   'cv_editor.skill_from');
        el('cve-move-to-label',     'cv_editor.skill_to');
        el('cve-move-btn-consultant', 'cv_editor.skill_move_consultant');
        el('cve-move-btn-global',   'cv_editor.skill_move_global');
        el('cve-move-btn-cancel',   'cv_editor.btn_cancel');
    }

    function _openSkillMove(tag, skillName, fromCat) {
        _moveTag  = tag;
        _moveFrom = fromCat;

        const overlay = _createSkillOverlay();
        _updateOverlayLabels();

        document.getElementById('cve-move-name').textContent = skillName;
        document.getElementById('cve-move-from').textContent = fromCat;

        // Dropdown: aktuelle Kategorie ausblenden
        const sel = document.getElementById('cve-move-target');
        if (sel) {
            Array.from(sel.options).forEach(opt => {
                opt.style.display = opt.value === fromCat ? 'none' : '';
            });
            const firstVisible = Array.from(sel.options).find(o => o.style.display !== 'none');
            if (firstVisible) sel.value = firstVisible.value;
        }

        // dialog.showModal() bricht aus allen Containern aus
        if (typeof overlay.showModal === 'function') {
            overlay.showModal();
        } else {
            overlay.style.display = 'flex';
        }
    }

    async function moveSkill(scope) {
        if (!_moveTag || !_aid) return;

        const skillName = _moveTag.querySelector('span:first-child')?.textContent?.trim();
        const toCat     = $('cve-move-target')?.value;
        const fromCat   = _moveFrom;

        if (!skillName || !toCat || toCat === fromCat) {
            showToast(t('cv_editor.skill_same_cat'), 'error');
            return;
        }

        try {
            const r = await fetch(`/cv-extractor/api/cv-editor/${_aid}/move-skill/`, {
                method: 'POST',
                headers: {'Content-Type':'application/json','X-CSRFToken':csrf()},
                body: JSON.stringify({skill_name: skillName, to_category: toCat, scope})
            });
            const d = await r.json();

            if (d.success) {
                // Ziel-Kategorie im DOM finden oder anlegen
                let targetCat = document.querySelector(`.cve-skill-cat[data-category-name="${toCat}"]`);
                if (!targetCat) {
                    _addSkillCatDOM(toCat, []);
                    targetCat = document.querySelector(`.cve-skill-cat[data-category-name="${toCat}"]`);
                }

                // Tag verschieben
                const targetTags = targetCat.querySelector('.cve-skill-tags');
                _moveTag.remove();
                targetTags.appendChild(_moveTag);

                // onClick neu setzen (closure hatte alten fromCat)
                _moveTag.onclick = () => _openSkillMove(_moveTag, skillName, toCat);

                // Badges aktualisieren
                const fromCatEl = document.querySelector(`.cve-skill-cat[data-category-name="${fromCat}"]`);
                _updateSkillBadge(fromCatEl);
                _updateSkillBadge(targetCat);

                // Ziel-Kategorie aufklappen
                const targetBody = targetCat.querySelector('.cve-skill-cat-body');
                if (targetBody && !targetBody.classList.contains('open')) {
                    targetBody.classList.add('open');
                    targetCat.querySelector('.cve-chv')?.classList.add('open');
                }

                closeSkillPopup();

                const msg = scope === 'both'
                    ? `✅ "${skillName}" → ${toCat} (${t('cv_editor.skill_scope_global')})`
                    : `✅ "${skillName}" → ${toCat} (${t('cv_editor.skill_scope_consultant')})`;
                showToast(msg, 'success');
                dirty();
            } else {
                showToast(d.error || t('cv_editor.err_move'), 'error');
            }
        } catch(e) {
            showToast(t('cv_editor.err_move'), 'error');
        }
    }

    function closeSkillPopup() {
        const overlay = document.getElementById('cve-skill-overlay');
        if (overlay) {
            if (typeof overlay.close === 'function') overlay.close();
            else overlay.style.display = 'none';
            overlay.remove(); // Immer neu erstellen beim nächsten Klick
        }
        _moveTag  = null;
        _moveFrom = '';
    }

    // ── Projekte ──────────────────────────────────────────────
    function _addProjectDOM(p) {
        const container = $('projects-container');
        if (!container) return;
        const proj = document.createElement('div');
        proj.className = 'cve-project';
        if (p.id) proj.dataset.projectId = p.id;

        const actsHtml = (p.activities||[]).map(a =>
            `<div class="cve-activity-item"><input type="text" value="${esc(a)}" oninput="cveEditor.dirty()"><button class="cve-btn-remove" onclick="this.closest('.cve-activity-item').remove();cveEditor.dirty()">✗</button></div>`
        ).join('');

        const techHtml = (p.technologies||[]).map(tech =>
            `<div class="cve-tag"><span>${esc(tech)}</span><span class="cve-remove" onclick="this.closest('.cve-tag').remove();cveEditor.dirty()">×</span></div>`
        ).join('');

        proj.innerHTML = `
            <div class="cve-project-hdr" onclick="this.nextElementSibling.classList.toggle('open');this.querySelector('.cve-chv').classList.toggle('open')">
                <div class="cve-project-title">
                    <span class="cve-project-period">${esc(p.period||'')}</span>
                    <span class="cve-project-company">${esc(p.company||'')}</span>
                    <span class="cve-project-role">${esc(p.role||'')}</span>
                </div>
                <i class="bi bi-chevron-down cve-chv"></i>
            </div>
            <div class="cve-project-body">
                <div class="cve-project-field"><label>${t('cv_editor.proj_period')}</label><input class="cve-project-period-input" value="${esc(p.period||'')}" oninput="cveEditor.dirty()"></div>
                <div class="cve-project-field"><label>${t('cv_editor.proj_company')}</label><input class="cve-project-company-input" value="${esc(p.company||'')}" oninput="cveEditor.dirty()"></div>
                <div class="cve-project-field"><label>${t('cv_editor.proj_role')}</label><input class="cve-project-role-input" value="${esc(p.role||'')}" oninput="cveEditor.dirty()"></div>
                <div class="cve-project-field"><label>${t('cv_editor.proj_activities')}</label>
                    <div class="cve-project-activities">${actsHtml}</div>
                    <button class="cve-add-btn" onclick="cveEditor._addActivity(this)">+ <span>${t('cv_editor.add_activity')}</span></button>
                </div>
                <div class="cve-project-field"><label>${t('cv_editor.proj_tech')}</label>
                    <div class="cve-tag-wrap">
                        <div class="cve-tags cve-project-tech-tags">${techHtml}</div>
                        <input class="cve-tag-input" placeholder="${t('cv_editor.add_tech')}">
                        <button class="cve-add-tag-btn">+</button>
                    </div>
                </div>
            </div>`;

        container.appendChild(proj);
        _initProjectView(proj);

        const tagWrap = proj.querySelector('.cve-tag-wrap');
        const inp = tagWrap.querySelector('.cve-tag-input');
        const btn = tagWrap.querySelector('.cve-add-tag-btn');
        const tags = tagWrap.querySelector('.cve-project-tech-tags');
        btn.onclick = () => {
            if (!inp.value.trim()) return;
            const tag = document.createElement('div');
            tag.className = 'cve-tag';
            tag.innerHTML = `<span>${esc(inp.value.trim())}</span><span class="cve-remove" onclick="this.closest('.cve-tag').remove();cveEditor.dirty()">×</span>`;
            tags.appendChild(tag); inp.value=''; dirty();
        };
    }

    function addProject() {
        _addProjectDOM({period:'',company:'',role:'',activities:[],technologies:[]});
        // Neues Projekt direkt im Edit-Mode
        const projs = document.querySelectorAll('.cve-project');
        const last  = projs[projs.length-1];
        if (last) last.classList.add('edit-mode');
        _updateProjectsBadge();
        dirty();
    }

    function _addActivity(btn) {
        const acts = btn.previousElementSibling;
        const item = document.createElement('div');
        item.className = 'cve-activity-item';
        item.innerHTML = `<input type="text" oninput="cveEditor.dirty()"><button class="cve-btn-remove" onclick="this.closest('.cve-activity-item').remove();cveEditor.dirty()">✗</button>`;
        acts.appendChild(item);
        dirty();
    }

    function _updateProjectsBadge() {
        const badge = $('projects-badge');
        const count = document.querySelectorAll('.cve-project').length;
        if (badge) badge.textContent = `${count} ${t('cv_editor.projects_label')}`;
    }

    // ── Admin Settings ───────────────────────────────────────
    let _settingsData = {};

    async function openAdminSettings() {
        if (!window.ABPE_CONFIG?.is_admin) return;
        const overlay = document.getElementById('cve-settings-overlay');
        const form    = document.getElementById('cve-settings-form');
        if (!overlay || !form) return;

        overlay.style.display = 'flex';
        form.innerHTML = `<div style="text-align:center;padding:40px;color:#6c757d;">
            <svg width="32" height="32" viewBox="0 0 24 24" fill="#adb5bd"><circle cx="12" cy="12" r="10" opacity=".3"/><path d="M12 2a10 10 0 0 1 10 10h-2a8 8 0 0 0-8-8z"/></svg>
        </div>`;

        try {
            const r = await fetch('/cv-extractor/api/settings/');
            const d = await r.json();
            if (d.success) {
                _settingsData = d.settings;
                _renderSettingsForm(d.settings, form);
            }
        } catch(e) {
            form.innerHTML = `<p style="color:#dc3545;padding:20px">${t('cv_editor.err_settings_load')}</p>`;
        }
    }

    function _renderSettingsForm(settings, container) {
        const groups = {};
        // Settings gruppieren
        for (const [key, val] of Object.entries(settings)) {
            const parts = key.split('.');
            const group = parts.length > 1 ? parts[0] : 'general';
            const subkey = parts.length > 1 ? parts.slice(1).join('.') : key;
            if (!groups[group]) groups[group] = [];
            groups[group].push({ key, subkey, val });
        }

        const groupIcons = {
            api:        '<path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 14H9V8h2v8zm4 0h-2V8h2v8z"/>',
            paths:      '<path d="M10 4H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V8c0-1.1-.9-2-2-2h-8l-2-2z"/>',
            system:     '<path d="M9.4 16.6L4.8 12l4.6-4.6L8 6l-6 6 6 6 1.4-1.4zm5.2 0l4.6-4.6-4.6-4.6L16 6l6 6-6 6-1.4-1.4z"/>',
            pipeline:   '<path d="M17 12h-5v5h5v-5zM16 1v2H8V1H6v2H5c-1.11 0-1.99.9-1.99 2L3 19c0 1.1.89 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2h-1V1h-2zm3 18H5V8h14v11z"/>',
            email:      '<path d="M20 4H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zm0 4l-8 5-8-5V6l8 5 8-5v2z"/>',
            elasticsearch: '<path d="M15.5 14h-.79l-.28-.27C15.41 12.59 16 11.11 16 9.5 16 5.91 13.09 3 9.5 3S3 5.91 3 9.5 5.91 16 9.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z"/>',
            suitecrm:   '<path d="M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zM9 17H7v-7h2v7zm4 0h-2V7h2v10zm4 0h-2v-4h2v4z"/>',
            templates:  '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8l-6-6zm-1 1.5L18.5 9H13V3.5zM6 20V4h5v7h7v9H6z"/>',
        };

        let html = '';
        for (const [group, items] of Object.entries(groups)) {
            const gid = 'cve-sg-' + group;
            const icon = groupIcons[group] || groupIcons.system;
            const label = group.charAt(0).toUpperCase() + group.slice(1).replace(/_/g,' ');

            html += `<div style="border:1px solid #dee2e6;border-radius:8px;margin-bottom:8px;overflow:hidden;">
                <div onclick="this.nextElementSibling.classList.toggle('open')"
                     style="display:flex;align-items:center;gap:10px;padding:12px 16px;
                            background:#f8f9fa;cursor:pointer;user-select:none;">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="#163258"><path d="${icon.match(/d="([^"]+)"/)?.[1]||''}"/></svg>
                    <span style="font-weight:600;font-size:.88rem;color:#163258;flex:1">${label}</span>
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="#6c757d"><path d="M7 10l5 5 5-5z"/></svg>
                </div>
                <div class="" style="display:none;padding:12px 16px;background:white;">`;

            for (const { key, subkey, val } of items) {
                const inputId = 'cve-s-' + key.replace(/\./g,'-');
                const isBoolean = typeof val === 'boolean';
                const isLong = typeof val === 'string' && val.length > 60;

                html += `<div style="margin-bottom:10px;display:grid;grid-template-columns:180px 1fr;gap:8px;align-items:center;">
                    <label style="font-size:.78rem;color:#6c757d;font-weight:500" for="${inputId}">${subkey}</label>`;

                if (isBoolean) {
                    html += `<label style="display:flex;align-items:center;gap:8px;cursor:pointer;">
                        <input type="checkbox" id="${inputId}" data-key="${key}" ${val?'checked':''} 
                               style="width:16px;height:16px;accent-color:#163258;cursor:pointer;">
                        <span style="font-size:.82rem;color:#212529">${val?'Aktiv':'Inaktiv'}</span>
                    </label>`;
                } else if (isLong) {
                    html += `<textarea id="${inputId}" data-key="${key}" rows="2"
                        style="width:100%;padding:6px 10px;border:1px solid #dee2e6;border-radius:6px;
                               font-size:.82rem;font-family:monospace;resize:vertical;">${val||''}</textarea>`;
                } else {
                    html += `<input type="text" id="${inputId}" data-key="${key}" value="${String(val||'').replace(/"/g,'&quot;')}"
                        style="width:100%;padding:6px 10px;border:1px solid #dee2e6;border-radius:6px;font-size:.82rem;">`;
                }
                html += `</div>`;
            }

            html += `</div></div>`;
        }

        container.innerHTML = html;

        // Toggle Sektionen
        container.querySelectorAll('[onclick]').forEach(el => {
            const content = el.nextElementSibling;
            el.addEventListener('click', () => {
                const isOpen = content.style.display !== 'none';
                content.style.display = isOpen ? 'none' : 'block';
                el.querySelector('svg:last-child').style.transform = isOpen ? '' : 'rotate(180deg)';
            });
        });
    }

    async function saveAdminSettings() {
        const form = document.getElementById('cve-settings-form');
        if (!form) return;

        // Werte aus Formular lesen
        const updated = JSON.parse(JSON.stringify(_settingsData));
        form.querySelectorAll('[data-key]').forEach(el => {
            const key = el.dataset.key;
            const parts = key.split('.');
            let obj = updated;
            for (let i = 0; i < parts.length - 1; i++) {
                obj = obj[parts[i]] = obj[parts[i]] || {};
            }
            const last = parts[parts.length - 1];
            if (el.type === 'checkbox') {
                obj[last] = el.checked;
            } else {
                const orig = _settingsData;
                let origVal = orig;
                parts.forEach(p => origVal = origVal?.[p]);
                obj[last] = typeof origVal === 'number' ? Number(el.value) : el.value;
            }
        });

        try {
            const r = await fetch('/cv-extractor/api/settings/', {
                method: 'POST',
                headers: {'Content-Type':'application/json','X-CSRFToken':csrf()},
                body: JSON.stringify(updated)
            });
            const d = await r.json();
            if (d.success) {
                showToast(t('cv_editor.settings_saved'), 'success');
                closeAdminSettings();
            } else {
                showToast(d.error || t('cv_editor.err_settings_save'), 'error');
            }
        } catch(e) {
            showToast(t('cv_editor.err_settings_save'), 'error');
        }
    }

    function closeAdminSettings() {
        const overlay = document.getElementById('cve-settings-overlay');
        if (overlay) overlay.style.display = 'none';
    }

    // ── Reaktivieren ──────────────────────────────────────────
    async function reactivateConsultant(aid, fn, ln) {
        if (!confirm(`${fn} ${ln} reaktivieren?`)) return;
        try {
            const r = await fetch(`/cv-extractor/api/cv-editor/${aid}/reactivate/`, {
                method: 'POST',
                headers: {'Content-Type':'application/json','X-CSRFToken':csrf()},
            });
            const d = await r.json();
            if (d.success) {
                showToast(`${fn} ${ln} ${t('cv_editor.reactivated')}`, 'success');
                loadConsultants();
            } else {
                showToast(d.error || t('cv_editor.err_reactivate'), 'error');
            }
        } catch(e) {
            showToast(t('cv_editor.err_reactivate'), 'error');
        }
    }

    // ── Projekt View/Edit ─────────────────────────────────────
    function _initProjectView(projEl) {
        const period  = projEl.querySelector('.cve-project-period-input')?.value  || '';
        const company = projEl.querySelector('.cve-project-company-input')?.value || '';
        const role    = projEl.querySelector('.cve-project-role-input')?.value    || '';
        const acts    = Array.from(projEl.querySelectorAll('.cve-project-activities .cve-activity-item input')).map(i=>i.value).filter(Boolean);
        const techs   = Array.from(projEl.querySelectorAll('.cve-project-tech-tags .cve-tag span:first-child')).map(el=>el.textContent.trim()).filter(Boolean);

        const view = document.createElement('div');
        view.className = 'cve-project-view';
        view.innerHTML = `
            <div class="cve-project-view-hdr">
                <div class="cve-project-view-meta">
                    ${period  ? `<span class="cve-project-view-date">${esc(period)}</span>`   : ''}
                    ${company ? `<span class="cve-project-view-client">${esc(company)}</span>` : ''}
                </div>
                <button class="cve-edit-btn cve-proj-edit-btn"><i class="bi bi-pencil"></i></button>
            </div>
            ${role ? `<div class="cve-project-view-role">${esc(role)}</div>` : ''}
            ${acts.length ? `<div class="cve-project-view-acts"><ul>${acts.map(a=>`<li>${esc(a)}</li>`).join('')}</ul></div>` : ''}
            ${techs.length ? `<div class="cve-project-view-tech"><strong>${t('cv_editor.proj_tech')}:</strong> ${techs.map(t=>esc(t)).join(', ')}</div>` : ''}`;

        view.querySelector('.cve-proj-edit-btn').addEventListener('click', e => {
            e.stopPropagation();
            projEl.classList.add('edit-mode');
        });

        projEl.insertBefore(view, projEl.firstChild);

        const backBar = document.createElement('div');
        backBar.className = 'cve-project-back-bar';
        const backBtn = document.createElement('button');
        backBtn.className = 'cve-edit-btn';
        backBtn.innerHTML = `<i class="bi bi-eye"></i> ${t('cv_editor.btn_preview')}`;
        backBtn.addEventListener('click', e => {
            e.stopPropagation();
            projEl.classList.remove('edit-mode');
            _refreshProjectView(projEl);
        });
        backBar.appendChild(backBtn);
        view.after(backBar);
    }

    function _refreshProjectView(projEl) {
        projEl.querySelector('.cve-project-view')?.remove();
        projEl.querySelector('.cve-project-back-bar')?.remove();
        _initProjectView(projEl);
    }

    // ── Toast ─────────────────────────────────────────────────
    function showToast(msg, type='success') {
        let c = $('cve-toast-container');
        if (!c) {
            c = document.createElement('div'); c.id='cve-toast-container';
            c.style.cssText='position:fixed;top:20px;right:20px;z-index:9999;display:flex;flex-direction:column;gap:8px;';
            document.body.appendChild(c);
        }
        const el = document.createElement('div');
        const colors = {success:'#27ae60',error:'#dc3545',info:'#163258'};
        el.style.cssText=`background:white;border-left:4px solid ${colors[type]||colors.info};border-radius:6px;padding:10px 16px;font-size:.83rem;box-shadow:0 2px 8px rgba(0,0,0,.15);display:flex;align-items:center;gap:8px;min-width:200px;`;
        el.innerHTML=`<span style="flex:1">${msg}</span><span style="cursor:pointer;color:#adb5bd" onclick="this.parentNode.remove()">×</span>`;
        c.appendChild(el);
        setTimeout(()=>{ if(el.parentNode) el.remove(); }, 3500);
    }

    // ── Init ──────────────────────────────────────────────────
    function init() {
        [
            ['languages-container','languages-tags'],
            ['branchen-container','branchen-tags'],
            ['fachbereiche-container','fachbereiche-tags'],
            ['schulungen-container','schulungen-tags'],
            ['zertifikate-container','zertifikate-tags'],
            ['produkte-container','produkte-tags'],
        ].forEach(([c,tg]) => _initTagInput(c, tg));

        const addEdu  = $('add-education'); if (addEdu)  addEdu.onclick  = addEducation;
        const addCat  = $('add-cat-btn');   if (addCat)  addCat.onclick  = addCategory;
        const addProj = $('add-project');   if (addProj) addProj.onclick = addProject;

        loadConsultants();
        setInterval(loadConsultants, 30000);
    }

    return {
        init, dirty,
        get _isDirty() { return _isDirty; },
        tryOpenList, toggleEditorMain, toggleSec,
        loadConsultants, filterTable,
        openEditor,
        toggleValidate, toggleAnon,
        saveSection,
        viewPdf, viewTxt, viewHtml, generateWord,
        deleteConsultant,
        addEducation,
        addCategory, _addSkill, _updateSkillBadge,
        _openSkillMove, moveSkill, closeSkillPopup,
        addProject, _addActivity,
        popupSave, popupDiscard, popupCancel,
        showToast,
        reactivateConsultant,
        openAdminSettings, closeAdminSettings, saveAdminSettings,
    };

})();

const _cveStyle = document.createElement('style');
_cveStyle.textContent = `@keyframes cveSlideIn{from{transform:translateX(100%);opacity:0}to{transform:translateX(0);opacity:1}}`;
document.head.appendChild(_cveStyle);
