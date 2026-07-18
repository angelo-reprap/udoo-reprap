/**
 * es-ki-wizard.js — KI-Vorlagen-Assistent (Email Studio Phase 2)
 * API: /ki-wizard/api/…  |  i18n: window.i18nData.es.*
 * Getrennt von es-studio.js — übergibt Ergebnis via sessionStorage + ESStudio.applyWizardResult
 */
'use strict';

window.ESKiWizard = (() => {

    const API = '/ki-wizard/api';
    const STORAGE_KEY = 'es_ki_wizard_apply';

    let _step = 'briefing';
    let _sessionId = null;
    let _questions = [];
    let _answers = {};
    let _meta = {};
    let _generated = null;
    let _busy = false;

    function t(key, fallback) {
        return window.i18nData?.es?.[key] || fallback || key;
    }

    function _csrf() {
        return (typeof ES !== 'undefined' && ES.csrf) ? ES.csrf() : '';
    }

    async function _api(method, path, body) {
        const opts = {
            method,
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': _csrf(),
            },
        };
        if (body !== undefined) opts.body = JSON.stringify(body);
        const r = await fetch(`${API}${path}`, opts);
        const data = await r.json().catch(() => ({}));
        if (!r.ok) {
            const msg = data.error || `HTTP ${r.status}`;
            throw new Error(msg);
        }
        return data;
    }

    function _setBusy(on) {
        _busy = on;
        const el = document.getElementById('es-ki-loading');
        if (el) el.style.display = on ? 'flex' : 'none';
        const btn = document.getElementById('es-ki-btn-next');
        if (btn) btn.disabled = on;
    }

    function _showError(msg) {
        const el = document.getElementById('es-ki-error');
        if (!el) return;
        el.textContent = msg || t('ki_error', 'Fehler');
        el.style.display = msg ? 'block' : 'none';
    }

    function _setStep(step) {
        _step = step;
        document.querySelectorAll('.es-ki-panel').forEach(p => p.classList.remove('active'));
        document.getElementById(`es-ki-panel-${step}`)?.classList.add('active');
        document.querySelectorAll('.es-ki-step').forEach(s => {
            s.classList.toggle('active', s.dataset.step === step);
            s.classList.toggle('done', _stepOrder(s.dataset.step) < _stepOrder(step));
        });
        const backBtn = document.getElementById('es-ki-btn-back');
        const nextBtn = document.getElementById('es-ki-btn-next');
        if (backBtn) backBtn.style.display = step === 'briefing' ? 'none' : '';
        if (nextBtn) {
            const labels = {
                briefing: t('ki_btn_start', 'Analysieren'),
                clarify: t('ki_btn_continue', 'Weiter'),
                meta: t('ki_btn_generate', 'Generieren'),
                preview: t('ki_btn_apply', 'In Editor übernehmen'),
            };
            nextBtn.querySelector('span').textContent = labels[step] || t('ki_btn_next', 'Weiter');
        }
    }

    function _stepOrder(s) {
        return ['briefing', 'clarify', 'meta', 'preview'].indexOf(s);
    }

    function _questionVisible(q, answers) {
        const showIf = q.show_if || {};
        for (const [key, allowed] of Object.entries(showIf)) {
            const val = answers[key];
            if (Array.isArray(allowed)) {
                if (!allowed.includes(val)) return false;
            } else if (val !== allowed) {
                return false;
            }
        }
        return true;
    }

    function _collectAnswersFromDom() {
        const multi = {};
        document.querySelectorAll('[data-ki-qid]').forEach(el => {
            const qid = el.dataset.kiQid;
            if (el.type === 'checkbox') {
                if (!multi[qid]) multi[qid] = [];
                if (el.checked) multi[qid].push(el.value);
            } else if (el.tagName === 'SELECT') {
                _answers[qid] = el.value;
            } else if (el.type === 'radio' && el.checked) {
                _answers[qid] = el.value;
            }
        });
        Object.assign(_answers, multi);
    }

    function _renderQuestions() {
        const box = document.getElementById('es-ki-questions');
        if (!box) return;
        box.innerHTML = '';
        _questions.filter(q => _questionVisible(q, _answers)).forEach(q => {
            const wrap = document.createElement('div');
            wrap.className = 'es-ki-q-block';
            const lbl = document.createElement('label');
            lbl.className = 'es-ki-lbl';
            lbl.textContent = q.question || q.id;
            wrap.appendChild(lbl);

            if (q.type === 'multiselect') {
                (q.options || []).forEach(opt => {
                    const row = document.createElement('label');
                    row.className = 'es-ki-check-row';
                    const inp = document.createElement('input');
                    inp.type = 'checkbox';
                    inp.dataset.kiQid = q.id;
                    inp.value = opt.value;
                    if ((_answers[q.id] || []).includes(opt.value)) inp.checked = true;
                    row.appendChild(inp);
                    row.appendChild(document.createTextNode(' ' + (opt.label || opt.value)));
                    wrap.appendChild(row);
                });
            } else {
                const sel = document.createElement('select');
                sel.className = 'form-select form-select-sm';
                sel.dataset.kiQid = q.id;
                (q.options || []).forEach(opt => {
                    const o = document.createElement('option');
                    o.value = opt.value;
                    o.textContent = opt.label || opt.value;
                    if (_answers[q.id] === opt.value) o.selected = true;
                    sel.appendChild(o);
                });
                wrap.appendChild(sel);
            }
            box.appendChild(wrap);
        });
    }

    function _fillMetaFields(suggestions) {
        const s = suggestions || {};
        const set = (id, v) => { const el = document.getElementById(id); if (el && v != null) el.value = v; };
        set('es-ki-meta-name', s.name);
        set('es-ki-meta-identifier', s.identifier);
        set('es-ki-meta-subject', s.subject);
        set('es-ki-meta-scope', s.app_scope || 'telefon');
        set('es-ki-meta-status', s.status || 'DRAFT');
        _meta = { ...s };
    }

    function _readMetaFields() {
        _meta = {
            ..._meta,
            name: document.getElementById('es-ki-meta-name')?.value?.trim() || '',
            identifier: document.getElementById('es-ki-meta-identifier')?.value?.trim() || '',
            subject: document.getElementById('es-ki-meta-subject')?.value?.trim() || '',
            app_scope: document.getElementById('es-ki-meta-scope')?.value || 'general',
            status: document.getElementById('es-ki-meta-status')?.value || 'DRAFT',
            sender_mode: _meta.sender_mode || _answers.A1 || 'USER',
            signature_mode: _meta.signature_mode || _answers.G1 || 'USER',
        };
    }

    function _showPreview() {
        const subj = document.getElementById('es-ki-preview-subject');
        const html = document.getElementById('es-ki-preview-html');
        const src = document.getElementById('es-ki-preview-source');
        if (subj) subj.textContent = _meta.subject || '';
        if (html) html.innerHTML = _generated?.html_body || '';
        if (src) {
            src.textContent = t('ki_source_label', 'Quelle') + ': ' + (_generated?.source || 'ai');
        }
    }

    function _reset() {
        _sessionId = null;
        _questions = [];
        _answers = {};
        _meta = {};
        _generated = null;
        _showError('');
        const briefing = document.getElementById('es-ki-briefing');
        if (briefing) briefing.value = '';
        _setStep('briefing');
    }

    async function _runBriefing() {
        const text = document.getElementById('es-ki-briefing')?.value?.trim();
        if (!text || text.length < 10) {
            _showError(t('ki_briefing_short', 'Bitte ausführlicher beschreiben (mind. 10 Zeichen).'));
            return;
        }
        _showError('');
        _setBusy(true);
        try {
            const created = await _api('POST', '/wizards/email_template/session/', { briefing: text });
            _sessionId = created.session_id;
            const analyzed = await _api('POST', `/session/${_sessionId}/analyze/`);
            _questions = analyzed.questions || [];
            _renderQuestions();
            _setStep('clarify');
        } catch (e) {
            _showError(e.message);
        } finally {
            _setBusy(false);
        }
    }

    async function _runClarify() {
        _collectAnswersFromDom();
        _setBusy(true);
        try {
            const res = await _api('POST', `/session/${_sessionId}/clarify/`, { answers: _answers });
            if (!res.complete) {
                _questions = res.questions || [];
                _renderQuestions();
                _showError(t('ki_clarify_more', 'Bitte alle Pflichtfragen beantworten.'));
                return;
            }
            _showError('');
            const metaRes = await _api('POST', `/session/${_sessionId}/suggest-meta/`);
            _fillMetaFields(metaRes.suggestions || {});
            _setStep('meta');
        } catch (e) {
            _showError(e.message);
        } finally {
            _setBusy(false);
        }
    }

    async function _runGenerate(refinement) {
        _readMetaFields();
        _setBusy(true);
        try {
            const body = refinement ? { refinement } : undefined;
            const gen = await _api('POST', `/session/${_sessionId}/generate/`, body);
            _generated = gen.generated || {};
            _showPreview();
            _setStep('preview');
        } catch (e) {
            _showError(e.message);
        } finally {
            _setBusy(false);
        }
    }

    async function refine() {
        const notes = document.getElementById('es-ki-refine-notes')?.value?.trim();
        if (!notes) {
            _showError(t('ki_refine_empty', 'Bitte kurz beschreiben, was geändert werden soll.'));
            return;
        }
        _showError('');
        await _runGenerate(notes);
    }

    function openRefine() {
        const name = document.getElementById('es-name-input')?.value?.trim() || '';
        const subject = document.getElementById('es-subject-input')?.value?.trim() || '';
        const html = document.getElementById('es-html-editor')?.value?.trim() || '';
        open();
        const briefing = document.getElementById('es-ki-briefing');
        if (briefing) {
            briefing.value = [
                t('ki_refine_intro', 'Bestehende Vorlage verfeinern:'),
                name ? `Name: ${name}` : '',
                subject ? `Betreff: ${subject}` : '',
                html ? `\nAktueller Inhalt (Auszug):\n${html.slice(0, 800)}` : '',
                `\n${t('ki_refine_wish', 'Gewünschte Anpassung:')}\n`,
            ].filter(Boolean).join('\n');
        }
    }

    function _runApply() {
        _readMetaFields();
        const fields = {
            name: _meta.name,
            identifier: _meta.identifier,
            subject: _meta.subject,
            description: _meta.description || document.getElementById('es-ki-briefing')?.value || '',
            app_scope: _meta.app_scope,
            event_type: _meta.event_type || 'general',
            sender_mode: _meta.sender_mode || 'USER',
            signature_mode: _meta.signature_mode || 'USER',
            status: _meta.status || 'DRAFT',
            html_body: _generated?.html_body || '',
            text_body: _generated?.text_body || '',
        };
        sessionStorage.setItem(STORAGE_KEY, JSON.stringify(fields));
        close();
        window.location.href = '/email-studio/studio/?new=blank&from_ki=1';
    }

    function open() {
        const modal = document.getElementById('es-ki-wizard-modal');
        if (!modal) return;
        _reset();
        modal.classList.add('show');
        modal.setAttribute('aria-hidden', 'false');
        document.getElementById('es-ki-briefing')?.focus();
    }

    function close() {
        const modal = document.getElementById('es-ki-wizard-modal');
        if (!modal) return;
        modal.classList.remove('show');
        modal.setAttribute('aria-hidden', 'true');
    }

    function back() {
        _showError('');
        const order = ['briefing', 'clarify', 'meta', 'preview'];
        const idx = order.indexOf(_step);
        if (idx > 0) _setStep(order[idx - 1]);
    }

    async function next() {
        if (_busy) return;
        if (_step === 'briefing') return _runBriefing();
        if (_step === 'clarify') return _runClarify();
        if (_step === 'meta') return _runGenerate('');
        if (_step === 'preview') return _runApply();
    }

    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') close();
    });

    return { open, close, back, next, refine, openRefine, STORAGE_KEY };

})();
