/**
 * template.js - Interaktive Features für den CV
 * Version: 2.0 (angepasst für Django)
 */

(function() {
    'use strict';

    // ===== SEITENZAHLEN DYNAMISCH AKTUALISIEREN =====
    function updateAllPageNumbers() {
        const pages = document.querySelectorAll('.page');
        const totalPages = pages.length;

        if (totalPages > 0) {
            pages.forEach((page, index) => {
                const currentPage = index + 1;
                const header = page.querySelector('.page-header');
                if (header) {
                    const right = header.querySelector('.header-right');
                    if (right) {
                        right.innerHTML = right.innerHTML.replace(
                            /Seite \d+ von \d+/,
                            `Seite ${currentPage} von ${totalPages}`
                        );
                    }
                }
            });
        }
    }

    // ===== INITIALISIERUNG =====
    document.addEventListener('DOMContentLoaded', function() {
        updateAllPageNumbers();
    });

    // Bei Druckvorschau/PDF-Export Seitenzahlen aktualisieren
    window.addEventListener('beforeprint', function() {
        updateAllPageNumbers();
    });

    // ===== EXPORT =====
    window.CV = {
        updatePageNumbers: updateAllPageNumbers,
        print: function() {
            updateAllPageNumbers();
            window.print();
        }
    };
})();
