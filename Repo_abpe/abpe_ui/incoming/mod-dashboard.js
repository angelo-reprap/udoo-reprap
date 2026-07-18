// mod-dashboard.js - Dashboard Modul spezifische Funktionen
// Lädt dashboard-help.json für die Tipps & Tricks

async function loadDashboardHelp(lang) {
    try {
        const response = await fetch(`/static/abpe_ui/i18n/${lang}/dashboard-help.json`);
        if (response.ok) {
            const data = await response.json();
            
            // Direkt die Tipps überschreiben
            const tip1 = document.querySelector('[data-i18n="tip1"]');
            const tip2 = document.querySelector('[data-i18n="tip2"]');
            const tip3 = document.querySelector('[data-i18n="tip3"]');
            const tip4 = document.querySelector('[data-i18n="tip4"]');
            
            if (tip1 && data.tip1) tip1.innerText = data.tip1;
            if (tip2 && data.tip2) tip2.innerText = data.tip2;
            if (tip3 && data.tip3) tip3.innerText = data.tip3;
            if (tip4 && data.tip4) tip4.innerText = data.tip4;
            
            console.log(`Dashboard-Hilfe geladen für ${lang}`, data);
        }
    } catch(e) {
        console.log('Dashboard-Hilfe nicht gefunden für', lang);
    }
}

// Initial laden
document.addEventListener('DOMContentLoaded', function() {
    const currentLang = document.documentElement.lang || 'de';
    console.log('Aktuelle Sprache (HTML lang):', document.documentElement.lang);
    console.log('CurrentLang Variable:', typeof currentLang !== 'undefined' ? currentLang : 'nicht definiert');
    loadDashboardHelp(currentLang);
});

// Bei Sprachwechsel neu laden
document.addEventListener('languageChanged', function(e) {
    console.log('Sprachwechsel Event empfangen:', e.detail.language);
    loadDashboardHelp(e.detail.language);
});
