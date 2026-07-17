// core-crm-lang-dropdown.js - Flaggen-Dropdown fuer Sprachauswahl im CRM-Header
(function() {
    var FLAG_ICON_OVERRIDES = {
        en: 'gb', ar: 'sa', zh: 'cn', ja: 'jp', ko: 'kr',
        cs: 'cz', sv: 'se', da: 'dk'
    };

    function flagClass(code) {
        return 'fi fi-' + (FLAG_ICON_OVERRIDES[code] || code);
    }

    function closeMenu() {
        var menu = document.getElementById('crm-lang-dd-menu');
        var btn = document.getElementById('crm-lang-dd-btn');
        if (menu) menu.style.display = 'none';
        if (btn) btn.setAttribute('aria-expanded', 'false');
    }

    async function initCrmLangDropdown() {
        var container = document.getElementById('lang-switcher');
        if (!container) return;

        var data;
        try {
            var res = await fetch('/crm/api/available-languages/');
            data = await res.json();
        } catch (e) {
            return;
        }
        var languages = data.languages || [];
        var current = data.current || 'de';
        if (!languages.length) return;

        function render(currentCode) {
            var curLang = null;
            for (var i = 0; i < languages.length; i++) {
                if (languages[i].code === currentCode) { curLang = languages[i]; break; }
            }
            if (!curLang) curLang = languages[0];

            var optionsHtml = languages.map(function(l) {
                return '<div class="crm-lang-dd-option" data-code="' + l.code + '" style="display:flex;align-items:center;gap:8px;padding:8px 12px;cursor:pointer;font-size:13px">' +
                    '<span class="' + flagClass(l.code) + '" style="border-radius:2px;width:18px;height:13px"></span>' +
                    '<span>' + (l.native || l.code.toUpperCase()) + '</span>' +
                    '</div>';
            }).join('');

            container.innerHTML =
                '<div style="position:relative">' +
                    '<button id="crm-lang-dd-btn" type="button" aria-haspopup="true" aria-expanded="false" style="display:flex;align-items:center;gap:6px;padding:6px 10px;border:1px solid #ced4da;border-radius:6px;background:#fff;cursor:pointer;font-size:13px;font-weight:500;color:#212529">' +
                        '<span class="' + flagClass(curLang.code) + '" style="border-radius:2px;width:18px;height:13px"></span>' +
                        '<span>' + curLang.code.toUpperCase() + '</span>' +
                        '<i class="bi bi-chevron-down" style="font-size:11px;color:#6c757d"></i>' +
                    '</button>' +
                    '<div id="crm-lang-dd-menu" style="display:none;position:absolute;top:calc(100% + 4px);right:0;background:#fff;border:1px solid #ced4da;border-radius:6px;min-width:150px;overflow:hidden;z-index:1000;box-shadow:0 4px 12px rgba(0,0,0,0.1)">' +
                        optionsHtml +
                    '</div>' +
                '</div>';

            var btn = document.getElementById('crm-lang-dd-btn');
            var menu = document.getElementById('crm-lang-dd-menu');

            btn.addEventListener('click', function(e) {
                e.stopPropagation();
                var isOpen = menu.style.display === 'block';
                menu.style.display = isOpen ? 'none' : 'block';
                btn.setAttribute('aria-expanded', isOpen ? 'false' : 'true');
            });

            var opts = container.querySelectorAll('.crm-lang-dd-option');
            opts.forEach(function(opt) {
                opt.addEventListener('mouseenter', function() { opt.style.background = '#f8f9fa'; });
                opt.addEventListener('mouseleave', function() { opt.style.background = ''; });
                opt.addEventListener('click', function() {
                    var code = opt.getAttribute('data-code');
                    closeMenu();
                    if (typeof setLanguage === 'function') {
                        setLanguage(code);
                    }
                    render(code);
                });
            });
        }

        render(current);

        document.addEventListener('click', closeMenu);

        document.addEventListener('languageChanged', function(e) {
            if (e.detail && e.detail.language) render(e.detail.language);
        });
    }

    document.addEventListener('DOMContentLoaded', initCrmLangDropdown);
})();
