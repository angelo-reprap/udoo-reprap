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
    let _refineMode = false;

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
        set('es-ki-meta-scope', s.app_scope || 'general');
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
            let label = t('ki_source_label', 'Quelle') + ': ' + (_generated?.source || 'ai');
            if (_generated?.ai_error) {
                label += ' — ' + _generated.ai_error;
            }
            src.textContent = label;
        }
        _renderLayoutSuggestions(_generated?.layout_suggestions || []);
        const warn = document.getElementById('es-ki-preview-warn');
        if (warn) {
            const msg = _generated?.ai_error || '';
            warn.textContent = msg;
            warn.style.display = msg ? 'block' : 'none';
        }
    }

    function _renderLayoutSuggestions(items) {
        const wrap = document.getElementById('es-ki-layout-suggestions');
        const list = document.getElementById('es-ki-layout-suggestions-list');
        if (!wrap || !list) return;
        list.innerHTML = '';
        if (!items || !items.length) {
            wrap.style.display = 'none';
            return;
        }
        wrap.style.display = 'block';
        items.forEach((s, idx) => {
            const row = document.createElement('div');
            row.className = 'es-ki-suggest-row';
            const q = document.createElement('div');
            q.className = 'es-ki-suggest-q';
            q.textContent = s.question || s.name || s.id || '';
            row.appendChild(q);
            if (s.description) {
                const d = document.createElement('div');
                d.className = 'es-ki-hint';
                d.textContent = s.description;
                row.appendChild(d);
            }
            const actions = document.createElement('div');
            actions.className = 'es-ki-suggest-actions';
            const yes = document.createElement('button');
            yes.type = 'button';
            yes.className = 'btn btn-sm btn-outline-primary';
            yes.textContent = t('ki_suggest_yes', 'Ja, übernehmen');
            yes.addEventListener('click', () => _applyLayoutSuggestion(s));
            const no = document.createElement('button');
            no.type = 'button';
            no.className = 'btn btn-sm btn-outline-secondary';
            no.textContent = t('ki_suggest_no', 'Nein');
            no.addEventListener('click', () => {
                row.remove();
                if (!list.children.length) wrap.style.display = 'none';
            });
            actions.appendChild(yes);
            actions.appendChild(no);
            row.appendChild(actions);
            list.appendChild(row);
        });
    }

    function _applyLayoutSuggestion(s) {
        const syntax = (s && s.syntax) || '';
        const notes = document.getElementById('es-ki-refine-notes');
        if (!notes) return;
        const tip = syntax
            ? t('ki_suggest_refine', 'Bitte Block einfügen:') + ' ' + syntax
            : (s.question || s.name || '');
        notes.value = (notes.value ? notes.value + '\n' : '') + tip;
        // Direkt in HTML einfügen wenn Syntax bekannt und noch nicht vorhanden
        if (syntax && _generated && _generated.html_body != null) {
            const token = syntax.split('\n')[0];
            if (token && !_generated.html_body.includes(token)) {
                const close = '{{block:signature}}';
                const body = _generated.html_body;
                if (body.includes(close)) {
                    _generated.html_body = body.replace(close, syntax + '\n' + close);
                } else {
                    _generated.html_body = body + '\n' + syntax;
                }
                const html = document.getElementById('es-ki-preview-html');
                if (html) html.innerHTML = _generated.html_body;
            }
        }
    }

    function _reset() {
        _sessionId = null;
        _questions = [];
        _answers = {};
        _meta = {};
        _generated = null;
        _refineMode = false;
        _showError('');
        const briefing = document.getElementById('es-ki-briefing');
        if (briefing) briefing.value = '';
        const refineNotes = document.getElementById('es-ki-refine-notes');
        if (refineNotes) refineNotes.value = '';
        const title = document.getElementById('es-ki-wizard-title');
        if (title) title.textContent = t('ki_title', 'KI-Vorlage generieren');
        _setStep('briefing');
    }

    function _syncFromEditorIfRefine() {
        if (!_refineMode) return;
        const fields = _collectEditorFields();
        _meta = {
            ..._meta,
            name: fields.name || _meta.name,
            identifier: fields.identifier || _meta.identifier,
            subject: fields.subject || _meta.subject,
            app_scope: fields.app_scope || _meta.app_scope,
            sender_mode: fields.sender_mode || _meta.sender_mode,
            signature_mode: fields.signature_mode || _meta.signature_mode,
            event_type: _meta.event_type || 'info',
            status: _meta.status || 'DRAFT',
        };
        // Editor-HTML nur als Basis, solange noch kein KI-Ergebnis da ist.
        // Sonst würde „Übernehmen“ / erneutes Verfeinern das KI-Ergebnis verwerfen.
        const src = (_generated && _generated.source) || '';
        const hasAiResult = !!(
            _generated
            && _generated.html_body
            && src
            && src !== 'editor'
        );
        if (!hasAiResult && fields.html_body) {
            _generated = {
                ...(_generated || {}),
                html_body: fields.html_body,
                text_body: fields.text_body || fields.html_body,
                source: 'editor',
            };
        }
    }

    function _updatePreviewFooterForRefine() {
        const nextBtn = document.getElementById('es-ki-btn-next');
        if (nextBtn && _refineMode) {
            nextBtn.querySelector('span').textContent = t(
                'ki_refine_apply',
                'Verfeinertes Ergebnis übernehmen',
            );
        }
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
            const analyze = analyzed.analyze || {};
            if (analyze.app_scope) _answers.S1 = analyze.app_scope;
            if (analyze.event_type) _answers.S2 = analyze.event_type;
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
        _syncFromEditorIfRefine();
        _readMetaFields();
        _setBusy(true);
        try {
            const body = {
                meta: _meta,
                html_body: _generated?.html_body || '',
                text_body: _generated?.text_body || '',
            };
            if (refinement) body.refinement = refinement;
            const gen = await _api('POST', `/session/${_sessionId}/generate/`, body);
            _generated = gen.generated || {};
            if (gen.generated?.ai_error) {
                _generated.ai_error = gen.generated.ai_error;
            }
            // Antwort-JSON nie im Body belassen (Fallback falls Backend alt)
            if (_generated.html_body) {
                _generated.html_body = _stripAnswerJson(_generated.html_body);
            }
            if (_generated.text_body) {
                _generated.text_body = _stripAnswerJson(_generated.text_body);
            }
            _showPreview();
            _setStep('preview');
            _updatePreviewFooterForRefine();
        } catch (e) {
            _showError(e.message);
        } finally {
            _setBusy(false);
        }
    }

    async function refine() {
        if (!_sessionId) {
            _showError(t('ki_refine_no_session', 'Keine Session — bitte zuerst Vorlage generieren.'));
            return;
        }
        const notes = document.getElementById('es-ki-refine-notes')?.value?.trim();
        if (!notes) {
            _showError(t('ki_refine_empty', 'Bitte kurz beschreiben, was geändert werden soll.'));
            return;
        }
        _showError('');
        await _runGenerate(notes);
    }

    function _collectEditorFields() {
        if (window.ESStudio?._syncCanvasToCode) {
            ESStudio._syncCanvasToCode();
        }
        return {
            name: document.getElementById('es-name-input')?.value?.trim() || '',
            identifier: document.getElementById('es-identifier-input')?.value?.trim() || '',
            subject: document.getElementById('es-subject-input')?.value?.trim() || '',
            html_body: document.getElementById('es-html-editor')?.value?.trim() || '',
            text_body: document.getElementById('es-txt-editor')?.value?.trim() || '',
            app_scope: document.querySelector('select[name="app_scope"]')?.value || 'general',
            sender_mode: document.querySelector('.es-mode-btn.active')?.dataset.mode || 'USER',
            signature_mode: document.querySelector('input[name="es-sig-mode"]:checked')?.value || 'USER',
        };
    }

    async function openRefine() {
        const fields = _collectEditorFields();
        if (!fields.html_body && !fields.subject) {
            alert(t('ki_refine_no_content', 'Kein Inhalt im Editor zum Verfeinern.'));
            return;
        }

        _refineMode = true;
        _showError('');
        _sessionId = null;
        _questions = [];
        _answers = {};
        _meta = {};
        _generated = null;

        const title = document.getElementById('es-ki-wizard-title');
        if (title) title.textContent = t('ki_refine_tab', 'KI verfeinern');

        _meta = {
            name: fields.name,
            identifier: fields.identifier,
            subject: fields.subject,
            app_scope: fields.app_scope || 'general',
            sender_mode: fields.sender_mode || 'USER',
            signature_mode: fields.signature_mode || 'USER',
            event_type: 'info',
            status: 'DRAFT',
        };
        _generated = {
            html_body: fields.html_body,
            text_body: fields.text_body,
            source: 'editor',
        };
        _showPreview();
        _setStep('preview');
        _updatePreviewFooterForRefine();
        _showModal('es-ki-refine-notes');
        _setBusy(true);

        let briefing = (fields.subject || fields.name || '').trim();
        if (briefing.length < 10) {
            briefing = (fields.html_body || '').replace(/<[^>]+>/g, ' ').trim().slice(0, 400);
        }
        if (briefing.length < 10) {
            briefing = 'Verfeinerung bestehender E-Mail-Vorlage im Editor';
        }

        try {
            const created = await _api('POST', '/wizards/email_template/session/', { briefing });
            _sessionId = created.session_id;

            _answers = {
                S1: fields.app_scope || 'general',
                S2: 'info',
                I1: 'prose',
                G1: fields.signature_mode || 'USER',
                A1: fields.sender_mode || 'USER',
                M2: 'none',
                L1: 'none',
                L3: 'none',
            };
            await _api('POST', `/session/${_sessionId}/clarify/`, { answers: _answers });

            _meta = {
                ..._meta,
                name: fields.name,
                identifier: fields.identifier,
                subject: fields.subject,
                app_scope: fields.app_scope || 'general',
                sender_mode: fields.sender_mode || 'USER',
                signature_mode: fields.signature_mode || 'USER',
            };
            _generated = {
                html_body: fields.html_body,
                text_body: fields.text_body,
                source: 'editor',
            };
            _showPreview();
            _focusModal('es-ki-refine-notes');
        } catch (e) {
            _refineMode = false;
            _showError(e.message);
        } finally {
            _setBusy(false);
        }
    }

    function _stripAnswerJson(text) {
        if (!text) return '';
        let out = String(text);
        const re = /\{\s*"[A-Z]\d+"\s*:\s*(?:"[^"]*"|true|false|null|\[[^\]]*\])\s*\}/g;
        for (let i = 0; i < 20; i++) {
            const next = out.replace(re, '');
            if (next === out) break;
            out = next;
        }
        return out.replace(/(?:<p>\s*<\/p>\s*)+/gi, '').replace(/\n{3,}/g, '\n\n').trim();
    }

    function _runApply() {
        _readMetaFields();
        // Kein _syncFromEditorIfRefine() hier — das würde das verfeinerte
        // _generated mit dem alten Editor-Inhalt überschreiben.
        const htmlBody = _stripAnswerJson(_generated?.html_body || '');
        const textBody = _stripAnswerJson(_generated?.text_body || '');
        if (!htmlBody.trim()) {
            _showError(t('ki_refine_no_content', 'Kein Inhalt zum Übernehmen.'));
            return;
        }
        const fields = {
            name: _meta.name,
            identifier: _meta.identifier,
            subject: _meta.subject,
            description: _meta.description || document.getElementById('es-ki-briefing')?.value || '',
            app_scope: _meta.app_scope,
            event_type: _meta.event_type || 'info',
            sender_mode: _meta.sender_mode || 'USER',
            signature_mode: _meta.signature_mode || 'USER',
            status: _meta.status || 'DRAFT',
            html_body: htmlBody,
            text_body: textBody,
        };

        if (_refineMode && window.ESStudio?.applyWizardResult) {
            close();
            ESStudio.applyWizardResult(fields);
            _refineMode = false;
            return;
        }

        sessionStorage.setItem(STORAGE_KEY, JSON.stringify(fields));
        close();
        window.location.href = '/email-studio/studio/?new=blank&from_ki=1';
    }

    function _focusModal(focusId) {
        if (!focusId) return;
        requestAnimationFrame(() => {
            const modal = document.getElementById('es-ki-wizard-modal');
            if (!modal || modal.getAttribute('aria-hidden') === 'true') return;
            document.getElementById(focusId)?.focus();
        });
    }

    function _showModal(focusId) {
        const modal = document.getElementById('es-ki-wizard-modal');
        if (!modal) {
            console.warn('[ESKiWizard] #es-ki-wizard-modal fehlt im DOM — ki-wizard-modal.html einbinden.');
            return;
        }
        modal.classList.add('show');
        modal.setAttribute('aria-hidden', 'false');
        _focusModal(focusId);
    }

    function open() {
        if (!document.getElementById('es-ki-wizard-modal')) {
            console.warn('[ESKiWizard] #es-ki-wizard-modal fehlt im DOM — ki-wizard-modal.html einbinden.');
            return;
        }
        _reset();
        _showModal('es-ki-briefing');
    }

    function close() {
        const modal = document.getElementById('es-ki-wizard-modal');
        if (!modal) return;
        const active = document.activeElement;
        if (active && modal.contains(active)) {
            active.blur();
        }
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
