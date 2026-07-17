// core-theme.js - Theme Manager
class ThemeManager {
    constructor() {
        this.currentTheme = localStorage.getItem('theme') || 'system';
        this.init();
    }
    init() {
        this.applyTheme();
        this.watchSystemTheme();
    }
    applyTheme() {
        const isDark = this.currentTheme === 'dark' || 
                      (this.currentTheme === 'system' && window.matchMedia('(prefers-color-scheme: dark)').matches);
        if (isDark) document.body.classList.add('dark-mode');
        else document.body.classList.remove('dark-mode');
    }
    setTheme(theme) {
        this.currentTheme = theme;
        localStorage.setItem('theme', theme);
        this.applyTheme();
    }
    watchSystemTheme() {
        window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
            if (this.currentTheme === 'system') this.applyTheme();
        });
    }
}
window.themeManager = new ThemeManager();
function toggleTheme() {
    const newTheme = themeManager.currentTheme === 'light' ? 'dark' : 'light';
    themeManager.setTheme(newTheme);
}
