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
  var INBOX_POLL_MS = 60000;
  var INBOX_POLL_MS_MAX = 180000;
  var inboxPollTimer = null;
  var inboxPollInFlight = false;
  var inboxPollBackoffMs = INBOX_POLL_MS;
  var inboxLastOkAt = null;
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
        '<span class="sh-inbox-meta" style="margin-left:auto;font-weight:400;font-size:.8rem;color:var(--text-secondary);display:flex;align-items:center;gap:10px">' +
        '<span id="sh-inbox-hint">' + _t('sh.inbox_hint', 'Verwalten bleibt Outlook · Lese-Überblick') + '</span>' +
        '<span id="sh-inbox-fresh" class="sh-inbox-fresh" title=""></span>' +
        '<button type="button" class="sh-inbox-refresh" id="sh-inbox-refresh" title="' +
        esc(_t('sh.inbox_refresh', 'Liste aktualisieren')) + '">' +
        '<i class="bi bi-arrow-clockwise"></i></button>' +
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
        '<div class="sh-pane" data-pane="radar_anfragen"><div class="sh-card sh-inbox-card sh-radar-card">' +
        '<div class="card-h"><i class="bi bi-broadcast"></i> ' +
        esc(_t('sh.tab_radar_a', 'Radar — Anfragen')) +
        '<span class="sh-inbox-meta" style="margin-left:auto;font-weight:400;font-size:.8rem;color:var(--text-secondary);display:flex;align-items:center;gap:10px;flex-wrap:wrap">' +
        '<span id="sh-radar-hint">' + esc(_t('sh.radar_hint', 'Freelancermap + Gulp + Hays')) + '</span>' +
        '<span id="r-new" class="sh-radar-count">0</span>' +
        '<button type="button" class="sh-inbox-refresh" id="sh-radar-refresh" title="' +
        esc(_t('sh.radar_refresh', 'Quellen aktualisieren')) + '">' +
        '<i class="bi bi-arrow-clockwise"></i></button>' +
        '</span></div>' +
        '<div class="sh-inbox-toolbar" id="sh-radar-toolbar"></div>' +
        '<div class="sh-inbox-split">' +
        '<div class="sh-inbox-list-wrap">' +
        '<div class="sh-inbox-pager sh-inbox-pager-top" id="sh-radar-pager"></div>' +
        '<div class="sh-inbox-list" id="sh-radar-list" tabindex="0"></div>' +
        '</div>' +
        '<div class="sh-inbox-viewer" id="sh-radar-viewer">' +
        '<div class="sh-viewer-empty">' + esc(_t('sh.radar_pick', 'Projekt auswählen')) + '</div>' +
        '</div></div></div></div>'
      );
    }
    if (name === 'radar_berater') {
      return (
        '<div class="sh-pane" data-pane="radar_berater"><div class="sh-card sh-inbox-card sh-radar-card">' +
        '<div class="card-h"><i class="bi bi-person-bounding-box"></i> ' +
        esc(_t('sh.tab_radar_b', 'Radar — Berater')) +
        '<span class="sh-inbox-meta" style="margin-left:auto;font-weight:400;font-size:.8rem;color:var(--text-secondary);display:flex;align-items:center;gap:10px;flex-wrap:wrap">' +
        '<span id="sh-radar-b-hint">' + esc(_t('sh.radar_b_hint', 'Gulp / Freelancermap')) + '</span>' +
        '<span id="r-b-new" class="sh-radar-count">0</span>' +
        '<button type="button" class="sh-inbox-refresh" id="sh-radar-b-refresh" title="' +
        esc(_t('sh.radar_b_refresh', 'Index aktualisieren (CRM→ES)')) + '">' +
        '<i class="bi bi-arrow-clockwise"></i></button>' +
        '</span></div>' +
        '<div class="paste" style="display:flex;gap:8px;padding:8px 12px;border-bottom:1px solid var(--border-color,#eee);flex-wrap:wrap">' +
        '<input id="sh-radar-paste" class="matching-form-input" style="flex:1;min-width:160px" ' +
        'placeholder="' + esc(_t('sh.radar_b_paste_ph', 'Gulp-ID / Talentfinder- oder Freelancermap-URL …')) + '">' +
        '<button type="button" class="matching-btn-sm" id="sh-radar-paste-btn">' +
        '<i class="bi bi-plus-lg"></i> ' + esc(_t('sh.radar_b_paste', 'Übernehmen')) + '</button>' +
        '<button type="button" class="matching-btn-sm" id="sh-radar-b-seed" title="' +
        esc(_t('sh.radar_b_seed_title', 'CRM-Kontakte mit gulp_id in Radar laden')) + '">' +
        '<i class="bi bi-database-down"></i> ' + esc(_t('sh.radar_b_seed', 'CRM-Seed')) + '</button>' +
        '<button type="button" class="matching-btn-sm" id="sh-radar-b-gulp-refresh" title="' +
        esc(_t('sh.radar_b_gulp_title', 'Gulp: Existenz + Verfügbarkeit prüfen (Batch)')) + '">' +
        '<i class="bi bi-cloud-arrow-down"></i> ' +
        esc(_t('sh.radar_b_gulp_refresh', 'Gulp aktualisieren')) + '</button>' +
        '<button type="button" class="matching-btn-sm" id="sh-radar-b-gulp-available" title="' +
        esc(_t('sh.radar_b_gulp_av_title', 'Talentfinder: aktuell verfügbare Berater einlesen')) + '">' +
        '<i class="bi bi-people"></i> ' +
        esc(_t('sh.radar_b_gulp_available', 'Verfügbare von Gulp')) + '</button>' +
        '<button type="button" class="matching-btn-sm" id="sh-radar-b-fl-available" title="' +
        esc(_t('sh.radar_b_fl_av_title', 'Freelancermap: verfügbare Freelancer einlesen')) + '">' +
        '<i class="bi bi-people-fill"></i> ' +
        esc(_t('sh.radar_b_fl_available', 'Verfügbare von Freelancermap')) + '</button></div>' +
        '<div class="sh-inbox-toolbar" id="sh-radar-b-toolbar"></div>' +
        '<div class="sh-inbox-split">' +
        '<div class="sh-inbox-list-wrap">' +
        '<div class="sh-inbox-pager sh-inbox-pager-top" id="sh-radar-b-pager"></div>' +
        '<div class="sh-inbox-list" id="sh-radar-b-list" tabindex="0"></div>' +
        '</div>' +
        '<div class="sh-inbox-viewer" id="sh-radar-b-viewer">' +
        '<div class="sh-viewer-empty">' + esc(_t('sh.radar_b_pick', 'Berater auswählen')) + '</div>' +
        '</div></div></div></div>'
      );
    }
    if (name === 'regeln') {
      return (
        '<div class="sh-pane" data-pane="regeln"><div class="sh-card">' +
        '<div class="card-h"><i class="bi bi-gear-wide-connected"></i> ' + _t('sh.tab_regeln', 'Regeln') +
        '</div>' +
        '<div id="sh-art-defaults" class="sh-art-defaults"></div>' +
        '<p class="sh-hint" data-i18n="sh.regeln_matching_hint">' +
        esc(_t('sh.regeln_matching_hint',
          'Automations-Regeln (Angebot/Vertrag/…) gehören zum Matching — nicht hier.')) +
        '</p></div></div>'
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
      '<div class="sh-m-wa" id="sh-m-wa" style="display:none">' +
      '<label class="qlbl" for="sh-m-wa-phone">' + _t('sh.wa_telefon', 'Telefon') + '</label>' +
      '<input type="tel" id="sh-m-wa-phone" class="sh-m-wa-phone" placeholder="0049…" autocomplete="tel" />' +
      '<div class="sh-m-wa-phone-meta" id="sh-m-wa-phone-meta"></div>' +
      '<div class="sh-pick-row" id="sh-m-wa-phone-sugs"></div>' +
      '<label class="qlbl" for="sh-m-wa-text">' + _t('sh.wa_nachricht', 'Nachricht') + '</label>' +
      '<textarea id="sh-m-wa-text" class="sh-m-wa-text" rows="5"></textarea>' +
      '<button type="button" class="primary wa" id="sh-m-wa-send">' +
      '<i class="bi bi-whatsapp"></i> ' + _t('sh.wa_versenden', 'Versenden') + '</button>' +
      '<div class="note" id="sh-m-wa-note"></div>' +
      '</div>' +
      '<button type="button" class="primary" id="sh-m-action"></button>' +
      '<div class="note" id="sh-m-actnote"></div>' +
      '<div class="sh-m-quick" id="sh-m-quick">' +
      '<button type="button" class="sh-m-qbtn" id="sh-m-erledigt">' +
      '<i class="bi bi-check2-circle"></i> ' + _t('sh.erg_erledigt', 'Erledigt') + '</button>' +
      '<button type="button" class="sh-m-qbtn" id="sh-m-verschieben">' +
      '<i class="bi bi-calendar-plus"></i> ' + _t('sh.verschieben', 'Verschieben') + '</button>' +
      '</div>' +
      '<div class="sh-m-snooze" id="sh-m-snooze" style="display:none">' +
      '<div class="qlbl">' + _t('sh.verschieben_wahl', 'Verschieben um') + '</div>' +
      '<div class="sh-pick-row" id="sh-m-snooze-opts"></div>' +
      '</div>' +
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
    stopInboxPoll();
    if (typeof stopRadarPoll === 'function') stopRadarPoll();
    if (typeof stopRadarBPoll === 'function') stopRadarBPoll();
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
      startInboxPoll();
    } else if (name === 'radar_anfragen') {
      loadRadarA();
      startRadarPoll();
    } else if (name === 'radar_berater') {
      loadRadarB();
      startRadarBPoll();
    } else if (name === 'regeln') {
      loadRegeln();
    } else {
      refreshStats();
    }
  }


  function renderArtDefaultsEditor() {
    var host = document.getElementById('sh-art-defaults');
    if (!host) return;

    function numCell(art, key, label, val) {
      return (
        '<label class="sh-art-def-cell">' +
        '<span>' + esc(label) + '</span>' +
        '<input type="number" min="0" max="99" step="1" inputmode="numeric" ' +
        'class="sh-art-def-num" data-art="' + esc(art) + '" data-key="' + key + '" ' +
        'value="' + esc(String(val)) + '" aria-label="' + esc(label) + '">' +
        '</label>'
      );
    }

    var head =
      '<div class="sh-art-def-row sh-art-def-row--head">' +
      '<div class="sh-art-def-name"></div>' +
      '<div class="sh-art-def-nums">' +
      '<span>Woche</span><span>Tag</span><span>Stunde</span><span>Minute</span>' +
      '</div></div>';

    var rows = TASK_ART_DEFAULT_ORDER.map(function (art) {
      var label = _t(TASK_ART_DEFAULT_LABEL_KEYS[art] || '', TASK_ART_DEFAULT_LABELS[art] || art);
      var def = getArtDefaults(art);
      var en = !!def.enabled;
      return (
        '<div class="sh-art-def-row" data-art="' + esc(art) + '">' +
        '<div class="sh-art-def-name">' +
        '<div>' + esc(label) + '</div>' +
        '<label class="sh-art-def-none">' +
        '<input type="checkbox" class="sh-art-def-enabled" data-art="' + esc(art) + '"' +
        (en ? '' : ' checked') + '> kein Default</label>' +
        '</div>' +
        '<div class="sh-art-def-nums' + (en ? '' : ' is-off') + '">' +
        numCell(art, 'weeks', 'Woche', def.weeks) +
        numCell(art, 'days', 'Tag', def.days) +
        numCell(art, 'hours', 'Stunde', def.hours) +
        numCell(art, 'minutes', 'Minute', def.minutes) +
        '</div></div>'
      );
    }).join('');

    host.innerHTML =
      '<div class="sh-art-defaults-h">' +
      '<b>' + esc(_t('sh.art_defaults_title', 'Neue Aufgabe — Defaults je Art')) + '</b>' +
      '<span class="sh-art-defaults-hint">' +
      esc(_t('sh.art_defaults_hint',
        'Offset ab jetzt: Woche + Tag + Stunde + Minute → Fälligkeit. Danach im Dialog weiter editierbar.')) +
      '</span></div>' +
      '<div class="sh-art-def-list">' + head + rows + '</div>' +
      '<div class="sh-art-def-actions">' +
      '<button type="button" class="sh-btn sh-btn-primary" id="sh-art-def-save">' +
      esc(_t('sh.art_defaults_save', 'Defaults speichern')) + '</button>' +
      '<button type="button" class="sh-btn" id="sh-art-def-reset">' +
      esc(_t('sh.art_defaults_reset', 'Werkseinstellungen')) + '</button>' +
      '<span class="sh-art-def-status" id="sh-art-def-status"></span></div>';

    function syncRowEnabled(row) {
      if (!row) return;
      var cb = row.querySelector('.sh-art-def-enabled');
      var nums = row.querySelector('.sh-art-def-nums');
      var off = !!(cb && cb.checked);
      if (nums) nums.classList.toggle('is-off', off);
      row.querySelectorAll('.sh-art-def-num').forEach(function (inp) {
        inp.disabled = off;
      });
    }

    host.querySelectorAll('.sh-art-def-row[data-art]').forEach(syncRowEnabled);
    host.querySelectorAll('.sh-art-def-enabled').forEach(function (cb) {
      cb.addEventListener('change', function () {
        syncRowEnabled(cb.closest('.sh-art-def-row'));
      });
    });

    var status = document.getElementById('sh-art-def-status');
    var saveBtn = document.getElementById('sh-art-def-save');
    var resetBtn = document.getElementById('sh-art-def-reset');

    if (saveBtn) {
      saveBtn.onclick = function () {
        var next = {};
        host.querySelectorAll('.sh-art-def-row[data-art]').forEach(function (row) {
          var art = row.getAttribute('data-art');
          var none = !!(row.querySelector('.sh-art-def-enabled') || {}).checked;
          if (none) {
            next[art] = { weeks: 0, days: 0, hours: 0, minutes: 0, enabled: false };
            return;
          }
          var read = function (key) {
            var el = row.querySelector('.sh-art-def-num[data-key="' + key + '"]');
            var n = el ? parseInt(el.value, 10) : 0;
            if (isNaN(n) || n < 0) n = 0;
            if (el) el.value = String(n);
            return n;
          };
          var pack = {
            weeks: read('weeks'),
            days: read('days'),
            hours: read('hours'),
            minutes: read('minutes'),
            enabled: true,
          };
          if (pack.weeks + pack.days + pack.hours + pack.minutes === 0) {
            pack.enabled = false;
            var cb = row.querySelector('.sh-art-def-enabled');
            if (cb) cb.checked = true;
            syncRowEnabled(row);
          }
          next[art] = pack;
        });
        saveArtDefaultsOverride(next);
        if (status) {
          status.textContent = _t(
            'sh.art_defaults_saved',
            'Gespeichert. Gilt ab der nächsten „Neue Aufgabe“ / Outreach-WV.'
          );
        }
      };
    }
    if (resetBtn) {
      resetBtn.onclick = function () {
        saveArtDefaultsOverride(null);
        renderArtDefaultsEditor();
        var st = document.getElementById('sh-art-def-status');
        if (st) st.textContent = _t('sh.art_defaults_restored', 'Werkseinstellungen wiederhergestellt.');
      };
    }
  }

  function loadRegeln() {
    renderArtDefaultsEditor();
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

  function inboxIsBusy() {
    // Aufgabe-Dialog / andere Overlays / aktive Eingabe → kein Soft-Reload
    if (document.getElementById('sh-mail-task-ovl')) return true;
    var ovl = document.getElementById('sh-ovl');
    if (ovl && ovl.style.display && ovl.style.display !== 'none') return true;
    if (document.querySelector('.ovl.open')) return true;
    var ae = document.activeElement;
    if (ae && /^(INPUT|TEXTAREA|SELECT)$/.test(ae.tagName)) {
      if (ae.closest && (ae.closest('#shaduler-root') || ae.closest('#sh-mail-task-ovl'))) return true;
    }
    return false;
  }

  function inboxTabActive() {
    var tab = document.querySelector('#shaduler-root .mtab.on');
    return !!(tab && tab.getAttribute('data-t') === 'posteingang');
  }

  function updateInboxFresh(ok) {
    var el = document.getElementById('sh-inbox-fresh');
    if (!el) return;
    if (ok) {
      inboxLastOkAt = new Date();
      inboxPollBackoffMs = INBOX_POLL_MS;
      el.classList.remove('stale');
    } else {
      el.classList.add('stale');
    }
    if (!inboxLastOkAt) {
      el.textContent = '';
      return;
    }
    var hh = String(inboxLastOkAt.getHours()).padStart(2, '0');
    var mm = String(inboxLastOkAt.getMinutes()).padStart(2, '0');
    el.textContent = ok
      ? (_t('sh.inbox_fresh', 'aktualisiert') + ' ' + hh + ':' + mm)
      : (_t('sh.inbox_stale', 'veraltet') + ' · ' + hh + ':' + mm);
  }

  function scheduleInboxPoll(delayMs) {
    stopInboxPoll();
    if (!inboxTabActive()) return;
    var ms = Math.max(INBOX_POLL_MS, Math.min(INBOX_POLL_MS_MAX, delayMs || inboxPollBackoffMs));
    inboxPollTimer = setTimeout(function () {
      inboxPollTimer = null;
      if (!inboxTabActive()) return;
      if (document.visibilityState === 'hidden') {
        scheduleInboxPoll(INBOX_POLL_MS);
        return;
      }
      loadInbox({ soft: true });
    }, ms);
  }

  function startInboxPoll() {
    inboxPollBackoffMs = INBOX_POLL_MS;
    scheduleInboxPoll(INBOX_POLL_MS);
    var btn = document.getElementById('sh-inbox-refresh');
    if (btn && !btn._bound) {
      btn._bound = true;
      btn.addEventListener('click', function () {
        inboxPollBackoffMs = INBOX_POLL_MS;
        loadInbox({ soft: false });
      });
    }
    if (!document._shInboxVisBound) {
      document._shInboxVisBound = true;
      document.addEventListener('visibilitychange', function () {
        if (document.visibilityState === 'visible' && inboxTabActive()) {
          scheduleInboxPoll(2000);
        }
      });
    }
  }

  function stopInboxPoll() {
    if (inboxPollTimer) {
      clearTimeout(inboxPollTimer);
      inboxPollTimer = null;
    }
  }

  function loadInbox(opts) {
    opts = opts || {};
    var soft = !!opts.soft;
    if (soft && inboxPollInFlight) return;
    if (soft && inboxIsBusy()) {
      scheduleInboxPoll(inboxPollBackoffMs);
      return;
    }
    if (!soft) renderInboxToolbar();
    inboxPollInFlight = true;
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
        inboxPollInFlight = false;
        if (soft && inboxIsBusy()) {
          scheduleInboxPoll(inboxPollBackoffMs);
          return;
        }
        var data = pack.j || {};
        var c = document.getElementById('sh-inbox');
        var hint = document.getElementById('sh-inbox-hint') ||
          document.querySelector('[data-pane="posteingang"] .card-h #sh-inbox-hint');
        if (!pack.ok || data.ok === false) {
          if (soft) {
            inboxPollBackoffMs = Math.min(INBOX_POLL_MS_MAX, inboxPollBackoffMs * 2);
            updateInboxFresh(false);
            scheduleInboxPoll(inboxPollBackoffMs);
            return;
          }
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
          var staleHint = (data.hint && String(data.hint).trim())
            ? (' · ⚠ ' + String(data.hint).trim())
            : '';
          hint.textContent = _t('sh.inbox_hint', 'Verwalten bleibt Outlook · Lese-Überblick') +
            (srcLabel ? ' · ' + srcLabel : '') + totalLbl +
            (data.unread != null ? ' · ' + data.unread + ' ' + _t('sh.inbox_unread', 'neu') : '') +
            staleHint;
          if (staleHint) hint.title = String(data.hint);
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
          inboxPollInFlight = false;
          loadInbox(opts);
          return;
        }
        if (!soft) renderInboxFilters(INBOX_ACCOUNTS);
        if (INBOX_SELECTED && INBOX_SELECTED.id) {
          var fresh = INBOX_ITEMS.filter(function (m) { return m.id === INBOX_SELECTED.id; })[0];
          if (fresh) INBOX_SELECTED = fresh;
        }
        renderInbox(INBOX_ITEMS, { soft: soft });
        renderInboxPager({
          total: INBOX_TOTAL,
          page: INBOX_PAGE,
          pages: INBOX_PAGES,
          page_size: INBOX_PAGE_SIZE,
        });
        setPostBadge(data.unread != null ? data.unread : INBOX_ITEMS.filter(function (m) { return m.unread; }).length);
        refreshStats();
        updateInboxFresh(true);
        if (inboxTabActive()) scheduleInboxPoll(INBOX_POLL_MS);
      })
      .catch(function () {
        inboxPollInFlight = false;
        if (soft) {
          inboxPollBackoffMs = Math.min(INBOX_POLL_MS_MAX, inboxPollBackoffMs * 2);
          updateInboxFresh(false);
          scheduleInboxPoll(inboxPollBackoffMs);
          return;
        }
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
    renderShPager({
      elId: 'sh-inbox-pager',
      total: meta && meta.total,
      page: meta && meta.page,
      pages: meta && meta.pages,
      page_size: meta && meta.page_size,
      emptyLabel: _t('sh.inbox_leer', 'Keine Mails'),
      onPage: function (p) {
        if (p === INBOX_PAGE) return;
        INBOX_PAGE = p;
        loadInbox();
        var list = document.getElementById('sh-inbox');
        if (list) list.scrollTop = 0;
      },
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
    acts +=
      '<button type="button" class="sh-mail-matching" data-id="' + esc(m.id || '') + '">' +
      '<i class="bi bi-diagram-3"></i> ' + esc(_t('sh.inbox_matching', 'Matching')) + '</button>';
    acts +=
      '<button type="button" class="sh-mail-reply" data-id="' + esc(m.id || '') + '">' +
      '<i class="bi bi-envelope-at"></i> ' + esc(_t('sh.inbox_reply', 'Antworten (Email Studio)')) + '</button>';
    if (m.mailto_url) {
      acts +=
        '<a class="sh-mail-outlook" href="' + esc(m.mailto_url) + '">' +
        '<i class="bi bi-box-arrow-up-right"></i> ' + esc(_t('sh.inbox_outlook', 'In Outlook öffnen')) + '</a>';
    }
    return '<div class="racts sh-viewer-acts">' + acts + '</div>';
  }

  function stripHtmlToPlain(html) {
    var d = document.createElement('div');
    try {
      d.innerHTML = sanitizeMailHtml(html) || String(html || '');
    } catch (e) {
      d.textContent = String(html || '');
    }
    return String(d.innerText || d.textContent || '')
      .replace(/\u00a0/g, ' ')
      .replace(/[ \t]+\n/g, '\n')
      .replace(/\n{3,}/g, '\n\n')
      .trim();
  }

  function mailPlainBody(m, detail) {
    detail = detail || (m && m._detail) || {};
    var plain = detail.body_plain || detail.body || detail.text || detail.content || '';
    var html = detail.body_html || detail.html || '';
    if (plain && !looksLikeHtml(plain)) return String(plain).trim();
    if (html) return stripHtmlToPlain(html);
    if (plain) return stripHtmlToPlain(plain);
    return String((m && m.prev) || '').trim();
  }

  function buildFullEmailForMatching(m, detail) {
    detail = detail || (m && m._detail) || {};
    var from = detail.from || detail.from_ || (m && m.from) || '';
    var to = detail.to || detail.to_ || '';
    var subject = detail.subject || detail.subj || (m && m.subj) || '';
    var date = detail.date || detail.date_ || (m && (m.received_at || m.age)) || '';
    var body = mailPlainBody(m, detail);
    var parts = [];
    if (from) parts.push('From: ' + from);
    if (to) parts.push('To: ' + to);
    if (date) parts.push('Date: ' + date);
    if (subject) parts.push('Subject: ' + subject);
    if (parts.length) parts.push('');
    parts.push(body || '');
    return parts.join('\n').trim();
  }

  function ensureMailDetail(m, done) {
    var existing = (m && m._detail) || null;
    if (existing && (existing.body_plain || existing.body_html || existing.body || existing.text)) {
      done(existing);
      return;
    }
    if (!(m && m.id)) {
      done(existing || {});
      return;
    }
    fetch(api('inbox/' + encodeURIComponent(m.id) + '/view/'), {
      credentials: 'same-origin',
      headers: { 'X-Requested-With': 'XMLHttpRequest' },
    })
      .then(function (r) { return r.json().then(function (j) { return { ok: r.ok, j: j }; }); })
      .then(function (pack) {
        var j = pack.j || {};
        if (pack.ok && j.ok) {
          m._detail = j;
          done(j);
          return;
        }
        done(existing || {});
      })
      .catch(function () { done(existing || {}); });
  }

  function openMatchingKiWizardFromMail(m) {
    if (!m) return;
    var btn = document.querySelector('.sh-mail-matching');
    if (btn) {
      btn.disabled = true;
      btn.innerHTML = '<i class="bi bi-hourglass-split"></i> …';
    }
    ensureMailDetail(m, function (detail) {
      var emailText = buildFullEmailForMatching(m, detail);
      var subject = (detail && (detail.subject || detail.subj)) || m.subj || '';
      var outerFrom = (detail && (detail.from || detail.from_)) || m.from || '';
      try {
        sessionStorage.setItem('matching_ki_from_mail', JSON.stringify({
          email_text: emailText,
          subject: subject,
          outer_from: outerFrom,
          from_mail: m.id || '',
        }));
      } catch (e) { /* ignore quota */ }
      var url = '/matching/?tab=neu';
      if (m.id) url += '&from_mail=' + encodeURIComponent(m.id);
      window.location.href = url;
    });
  }

  function bindViewerActions(root, m) {
    if (!root) return;
    var btn = root.querySelector('.sh-mail-task');
    if (btn) {
      btn.addEventListener('click', function () {
        openMailTaskChooser(m);
      });
    }
    var matchBtn = root.querySelector('.sh-mail-matching');
    if (matchBtn) {
      matchBtn.addEventListener('click', function (e) {
        e.preventDefault();
        openMatchingKiWizardFromMail(m);
      });
    }
    var replyBtn = root.querySelector('.sh-mail-reply');
    if (replyBtn) {
      replyBtn.addEventListener('click', function (e) {
        e.preventDefault();
        openMailReplyComposer(m);
      });
    }
  }

  function closeMailTaskChooser() {
    var ovl = document.getElementById('sh-mail-task-ovl');
    if (ovl) ovl.remove();
  }

  function closeMailReplyComposer() {
    var ovl = document.getElementById('sh-mail-reply-ovl');
    if (ovl) ovl.remove();
  }

  function parseDisplayNameFromFrom(from) {
    var s = String(from || '').trim();
    if (!s) return '';
    var m = s.match(/^"?([^"<]+)"?\s*</);
    var n = m ? m[1].trim() : '';
    if (!n) return '';
    if (n.indexOf(',') >= 0) {
      var parts = n.split(',').map(function (x) { return x.trim(); }).filter(Boolean);
      if (parts.length >= 2) return parts[1] + ' ' + parts[0];
    }
    return n;
  }

  function guessContactFirstLast(fullName) {
    var n = String(fullName || '').trim();
    if (!n) return { first: '', last: '', display: '' };
    var parts = n.split(/\s+/).filter(Boolean);
    if (parts.length === 1) return { first: '', last: parts[0], display: parts[0] };
    return {
      first: parts[0],
      last: parts.slice(1).join(' '),
      display: n,
    };
  }

  function buildAnfrageAckBody(anrede, name) {
    var n = String(name || '').trim();
    var greet;
    if (anrede === 'frau') {
      greet = n ? ('Sehr geehrte Frau ' + n + ',') : 'Sehr geehrte Damen und Herren,';
    } else if (anrede === 'damen') {
      greet = 'Sehr geehrte Damen und Herren,';
    } else if (anrede === 'neutral') {
      greet = n ? ('Sehr geehrte/r ' + n + ',') : 'Sehr geehrte Damen und Herren,';
    } else {
      greet = n ? ('Sehr geehrter Herr ' + n + ',') : 'Sehr geehrte Damen und Herren,';
    }
    return (
      greet + '\n\n' +
      'vielen Dank für Ihre Anfrage.\n\n' +
      'Wir werden Ihnen diesbezüglich schnellstmöglich Beratervorschläge unterbreiten.\n\n' +
      'Mit freundlichen Grüßen'
    );
  }

  function bodyTextToHtml(text) {
    return String(text || '')
      .replace(/\r\n/g, '\n')
      .replace(/\r/g, '\n')
      .split('\n')
      .map(function (line) { return esc(line); })
      .join('<br>\n');
  }

  function formatReplyStamp(d) {
    d = d || new Date();
    var dd = String(d.getDate()).padStart(2, '0');
    var mm = String(d.getMonth() + 1).padStart(2, '0');
    var yyyy = d.getFullYear();
    var hh = String(d.getHours()).padStart(2, '0');
    var mi = String(d.getMinutes()).padStart(2, '0');
    return dd + '.' + mm + '.' + yyyy + ', ' + hh + ':' + mi;
  }

  function tomorrowDueDateTime() {
    var d = new Date();
    d.setDate(d.getDate() + 1);
    d.setHours(9, 0, 0, 0);
    return {
      date: d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0'),
      time: '09:00',
    };
  }

  function currentUserEmailHint() {
    var cfg = window.ABPE_CONFIG || {};
    return String(
      (cfg.user && (cfg.user.email || cfg.user.username)) ||
      cfg.user_email || cfg.email || cfg.username || ''
    ).trim().toLowerCase();
  }

  var EMAIL_ADDR_RE = /[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}/g;

  function normalizeEmailAddr(email) {
    return String(email || '').trim().toLowerCase().replace(/^<|>$/g, '');
  }

  function isIgnorableEmail(email) {
    email = normalizeEmailAddr(email);
    if (!email || email.indexOf('@') < 0) return true;
    return /^(noreply|no-reply|donotreply|mailer-daemon|postmaster|notifications?)@/i.test(email);
  }

  function guessNameNearEmail(text, email) {
    var s = String(text || '');
    var idx = s.toLowerCase().indexOf(String(email || '').toLowerCase());
    if (idx < 0) return '';
    var before = s.slice(Math.max(0, idx - 80), idx).replace(/\s+/g, ' ').trim();
    // "Tristan Treder <email>" or "Tristan Treder\nemail"
    var m = before.match(/([A-ZÄÖÜ][a-zäöüßA-ZÄÖÜ\-]+(?:\s+[A-ZÄÖÜ][a-zäöüßA-ZÄÖÜ\-]+){0,3})\s*[<\(\[:]?\s*$/);
    if (m) return m[1].trim();
    m = before.match(/([A-ZÄÖÜ][a-zäöüßA-ZÄÖÜ\-]+,\s*[A-ZÄÖÜ][a-zäöüßA-ZÄÖÜ\-]+)\s*$/);
    if (m) {
      var parts = m[1].split(',').map(function (x) { return x.trim(); });
      if (parts.length >= 2) return parts[1] + ' ' + parts[0];
      return m[1];
    }
    return '';
  }

  function addEmailCandidate(map, email, name, source) {
    email = normalizeEmailAddr(email);
    if (isIgnorableEmail(email)) return;
    if (!map[email]) {
      map[email] = { email: email, name: '', sources: [] };
    }
    if (name && !map[email].name) map[email].name = String(name).trim();
    if (source && map[email].sources.indexOf(source) < 0) {
      map[email].sources.push(source);
    }
  }

  function harvestEmailsFromText(map, text, source) {
    var s = String(text || '');
    if (!s) return;
    // Name <email>
    var named = /([^<>\n\r,;"]{2,60})\s*<\s*([a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,})\s*>/g;
    var nm;
    while ((nm = named.exec(s))) {
      addEmailCandidate(map, nm[2], String(nm[1]).replace(/^[\s"']+|[\s"']+$/g, ''), source);
    }
    var re = new RegExp(EMAIL_ADDR_RE.source, 'g');
    var m;
    while ((m = re.exec(s))) {
      var em = m[0];
      var guessed = guessNameNearEmail(s, em);
      addEmailCandidate(map, em, guessed, source);
    }
  }

  function collectMailEmailCandidates(m, detail) {
    detail = detail || (m && m._detail) || {};
    var map = {};
    var fromName = parseDisplayNameFromFrom(detail.from || detail.from_ || (m && m.from) || '');
    addEmailCandidate(map, detail.from || detail.from_ || (m && m.from), fromName, 'from');
    addEmailCandidate(map, m && m.reply_email, fromName, 'from');
    harvestEmailsFromText(map, detail.to || detail.to_ || '', 'to');
    harvestEmailsFromText(map, detail.cc || detail.cc_ || '', 'cc');
    harvestEmailsFromText(map, detail.bcc || detail.bcc_ || '', 'bcc');
    harvestEmailsFromText(map, detail.reply_to || detail.replyto || '', 'reply_to');
    var body = detail.body_plain || detail.body || detail.text || '';
    if (!body && detail.body_html) {
      try {
        var tmp = document.createElement('div');
        tmp.innerHTML = detail.body_html;
        body = tmp.innerText || tmp.textContent || '';
      } catch (e) { body = String(detail.body_html || ''); }
    }
    if (!body && m && m.prev) body = m.prev;
    harvestEmailsFromText(map, body, 'body');
    harvestEmailsFromText(map, (m && m.subj) || detail.subject || '', 'subject');

    var list = Object.keys(map).map(function (k) { return map[k]; });
    list.sort(function (a, b) {
      function score(c) {
        var s = 0;
        if (c.sources.indexOf('body') >= 0) s += 8;
        if (c.sources.indexOf('to') >= 0) s += 4;
        if (c.sources.indexOf('cc') >= 0) s += 2;
        if (c.sources.indexOf('from') >= 0) s += 1;
        if (!/@abcona\.de$/i.test(c.email)) s += 5;
        if (c.name) s += 1;
        return s;
      }
      return score(b) - score(a);
    });
    return list;
  }

  function pickDefaultRecipientRoles(candidates, outerFromEmail) {
    var roles = {}; // email -> 'to'|'cc'|'bcc'|''
    var outer = normalizeEmailAddr(outerFromEmail);
    candidates.forEach(function (c) { roles[c.email] = ''; });

    var preferred = candidates.filter(function (c) {
      return !/@abcona\.de$/i.test(c.email) && c.email !== outer;
    });
    // Body-Kontakte (z.B. Hays) vor dem äußeren Weiterleiter
    var bodyExt = preferred.filter(function (c) { return c.sources.indexOf('body') >= 0; });
    var toPick = (bodyExt[0] || preferred[0] || candidates[0] || null);
    if (toPick) roles[toPick.email] = 'to';

    // Weiterleiter als CC-Vorschlag, wenn An jemand anderes ist
    if (outer && roles[outer] === '' && toPick && toPick.email !== outer) {
      roles[outer] = 'cc';
    }
    return roles;
  }

  function sourceLabel(sources) {
    var map = {
      from: _t('sh.inbox_reply_src_from', 'Von'),
      to: _t('sh.inbox_reply_src_to', 'An'),
      cc: _t('sh.inbox_reply_src_cc', 'CC'),
      bcc: 'BCC',
      body: _t('sh.inbox_reply_src_body', 'Text'),
      reply_to: 'Reply-To',
      subject: _t('sh.inbox_reply_src_subj', 'Betreff'),
      manual: _t('sh.inbox_reply_src_manual', 'Manuell'),
    };
    return (sources || []).map(function (s) { return map[s] || s; }).join(', ');
  }

  function openMailReplyComposer(m) {
    closeMailReplyComposer();
    m = m || {};

    function launch(detail) {
      m._detail = detail || m._detail || {};
      _openMailReplyComposerWithDetail(m, m._detail);
    }

    if (m._detail && (m._detail.body_plain || m._detail.body_html || m._detail.body)) {
      launch(m._detail);
      return;
    }
    ensureMailDetail(m, function (detail) {
      launch(detail || {});
    });
  }

  function _openMailReplyComposerWithDetail(m, detail) {
    var outerFromEmail = normalizeEmailAddr(
      m.reply_email || extractEmailFromFrom(detail.from || detail.from_ || m.from) || ''
    );
    var candidates = collectMailEmailCandidates(m, detail);
    var roles = pickDefaultRecipientRoles(candidates, outerFromEmail);

    var defaultTo = candidates.filter(function (c) { return roles[c.email] === 'to'; })[0];
    var crmName = String(m.crm_name || '').trim();
    var fromName = parseDisplayNameFromFrom(detail.from || detail.from_ || m.from);
    var contactName = (defaultTo && defaultTo.name) || crmName || fromName;
    var nameParts = guessContactFirstLast(contactName);
    var nameForAnrede = nameParts.last || nameParts.display || contactName;
    var subjRaw = String(detail.subject || detail.subj || m.subj || '').trim();
    var subject = subjRaw
      ? (/^re\s*:/i.test(subjRaw) ? subjRaw : ('Re: ' + subjRaw))
      : _t('sh.inbox_reply_subj', 'Ihre Anfrage — Eingangsbestätigung');

    var recipRows = candidates.map(function (c) {
      var role = roles[c.email] || '';
      function opt(v, label) {
        return '<option value="' + v + '"' + (role === v ? ' selected' : '') + '>' + esc(label) + '</option>';
      }
      return (
        '<div class="sh-mr-recip" data-email="' + esc(c.email) + '">' +
        '<div class="sh-mr-recip-main">' +
        '<b class="em">' + esc(c.email) + '</b>' +
        (c.name ? '<span class="nm">' + esc(c.name) + '</span>' : '') +
        '<span class="src">' + esc(sourceLabel(c.sources)) + '</span></div>' +
        '<select class="sh-mr-role" aria-label="Rolle">' +
        opt('', '—') +
        opt('to', _t('sh.inbox_reply_role_to', 'An')) +
        opt('cc', _t('sh.inbox_reply_role_cc', 'CC')) +
        opt('bcc', _t('sh.inbox_reply_role_bcc', 'BCC')) +
        '</select></div>'
      );
    }).join('');

    var ovl = document.createElement('div');
    ovl.className = 'ovl open';
    ovl.id = 'sh-mail-reply-ovl';
    ovl.innerHTML =
      '<div class="sh-modal sh-mail-reply-modal">' +
      '<div class="mh">' +
      '<div class="ico"><i class="bi bi-envelope-at"></i></div>' +
      '<div><b>' + esc(_t('sh.inbox_reply', 'Antworten (Email Studio)')) + '</b>' +
      '<small class="sh-mt-subj">' + esc(_t('sh.inbox_reply_tpl', 'Vorlage: Anfrage-Bestätigung')) + '</small></div>' +
      '<button type="button" class="x" id="sh-mr-close"><i class="bi bi-x-lg"></i></button>' +
      '</div>' +
      '<div class="mb">' +
      '<div class="inp sh-mr-span">' +
      '<label>' + esc(_t('sh.inbox_reply_recips', 'Empfänger (erkannte Adressen)')) + '</label>' +
      '<div id="sh-mr-recips" class="sh-mr-recips">' +
      (recipRows || '<div class="note">' + esc(_t('sh.inbox_reply_no_emails', 'Keine Adressen erkannt')) + '</div>') +
      '</div></div>' +
      '<div class="sh-mr-grid sh-mr-add-row">' +
      '<div class="inp sh-mr-span2"><label for="sh-mr-add-email">' +
      esc(_t('sh.inbox_reply_add', 'Weitere Adresse')) + '</label>' +
      '<input type="email" id="sh-mr-add-email" placeholder="name@firma.de"></div>' +
      '<div class="inp"><label for="sh-mr-add-role">' + esc(_t('sh.inbox_reply_role', 'Als')) + '</label>' +
      '<select id="sh-mr-add-role">' +
      '<option value="to">' + esc(_t('sh.inbox_reply_role_to', 'An')) + '</option>' +
      '<option value="cc">CC</option>' +
      '<option value="bcc">BCC</option>' +
      '</select></div>' +
      '<div class="inp sh-mr-add-btn-wrap"><label>&nbsp;</label>' +
      '<button type="button" class="sh-mr-add-btn" id="sh-mr-add-btn">' +
      '<i class="bi bi-plus-lg"></i> ' + esc(_t('sh.inbox_reply_add_btn', 'Hinzufügen')) +
      '</button></div></div>' +
      '<div class="sh-mr-grid">' +
      '<div class="inp"><label for="sh-mr-anrede">' + esc(_t('sh.inbox_reply_anrede', 'Anrede')) + '</label>' +
      '<select id="sh-mr-anrede">' +
      '<option value="herr">' + esc(_t('sh.anrede_herr', 'Herr')) + '</option>' +
      '<option value="frau">' + esc(_t('sh.anrede_frau', 'Frau')) + '</option>' +
      '<option value="damen">' + esc(_t('sh.anrede_damen', 'Damen und Herren')) + '</option>' +
      '<option value="neutral">' + esc(_t('sh.anrede_neutral', 'Sehr geehrte/r')) + '</option>' +
      '</select></div>' +
      '<div class="inp"><label for="sh-mr-name">' + esc(_t('sh.inbox_reply_name', 'Name')) + '</label>' +
      '<input type="text" id="sh-mr-name" value="' + esc(nameForAnrede) + '"></div>' +
      '</div>' +
      '<div class="inp"><label for="sh-mr-subj">' + esc(_t('sh.inbox_reply_subject', 'Betreff')) + '</label>' +
      '<input type="text" id="sh-mr-subj" value="' + esc(subject) + '"></div>' +
      '<div class="sh-mr-grid">' +
      '<div class="inp"><label for="sh-mr-sender">' + esc(_t('sh.inbox_reply_sender', 'Absender')) + '</label>' +
      '<select id="sh-mr-sender"><option value="">…</option></select></div>' +
      '<div class="inp"><label for="sh-mr-sig">' + esc(_t('sh.inbox_reply_sig', 'Signatur')) + '</label>' +
      '<select id="sh-mr-sig"><option value="">' + esc(_t('sh.inbox_reply_sig_none', '— keine —')) + '</option></select></div>' +
      '</div>' +
      '<div class="inp"><label for="sh-mr-body">' + esc(_t('sh.inbox_reply_body', 'Nachricht')) + '</label>' +
      '<textarea id="sh-mr-body" rows="10"></textarea></div>' +
      '<div id="sh-mr-msg" class="sh-mr-msg" style="display:none"></div>' +
      '<div class="sh-mr-actions">' +
      '<button type="button" class="sh-mr-cancel" id="sh-mr-cancel">' +
      esc(_t('sh.inbox_reply_cancel', 'Abbrechen')) + '</button>' +
      '<button type="button" class="primary" id="sh-mr-send">' +
      '<i class="bi bi-send"></i> ' + esc(_t('sh.inbox_reply_send', 'Senden & Aufgabe')) +
      '</button></div>' +
      '<div class="note">' + esc(_t('sh.inbox_reply_hint',
        'Nach dem Versand öffnet sich „Aufgabe erzeugen“ (Standard: Wiedervorlage).')) +
      '</div></div></div>';
    document.body.appendChild(ovl);

    var bodyEl = document.getElementById('sh-mr-body');
    var anredeEl = document.getElementById('sh-mr-anrede');
    var nameEl = document.getElementById('sh-mr-name');
    var bodyTouched = false;
    var nameTouched = false;

    function refreshBodyFromTpl() {
      if (!bodyEl || bodyTouched) return;
      bodyEl.value = buildAnfrageAckBody(
        anredeEl ? anredeEl.value : 'herr',
        nameEl ? nameEl.value : ''
      );
    }
    refreshBodyFromTpl();
    if (anredeEl) anredeEl.addEventListener('change', refreshBodyFromTpl);
    if (nameEl) {
      nameEl.addEventListener('input', function () {
        nameTouched = true;
        refreshBodyFromTpl();
      });
    }
    if (bodyEl) {
      bodyEl.addEventListener('input', function () { bodyTouched = true; });
    }

    function selectedBuckets() {
      var to = [];
      var cc = [];
      var bcc = [];
      var host = document.getElementById('sh-mr-recips');
      if (!host) return { to: to, cc: cc, bcc: bcc };
      host.querySelectorAll('.sh-mr-recip').forEach(function (row) {
        var em = row.getAttribute('data-email') || '';
        var sel = row.querySelector('.sh-mr-role');
        var role = sel ? sel.value : '';
        if (!em || !role) return;
        if (role === 'to') to.push(em);
        else if (role === 'cc') cc.push(em);
        else if (role === 'bcc') bcc.push(em);
      });
      return { to: to, cc: cc, bcc: bcc };
    }

    function syncNameFromTo() {
      if (nameTouched || !nameEl) return;
      var buckets = selectedBuckets();
      var toEm = buckets.to[0];
      if (!toEm) return;
      var hit = candidates.filter(function (c) { return c.email === toEm; })[0];
      if (hit && hit.name) {
        var parts = guessContactFirstLast(hit.name);
        nameEl.value = parts.last || parts.display || hit.name;
        refreshBodyFromTpl();
      }
    }

    var recipHost = document.getElementById('sh-mr-recips');
    if (recipHost) {
      recipHost.addEventListener('change', function (ev) {
        if (ev.target && ev.target.classList.contains('sh-mr-role')) syncNameFromTo();
      });
    }

    var addBtn = document.getElementById('sh-mr-add-btn');
    if (addBtn) {
      addBtn.onclick = function () {
        var inp = document.getElementById('sh-mr-add-email');
        var roleEl = document.getElementById('sh-mr-add-role');
        var em = normalizeEmailAddr(inp && inp.value);
        var role = (roleEl && roleEl.value) || 'to';
        if (isIgnorableEmail(em) || em.indexOf('@') < 0) {
          showMsg(false, _t('sh.inbox_reply_err_email', 'Bitte gültige E-Mail eingeben'));
          return;
        }
        var existing = null;
        if (recipHost) {
          recipHost.querySelectorAll('.sh-mr-recip').forEach(function (row) {
            if ((row.getAttribute('data-email') || '') === em) existing = row;
          });
        }
        if (existing) {
          var sel = existing.querySelector('.sh-mr-role');
          if (sel) sel.value = role;
        } else {
          candidates.push({ email: em, name: '', sources: ['manual'] });
          var row = document.createElement('div');
          row.className = 'sh-mr-recip';
          row.setAttribute('data-email', em);
          row.innerHTML =
            '<div class="sh-mr-recip-main"><b class="em">' + esc(em) + '</b>' +
            '<span class="src">' + esc(sourceLabel(['manual'])) + '</span></div>' +
            '<select class="sh-mr-role">' +
            '<option value="">—</option>' +
            '<option value="to"' + (role === 'to' ? ' selected' : '') + '>' + esc(_t('sh.inbox_reply_role_to', 'An')) + '</option>' +
            '<option value="cc"' + (role === 'cc' ? ' selected' : '') + '>CC</option>' +
            '<option value="bcc"' + (role === 'bcc' ? ' selected' : '') + '>BCC</option>' +
            '</select>';
          if (recipHost) {
            var emptyNote = recipHost.querySelector('.note');
            if (emptyNote) emptyNote.remove();
            recipHost.appendChild(row);
          }
        }
        if (inp) inp.value = '';
        syncNameFromTo();
        showMsg(true, '');
        var msg = document.getElementById('sh-mr-msg');
        if (msg) msg.style.display = 'none';
      };
    }

    function showMsg(ok, text) {
      var el = document.getElementById('sh-mr-msg');
      if (!el) return;
      if (!text) { el.style.display = 'none'; return; }
      el.style.display = 'block';
      el.className = 'sh-mr-msg ' + (ok ? 'ok' : 'err');
      el.textContent = text;
    }

    var closeBtn = document.getElementById('sh-mr-close');
    var cancelBtn = document.getElementById('sh-mr-cancel');
    if (closeBtn) closeBtn.onclick = closeMailReplyComposer;
    if (cancelBtn) cancelBtn.onclick = closeMailReplyComposer;
    ovl.addEventListener('click', function (ev) {
      if (ev.target === ovl) closeMailReplyComposer();
    });

    // Absender + Signaturen laden
    var senderSel = document.getElementById('sh-mr-sender');
    var sigSel = document.getElementById('sh-mr-sig');
    var userHint = currentUserEmailHint();
    var boxHint = String(m.account || m.box || '').trim().toLowerCase();

    Promise.all([
      fetch('/email-studio/api/senders/', { credentials: 'same-origin', headers: { 'X-Requested-With': 'XMLHttpRequest' } })
        .then(function (r) { return r.ok ? r.json() : { senders: [] }; })
        .catch(function () { return { senders: [] }; }),
      fetch('/email-studio/api/signatures/', { credentials: 'same-origin', headers: { 'X-Requested-With': 'XMLHttpRequest' } })
        .then(function (r) { return r.ok ? r.json() : { signatures: [] }; })
        .catch(function () { return { signatures: [] }; }),
    ]).then(function (pack) {
      var senders = (pack[0] && pack[0].senders) || [];
      var sigs = (pack[1] && pack[1].signatures) || [];
      senders = senders.filter(function (s) { return s.is_active !== false; });

      if (senderSel) {
        senderSel.innerHTML = senders.map(function (s) {
          var label = (s.display_name || s.email || '') +
            (s.email ? ' <' + s.email + '>' : '');
          return '<option value="' + esc(String(s.id)) + '">' + esc(label) + '</option>';
        }).join('') || '<option value="">' + esc(_t('sh.inbox_reply_no_sender', 'Kein Absender')) + '</option>';

        var pick = '';
        senders.forEach(function (s) {
          var em = String(s.email || '').toLowerCase();
          if (userHint && em === userHint) pick = String(s.id);
        });
        if (!pick && boxHint) {
          senders.forEach(function (s) {
            var em = String(s.email || '').toLowerCase();
            if (em === boxHint || em.indexOf(boxHint) === 0 || boxHint.indexOf(em.split('@')[0]) >= 0) {
              pick = String(s.id);
            }
          });
        }
        if (!pick) {
          senders.forEach(function (s) {
            if (s.is_default) pick = String(s.id);
          });
        }
        if (pick) senderSel.value = pick;
      }

      if (sigSel) {
        sigSel.innerHTML = '<option value="">' + esc(_t('sh.inbox_reply_sig_none', '— keine —')) + '</option>' +
          sigs.map(function (s) {
            return '<option value="' + esc(String(s.id)) + '"' +
              (s.is_default ? ' selected' : '') + '>' + esc(s.name || s.identifier || '') + '</option>';
          }).join('');
        function syncSigToSender() {
          if (!sigSel || !senderSel) return;
          var sid = senderSel.value;
          var match = sigs.filter(function (s) {
            return String(s.sender_account_id || '') === String(sid);
          })[0];
          if (match) sigSel.value = String(match.id);
        }
        senderSel && senderSel.addEventListener('change', syncSigToSender);
        syncSigToSender();
      }
    });

    var sendBtn = document.getElementById('sh-mr-send');
    if (sendBtn) {
      sendBtn.onclick = function () {
        var buckets = selectedBuckets();
        var subj = (document.getElementById('sh-mr-subj') || {}).value || '';
        var bodyTxt = (document.getElementById('sh-mr-body') || {}).value || '';
        var senderId = (document.getElementById('sh-mr-sender') || {}).value || '';
        var sigId = (document.getElementById('sh-mr-sig') || {}).value || '';
        var cName = (document.getElementById('sh-mr-name') || {}).value || contactName || '';

        subj = String(subj).trim();
        bodyTxt = String(bodyTxt).trim();
        if (!buckets.to.length) {
          showMsg(false, _t('sh.inbox_reply_err_to', 'Bitte mindestens eine Adresse als „An“ wählen'));
          return;
        }
        if (!subj) { showMsg(false, _t('sh.inbox_reply_err_subj', 'Betreff fehlt')); return; }
        if (!bodyTxt) { showMsg(false, _t('sh.inbox_reply_err_body', 'Nachricht fehlt')); return; }

        sendBtn.disabled = true;
        sendBtn.innerHTML = '<i class="bi bi-hourglass-split"></i> …';
        showMsg(true, _t('sh.inbox_reply_sending', 'Wird gesendet …'));

        var sendUrl = m.id
          ? api('inbox/' + encodeURIComponent(m.id) + '/ack-send/')
          : '/crm/api/email/send/';
        var payload = m.id
          ? {
              to: buckets.to,
              cc: buckets.cc,
              bcc: buckets.bcc,
              subject: subj,
              body: bodyTextToHtml(bodyTxt),
              contact_name: cName,
              signature_id: sigId || null,
              sender_id: senderId || null,
              crm_id: m.crm_bean_id || '',
              template_identifier: 'crm_manual_email',
            }
          : {
              template_identifier: 'crm_manual_email',
              to_email: buckets.to[0],
              subject: subj,
              body: bodyTextToHtml(bodyTxt),
              contact_name: cName,
              signature_id: sigId || null,
              sender_id: senderId || null,
              crm_id: m.crm_bean_id || '',
            };

        fetch(sendUrl, {
          method: 'POST',
          credentials: 'same-origin',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken(),
            'X-Requested-With': 'XMLHttpRequest',
          },
          body: JSON.stringify(payload),
        })
          .then(function (r) { return r.json().then(function (j) { return { ok: r.ok, j: j }; }); })
          .then(function (pack) {
            var j = pack.j || {};
            if (pack.ok && (j.ok !== false) && (j.success !== false) && !j.error) {
              closeMailReplyComposer();
              toast(_t('sh.inbox_reply_sent', 'Bestätigung gesendet'));
              markMailRead(m.id, document.querySelector('#sh-inbox .ritem.on'));
              openMailTaskChooser(m, {
                defaultArt: 'wiedervorlage',
                notiz: _t('sh.inbox_reply_task_notiz', 'Auf E-Mail geantwortet am') +
                  ' ' + formatReplyStamp(new Date()) +
                  (buckets.to.length ? (' → ' + buckets.to.join(', ')) : ''),
                due: tomorrowDueDateTime(),
                titleHint: _t('sh.inbox_reply_task_title', 'Nach Bestätigung — Wiedervorlage'),
              });
            } else {
              sendBtn.disabled = false;
              sendBtn.innerHTML = '<i class="bi bi-send"></i> ' +
                esc(_t('sh.inbox_reply_send', 'Senden & Aufgabe'));
              showMsg(false, j.error || _t('sh.inbox_reply_err_send', 'Senden fehlgeschlagen'));
            }
          })
          .catch(function () {
            sendBtn.disabled = false;
            sendBtn.innerHTML = '<i class="bi bi-send"></i> ' +
              esc(_t('sh.inbox_reply_send', 'Senden & Aufgabe'));
            showMsg(false, _t('sh.inbox_reply_err_send', 'Senden fehlgeschlagen'));
          });
      };
    }
  }

  function extractEmailFromFrom(from) {
    var s = String(from || '');
    var m = s.match(/<([^>]+@[^>]+)>/);
    if (m) return m[1].trim();
    m = s.match(/([^\s<>]+@[^\s<>]+)/);
    return m ? m[1].trim() : '';
  }


  // Defaults pro Aufgaben-Art: Offset ab jetzt = Woche + Tag + Stunde + Minute.
  // Unter Regeln einstellbar. Termin = „kein Default“.
  var TASK_ART_DEFAULTS_BASE = {
    anruf: { weeks: 0, days: 0, hours: 1, minutes: 0, enabled: true },
    sms_messenger: { weeks: 0, days: 0, hours: 1, minutes: 0, enabled: true },
    wiedervorlage: { weeks: 0, days: 1, hours: 0, minutes: 0, enabled: true },
    email: { weeks: 0, days: 0, hours: 2, minutes: 0, enabled: true },
    post: { weeks: 0, days: 2, hours: 0, minutes: 0, enabled: true },
    termin: { weeks: 0, days: 0, hours: 0, minutes: 0, enabled: false },
    dokument: { weeks: 0, days: 1, hours: 0, minutes: 0, enabled: true },
    intern: { weeks: 0, days: 1, hours: 0, minutes: 0, enabled: true },
  };
  var TASK_ART_DEFAULT_LABELS = {
    anruf: 'Anruf',
    sms_messenger: 'WhatsApp',
    wiedervorlage: 'Wiedervorlage',
    email: 'E-Mail',
    post: 'Post',
    termin: 'Termin',
    dokument: 'Dokument',
    intern: 'Intern',
  };
  var TASK_ART_DEFAULT_LABEL_KEYS = {
    anruf: 'sh.art_anruf_one',
    sms_messenger: 'sh.art_sms_messenger_short',
    wiedervorlage: 'sh.art_wiedervorlage_one',
    email: 'sh.art_email_one',
    post: 'sh.art_post',
    termin: 'sh.art_termin_one',
    dokument: 'sh.art_dokument_one',
    intern: 'sh.art_intern_one',
  };
  var TASK_ART_DEFAULT_ORDER = [
    'anruf', 'sms_messenger', 'wiedervorlage', 'email',
    'post', 'termin', 'dokument', 'intern',
  ];
  var ART_DEFAULTS_LS_KEY = 'sh_task_art_defaults_v2';

  function nzInt(v, fallback) {
    var n = parseInt(v, 10);
    return isNaN(n) || n < 0 ? (fallback || 0) : n;
  }

  /** Altes Format {days, dauer_min} → Woche/Tag/Std/Min. */
  function migrateLegacyArtDefault(raw) {
    if (!raw || typeof raw !== 'object') {
      return { weeks: 0, days: 0, hours: 0, minutes: 0, enabled: false };
    }
    if (raw.weeks != null || raw.hours != null || raw.minutes != null || raw.enabled === false || raw.enabled === true) {
      var weeks = nzInt(raw.weeks, 0);
      var days = nzInt(raw.days, 0);
      var hours = nzInt(raw.hours, 0);
      var minutes = nzInt(raw.minutes, 0);
      var enabled = raw.enabled !== false && (weeks + days + hours + minutes > 0 || raw.enabled === true);
      if (raw.enabled === false) enabled = false;
      return { weeks: weeks, days: days, hours: hours, minutes: minutes, enabled: enabled };
    }
    var legDays = raw.days != null && raw.days !== '' ? nzInt(raw.days, 0) : 0;
    var dur = raw.dauer_min != null && raw.dauer_min !== '' ? nzInt(raw.dauer_min, 0) : 0;
    if (raw.days == null && raw.dauer_min == null) {
      return { weeks: 0, days: 0, hours: 0, minutes: 0, enabled: false };
    }
    return {
      weeks: 0,
      days: (raw.days != null && raw.days !== '') ? legDays : 0,
      hours: Math.floor(dur / 60),
      minutes: dur % 60,
      enabled: !!(dur || (raw.days != null && raw.days !== '')),
    };
  }

  function loadArtDefaultsOverride() {
    try {
      var raw = localStorage.getItem(ART_DEFAULTS_LS_KEY);
      if (!raw) {
        var old = localStorage.getItem('sh_task_art_defaults');
        if (!old) return {};
        var o1 = JSON.parse(old);
        if (!o1 || typeof o1 !== 'object') return {};
        var migrated = {};
        Object.keys(o1).forEach(function (k) {
          migrated[k] = migrateLegacyArtDefault(o1[k]);
        });
        localStorage.setItem(ART_DEFAULTS_LS_KEY, JSON.stringify(migrated));
        return migrated;
      }
      var o = JSON.parse(raw);
      return o && typeof o === 'object' ? o : {};
    } catch (e) {
      return {};
    }
  }

  function saveArtDefaultsOverride(map) {
    try {
      if (!map || !Object.keys(map).length) {
        localStorage.removeItem(ART_DEFAULTS_LS_KEY);
      } else {
        localStorage.setItem(ART_DEFAULTS_LS_KEY, JSON.stringify(map));
      }
    } catch (e) { /* ignore */ }
  }

  function getArtDefaults(art) {
    var base = migrateLegacyArtDefault(TASK_ART_DEFAULTS_BASE[art]);
    var overRaw = loadArtDefaultsOverride()[art];
    if (!overRaw) return base;
    return migrateLegacyArtDefault(overRaw);
  }

  function formatDauerLabel(min) {
    var m = parseInt(min, 10);
    if (!m || m < 1) return '';
    if (m % 60 === 0) return String(m / 60) + ' Std';
    if (m === 90) return '1,5 Std';
    if (m > 60) {
      var h = Math.floor(m / 60);
      var r = m % 60;
      return h + ' Std ' + r + ' Min';
    }
    return String(m) + ' Min';
  }

  function ymdFromDate(d) {
    return d.getFullYear() + '-' +
      String(d.getMonth() + 1).padStart(2, '0') + '-' +
      String(d.getDate()).padStart(2, '0');
  }

  /** Fälligkeit aus Art-Default (Offset ab jetzt). null wenn kein Default. */
  function dueDateTimeFromArt(art) {
    var def = getArtDefaults(art);
    if (!def || !def.enabled) return null;
    var weeks = nzInt(def.weeks, 0);
    var days = nzInt(def.days, 0);
    var hours = nzInt(def.hours, 0);
    var minutes = nzInt(def.minutes, 0);
    if (weeks + days + hours + minutes === 0) return null;
    var d = new Date();
    d.setDate(d.getDate() + weeks * 7 + days);
    d.setHours(d.getHours() + hours);
    d.setMinutes(d.getMinutes() + minutes, 0, 0);
    return {
      date: ymdFromDate(d),
      time: String(d.getHours()).padStart(2, '0') + ':' + String(d.getMinutes()).padStart(2, '0'),
      def: def,
    };
  }

  function applyArtDueDefaults(art) {
    var def = getArtDefaults(art);
    var dateEl = document.getElementById('sh-mt-date');
    var timeEl = document.getElementById('sh-mt-time');
    var dauerEl = document.getElementById('sh-mt-dauer');
    if (!dateEl && !timeEl && !dauerEl) return;
    if (!def || !def.enabled) return;

    var weeks = nzInt(def.weeks, 0);
    var days = nzInt(def.days, 0);
    var hours = nzInt(def.hours, 0);
    var minutes = nzInt(def.minutes, 0);
    if (weeks + days + hours + minutes === 0) return;

    var d = new Date();
    d.setDate(d.getDate() + weeks * 7 + days);
    d.setHours(d.getHours() + hours);
    d.setMinutes(d.getMinutes() + minutes, 0, 0);
    if (dateEl) dateEl.value = ymdFromDate(d);
    if (timeEl) {
      timeEl.value = String(d.getHours()).padStart(2, '0') + ':' +
        String(d.getMinutes()).padStart(2, '0');
    }

    if (dauerEl) {
      var durMin = hours * 60 + minutes;
      if (durMin > 0) {
        var v = String(durMin);
        if (!Array.prototype.some.call(dauerEl.options, function (o) { return o.value === v; })) {
          var opt = document.createElement('option');
          opt.value = v;
          opt.textContent = formatDauerLabel(v) || (v + ' Min');
          dauerEl.appendChild(opt);
        }
        dauerEl.value = v;
      } else {
        dauerEl.value = '';
      }
    }
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

  function openMailTaskChooser(m, opts) {
    closeMailTaskChooser();
    m = m || {};
    opts = opts || {};
    var defaultArt = opts.defaultArt || 'anruf';
    var arts = [
      { id: 'anruf', label: _t('sh.art_anruf', 'Anruf'), icon: 'bi-telephone' },
      { id: 'sms_messenger', label: _t('sh.art_sms_messenger_short', 'WhatsApp'), icon: 'bi-whatsapp' },
      { id: 'wiedervorlage', label: _t('sh.art_wiedervorlage', 'Wiedervorlage'), icon: 'bi-arrow-repeat' },
      { id: 'email', label: _t('sh.art_email', 'E-Mail'), icon: 'bi-envelope' },
      { id: 'post', label: _t('sh.art_post', 'Post'), icon: 'bi-mailbox' },
      { id: 'termin', label: _t('sh.art_termin', 'Termin'), icon: 'bi-calendar-event' },
      { id: 'dokument', label: _t('sh.art_dokument', 'Dokument'), icon: 'bi-file-earmark-text' },
      { id: 'intern', label: _t('sh.art_intern', 'Intern'), icon: 'bi-briefcase' },
    ];
    var artBtns = arts.map(function (a) {
      return '<button type="button" class="sh-pick' + (a.id === defaultArt ? ' on' : '') + '" data-art="' + a.id + '">' +
        (a.icon ? '<i class="bi ' + a.icon + '"></i> ' : '') + esc(a.label) + '</button>';
    }).join('');
    var dueDef = opts.due || defaultDueDateTime();
    var notizPrefill = opts.notiz != null ? String(opts.notiz) : '';
    var titleMain = opts.titleHint || _t('sh.inbox_task', 'Aufgabe erzeugen');
    var ovl = document.createElement('div');
    ovl.className = 'ovl open';
    ovl.id = 'sh-mail-task-ovl';
    ovl.innerHTML =
      '<div class="sh-modal sh-mail-task-modal">' +
      '<div class="mh">' +
      '<div class="ico"><i class="bi bi-check2-square"></i></div>' +
      '<div><b>' + esc(titleMain) + '</b>' +
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
      esc(_t('sh.inbox_notiz_ph', 'Kurz notieren, was zu tun ist …')) + '">' +
      esc(notizPrefill) + '</textarea></div>' +
      '<button type="button" class="primary" id="sh-mt-save">' +
      '<i class="bi bi-check2"></i> ' + esc(_t('sh.inbox_task_create', 'Aufgabe anlegen')) +
      '</button>' +
      '</div></div>';
    document.body.appendChild(ovl);

    var selectedArt = defaultArt;
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
        applyArtDueDefaults(selectedArt);
      });
    });
    // Start-Art: Defaults sofort setzen (weiter editierbar)
    applyArtDueDefaults(selectedArt);
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
    m._detail = Object.assign({}, m._detail || {}, {
      body_plain: (m._detail && m._detail.body_plain) || m.prev || '',
      from: (m._detail && m._detail.from) || m.from || '',
      subject: (m._detail && m._detail.subject) || m.subj || '',
      subj: (m._detail && m._detail.subj) || m.subj || '',
    });
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
    m._detail = detail || m._detail || {};
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

  function renderInbox(items, opts) {
    opts = opts || {};
    var soft = !!opts.soft;
    var c = document.getElementById('sh-inbox');
    if (!c) return;
    c.innerHTML = '';
    if (!items.length) {
      c.innerHTML = '<div class="none" style="padding:12px">' + esc(_t('sh.inbox_leer', 'Keine Mails')) + '</div>';
      // Soft-Poll: Viewer / Auswahl nicht zerstören (z.B. Filter leer, Dialog offen)
      if (!soft) showViewerEmpty();
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

  var RADAR_ITEMS = [];
  var RADAR_SELECTED = null;
  var RADAR_PAGE = 1;
  var RADAR_PAGE_SIZE = 20;
  var RADAR_Q = '';
  var RADAR_DAYS = 2; // 0 = alle; 1/2/7/30
  var RADAR_SORT = 'date_desc';
  var RADAR_SOURCE = ''; // '' | freelancermap | gulp | hays
  var RADAR_BOOTSTRAPPED = false;
  var RADAR_LOADING = false;
  var RADAR_BG_REFRESH_MS = 3 * 60 * 1000; // Live-Fetch max alle 3 Min
  var RADAR_POLL_MS = 60000; // Soft-Poll ES/DB alle 60s wenn Tab aktiv
  var RADAR_POLL_MS_MAX = 180000;
  var radarPollTimer = null;
  var radarPollBackoffMs = RADAR_POLL_MS;
  try {
    var _rps = parseInt(localStorage.getItem('sh_radar_page_size') || '20', 10);
    if ([5, 10, 20, 50].indexOf(_rps) >= 0) RADAR_PAGE_SIZE = _rps;
    var _rd = parseInt(localStorage.getItem('sh_radar_days') || '2', 10);
    if ([0, 1, 2, 7, 30].indexOf(_rd) >= 0) RADAR_DAYS = _rd;
    var _rs = localStorage.getItem('sh_radar_sort') || 'date_desc';
    if (_rs === 'date_asc' || _rs === 'date_desc') RADAR_SORT = _rs;
    var _rq = localStorage.getItem('sh_radar_source') || '';
    if (_rq === 'freelancermap' || _rq === 'gulp' || _rq === 'hays' || _rq === '') RADAR_SOURCE = _rq;
    var _rqq = localStorage.getItem('sh_radar_q');
    if (_rqq != null) RADAR_Q = String(_rqq);
  } catch (e) { /* ignore */ }

  function radarDaysLabel(d) {
    if (d === 0) return _t('sh.radar_days_all', 'alle');
    if (d === 1) return _t('sh.radar_days_1', 'heute');
    if (d === 2) return _t('sh.radar_days_2', '2 Tage');
    if (d === 7) return _t('sh.radar_days_7', '7 Tage');
    if (d === 30) return _t('sh.radar_days_30', '30 Tage');
    return String(d) + 'd';
  }

  function renderRadarToolbar() {
    var t = document.getElementById('sh-radar-toolbar');
    if (!t) return;
    var sizes = [5, 10, 20, 50];
    var sizeOpts = sizes.map(function (n) {
      return '<option value="' + n + '"' + (RADAR_PAGE_SIZE === n ? ' selected' : '') + '>' +
        n + '</option>';
    }).join('');
    var dayOpts = [
      [1, _t('sh.radar_days_1', 'heute')],
      [2, _t('sh.radar_days_2', '2 Tage')],
      [7, _t('sh.radar_days_7', '7 Tage')],
      [30, _t('sh.radar_days_30', '30 Tage')],
      [0, _t('sh.radar_days_all', 'alle')],
    ].map(function (p) {
      return '<option value="' + p[0] + '"' + (RADAR_DAYS === p[0] ? ' selected' : '') + '>' +
        esc(p[1]) + '</option>';
    }).join('');
    t.innerHTML =
      '<form class="sh-inbox-search" id="sh-radar-search">' +
      '<input type="search" id="sh-radar-q" value="' + esc(RADAR_Q) + '" ' +
      'placeholder="' + esc(_t('sh.radar_search_ph', 'Titel, Skills, Firma, Stadt …')) + '" />' +
      '<button type="submit" class="pri"><i class="bi bi-search"></i> ' +
      esc(_t('sh.inbox_search', 'Suchen')) + '</button></form>' +
      '<div class="sh-inbox-opts">' +
      '<select id="sh-radar-days" title="' + esc(_t('sh.radar_zeitraum', 'Zeitraum')) + '">' +
      dayOpts +
      '</select>' +
      '<select id="sh-radar-sort">' +
      '<option value="date_desc"' + (RADAR_SORT === 'date_desc' ? ' selected' : '') + '>' +
      esc(_t('sh.inbox_sort_new', 'Datum: neueste')) + '</option>' +
      '<option value="date_asc"' + (RADAR_SORT === 'date_asc' ? ' selected' : '') + '>' +
      esc(_t('sh.inbox_sort_old', 'Datum: älteste')) + '</option>' +
      '</select>' +
      '<select id="sh-radar-source">' +
      '<option value="">' + esc(_t('sh.radar_src_all', 'Quelle: alle')) + '</option>' +
      '<option value="freelancermap"' + (RADAR_SOURCE === 'freelancermap' ? ' selected' : '') + '>' +
      esc(_t('sh.radar_src_fm', 'Freelancermap')) + '</option>' +
      '<option value="gulp"' + (RADAR_SOURCE === 'gulp' ? ' selected' : '') + '>' +
      esc(_t('sh.radar_src_gulp', 'Gulp')) + '</option>' +
      '<option value="hays"' + (RADAR_SOURCE === 'hays' ? ' selected' : '') + '>' +
      esc(_t('sh.radar_src_hays', 'Hays')) + '</option>' +
      '</select>' +
      '<label class="sh-inbox-pagesize sh-radar-pagesize"><span>' +
      esc(_t('sh.inbox_per_page', 'Anzeigen')) + '</span> ' +
      '<select id="sh-radar-pagesize">' + sizeOpts + '</select></label>' +
      '</div>';

    var form = document.getElementById('sh-radar-search');
    if (form) {
      form.addEventListener('submit', function (e) {
        e.preventDefault();
        var inp = document.getElementById('sh-radar-q');
        RADAR_Q = inp ? String(inp.value || '').trim() : '';
        try { localStorage.setItem('sh_radar_q', RADAR_Q); } catch (eQ) { /* ignore */ }
        RADAR_PAGE = 1;
        loadRadarA({ soft: true });
      });
    }
    var days = document.getElementById('sh-radar-days');
    if (days) days.addEventListener('change', function () {
      RADAR_DAYS = parseInt(days.value, 10);
      if ([0, 1, 2, 7, 30].indexOf(RADAR_DAYS) < 0) RADAR_DAYS = 2;
      try { localStorage.setItem('sh_radar_days', String(RADAR_DAYS)); } catch (e2) { /* ignore */ }
      RADAR_PAGE = 1;
      loadRadarA({ soft: true });
    });
    var sort = document.getElementById('sh-radar-sort');
    if (sort) sort.addEventListener('change', function () {
      RADAR_SORT = sort.value || 'date_desc';
      try { localStorage.setItem('sh_radar_sort', RADAR_SORT); } catch (e3) { /* ignore */ }
      RADAR_PAGE = 1;
      loadRadarA({ soft: true });
    });
    var src = document.getElementById('sh-radar-source');
    if (src) src.addEventListener('change', function () {
      RADAR_SOURCE = src.value || '';
      try { localStorage.setItem('sh_radar_source', RADAR_SOURCE); } catch (e4) { /* ignore */ }
      RADAR_PAGE = 1;
      loadRadarA({ soft: true });
    });
    var psz = document.getElementById('sh-radar-pagesize');
    if (psz) psz.addEventListener('change', function () {
      RADAR_PAGE_SIZE = parseInt(psz.value, 10) || 20;
      RADAR_PAGE = 1;
      try { localStorage.setItem('sh_radar_page_size', String(RADAR_PAGE_SIZE)); } catch (e5) { /* ignore */ }
      renderRadarA(RADAR_ITEMS);
    });
  }

  function stopRadarPoll() {
    if (radarPollTimer) {
      clearTimeout(radarPollTimer);
      radarPollTimer = null;
    }
  }

  function radarTabActive() {
    var tab = document.querySelector('#shaduler-root .mtab.on');
    return !!(tab && tab.getAttribute('data-t') === 'radar_anfragen');
  }

  function scheduleRadarPoll(delayMs) {
    stopRadarPoll();
    if (!radarTabActive()) return;
    var ms = Math.max(RADAR_POLL_MS, Math.min(RADAR_POLL_MS_MAX, delayMs || radarPollBackoffMs));
    radarPollTimer = setTimeout(function () {
      radarPollTimer = null;
      if (!radarTabActive()) return;
      if (document.visibilityState === 'hidden') {
        scheduleRadarPoll(RADAR_POLL_MS);
        return;
      }
      // Alle ~3 Min Live (FM), sonst Soft ES/DB — neue Projekte vom Scheduler sichtbar machen
      var doLive = false;
      try {
        var lastLive = parseInt(sessionStorage.getItem('sh_radar_live_at') || '0', 10);
        doLive = !lastLive || (Date.now() - lastLive) > RADAR_BG_REFRESH_MS;
      } catch (eLive) { /* ignore */ }
      if (doLive) {
        try { sessionStorage.setItem('sh_radar_live_at', String(Date.now())); } catch (eSet) { /* ignore */ }
        loadRadarA({ refresh: true, soft: true });
      } else {
        loadRadarA({ soft: true });
      }
      radarPollBackoffMs = RADAR_POLL_MS;
      scheduleRadarPoll(RADAR_POLL_MS);
    }, ms);
  }

  function startRadarPoll() {
    radarPollBackoffMs = RADAR_POLL_MS;
    scheduleRadarPoll(RADAR_POLL_MS);
  }


  function loadRadarA(opts) {
    opts = opts || {};
    // Standard: ES/DB (schnell). Live-Fetch nur per ↻ oder Hintergrund.
    var doRefresh = opts.refresh === true;
    var soft = !!opts.soft;
    // Parallele Live-Fetches vermeiden; Filter/Suche (soft) trotzdem erlauben
    if (RADAR_LOADING && doRefresh) return;
    if (RADAR_LOADING && !soft && !doRefresh) return;
    renderRadarToolbar();
    var list = document.getElementById('sh-radar-list');
    var viewer = document.getElementById('sh-radar-viewer');
    if (!soft) {
      if (list) list.innerHTML = '<div class="sh-viewer-loading">' + esc(_t('sh.loading', 'Laden…')) + '</div>';
      if (viewer) {
        viewer.innerHTML = '<div class="sh-viewer-empty">' + esc(_t('sh.radar_pick', 'Projekt auswählen')) + '</div>';
      }
    }
    var btn = document.getElementById('sh-radar-refresh');
    if (btn) {
      btn.onclick = function () {
        loadRadarA({ refresh: true });
      };
      if (doRefresh) {
        btn.disabled = true;
        btn.classList.add('busy');
      }
    }
    var q = 'radar/anfragen/?demo=0&today=1&pages=1' +
      '&refresh=' + (doRefresh ? '1' : '0') +
      '&days=' + encodeURIComponent(String(RADAR_DAYS)) +
      '&sort=' + encodeURIComponent(RADAR_SORT || 'date_desc') +
      '&limit=300';
    if (RADAR_Q) q += '&q=' + encodeURIComponent(RADAR_Q);
    if (RADAR_SOURCE) q += '&source=' + encodeURIComponent(RADAR_SOURCE);
    RADAR_LOADING = true;
    fetch(api(q), {
      credentials: 'same-origin',
      headers: { 'X-Requested-With': 'XMLHttpRequest' },
    })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        RADAR_LOADING = false;
        if (btn) { btn.disabled = false; btn.classList.remove('busy'); }
        RADAR_ITEMS = data.results || [];
        if (!soft) RADAR_PAGE = 1;
        RADAR_BOOTSTRAPPED = true;
        renderRadarA(RADAR_ITEMS);
        var hint = document.getElementById('sh-radar-hint');
        if (hint) {
          var by = data.by_source || {};
          var parts = [];
          Object.keys(by).forEach(function (k) {
            if (k) parts.push(k + ': ' + by[k]);
          });
          var ls = data.list_source || '';
          var lsLbl = ls === 'elasticsearch' ? 'ES' : (ls === 'db' ? 'DB' : (ls === 'live' ? 'Live' : ls));
          hint.textContent = data.demo
            ? _t('sh.radar_demo', 'Demo')
            : _t('sh.radar_hint', 'Freelancermap + Gulp + Hays') +
              ' · ' + radarDaysLabel(RADAR_DAYS) +
              (lsLbl ? (' · ' + lsLbl) : '') +
              (parts.length ? (' · ' + parts.join(', ')) : '') +
              (data.raw_count != null && data.count != null && data.raw_count > data.count
                ? (' · ' + data.count + '/' + data.raw_count + ' dedup')
                : '') +
              (doRefresh && data.fetched != null ? (' · ' + data.fetched + ' gelesen') : '');
        }
        refreshStats();
        if (doRefresh) {
          try { sessionStorage.setItem('sh_radar_live_at', String(Date.now())); } catch (e2) { /* ignore */ }
        }
        // Sanfter Hintergrund-Live-Fetch max alle 5 Min (nicht bei Filterwechseln)
        if (!doRefresh && !soft) {
          try {
            var lastLive = parseInt(sessionStorage.getItem('sh_radar_live_at') || '0', 10);
            if (!lastLive || (Date.now() - lastLive) > RADAR_BG_REFRESH_MS) {
              sessionStorage.setItem('sh_radar_live_at', String(Date.now()));
              setTimeout(function () {
                loadRadarA({ refresh: true, soft: true });
              }, 1200);
            }
          } catch (eBg) { /* ignore */ }
        }
      })
      .catch(function () {
        RADAR_LOADING = false;
        if (btn) { btn.disabled = false; btn.classList.remove('busy'); }
        if (!soft) {
          RADAR_ITEMS = [];
          renderRadarA([]);
          toast(_t('sh.radar_err', 'Radar konnte nicht geladen werden'));
        }
      });
  }

  function renderRadarA(items) {
    var c = document.getElementById('sh-radar-list');
    if (!c) return;
    items = items || [];
    var total = items.length;
    var size = Math.max(1, RADAR_PAGE_SIZE || 20);
    var pages = Math.max(1, Math.ceil(total / size) || 1);
    if (RADAR_PAGE > pages) RADAR_PAGE = pages;
    if (RADAR_PAGE < 1) RADAR_PAGE = 1;
    var start = (RADAR_PAGE - 1) * size;
    var slice = items.slice(start, start + size);

    c.innerHTML = '';
    if (!total) {
      c.innerHTML = '<div class="sh-viewer-empty">' +
        esc(_t('sh.radar_empty', 'Keine Projekte')) +
        ' (' + esc(radarDaysLabel(RADAR_DAYS)) +
        (RADAR_Q ? ' · „' + esc(RADAR_Q) + '“' : '') +
        (RADAR_SOURCE ? ' · ' + esc(RADAR_SOURCE) : '') +
        ')</div>';
    }
    slice.forEach(function (r) {
      var e = document.createElement('div');
      e.className = 'ritem' + (RADAR_SELECTED && RADAR_SELECTED.id === r.id ? ' on' : '');
      e.setAttribute('data-id', r.id);
      var grpN = Number(r.grp || r.anbieter_anzahl || 1) || 1;
      var links = r.group_links || [];
      var srcHtml = (r.sources || []).map(function (s) {
        return '<span class="src">' + esc(s) + '</span>';
      }).join('');
      var grpHtml = grpN > 1
        ? ('<span class="grp" data-grp-toggle="1" title="' +
          esc(_t('sh.radar_grp_title', 'Gleiche Anfrage auf mehreren Börsen')) + '">' +
          '<i class="bi bi-stack"></i> ' + grpN + ' ' +
          esc(_t('sh.radar_anbieter', 'Anbieter')) + '</span>')
        : '';
      var linksHtml = '';
      if (grpN > 1 && links.length) {
        linksHtml = '<div class="sources">' + links.map(function (lk) {
          var label = (lk.source || '') + (lk.company ? (' · ' + lk.company) : '');
          var href = lk.url || '#';
          return '<a href="' + esc(href) + '" target="_blank" rel="noopener" data-peer="' +
            esc(lk.id || '') + '"><i class="bi bi-box-arrow-up-right"></i> ' +
            esc(label || lk.headline || href) + '</a>';
        }).join('') + '</div>';
      }
      e.innerHTML =
        '<div class="top">' +
        '<b class="hl">' + esc(r.headline || '') + '</b>' +
        grpHtml + srcHtml +
        (r.age ? '<span class="age">' + esc(r.age) + '</span>' : '') +
        '</div>' +
        '<div class="meta">' + esc(r.meta || '') + '</div>' +
        (r.contact || r.company
          ? '<div class="meta">' + esc([r.contact, r.company].filter(Boolean).join(' · ')) + '</div>'
          : '') +
        linksHtml;
      e.onclick = function (ev) {
        var t = ev.target;
        if (t && t.closest && t.closest('[data-grp-toggle]')) {
          ev.preventDefault();
          ev.stopPropagation();
          var box = e.querySelector('.sources');
          if (box) box.classList.toggle('open');
          return;
        }
        if (t && t.closest && t.closest('.sources a')) {
          ev.stopPropagation();
          return;
        }
        openRadarItem(r, e);
      };
      c.appendChild(e);
    });
    var el = document.getElementById('r-new');
    if (el) el.textContent = String(total);
    el = document.getElementById('tb-ra');
    if (el) el.textContent = total;
    renderRadarPager({ total: total, page: RADAR_PAGE, pages: pages, page_size: size });
  }

  function renderRadarPager(meta) {
    renderShPager({
      elId: 'sh-radar-pager',
      total: meta && meta.total,
      page: meta && meta.page,
      pages: meta && meta.pages,
      page_size: meta && meta.page_size,
      emptyLabel: _t('sh.radar_empty', 'Keine Projekte'),
      onPage: function (p) {
        if (p === RADAR_PAGE) return;
        RADAR_PAGE = p;
        renderRadarA(RADAR_ITEMS);
      },
    });
  }

  /** Pagination: First << | < 1 2 3 4 5 > | >> Last  (<< >> = ±5 Seiten) */
  function renderShPager(opts) {
    opts = opts || {};
    var el = document.getElementById(opts.elId || '');
    if (!el) return;
    var total = Math.max(0, Number(opts.total) || 0);
    var page = Math.max(1, Number(opts.page) || 1);
    var pages = Math.max(1, Number(opts.pages) || 1);
    var size = Math.max(1, Number(opts.page_size) || 20);
    var onPage = typeof opts.onPage === 'function' ? opts.onPage : function () {};
    if (!total) {
      el.innerHTML = '<span class="sh-pager-meta">' +
        esc(opts.emptyLabel || _t('sh.radar_empty', 'Keine Einträge')) + '</span>';
      return;
    }
    page = Math.min(page, pages);
    var from = (page - 1) * size + 1;
    var to = Math.min(total, page * size);
    var win = 5;
    var startPg = Math.max(1, page - Math.floor(win / 2));
    var endPg = Math.min(pages, startPg + win - 1);
    startPg = Math.max(1, endPg - win + 1);
    var nums = '';
    for (var i = startPg; i <= endPg; i++) {
      nums += '<button type="button" class="sh-pg' + (i === page ? ' on' : '') +
        '" data-page="' + i + '">' + i + '</button>';
    }
    var jumpBack = Math.max(1, page - 5);
    var jumpFwd = Math.min(pages, page + 5);
    function btn(label, pageNum, aria, extraClass) {
      var dis = false;
      if (aria === 'first' || aria === 'jump-back' || aria === 'prev') {
        dis = page <= 1;
      } else if (aria === 'next' || aria === 'jump-fwd' || aria === 'last') {
        dis = page >= pages;
      }
      return '<button type="button" class="sh-pg' + (extraClass ? (' ' + extraClass) : '') +
        '" data-page="' + pageNum + '" aria-label="' + aria + '"' +
        (dis ? ' disabled' : '') + '>' + label + '</button>';
    }
    el.innerHTML =
      '<span class="sh-pager-meta">' + esc(from + '–' + to + ' / ' + total) + '</span>' +
      '<div class="sh-pager-btns">' +
      btn(esc(_t('sh.pager_first', 'First')), 1, 'first', 'sh-pg-nav') +
      btn('&laquo;', jumpBack, 'jump-back', 'sh-pg-nav') +
      '<span class="sh-pg-sep" aria-hidden="true">|</span>' +
      btn('&lt;', Math.max(1, page - 1), 'prev', 'sh-pg-nav') +
      nums +
      btn('&gt;', Math.min(pages, page + 1), 'next', 'sh-pg-nav') +
      '<span class="sh-pg-sep" aria-hidden="true">|</span>' +
      btn('&raquo;', jumpFwd, 'jump-fwd', 'sh-pg-nav') +
      btn(esc(_t('sh.pager_last', 'Last')), pages, 'last', 'sh-pg-nav') +
      '</div>';
    el.querySelectorAll('.sh-pg').forEach(function (b) {
      b.addEventListener('click', function () {
        if (b.disabled) return;
        var p = parseInt(b.getAttribute('data-page'), 10);
        if (!p || p < 1 || p > pages) return;
        onPage(p);
      });
    });
  }

  function openRadarItem(r, rowEl) {
    RADAR_SELECTED = r;
    document.querySelectorAll('#sh-radar-list .ritem.on').forEach(function (el) {
      el.classList.remove('on');
    });
    if (rowEl) rowEl.classList.add('on');
    var v = document.getElementById('sh-radar-viewer');
    if (!v) return;
    v.innerHTML = '<div class="sh-viewer-loading">' + esc(_t('sh.loading', 'Laden…')) + '</div>';

    function paint(item) {
      var eck = item.eckdaten || {};
      var body = item.beschreibung || '';
      var url = item.external_url || eck.url || '';
      var srcName = ((item.sources || [])[0] || eck.source || 'freelancermap') + '';
      var srcLow = srcName.toLowerCase();
      var openLabel = srcLow.indexOf('gulp') >= 0
        ? _t('sh.radar_open_gulp', 'Auf Gulp öffnen')
        : (srcLow.indexOf('hays') >= 0
          ? _t('sh.radar_open_hays', 'Auf Hays öffnen')
          : _t('sh.radar_open_fm', 'Auf Freelancermap öffnen'));
      var acts =
        '<div class="racts sh-viewer-acts">' +
        '<button type="button" class="pri sh-radar-task">' +
        '<i class="bi bi-check2-square"></i> ' + esc(_t('sh.inbox_task', 'Aufgabe erzeugen')) +
        '</button>' +
        '<button type="button" class="sh-radar-matching">' +
        '<i class="bi bi-diagram-3"></i> ' + esc(_t('sh.inbox_matching', 'Matching')) +
        '</button>' +
        '<button type="button" class="sh-radar-archive">' +
        '<i class="bi bi-archive"></i> ' + esc(_t('sh.radar_archive', 'Archivieren')) +
        '</button>' +
        (url
          ? '<a class="sh-radar-ext" href="' + esc(url) + '" target="_blank" rel="noopener">' +
            '<i class="bi bi-box-arrow-up-right"></i> ' +
            esc(openLabel) + '</a>'
          : '') +
        '</div>';

      var metaBits = [
        eck.industry,
        eck.city,
        eck.remote_percent != null
          ? (eck.remote_percent >= 100 ? '100% Remote' : (eck.remote_percent + '% Remote'))
          : '',
        eck.beginning ? ('Start ' + eck.beginning) : '',
        eck.duration_text,
        srcName,
      ].filter(Boolean);

      var grpN = Number((r && (r.grp || r.anbieter_anzahl)) || item.grp || 1) || 1;
      var links = (r && r.group_links) || item.group_links || [];
      var grpBar = '';
      if (grpN > 1 && links.length) {
        grpBar =
          '<div class="sh-radar-ext-bar sh-radar-grp-bar">' +
          '<span class="grp"><i class="bi bi-stack"></i> ' + grpN + ' ' +
          esc(_t('sh.radar_anbieter', 'Anbieter')) + '</span> ' +
          links.map(function (lk) {
            var href = lk.url || '#';
            var lab = lk.source || href;
            return '<a class="sh-radar-ext-link" href="' + esc(href) +
              '" target="_blank" rel="noopener">' + esc(lab) + '</a>';
          }).join(' · ') +
          '</div>';
      }

      v.innerHTML =
        acts +
        '<div class="sh-viewer-head">' +
        '<div class="from">' + esc(eck.company || item.company || '—') +
        (eck.contact || item.contact ? (' · ' + esc(eck.contact || item.contact)) : '') +
        '</div>' +
        '<div class="subj">' + esc(item.headline || '') + '</div>' +
        '<div class="meta">' + esc(metaBits.join(' · ')) +
        (eck.created ? ' · ' + esc(String(eck.created).replace('T', ' ').slice(0, 16)) : '') +
        '</div></div>' +
        grpBar +
        (url
          ? '<div class="sh-radar-ext-bar">' +
            '<a class="sh-radar-ext-link" href="' + esc(url) + '" target="_blank" rel="noopener">' +
            '<i class="bi bi-box-arrow-up-right"></i> ' +
            esc(openLabel) +
            '</a>' +
            '<span class="sh-radar-ext-url">' + esc(url) + '</span></div>'
          : '') +
        '<div class="sh-viewer-body sh-readable">' +
        plainToReadableHtml(body) +
        '</div>';

      var taskBtn = v.querySelector('.sh-radar-task');
      if (taskBtn) {
        taskBtn.onclick = function () {
          openRadarTaskChooser(item);
        };
      }
      var matchBtn = v.querySelector('.sh-radar-matching');
      if (matchBtn) {
        matchBtn.onclick = function () {
          openMatchingFromRadar(item);
        };
      }
      var archBtn = v.querySelector('.sh-radar-archive');
      if (archBtn) {
        archBtn.onclick = function () {
          archiveRadarItem(item);
        };
      }
    }

    // Detail nachladen (falls nur Listen-Stub)
    fetch(api('radar/anfragen/' + encodeURIComponent(r.id) + '/'), {
      credentials: 'same-origin',
      headers: { 'X-Requested-With': 'XMLHttpRequest' },
    })
      .then(function (resp) { return resp.json(); })
      .then(function (j) {
        if (j && j.ok && j.item) {
          paint(j.item);
        } else {
          paint(r);
        }
      })
      .catch(function () { paint(r); });
  }

  function openMatchingFromRadar(item) {
    var eck = item.eckdaten || {};
    var text = [
      item.headline || '',
      '',
      item.meta || '',
      (eck.company ? ('Firma: ' + eck.company) : ''),
      (eck.contact ? ('Ansprechpartner: ' + eck.contact) : ''),
      (item.external_url ? ('URL: ' + item.external_url) : ''),
      '',
      item.beschreibung || '',
    ].filter(function (x, i, a) {
      // drop duplicate empties
      return !(x === '' && a[i - 1] === '');
    }).join('\n');
    try {
      sessionStorage.setItem('matching_ki_from_mail', JSON.stringify({
        email_text: text,
        subject: item.headline || '',
        outer_from: eck.contact || eck.company || ((item.sources || [])[0] || 'radar'),
        from_mail: '',
      }));
    } catch (e) { /* ignore */ }
    window.location.href = '/matching/?tab=neu';
  }

  function archiveRadarItem(item) {
    fetch(api('radar/anfragen/' + encodeURIComponent(item.id) + '/verwerfen/'), {
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
        if (j && j.ok) {
          toast(_t('sh.radar_archived', 'Archiviert'));
          RADAR_ITEMS = RADAR_ITEMS.filter(function (x) { return x.id !== item.id; });
          RADAR_SELECTED = null;
          renderRadarA(RADAR_ITEMS);
          var v = document.getElementById('sh-radar-viewer');
          if (v) {
            v.innerHTML = '<div class="sh-viewer-empty">' +
              esc(_t('sh.radar_pick', 'Projekt auswählen')) + '</div>';
          }
        } else {
          toast(_t('sh.toast_error', 'Speichern fehlgeschlagen'));
        }
      })
      .catch(function () {
        toast(_t('sh.toast_error', 'Speichern fehlgeschlagen'));
      });
  }

  function openRadarTaskChooser(item) {
    // Wiederverwendet Aufgabe-Popup-Muster mit Mail-ähnlichem Stub
    var fakeMail = {
      id: 'radar:' + item.id,
      subj: item.headline || '',
      from: (item.eckdaten && item.eckdaten.contact) || item.contact || item.company || 'Radar',
      reply_email: '',
      prev: item.beschreibung || '',
      crm_name: (item.eckdaten && item.eckdaten.company) || item.company || '',
    };
    // Fallback: manuelle Aufgabe über api/aufgaben/create
    closeMailTaskChooser();
    var dueDef = tomorrowDueDateTime();
    var ovl = document.createElement('div');
    ovl.className = 'ovl open';
    ovl.id = 'sh-mail-task-ovl';
    ovl.innerHTML =
      '<div class="sh-modal sh-mail-task-modal">' +
      '<div class="mh">' +
      '<div class="ico"><i class="bi bi-check2-square"></i></div>' +
      '<div><b>' + esc(_t('sh.inbox_task', 'Aufgabe erzeugen')) + '</b>' +
      '<small class="sh-mt-subj">' + esc(item.headline || '') + '</small></div>' +
      '<button type="button" class="x" id="sh-mt-close"><i class="bi bi-x-lg"></i></button></div>' +
      '<div class="mb">' +
      '<div class="excerpt"><div class="lbl">Radar</div>' + esc(item.meta || '') + '</div>' +
      '<div class="qlbl">' + esc(_t('sh.inbox_pick_art', 'Art')) + '</div>' +
      '<div class="sh-pick-row" id="sh-mt-arts">' +
      '<button type="button" class="sh-pick on" data-art="wiedervorlage"><i class="bi bi-arrow-repeat"></i> Wiedervorlage</button>' +
      '<button type="button" class="sh-pick" data-art="anruf"><i class="bi bi-telephone"></i> Anruf</button>' +
      '<button type="button" class="sh-pick" data-art="email"><i class="bi bi-envelope"></i> E-Mail</button>' +
      '<button type="button" class="sh-pick" data-art="intern"><i class="bi bi-briefcase"></i> Intern</button>' +
      '</div>' +
      '<div class="qlbl">' + esc(_t('sh.inbox_pick_due', 'Fälligkeit')) + '</div>' +
      '<div class="sh-due-grid">' +
      '<div class="inp"><label>Tag</label><input type="date" id="sh-mt-date" value="' + esc(dueDef.date) + '"></div>' +
      '<div class="inp"><label>Uhrzeit</label><input type="time" id="sh-mt-time" value="' + esc(dueDef.time) + '"></div>' +
      '</div>' +
      '<div class="inp"><label>Notiz</label><textarea id="sh-mt-notiz" rows="3">' +
      esc('Radar: ' + (item.headline || '') + (item.external_url ? ('\n' + item.external_url) : '')) +
      '</textarea></div>' +
      '<button type="button" class="primary" id="sh-mt-save"><i class="bi bi-check2"></i> Aufgabe anlegen</button>' +
      '</div></div>';
    document.body.appendChild(ovl);
    var selectedArt = 'wiedervorlage';
    ovl.querySelectorAll('#sh-mt-arts .sh-pick').forEach(function (b) {
      b.addEventListener('click', function () {
        ovl.querySelectorAll('#sh-mt-arts .sh-pick').forEach(function (x) { x.classList.remove('on'); });
        b.classList.add('on');
        selectedArt = b.getAttribute('data-art') || 'wiedervorlage';
        applyArtDueDefaults(selectedArt);
      });
    });
    applyArtDueDefaults(selectedArt);
    document.getElementById('sh-mt-close').onclick = closeMailTaskChooser;
    ovl.addEventListener('click', function (ev) {
      if (ev.target === ovl) closeMailTaskChooser();
    });
    document.getElementById('sh-mt-save').onclick = function () {
      var notiz = (document.getElementById('sh-mt-notiz') || {}).value || '';
      var dateEl = document.getElementById('sh-mt-date');
      var timeEl = document.getElementById('sh-mt-time');
      var save = document.getElementById('sh-mt-save');
      save.disabled = true;
      fetch(api('aufgaben/create/'), {
        method: 'POST',
        credentials: 'same-origin',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrfToken(),
          'X-Requested-With': 'XMLHttpRequest',
        },
        body: JSON.stringify({
          art: selectedArt,
          titel: (item.headline || 'Radar-Anfrage').slice(0, 240),
          beschreibung: notiz,
          ref_type: 'radar_item',
          ref_id: String(item.id),
          quelle: 'radar',
          faellig_am: dateEl ? dateEl.value : '',
          faellig_zeit: timeEl ? timeEl.value : '',
        }),
      })
        .then(function (r) { return r.json(); })
        .then(function (j) {
          save.disabled = false;
          if (j && j.ok) {
            closeMailTaskChooser();
            toast(_t('sh.toast_mail_task', 'Aufgabe erzeugt'));
          } else {
            toast(j.error || _t('sh.toast_error', 'Speichern fehlgeschlagen'));
          }
        })
        .catch(function () {
          save.disabled = false;
          toast(_t('sh.toast_error', 'Speichern fehlgeschlagen'));
        });
    };
    // silence unused
    void fakeMail;
  }

  function stopRadarBPoll() {
    if (radarBPollTimer) {
      clearTimeout(radarBPollTimer);
      radarBPollTimer = null;
    }
  }

  function radarBTabActive() {
    var tab = document.querySelector('#shaduler-root .mtab.on');
    return !!(tab && tab.getAttribute('data-t') === 'radar_berater');
  }

  function scheduleRadarBPoll(delayMs) {
    stopRadarBPoll();
    if (!radarBTabActive()) return;
    radarBPollTimer = setTimeout(function () {
      radarBPollTimer = null;
      if (!radarBTabActive()) return;
      if (document.visibilityState === 'hidden') {
        scheduleRadarBPoll(RADAR_B_POLL_MS);
        return;
      }
      loadRadarB({ soft: true });
      scheduleRadarBPoll(RADAR_B_POLL_MS);
    }, Math.max(30000, delayMs || RADAR_B_POLL_MS));
  }

  function startRadarBPoll() {
    scheduleRadarBPoll(RADAR_B_POLL_MS);
  }


  function loadRadarB(opts) {
    opts = opts || {};
    var soft = !!opts.soft;
    renderRadarBToolbar();
    var list = document.getElementById('sh-radar-b-list');
    var viewer = document.getElementById('sh-radar-b-viewer');
    if (!soft) {
      if (list) list.innerHTML = '<div class="sh-viewer-loading">' + esc(_t('sh.loading', 'Laden…')) + '</div>';
      if (viewer) {
        viewer.innerHTML = '<div class="sh-viewer-empty">' + esc(_t('sh.radar_b_pick', 'Berater auswählen')) + '</div>';
      }
    }
    var btn = document.getElementById('sh-radar-b-refresh');
    if (btn && !btn.dataset.bound) {
      btn.dataset.bound = '1';
      btn.onclick = function () {
        btn.disabled = true;
        btn.classList.add('busy');
        fetch(api('radar/berater/reindex/'), {
          method: 'POST',
          credentials: 'same-origin',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': (document.cookie.match(/csrftoken=([^;]+)/) || [])[1] || '',
            'X-Requested-With': 'XMLHttpRequest',
          },
          body: JSON.stringify({ reindex: true }),
        })
          .then(function (r) { return r.json(); })
          .then(function (d) {
            btn.disabled = false;
            btn.classList.remove('busy');
            if (!d.ok) {
              toast(d.error || _t('sh.toast_error', 'Index-Update fehlgeschlagen'));
              return;
            }
            toast(_t('sh.radar_b_reindex_ok', 'Index') + ': ' +
              (d.seeded || 0) + ' sync' +
              (d.deleted != null ? (', −' + d.deleted) : '') +
              (d.reindex && d.reindex.indexed != null ? (', ES ' + d.reindex.indexed) : ''));
            loadRadarB({ soft: true });
          })
          .catch(function () {
            btn.disabled = false;
            btn.classList.remove('busy');
            toast(_t('sh.toast_error', 'Index-Update fehlgeschlagen'));
          });
      };
    }
    var pasteBtn = document.getElementById('sh-radar-paste-btn');
    if (pasteBtn && !pasteBtn.dataset.bound) {
      pasteBtn.dataset.bound = '1';
      pasteBtn.onclick = function () {
        var inp = document.getElementById('sh-radar-paste');
        var text = inp ? String(inp.value || '').trim() : '';
        if (!text) { toast(_t('sh.radar_b_paste_need', 'Gulp- oder Freelancermap-URL/ID eingeben')); return; }
        pasteBtn.disabled = true;
        fetch(api('radar/berater/einfuegen/'), {
          method: 'POST',
          credentials: 'same-origin',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': (document.cookie.match(/csrftoken=([^;]+)/) || [])[1] || '',
            'X-Requested-With': 'XMLHttpRequest',
          },
          body: JSON.stringify({ text: text }),
        })
          .then(function (r) { return r.json(); })
          .then(function (d) {
            pasteBtn.disabled = false;
            if (!d.ok) {
              toast(d.error || _t('sh.toast_error', 'Fehler'));
              return;
            }
            if (inp) inp.value = '';
            toast(d.fetched
              ? _t('sh.radar_b_paste_ok', 'Profil übernommen')
              : _t('sh.radar_b_paste_placeholder', 'Platzhalter angelegt (Gulp-/FM-Login für Details)'));
            loadRadarB({ soft: true });
          })
          .catch(function () {
            pasteBtn.disabled = false;
            toast(_t('sh.toast_error', 'Fehler'));
          });
      };
    }
    var seedBtn = document.getElementById('sh-radar-b-seed');
    if (seedBtn && !seedBtn.dataset.bound) {
      seedBtn.dataset.bound = '1';
      seedBtn.onclick = function () {
        seedBtn.disabled = true;
        seedBtn.classList.add('busy');
        fetch(api('radar/berater/seed/'), {
          method: 'POST',
          credentials: 'same-origin',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': (document.cookie.match(/csrftoken=([^;]+)/) || [])[1] || '',
            'X-Requested-With': 'XMLHttpRequest',
          },
          body: JSON.stringify({ limit: 0, reindex: true }),
        })
          .then(function (r) { return r.json(); })
          .then(function (d) {
            seedBtn.disabled = false;
            seedBtn.classList.remove('busy');
            if (!d.ok) {
              toast(d.error || _t('sh.toast_error', 'CRM-Seed fehlgeschlagen'));
              return;
            }
            toast(_t('sh.radar_b_seed_ok', 'CRM-Seed') + ': ' +
              (d.seeded || 0) + ' / CRM gulp_id: ' + (d.crm_with_gulp != null ? d.crm_with_gulp : '?'));
            loadRadarB({ soft: true });
          })
          .catch(function () {
            seedBtn.disabled = false;
            seedBtn.classList.remove('busy');
            toast(_t('sh.toast_error', 'CRM-Seed fehlgeschlagen'));
          });
      };
    }
    var gulpBtn = document.getElementById('sh-radar-b-gulp-refresh');
    if (gulpBtn && !gulpBtn.dataset.bound) {
      gulpBtn.dataset.bound = '1';
      gulpBtn.dataset.labelHtml = gulpBtn.innerHTML;
      gulpBtn.onclick = function () {
        if (gulpBtn.disabled) return;
        gulpBtn.disabled = true;
        gulpBtn.classList.add('busy');
        gulpBtn.innerHTML = '<i class="bi bi-hourglass-split"></i> ' +
          esc(_t('sh.radar_b_gulp_busy', 'Gulp läuft…'));
        var hintEl = document.getElementById('sh-radar-b-hint');
        var hintPrev = hintEl ? hintEl.textContent : '';
        if (hintEl) {
          hintEl.textContent = _t('sh.radar_b_gulp_run', 'Gulp-Check läuft (max. 50) …');
        }
        toast(_t('sh.radar_b_gulp_run', 'Gulp-Check läuft (max. 50) …'), 8000);
        var selId = RADAR_B_SELECTED && RADAR_B_SELECTED.id ? RADAR_B_SELECTED.id : null;
        fetch(api('radar/berater/gulp-aktualisieren/'), {
          method: 'POST',
          credentials: 'same-origin',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': (document.cookie.match(/csrftoken=([^;]+)/) || [])[1] || '',
            'X-Requested-With': 'XMLHttpRequest',
          },
          body: JSON.stringify({ limit: 50, delay: 0.35 }),
        })
          .then(function (r) {
            return r.json().then(function (j) { return { ok: r.ok, status: r.status, j: j }; });
          })
          .then(function (pack) {
            gulpBtn.disabled = false;
            gulpBtn.classList.remove('busy');
            gulpBtn.innerHTML = gulpBtn.dataset.labelHtml || gulpBtn.innerHTML;
            var d = pack.j || {};
            if (hintEl && hintPrev) hintEl.textContent = hintPrev;
            if (d.needs_auth || pack.status === 401) {
              toast(d.error || _t('sh.radar_b_gulp_auth', 'Gulp-Login fehlt — CV-Extractor Session erneuern'), 6000);
              return;
            }
            if (!d.ok && d.error) {
              toast(d.error, 6000);
              return;
            }
            var msg =
              _t('sh.radar_b_gulp_ok', 'Gulp') + ': ' +
              (d.scanned || 0) + ' geprüft · ' +
              (d.updated || 0) + ' geändert · ' +
              (d.unchanged || 0) + ' gleich · ' +
              (d.gone || 0) + ' weg · ' +
              (d.errors || 0) + ' Fehler';
            toast(msg, 7000);
            loadRadarB({ soft: true, reselectId: selId });
          })
          .catch(function () {
            gulpBtn.disabled = false;
            gulpBtn.classList.remove('busy');
            gulpBtn.innerHTML = gulpBtn.dataset.labelHtml || gulpBtn.innerHTML;
            if (hintEl && hintPrev) hintEl.textContent = hintPrev;
            toast(_t('sh.toast_error', 'Gulp-Update fehlgeschlagen'), 5000);
          });
      };
    }
    var availBtn = document.getElementById('sh-radar-b-gulp-available');
    if (availBtn && !availBtn.dataset.bound) {
      availBtn.dataset.bound = '1';
      availBtn.dataset.labelHtml = availBtn.innerHTML;
      availBtn.onclick = function () {
        if (availBtn.disabled) return;
        availBtn.disabled = true;
        availBtn.classList.add('busy');
        availBtn.innerHTML = '<i class="bi bi-hourglass-split"></i> ' +
          esc(_t('sh.radar_b_gulp_av_busy', 'Verfügbare laden…'));
        var hintEl = document.getElementById('sh-radar-b-hint');
        var hintPrev = hintEl ? hintEl.textContent : '';
        if (hintEl) {
          hintEl.textContent = _t('sh.radar_b_gulp_av_run', 'Talentfinder verfügbar → Radar…');
        }
        toast(_t('sh.radar_b_gulp_av_run', 'Talentfinder verfügbar → Radar…'), 10000);
        fetch(api('radar/berater/gulp-verfuegbar/'), {
          method: 'POST',
          credentials: 'same-origin',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': (document.cookie.match(/csrftoken=([^;]+)/) || [])[1] || '',
            'X-Requested-With': 'XMLHttpRequest',
          },
          body: JSON.stringify({ limit: 40, pages: 2, page_size: 20, delay: 0.35, enrich: true }),
        })
          .then(function (r) {
            return r.json().then(function (j) { return { ok: r.ok, status: r.status, j: j }; });
          })
          .then(function (pack) {
            availBtn.disabled = false;
            availBtn.classList.remove('busy');
            availBtn.innerHTML = availBtn.dataset.labelHtml || availBtn.innerHTML;
            var d = pack.j || {};
            if (hintEl && hintPrev) hintEl.textContent = hintPrev;
            if (d.needs_auth || pack.status === 401) {
              toast(d.error || _t('sh.radar_b_gulp_auth', 'Gulp-Login fehlt — CV-Extractor Session erneuern'), 6000);
              return;
            }
            if (!d.ok && d.error) {
              toast(d.error, 6000);
              return;
            }
            toast(
              _t('sh.radar_b_gulp_av_ok', 'Verfügbare') + ': ' +
              (d.scanned || 0) + ' geprüft · ' +
              (d.created || 0) + ' neu · ' +
              (d.updated || 0) + ' aktualisiert · ' +
              (d.crm_updated || 0) + ' CRM · ' +
              (d.errors || 0) + ' Fehler',
              8000
            );
            loadRadarB({ soft: true });
          })
          .catch(function () {
            availBtn.disabled = false;
            availBtn.classList.remove('busy');
            availBtn.innerHTML = availBtn.dataset.labelHtml || availBtn.innerHTML;
            if (hintEl && hintPrev) hintEl.textContent = hintPrev;
            toast(_t('sh.toast_error', 'Verfügbare-Sync fehlgeschlagen'), 5000);
          });
      };
    }
    var flAvailBtn = document.getElementById('sh-radar-b-fl-available');
    if (flAvailBtn && !flAvailBtn.dataset.bound) {
      flAvailBtn.dataset.bound = '1';
      flAvailBtn.dataset.labelHtml = flAvailBtn.innerHTML;
      flAvailBtn.onclick = function () {
        if (flAvailBtn.disabled) return;
        flAvailBtn.disabled = true;
        flAvailBtn.classList.add('busy');
        flAvailBtn.innerHTML = '<i class="bi bi-hourglass-split"></i> ' +
          esc(_t('sh.radar_b_fl_av_busy', 'FM Verfügbare laden…'));
        var hintEl = document.getElementById('sh-radar-b-hint');
        var hintPrev = hintEl ? hintEl.textContent : '';
        if (hintEl) {
          hintEl.textContent = _t('sh.radar_b_fl_av_run', 'Freelancermap verfügbar → Radar…');
        }
        toast(_t('sh.radar_b_fl_av_run', 'Freelancermap verfügbar → Radar…'), 10000);
        fetch(api('radar/berater/fl-verfuegbar/'), {
          method: 'POST',
          credentials: 'same-origin',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': (document.cookie.match(/csrftoken=([^;]+)/) || [])[1] || '',
            'X-Requested-With': 'XMLHttpRequest',
          },
          body: JSON.stringify({ limit: 36, pages: 2, delay: 0.15 }),
        })
          .then(function (r) {
            return r.json().then(function (j) { return { ok: r.ok, status: r.status, j: j }; });
          })
          .then(function (pack) {
            flAvailBtn.disabled = false;
            flAvailBtn.classList.remove('busy');
            flAvailBtn.innerHTML = flAvailBtn.dataset.labelHtml || flAvailBtn.innerHTML;
            var d = pack.j || {};
            if (hintEl && hintPrev) hintEl.textContent = hintPrev;
            if (!d.ok && d.error) {
              toast(d.error, 6000);
              return;
            }
            toast(
              _t('sh.radar_b_fl_av_ok', 'Freelancermap') + ': ' +
              (d.scanned || 0) + ' geprüft · ' +
              (d.created || 0) + ' neu · ' +
              (d.updated || 0) + ' aktualisiert · ' +
              (d.crm_updated || 0) + ' CRM · ' +
              (d.errors || 0) + ' Fehler' +
              (d.fm_total != null ? (' · FM ' + d.fm_total) : ''),
              8000
            );
            loadRadarB({ soft: true });
          })
          .catch(function () {
            flAvailBtn.disabled = false;
            flAvailBtn.classList.remove('busy');
            flAvailBtn.innerHTML = flAvailBtn.dataset.labelHtml || flAvailBtn.innerHTML;
            if (hintEl && hintPrev) hintEl.textContent = hintPrev;
            toast(_t('sh.toast_error', 'Freelancermap-Sync fehlgeschlagen'), 5000);
          });
      };
    }
    var statusParam = RADAR_B_AVAIL ? 'neu' : 'all';
    var q = 'radar/berater/?demo=0&status=' + encodeURIComponent(statusParam) +
      '&refresh=0' +
      '&days=' + encodeURIComponent(String(RADAR_B_DAYS)) +
      '&sort=' + encodeURIComponent(RADAR_B_SORT || 'date_desc') +
      '&available=' + (RADAR_B_AVAIL ? '1' : '0') +
      '&seed=1&limit=10000';
    if (RADAR_B_Q) q += '&q=' + encodeURIComponent(RADAR_B_Q);
    if (RADAR_B_SOURCE) q += '&source=' + encodeURIComponent(RADAR_B_SOURCE);
    if (RADAR_B_MATCH) q += '&match=' + encodeURIComponent(RADAR_B_MATCH);
    fetch(api(q), {
      credentials: 'same-origin',
      headers: { 'X-Requested-With': 'XMLHttpRequest' },
    })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        RADAR_B_ITEMS = data.results || [];
        if (!soft) RADAR_B_PAGE = 1;
        renderRadarB(RADAR_B_ITEMS);
        var hint = document.getElementById('sh-radar-b-hint');
        if (hint) {
          var by = data.by_source || {};
          var parts = [];
          Object.keys(by).forEach(function (k) { if (k) parts.push(k + ': ' + by[k]); });
          var ls = data.list_source || '';
          var lsLbl = ls === 'elasticsearch' ? 'ES' : (ls === 'db' ? 'DB' : ls);
          var ei = data.es_info || {};
          var esNote = '';
          if (ls !== 'elasticsearch') {
            if (ei.search_error) esNote = ' · ES-Fehler';
            else if (ei.fallback === 'empty_index') esNote = ' · ES leer';
            else if (ei.fallback === 'filter_miss') esNote = ' · ES-Filter 0 → DB';
            else if (ei.fallback === 'es_unavailable') esNote = ' · ES offline';
            else if (ei.count != null) esNote = ' · ES docs: ' + ei.count;
          } else if (ei.count != null && data.es_total != null && ei.count !== data.es_total) {
            esNote = ' · Index ' + ei.count;
          }
          hint.textContent = data.demo
            ? _t('sh.radar_demo', 'Demo')
            : _t('sh.radar_b_hint', 'Gulp / Freelancermap') +
              (lsLbl ? (' · ' + lsLbl) : '') +
              (data.es_total != null ? (' · ' + data.es_total) : '') +
              (parts.length ? (' · ' + parts.join(', ')) : '') +
              esNote +
              (ls === 'elasticsearch'
                ? ' · Liste ES / Detail DB'
                : ' · Fallback DB (Detail DB)');
        }
        refreshStats();
        if (opts.reselectId) {
          var hit = null;
          for (var ri = 0; ri < RADAR_B_ITEMS.length; ri++) {
            if (String(RADAR_B_ITEMS[ri].id) === String(opts.reselectId)) {
              hit = RADAR_B_ITEMS[ri];
              break;
            }
          }
          if (hit) {
            var rowEl = document.querySelector(
              '#sh-radar-b-list .ritem[data-id="' + String(hit.id).replace(/"/g, '') + '"]'
            );
            openRadarBeraterItem(hit, rowEl);
          }
        }
      })
      .catch(function () {
        RADAR_B_ITEMS = [];
        renderRadarB([]);
        toast(_t('sh.radar_err', 'Radar konnte nicht geladen werden'));
      });
  }

  var RADAR_B_ITEMS = [];
  var RADAR_B_SELECTED = null;
  var RADAR_B_PAGE = 1;
  var RADAR_B_PAGE_SIZE = 20;
  var RADAR_B_Q = '';
  var RADAR_B_DAYS = 0;
  var RADAR_B_SORT = 'date_desc';
  var RADAR_B_SOURCE = '';
  var RADAR_B_STATUS = 'neu';
  var RADAR_B_MATCH = '';
  var RADAR_B_AVAIL = true;
  var RADAR_B_POLL_MS = 90000;
  var radarBPollTimer = null;
  try {
    var _bps = parseInt(localStorage.getItem('sh_radar_b_page_size') || '20', 10);
    if ([5, 10, 20, 50].indexOf(_bps) >= 0) RADAR_B_PAGE_SIZE = _bps;
    var _bd = parseInt(localStorage.getItem('sh_radar_b_days') || '0', 10);
    if ([0, 1, 2, 7, 30].indexOf(_bd) >= 0) RADAR_B_DAYS = _bd;
  } catch (eB) { /* ignore */ }

  function renderRadarBToolbar() {
    var t = document.getElementById('sh-radar-b-toolbar');
    if (!t) return;
    var sizes = [5, 10, 20, 50];
    var sizeOpts = sizes.map(function (n) {
      return '<option value="' + n + '"' + (RADAR_B_PAGE_SIZE === n ? ' selected' : '') + '>' + n + '</option>';
    }).join('');
    var dayOpts = [
      [0, _t('sh.radar_days_all', 'alle')],
      [1, _t('sh.radar_days_1', 'heute')],
      [2, _t('sh.radar_days_2', '2 Tage')],
      [7, _t('sh.radar_days_7', '7 Tage')],
      [30, _t('sh.radar_days_30', '30 Tage')],
    ].map(function (p) {
      return '<option value="' + p[0] + '"' + (RADAR_B_DAYS === p[0] ? ' selected' : '') + '>' + esc(p[1]) + '</option>';
    }).join('');
    t.innerHTML =
      '<form class="sh-inbox-search" id="sh-radar-b-search">' +
      '<input type="search" id="sh-radar-b-q" value="' + esc(RADAR_B_Q) + '" ' +
      'placeholder="' + esc(_t('sh.radar_b_search_ph', 'Name, Gulp-/FM-ID, Skills, Ort …')) + '" />' +
      '<button type="submit" class="pri"><i class="bi bi-search"></i> ' +
      esc(_t('sh.inbox_search', 'Suchen')) + '</button></form>' +
      '<div class="sh-inbox-opts">' +
      '<select id="sh-radar-b-days">' + dayOpts + '</select>' +
      '<select id="sh-radar-b-sort">' +
      '<option value="date_desc"' + (RADAR_B_SORT === 'date_desc' ? ' selected' : '') + '>' +
      esc(_t('sh.inbox_sort_new', 'Datum: neueste')) + '</option>' +
      '<option value="date_asc"' + (RADAR_B_SORT === 'date_asc' ? ' selected' : '') + '>' +
      esc(_t('sh.inbox_sort_old', 'Datum: älteste')) + '</option>' +
      '</select>' +
      '<select id="sh-radar-b-match">' +
      '<option value="">' + esc(_t('sh.radar_b_match_all', 'Match: alle')) + '</option>' +
      '<option value="bekannt"' + (RADAR_B_MATCH === 'bekannt' ? ' selected' : '') + '>bekannt (CRM)</option>' +
      '<option value="unbekannt"' + (RADAR_B_MATCH === 'unbekannt' ? ' selected' : '') + '>unbekannt</option>' +
      '</select>' +
      '<select id="sh-radar-b-source" title="Quelle">' +
      '<option value="">' + esc(_t('sh.radar_b_src_all', 'Quelle: alle')) + '</option>' +
      '<option value="gulp"' + (RADAR_B_SOURCE === 'gulp' ? ' selected' : '') + '>Gulp</option>' +
      '<option value="freelancermap"' + (RADAR_B_SOURCE === 'freelancermap' ? ' selected' : '') + '>Freelancermap</option>' +
      '</select>' +
      '<select id="sh-radar-b-avail">' +
      '<option value="1"' + (RADAR_B_AVAIL ? ' selected' : '') + '>' + esc(_t('sh.radar_b_avail', 'verfügbar/neu')) + '</option>' +
      '<option value="0"' + (!RADAR_B_AVAIL ? ' selected' : '') + '>' + esc(_t('sh.radar_b_allvis', 'alle sichtbaren')) + '</option>' +
      '</select>' +
      '<label class="sh-inbox-pagesize"><span>' + esc(_t('sh.inbox_per_page', 'Anzeigen')) + '</span> ' +
      '<select id="sh-radar-b-pagesize">' + sizeOpts + '</select></label>' +
      '</div>';
    var form = document.getElementById('sh-radar-b-search');
    if (form) {
      form.addEventListener('submit', function (e) {
        e.preventDefault();
        var inp = document.getElementById('sh-radar-b-q');
        RADAR_B_Q = inp ? String(inp.value || '').trim() : '';
        RADAR_B_PAGE = 1;
        loadRadarB({ soft: true });
      });
    }
    var days = document.getElementById('sh-radar-b-days');
    if (days) days.onchange = function () {
      RADAR_B_DAYS = parseInt(days.value, 10) || 0;
      try { localStorage.setItem('sh_radar_b_days', String(RADAR_B_DAYS)); } catch (e2) {}
      RADAR_B_PAGE = 1;
      loadRadarB({ soft: true });
    };
    var sort = document.getElementById('sh-radar-b-sort');
    if (sort) sort.onchange = function () {
      RADAR_B_SORT = sort.value || 'date_desc';
      loadRadarB({ soft: true });
    };
    var match = document.getElementById('sh-radar-b-match');
    if (match) match.onchange = function () {
      RADAR_B_MATCH = match.value || '';
      loadRadarB({ soft: true });
    };
    var srcSel = document.getElementById('sh-radar-b-source');
    if (srcSel) srcSel.onchange = function () {
      RADAR_B_SOURCE = srcSel.value || '';
      RADAR_B_PAGE = 1;
      loadRadarB({ soft: true });
    };
    var avail = document.getElementById('sh-radar-b-avail');
    if (avail) avail.onchange = function () {
      RADAR_B_AVAIL = avail.value !== '0';
      loadRadarB({ soft: true });
    };
    var psz = document.getElementById('sh-radar-b-pagesize');
    if (psz) psz.onchange = function () {
      RADAR_B_PAGE_SIZE = parseInt(psz.value, 10) || 20;
      RADAR_B_PAGE = 1;
      try { localStorage.setItem('sh_radar_b_page_size', String(RADAR_B_PAGE_SIZE)); } catch (e3) {}
      renderRadarB(RADAR_B_ITEMS);
    };
  }

  function renderRadarB(items) {
    var c = document.getElementById('sh-radar-b-list');
    if (!c) return;
    items = items || [];
    var total = items.length;
    var size = Math.max(1, RADAR_B_PAGE_SIZE || 20);
    var pages = Math.max(1, Math.ceil(total / size) || 1);
    if (RADAR_B_PAGE > pages) RADAR_B_PAGE = pages;
    if (RADAR_B_PAGE < 1) RADAR_B_PAGE = 1;
    var start = (RADAR_B_PAGE - 1) * size;
    var slice = items.slice(start, start + size);
    c.innerHTML = '';
    if (!total) {
      var emptyExtra = '';
      try {
        var hintEl = document.getElementById('sh-radar-b-hint');
        if (hintEl && /Index\s+\d+/.test(hintEl.textContent || '')) {
          emptyExtra = '<div style="margin-top:8px;opacity:.75">' +
            esc(_t('sh.radar_b_filter_empty',
              'Index hat Einträge, aktueller Filter trifft 0. Bitte „alle sichtbaren“ wählen oder ↻.')) +
            '</div>';
        }
      } catch (eEmpty) { /* ignore */ }
      c.innerHTML = '<div class="sh-viewer-empty">' +
        esc(_t('sh.radar_b_empty', 'Keine Berater')) +
        ' — ' + esc(_t('sh.radar_b_empty_hint', '„CRM-Seed“ oder Gulp-/FM-URL einfügen')) +
        emptyExtra + '</div>';
    }
    var lbl = { known: '✔ CRM', maybe: '? unsicher', new: 'neu' };
    slice.forEach(function (r) {
      var e = document.createElement('div');
      e.className = 'ritem' + (RADAR_B_SELECTED && RADAR_B_SELECTED.id === r.id ? ' on' : '');
      e.setAttribute('data-id', r.id);
      e.innerHTML =
        '<div class="top"><span class="mstat ' + esc(r.st || 'new') + '">' +
        esc(lbl[r.st] || r.match_status || r.st) + '</span>' +
        '<b class="hl">' + esc(r.name || '') + '</b>' +
        '<span class="src">' + esc(r.src || 'gulp') + '</span>' +
        (r.age ? '<span class="age">' + esc(r.age) + '</span>' : '') +
        '</div>' +
        '<div class="meta">' + esc(r.meta || '') + '</div>' +
        '<div class="meta" style="color:var(--status-green)">' + esc(r.note || '') + '</div>';
      e.onclick = function () { openRadarBeraterItem(r, e); };
      c.appendChild(e);
    });
    var countEl = document.getElementById('r-b-new');
    if (countEl) countEl.textContent = String(total);
    renderShPager({
      elId: 'sh-radar-b-pager',
      total: total,
      page: RADAR_B_PAGE,
      pages: pages,
      page_size: size,
      emptyLabel: _t('sh.radar_b_empty', 'Keine Berater'),
      onPage: function (p) {
        if (p === RADAR_B_PAGE) return;
        RADAR_B_PAGE = p;
        renderRadarB(RADAR_B_ITEMS);
      },
    });
  }

  function openRadarBeraterItem(r, rowEl) {
    RADAR_B_SELECTED = r;
    document.querySelectorAll('#sh-radar-b-list .ritem.on').forEach(function (el) {
      el.classList.remove('on');
    });
    if (rowEl) rowEl.classList.add('on');
    var v = document.getElementById('sh-radar-b-viewer');
    if (!v || !r || !r.id) return;

    function paint(item) {
      item = item || r;
      var skills = (item.skills || []).map(function (s) {
        return '<span class="src" style="margin:2px">' + esc(s) + '</span>';
      }).join(' ');
      var gulpUrl = item.profil_url || (item.gulp_id
        ? ('https://www.gulp.de/talentfinder/app/experten?gulpId=' +
          encodeURIComponent(String(item.gulp_id)))
        : '');
      var isFm = !!(item.fm_id || (item.src || '').toLowerCase() === 'freelancermap');
      var portalLabel = isFm ? 'Freelancermap' : 'Gulp';
      var kontaktUrl = item.kontakt_url || '';
      if (!kontaktUrl && item.mongo_id && !isFm) {
        kontaktUrl = 'https://www.gulp.de/talentfinder/app/experten/' +
          encodeURIComponent(String(item.mongo_id)) + '/kontaktieren';
      }
      if (!kontaktUrl && isFm && item.profil_url) {
        kontaktUrl = item.profil_url;
      }
      var kontaktTitle = isFm
        ? _t('sh.radar_b_kontakt_fm_title', 'Über Freelancermap anschreiben (Login nötig)')
        : _t('sh.radar_b_kontakt_title', 'Über Gulp anschreiben (kostenpflichtig, ca. 50 €)');
      var acts =
        '<div class="racts sh-viewer-acts">' +
        (gulpUrl
          ? '<a class="sh-radar-ext" href="' + esc(gulpUrl) + '" target="_blank" rel="noopener">' +
            '<i class="bi bi-box-arrow-up-right"></i> ' + esc(portalLabel) + '</a>'
          : '') +
        (kontaktUrl
          ? '<a class="sh-radar-ext pri" href="' + esc(kontaktUrl) +
            '" target="_blank" rel="noopener" title="' +
            esc(kontaktTitle) + '">' +
            '<i class="bi bi-envelope"></i> ' +
            esc(_t('sh.radar_b_kontakt', 'Anschreiben')) + '</a>'
          : '') +
        (item.gulp_id
          ? '<button type="button" id="sh-radar-b-gulp-one" title="' +
            esc(_t('sh.radar_b_gulp_one_title', 'Diesen Berater bei Gulp prüfen')) + '">' +
            '<i class="bi bi-cloud-arrow-down"></i> ' +
            esc(_t('sh.radar_b_gulp_one', 'Gulp prüfen')) + '</button>'
          : '') +
        (item.crm_url
          ? '<a class="sh-radar-ext" href="' + esc(item.crm_url) + '" target="_blank" rel="noopener">' +
            '<i class="bi bi-person-badge"></i> CRM</a>'
          : '<button type="button" disabled>' +
            esc(_t('sh.radar_b_crm_later', 'CRM-Anlage folgt')) + '</button>') +
        '<button type="button" class="pri" id="sh-radar-b-ok">' +
        '<i class="bi bi-check2"></i> ' + esc(_t('sh.radar_b_confirm', 'Bestätigen')) + '</button>' +
        '<button type="button" id="sh-radar-b-no">' +
        '<i class="bi bi-x-lg"></i> ' + esc(_t('sh.radar_b_dismiss', 'Verwerfen')) + '</button>' +
        '</div>';
      v.innerHTML =
        acts +
        '<div class="sh-viewer-head">' +
        '<div class="from">' + esc(item.name || '') +
        (item.gulp_id ? ' · Gulp ' + esc(item.gulp_id) : '') +
        (item.fm_id ? ' · FM ' + esc(String(item.fm_id)) : '') + '</div>' +
        '<div class="meta">' + esc(item.meta || '') + '</div>' +
        '<div class="meta">' + esc(item.note || '') +
        (item.verfuegbar_ab ? (' · ab ' + esc(String(item.verfuegbar_ab))) : '') +
        (item.satz != null && item.satz !== '' ? (' · ' + esc(String(item.satz)) + ' €') : '') +
        (item.ort ? (' · ' + esc(String(item.ort))) : '') +
        (item.cv_versions ? (' · CV-Versionen: ' + esc(String(item.cv_versions))) : '') +
        ' · ' + esc(_t('sh.radar_b_from_db', 'Detail aus DB')) +
        '</div></div>' +
        (skills ? '<div style="margin:8px 0">' + skills + '</div>' : '') +
        '<div class="sh-viewer-body sh-readable" style="white-space:pre-wrap">' +
        esc((item.beschreibung || '').slice(0, 4000) || '—') + '</div>';
      var ok = document.getElementById('sh-radar-b-ok');
      var no = document.getElementById('sh-radar-b-no');
      var gulpOne = document.getElementById('sh-radar-b-gulp-one');
      if (gulpOne) gulpOne.onclick = function () {
        if (gulpOne.disabled) return;
        gulpOne.disabled = true;
        gulpOne.classList.add('busy');
        var prev = gulpOne.innerHTML;
        gulpOne.innerHTML = '<i class="bi bi-hourglass-split"></i> …';
        toast(_t('sh.radar_b_gulp_one_run', 'Gulp prüft diesen Berater…'), 5000);
        fetch(api('radar/berater/gulp-aktualisieren/'), {
          method: 'POST',
          credentials: 'same-origin',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': (document.cookie.match(/csrftoken=([^;]+)/) || [])[1] || '',
            'X-Requested-With': 'XMLHttpRequest',
          },
          body: JSON.stringify({ ids: [item.id], limit: 1, delay: 0 }),
        })
          .then(function (res) {
            return res.json().then(function (j) { return { status: res.status, j: j }; });
          })
          .then(function (pack) {
            gulpOne.disabled = false;
            gulpOne.classList.remove('busy');
            gulpOne.innerHTML = prev;
            var d = pack.j || {};
            if (d.needs_auth || pack.status === 401) {
              toast(d.error || _t('sh.radar_b_gulp_auth', 'Gulp-Login fehlt — CV-Extractor Session erneuern'), 6000);
              return;
            }
            var row = (d.results && d.results[0]) || {};
            var act = row.action || '';
            if (act === 'updated') {
              toast(_t('sh.radar_b_gulp_one_upd', 'Aktualisiert') +
                (row.changed && row.changed.length ? (': ' + row.changed.join(', ')) : ''), 6000);
            } else if (act === 'unchanged') {
              toast(_t('sh.radar_b_gulp_one_same', 'Unverändert (Gulp ok)'), 4000);
            } else if (act === 'gone') {
              toast(_t('sh.radar_b_gulp_one_gone', 'Nicht mehr in Gulp'), 6000);
            } else if (d.error || row.error) {
              toast(d.error || row.error, 6000);
            } else {
              toast(_t('sh.radar_b_gulp_ok', 'Gulp') + ': ' + (act || 'ok'), 4000);
            }
            loadRadarB({ soft: true, reselectId: item.id });
          })
          .catch(function () {
            gulpOne.disabled = false;
            gulpOne.classList.remove('busy');
            gulpOne.innerHTML = prev;
            toast(_t('sh.toast_error', 'Gulp-Update fehlgeschlagen'), 5000);
          });
      };
      if (ok) ok.onclick = function () {
        fetch(api('radar/berater/' + encodeURIComponent(item.id) + '/bestaetigen/'), {
          method: 'POST',
          credentials: 'same-origin',
          headers: {
            'X-CSRFToken': (document.cookie.match(/csrftoken=([^;]+)/) || [])[1] || '',
            'X-Requested-With': 'XMLHttpRequest',
          },
        }).then(function (res) { return res.json(); }).then(function (d) {
          toast(d.ok ? _t('sh.toast_link', 'Bestätigt') : (d.error || 'Fehler'));
          loadRadarB({ soft: true });
        });
      };
      if (no) no.onclick = function () {
        fetch(api('radar/berater/' + encodeURIComponent(item.id) + '/verwerfen/'), {
          method: 'POST',
          credentials: 'same-origin',
          headers: {
            'X-CSRFToken': (document.cookie.match(/csrftoken=([^;]+)/) || [])[1] || '',
            'X-Requested-With': 'XMLHttpRequest',
          },
        }).then(function (res) { return res.json(); }).then(function (d) {
          toast(d.ok ? _t('sh.toast_dismiss', 'Verworfen') : (d.error || 'Fehler'));
          loadRadarB({ soft: true });
        });
      };
    }

    // Liste = ES (ohne Text) → Detail aus DB laden
    v.innerHTML = '<div class="sh-viewer-loading">' + esc(_t('sh.loading', 'Laden…')) + '</div>';
    fetch(api('radar/berater/' + encodeURIComponent(r.id) + '/?chars=4000'), {
      credentials: 'same-origin',
      headers: { 'X-Requested-With': 'XMLHttpRequest' },
    })
      .then(function (res) { return res.json(); })
      .then(function (d) {
        if (d && d.ok && d.item) {
          paint(d.item);
        } else {
          paint(r);
          toast(d && d.error ? d.error : _t('sh.radar_b_detail_err', 'Detail nicht geladen'));
        }
      })
      .catch(function () {
        paint(r);
        toast(_t('sh.radar_b_detail_err', 'Detail nicht geladen'));
      });
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
    if (done) done.onclick = onWeiter;
    if (act) act.onclick = function () { showPhase('res'); };
    if (ovl) ovl.addEventListener('click', function (e) {
      if (e.target === ovl) closeModal();
    });
  }

  function crmDetailUrl(t, tab) {
    if (!t) return '';
    var base = '';
    if (t.crm_url) {
      base = String(t.crm_url);
    } else if (t.ref_id) {
      if (t.ref_type === 'berater' || t.ref_type === 'ansprechpartner') {
        base = '/crm/berater/?detail=' + encodeURIComponent(t.ref_id);
      } else if (t.ref_type === 'firma') {
        base = '/crm/kunden/?detail=' + encodeURIComponent(t.ref_id);
      }
    }
    if (!base) return '';
    if (tab) {
      base += (base.indexOf('?') >= 0 ? '&' : '?') + 'tab=' + encodeURIComponent(tab);
    }
    return base;
  }

  function onWeiter() {
    var t = currentTask;
    var url = '';
    // Nach Erledigt → CRM Notizen (neues Fenster); nach Snooze nur schließen
    var lastAction = (t && t._lastAction) || '';
    if (lastAction !== 'snooze') {
      url = crmDetailUrl(t, 'notizen');
    }
    closeModal();
    if (url) {
      window.open(url, '_blank', 'noopener');
    }
  }

  function updateWeiterButton(action) {
    var done = document.getElementById('sh-m-done');
    if (!done) return;
    var hasCrm = !!crmDetailUrl(currentTask, 'notizen');
    if (action === 'snooze' || !hasCrm) {
      done.innerHTML = _t('sh.popup_weiter', 'Weiter') + ' <i class="bi bi-arrow-right"></i>';
    } else {
      done.innerHTML = _t('sh.popup_crm_notizen', 'CRM Notizen öffnen') +
        ' <i class="bi bi-box-arrow-up-right"></i>';
    }
    done.onclick = onWeiter;
  }

  function showPhase(which) {
    ['act', 'res', 'fx'].forEach(function (p) {
      var el = document.getElementById('sh-ph-' + p);
      if (!el) return;
      var on = p === which;
      el.classList.toggle('on', on);
      el.style.display = on ? '' : 'none';
    });
    if (which !== 'act') {
      var snoozeBox = document.getElementById('sh-m-snooze');
      if (snoozeBox) snoozeBox.style.display = 'none';
    }
  }

  function findResultByCode(code) {
    var list = (currentTask && currentTask.results) || [];
    for (var i = 0; i < list.length; i++) {
      if (list[i].code === code) return list[i];
    }
    if (code === 'erledigt') {
      return { code: 'erledigt', label: _t('sh.erg_erledigt', 'Erledigt ✓'), fx: [_t('sh.fx_historie', 'Historie-Eintrag')] };
    }
    if (code === 'snooze') {
      return { code: 'snooze', label: _t('sh.erg_snooze', 'Verschoben'), fx: [_t('sh.fx_snooze', 'Fälligkeit verschoben')] };
    }
    return { code: code, label: code, fx: [] };
  }

  function dialTaskPhone(t) {
    if (!t) return false;
    var phone = '';
    if (t.phone) phone = t.phone;
    if (!phone && t.excerpt && t.excerpt.phone) phone = t.excerpt.phone;
    if (!phone && t.beschreibung) {
      var m = String(t.beschreibung).match(/tel:([+\d\s\-()/]+)/i);
      if (m) phone = m[1];
    }
    phone = String(phone || '').replace(/[^\d+]/g, '');
    if (!phone) return false;
    window.location.href = 'tel:' + phone;
    return true;
  }

  function buildWhatsAppLink(phone, text) {
    var digits = normalizeWaPhone(phone).waDigits;
    if (!digits) return '';
    var url = 'https://wa.me/' + digits;
    if (text) url += '?text=' + encodeURIComponent(text);
    return url;
  }

  /** DE-Nummern → 0049… prüfen; waDigits ohne führende 00. */
  function normalizeWaPhone(raw) {
    var s = String(raw || '').replace(/[^\d+]/g, '');
    if (!s) return { norm: '', ok: false, waDigits: '' };
    if (s.charAt(0) === '+') s = '00' + s.slice(1);
    var norm = s;
    if (s.indexOf('0049') === 0) {
      norm = s;
    } else if (s.indexOf('49') === 0 && s.length >= 11) {
      norm = '00' + s;
    } else if (s.charAt(0) === '0' && s.indexOf('00') !== 0) {
      norm = '0049' + s.slice(1);
    }
    var ok = /^0049\d{6,13}$/.test(norm);
    var waDigits = ok ? norm.replace(/^00/, '') : s.replace(/^00/, '').replace(/^\+/, '');
    return { norm: ok ? norm : s, ok: ok, waDigits: waDigits };
  }

  function waDefaultText(t) {
    if (!t) return '';
    if (t.wa_text) return String(t.wa_text);
    if (t.gentext) return String(t.gentext);
    var b = String(t.beschreibung || '').trim();
    // Mail-artige Beschreibung nicht als WA-Text nehmen
    if (b && !/^Von:\s/i.test(b) && !/^Notiz:\s/i.test(b) && b.indexOf('Mail-ID:') < 0) {
      return b.replace(/\n?tel:[^\n]+/ig, '').trim();
    }
    return String(t.titel || '');
  }

  function setupWhatsAppCompose(t) {
    var waBox = document.getElementById('sh-m-wa');
    var waText = document.getElementById('sh-m-wa-text');
    var waPhone = document.getElementById('sh-m-wa-phone');
    var waMeta = document.getElementById('sh-m-wa-phone-meta');
    var waSugs = document.getElementById('sh-m-wa-phone-sugs');
    var waSend = document.getElementById('sh-m-wa-send');
    var waNote = document.getElementById('sh-m-wa-note');
    var actBtn = document.getElementById('sh-m-action');
    var actNote = document.getElementById('sh-m-actnote');
    var isWa = t && (t.art === 'sms_messenger' || t.whatsapp_url || t.wa);
    if (!waBox) return false;
    if (!isWa) {
      waBox.style.display = 'none';
      if (actBtn) actBtn.style.display = '';
      return false;
    }
    waBox.style.display = 'block';
    if (actBtn) actBtn.style.display = 'none';
    if (actNote) actNote.style.display = 'none';
    if (waText) waText.value = waDefaultText(t);

    var phone = t.phone || '';
    if (!phone && t.whatsapp_url) {
      var pm = String(t.whatsapp_url).match(/wa\.me\/(\d+)/);
      if (pm) phone = '00' + pm[1];
    }
    var phones = Array.isArray(t.phones) ? t.phones.slice() : [];
    // Mobil zuerst in Vorschlägen
    phones.sort(function (a, b) {
      return (b.is_mobile ? 1 : 0) - (a.is_mobile ? 1 : 0);
    });

    function setPhoneValue(val, fromSug) {
      if (!waPhone) return;
      var n = normalizeWaPhone(val);
      waPhone.value = n.ok ? n.norm : String(val || '');
      updatePhoneMeta();
      if (fromSug && waSugs) {
        waSugs.querySelectorAll('.sh-pick').forEach(function (el) {
          el.classList.toggle('on', el.getAttribute('data-phone') === waPhone.value
            || normalizeWaPhone(el.getAttribute('data-phone')).norm === n.norm);
        });
      }
    }

    function updatePhoneMeta() {
      if (!waPhone || !waMeta) return;
      var raw = waPhone.value.trim();
      waPhone.classList.remove('ok', 'bad');
      waMeta.classList.remove('ok', 'bad');
      if (!raw) {
        waMeta.textContent = _t('sh.wa_phone_hint', 'Format: 0049… (Mobil bevorzugt)');
        return false;
      }
      var n = normalizeWaPhone(raw);
      if (n.ok) {
        waPhone.classList.add('ok');
        waMeta.classList.add('ok');
        waPhone.value = n.norm;
        waMeta.textContent = _t('sh.wa_phone_ok', 'OK — ') + n.norm;
        return true;
      }
      waPhone.classList.add('bad');
      waMeta.classList.add('bad');
      waMeta.textContent = _t('sh.wa_phone_bad', 'Ungültig — bitte 0049… (z.B. 0049171…)');
      return false;
    }

    if (waSugs) {
      waSugs.innerHTML = '';
      var mobiles = phones.filter(function (p) { return p.is_mobile || p.field_name === 'phone_mobile' || p.field_name === 'whatsapp'; });
      var show = mobiles.length ? mobiles : phones;
      if (show.length) {
        var lbl = document.createElement('div');
        lbl.className = 'qlbl';
        lbl.style.cssText = 'width:100%;margin:0 0 4px;font-size:.75rem';
        lbl.textContent = _t('sh.wa_vorschlag', 'Vorschlag aus CRM');
        waSugs.appendChild(lbl);
      }
      show.forEach(function (p) {
        var raw = p.norm || p.raw || '';
        if (!raw) return;
        var n = normalizeWaPhone(raw);
        var b = document.createElement('button');
        b.type = 'button';
        b.className = 'sh-pick' + (p.is_mobile || p.field_name === 'phone_mobile' || p.field_name === 'whatsapp' ? ' mobile' : '');
        b.setAttribute('data-phone', n.ok ? n.norm : raw);
        b.innerHTML = '<i class="bi bi-phone"></i> ' + esc(p.label || 'Mobil') + ': ' + esc(n.ok ? n.norm : raw);
        b.addEventListener('click', function () {
          setPhoneValue(raw, true);
        });
        waSugs.appendChild(b);
      });
    }

    if (waPhone) {
      setPhoneValue(phone || (phones[0] && (phones[0].norm || phones[0].raw)) || '', false);
      waPhone.oninput = function () { updatePhoneMeta(); };
      waPhone.onchange = function () { updatePhoneMeta(); };
    }

    if (waNote) {
      waNote.textContent = _t('sh.wa_hint', 'Öffnet WhatsApp mit dem Text — danach Ergebnis wählen.');
    }
    if (waSend) {
      waSend.className = 'primary wa';
      waSend.onclick = function () {
        var text = waText ? waText.value.trim() : '';
        if (!updatePhoneMeta()) {
          toast(_t('sh.wa_phone_required', 'Bitte gültige Telefonnummer (0049…) eintragen'));
          if (waPhone) waPhone.focus();
          return;
        }
        var n = normalizeWaPhone(waPhone.value);
        var url = buildWhatsAppLink(n.norm, text);
        if (!url) {
          toast(_t('sh.wa_phone_required', 'Bitte gültige Telefonnummer (0049…) eintragen'));
          return;
        }
        if (!text) {
          toast(_t('sh.wa_empty', 'Bitte Nachricht eingeben'));
          return;
        }
        window.open(url, '_blank', 'noopener');
        showPhase('res');
      };
    }
    return true;
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
    var isWa = t && (t.art === 'sms_messenger' || t.whatsapp_url || t.wa);
    var ex = t.excerpt || {};
    var html = '';
    if (!isWa && ex.stand) html += '<div><b>' + esc(_t('sh.stand', 'Stand')) + ':</b> ' + esc(ex.stand) + '</div>';
    if (ex.hist && ex.hist.length) {
      html += '<ul>' + ex.hist.map(function (h) { return '<li>' + esc(h) + '</li>'; }).join('') + '</ul>';
    }
    var excerptEl = document.getElementById('sh-m-excerpt');
    if (html) {
      excerptEl.style.display = '';
      excerptEl.innerHTML = html;
    } else {
      excerptEl.style.display = isWa ? 'none' : '';
      excerptEl.innerHTML = isWa ? '' : ('<div class="none">' + esc(_t('sh.kein_auszug', 'Kein Auszug')) + '</div>');
    }
    document.getElementById('sh-m-action').textContent = t.action_label || _t('sh.erledigen', 'Erledigen');
    document.getElementById('sh-m-actnote').textContent = t.action_note || '';
    document.getElementById('sh-m-actnote').style.display = '';

    var snoozeBox = document.getElementById('sh-m-snooze');
    if (snoozeBox) snoozeBox.style.display = 'none';

    var isWaCompose = setupWhatsAppCompose(t);

    var actBtn = document.getElementById('sh-m-action');
    if (actBtn && !isWaCompose) {
      actBtn.style.display = '';
      actBtn.onclick = function () {
        if (t.whatsapp_url) {
          window.open(t.whatsapp_url, '_blank', 'noopener');
        } else if (t.art === 'anruf') {
          dialTaskPhone(t);
        }
        // Nach Kanal-Aktion → Ergebniswahl (Nicht erreicht / …)
        showPhase('res');
      };
    }

    var btnErledigt = document.getElementById('sh-m-erledigt');
    if (btnErledigt) {
      btnErledigt.onclick = function () {
        applyResult(findResultByCode('erledigt'));
      };
    }
    var btnVerschieben = document.getElementById('sh-m-verschieben');
    if (btnVerschieben) {
      btnVerschieben.onclick = function () {
        var box = document.getElementById('sh-m-snooze');
        var opts = document.getElementById('sh-m-snooze-opts');
        if (!box || !opts) {
          applyResult(Object.assign({}, findResultByCode('snooze'), { daten: { days: 1 } }));
          return;
        }
        if (box.style.display === 'block') {
          box.style.display = 'none';
          return;
        }
        var choices = [
          { days: 1, label: _t('sh.snooze_1d', '+1 Tag') },
          { days: 2, label: _t('sh.snooze_2d', '+2 Tage') },
          { days: 7, label: _t('sh.snooze_1w', '+1 Woche') },
        ];
        opts.innerHTML = '';
        choices.forEach(function (c) {
          var b = document.createElement('button');
          b.type = 'button';
          b.className = 'sh-pick';
          b.textContent = c.label;
          b.addEventListener('click', function () {
            applyResult(Object.assign({}, findResultByCode('snooze'), {
              label: _t('sh.erg_snooze', 'Verschoben') + ' (' + c.label + ')',
              daten: { days: c.days },
            }));
          });
          opts.appendChild(b);
        });
        box.style.display = 'block';
      };
    }

    var results = t.results || [
      { code: 'erledigt', label: _t('sh.erg_erledigt', 'Erledigt ✓'), sub: '', fx: [_t('sh.fx_historie', 'Historie-Eintrag')] },
      { code: 'snooze', label: _t('sh.erg_snooze', 'Später (+1 Tag)'), sub: '', fx: [_t('sh.fx_snooze', 'Fälligkeit +1 Tag')], daten: { days: 1 } },
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
    var isSnooze = (r.code === 'snooze') || /snooze|später|verschob/i.test(String(r.label || ''));
    var daten = r.daten && typeof r.daten === 'object' ? r.daten : {};
    if (isSnooze && daten.days == null) daten.days = 1;

    function finishLocal(action) {
      action = action || (isSnooze ? 'snooze' : 'erledigt');
      if (currentTask) currentTask._lastAction = action;
      if (currentTask && currentTask.id) {
        if (action === 'snooze') {
          // Task bleibt, Liste neu laden
          loadAufgaben();
        } else {
          TASKS = TASKS.filter(function (t) { return t.id !== currentTask.id; });
          STATS.erledigt_heute = (STATS.erledigt_heute || 0) + 1;
          renderAcc();
          refreshStats();
        }
      }
      showPhase('fx');
      var fxTitle = document.querySelector('#sh-ph-fx .qlbl');
      if (fxTitle) {
        fxTitle.innerHTML = action === 'snooze'
          ? ('<i class="bi bi-calendar-check" style="color:var(--abcona-blue)"></i> ' +
            _t('sh.popup_verschoben', 'Verschoben — automatisch passiert:'))
          : ('<i class="bi bi-check-circle" style="color:var(--status-green)"></i> ' +
            _t('sh.popup_erledigt', 'Erledigt — automatisch passiert:'));
      }
      // CRM-Hinweis in FX-Liste, wenn Weiter dorthin führt
      if (action !== 'snooze' && crmDetailUrl(currentTask, 'notizen')) {
        var fxEl = document.getElementById('sh-m-fx');
        if (fxEl && fxEl.innerHTML.indexOf('CRM') < 0) {
          fxEl.innerHTML += '<div class="fx-item"><i class="bi bi-box-arrow-up-right"></i> ' +
            esc(_t('sh.fx_crm_notizen', 'Weiter → CRM Notizen (neues Fenster)')) + '</div>';
        }
      }
      updateWeiterButton(action);
      toast(action === 'snooze'
        ? _t('sh.toast_verschoben', 'Aufgabe verschoben')
        : _t('sh.toast_erledigt', isDemo ? 'Aufgabe erledigt (Demo)' : 'Aufgabe erledigt'));
    }

    if (isDemo) {
      finishLocal(isSnooze ? 'snooze' : 'erledigt');
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
        code: r.code || (isSnooze ? 'snooze' : 'erledigt'),
        ergebnis_id: r.id || '',
        daten: daten,
      }),
    })
      .then(function (res) { return res.json().then(function (j) { return { ok: res.ok, j: j }; }); })
      .then(function (pack) {
        if (!pack.ok) {
          toast((pack.j && (pack.j.error || pack.j.detail)) || _t('sh.toast_error', 'Speichern fehlgeschlagen'));
          return;
        }
        if (pack.j && pack.j.fx && pack.j.fx.length) {
          fx.innerHTML = pack.j.fx.map(function (x) {
            return '<div class="fx-item"><i class="bi bi-check2"></i> ' + esc(x) + '</div>';
          }).join('');
        }
        finishLocal((pack.j && pack.j.action) || (isSnooze ? 'snooze' : 'erledigt'));
      })
      .catch(function () {
        toast(_t('sh.toast_error', 'Speichern fehlgeschlagen'));
      });
  }

  function closeModal() {
    var ovl = document.getElementById('sh-ovl');
    if (ovl) ovl.style.display = 'none';
    currentTask = null;
  }

  function toast(msg, ms) {
    var el = document.getElementById('sh-toast');
    if (!el) return;
    el.innerHTML = '<i class="bi bi-check2-circle"></i> ' + esc(msg);
    el.classList.add('on');
    if (toast._timer) clearTimeout(toast._timer);
    var wait = (typeof ms === 'number' && ms > 0) ? ms : 3200;
    toast._timer = setTimeout(function () { el.classList.remove('on'); }, wait);
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
    getArtDefaults: getArtDefaults,
    dueDateTimeFromArt: dueDateTimeFromArt,
  };
})(window);
