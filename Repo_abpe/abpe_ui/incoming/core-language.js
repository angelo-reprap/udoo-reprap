// core-language.js - i18n Sprachlogik (Portal)
(function() {
if (window.__ABPE_UI_LANGUAGE__) return;
window.__ABPE_UI_LANGUAGE__ = true;

let currentLang = window.ABPE_CONFIG?.current_lang || 'de';

// window.i18nData global — alle Modul-JS können t() nutzen
window.i18nData = window.i18nData || {};
let translations = window.i18nData;

// Letztes aktives Modul merken
let _currentModuleId = null;

// Portal-Shell-Keys — dürfen von Modul-JSON (z.B. email_studio.help-Objekt) nicht überschrieben werden
const PORTAL_SHELL_KEYS = new Set([
    'help', 'profile', 'settings', 'admin', 'logout', 'cancel', 'save',
    'first_name', 'last_name', 'email', 'search', 'footer', 'login',
    'documentation', 'architecture', 'modules', 'mobile', 'password',
    'address', 'phone', 'start_matching', 'all', 'error',
]);

function _mergeModuleI18n(data) {
    if (!data || typeof data !== 'object') return;
    for (const [key, val] of Object.entries(data)) {
        if (key === 'es' && val && typeof val === 'object') {
            translations.es = { ...(translations.es || {}), ...val };
            continue;
        }
        if (key === 'help' && val && typeof val === 'object') {
            translations.help_section = val;
            continue;
        }
        if (PORTAL_SHELL_KEYS.has(key)) continue;
        translations[key] = val;
    }
}

async function loadFile(lang, filename) {
    const url = `/static/abpe_ui/i18n/${lang}/${filename}`;
    try {
        const response = await fetch(url);
        if (response.ok) {
            const data = await response.json();
            if (filename.startsWith('modules/')) {
                _mergeModuleI18n(data);
            } else {
                Object.assign(translations, data);
            }
            return true;
        }
    } catch (e) {}
    return false;
}

/**
 * Lädt Modul-Sprachdateien — mit Unterverzeichnis-Support.
 *
 * Strategie:
 *   1. Prüft ob modules/{moduleId}/manifest.json existiert
 *   2. Wenn ja → lädt alle darin gelisteten Dateien (neue Struktur)
 *   3. Wenn nein → Fallback auf modules/{moduleId}.json (alte Struktur)
 *
 * manifest.json Format:
 *   { "files": ["doc/01_grundlagen.json", "doc/02_modulsystem.json", ...] }
 */
async function _loadModuleLanguage(lang, moduleId) {
    const manifestUrl = `/static/abpe_ui/i18n/${lang}/modules/${moduleId}/manifest.json`;
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

    // Fallback — alte einzelne JSON (alle anderen Module unverändert)
    console.log(`📄 Modul-Fallback: modules/${moduleId}.json`);
    await loadFile(lang, `modules/${moduleId}.json`);
}

async function loadLanguage(lang, moduleId = null) {
    console.log(`📚 Lade Sprache: ${lang}${moduleId ? ' [' + moduleId + ']' : ''}`);
    currentLang = lang;

    // translations immer auf window.i18nData zeigen
    translations = window.i18nData;

    // Core-Dateien immer laden
    await loadFile(lang, 'core-common.json');
    await loadFile(lang, 'ui-components.json');
    await loadFile(lang, 'help-modal.json');

    // Modul-JSON laden — neu übergeben oder letztes merken
    if (moduleId && moduleId !== 'null') _currentModuleId = moduleId;
    if (_currentModuleId) {
        await _loadModuleLanguage(lang, _currentModuleId);
    }

    applyTranslations();
    updateLanguageButtons();
}

window.applyTranslations = function applyTranslations() {
    // data-i18n — flache und verschachtelte Keys
    document.querySelectorAll('[data-i18n]').forEach(el => {
        const key = el.getAttribute('data-i18n');
        const val = _resolveKey(key);
        if (val) el.innerText = val;
    });

    // data-i18n-placeholder
    document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
        const key = el.getAttribute('data-i18n-placeholder');
        const val = _resolveKey(key);
        if (val) el.placeholder = val;
    });

    // data-titles — Modul-Titel aus module.json (via Translator → titles.<lang>)
    document.querySelectorAll('[data-titles]').forEach(el => {
        try {
            const titles = JSON.parse(el.getAttribute('data-titles') || '{}');
            const title = titles[currentLang] || titles.de;
            if (title) {
                const span = el.querySelector('.nav-title') || el;
                span.innerText = title;
            }
        } catch(e) {}
    });
}

window.mergeModuleI18n = _mergeModuleI18n;

function _resolveKey(key) {
    const keys = key.split('.');
    let val = translations;
    for (const k of keys) {
        if (val && typeof val === 'object') val = val[k];
        else return null;
    }
    return typeof val === 'string' ? val : null;
}

async function setLanguage(lang) {
    if (lang === currentLang) {
        // Trotzdem Event dispatchen damit Module sich aktualisieren
        document.dispatchEvent(new CustomEvent('languageChanged', {
            detail: { language: lang, moduleId: _currentModuleId }
        }));
        return;
    }
    console.log(`🔄 Sprache wechseln zu: ${lang}`);
    await loadLanguage(lang, _currentModuleId);

    // languageChanged dispatchen damit Module reagieren können
    document.dispatchEvent(new CustomEvent('languageChanged', {
        detail: { language: lang, moduleId: _currentModuleId }
    }));

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
    } catch(e) {}
}

function updateLanguageButtons() {
    document.querySelectorAll('.lang-btn').forEach(btn => {
        btn.classList.toggle('active', btn.getAttribute('data-lang') === currentLang);
    });
}

async function initLanguageSelector() {
    try {
        const response = await fetch('/api/available-languages/');
        const data = await response.json();

        const serverLang = data.current || currentLang;
        currentLang = serverLang;
        await loadLanguage(currentLang);

        document.dispatchEvent(new CustomEvent('languageSelectorReady', {
            detail: { language: currentLang }
        }));

    } catch (e) {
        console.error('Fehler beim Laden der Sprachen:', e);
        await loadLanguage(currentLang);
    }
}

async function initLanguage(lang) {
    if (lang && lang !== currentLang) currentLang = lang;
    await loadLanguage(currentLang);
}

window.setLanguage = setLanguage;
window.initLanguage = initLanguage;
window.applyTranslations = applyTranslations;
window.mergeModuleI18n = _mergeModuleI18n;

document.addEventListener('DOMContentLoaded', () => {
    initLanguageSelector();
});

})();
