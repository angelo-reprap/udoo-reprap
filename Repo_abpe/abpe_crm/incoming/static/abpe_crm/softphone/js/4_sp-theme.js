// sp-theme.js — Dark/Light Mode
// SP_Theme.set('dark'), SP_Theme.set('light')
window.SP_Theme = (function() {
    function set(mode) {
        document.documentElement.setAttribute('data-theme', mode);
        try { localStorage.setItem('sp_theme', mode); } catch(e) {}
    }
    function init() {
        const saved = (() => { try { return localStorage.getItem('sp_theme'); } catch(e) { return null; } })();
        const preferred = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
        set(saved || preferred);
    }
    function toggle() {
        var current = document.documentElement.getAttribute('data-theme') || 'light';
        var next = current === 'dark' ? 'light' : 'dark';
        set(next);
        var btn = document.getElementById('sp-theme-btn');
        if (btn) btn.querySelector('i').className = next === 'dark' ? 'bi bi-sun' : 'bi bi-moon';
    }
    return { set, init, toggle };
})();
// TODO: CSS-Variablen für beide Modi definieren in softphone.css
