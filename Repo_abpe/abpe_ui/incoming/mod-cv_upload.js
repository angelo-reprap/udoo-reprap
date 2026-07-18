// mod-cv_upload.js
// Alle Texte über t('cv_upload.key') — kein hardcoded Text

const cvUpload = (() => {

    const EXTENSION_ID = 'pccckjkmnkmhakbgdgodhbfcdoldcbjn';

    let selFile = null;
    let allPersons = [];
    let uploads = [];
    let dupeTimer = null;
    let pollTimer = null;
    let PLATFORMS = [];
    let _nmData = {};
    let _nmPlatform = '';
    let _nmRes = null;
    let _nmFormOpen = false;

    const $ = id => document.getElementById(id);
    const csrf = () => $('csrf') ? $('csrf').value : '';

    // ── i18n Lookup ───────────────────────────────────────────────────
    function t(key, vars = {}) {
        const keys = key.split('.');
        let val = window.i18nData || {};
        for (const k of keys) { val = val[k]; if (val === undefined) return key; }
        if (typeof val === 'string') {
            return val.replace(/\{(\w+)\}/g, (_, k) => vars[k] !== undefined ? vars[k] : `{${k}}`);
        }
        return key;
    }

    function icon(name) { return `<i class="bi bi-${name}"></i>`; }

    // ── Hilfsfunktionen ───────────────────────────────────────────────
    function fmtBytes(b) {
        if (!b) return '';
        const k = 1024, s = ['B', 'KB', 'MB'];
        const i = Math.floor(Math.log(b) / Math.log(k));
        return (b / Math.pow(k, i)).toFixed(1) + ' ' + s[i];
    }

    function fmtDate(iso) {
        if (!iso) return '–';
        const d = new Date(iso);
        return d.toLocaleDateString() + ' ' + d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    }

    function esc(s) {
        return (s || '').replace(/[&<>]/g, m => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' }[m]));
    }

    function incVersion(v) {
        const p = (v || '1.0.0.0').split('.');
        if (p.length === 4) { p[3] = String(parseInt(p[3]) + 1); return p.join('.'); }
        return '1.0.0.1';
    }

    function triggerDupe() {
        clearTimeout(dupeTimer);
        dupeTimer = setTimeout(checkDupe, 450);
    }

    function spinning(text) { return `${icon('hourglass-split')} ${text}`; }

    // ── Plattformen ───────────────────────────────────────────────────
    async function loadPlatforms() {
        try {
            const r = await fetch('/cv-extractor/api/url-platforms/');
            const d = await r.json();
            if (d.success) { PLATFORMS = d.platforms.filter(p => p.enabled); initPlatformDropdowns(); }
        } catch (e) {
            PLATFORMS = [
                { code: 'fl',    label: 'freelancermap.de', pattern: 'freelancermap.de', enabled: true },
                { code: 'gu',    label: 'GULP',             pattern: 'gulp.de',          enabled: true },
                { code: 'other', label: 'Andere',           pattern: '',                 enabled: true },
            ];
            initPlatformDropdowns();
        }
    }

    function initPlatformDropdowns() {
        const sel = $('url-platform');
        if (!sel) return;
        sel.innerHTML = '';
        PLATFORMS.filter(p => p.enabled).forEach(p => {
            const o = document.createElement('option');
            o.value = p.code; o.textContent = p.label;
            sel.appendChild(o);
        });
        const btn = $('flm-session-btn');
        if (btn) btn.style.display = 'none';
        sel.addEventListener('change', () => {
            const show = sel.value === 'fl' || sel.value === 'gu';
            if (btn) btn.style.display = show ? 'inline-flex' : 'none';
            if (show) checkSessionStatus(sel.value);
        });
        checkSessionStatus();
    }

    function autoDetectPlatform(url) {
        const sel = $('url-platform');
        if (!sel) return;
        if (/^\d+$/.test(url.trim())) {
            sel.value = 'gu';
            const btn = $('flm-session-btn');
            if (btn) btn.style.display = 'inline-flex';
            checkSessionStatus('gu'); return;
        }
        const found = PLATFORMS.find(p => p.pattern && url.includes(p.pattern));
        sel.value = found ? found.code : 'other';
        const btn = $('flm-session-btn');
        const showBtn = found && (found.code === 'fl' || found.code === 'gu');
        if (btn) btn.style.display = showBtn ? 'inline-flex' : 'none';
        if (showBtn) checkSessionStatus(found.code);
    }

    // ── Batch ─────────────────────────────────────────────────────────
    function toggleBatch() {
        const a = $('batch-area'), b = $('batch-toggle-btn');
        const open = a.style.display === 'none' || a.style.display === '';
        a.style.display = open ? 'block' : 'none';
        if (b) b.classList.toggle('cv-btn-primary', open);
    }

    function handleCsvDrop(e) {
        e.preventDefault(); $('url-dz').classList.remove('over');
        const file = e.dataTransfer.files[0];
        if (file) loadUrlFile({ files: [file] });
    }

    function loadUrlFile(input) {
        const file = input.files[0]; if (!file) return;
        const reader = new FileReader();
        reader.onload = e => {
            const lines = e.target.result.split('\n').map(l => l.split(',')[0].trim()).filter(l => l.startsWith('http'));
            $('url-batch').value = lines.join('\n'); updateBatchCount();
        };
        reader.readAsText(file);
    }

    function updateBatchCount() {
        const lines = ($('url-batch').value || '').split('\n').map(l => l.trim()).filter(l => l.startsWith('http'));
        const el = $('batch-count');
        if (el) el.textContent = lines.length ? `${lines.length} URL${lines.length > 1 ? 's' : ''}` : '';
    }

    async function importSingleUrl() {
        let url = $('url-input').value.trim();
        const platform = $('url-platform').value;
        if (!url) { alert(t('cv_upload.err_url_required')); return; }
        if (platform === 'gu' && /^\d+$/.test(url)) url = `https://www.gulp.de/talentfinder/app/experten?gulpId=${url}`;
        const btn = $('url-import-btn');
        btn.disabled = true;
        btn.innerHTML = spinning(t('cv_upload.status_importing'));
        const res = $('url-result');
        res.style.display = 'block';
        res.innerHTML = spinning(t('cv_upload.status_fetching'));
        try {
            const r = await fetch('/cv-extractor/api/import-url/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf() },
                body: JSON.stringify({ url, platform, cookies: {} })
            });
            const d = await r.json();
            if (d.success) {
                res.innerHTML = `<div style="display:flex;gap:8px;align-items:start;">${icon('check-circle')} <div><strong>${d.name}</strong><br><small style="color:var(--text-secondary)">${icon('folder')} ${d.dir} · ${d.keywords} Keywords${d.downloaded > 0 ? ` · ${icon('file-earmark-pdf')} ${d.downloaded} PDF(s)` : ''}</small></div></div>`;
                if ((platform === 'gu' || platform === 'fl') && d.dir) {
                    const dirName = d.dir.split('/').pop();
                    const dbRes = await fetch('/cv-extractor/api/import-url-to-db/', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf() },
                        body: JSON.stringify({ dir_name: dirName, platform })
                    });
                    const dbData = await dbRes.json();
                    if (dbData.success) res.innerHTML += `<br><small style="color:var(--color-text-success)">${icon('gear')} ${t('cv_upload.status_pipeline')}${dbData.editor_url ? `<a href="${dbData.editor_url}" target="_blank" style="margin-left:8px;font-weight:500;color:var(--accent-color)">${icon('pencil-square')} ${t('cv_upload.editor_open')}</a>` : ''}</small>`;
                }
                loadUploads();
                if (d.name) {
                    const parts = d.name.trim().split(' ');
                    const fn = $('fn'), ln = $('ln');
                    if (fn && ln) { if (parts.length >= 2) { fn.value = parts[0]; ln.value = parts.slice(1).join(' '); } else fn.value = d.name; }
                }
            } else if (d.name_missing) {
                showNameMissingPopup(d, platform, res);
            } else {
                res.innerHTML = `<div style="color:var(--color-text-danger)">${icon('x-circle')} ${d.error || t('cv_upload.err_import')}</div>`;
            }
        } catch (e) {
            res.innerHTML = `<div style="color:var(--color-text-danger)">${icon('x-circle')} ${e.message}</div>`;
        }
        btn.disabled = false;
        btn.innerHTML = `${icon('download')} <span data-i18n="cv_upload.btn_import">${t('cv_upload.btn_import')}</span>`;
    }

    async function importBatch() {
        const lines = ($('url-batch').value || '').split('\n').map(l => l.trim()).filter(l => l.startsWith('http'));
        if (!lines.length) { alert(t('cv_upload.err_no_urls')); return; }
        $('url-queue').style.display = 'block';
        const qList = $('url-queue-list');
        const items = lines.map(url => {
            const p = PLATFORMS.find(pl => pl.pattern && url.includes(pl.pattern));
            return { url, label: p ? p.label : 'Andere', code: p ? p.code : 'other', status: 'wartend', name: '' };
        });
        const statusHtml = {
            wartend: `<span class="cv-badge cv-badge-wait">${t('cv_upload.sort_status')}</span>`,
            läuft:   `<span class="cv-badge cv-badge-proc">${icon('hourglass-split')}</span>`,
            fertig:  `<span class="cv-badge cv-badge-ok">✓ ${t('cv_upload.status_done')}</span>`,
            fehler:  `<span class="cv-badge cv-badge-fail">✗ ${t('cv_upload.err_import')}</span>`,
        };
        const renderQueue = () => {
            qList.innerHTML = items.map(it => `
                <div style="display:flex;align-items:center;gap:8px;padding:6px 8px;border-radius:var(--border-radius-md);background:var(--bg-secondary);border:0.5px solid var(--border-color);margin-bottom:4px;font-size:.75rem;">
                    <div style="flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${it.name || it.url.substring(0, 50)}</div>
                    <div style="color:var(--text-secondary);width:110px;text-align:right;">${it.label}</div>
                    <div style="width:80px;text-align:right;">${statusHtml[it.status] || ''}</div>
                </div>`).join('');
        };
        renderQueue();
        for (let i = 0; i < items.length; i++) {
            items[i].status = 'läuft'; renderQueue();
            try {
                const r = await fetch('/cv-extractor/api/import-url/', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf() },
                    body: JSON.stringify({ url: items[i].url, platform: items[i].code, cookies: {} })
                });
                const d = await r.json();
                items[i].status = d.success ? 'fertig' : 'fehler';
                items[i].name = d.name || '';
            } catch (e) { items[i].status = 'fehler'; }
            renderQueue();
            if (i < items.length - 1) await new Promise(r => setTimeout(r, 1500));
        }
        loadUploads();
    }

    // ── Dublettenprüfung ──────────────────────────────────────────────
    async function checkDupe() {
        const fn = $('fn').value.trim(), ln = $('ln').value.trim();
        if (!fn || !ln || !selFile) {
            $('dupe-box').innerHTML = `<div class="cv-dupe-empty">${icon('info-circle')}<p>${t('cv_upload.dupe_hint')}</p></div>`;
            $('up-btn').disabled = true; return;
        }
        $('dupe-box').innerHTML = `<div class="cv-dupe-empty">${spinning(t('cv_upload.status_checking'))}</div>`;
        try {
            const r = await fetch('/cv-extractor/api/check-duplicate/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf() },
                body: JSON.stringify({ first_name: fn, last_name: ln })
            });
            showDupe(await r.json(), fn, ln);
        } catch (e) {
            $('dupe-box').innerHTML = `<div style="color:var(--color-text-danger);font-size:.8rem;padding:8px;">${t('cv_upload.err_upload')}: ${esc(e.message)}</div>`;
            $('up-btn').disabled = true;
        }
    }

    function showDupe(data, fn, ln) {
        if (!data.success) {
            $('dupe-box').innerHTML = `<div style="color:var(--color-text-danger);font-size:.8rem;padding:8px;">${esc(data.error)}</div>`;
            $('up-btn').disabled = true; return;
        }
        const persons = data.persons || [];
        allPersons = persons;
        const baseDir = `${ln.toLowerCase()}_${fn.toLowerCase()}`;
        if (!persons.length) {
            $('dupe-box').innerHTML = `
                <div style="background:var(--color-background-success);border-radius:var(--border-radius-md);padding:10px;margin-bottom:8px;font-size:.8rem;color:var(--color-text-success);">
                    ${icon('person-plus')} <strong>${t('cv_upload.new_person_label')}</strong><br>
                    Verzeichnis: <code>${esc(baseDir)}</code><br>Version: <code>1.0.0.0</code>
                </div>
                <button class="cv-btn-primary cv-btn-full" onclick="cvUpload.selectNew('${esc(baseDir)}','new_person')">
                    ${icon('check')} ${t('cv_upload.new_person_btn')}
                </button>`;
            return;
        }
        let html = `<div style="background:var(--color-background-info);border-radius:var(--border-radius-md);padding:8px;margin-bottom:8px;font-size:.78rem;color:var(--color-text-info);">
            ${icon('people')} <strong>${persons.length} ${t('cv_upload.persons_found')}</strong></div>`;
        persons.forEach((p, i) => {
            const nextV = incVersion(p.latest_version);
            html += `<div class="cv-person-card" id="pc-${i}" onclick="cvUpload.selectPerson(${i})">
                <div style="display:flex;justify-content:space-between;align-items:start;">
                    <div><strong>${esc(fn)} ${esc(ln)}</strong><br><code style="font-size:.72rem">${esc(p.directory)}</code></div>
                    <span class="cv-badge cv-badge-wait">v${esc(p.latest_version || '–')}</span>
                </div>
                <button class="cv-btn-primary cv-btn-full" style="margin-top:8px;font-size:.75rem;" onclick="event.stopPropagation();cvUpload.selectPerson(${i})">
                    ${icon('plus-circle')} ${t('cv_upload.new_version_btn', { version: nextV })}
                </button>
            </div>`;
        });
        html += `<div style="margin-top:6px;">
            <button class="cv-btn-secondary cv-btn-full" style="font-size:.75rem;" onclick="cvUpload.selectNew('${esc(baseDir)}-${persons.length + 1}','new_person')">
                ${icon('plus')} ${t('cv_upload.new_namesake_btn')}
            </button>
        </div>`;
        $('dupe-box').innerHTML = html;
        $('up-btn').disabled = true;
    }

    function selectPerson(i) {
        document.querySelectorAll('.cv-person-card').forEach(c => c.classList.remove('sel'));
        document.getElementById(`pc-${i}`)?.classList.add('sel');
        const p = allPersons[i];
        $('sel-dir').value = p.directory;
        $('sel-ver').value = incVersion(p.latest_version);
        $('sel-act').value = 'new_version';
        $('up-btn').disabled = false;
    }

    function selectNew(dir, action) {
        $('sel-dir').value = dir; $('sel-ver').value = '1.0.0.0';
        $('sel-act').value = action; $('up-btn').disabled = false;
        document.querySelectorAll('.cv-person-card').forEach(c => c.classList.remove('sel'));
    }

    // ── File Handling ─────────────────────────────────────────────────
    function handleFile(file) {
        const ext = file.name.toLowerCase().split('.').pop();
        if (!['pdf', 'doc', 'docx'].includes(ext)) { alert(t('cv_upload.err_filetype')); return; }
        selFile = file;
        $('pdf-name').textContent = file.name;
        $('pdf-meta').textContent = fmtBytes(file.size);
        $('pdf-badge').classList.add('show');
        $('up-btn').disabled = true;
        checkDupe();
    }

    // ── Upload ────────────────────────────────────────────────────────
    async function uploadPDF() {
        if (!selFile) return;
        $('up-btn').disabled = true;
        $('up-btn').innerHTML = spinning(t('cv_upload.status_uploading'));
        $('prog').classList.add('show');
        $('prog-bar').style.width = '10%';
        const fd = new FormData();
        fd.append('pdf_file', selFile);
        fd.append('first_name', $('fn').value.trim());
        fd.append('last_name', $('ln').value.trim());
        fd.append('email', $('email').value.trim());
        fd.append('phone', $('phone').value.trim());
        fd.append('website', $('website').value.trim());
        fd.append('address', $('address').value.trim());
        fd.append('target_directory', $('sel-dir').value);
        fd.append('target_version', $('sel-ver').value);
        fd.append('action_type', $('sel-act').value);
        let pct = 10;
        const sim = setInterval(() => { pct = Math.min(pct + 8, 88); $('prog-bar').style.width = pct + '%'; }, 1500);
        try {
            const r = await fetch('/cv-extractor/api/upload/async/', {
                method: 'POST', headers: { 'X-CSRFToken': csrf() }, body: fd
            });
            const d = await r.json();
            clearInterval(sim); $('prog-bar').style.width = '100%';
            if (d.success) {
                $('up-btn').innerHTML = `${icon('check')} ${t('cv_upload.status_uploaded')}`;
                $('rst-btn').style.display = 'inline-flex';
                $('pdf-meta').textContent = t('cv_upload.status_processing');
                loadUploads(); startPolling(d.upload_id);
            } else { throw new Error(d.error || t('cv_upload.err_upload')); }
        } catch (e) {
            clearInterval(sim);
            alert(`${t('cv_upload.err_upload')}: ${e.message}`);
            $('up-btn').disabled = false;
            $('up-btn').innerHTML = `${icon('upload')} <span data-i18n="cv_upload.btn_upload">${t('cv_upload.btn_upload')}</span>`;
            $('prog').classList.remove('show');
        }
    }

    function resetUpload() {
        selFile = null; allPersons = [];
        ['fn', 'ln', 'email', 'phone', 'website', 'address', 'sel-dir', 'sel-ver', 'sel-act'].forEach(id => { $(id) && ($(id).value = ''); });
        $('fi').value = '';
        $('pdf-badge').classList.remove('show');
        $('pdf-name').textContent = '';
        $('pdf-meta').textContent = '';
        $('prog').classList.remove('show');
        $('prog-bar').style.width = '0%';
        $('up-btn').disabled = true;
        $('up-btn').innerHTML = `${icon('upload')} <span data-i18n="cv_upload.btn_upload">${t('cv_upload.btn_upload')}</span>`;
        $('rst-btn').style.display = 'none';
        $('dupe-box').innerHTML = `<div class="cv-dupe-empty">${icon('info-circle')}<p data-i18n="cv_upload.dupe_hint">${t('cv_upload.dupe_hint')}</p></div>`;
    }

    function startPolling(uploadId) {
        clearInterval(pollTimer);
        pollTimer = setInterval(async () => {
            try {
                const r = await fetch(`/cv-extractor/api/upload/${uploadId}/status/`);
                const d = await r.json();
                if (d.success && (d.status === 'completed' || d.status === 'failed')) {
                    clearInterval(pollTimer); loadUploads();
                    if (d.status === 'completed' && d.aid) {
                        $('pdf-meta').innerHTML = `✓ ${t('cv_upload.status_done')} – <a href="/cv-extractor/editor/${d.aid}/" target="_blank" style="color:var(--accent-color)">${t('cv_upload.editor_open')}</a>`;
                    }
                } else { loadUploads(); }
            } catch (e) {}
        }, 3000);
    }

    // ── Tabelle ───────────────────────────────────────────────────────
    async function loadUploads() {
        try {
            const r = await fetch('/cv-extractor/api/uploads/?limit=100');
            const d = await r.json();
            if (d.success) { uploads = d.uploads || []; renderTable(); }
        } catch (e) {}
    }

    function renderTable() {
        const term = ($('search').value || '').toLowerCase();
        const sort = $('sort').value;
        let rows = uploads.filter(u => !term ||
            (u.last_name || '').toLowerCase().includes(term) ||
            (u.first_name || '').toLowerCase().includes(term) ||
            (u.aid || '').toLowerCase().includes(term) ||
            (u.status || '').toLowerCase().includes(term));
        rows.sort((a, b) => {
            if (sort === 'newest') return new Date(b.created_at) - new Date(a.created_at);
            if (sort === 'oldest') return new Date(a.created_at) - new Date(b.created_at);
            if (sort === 'ln_asc') return (a.last_name || '').localeCompare(b.last_name || '');
            if (sort === 'ln_desc') return (b.last_name || '').localeCompare(a.last_name || '');
            if (sort === 'status') return (a.status || '').localeCompare(b.status || '');
            return 0;
        });
        const sm = {
            completed:     { dot: 'cv-dot-ok',   badge: 'cv-badge-ok',   label: t('cv_upload.status_done') },
            profile_ready: { dot: 'cv-dot-ok',   badge: 'cv-badge-ok',   label: t('cv_upload.status_done') },
            processing:    { dot: 'cv-dot-proc',  badge: 'cv-badge-proc', label: t('cv_upload.status_pipeline') },
            failed:        { dot: 'cv-dot-fail',  badge: 'cv-badge-fail', label: t('cv_upload.err_upload') },
            uploaded:      { dot: 'cv-dot-wait',  badge: 'cv-badge-wait', label: t('cv_upload.status_loading') },
        };
        if (!rows.length) {
            $('tbl-body').innerHTML = `<tr><td colspan="9" class="cv-tbl-loading">${t('cv_upload.status_no_entries')}</td></tr>`;
            return;
        }
        $('tbl-body').innerHTML = rows.map(u => {
            const s = sm[u.status] || sm.uploaded;
            const editDisabled = !u.aid ? 'disabled' : '';
            const editClick = u.editor_url ? `onclick="window.open('${esc(u.editor_url)}','_blank')"` : '';
            return `<tr>
                <td><strong>${esc(u.last_name || '–')}</strong></td>
                <td>${esc(u.first_name || '–')}</td>
                <td><code style="font-size:.75rem">${esc(u.aid || '–')}</code></td>
                <td>${esc(u.version || '–')}</td>
                <td><span class="cv-dot ${s.dot}"></span><span class="cv-badge ${s.badge}">${s.label}</span>${u.error_message ? `<br><small style="color:var(--color-text-danger)">${esc(u.error_message.substring(0, 60))}</small>` : ''}</td>
                <td style="font-size:.75rem;color:var(--text-secondary)">${fmtDate(u.created_at)}</td>
                <td>${u.action_type === 'new_version' ? '<span class="cv-update-badge">↑ Update</span>' : ''}</td>
                <td style="text-align:center">${u.aid ? `<span class="cv-valid-circle ${u.pipeline_step === 'validated' ? 'cv-valid-ok' : 'cv-valid-fail'}">${u.pipeline_step === 'validated' ? '✓' : '✗'}</span>` : '–'}</td>
                <td><div class="cv-tbl-actions">
                    <button class="cv-btn-edit" ${editDisabled} ${editClick}>${icon('pencil-square')} ${t('cv_upload.col_actions')}</button>
                    ${u.aid ? `<button class="cv-btn-delete" onclick="cvUpload.deleteConsultant('${esc(u.aid)}','${esc(u.first_name)} ${esc(u.last_name)}')">${icon('trash')}</button>` : ''}
                </div></td>
            </tr>`;
        }).join('');
    }

    async function deleteConsultant(aid, name) {
        const cn = prompt(t('cv_upload.confirm_delete', { name, aid }));
        if (!cn) return;
        const r = await fetch(`/cv-extractor/api/cv-editor/${aid}/delete/`, {
            method: 'DELETE',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf() },
            body: JSON.stringify({ confirm_name: cn })
        });
        const d = await r.json();
        if (d.success) { alert(`✓ ${name} ${t('cv_upload.delete_success')}`); loadUploads(); }
        else alert(`${t('cv_upload.err_delete')}: ` + (d.error || d.detail || JSON.stringify(d)));
    }

    // ── Session ───────────────────────────────────────────────────────
    async function checkSessionStatus(platform) {
        try {
            const apiUrl = platform === 'gu' ? '/cv-extractor/api/gu-session/' : '/cv-extractor/api/flm-session/';
            const r = await fetch(apiUrl);
            const d = await r.json();
            const btn = $('flm-session-btn');
            if (btn) {
                if (d.has_session) { btn.title = t('cv_upload.session_active'); }
                else { btn.title = '…'; await autoRenewSession(btn, platform); }
            }
            return d;
        } catch (e) { return null; }
    }

    async function autoRenewSession(btn, platform) {
        if (typeof chrome === 'undefined' || !chrome.runtime) {
            setSessionError(btn, `ERROR 1: ${t('cv_upload.session_error_ext')}`, ''); return;
        }
        let res;
        try {
            res = await new Promise((resolve, reject) => {
                chrome.runtime.sendMessage(EXTENSION_ID, { action: 'getCookies' }, r => {
                    if (chrome.runtime.lastError) return reject(new Error(chrome.runtime.lastError.message));
                    resolve(r);
                });
            });
        } catch (e) { setSessionError(btn, `ERROR 1: ${e.message}`, ''); return; }
        if (!res) { setSessionError(btn, `ERROR 2: ${t('cv_upload.session_error_no_answer')}`, ''); return; }
        if (!res.success && res.error && res.error.includes('PHPSESSID')) { setSessionError(btn, `ERROR 2: ${t('cv_upload.session_error_cookies')}`, ''); return; }
        if (!res.success) { setSessionError(btn, `ERROR 3: ${t('cv_upload.session_error_failed')}`, ''); return; }
        btn.title = t('cv_upload.session_active');
    }

    function setSessionError(btn, debugMsg, adminMsg) {
        if (!btn) return;
        btn.setAttribute('data-error', debugMsg);
        btn.setAttribute('data-admin', adminMsg);
    }

    async function handleSessionBtn() {
        const sel = $('url-platform');
        const platform = sel ? sel.value : 'fl';
        const d = await checkSessionStatus(platform);
        openSessionModal(d, platform);
    }

    async function openSessionModal(d = null, platform = 'fl') {
        const apiUrl = platform === 'gu' ? '/cv-extractor/api/gu-session/' : '/cv-extractor/api/flm-session/';
        if (!d) { try { const r = await fetch(apiUrl); d = await r.json(); } catch (e) { d = { has_session: false }; } }
        $('flm-modal').style.display = 'flex';
        const status = $('flm-status'), action = $('flm-action');
        if (d.has_session) {
            status.innerHTML = `<div style="background:var(--color-background-success);border-radius:var(--border-radius-md);padding:12px;color:var(--color-text-success);font-size:.83rem;">${icon('check-circle')} <strong>${t('cv_upload.session_active')}</strong> — ${d.cookie_count} ${t('cv_upload.session_cookies')}${d.has_remember ? ` (${t('cv_upload.session_remember')} ✓)` : ''}<br><small>${t('cv_upload.session_saved')}: ${d.saved_at ? new Date(d.saved_at).toLocaleString() : '?'}</small></div>`;
            action.style.display = 'none';
        } else {
            const btn = $('flm-session-btn');
            const errorMsg = btn ? btn.getAttribute('data-error') : null;
            const adminMsg = btn ? btn.getAttribute('data-admin') : null;
            status.innerHTML = `<div style="background:var(--color-background-danger);border-radius:var(--border-radius-md);padding:12px;color:var(--color-text-danger);font-size:.83rem;">${icon('x-circle')} <strong>${t('cv_upload.session_inactive')}</strong></div>${errorMsg ? `<div style="background:var(--color-background-warning);border-radius:var(--border-radius-md);padding:10px;color:var(--color-text-warning);font-size:.8rem;margin-top:8px;">${errorMsg}</div>` : ''}${adminMsg ? `<div style="font-size:.75rem;color:var(--text-secondary);padding:8px;margin-top:6px;">${adminMsg}</div>` : ''}`;
            action.style.display = 'block';
        }
    }

    async function callExtensionFromModal() {
        const btn = $('flm-ext-btn'), result = $('flm-ext-result');
        btn.disabled = true;
        btn.innerHTML = spinning(t('cv_upload.status_extension'));
        result.innerHTML = '';
        try {
            const res = await new Promise((resolve, reject) => {
                if (typeof chrome === 'undefined' || !chrome.runtime) return reject(new Error(t('cv_upload.session_error_ext')));
                chrome.runtime.sendMessage(EXTENSION_ID, { action: 'getCookies' }, r => {
                    if (chrome.runtime.lastError) return reject(new Error(chrome.runtime.lastError.message));
                    resolve(r);
                });
            });
            if (res && res.success) {
                result.innerHTML = `<span style="color:var(--color-text-success)">${icon('check')} ${t('cv_upload.status_success')}</span>`;
                await checkSessionStatus();
                setTimeout(() => closeSessionModal(), 1500);
            } else {
                result.innerHTML = `<span style="color:var(--color-text-danger)">${icon('x')} ${res ? res.error : t('cv_upload.err_upload')}</span><br><small>${t('cv_upload.contact_admin')}</small>`;
            }
        } catch (e) {
            result.innerHTML = `<span style="color:var(--color-text-danger)">${icon('x')} ${e.message}</span><br><small>${t('cv_upload.contact_admin')}</small>`;
        }
        btn.disabled = false;
        btn.innerHTML = `${icon('arrow-clockwise')} <span data-i18n="cv_upload.session_renew">${t('cv_upload.session_renew')}</span>`;
    }

    function closeSessionModal(e) {
        if (e && e.target !== $('flm-modal')) return;
        $('flm-modal').style.display = 'none';
    }

    // ── Name-Missing Modal ────────────────────────────────────────────
    function showNameMissingPopup(d, platform, resEl) {
        _nmData = d; _nmPlatform = platform; _nmRes = resEl; _nmFormOpen = false;
        const sub = $('nm-subtitle');
        if (sub) sub.textContent = d.fl_id ? `freelancermap ID: ${d.fl_id}` : `GULP ID: ${d.gulp_id || '–'}`;
        $('nm-dir-preview').textContent = d.provisional_dir || d.hash_id;
        $('nm-form-wrap').style.display = 'none';
        $('nm-name-preview').style.display = 'none';
        $('nm-first').value = ''; $('nm-last').value = '';
        $('nm-confirm-btn').disabled = true;
        $('nm-confirm-btn').style.opacity = '.4';
        $('name-missing-modal').style.display = 'flex';
    }

    function nmToggleForm() {
        _nmFormOpen = !_nmFormOpen;
        $('nm-form-wrap').style.display = _nmFormOpen ? 'block' : 'none';
        $('nm-toggle-btn').innerHTML = _nmFormOpen
            ? `${icon('x')} ${t('cv_upload.name_no_name')}`
            : `${icon('pencil')} ${t('cv_upload.name_enter')}`;
        if (_nmFormOpen) $('nm-first').focus();
        if (!_nmFormOpen) { $('nm-name-preview').style.display = 'none'; $('nm-confirm-btn').disabled = true; $('nm-confirm-btn').style.opacity = '.4'; }
    }

    function nmUpdatePreview() {
        const f = $('nm-first').value.trim(), l = $('nm-last').value.trim();
        const prev = $('nm-name-preview'), prevText = $('nm-name-preview-text'), btn = $('nm-confirm-btn');
        if (f && l) {
            prevText.textContent = l.toLowerCase() + '_' + f.toLowerCase();
            prev.style.display = 'block'; btn.disabled = false; btn.style.opacity = '1';
        } else {
            prev.style.display = 'none'; btn.disabled = true; btn.style.opacity = '.4';
        }
    }

    async function nmSaveAnonymous() {
        $('name-missing-modal').style.display = 'none';
        await nmRunPipeline(_nmData.provisional_dir, '', '');
    }

    async function nmSaveWithName() {
        const f = $('nm-first').value.trim(), l = $('nm-last').value.trim();
        if (!f || !l) return;
        $('name-missing-modal').style.display = 'none';
        await nmRunPipeline(_nmData.provisional_dir, f, l, l.toLowerCase() + '_' + f.toLowerCase());
    }

    async function nmRunPipeline(dirName, firstName, lastName, newDirName) {
        if (!_nmRes) return;
        _nmRes.style.display = 'block';
        _nmRes.innerHTML = spinning(t('cv_upload.status_fetching'));
        const targetDir = newDirName || dirName;
        try {
            const importRes = await fetch('/cv-extractor/api/import-url/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf() },
                body: JSON.stringify({ url: _nmData.url, platform: _nmPlatform, cookies: {}, force_dir: targetDir, first_name: firstName, last_name: lastName })
            });
            const importData = await importRes.json();
            if (!importData.success && !importData.name_missing) {
                _nmRes.innerHTML = `<div style="color:var(--color-text-danger)">${icon('x-circle')} ${importData.error || t('cv_upload.err_import')}</div>`; return;
            }
            if (importData.dir) dirName = importData.dir.split('/').pop();
            else dirName = targetDir;
        } catch (e) { _nmRes.innerHTML = `<div style="color:var(--color-text-danger)">${icon('x-circle')} ${e.message}</div>`; return; }
        _nmRes.innerHTML = spinning(t('cv_upload.status_pipeline'));
        try {
            const dbRes = await fetch('/cv-extractor/api/import-url-to-db/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf() },
                body: JSON.stringify({ dir_name: dirName, platform: _nmPlatform, first_name: firstName, last_name: lastName })
            });
            const dbData = await dbRes.json();
            if (dbData.success) {
                _nmRes.innerHTML = `<div style="display:flex;gap:8px;align-items:start;">${icon('check-circle')} <div><strong>${firstName ? firstName + ' ' + lastName : dirName}</strong><br><small style="color:var(--text-secondary)">${icon('folder')} ${dirName}</small>${dbData.editor_url ? `<a href="${dbData.editor_url}" target="_blank" style="margin-left:8px;color:var(--accent-color);font-size:.75rem;">${icon('pencil-square')} ${t('cv_upload.editor_open')}</a>` : ''}</div></div>`;
            } else {
                _nmRes.innerHTML = `<div style="color:var(--color-text-danger)">${icon('x-circle')} ${dbData.error || t('cv_upload.err_upload')}</div>`;
            }
        } catch (e) { _nmRes.innerHTML = `<div style="color:var(--color-text-danger)">${icon('x-circle')} ${e.message}</div>`; }
        loadUploads();
        if (firstName && lastName) { const fn = $('fn'), ln = $('ln'); if (fn) fn.value = firstName; if (ln) ln.value = lastName; }
    }

    function closeNameModal(e) {
        if (e && e.target !== $('name-missing-modal')) return;
        $('name-missing-modal').style.display = 'none';
    }

    // ── Init ──────────────────────────────────────────────────────────
    function init() {
        const dz = $('dz'), fi = $('fi');
        if (dz) {
            dz.addEventListener('click', () => fi.click());
            dz.addEventListener('dragover', e => { e.preventDefault(); dz.classList.add('over'); });
            dz.addEventListener('dragleave', () => dz.classList.remove('over'));
            dz.addEventListener('drop', e => { e.preventDefault(); dz.classList.remove('over'); if (e.dataTransfer.files[0]) handleFile(e.dataTransfer.files[0]); });
        }
        if (fi) fi.addEventListener('change', e => { if (e.target.files[0]) handleFile(e.target.files[0]); });
        const fnEl = $('fn'), lnEl = $('ln');
        if (fnEl) fnEl.addEventListener('input', triggerDupe);
        if (lnEl) lnEl.addEventListener('input', triggerDupe);
        const upBtn = $('up-btn'); if (upBtn) upBtn.addEventListener('click', uploadPDF);
        const rstBtn = $('rst-btn'); if (rstBtn) rstBtn.addEventListener('click', resetUpload);
        const searchEl = $('search'); if (searchEl) searchEl.addEventListener('input', renderTable);
        const sortEl = $('sort'); if (sortEl) sortEl.addEventListener('change', renderTable);
        loadPlatforms();
        loadUploads();
        setInterval(loadUploads, 30000);
    }

    return {
        init, autoDetectPlatform, toggleBatch, handleCsvDrop, loadUrlFile,
        updateBatchCount, importSingleUrl, importBatch,
        selectPerson, selectNew, loadUploads, deleteConsultant,
        handleSessionBtn, closeSessionModal, callExtensionFromModal,
        showNameMissingPopup, nmToggleForm, nmUpdatePreview,
        nmSaveAnonymous, nmSaveWithName, closeNameModal,
    };

})();
