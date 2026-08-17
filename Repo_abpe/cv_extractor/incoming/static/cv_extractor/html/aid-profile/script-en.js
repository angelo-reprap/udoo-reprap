(function() {
    'use strict';

    const PAGE_HEIGHT_PX = 1122; // 29.7cm bei 96dpi
    const PAGE_PADDING_PX = 160; // 1.5cm oben + unten
    const USABLE_HEIGHT = PAGE_HEIGHT_PX - PAGE_PADDING_PX - 60; // 60px header

    function updateAllPageNumbers() {
        const pages = document.querySelectorAll('.page');
        const totalPages = pages.length;
        if (totalPages > 0) {
            pages.forEach((page, index) => {
                const right = page.querySelector('.page-header .header-right');
                if (right) {
                    right.innerHTML = `· Seite ${index + 1} von ${totalPages}`;
                }
            });
        }
    }

    function reorganizeExpPages() {
        const expPages = document.querySelectorAll('[id^="page-exp-"]');
        if (!expPages.length) return;

        const firstPage = expPages[0];
        const headerHTML = firstPage.querySelector('.page-header').outerHTML;

        // Alle experience-items sammeln
        const allItems = [];
        expPages.forEach(page => {
            page.querySelectorAll('.experience-item').forEach(item => {
                allItems.push(item.cloneNode(true));
            });
        });

        if (!allItems.length) return;

        // Alte Seiten entfernen
        expPages.forEach(page => page.remove());

        let currentPageEl = null;
        let currentSection = null;
        let currentHeight = 0;
        let pageCount = 0;
        let isFirst = true;

        function newPage() {
            pageCount++;
            currentPageEl = document.createElement('div');
            currentPageEl.className = 'page';
            currentPageEl.id = `page-exp-${pageCount}`;
            currentPageEl.innerHTML = headerHTML;
            currentSection = document.createElement('div');
            currentSection.className = 'section';
            if (isFirst) {
                const h2 = document.createElement('h2');
                h2.className = 'section-title';
                h2.textContent = 'Professional Experience';
                currentSection.appendChild(h2);
                isFirst = false;
                currentHeight = 50;
            } else {
                currentHeight = 0;
            }
            currentPageEl.appendChild(currentSection);
            // Vor den Skill-Seiten einfügen
            const skillPage = document.querySelector('[id^="page-skills"]');
            if (skillPage) {
                document.querySelector('.pdf-container').insertBefore(currentPageEl, skillPage);
            } else {
                document.querySelector('.pdf-container').appendChild(currentPageEl);
            }
        }

        newPage();

        allItems.forEach(item => {
            const temp = item.cloneNode(true);
            temp.style.visibility = 'hidden';
            temp.style.position = 'absolute';
            document.body.appendChild(temp);
            const itemHeight = temp.offsetHeight + 12; // 12px margin
            document.body.removeChild(temp);

            if (currentHeight + itemHeight > USABLE_HEIGHT && currentHeight > 0) {
                newPage();
            }
            currentSection.appendChild(item);
            currentHeight += itemHeight;
        });
    }

    function reorganizeSkillPages() {
        const skillPages = document.querySelectorAll('[id^="page-skills"]');
        if (!skillPages.length) return;

        const firstPage = skillPages[0];
        const headerHTML = firstPage.querySelector('.page-header').outerHTML;

        const allBlocks = [];
        skillPages.forEach(page => {
            page.querySelectorAll('.skill-block').forEach(block => {
                allBlocks.push(block.cloneNode(true));
            });
        });

        if (!allBlocks.length) return;

        skillPages.forEach(page => page.remove());

        let currentPageEl = null;
        let currentSection = null;
        let currentHeight = 0;
        let pageCount = 0;
        let isFirst = true;

        function newPage() {
            pageCount++;
            currentPageEl = document.createElement('div');
            currentPageEl.className = 'page';
            currentPageEl.id = `page-skills-${pageCount}`;
            currentPageEl.innerHTML = headerHTML;
            currentSection = document.createElement('div');
            currentSection.className = 'section';
            if (isFirst) {
                const h2 = document.createElement('h2');
                h2.className = 'section-title';
                h2.textContent = 'Technical Skills';
                currentSection.appendChild(h2);
                isFirst = false;
                currentHeight = 50;
            } else {
                currentHeight = 0;
            }
            currentPageEl.appendChild(currentSection);
            document.querySelector('.pdf-container').appendChild(currentPageEl);
        }

        newPage();

        allBlocks.forEach(block => {
            const temp = block.cloneNode(true);
            temp.style.visibility = 'hidden';
            temp.style.position = 'absolute';
            document.body.appendChild(temp);
            const blockHeight = temp.offsetHeight + 20;
            document.body.removeChild(temp);

            if (currentHeight + blockHeight > USABLE_HEIGHT && currentHeight > 0) {
                newPage();
            }
            currentSection.appendChild(block);
            currentHeight += blockHeight;
        });

        updateAllPageNumbers();
    }

    function initHoverEffects() {
        document.querySelectorAll('.experience-item').forEach(item => {
            item.addEventListener('mouseenter', function() {
                this.style.transform = 'translateY(-2px)';
                this.style.boxShadow = '0 8px 16px rgba(37,99,235,0.12)';
                this.style.borderColor = '#2563eb';
            });
            item.addEventListener('mouseleave', function() {
                this.style.transform = 'translateY(0)';
                this.style.boxShadow = 'none';
                this.style.borderColor = '#e5e7eb';
            });
        });
    }

    function initPrintOptimization() {
        window.addEventListener('beforeprint', updateAllPageNumbers);
    }

    document.addEventListener('DOMContentLoaded', function() {
        reorganizeExpPages();
        reorganizeSkillPages();
        updateAllPageNumbers();
        initHoverEffects();
        initPrintOptimization();
    });

    window.addEventListener('beforeprint', updateAllPageNumbers);

    window.CV = {
        updatePageNumbers: updateAllPageNumbers,
        print: function() { updateAllPageNumbers(); window.print(); }
    };
})();
