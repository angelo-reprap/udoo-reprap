// core-language.js - i18n Sprachlogik (abpe_crm)
let currentLang = window.ABPE_CONFIG?.current_lang || 'de';

window.i18nData = window.i18nData || {};
let translations = window.i18nData;

let _currentModuleId = null;

function _getModuleId(override) {
    if (override && override !== 'null') return override;
    if (window.ABPE_CONFIG?.module_id) return window.ABPE_CONFIG.module_id;
    const tab = window.CRM_TAB || window.ABPE_CONFIG?.tab;
    if (tab) return 'crm_' + tab;
    return null;
}

function _flattenModuleJson(data) {
    if (!data || typeof data !== 'object' || Array.isArray(data)) return data;
    const keys = Object.keys(data);
    if (keys.length === 1) {
        const k = keys[0];
        const inner = data[k];
        if (inner && typeof inner === 'object' && !Array.isArray(inner)) {
            const sample = Object.values(inner)[0];
            if (typeof sample === 'string') return inner;
        }
    }
    return data;
}

async function loadFile(lang, filename) {
    const url = `/static/abpe_crm/i18n/${lang}/${filename}?v=${Date.now()}`;
    try {
        const response = await fetch(url);
        if (response.ok) {
            const data = _flattenModuleJson(await response.json());
            Object.assign(translations, data);
            return true;
        }
    } catch (e) {}
    return false;
}

async function _loadModuleLanguage(lang, moduleId) {
    const manifestUrl = `/static/abpe_crm/i18n/${lang}/modules/${moduleId}/manifest.json`;
    try {
        const res = await fetch(manifestUrl);
        if (res.ok) {
            const manifest = await res.json();
            const files = manifest.files || [];
            console.log(`📂 Modul-Unterverzeichnis: ${moduleId} → ${files.length} Dateien`);
            for (const file of files) {
                await loadFile(lang, `modules/${moduleId}/${file}`);
            }
            return;
        }
    } catch (e) {}

    console.log(`📄 Modul-Fallback: modules/${moduleId}.json`);
    await loadFile(lang, `modules/${moduleId}.json`);
}

async function loadLanguage(lang, moduleId = null) {
    console.log(`📚 Lade Sprache: ${lang}${moduleId ? ' [' + moduleId + ']' : ''}`);
    currentLang = lang;
    window.i18nData = {};
    translations = window.i18nData;

    await loadFile(lang, 'core-common.json');
    await loadFile(lang, 'ui-components.json');
    await loadFile(lang, 'help-modal.json');
    await loadFile(lang, 'crm.json');

    if (moduleId && moduleId !== 'null') {
        _currentModuleId = moduleId;
    } else if (!_currentModuleId) {
        _currentModuleId = _getModuleId(null);
    }

    if (_currentModuleId) {
        await _loadModuleLanguage(lang, _currentModuleId);
    }

    applyTranslations();
    updateLanguageButtons();
    _refreshPbxUi();
}

function _refreshPbxUi() {
    const run = () => {
        if (!document.getElementById('pbx-root') || typeof PBX === 'undefined') return;
        const P = PBX;
        if (typeof window.applyTranslations === 'function') window.applyTranslations();
        if (typeof P.refreshI18n === 'function') {
            try { P.refreshI18n(); } catch (e) { console.warn('PBX.refreshI18n:', e); }
        } else {
            if (typeof P.renderHud === 'function') P.renderHud();
            if (typeof P.renderPark === 'function') P.renderPark();
            if (typeof P.renderKonf === 'function') P.renderKonf();
            if (typeof P.renderQueues === 'function') P.renderQueues();
            if (typeof P.updateCount === 'function') P.updateCount();
        }
        // MeetMe immer nachziehen (auch wenn refreshI18n veraltet / tab-gated)
        if (typeof P.meetmeRenderStrip === 'function') P.meetmeRenderStrip();
        const id = P._meetmeState && P._meetmeState.selectedId;
        const cached = id && P._meetmeState.detailCache && P._meetmeState.detailCache[id];
        if (cached && typeof P.meetmeRenderDetail === 'function') P.meetmeRenderDetail(cached);
        const tab = P.tab;
        if (tab === 'cdr' && typeof P.loadCdr === 'function') P.loadCdr();
        else if (tab === 'stats' && typeof P.loadStats === 'function') P.loadStats();
        else if (tab === 'vm' && typeof P.loadVm === 'function') P.loadVm();
        else if (tab === 'wavnotes' && typeof P.loadWavNotes === 'function') P.loadWavNotes();
    };
    if (typeof requestAnimationFrame === 'function') {
        requestAnimationFrame(() => requestAnimationFrame(run));
    } else {
        setTimeout(run, 50);
    }
}

window.applyTranslations = function applyTranslations() {
    document.querySelectorAll('[data-i18n]').forEach(el => {
        const key = el.getAttribute('data-i18n');
        const val = _resolveKey(key);
        if (val) el.innerText = val;
    });

    document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
        const key = el.getAttribute('data-i18n-placeholder');
        const val = _resolveKey(key);
        if (val) el.placeholder = val;
    });

    document.querySelectorAll('[data-i18n-title]').forEach(el => {
        const key = el.getAttribute('data-i18n-title');
        const val = _resolveKey(key);
        if (val) el.title = val;
    });

    document.querySelectorAll('[data-titles]').forEach(el => {
        try {
            const titles = JSON.parse(el.getAttribute('data-titles') || '{}');
            const title = titles[currentLang];
            if (title) {
                const span = el.querySelector('.nav-title') || el;
                span.innerText = title;
            }
        } catch (e) {}
    });
};

function _resolveKey(key) {
    if (!key) return null;
    if (typeof translations[key] === 'string') return translations[key];
    const keys = key.split('.');
    let val = translations;
    for (const k of keys) {
        if (val && typeof val === 'object') val = val[k];
        else { val = null; break; }
    }
    if (typeof val === 'string') return val;
    if (_currentModuleId && translations[_currentModuleId] && typeof translations[_currentModuleId][key] === 'string') {
        return translations[_currentModuleId][key];
    }
    return null;
}

window.t = function(key, fallback) {
    const val = _resolveKey(key);
    if (val != null) return val;
    if (fallback != null) return fallback;
    return key;
};

function _afterLanguageChange(lang) {
    document.dispatchEvent(new CustomEvent('languageChanged', {
        detail: { language: lang, moduleId: _currentModuleId }
    }));
}

async function setLanguage(lang) {
    if (lang !== currentLang) console.log(`🔄 Sprache wechseln zu: ${lang}`);
    await loadLanguage(lang, _currentModuleId);
    _afterLanguageChange(lang);

    try {
        const csrf = document.cookie.split(';')
            .map(c => c.trim())
            .find(c => c.startsWith('csrftoken='))
            ?.split('=')[1] || '';
        await fetch('/api/set-language/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
            body: JSON.stringify({ language: lang })
        });
    } catch (e) {}
}

function updateLanguageButtons() {
    document.querySelectorAll('.lang-btn').forEach(btn => {
        btn.classList.toggle('active', btn.getAttribute('data-lang') === currentLang);
    });
}

async function initLanguageSelector() {
    try {
        const response = await fetch('/crm/api/available-languages/');
        const data = await response.json();

        const container = document.querySelector('.language-selector');
        if (container && data.languages) {
            container.innerHTML = '';
            data.languages.forEach(lang => {
                const btn = document.createElement('button');
                btn.className = `lang-btn ${lang.code === currentLang ? 'active' : ''}`;
                btn.setAttribute('data-lang', lang.code);
                btn.innerHTML = lang.code.toUpperCase();
                btn.title = lang.native;
                btn.addEventListener('click', (e) => {
                    e.preventDefault();
                    setLanguage(lang.code);
                });
                container.appendChild(btn);
            });
        }

        const serverLang = data.current || currentLang;
        currentLang = serverLang;
        await loadLanguage(currentLang, _getModuleId(null));

        document.dispatchEvent(new CustomEvent('languageSelectorReady', {
            detail: { language: currentLang, moduleId: _currentModuleId }
        }));

    } catch (e) {
        console.error('Fehler beim Laden der Sprachen:', e);
        await loadLanguage(currentLang, _getModuleId(null));
    }
}

async function initLanguage(lang, moduleId) {
    if (lang && lang !== currentLang) currentLang = lang;
    if (moduleId) _currentModuleId = moduleId;
    await loadLanguage(currentLang, _getModuleId(moduleId));
}

document.addEventListener('DOMContentLoaded', () => {
    initLanguageSelector();
});
