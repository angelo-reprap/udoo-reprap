// sp-contacts.js — Adressbuch
// Lookup-Logik:
//   1. pbx_extensions[X]  → intern (sofort)
//   2. contacts[].phones  → lokal JSON
//   3. api_base/berater/?q=X → CRM lazy
//   4. nur Nummer anzeigen
window.SP_Contacts = (function() {
    let _contacts = [];
    let _extensions = {};
    async function load(url) {
        try {
            const r = await fetch(url || window.SP_CONFIG.contacts_url);
            _contacts = await r.json();
        } catch(e) { console.warn('SP_Contacts: Laden fehlgeschlagen', e); }
    }
    function setExtensions(map) { _extensions = map || {}; }
    async function lookup(num) {
        if (!num) return null;
        if (_extensions[num]) return _extensions[num];
        const c = _contacts.find(function(c) {
            return (c.phones || []).some(function(p) { return p.norm === num || p.raw === num; });
        });
        if (c) return c.full_name || c.name || null;
        if (window.SP_CONFIG.api_base) {
            try {
                const r = await fetch(window.SP_CONFIG.api_base + '/berater/?q=' + encodeURIComponent(num) + '&per_page=1&typ=alle');
                const d = await r.json();
                const first = (d.results || d.berater || [])[0];
                if (first) return (first.first_name || '') + ' ' + (first.last_name || '');
            } catch(e) {}
        }
        return null;
    }
    function search(q, limit) {
        if (!q || q.length < 2) return [];
        q = q.toLowerCase();
        return _contacts.filter(function(c) {
            return (c.full_name || c.name || '').toLowerCase().includes(q) ||
                   (c.phones || []).some(function(p) { return (p.norm || p.raw || '').includes(q); });
        }).slice(0, limit || 8);
    }
    return { load, lookup, search, setExtensions };
})();
// TODO: Kontakte beim Start laden
