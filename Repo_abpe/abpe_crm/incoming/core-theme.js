// core-theme.js - Theme Manager (CRM)
class ThemeManager {
    constructor() {
        this.currentTheme = localStorage.getItem('theme') || 'system';
    }

    init() {
        this.applyTheme();
        this.watchSystemTheme();
        this.loadFromServer();
    }

    isDark() {
        return this.currentTheme === 'dark' ||
            (this.currentTheme === 'system' &&
                window.matchMedia('(prefers-color-scheme: dark)').matches);
    }

    applyTheme() {
        const isDark = this.isDark();
        document.documentElement.setAttribute('data-bs-theme', isDark ? 'dark' : 'light');
        document.documentElement.classList.remove('dark-mode-pending');
        if (isDark) document.body.classList.add('dark-mode');
        else document.body.classList.remove('dark-mode');
        if (typeof updateThemeIcons === 'function') updateThemeIcons();
        document.dispatchEvent(new CustomEvent('themeChanged', {
            detail: { theme: this.currentTheme, dark: isDark },
        }));
    }

    setTheme(theme, opts) {
        opts = opts || {};
        if (!['light', 'dark', 'system'].includes(theme)) return;
        this.currentTheme = theme;
        localStorage.setItem('theme', theme);
        this.applyTheme();
        if (!opts.skipServer) this.persistToServer(theme);
    }

    toggleTheme() {
        this.setTheme(this.isDark() ? 'light' : 'dark');
    }

    persistToServer(theme) {
        const base = (window.ABPE_CONFIG && window.ABPE_CONFIG.crm_api_url) || '/crm/api/';
        const csrf = (document.cookie.match(/csrftoken=([^;]+)/) || [])[1] || '';
        fetch(base + 'user-settings/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrf,
                'X-Requested-With': 'XMLHttpRequest',
            },
            body: JSON.stringify({ theme: theme }),
        }).catch(function () {});
    }

    loadFromServer() {
        const base = (window.ABPE_CONFIG && window.ABPE_CONFIG.crm_api_url) || '/crm/api/';
        fetch(base + 'user-settings/', { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
            .then(function (r) { return r.json(); })
            .then(function (d) {
                if (d.success && d.data && d.data.theme) {
                    themeManager.setTheme(d.data.theme, { skipServer: true });
                }
            })
            .catch(function () {});
    }

    watchSystemTheme() {
        window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', function () {
            if (themeManager.currentTheme === 'system') themeManager.applyTheme();
        });
    }
}

window.themeManager = new ThemeManager();

function toggleTheme() {
    themeManager.toggleTheme();
}

document.addEventListener('DOMContentLoaded', function () {
    if (window.themeManager) themeManager.init();
});
