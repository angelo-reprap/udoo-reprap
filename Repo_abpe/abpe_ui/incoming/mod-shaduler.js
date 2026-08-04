/* mod-shaduler.js — Reiter-Router (V1-Skelett) */
(function (global) {
  'use strict';

  function _t(key, fallback) {
    if (typeof global._t === 'function' && global._t !== _t) {
      try { return global._t(key, fallback); } catch (e) {}
    }
    if (typeof global.t === 'function') {
      try { return global.t(key) || fallback; } catch (e) {}
    }
    return fallback || key;
  }

  var cfg = { api_base: '/shaduler/api/', tab: 'aufgaben' };
  var loaded = {};

  function setTab(name) {
    cfg.tab = name || 'aufgaben';
    document.querySelectorAll('#shaduler-root .mtab').forEach(function (b) {
      b.classList.toggle('on', b.getAttribute('data-t') === cfg.tab);
    });
    var url = new URL(window.location.href);
    url.searchParams.set('tab', cfg.tab);
    window.history.replaceState({}, '', url);
    loadTab(cfg.tab);
  }

  function loadTab(name) {
    var body = document.getElementById('shaduler-tab-body');
    if (!body) return;
    if (loaded[name]) {
      body.innerHTML = loaded[name];
      return;
    }
    body.innerHTML = '<div class="sh-loading">' + _t('sh.loading', 'Laden…') + '</div>';
    // Fragmente liegen serverseitig; vorerst Inline-Stub bis Template-Partial-Endpoint kommt
    var html =
      '<div class="sh-pane" data-pane="' + name + '">' +
      '<p class="sh-hint">' + _t('sh.tab_stub', 'Reiter „') + name +
      _t('sh.tab_stub_suffix', '“ — API/UI folgen (V1).') + '</p></div>';
    loaded[name] = html;
    body.innerHTML = html;
    refreshStats();
  }

  function refreshStats() {
    fetch((cfg.api_base || '/shaduler/api/') + 'stats/', {
      headers: { 'X-Requested-With': 'XMLHttpRequest' },
      credentials: 'same-origin',
    })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        var b = data.badges || {};
        var el;
        el = document.getElementById('tb-a'); if (el) el.textContent = b.aufgaben || 0;
        el = document.getElementById('tb-post'); if (el) el.textContent = b.posteingang || 0;
        el = document.getElementById('tb-ra'); if (el) el.textContent = b.radar_anfragen || 0;
        el = document.getElementById('tb-rb'); if (el) el.textContent = b.radar_berater || 0;
      })
      .catch(function () {});
  }

  function init(userCfg) {
    cfg = Object.assign({}, cfg, userCfg || global.SHADULER_CONFIG || {});
    document.querySelectorAll('#shaduler-root .mtab').forEach(function (btn) {
      btn.addEventListener('click', function () {
        setTab(btn.getAttribute('data-t'));
      });
    });
    setTab(cfg.tab || 'aufgaben');
  }

  global.Shaduler = { init: init, setTab: setTab, refreshStats: refreshStats, _t: _t };
})(window);
