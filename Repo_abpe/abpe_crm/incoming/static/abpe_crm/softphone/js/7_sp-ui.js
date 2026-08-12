/**
 * 7_sp-ui.js — Drag, Pin, Panel-Positionierung
 * Extrahiert aus mod-softphone-ext.js
 * Nur relevant wenn SP_STANDALONE=false (Portal-Modal)
 * Im Standalone: Panels werden relativ zum Modal positioniert
 */

// Drag & Pin — nur im Portal-Modal-Modus
Softphone._pinned = (function() {
    try { return localStorage.getItem('sp_pinned') === '1'; } catch(e) { return false; }
})();

Softphone._applyPinnedPosition = function() {
    var modal = document.getElementById('sp-modal');
    if (!modal) return;
    var fopOpen = document.getElementById('sp-fop-panel') &&
        document.getElementById('sp-fop-panel').style.display === 'block';
    modal.style.left  = '';
    modal.style.right = (200 + (fopOpen ? 164 : 0)) + 'px';
    modal.style.top   = '80px';
};

Softphone._restorePosition = function() {
    var modal = document.getElementById('sp-modal');
    if (!modal) return;
    // Pin nur beachten wenn Pin-Button existiert
    var hasPinBtn = !!document.getElementById('sp-pin-btn');
    if (!hasPinBtn && Softphone._pinned) {
        Softphone._pinned = false;
        try { localStorage.removeItem('sp_pinned'); } catch(e) {}
    }
    if (Softphone._pinned) { Softphone._applyPinnedPosition(); return; }
    try {
        var x = localStorage.getItem('sp_modal_x');
        var y = localStorage.getItem('sp_modal_y');
        if (x && y) {
            modal.style.right = '';
            modal.style.left  = x + 'px';
            modal.style.top   = y + 'px';
        } else {
            modal.style.right = '20px';
            modal.style.left  = '';
            modal.style.top   = '80px';
        }
    } catch(e) {}
};

Softphone._initDrag = function() {
    var handle = document.getElementById('sp-drag-handle');
    var modal  = document.getElementById('sp-modal');
    if (!handle || !modal) return;

    var dragging = false, startX, startY, origLeft, origTop;

    handle.addEventListener('mousedown', function(e) {
        if (e.target.closest('button')) return;
        if (Softphone._pinned) return;
        dragging = true;
        var spd = document.getElementById('sp-speed-panel');
        var fop = document.getElementById('sp-fop-panel');
        if (spd && spd.style.display === 'block') Softphone.toggleSpeedDial();
        if (fop && fop.style.display === 'block') Softphone.toggleFOP();
        if (Softphone._closeRecent) Softphone._closeRecent();
        var rect = modal.getBoundingClientRect();
        startX = e.clientX; startY = e.clientY;
        origLeft = rect.left; origTop = rect.top;
        modal.style.right = '';
        modal.style.left  = origLeft + 'px';
        modal.style.top   = origTop  + 'px';
        document.body.style.userSelect = 'none';
    });

    document.addEventListener('mousemove', function(e) {
        if (!dragging) return;
        var newL = Math.max(0, Math.min(window.innerWidth  - 260, origLeft + e.clientX - startX));
        var newT = Math.max(0, Math.min(window.innerHeight - 50,  origTop  + e.clientY - startY));
        modal.style.left = newL + 'px';
        modal.style.top  = newT + 'px';
    });

    document.addEventListener('mouseup', function() {
        if (!dragging) return;
        dragging = false;
        document.body.style.userSelect = '';
        try {
            localStorage.setItem('sp_modal_x', parseInt(modal.style.left));
            localStorage.setItem('sp_modal_y', parseInt(modal.style.top));
        } catch(e) {}
    });
};

Softphone.togglePin = function() {
    Softphone._pinned = !Softphone._pinned;
    try { localStorage.setItem('sp_pinned', Softphone._pinned ? '1' : '0'); } catch(e) {}
    var icon = document.getElementById('sp-pin-icon');
    var btn  = document.getElementById('sp-pin-btn');
    if (Softphone._pinned) {
        if (icon) icon.className = 'bi bi-pin-fill';
        if (btn)  btn.style.color = '#fbbf24';
        Softphone._applyPinnedPosition();
    } else {
        if (icon) icon.className = 'bi bi-arrows-move';
        if (btn)  btn.style.color = 'rgba(255,255,255,0.5)';
    }
};

// Panel-Positionierung (Speed links, FOP rechts vom Modal)
Softphone._positionPanel = function(panelId, side) {
    var modal = document.getElementById('sp-modal');
    var panel = document.getElementById(panelId);
    if (!modal || !panel) return;
    var r = modal.getBoundingClientRect();
    panel.style.position = 'fixed';
    panel.style.top      = r.top + 'px';
    panel.style.zIndex   = '10000';
    if (side === 'left') {
        panel.style.left  = '';
        panel.style.right = (window.innerWidth - r.left + 4) + 'px';
    } else {
        panel.style.right = '';
        panel.style.left  = (r.right + 4) + 'px';
    }
};
