// Globale Funktionen für das ABpE CRM

// Toggle für Sektionen (auf-/zuklappen)
function toggleSection(header) {
    if (!header) return;
    header.classList.toggle('open');
    const content = header.nextElementSibling;
    if (content) {
        content.classList.toggle('open');
    }
}

// Spezieller Toggle für Statistik (mit ID)
function toggleStats() {
    const statsHeader = document.getElementById('statsToggleHeader');
    if (statsHeader) {
        toggleSection(statsHeader);
    }
}

// User Menu Toggle
function toggleUserMenu() {
    const dropdown = document.getElementById('userDropdown');
    if (dropdown) {
        dropdown.classList.toggle('show');
    }
}

// Hilfe Modal Toggle
function toggleHelp() {
    const modal = document.getElementById('helpModal');
    if (modal) {
        modal.classList.toggle('show');
    }
}

// Hilfe Modal schließen bei Klick außerhalb
function closeHelpOnOutside(event) {
    const modal = document.getElementById('helpModal');
    if (event.target === modal) {
        toggleHelp();
    }
}

// Mobile Sidebar Toggle
function toggleMobileSidebar() {
    const sidebar = document.getElementById('sidebar');
    if (sidebar) {
        sidebar.classList.toggle('open');
    }
}

// Klick außerhalb schließt User Menu
document.addEventListener('click', function(e) {
    const userMenu = document.querySelector('.user-menu');
    const dropdown = document.getElementById('userDropdown');
    if (userMenu && dropdown && !userMenu.contains(e.target)) {
        dropdown.classList.remove('show');
    }
});

// Tastaturkürzel
document.addEventListener('keydown', function(e) {
    // Nicht in Input-Feldern
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {
        return;
    }
    
    // ? = Hilfe öffnen
    if (e.key === '?') {
        e.preventDefault();
        toggleHelp();
    }
    
    // / = Suchfeld fokussieren
    if (e.key === '/') {
        e.preventDefault();
        const searchInput = document.getElementById('searchInput');
        if (searchInput) {
            searchInput.focus();
        }
    }
    
    // s oder S = Statistik Toggle
    if (e.key === 's' || e.key === 'S') {
        toggleStats();
    }
});

// Initialisierung: Stelle sicher dass alle Funktionen global verfügbar sind
window.toggleSection = toggleSection;
window.toggleStats = toggleStats;
window.toggleUserMenu = toggleUserMenu;
window.toggleHelp = toggleHelp;
window.closeHelpOnOutside = closeHelpOnOutside;
window.toggleMobileSidebar = toggleMobileSidebar;
