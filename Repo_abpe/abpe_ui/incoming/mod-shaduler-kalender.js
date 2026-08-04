/* mod-shaduler-kalender.js — Tag/Woche/Monat/Jahr (Stub) */
(function (global) {
  'use strict';
  global.ShadulerCal = {
    render: function (root, view) {
      if (!root) return;
      root.innerHTML = '<p class="sh-hint">Kalender (' + (view || 'week') + ') — folgt V1.1</p>';
    }
  };
})(window);
