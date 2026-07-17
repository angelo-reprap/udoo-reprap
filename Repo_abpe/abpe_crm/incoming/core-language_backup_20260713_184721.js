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

async function loadFile(lang, filename) {
    const url = `/static/abpe_crm/i18n/${lang}/${filename}`;
    try {
        const response = await fetch(url);
        if (response.ok) {
            const data = await response.json();
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
    const keys = key.split('.');
    let val = translations;
    for (const k of keys) {
        if (val && typeof val === 'object') val = val[k];
        else return null;
    }
    return typeof val === 'string' ? val : null;
}

window.t = function(key, fallback) {
    const val = _resolveKey(key);
    if (val != null) return val;
    if (fallback != null) return fallback;
    return key;
};

async function setLanguage(lang) {
    if (lang === currentLang) {
        applyTranslations();
        document.dispatchEvent(new CustomEvent('languageChanged', {
            detail: { language: lang, moduleId: _currentModuleId }
        }));
        return;
    }
    console.log(`🔄 Sprache wechseln zu: ${lang}`);
    await loadLanguage(lang, _currentModuleId);

    document.dispatchEvent(new CustomEvent('languageChanged', {
        detail: { language: lang, moduleId: _currentModuleId }
    }));

    try {
        const csrf = document.cookie.split(';')
            .map(c => c.trim())
            .find(c => c.startsWith('csrftoken='))
            ?.split('=')[1] || '';
        const urls = ['/crm/api/set-language/', '/api/set-language/'];
        for (const url of urls) {
            const res = await fetch(url, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
                body: JSON.stringify({ language: lang })
            });
            if (res.ok) break;
        }
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
