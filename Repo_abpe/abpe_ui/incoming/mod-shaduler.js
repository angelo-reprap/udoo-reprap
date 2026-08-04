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
  var STATS = { heute: 0, ueberfaellig: 0, geplant: 0, erledigt_heute: 0, posteingang: 0 };
  var openGroups = { wiedervorlage: true, anruf: true, intern: true };
  var currentTask = null;
  var currentResult = null;
  var INBOX_ACCOUNT = '';
  var INBOX_ACCOUNTS = [];
  var INBOX_Q = '';
  var INBOX_SORT = 'date_desc';
  var INBOX_ATTACH = ''; // '' | '1' | '0'
  var INBOX_UNREAD = false;
  var INBOX_PAGE = 1;
  var INBOX_PAGE_SIZE = 20;
  var INBOX_TOTAL = 0;
  var INBOX_PAGES = 1;
  var INBOX_ITEMS = [];
  var INBOX_SELECTED = null;
  var EDMS_API = '/edms/api/';

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
        '<div class="sh-pane" data-pane="posteingang"><div class="sh-card sh-inbox-card">' +
        '<div class="card-h"><i class="bi bi-inbox"></i> Posteingang' +
        '<span style="margin-left:auto;font-weight:400;font-size:.8rem;color:var(--text-secondary)">' +
        _t('sh.inbox_hint', 'Verwalten bleibt Outlook · Lese-Überblick') +
        '</span></div>' +
        '<div class="sh-inbox-pager sh-inbox-pager-top" id="sh-inbox-pager"></div>' +
        '<div class="sh-inbox-filters" id="sh-inbox-filters"></div>' +
        '<div class="sh-inbox-toolbar" id="sh-inbox-toolbar"></div>' +
        '<div class="sh-inbox-split">' +
        '<div class="sh-inbox-list-wrap">' +
        '<div class="sh-inbox-list" id="sh-inbox" tabindex="0"></div>' +
        '</div>' +
        '<div class="sh-inbox-viewer" id="sh-inbox-viewer">' +
        '<div class="sh-viewer-empty">' + esc(_t('sh.inbox_pick', 'Mail auswählen')) + '</div>' +
        '</div></div></div></div>'
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
        '<div class="card-h"><i class="bi bi-sliders"></i> ' + _t('sh.tab_regeln', 'Regeln') +
        '<a href="/admin/abpe_shaduler/prozessregel/" target="_blank" rel="noopener" ' +
        'style="margin-left:auto;font-size:.8rem;font-weight:500">' +
        _t('sh.regeln_admin_link', 'Zum Admin öffnen') + '</a></div>' +
        '<p class="sh-hint" data-i18n="sh.regeln_admin_hint">Regeln vorerst im Django-Admin.</p>' +
        '<div id="sh-regeln-list"></div></div></div>'
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
      '<div class="sh-modal">' +
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
    } else if (name === 'regeln') {
      loadRegeln();
    } else {
      refreshStats();
    }
  }

  function loadRegeln() {
    fetch(api('regeln/'), { credentials: 'same-origin', headers: { 'X-Requested-With': 'XMLHttpRequest' } })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        var c = document.getElementById('sh-regeln-list');
        if (!c) return;
        var rows = data.results || [];
        if (!rows.length) {
          c.innerHTML = '<div class="none" style="padding:8px">' + esc(_t('sh.regeln_leer', 'Noch keine Regeln — Seed oder Admin.')) + '</div>';
          return;
        }
        c.innerHTML = rows.map(function (r) {
          return (
            '<div class="ritem" style="margin-bottom:8px">' +
            '<div class="top"><b class="hl">' + esc(r.name) + '</b>' +
            '<span class="src">' + esc(r.ausloeser_typ) + '=' + esc(r.ausloeser_wert) + '</span></div>' +
            '<div class="meta">' + esc(String(r.schritte)) + ' Schritte</div></div>'
          );
        }).join('');
        refreshStats();
      })
      .catch(function () {
        var c = document.getElementById('sh-regeln-list');
        if (c) c.innerHTML = '<div class="none">Fehler beim Laden</div>';
      });
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
          onOpenTask: openModal,
        });
      }
      refreshStats();
    });
  }

  function inboxResetPage() {
    INBOX_PAGE = 1;
  }

  function loadInbox() {
    renderInboxToolbar();
    var q = 'inbox/?page=' + encodeURIComponent(INBOX_PAGE) +
      '&page_size=' + encodeURIComponent(INBOX_PAGE_SIZE);
    if (INBOX_ACCOUNT) q += '&account=' + encodeURIComponent(INBOX_ACCOUNT);
    if (INBOX_Q) q += '&q=' + encodeURIComponent(INBOX_Q);
    if (INBOX_SORT) q += '&sort=' + encodeURIComponent(INBOX_SORT);
    if (INBOX_ATTACH !== '') q += '&has_attachment=' + encodeURIComponent(INBOX_ATTACH);
    if (INBOX_UNREAD) q += '&unread=1';
    fetch(api(q), { credentials: 'same-origin', headers: { 'X-Requested-With': 'XMLHttpRequest' } })
      .then(function (r) { return r.json().then(function (j) { return { ok: r.ok, j: j }; }); })
      .then(function (pack) {
        var data = pack.j || {};
        var c = document.getElementById('sh-inbox');
        var hint = document.querySelector('[data-pane="posteingang"] .card-h span');
        if (!pack.ok || data.ok === false) {
          if (c) {
            c.innerHTML =
              '<div class="none" style="padding:12px">' +
              esc(data.error || _t('sh.inbox_error', 'Posteingang nicht erreichbar (ES/IMAP prüfen).')) +
              '</div>';
          }
          if (hint) hint.textContent = _t('sh.inbox_hint', 'Verwalten bleibt Outlook · Lese-Überblick');
          renderInboxFilters([]);
          renderInboxPager({ total: 0, page: 1, pages: 1, page_size: INBOX_PAGE_SIZE });
          showViewerEmpty();
          refreshStats();
          return;
        }
        if (hint) {
          var src = data.source || '';
          var srcLabel = src === 'elasticsearch' ? 'ES' : (src === 'imap' ? 'IMAP' : (src === 'ingest_email_db' ? 'DB' : src));
          var totalLbl = data.total != null ? (' · ' + data.total + ' ' + _t('sh.inbox_mails', 'Mails')) : '';
          hint.textContent = _t('sh.inbox_hint', 'Verwalten bleibt Outlook · Lese-Überblick') +
            (srcLabel ? ' · ' + srcLabel : '') + totalLbl +
            (data.unread != null ? ' · ' + data.unread + ' ' + _t('sh.inbox_unread', 'neu') : '');
        }
        INBOX_ACCOUNTS = data.accounts || [];
        if (data.filter_account) INBOX_ACCOUNT = data.filter_account;
        INBOX_ITEMS = data.results || [];
        INBOX_TOTAL = data.total != null ? Number(data.total) : INBOX_ITEMS.length;
        INBOX_PAGES = data.pages != null ? Math.max(1, Number(data.pages)) : 1;
        if (data.page != null) INBOX_PAGE = Math.max(1, Number(data.page));
        if (data.page_size != null) INBOX_PAGE_SIZE = Number(data.page_size) || INBOX_PAGE_SIZE;
        if (INBOX_PAGE > INBOX_PAGES && INBOX_TOTAL > 0) {
          INBOX_PAGE = INBOX_PAGES;
          loadInbox();
          return;
        }
        renderInboxFilters(INBOX_ACCOUNTS);
        renderInbox(INBOX_ITEMS);
        renderInboxPager({
          total: INBOX_TOTAL,
          page: INBOX_PAGE,
          pages: INBOX_PAGES,
          page_size: INBOX_PAGE_SIZE,
        });
        setPostBadge(data.unread != null ? data.unread : INBOX_ITEMS.filter(function (m) { return m.unread; }).length);
        refreshStats();
      })
      .catch(function () {
        renderInbox([]);
        renderInboxPager({ total: 0, page: 1, pages: 1, page_size: INBOX_PAGE_SIZE });
        showViewerEmpty();
      });
  }

  function setPostBadge(n) {
    STATS.posteingang = n || 0;
    var el = document.getElementById('tb-post');
    if (el) el.textContent = STATS.posteingang;
  }

  function renderInboxToolbar() {
    var t = document.getElementById('sh-inbox-toolbar');
    if (!t) return;
    var sizes = [5, 10, 20, 50];
    var sizeOpts = sizes.map(function (n) {
      return '<option value="' + n + '"' + (INBOX_PAGE_SIZE === n ? ' selected' : '') + '>' +
        n + '</option>';
    }).join('');
    t.innerHTML =
      '<form class="sh-inbox-search" id="sh-inbox-search">' +
      '<input type="search" id="sh-inbox-q" value="' + esc(INBOX_Q) + '" ' +
      'placeholder="' + esc(_t('sh.inbox_search_ph', 'Betreff, Absender, Text …')) + '" />' +
      '<button type="submit" class="pri"><i class="bi bi-search"></i> ' +
      esc(_t('sh.inbox_search', 'Suchen')) + '</button></form>' +
      '<div class="sh-inbox-opts">' +
      '<select id="sh-inbox-attach">' +
      '<option value="">' + esc(_t('sh.inbox_att_all', 'Anhang: alle')) + '</option>' +
      '<option value="1"' + (INBOX_ATTACH === '1' ? ' selected' : '') + '>' +
      esc(_t('sh.inbox_att_yes', 'nur mit Anhang')) + '</option>' +
      '<option value="0"' + (INBOX_ATTACH === '0' ? ' selected' : '') + '>' +
      esc(_t('sh.inbox_att_no', 'ohne Anhang')) + '</option>' +
      '</select>' +
      '<select id="sh-inbox-sort">' +
      '<option value="date_desc"' + (INBOX_SORT === 'date_desc' ? ' selected' : '') + '>' +
      esc(_t('sh.inbox_sort_new', 'Datum: neueste')) + '</option>' +
      '<option value="date_asc"' + (INBOX_SORT === 'date_asc' ? ' selected' : '') + '>' +
      esc(_t('sh.inbox_sort_old', 'Datum: älteste')) + '</option>' +
      '</select>' +
      '<label class="sh-inbox-pagesize"><span>' + esc(_t('sh.inbox_per_page', 'Anzeigen')) + '</span> ' +
      '<select id="sh-inbox-pagesize">' + sizeOpts + '</select></label>' +
      '<label class="sh-inbox-unread"><input type="checkbox" id="sh-inbox-unread"' +
      (INBOX_UNREAD ? ' checked' : '') + '> ' + esc(_t('sh.inbox_only_new', 'nur neu')) + '</label>' +
      '</div>';
    var form = document.getElementById('sh-inbox-search');
    if (form) {
      form.addEventListener('submit', function (e) {
        e.preventDefault();
        var inp = document.getElementById('sh-inbox-q');
        INBOX_Q = inp ? String(inp.value || '').trim() : '';
        inboxResetPage();
        loadInbox();
      });
    }
    var att = document.getElementById('sh-inbox-attach');
    if (att) att.addEventListener('change', function () {
      INBOX_ATTACH = att.value; inboxResetPage(); loadInbox();
    });
    var sort = document.getElementById('sh-inbox-sort');
    if (sort) sort.addEventListener('change', function () {
      INBOX_SORT = sort.value || 'date_desc'; inboxResetPage(); loadInbox();
    });
    var psz = document.getElementById('sh-inbox-pagesize');
    if (psz) psz.addEventListener('change', function () {
      INBOX_PAGE_SIZE = parseInt(psz.value, 10) || 20;
      inboxResetPage();
      loadInbox();
    });
    var un = document.getElementById('sh-inbox-unread');
    if (un) un.addEventListener('change', function () {
      INBOX_UNREAD = !!un.checked; inboxResetPage(); loadInbox();
    });
  }

  function renderInboxPager(meta) {
    var el = document.getElementById('sh-inbox-pager');
    if (!el) return;
    meta = meta || {};
    var total = Math.max(0, Number(meta.total) || 0);
    var page = Math.max(1, Number(meta.page) || 1);
    var pages = Math.max(1, Number(meta.pages) || 1);
    var size = Math.max(1, Number(meta.page_size) || INBOX_PAGE_SIZE);
    if (!total) {
      el.innerHTML = '<span class="sh-pager-meta">' + esc(_t('sh.inbox_leer', 'Keine Mails')) + '</span>';
      return;
    }
    var from = (page - 1) * size + 1;
    var to = Math.min(total, page * size);
    var win = 5;
    var start = Math.max(1, page - Math.floor(win / 2));
    var end = Math.min(pages, start + win - 1);
    start = Math.max(1, end - win + 1);
    var nums = '';
    for (var i = start; i <= end; i++) {
      nums += '<button type="button" class="sh-pg' + (i === page ? ' on' : '') + '" data-page="' + i + '">' + i + '</button>';
    }
    el.innerHTML =
      '<span class="sh-pager-meta">' + esc(from + '–' + to + ' / ' + total) + '</span>' +
      '<div class="sh-pager-btns">' +
      '<button type="button" class="sh-pg" data-page="' + (page - 1) + '"' +
      (page <= 1 ? ' disabled' : '') + ' aria-label="prev">&lt;</button>' +
      nums +
      '<button type="button" class="sh-pg" data-page="' + (page + 1) + '"' +
      (page >= pages ? ' disabled' : '') + ' aria-label="next">&gt;</button>' +
      '</div>';
    el.querySelectorAll('.sh-pg').forEach(function (btn) {
      btn.addEventListener('click', function () {
        if (btn.disabled) return;
        var p = parseInt(btn.getAttribute('data-page'), 10);
        if (!p || p < 1 || p > pages || p === INBOX_PAGE) return;
        INBOX_PAGE = p;
        loadInbox();
        var list = document.getElementById('sh-inbox');
        if (list) list.scrollTop = 0;
      });
    });
  }

  function renderInboxFilters(accounts) {
    var f = document.getElementById('sh-inbox-filters');
    if (!f) return;
    var chips =
      '<button type="button" class="sh-acc-chip' + (!INBOX_ACCOUNT ? ' on' : '') + '" data-account="">' +
      esc(_t('sh.inbox_all', 'Alle')) + '</button>';
    (accounts || []).forEach(function (a) {
      var label = a.label || a.user || '';
      if (!label || label === '?') return;
      var on = INBOX_ACCOUNT && INBOX_ACCOUNT === label;
      chips +=
        '<button type="button" class="sh-acc-chip' + (on ? ' on' : '') + '" data-account="' + esc(label) + '">' +
        esc(label) + (a.count != null ? ' <span class="n">' + a.count + '</span>' : '') +
        '</button>';
    });
    f.innerHTML = chips;
    f.querySelectorAll('.sh-acc-chip').forEach(function (btn) {
      btn.addEventListener('click', function () {
        INBOX_ACCOUNT = btn.getAttribute('data-account') || '';
        inboxResetPage();
        loadInbox();
      });
    });
  }

  function markMailRead(id, rowEl) {
    if (!id) return;
    fetch(api('inbox/' + encodeURIComponent(id) + '/read/'), {
      method: 'POST',
      credentials: 'same-origin',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrfToken(),
        'X-Requested-With': 'XMLHttpRequest',
      },
      body: '{}',
    })
      .then(function (r) { return r.json(); })
      .then(function (j) {
        if (!(j && j.ok)) return;
        if (rowEl) {
          rowEl.classList.remove('unread');
          var badge = rowEl.querySelector('.mstat.maybe');
          if (badge) badge.remove();
          var hl = rowEl.querySelector('.hl');
          if (hl) hl.style.fontWeight = '400';
        }
        var item = INBOX_ITEMS.filter(function (m) { return m.id === id; })[0];
        if (item && item.unread) {
          item.unread = false;
          if (STATS.posteingang > 0) setPostBadge(STATS.posteingang - 1);
        }
      })
      .catch(function () {});
  }

  function showViewerEmpty() {
    var v = document.getElementById('sh-inbox-viewer');
    if (!v) return;
    v.innerHTML = '<div class="sh-viewer-empty">' + esc(_t('sh.inbox_pick', 'Mail auswählen')) + '</div>';
    INBOX_SELECTED = null;
  }

  function edmsViewUrl(vp) {
    vp = vp || {};
    var qs = 'account=' + encodeURIComponent(vp.account || '') +
      '&folder=' + encodeURIComponent(vp.folder || 'INBOX');
    if (vp.uid) qs += '&uid=' + encodeURIComponent(vp.uid);
    else if (vp.message_id) qs += '&message_id=' + encodeURIComponent(vp.message_id);
    return EDMS_API + 'mail/view/?' + qs;
  }

  function edmsAttachUrl(vp, index, preview) {
    vp = vp || {};
    var qs = 'account=' + encodeURIComponent(vp.account || '') +
      '&folder=' + encodeURIComponent(vp.folder || 'INBOX') +
      '&index=' + encodeURIComponent(String(index));
    if (vp.uid) qs += '&uid=' + encodeURIComponent(vp.uid);
    else if (vp.message_id) qs += '&message_id=' + encodeURIComponent(vp.message_id);
    return EDMS_API + (preview ? 'mail/attachment/preview/?' : 'mail/attachment/?') + qs;
  }

  function openInboxMail(m, rowEl) {
    if (!m) return;
    INBOX_SELECTED = m;
    document.querySelectorAll('#sh-inbox .ritem.on').forEach(function (el) { el.classList.remove('on'); });
    if (rowEl) rowEl.classList.add('on');
    var list = document.getElementById('sh-inbox');
    if (list && document.activeElement !== list &&
        !(document.activeElement && /^(INPUT|TEXTAREA|SELECT|BUTTON)$/.test(document.activeElement.tagName))) {
      try { list.focus({ preventScroll: true }); } catch (e) { list.focus(); }
    }
    if (m.unread) markMailRead(m.id, rowEl);
    var v = document.getElementById('sh-inbox-viewer');
    if (!v) return;
    v.innerHTML = '<div class="sh-viewer-loading">' + esc(_t('sh.loading', 'Laden…')) + '</div>';

    // Primär: ES-Detail (zuverlässig). EDMS danach optional für Anhänge.
    fetch(api('inbox/' + encodeURIComponent(m.id) + '/view/'), {
      credentials: 'same-origin',
      headers: { 'X-Requested-With': 'XMLHttpRequest' },
    })
      .then(function (r) { return r.json().then(function (j) { return { ok: r.ok, j: j }; }); })
      .then(function (pack) {
        var j = pack.j || {};
        if (pack.ok && j.ok) {
          renderViewerDetail(m, j, v, { source: 'es' });
          tryEdmsAttachments(m, v, j);
          return;
        }
        tryEdmsFull(m, v, j.error);
      })
      .catch(function () { tryEdmsFull(m, v, null); });
  }

  function tryEdmsFull(m, v, prevErr) {
    var vp = m.view_params || {
      account: m.account, folder: m.folder || 'INBOX', uid: m.uid, message_id: m.message_id,
    };
    if (!(vp.account && vp.folder && (vp.uid || vp.message_id))) {
      renderViewerFallback(m, v, prevErr || _t('sh.inbox_view_err', 'Mail-Detail nicht ladbar'));
      return;
    }
    fetch(edmsViewUrl(vp), { credentials: 'same-origin', headers: { 'X-Requested-With': 'XMLHttpRequest' } })
      .then(function (r) { return r.json().then(function (j) { return { ok: r.ok, status: r.status, j: j }; }); })
      .then(function (pack) {
        var j = pack.j || {};
        if (pack.ok && j.ok !== false) {
          renderViewerDetail(m, j, v, { source: 'edms' });
          return;
        }
        // uid fehlgeschlagen → message_id erneut versuchen
        if (vp.uid && vp.message_id) {
          var vp2 = Object.assign({}, vp, { uid: '' });
          return fetch(edmsViewUrl(vp2), { credentials: 'same-origin', headers: { 'X-Requested-With': 'XMLHttpRequest' } })
            .then(function (r2) { return r2.json().then(function (j2) { return { ok: r2.ok, j: j2 }; }); })
            .then(function (pack2) {
              if (pack2.ok && pack2.j && pack2.j.ok !== false) {
                renderViewerDetail(m, pack2.j, v, { source: 'edms' });
              } else {
                renderViewerFallback(m, v, (j && j.error) || prevErr || _t('sh.inbox_view_err', 'Mail-Detail nicht ladbar'));
              }
            });
        }
        renderViewerFallback(m, v, (j && j.error) || prevErr || _t('sh.inbox_view_err', 'Mail-Detail nicht ladbar'));
      })
      .catch(function () {
        renderViewerFallback(m, v, prevErr || _t('sh.inbox_view_err', 'Mail-Detail nicht ladbar'));
      });
  }

  function tryEdmsAttachments(m, v, esDetail) {
    var atts = (esDetail && esDetail.attachments) || [];
    if (atts.length) return; // ES hat schon Anhänge-Meta
    var vp = (esDetail && esDetail.view_params) || m.view_params || {
      account: m.account, folder: m.folder || 'INBOX', uid: m.uid, message_id: m.message_id,
    };
    if (!(vp.account && vp.folder && (vp.uid || vp.message_id))) return;
    fetch(edmsViewUrl(vp), { credentials: 'same-origin', headers: { 'X-Requested-With': 'XMLHttpRequest' } })
      .then(function (r) { return r.json().then(function (j) { return { ok: r.ok, j: j }; }); })
      .then(function (pack) {
        var j = pack.j || {};
        if (!pack.ok || j.ok === false) return;
        var edmsAtts = j.attachments || [];
        if (!edmsAtts.length) return;
        // Body aus ES behalten, Anhänge aus EDMS
        var merged = Object.assign({}, esDetail, {
          attachments: edmsAtts,
          hint: undefined,
          source: 'es+edms',
        });
        if (INBOX_SELECTED && INBOX_SELECTED.id === m.id) {
          renderViewerDetail(m, merged, v, { source: 'es+edms' });
        }
      })
      .catch(function () {});
  }

  function renderViewerActions(m, host) {
    host._mail = m;
  }

  function viewerActionsHtml(m) {
    var acts =
      '<button type="button" class="pri sh-mail-task" data-id="' + esc(m.id) + '">' +
      '<i class="bi bi-check2-square"></i> ' + esc(_t('sh.inbox_task', 'Aufgabe erzeugen')) + '</button>';
    if (m.matching_url) {
      acts +=
        '<a class="sh-mail-matching" href="' + esc(m.matching_url) + '">' +
        '<i class="bi bi-diagram-3"></i> ' + esc(_t('sh.inbox_matching', 'Im Matching öffnen')) + '</a>';
    }
    acts +=
      '<a class="sh-mail-studio" href="' + esc(m.email_studio_url || '/email-studio/studio/') + '">' +
      '<i class="bi bi-envelope-at"></i> ' + esc(_t('sh.inbox_reply', 'Antworten (Email Studio)')) + '</a>';
    if (m.mailto_url) {
      acts +=
        '<a class="sh-mail-outlook" href="' + esc(m.mailto_url) + '">' +
        '<i class="bi bi-box-arrow-up-right"></i> ' + esc(_t('sh.inbox_outlook', 'In Outlook öffnen')) + '</a>';
    }
    return '<div class="racts sh-viewer-acts">' + acts + '</div>';
  }

  function bindViewerActions(root, m) {
    if (!root) return;
    var btn = root.querySelector('.sh-mail-task');
    if (btn) {
      btn.addEventListener('click', function () {
        openMailTaskChooser(m);
      });
    }
  }

  function closeMailTaskChooser() {
    var ovl = document.getElementById('sh-mail-task-ovl');
    if (ovl) ovl.remove();
  }

  function extractEmailFromFrom(from) {
    var s = String(from || '');
    var m = s.match(/<([^>]+@[^>]+)>/);
    if (m) return m[1].trim();
    m = s.match(/([^\s<>]+@[^\s<>]+)/);
    return m ? m[1].trim() : '';
  }

  function defaultDueDateTime() {
    var d = new Date();
    d.setMinutes(0, 0, 0);
    d.setHours(d.getHours() + 1);
    var yyyy = d.getFullYear();
    var mm = String(d.getMonth() + 1).padStart(2, '0');
    var dd = String(d.getDate()).padStart(2, '0');
    var hh = String(d.getHours()).padStart(2, '0');
    var mi = String(d.getMinutes()).padStart(2, '0');
    return { date: yyyy + '-' + mm + '-' + dd, time: hh + ':' + mi };
  }

  function renderCrmBlock(host, info) {
    if (!host) return;
    if (info && info.found) {
      var name = info.crm_name || info.crm || '';
      var mod = info.crm_bean_module || '';
      var modLbl = /account/i.test(mod) ? 'Firma' : (/contact/i.test(mod) ? 'Kontakt' : 'CRM');
      host.innerHTML =
        '<div class="sh-crm-hit">' +
        '<div class="sh-crm-hit-top"><i class="bi bi-person-check"></i> ' +
        '<b>' + esc(modLbl) + '</b>' +
        (name ? ': ' + esc(name) : '') + '</div>' +
        (info.crm_url || info.matching_url
          ? '<a class="sh-crm-link" href="' + esc(info.crm_url || info.matching_url) +
            '" target="_blank" rel="noopener">' + esc(_t('sh.inbox_crm_open', 'Datensatz öffnen')) + '</a>'
          : '') +
        '<label class="sh-mail-crm-note">' +
        '<input type="checkbox" id="sh-mt-crm" checked> ' +
        esc(_t('sh.inbox_crm_note', 'Notiz auch am CRM-Kontakt / Firma ablegen')) +
        '</label></div>';
    } else {
      host.innerHTML =
        '<div class="note">' + esc(_t('sh.inbox_crm_unknown',
          'Absender nicht im CRM — Notiz nur an der Aufgabe')) + '</div>';
    }
  }

  function openMailTaskChooser(m) {
    closeMailTaskChooser();
    m = m || {};
    var arts = [
      { id: 'anruf', label: _t('sh.art_anruf', 'Anruf') },
      { id: 'wiedervorlage', label: _t('sh.art_wiedervorlage', 'Wiedervorlage') },
      { id: 'email', label: _t('sh.art_email', 'E-Mail') },
      { id: 'termin', label: _t('sh.art_termin', 'Termin') },
      { id: 'dokument', label: _t('sh.art_dokument', 'Dokument') },
      { id: 'intern', label: _t('sh.art_intern', 'Intern') },
    ];
    var artBtns = arts.map(function (a, i) {
      return '<button type="button" class="sh-pick' + (i === 0 ? ' on' : '') + '" data-art="' + a.id + '">' +
        esc(a.label) + '</button>';
    }).join('');
    var dueDef = defaultDueDateTime();
    var ovl = document.createElement('div');
    ovl.className = 'ovl open';
    ovl.id = 'sh-mail-task-ovl';
    ovl.innerHTML =
      '<div class="sh-modal sh-mail-task-modal">' +
      '<div class="mh">' +
      '<div class="ico"><i class="bi bi-check2-square"></i></div>' +
      '<div><b>' + esc(_t('sh.inbox_task', 'Aufgabe erzeugen')) + '</b>' +
      '<small class="sh-mt-subj">' + esc(m.subj || '') + '</small></div>' +
      '<button type="button" class="x" id="sh-mt-close"><i class="bi bi-x-lg"></i></button>' +
      '</div>' +
      '<div class="mb">' +
      '<div class="excerpt"><div class="lbl">' + esc(_t('sh.inbox_from', 'Von')) + '</div>' +
      esc(m.from || '—') +
      '<div id="sh-mt-crm-box" class="sh-crm-box"><div class="note">' +
      esc(_t('sh.inbox_crm_loading', 'CRM wird geprüft …')) + '</div></div></div>' +
      '<div class="qlbl">' + esc(_t('sh.inbox_pick_art', 'Art')) + '</div>' +
      '<div class="sh-pick-row" id="sh-mt-arts">' + artBtns + '</div>' +
      '<div class="qlbl">' + esc(_t('sh.inbox_pick_due', 'Fälligkeit')) + '</div>' +
      '<div class="sh-due-grid">' +
      '<div class="inp"><label for="sh-mt-date">' + esc(_t('sh.inbox_due_date', 'Tag')) + '</label>' +
      '<input type="date" id="sh-mt-date" value="' + esc(dueDef.date) + '"></div>' +
      '<div class="inp"><label for="sh-mt-time">' + esc(_t('sh.inbox_due_time', 'Uhrzeit')) + '</label>' +
      '<input type="time" id="sh-mt-time" value="' + esc(dueDef.time) + '"></div>' +
      '<div class="inp"><label for="sh-mt-dauer">' + esc(_t('sh.inbox_due_dauer', 'Dauer')) + '</label>' +
      '<select id="sh-mt-dauer">' +
      '<option value="">—</option>' +
      '<option value="15">15 Min</option>' +
      '<option value="30" selected>30 Min</option>' +
      '<option value="45">45 Min</option>' +
      '<option value="60">1 Std</option>' +
      '<option value="90">1,5 Std</option>' +
      '<option value="120">2 Std</option>' +
      '</select></div></div>' +
      '<div class="sh-pick-row sh-due-quick">' +
      '<button type="button" class="sh-pick" data-quick="heute">' + esc(_t('sh.due_heute', 'heute')) + '</button>' +
      '<button type="button" class="sh-pick" data-quick="morgen">' + esc(_t('sh.due_morgen', 'morgen')) + '</button>' +
      '<button type="button" class="sh-pick" data-quick="1h">' + esc(_t('sh.due_1h', 'in 1 Stunde')) + '</button>' +
      '</div>' +
      '<div class="inp"><label for="sh-mt-notiz">' + esc(_t('sh.inbox_notiz', 'Notiz')) + '</label>' +
      '<textarea id="sh-mt-notiz" rows="3" placeholder="' +
      esc(_t('sh.inbox_notiz_ph', 'Kurz notieren, was zu tun ist …')) + '"></textarea></div>' +
      '<button type="button" class="primary" id="sh-mt-save">' +
      '<i class="bi bi-check2"></i> ' + esc(_t('sh.inbox_task_create', 'Aufgabe anlegen')) +
      '</button>' +
      '</div></div>';
    document.body.appendChild(ovl);

    var selectedArt = 'anruf';
    var crmInfo = {
      found: !!(m.crm_bean_id || m.crm_found),
      crm_bean_id: m.crm_bean_id || '',
      crm_bean_module: m.crm_bean_module || '',
      crm_name: m.crm_name || '',
      crm: m.crm || '',
      crm_url: m.crm_url || '',
      matching_url: m.matching_url || '',
    };
    var crmBox = document.getElementById('sh-mt-crm-box');
    if (crmInfo.found) renderCrmBlock(crmBox, crmInfo);
    else if (crmBox) {
      // Live-Lookup Absender
      var email = m.reply_email || extractEmailFromFrom(m.from);
      if (email) {
        fetch(api('inbox/crm-lookup/?email=' + encodeURIComponent(email)), {
          credentials: 'same-origin',
          headers: { 'X-Requested-With': 'XMLHttpRequest' },
        })
          .then(function (r) { return r.json(); })
          .then(function (j) {
            if (j && j.ok && j.found) {
              crmInfo = j;
              m.crm_bean_id = j.crm_bean_id;
              m.crm_bean_module = j.crm_bean_module;
              m.crm_name = j.crm_name;
              m.crm = j.crm;
              m.crm_url = j.crm_url;
              if (j.matching_url) m.matching_url = j.matching_url;
            }
            renderCrmBlock(crmBox, j && j.ok ? j : { found: false });
          })
          .catch(function () { renderCrmBlock(crmBox, { found: false }); });
      } else {
        renderCrmBlock(crmBox, { found: false });
      }
    }

    ovl.querySelectorAll('#sh-mt-arts .sh-pick').forEach(function (b) {
      b.addEventListener('click', function () {
        ovl.querySelectorAll('#sh-mt-arts .sh-pick').forEach(function (x) { x.classList.remove('on'); });
        b.classList.add('on');
        selectedArt = b.getAttribute('data-art') || 'email';
      });
    });
    ovl.querySelectorAll('.sh-due-quick .sh-pick').forEach(function (b) {
      b.addEventListener('click', function () {
        var q = b.getAttribute('data-quick');
        var d = new Date();
        if (q === 'morgen') d.setDate(d.getDate() + 1);
        if (q === '1h') {
          d.setMinutes(0, 0, 0);
          d.setHours(d.getHours() + 1);
        } else {
          d.setHours(9, 0, 0, 0);
        }
        var dateEl = document.getElementById('sh-mt-date');
        var timeEl = document.getElementById('sh-mt-time');
        if (dateEl) {
          dateEl.value = d.getFullYear() + '-' +
            String(d.getMonth() + 1).padStart(2, '0') + '-' +
            String(d.getDate()).padStart(2, '0');
        }
        if (timeEl) {
          timeEl.value = String(d.getHours()).padStart(2, '0') + ':' +
            String(d.getMinutes()).padStart(2, '0');
        }
        ovl.querySelectorAll('.sh-due-quick .sh-pick').forEach(function (x) { x.classList.remove('on'); });
        b.classList.add('on');
      });
    });
    var closeBtn = document.getElementById('sh-mt-close');
    if (closeBtn) closeBtn.onclick = closeMailTaskChooser;
    ovl.addEventListener('click', function (ev) {
      if (ev.target === ovl) closeMailTaskChooser();
    });
    var save = document.getElementById('sh-mt-save');
    if (save) {
      save.onclick = function () {
        var ta = document.getElementById('sh-mt-notiz');
        var crmCb = document.getElementById('sh-mt-crm');
        var dateEl = document.getElementById('sh-mt-date');
        var timeEl = document.getElementById('sh-mt-time');
        var dauerEl = document.getElementById('sh-mt-dauer');
        var payload = {
          art: selectedArt,
          faellig_am: dateEl ? dateEl.value : '',
          faellig_zeit: timeEl ? timeEl.value : '',
          dauer_min: dauerEl && dauerEl.value ? parseInt(dauerEl.value, 10) : null,
          notiz: ta ? String(ta.value || '').trim() : '',
          crm_notiz: crmCb ? !!crmCb.checked : false,
        };
        save.disabled = true;
        fetch(api('inbox/' + encodeURIComponent(m.id) + '/aufgabe/'), {
          method: 'POST',
          credentials: 'same-origin',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken(),
            'X-Requested-With': 'XMLHttpRequest',
          },
          body: JSON.stringify(payload),
        })
          .then(function (r) { return r.json(); })
          .then(function (j) {
            save.disabled = false;
            if (j && j.ok) {
              closeMailTaskChooser();
              var msg = _t('sh.toast_mail_task', 'Aufgabe aus Mail erzeugt');
              if (j.crm_notiz) msg += ' · ' + _t('sh.toast_crm_note', 'CRM-Notiz gesetzt');
              if (j.crm_name) msg += ' · ' + j.crm_name;
              toast(msg);
              TASKS = null;
              markMailRead(m.id, document.querySelector('#sh-inbox .ritem.on'));
            } else {
              toast(_t('sh.toast_error', 'Speichern fehlgeschlagen'));
            }
          })
          .catch(function () {
            save.disabled = false;
            toast(_t('sh.toast_error', 'Speichern fehlgeschlagen'));
          });
      };
    }
  }

  function looksLikeHtml(s) {
    var t = String(s || '');
    // echte Tags — nicht <email@domain> aus Plaintext-Headern
    return /<\s*(html|body|div|p|br|table|tr|td|span|font|h[1-6]|ul|ol|li|blockquote|hr|img|a)\b/i.test(t)
      || /<\s*!(DOCTYPE|----)/i.test(t);
  }

  function plainToReadableHtml(text) {
    var t = String(text || '').replace(/\r\n/g, '\n').replace(/\r/g, '\n').trim();
    if (!t) return '';
    t = t.replace(/[ \t]+\n/g, '\n');
    // Wenig echte Absätze (Index/Quelltext ohne Leerzeilen): Soft-Breaks an typischen Mail-Markern
    var blankCount = (t.match(/\n\s*\n/g) || []).length;
    if (blankCount < 2 && t.length > 120) {
      t = t
        .replace(/\s*(-{3,}|_{3,}|\*{3,})\s*/g, '\n\n$1\n\n')
        .replace(/(^|[\s>])(Von|From|Gesendet|Sent|An|To|Betreff|Subject|Cc|Bcc)\s*:/gi, '$1\n\n$2:')
        .replace(/\s+(Mit freundlichen Grüßen|Viele Grüße|Liebe Grüße|Best regards|Kind regards|Freundliche Grüße)\b/gi, '\n\n$1')
        .replace(/\s+(Hallo\b|Liebe[rn]?\s+\S+|Guten\s+(Tag|Morgen|Abend)\b)/g, '\n\n$1');
    }
    var paras = t.split(/\n\s*\n+/);
    var out = [];
    for (var i = 0; i < paras.length; i++) {
      var p = paras[i].trim();
      if (!p) continue;
      out.push('<p class="sh-p">' + esc(p).replace(/\n/g, '<br>\n') + '</p>');
    }
    return out.join('\n');
  }

  function enhanceHtmlBreaks(html) {
    var s = String(html || '');
    var blocks = (s.match(/<(br|p|div|tr|li|h[1-6]|hr)\b/gi) || []).length;
    // Flaches HTML ohne Absätze, aber mit Newlines → Umbrüche sichtbar machen
    if (blocks < 2 && /\n/.test(s)) {
      s = s.replace(/\r\n/g, '\n').replace(/\r/g, '\n');
      s = s.replace(/\n{2,}/g, '</p><p class="sh-p">');
      s = s.replace(/\n/g, '<br>\n');
      if (s.indexOf('<p') < 0) s = '<p class="sh-p">' + s + '</p>';
    }
    return s;
  }

  function bodyBlockFromDetail(detail, m) {
    var html = detail.body_html || '';
    var plain = detail.body_plain || detail.body || '';
    if (!html && looksLikeHtml(plain)) {
      html = plain;
      plain = '';
    }
    if (!html && !plain && looksLikeHtml(m.prev)) {
      html = m.prev;
    }
    if (!html && !plain && m.prev) {
      plain = m.prev;
    }
    if (html) {
      if (!looksLikeHtml(html)) {
        // fälschlich als HTML markierter Plaintext
        return '<div class="sh-viewer-body sh-readable">' + plainToReadableHtml(html) + '</div>';
      }
      return '<div class="sh-viewer-body sh-html">' +
        enhanceHtmlBreaks(sanitizeMailHtml(html)) + '</div>';
    }
    return '<div class="sh-viewer-body sh-readable">' +
      plainToReadableHtml(plain || '') + '</div>';
  }

  function renderViewerFallback(m, v, errMsg) {
    if (!v) return;
    var body = bodyBlockFromDetail({ body_html: '', body_plain: m.prev || '' }, m);
    v.innerHTML =
      viewerActionsHtml(m) +
      '<div class="sh-viewer-head">' +
      '<div class="from">' + esc(m.from || '—') + '</div>' +
      '<div class="subj">' + esc(m.subj || '') + '</div>' +
      '<div class="meta">' + esc(m.box || m.account || '') +
      (m.age ? ' · ' + esc(m.age) : '') +
      (m.crm && m.crm !== '—' ? ' · ' + esc(m.crm) : '') +
      '</div></div>' +
      (errMsg ? '<div class="sh-viewer-warn">' + esc(errMsg) +
        ' — ' + esc(_t('sh.inbox_es_fallback', 'Vorschau aus Index')) + '</div>' : '') +
      body;
    bindViewerActions(v, m);
  }

  function mergeCrmIntoMail(m, detail) {
    if (!m || !detail) return m;
    ['crm', 'crm_bean_id', 'crm_bean_module', 'crm_name', 'crm_url', 'crm_found',
      'matching_url', 'email_studio_url',
      'mailto_url', 'reply_email', 'request_id'].forEach(function (k) {
      if (detail[k] != null && detail[k] !== '' && (!m[k] || k.indexOf('crm') === 0)) m[k] = detail[k];
    });
    return m;
  }

  function renderViewerDetail(m, detail, v, opts) {
    if (!v) return;
    opts = opts || {};
    m = mergeCrmIntoMail(m, detail);
    var vp = detail.view_params || m.view_params || {
      account: m.account, folder: m.folder || 'INBOX', uid: m.uid, message_id: m.message_id,
    };
    var atts = detail.attachments || detail.anhange || [];
    var attHtml = '';
    if (atts.length) {
      attHtml = '<div class="sh-viewer-atts">' + atts.map(function (a, i) {
        var name = a.filename || a.name || ('anhang_' + i);
        var size = a.size != null ? (' · ' + formatBytes(a.size)) : '';
        var idx = a.index != null ? a.index : i;
        var canEdms = vp.account && vp.folder && (vp.uid || vp.message_id);
        if (canEdms) {
          return (
            '<a class="sh-att" href="' + esc(edmsAttachUrl(vp, idx, false)) + '" target="_blank" rel="noopener">' +
            '<i class="bi bi-paperclip"></i> <span class="n">' + esc(name) + '</span>' +
            '<span class="s">' + esc(size) + '</span>' +
            '<span class="o">' + esc(_t('sh.inbox_open_att', 'öffnen')) + '</span></a>'
          );
        }
        return (
          '<span class="sh-att"><i class="bi bi-paperclip"></i> <span class="n">' + esc(name) + '</span>' +
          '<span class="s">' + esc(size) + '</span></span>'
        );
      }).join('') + '</div>';
    }
    var hint = '';
    if (opts.source === 'es' && detail.hint) {
      hint = '<div class="sh-viewer-hint">' + esc(_t('sh.inbox_from_es', 'Anzeige aus Mail-Index')) + '</div>';
    }
    v.innerHTML =
      viewerActionsHtml(m) +
      '<div class="sh-viewer-head">' +
      '<div class="from">' + esc(detail.from || detail.from_ || m.from || '—') + '</div>' +
      (detail.to || detail.to_ ? '<div class="to">an ' + esc(detail.to || detail.to_) + '</div>' : '') +
      '<div class="subj">' + esc(detail.subject || detail.subj || m.subj || '') + '</div>' +
      '<div class="meta">' +
      esc(detail.date || detail.date_ || m.received_at || m.age || '') +
      (vp.folder ? ' · ' + esc(vp.folder) : '') +
      (m.crm && m.crm !== '—' ? ' · ' + esc(m.crm) : '') +
      '</div></div>' +
      hint + attHtml + bodyBlockFromDetail(detail, m);
    bindViewerActions(v, m);
  }

  function formatBytes(n) {
    n = Number(n) || 0;
    if (n < 1024) return n + ' B';
    if (n < 1048576) return (n / 1024).toFixed(1) + ' KB';
    return (n / 1048576).toFixed(1) + ' MB';
  }

  function sanitizeMailHtml(html) {
    var s = String(html || '');
    s = s.replace(/<script[\s\S]*?<\/script>/gi, '');
    s = s.replace(/<style[\s\S]*?<\/style>/gi, '');
    s = s.replace(/<iframe[\s\S]*?<\/iframe>/gi, '');
    s = s.replace(/<link[\s\S]*?>/gi, '');
    s = s.replace(/\son\w+\s*=\s*(['"]).*?\1/gi, '');
    s = s.replace(/\son\w+\s*=\s*[^\s>]+/gi, '');
    s = s.replace(/\s(style|width|height|bgcolor|background|color)\s*=\s*(['"])[\s\S]*?\2/gi, '');
    s = s.replace(/<(html|body|head)[^>]*>/gi, '').replace(/<\/(html|body|head)>/gi, '');
    return s;
  }

  function renderInbox(items) {
    var c = document.getElementById('sh-inbox');
    if (!c) return;
    c.innerHTML = '';
    if (!items.length) {
      c.innerHTML = '<div class="none" style="padding:12px">' + esc(_t('sh.inbox_leer', 'Keine Mails')) + '</div>';
      showViewerEmpty();
      return;
    }
    items.forEach(function (m, idx) {
      var e = document.createElement('div');
      e.className = 'ritem compact' + (m.unread ? ' unread' : '') +
        (INBOX_SELECTED && INBOX_SELECTED.id === m.id ? ' on' : '');
      e.setAttribute('data-mail-id', m.id || '');
      e.setAttribute('data-idx', String(idx));
      e.setAttribute('role', 'option');
      e.innerHTML =
        '<div class="row1">' +
        '<span class="marks">' +
        (m.unread ? '<span class="mstat maybe">' + esc(_t('sh.inbox_unread', 'neu')) + '</span>' : '') +
        (m.has_attachments ? '<span class="att" title="Anhang"><i class="bi bi-paperclip"></i></span>' : '') +
        '</span>' +
        '<b class="hl">' + esc(m.subj) + '</b>' +
        '<span class="age">' + esc(m.age) + '</span></div>' +
        '<div class="row2">' +
        '<span class="from">' + esc(shortFrom(m.from)) + '</span>' +
        '<span class="src">' + esc(m.box || m.account || '') + '</span>' +
        (m.crm && m.crm !== '—' ? '<span class="crm">' + esc(m.crm) + '</span>' : '') +
        '</div>';
      e.addEventListener('click', function () { openInboxMail(m, e); });
      c.appendChild(e);
    });
    bindInboxKeys(c);
  }

  function shortFrom(from) {
    var s = String(from || '').trim();
    var m = s.match(/^"?([^"<]+)"?\s*</);
    if (m) return m[1].trim();
    return s.length > 42 ? s.slice(0, 40) + '…' : s;
  }

  function bindInboxKeys(listEl) {
    if (!listEl || listEl._keysBound) return;
    listEl._keysBound = true;
    listEl.addEventListener('keydown', function (ev) {
      if (ev.key !== 'ArrowDown' && ev.key !== 'ArrowUp' && ev.key !== 'j' && ev.key !== 'k') return;
      if (ev.target && (ev.target.tagName === 'INPUT' || ev.target.tagName === 'TEXTAREA' || ev.target.tagName === 'SELECT')) return;
      ev.preventDefault();
      var rows = Array.prototype.slice.call(listEl.querySelectorAll('.ritem.compact'));
      if (!rows.length) return;
      var cur = listEl.querySelector('.ritem.on');
      var i = cur ? rows.indexOf(cur) : -1;
      var down = (ev.key === 'ArrowDown' || ev.key === 'j');
      var next = down ? Math.min(rows.length - 1, i + 1) : Math.max(0, i < 0 ? 0 : i - 1);
      var row = rows[next];
      if (!row) return;
      var id = row.getAttribute('data-mail-id');
      var mail = INBOX_ITEMS.filter(function (m) { return m.id === id; })[0];
      if (mail) {
        openInboxMail(mail, row);
        row.scrollIntoView({ block: 'nearest' });
      }
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
    if (b.posteingang != null) STATS.posteingang = b.posteingang;
    var el;
    el = document.getElementById('tb-a'); if (el) el.textContent = b.aufgaben != null ? b.aufgaben : (STATS.heute + STATS.ueberfaellig);
    el = document.getElementById('tb-post'); if (el) el.textContent = b.posteingang != null ? b.posteingang : (STATS.posteingang || 0);
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
          posteingang: ((data.badges || {}).posteingang != null
            ? data.badges.posteingang
            : (STATS.posteingang || 0)),
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
        posteingang: STATS.posteingang || 0,
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
    var actBtn = document.getElementById('sh-m-action');
    if (actBtn) {
      actBtn.onclick = function () {
        if (t.whatsapp_url) {
          window.open(t.whatsapp_url, '_blank', 'noopener');
        }
        showPhase('res');
      };
    }
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
