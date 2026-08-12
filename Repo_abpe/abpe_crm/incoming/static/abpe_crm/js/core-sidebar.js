// Sidebar und Arc (Kreisabschnitt) Logik

const sidebar = document.getElementById('sidebar');
const arc = document.getElementById('sidebarArc');

function updateArcPosition() {
    if (!sidebar || !arc) return;
    
    if (sidebar.classList.contains('open')) {
        // Mobile geöffnet
        arc.style.left = '250px';
    } else if (window.innerWidth <= 768) {
        // Mobile geschlossen
        arc.style.left = '0px';
    } else if (sidebar.matches(':hover')) {
        // Desktop Hover
        const expanded = getComputedStyle(document.documentElement)
            .getPropertyValue('--sidebar-width-expanded').trim();
        arc.style.left = expanded;
    } else {
        // Desktop normal
        const collapsed = getComputedStyle(document.documentElement)
            .getPropertyValue('--sidebar-width-collapsed').trim();
        arc.style.left = collapsed;
    }
}

if (sidebar && arc) {
    // Bei Hover die Arc-Position anpassen
    sidebar.addEventListener('mouseenter', updateArcPosition);
    sidebar.addEventListener('mouseleave', updateArcPosition);
    
    // Bei Fenster-Größenänderung
    window.addEventListener('resize', updateArcPosition);
    
    // Initiale Position setzen
    setTimeout(updateArcPosition, 100);
}

// Stelle sicher dass toggleMobileSidebar die Arc-Position aktualisiert
const originalToggle = window.toggleMobileSidebar;
if (originalToggle) {
    window.toggleMobileSidebar = function() {
        originalToggle();
        updateArcPosition();
    };
}
