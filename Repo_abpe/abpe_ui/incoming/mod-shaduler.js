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
    if (name === 'kalender') {
      return '<div class="sh-pane" data-pane="kalender"><div id="sh-cal-root"></div></div>' + modalHtml();
    }
    if (name === 'posteingang') {
      return (
        '<div class="sh-pane" data-pane="posteingang"><div class="sh-card">' +
        '<div class="card-h"><i class="bi bi-inbox"></i> Posteingang' +
        '<span style="margin-left:auto;font-weight:400;font-size:.8rem;color:var(--text-secondary)">' +
        _t('sh.inbox_hint', 'Verwalten bleibt Outlook · Lese-Überblick') +
        '</span></div><div id="sh-inbox"></div></div></div>'
      );
    }
    if (name === 'radar_anfragen') {
      return (
        '<div class="sh-pane" data-pane="radar_anfragen">' +
        '<div class="stats-grid">' +
        '<div class="stat-card"><div class="stat-value teal" id="r-new">0</div><div class="stat-title">neue Treffer</div></div>' +
        '<div class="stat-card"><div class="stat-value teal" id="r-best">—</div><div class="stat-title">bester Score</div></div>' +
        '<div class="stat-card"><div class="stat-value">5 Min</div><div class="stat-title">Poll-Takt</div></div>' +
        '<div class="stat-card"><div class="stat-value">2</div><div class="stat-title">gesperrt gefiltert</div></div>' +
        '</div>' +
        '<div class="sh-card"><div class="card-h"><i class="bi bi-broadcast"></i> Projektausschreibungen</div>' +
        '<div id="sh-radar-a"></div></div></div>'
      );
    }
    if (name === 'radar_berater') {
      return (
        '<div class="sh-pane" data-pane="radar_berater"><div class="sh-card">' +
        '<div class="card-h"><i class="bi bi-person-bounding-box"></i> Berater-Profile</div>' +
        '<div class="paste"><input id="sh-radar-paste" placeholder="Talentfinder: Profil-URL oder Text …">' +
        '<button type="button" id="sh-radar-paste-btn"><i class="bi bi-plus-lg"></i></button></div>' +
        '<div id="sh-radar-b"></div></div></div>'
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
    } else if (name === 'kalender') {
      bindModal();
      loadKalender();
    } else if (name === 'posteingang') {
      loadInbox();
    } else if (name === 'radar_anfragen') {
      loadRadarA();
    } else if (name === 'radar_berater') {
      loadRadarB();
    } else {
      refreshStats();
    }
  }

  function ensureTasks(cb) {
    if (TASKS && TASKS.length) { cb(TASKS); return; }
    fetch(api('aufgaben/'), { credentials: 'same-origin', headers: { 'X-Requested-With': 'XMLHttpRequest' } })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        TASKS = data.results || [];
        cb(TASKS);
      })
      .catch(function () { cb([]); });
  }

  function loadKalender() {
    ensureTasks(function (tasks) {
      if (global.ShadulerCal && typeof global.ShadulerCal.render === 'function') {
        global.ShadulerCal.render(document.getElementById('sh-cal-root'), tasks, {
          arten: ARTEN,
          order: ORDER,
          today: 3,
          onOpenTask: openModal,
        });
      }
      refreshStats();
    });
  }

  function loadInbox() {
    fetch(api('inbox/?demo=1'), { credentials: 'same-origin', headers: { 'X-Requested-With': 'XMLHttpRequest' } })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        renderInbox(data.results || []);
        refreshStats();
      })
      .catch(function () { renderInbox([]); });
  }

  function renderInbox(items) {
    var c = document.getElementById('sh-inbox');
    if (!c) return;
    c.innerHTML = '';
    if (!items.length) {
      c.innerHTML = '<div class="none" style="padding:12px">' + esc(_t('sh.inbox_leer', 'Keine Mails')) + '</div>';
      return;
    }
    items.forEach(function (m) {
      var e = document.createElement('div');
      e.className = 'ritem';
      e.innerHTML =
        '<div class="top">' +
        (m.unread ? '<span class="mstat maybe" style="min-width:auto">neu</span>' : '') +
        '<b class="hl" style="' + (m.unread ? '' : 'font-weight:400') + '">' + esc(m.subj) + '</b>' +
        '<span class="src">' + esc(m.box) + '</span><span class="age">' + esc(m.age) + '</span></div>' +
        '<div class="meta"><i class="bi bi-person"></i> ' + esc(m.from) +
        (m.crm && m.crm !== '—' ? ' · <span style="color:var(--abcona-blue-light)"><i class="bi bi-link-45deg"></i>' + esc(m.crm) + '</span>' : '') +
        '</div><div class="meta" style="font-style:italic">„' + esc(m.prev) + '”</div>' +
        '<div class="racts"><button type="button" class="pri sh-mail-task" data-id="' + esc(m.id) + '">' +
        '<i class="bi bi-check2-square"></i> Aufgabe erzeugen</button></div>';
      c.appendChild(e);
    });
    c.querySelectorAll('.sh-mail-task').forEach(function (btn) {
      btn.addEventListener('click', function () {
        toast(_t('sh.toast_mail_task', 'Aufgabe aus Mail erzeugt (Demo)'));
      });
    });
  }

  function loadRadarA() {
    fetch(api('radar/anfragen/?demo=1'), { credentials: 'same-origin', headers: { 'X-Requested-With': 'XMLHttpRequest' } })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        renderRadarA(data.results || []);
        refreshStats();
      })
      .catch(function () { renderRadarA([]); });
  }

  function renderRadarA(items) {
    var c = document.getElementById('sh-radar-a');
    if (!c) return;
    c.innerHTML = '';
    var best = 0;
    items.forEach(function (r) {
      if (r.score > best) best = r.score;
      var e = document.createElement('div');
      e.className = 'ritem';
      e.innerHTML =
        '<div class="top"><span class="score ' + (r.score < 75 ? 'mid' : '') + '">' + esc(r.score) + '%</span>' +
        '<b class="hl">' + esc(r.headline) + '</b>' +
        (r.grp > 1 ? '<span class="grp"><i class="bi bi-stack"></i> ' + r.grp + ' Anbieter</span>' : '') +
        (r.sources || []).map(function (s) { return '<span class="src">' + esc(s) + '</span>'; }).join('') +
        '<span class="age">' + esc(r.age) + '</span></div>' +
        '<div class="meta">' + esc(r.meta) + '</div>' +
        '<div class="chips">' + (r.top || []).map(function (t, i) {
          return '<span class="chip ' + (i === 0 ? 'top' : '') + '"><i class="bi bi-person"></i> ' + esc(t) + '</span>';
        }).join('') + '</div>' +
        '<div class="racts">' +
        '<button type="button" class="pri sh-take"><i class="bi bi-diagram-3"></i> Übernehmen → Matching</button>' +
        '<button type="button" class="sh-dismiss"><i class="bi bi-x-lg"></i> Verwerfen</button></div>';
      c.appendChild(e);
      e.querySelector('.sh-take').onclick = function () {
        toast(_t('sh.toast_takeover', 'Anfrage übernommen — Matching läuft (Demo)'));
        e.remove();
        var n = document.getElementById('r-new');
        if (n) n.textContent = c.querySelectorAll('.ritem').length;
      };
      e.querySelector('.sh-dismiss').onclick = function () {
        toast(_t('sh.toast_dismiss', 'Verworfen (Demo)'));
        e.remove();
        var n = document.getElementById('r-new');
        if (n) n.textContent = c.querySelectorAll('.ritem').length;
      };
    });
    var el = document.getElementById('r-new'); if (el) el.textContent = items.length;
    el = document.getElementById('r-best'); if (el) el.textContent = best ? (best + '%') : '—';
    el = document.getElementById('tb-ra'); if (el) el.textContent = items.length;
  }

  function loadRadarB() {
    fetch(api('radar/berater/?demo=1'), { credentials: 'same-origin', headers: { 'X-Requested-With': 'XMLHttpRequest' } })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        renderRadarB(data.results || []);
        refreshStats();
      })
      .catch(function () { renderRadarB([]); });
  }

  function renderRadarB(items) {
    var c = document.getElementById('sh-radar-b');
    if (!c) return;
    c.innerHTML = '';
    var lbl = { known: '✔ im Bestand', maybe: '? unsicher', new: 'neu entdeckt' };
    items.forEach(function (r) {
      var e = document.createElement('div');
      e.className = 'ritem';
      var acts = '';
      if (r.st === 'maybe') {
        acts = '<button type="button" class="pri sh-confirm"><i class="bi bi-check2"></i> Verknüpfen</button>';
      } else if (r.st === 'new') {
        acts = '<button type="button" class="pri"><i class="bi bi-eye"></i> Beobachten</button>' +
          '<button type="button" class="sh-dismiss"><i class="bi bi-x-lg"></i> Verwerfen</button>';
      } else {
        acts = '<button type="button"><i class="bi bi-person-badge"></i> Profil öffnen</button>';
      }
      e.innerHTML =
        '<div class="top"><span class="mstat ' + esc(r.st) + '">' + esc(lbl[r.st] || r.st) + '</span>' +
        '<b class="hl">' + esc(r.name) + '</b><span class="src">' + esc(r.src) + '</span></div>' +
        '<div class="meta">' + esc(r.meta) + '</div>' +
        '<div class="meta" style="color:var(--status-green)"><i class="bi bi-info-circle"></i> ' + esc(r.note) + '</div>' +
        '<div class="racts">' + acts + '</div>';
      c.appendChild(e);
      var conf = e.querySelector('.sh-confirm');
      if (conf) conf.onclick = function () { toast(_t('sh.toast_link', 'Profil verknüpft (Demo)')); };
      var dis = e.querySelector('.sh-dismiss');
      if (dis) dis.onclick = function () { e.remove(); toast(_t('sh.toast_dismiss', 'Verworfen (Demo)')); };
    });
    var el = document.getElementById('tb-rb'); if (el) el.textContent = items.length;
    var pasteBtn = document.getElementById('sh-radar-paste-btn');
    if (pasteBtn) {
      pasteBtn.onclick = function () {
        toast(_t('sh.toast_paste', 'Parsing + Abgleich (Demo)'));
      };
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
      fetch(api('aufgaben/'), { credentials: 'same-origin', headers: { 'X-Requested-With': 'XMLHttpRequest' } }).then(function (r) { return r.json(); }),
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
      var hint = document.getElementById('sh-demo-hint');
      if (hint) {
        if (data.demo) {
          hint.style.display = 'block';
          hint.textContent = _t(
            'sh.demo_hint',
            'Demo-Daten — UI wie Final-Mockup.'
          );
        } else if (!TASKS.length) {
          hint.style.display = 'block';
          hint.textContent = _t(
            'sh.empty_hint',
            'Keine offenen Aufgaben. Seed: python manage.py seed_shaduler --demo-tasks'
          );
        } else {
          hint.style.display = 'none';
        }
      }
      renderAcc();
      refreshStatsFrom(Object.assign({}, stats, data.stats || {}));
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

  function csrfToken() {
    var m = document.cookie.match(/(?:^|; )csrftoken=([^;]+)/);
    return m ? decodeURIComponent(m[1]) : '';
  }

  function applyResult(r) {
    currentResult = r;
    var fx = document.getElementById('sh-m-fx');
    fx.innerHTML = (r.fx || []).map(function (x) {
      return '<div class="fx-item"><i class="bi bi-check2"></i> ' + esc(x) + '</div>';
    }).join('') || '<div class="none">—</div>';

    var tid = currentTask && currentTask.id;
    var isDemo = !tid || String(tid).indexOf('demo') === 0;

    function finishLocal() {
      if (currentTask && currentTask.id) {
        TASKS = TASKS.filter(function (t) { return t.id !== currentTask.id; });
        STATS.erledigt_heute = (STATS.erledigt_heute || 0) + 1;
        renderAcc();
        refreshStats();
      }
      showPhase('fx');
      toast(_t('sh.toast_erledigt', isDemo ? 'Aufgabe erledigt (Demo)' : 'Aufgabe erledigt'));
    }

    if (isDemo) {
      finishLocal();
      return;
    }

    fetch(api('aufgaben/' + tid + '/ergebnis/'), {
      method: 'POST',
      credentials: 'same-origin',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrfToken(),
        'X-Requested-With': 'XMLHttpRequest',
      },
      body: JSON.stringify({
        code: r.code || '',
        ergebnis_id: r.id || '',
        daten: {},
      }),
    })
      .then(function (res) { return res.json().then(function (j) { return { ok: res.ok, j: j }; }); })
      .then(function (pack) {
        if (pack.j && pack.j.fx && pack.j.fx.length) {
          fx.innerHTML = pack.j.fx.map(function (x) {
            return '<div class="fx-item"><i class="bi bi-check2"></i> ' + esc(x) + '</div>';
          }).join('');
        }
        finishLocal();
      })
      .catch(function () {
        toast(_t('sh.toast_error', 'Speichern fehlgeschlagen'));
        showPhase('fx');
      });
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
