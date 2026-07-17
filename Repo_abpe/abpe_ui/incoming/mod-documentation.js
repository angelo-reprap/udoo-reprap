// mod-documentation.js - Dokumentations-Modul

function getDocPage() {
    const path = window.location.pathname;
    if (path.includes('user-manual'))  return 'user_manual';
    if (path.includes('operations'))   return 'operations';
    if (path.includes('new-module'))   return 'new_module';
    if (path.includes('/api/') || path.includes('api-reference') || path.includes('api_reference')) return 'api_reference';
    return 'doc';
}

async function loadDocumentation(lang) {
    const page = getDocPage();
    console.log(`Lade Dokumentation für: ${lang} | Seite: ${page}`);

    try {
        // ── Schritt 1: manifest.json laden ──────────────────────────────
        const manifestUrl = `/static/abpe_ui/i18n/${lang}/modules/documentation/manifest.json`;
        const manifestResp = await fetch(manifestUrl);
        if (!manifestResp.ok) {
            // Fallback auf alte monolithische Datei
            console.warn('Kein Unterverzeichnis — Fallback auf documentation.json');
            return await _loadDocumentationLegacy(lang, page);
        }
        const manifest = await manifestResp.json();

        // ── Schritt 2: Nur Dateien der aktuellen Subpage laden ───────────
        const pageFiles = (manifest.files || []).filter(f => f.startsWith(`${page}/`));
        console.log(`Lade ${pageFiles.length} Dateien für Subpage: ${page}`);

        const doc = {};
        for (const file of pageFiles) {
            const url = `/static/abpe_ui/i18n/${lang}/modules/documentation/${file}`;
            try {
                const resp = await fetch(url);
                if (resp.ok) {
                    const data = await resp.json();
                    // meta.json hat toc + sections + evtl. version etc.
                    // content-Dateien haben { section_id: html }
                    Object.assign(doc, data);
                }
            } catch(e) {
                console.warn(`Fehler beim Laden: ${file}`, e);
            }
        }

        // content zusammenführen (kommt aus einzelnen Dateien)
        if (!doc.content) doc.content = {};
        for (const file of pageFiles) {
            if (file === `${page}/meta.json`) continue;
            const url = `/static/abpe_ui/i18n/${lang}/modules/documentation/${file}`;
            try {
                const resp = await fetch(url);
                if (resp.ok) {
                    const data = await resp.json();
                    Object.assign(doc.content, data);
                }
            } catch(e) {}
        }

        _renderDocumentation(doc, page);

    } catch (error) {
        console.error('Fehler beim Laden der Dokumentation:', error);
    }
}

async function _loadDocumentationLegacy(lang, page) {
    try {
        const response = await fetch(`/static/abpe_ui/i18n/${lang}/modules/documentation.json`);
        if (!response.ok) throw new Error('Datei nicht gefunden');
        const data = await response.json();
        const doc = data[page] || data.doc;
        if (doc) _renderDocumentation(doc, page);
    } catch(e) {
        console.error('Legacy-Fallback fehlgeschlagen:', e);
    }
}

function _renderDocumentation(doc, page) {
    // ── TOC ──────────────────────────────────────────────────────────────
    const tocTitle = document.querySelector('[data-i18n="doc.toc.title"]');
    if (tocTitle && doc.toc && doc.toc.title) {
        tocTitle.innerText = doc.toc.title;
    }

    const tocContainer = document.getElementById('toc-container');
    if (tocContainer && doc.sections) {
        tocContainer.innerHTML = '';
        doc.sections.forEach(section => {
            const btn = document.createElement('button');
            btn.className = 'toc-item';
            btn.setAttribute('data-section', section.id);
            btn.innerHTML = `${section.number}. ${section.title}`;
            btn.addEventListener('click', () => {
                const targetSection = document.getElementById(`section-${section.id}`);
                if (targetSection) {
                    targetSection.scrollIntoView({ behavior: 'smooth' });
                    const header = targetSection.querySelector('.section-header');
                    if (header && !header.classList.contains('open')) {
                        if (typeof toggleSection === 'function') toggleSection(header);
                    }
                }
            });
            tocContainer.appendChild(btn);
        });
        console.log('TOC gefüllt mit', doc.sections.length, 'Einträgen');
    }

    // ── Kapitel ───────────────────────────────────────────────────────────
    const chaptersContainer = document.getElementById('chapters-container');
    if (chaptersContainer && doc.sections && doc.content) {
        chaptersContainer.innerHTML = '';
        doc.sections.forEach(section => {
            const contentHtml = doc.content[section.id] || '<p>Inhalt folgt...</p>';
            const sectionDiv = document.createElement('div');
            sectionDiv.className = 'toggle-section';
            sectionDiv.id = `section-${section.id}`;
            sectionDiv.innerHTML = `
                <div class="section-header" onclick="toggleSection(this)">
                    <i class="bi bi-info-circle"></i>
                    <span>${section.number}. ${section.title}</span>
                    <i class="bi bi-chevron-down"></i>
                </div>
                <div class="section-content">${contentHtml}</div>
            `;
            chaptersContainer.appendChild(sectionDiv);
        });
        console.log('Kapitel gefüllt mit', doc.sections.length, 'Einträgen für Seite:', page);
        if (typeof DocTut !== 'undefined') DocTut.init();
    }
}

document.addEventListener('DOMContentLoaded', function() {
    const currentLang = document.documentElement.lang || 'de';
    loadDocumentation(currentLang);
});

document.addEventListener('languageChanged', function(e) {
    loadDocumentation(e.detail.language);
});
