/* mod-shaduler.js — Reiter-Router + Aufgaben-Queue (Mockup V1) */
(function (global) {
  'use strict';

  function _t(key, fallback) {
    try {
      if (typeof global.loadLanguage === 'function' && global.ABPE_I18N) {
        /* portal _t often on window */
      }
    } catch (e) {}
    if (global.Shaduler && global.Shaduler.__portal_t) {
      try {
        var v = global.Shaduler.__portal_t(key, fallback);
        if (v && v !== key) return v;
      } catch (e2) {}
    }
    var portalT = Object.getOwnPropertyDescriptor(global, '_t');
    if (portalT && typeof portalT.value === 'function' && portalT.value !== _t) {
      try {
        var r = portalT.value(key, fallback);
        if (r && r !== key) return r;
      } catch (e3) {}
    }
    return fallback || key;
  }

  var cfg = { api_base: '/shaduler/api/', tab: 'aufgaben' };
  var loaded = {};
  var TASKS = [];
  var STATS = { heute: 0, ueberfaellig: 0, geplant: 0, erledigt_heute: 0 };
  var openGroups = { wiedervorlage: true, anruf: true, intern: true };
  var currentTask = null;
  var currentResult = null;

  var ARTEN = {
    wiedervorlage: { icon: 'bi-arrow-repeat', cv: '--a-wv', labelKey: 'sh.art_wiedervorlage', label: 'Wiedervorlagen', short: 'wv' },
    anruf: { icon: 'bi-telephone', cv: '--a-anruf', labelKey: 'sh.art_anruf', label: 'Anrufe', short: 'anruf' },
    email: { icon: 'bi-envelope', cv: '--a-email', labelKey: 'sh.art_email', label: 'E-Mails', short: 'email' },
    dokument: { icon: 'bi-file-earmark-text', cv: '--a-doc', labelKey: 'sh.art_dokument', label: 'Dokumente', short: 'doc' },
    post: { icon: 'bi-mailbox', cv: '--a-post', labelKey: 'sh.art_post', label: 'Post', short: 'post' },
    sms_messenger: { icon: 'bi-whatsapp', cv: '--a-wa', labelKey: 'sh.art_sms_messenger', label: 'WhatsApp / SMS', short: 'wa' },
    termin: { icon: 'bi-calendar-event', cv: '--a-allg', labelKey: 'sh.art_termin', label: 'Termine', short: 'termin' },
    intern: { icon: 'bi-briefcase', cv: '--a-allg', labelKey: 'sh.art_intern', label: 'Allgemeines', short: 'allg' },
  };
  var ORDER = ['wiedervorlage', 'anruf', 'email', 'dokument', 'post', 'sms_messenger', 'termin', 'intern'];

  function api(path) {
    return (cfg.api_base || '/shaduler/api/') + path.replace(/^\//, '');
  }

  function esc(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

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

  function paneHtml(name) {
    if (name === 'aufgaben') {
      return (
        '<div class="sh-pane" data-pane="aufgaben">' +
        '<div class="stats-grid">' +
        '<div class="stat-card"><div class="stat-value" id="n-today">0</div><div class="stat-title" data-i18n="sh.stat_heute">heute fällig</div></div>' +
        '<div class="stat-card"><div class="stat-value red" id="n-ov">0</div><div class="stat-title" data-i18n="sh.stat_ueberfaellig">überfällig</div></div>' +
        '<div class="stat-card"><div class="stat-value" id="n-plan">0</div><div class="stat-title" data-i18n="sh.stat_geplant">geplant</div></div>' +
        '<div class="stat-card"><div class="stat-value" id="n-done">0</div><div class="stat-title" data-i18n="sh.stat_erledigt">heute erledigt</div></div>' +
        '</div>' +
        '<div class="sh-card"><div id="sh-acc"></div></div>' +
        '<div id="sh-demo-hint" class="sh-hint" style="display:none"></div>' +
        '</div>' +
        modalHtml()
      );
    }
    if (name === 'regeln') {
      return (
        '<div class="sh-pane" data-pane="regeln"><div class="sh-card">' +
        '<p class="sh-hint" data-i18n="sh.regeln_admin_hint">Regeln vorerst im Django-Admin (ProzessRegel + Schritte).</p>' +
        '<p><a href="/admin/abpe_shaduler/prozessregel/" target="_blank" rel="noopener">' +
        _t('sh.regeln_admin_link', 'Zum Admin öffnen') + '</a></p></div></div>'
      );
    }
    return (
      '<div class="sh-pane" data-pane="' + esc(name) + '">' +
      '<p class="sh-hint">' + _t('sh.tab_stub', 'Reiter folgt in der nächsten Etappe:') +
      ' <b>' + esc(name) + '</b></p></div>'
    );
  }

  function modalHtml() {
    return (
      '<div class="ovl" id="sh-ovl" style="display:none">' +
      '<div class="modal">' +
      '<div class="mh">' +
      '<div class="ico"><i id="sh-m-ico" class="bi bi-telephone"></i></div>' +
      '<div><b id="sh-m-title"></b><small id="sh-m-ref"></small></div>' +
      '<button type="button" class="x" id="sh-m-close"><i class="bi bi-x-lg"></i></button>' +
      '</div>' +
      '<div class="mb">' +
      '<div class="phase on" id="sh-ph-act">' +
      '<div class="excerpt" id="sh-m-excerpt"></div>' +
      '<button type="button" class="primary" id="sh-m-action"></button>' +
      '<div class="note" id="sh-m-actnote"></div>' +
      '</div>' +
      '<div class="phase" id="sh-ph-res" style="display:none">' +
      '<div class="qlbl">' + _t('sh.popup_ergebnis', 'Wie ist es ausgegangen?') + '</div>' +
      '<div class="results" id="sh-m-results"></div>' +
      '</div>' +
      '<div class="phase" id="sh-ph-fx" style="display:none">' +
      '<div class="qlbl"><i class="bi bi-check-circle" style="color:var(--status-green)"></i> ' +
      _t('sh.popup_erledigt', 'Erledigt — automatisch passiert:') + '</div>' +
      '<div class="fx" id="sh-m-fx"></div>' +
      '<button type="button" class="done-btn" id="sh-m-done">' +
      _t('sh.popup_weiter', 'Weiter') + ' <i class="bi bi-arrow-right"></i></button>' +
      '</div>' +
      '</div></div></div>' +
      '<div class="toast" id="sh-toast"></div>'
    );
  }

  function loadTab(name) {
    var body = document.getElementById('shaduler-tab-body');
    if (!body) return;
    body.innerHTML = paneHtml(name);
    applyI18n(body);
    if (name === 'aufgaben') {
      bindModal();
      loadAufgaben();
    } else {
      refreshStats();
    }
  }

  function applyI18n(root) {
    (root || document).querySelectorAll('[data-i18n]').forEach(function (el) {
      var k = el.getAttribute('data-i18n');
      var v = _t(k, el.textContent);
      if (v) el.textContent = v;
    });
  }

  function loadAufgaben() {
    Promise.all([
      fetch(api('stats/'), { credentials: 'same-origin', headers: { 'X-Requested-With': 'XMLHttpRequest' } }).then(function (r) { return r.json(); }),
      fetch(api('aufgaben/?demo=1'), { credentials: 'same-origin', headers: { 'X-Requested-With': 'XMLHttpRequest' } }).then(function (r) { return r.json(); }),
    ]).then(function (pair) {
      var stats = pair[0] || {};
      var data = pair[1] || {};
      TASKS = data.results || [];
      STATS = {
        heute: stats.heute || 0,
        ueberfaellig: stats.ueberfaellig || 0,
        geplant: stats.geplant || 0,
        erledigt_heute: stats.erledigt_heute || 0,
      };
      if (data.demo) {
        var hint = document.getElementById('sh-demo-hint');
        if (hint) {
          hint.style.display = 'block';
          hint.textContent = _t(
            'sh.demo_hint',
            'Demo-Daten (noch keine Migration) — UI wie Final-Mockup. Später echte Aufgaben aus der DB.'
          );
        }
      }
      renderAcc();
      refreshStatsFrom(stats);
    }).catch(function () {
      TASKS = [];
      renderAcc();
    });
  }

  function refreshStatsFrom(stats) {
    var b = (stats && stats.badges) || {};
    var el;
    el = document.getElementById('tb-a'); if (el) el.textContent = b.aufgaben != null ? b.aufgaben : (STATS.heute + STATS.ueberfaellig);
    el = document.getElementById('tb-post'); if (el) el.textContent = b.posteingang || 0;
    el = document.getElementById('tb-ra'); if (el) el.textContent = b.radar_anfragen || 0;
    el = document.getElementById('tb-rb'); if (el) el.textContent = b.radar_berater || 0;
    el = document.getElementById('n-today'); if (el) el.textContent = STATS.heute;
    el = document.getElementById('n-ov'); if (el) el.textContent = STATS.ueberfaellig;
    el = document.getElementById('n-plan'); if (el) el.textContent = STATS.geplant;
    el = document.getElementById('n-done'); if (el) el.textContent = STATS.erledigt_heute;
  }

  function refreshStats() {
    fetch(api('stats/'), { credentials: 'same-origin', headers: { 'X-Requested-With': 'XMLHttpRequest' } })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        STATS = {
          heute: data.heute || 0,
          ueberfaellig: data.ueberfaellig || 0,
          geplant: data.geplant || 0,
          erledigt_heute: data.erledigt_heute || 0,
        };
        refreshStatsFrom(data);
      })
      .catch(function () {});
  }

  function renderAcc() {
    var c = document.getElementById('sh-acc');
    if (!c) return;
    c.innerHTML = '';
    var head = document.createElement('div');
    head.className = 'acc-head';
    head.innerHTML =
      '<span class="gi" style="background:var(--abcona-blue,#163258)"><i class="bi bi-collection"></i></span>' +
      '<b>' + esc(_t('sh.alle', 'Alle')) + '</b>' +
      '<span class="cnt">(' + TASKS.length + ')</span>';
    c.appendChild(head);

    ORDER.forEach(function (art) {
      var a = ARTEN[art];
      if (!a) return;
      var list = TASKS.filter(function (t) { return t.art === art; });
      var ov = list.filter(function (t) { return t.ueberfaellig; }).length;
      var open = !!openGroups[art];
      var acc = document.createElement('div');
      acc.className = 'acc' + (open ? ' open' : '');
      var label = _t(a.labelKey, a.label);
      acc.innerHTML =
        '<div class="acc-head">' +
        '<span class="gi" style="background:var(' + a.cv + ')"><i class="bi ' + a.icon + '"></i></span>' +
        '<b>' + esc(label) + '</b>' +
        '<span class="cnt">(' + list.length + ')' +
        (ov ? ' <span class="ovd">· ' + ov + ' <i class="bi bi-exclamation-triangle-fill"></i></span>' : '') +
        '</span><span class="car"><i class="bi bi-chevron-right"></i></span></div>' +
        '<div class="acc-body">' +
        (list.length ? '' : '<div class="none">' + esc(_t('sh.keine_aufgaben', 'keine offenen Aufgaben')) + '</div>') +
        '</div>';
      acc.querySelector('.acc-head').addEventListener('click', function () {
        openGroups[art] = !openGroups[art];
        renderAcc();
      });
      var body = acc.querySelector('.acc-body');
      list.forEach(function (t) {
        var el = document.createElement('div');
        el.className = 'task' + (t.ueberfaellig ? ' ov' : '');
        el.innerHTML =
          '<div class="tx"><b>' + esc(t.titel) + '</b><small>' + esc(t.ref_label || t.ref_type || '') + '</small></div>' +
          '<span class="due">' + (t.ueberfaellig ? '<i class="bi bi-exclamation-triangle-fill"></i> ' : '') +
          esc(t.due_label || '') + '</span>';
        el.addEventListener('click', function () { openModal(t); });
        body.appendChild(el);
      });
      c.appendChild(acc);
    });

    refreshStatsFrom({
      heute: STATS.heute, ueberfaellig: STATS.ueberfaellig,
      geplant: STATS.geplant, erledigt_heute: STATS.erledigt_heute,
      badges: {
        aufgaben: TASKS.filter(function (t) { return t.ueberfaellig || t.bucket === 'heute'; }).length,
      },
    });
  }

  function bindModal() {
    var close = document.getElementById('sh-m-close');
    var done = document.getElementById('sh-m-done');
    var act = document.getElementById('sh-m-action');
    var ovl = document.getElementById('sh-ovl');
    if (close) close.onclick = closeModal;
    if (done) done.onclick = closeModal;
    if (act) act.onclick = function () { showPhase('res'); };
    if (ovl) ovl.addEventListener('click', function (e) {
      if (e.target === ovl) closeModal();
    });
  }

  function showPhase(which) {
    ['act', 'res', 'fx'].forEach(function (p) {
      var el = document.getElementById('sh-ph-' + p);
      if (!el) return;
      var on = p === which;
      el.classList.toggle('on', on);
      el.style.display = on ? '' : 'none';
    });
  }

  function openModal(t) {
    currentTask = t;
    currentResult = null;
    var ovl = document.getElementById('sh-ovl');
    if (!ovl) return;
    var art = ARTEN[t.art] || ARTEN.intern;
    var ico = document.getElementById('sh-m-ico');
    if (ico) ico.className = 'bi ' + art.icon;
    document.getElementById('sh-m-title').textContent = t.titel || '';
    document.getElementById('sh-m-ref').textContent = t.ref_label || '';
    var ex = t.excerpt || {};
    var html = '';
    if (ex.stand) html += '<div><b>' + esc(_t('sh.stand', 'Stand')) + ':</b> ' + esc(ex.stand) + '</div>';
    if (ex.hist && ex.hist.length) {
      html += '<ul>' + ex.hist.map(function (h) { return '<li>' + esc(h) + '</li>'; }).join('') + '</ul>';
    }
    document.getElementById('sh-m-excerpt').innerHTML = html || '<div class="none">' + esc(_t('sh.kein_auszug', 'Kein Auszug')) + '</div>';
    document.getElementById('sh-m-action').textContent = t.action_label || _t('sh.erledigen', 'Erledigen');
    document.getElementById('sh-m-actnote').textContent = t.action_note || '';
    var results = t.results || [
      { label: _t('sh.erg_erledigt', 'Erledigt ✓'), sub: '', fx: [_t('sh.fx_historie', 'Historie-Eintrag')] },
      { label: _t('sh.erg_snooze', 'Später (+1 Tag)'), sub: '', fx: [_t('sh.fx_snooze', 'Fälligkeit +1 Tag')] },
    ];
    var box = document.getElementById('sh-m-results');
    box.innerHTML = '';
    results.forEach(function (r) {
      var btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'rbtn';
      btn.innerHTML = '<b>' + esc(r.label) + '</b>' + (r.sub ? '<small>' + esc(r.sub) + '</small>' : '');
      btn.addEventListener('click', function () { applyResult(r); });
      box.appendChild(btn);
    });
    showPhase('act');
    ovl.style.display = 'flex';
  }

  function applyResult(r) {
    currentResult = r;
    var fx = document.getElementById('sh-m-fx');
    fx.innerHTML = (r.fx || []).map(function (x) {
      return '<div class="fx-item"><i class="bi bi-check2"></i> ' + esc(x) + '</div>';
    }).join('') || '<div class="none">—</div>';
    // lokal aus Queue nehmen (Demo)
    if (currentTask && currentTask.id) {
      TASKS = TASKS.filter(function (t) { return t.id !== currentTask.id; });
      STATS.erledigt_heute = (STATS.erledigt_heute || 0) + 1;
      renderAcc();
    }
    showPhase('fx');
    toast(_t('sh.toast_erledigt', 'Aufgabe erledigt (Demo)'));
  }

  function closeModal() {
    var ovl = document.getElementById('sh-ovl');
    if (ovl) ovl.style.display = 'none';
    currentTask = null;
  }

  function toast(msg) {
    var el = document.getElementById('sh-toast');
    if (!el) return;
    el.innerHTML = '<i class="bi bi-check2-circle"></i> ' + esc(msg);
    el.classList.add('on');
    setTimeout(function () { el.classList.remove('on'); }, 2200);
  }

  function init(userCfg) {
    // Portal-_t merken falls vorhanden
    if (typeof global._t === 'function') {
      try {
        var desc = Object.getOwnPropertyDescriptor(global, '_t');
        if (desc && desc.value && desc.value !== _t) {
          global.Shaduler = global.Shaduler || {};
          global.Shaduler.__portal_t = desc.value;
        }
      } catch (e) {}
    }
    cfg = Object.assign({}, cfg, userCfg || global.SHADULER_CONFIG || {});
    document.querySelectorAll('#shaduler-root .mtab').forEach(function (btn) {
      btn.addEventListener('click', function () {
        setTab(btn.getAttribute('data-t'));
      });
    });
    setTab(cfg.tab || 'aufgaben');
  }

  global.Shaduler = {
    init: init,
    setTab: setTab,
    refreshStats: refreshStats,
    _t: _t,
  };
})(window);
