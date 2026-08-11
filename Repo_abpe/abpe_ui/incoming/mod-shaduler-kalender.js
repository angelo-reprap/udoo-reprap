/* mod-shaduler-kalender.js — Tag/Woche/Monat/Jahr (echte faellig_am-Daten) */
(function (global) {
  'use strict';

  var calView = 'monat';
  var cursor = null; // Date at month start focus
  var ARTEN = null;
  var ORDER = null;
  var onOpenTask = null;
  var onCreateEntry = null;

  function esc(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }

  function _t(key, fallback) {
    if (global.Shaduler && typeof global.Shaduler._t === 'function') {
      try {
        var v = global.Shaduler._t(key, fallback);
        if (v && v !== key) return v;
      } catch (e) { /* ignore */ }
    }
    return fallback || key;
  }

  function ymd(d) {
    if (!d) return '';
    return d.getFullYear() + '-' +
      String(d.getMonth() + 1).padStart(2, '0') + '-' +
      String(d.getDate()).padStart(2, '0');
  }

  function parseDay(t) {
    if (t && t.faellig_am) {
      var p = String(t.faellig_am).slice(0, 10).split('-');
      if (p.length === 3) return new Date(+p[0], +p[1] - 1, +p[2]);
    }
    if (t && t.day) {
      var now = new Date();
      return new Date(now.getFullYear(), now.getMonth(), +t.day);
    }
    return null;
  }

  function sameDay(a, b) {
    return a && b && a.getFullYear() === b.getFullYear()
      && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();
  }

  function startOfWeek(d) {
    var x = new Date(d.getFullYear(), d.getMonth(), d.getDate());
    var day = (x.getDay() + 6) % 7; // Mo=0
    x.setDate(x.getDate() - day);
    return x;
  }

  function render(root, tasks, opts) {
    if (!root) return;
    opts = opts || {};
    ARTEN = opts.arten || {};
    ORDER = opts.order || Object.keys(ARTEN);
    onOpenTask = opts.onOpenTask || function () {};
    onCreateEntry = opts.onCreateEntry || null;
    if (opts.view) calView = opts.view;
    var today = new Date();
    today.setHours(0, 0, 0, 0);
    if (!cursor) {
      cursor = new Date(today.getFullYear(), today.getMonth(), today.getDate());
    }
    if (opts.selDate) cursor = new Date(opts.selDate);

    root.innerHTML =
      '<div class="sh-card">' +
      '<div class="card-h"><i class="bi bi-calendar3"></i> ' + esc(_t('sh.cal_title', 'Kalender')) +
      '<div class="viewsw" id="sh-vsw">' +
      '<button type="button" data-v="tag">' + esc(_t('sh.cal_view_day', 'Tag')) + '</button>' +
      '<button type="button" data-v="woche">' + esc(_t('sh.cal_view_week', 'Woche')) + '</button>' +
      '<button type="button" data-v="monat" class="on">' + esc(_t('sh.cal_view_month', 'Monat')) + '</button>' +
      '<button type="button" data-v="jahr">' + esc(_t('sh.cal_view_year', 'Jahr')) + '</button>' +
      '</div>' +
      '<button type="button" class="sh-neue-btn sh-cal-new" id="sh-cal-new" title="' +
      esc(_t('sh.cal_new', 'Neuer Kalender-Eintrag')) + '">' +
      '<i class="bi bi-plus-lg"></i> ' + esc(_t('sh.cal_new_btn', 'Neuer Eintrag')) + '</button>' +
      '</div>' +
      '<div class="cal-nav">' +
      '<button type="button" id="sh-cal-prev"><i class="bi bi-chevron-left"></i></button>' +
      '<b id="sh-cal-title"></b>' +
      '<button type="button" id="sh-cal-next"><i class="bi bi-chevron-right"></i></button>' +
      '<button type="button" id="sh-cal-today" style="padding:0 10px;font-size:.78rem">' +
      esc(_t('sh.cal_today', 'Heute')) + '</button>' +
      '</div><div id="sh-cal-body"></div></div>';

    root.querySelectorAll('#sh-vsw button').forEach(function (b) {
      b.addEventListener('click', function () {
        calView = b.getAttribute('data-v');
        paint(tasks);
      });
    });
    var newBtn = root.querySelector('#sh-cal-new');
    if (newBtn && onCreateEntry) {
      newBtn.addEventListener('click', function (e) {
        e.preventDefault();
        e.stopPropagation();
        var d = cursor ? new Date(cursor) : new Date();
        var now = new Date();
        onCreateEntry({
          date: ymd(d),
          time: String(now.getHours()).padStart(2, '0') + ':' +
            String(Math.floor(now.getMinutes() / 5) * 5).padStart(2, '0'),
        });
      });
    } else if (newBtn) {
      newBtn.style.display = 'none';
    }    root.querySelector('#sh-cal-prev').onclick = function () {
      if (calView === 'tag') cursor.setDate(cursor.getDate() - 1);
      else if (calView === 'woche') cursor.setDate(cursor.getDate() - 7);
      else if (calView === 'monat') cursor.setMonth(cursor.getMonth() - 1);
      else cursor.setFullYear(cursor.getFullYear() - 1);
      paint(tasks);
    };
    root.querySelector('#sh-cal-next').onclick = function () {
      if (calView === 'tag') cursor.setDate(cursor.getDate() + 1);
      else if (calView === 'woche') cursor.setDate(cursor.getDate() + 7);
      else if (calView === 'monat') cursor.setMonth(cursor.getMonth() + 1);
      else cursor.setFullYear(cursor.getFullYear() + 1);
      paint(tasks);
    };
    root.querySelector('#sh-cal-today').onclick = function () {
      cursor = new Date();
      cursor.setHours(0, 0, 0, 0);
      calView = 'tag';
      paint(tasks);
    };
    paint(tasks);
  }

  function paint(tasks) {
    tasks = tasks || [];
    var body = document.getElementById('sh-cal-body');
    var title = document.getElementById('sh-cal-title');
    if (!body || !title) return;
    document.querySelectorAll('#sh-vsw button').forEach(function (b) {
      b.classList.toggle('on', b.getAttribute('data-v') === calView);
    });
    body.innerHTML = '';
    var today = new Date();
    today.setHours(0, 0, 0, 0);
    var months = [
      _t('sh.month_01', 'Januar'), _t('sh.month_02', 'Februar'), _t('sh.month_03', 'März'),
      _t('sh.month_04', 'April'), _t('sh.month_05', 'Mai'), _t('sh.month_06', 'Juni'),
      _t('sh.month_07', 'Juli'), _t('sh.month_08', 'August'), _t('sh.month_09', 'September'),
      _t('sh.month_10', 'Oktober'), _t('sh.month_11', 'November'), _t('sh.month_12', 'Dezember'),
    ];
    var monthsShort = [
      _t('sh.month_short_01', 'Jan'), _t('sh.month_short_02', 'Feb'), _t('sh.month_short_03', 'Mär'),
      _t('sh.month_short_04', 'Apr'), _t('sh.month_short_05', 'Mai'), _t('sh.month_short_06', 'Jun'),
      _t('sh.month_short_07', 'Jul'), _t('sh.month_short_08', 'Aug'), _t('sh.month_short_09', 'Sep'),
      _t('sh.month_short_10', 'Okt'), _t('sh.month_short_11', 'Nov'), _t('sh.month_short_12', 'Dez'),
    ];
    var dows = [
      _t('sh.dow_mo', 'Mo'), _t('sh.dow_di', 'Di'), _t('sh.dow_mi', 'Mi'),
      _t('sh.dow_do', 'Do'), _t('sh.dow_fr', 'Fr'), _t('sh.dow_sa', 'Sa'), _t('sh.dow_so', 'So'),
    ];

    function tasksOn(d) {
      return tasks.filter(function (t) {
        var td = parseDay(t);
        return td && sameDay(td, d);
      });
    }

    if (calView === 'monat') {
      title.textContent = months[cursor.getMonth()] + ' ' + cursor.getFullYear();
      var g = document.createElement('div');
      g.className = 'grid';
      dows.forEach(function (d) {
        g.innerHTML += '<div class="dow">' + d + '</div>';
      });
      var first = new Date(cursor.getFullYear(), cursor.getMonth(), 1);
      var start = startOfWeek(first);
      for (var i = 0; i < 42; i++) {
        (function (offset) {
          var day = new Date(start.getFullYear(), start.getMonth(), start.getDate() + offset);
          var inMonth = day.getMonth() === cursor.getMonth();
          var list = tasksOn(day);
          var byArt = {};
          list.forEach(function (t) { byArt[t.art] = (byArt[t.art] || 0) + 1; });
          var badges = '';
          ORDER.forEach(function (a) {
            if (byArt[a] && ARTEN[a]) {
              badges +=
                '<span class="bdg" style="background:var(' + ARTEN[a].cv + ')">' +
                '<i class="bi ' + ARTEN[a].icon + '"></i>' + byArt[a] + '</span>';
            }
          });
          var hasOv = list.some(function (t) { return t.ueberfaellig; });
          var e = document.createElement('div');
          e.className = 'day' + (inMonth ? '' : ' other') + (sameDay(day, today) ? ' today' : '');
          e.innerHTML =
            '<span class="num">' + day.getDate() + '</span>' +
            (hasOv ? '<span class="dot-ov"></span>' : '') +
            '<div class="badges">' + badges + '</div>';
          e.onclick = function () {
            cursor = new Date(day);
            calView = 'tag';
            paint(tasks);
          };
          g.appendChild(e);
        })(i);
      }
      body.appendChild(g);
    } else if (calView === 'woche') {
      var ws = startOfWeek(cursor);
      var we = new Date(ws.getFullYear(), ws.getMonth(), ws.getDate() + 6);
      title.textContent =
        String(ws.getDate()).padStart(2, '0') + '.' + String(ws.getMonth() + 1).padStart(2, '0') +
        '. – ' +
        String(we.getDate()).padStart(2, '0') + '.' + String(we.getMonth() + 1).padStart(2, '0') +
        '.' + we.getFullYear();
      var w = document.createElement('div');
      w.className = 'week';
      for (var di = 0; di < 7; di++) {
        (function (offset) {
          var day = new Date(ws.getFullYear(), ws.getMonth(), ws.getDate() + offset);
          var list = tasksOn(day);
          var e = document.createElement('div');
          e.className = 'wday' + (sameDay(day, today) ? ' today' : '');
          e.innerHTML =
            '<h4>' + dows[offset] + ' ' + day.getDate() + '</h4>' +
            list.map(function (t) {
              var a = ARTEN[t.art] || {};
              return (
                '<div class="wev" style="--evc:var(' + (a.cv || '--a-allg') + ')" data-id="' + esc(t.id) + '">' +
                (t.zeit ? esc(t.zeit) + ' ' : '') + esc(t.titel) + '</div>'
              );
            }).join('');
          e.querySelectorAll('.wev').forEach(function (el) {
            el.addEventListener('click', function (ev) {
              ev.stopPropagation();
              var t = tasks.find(function (x) { return String(x.id) === el.getAttribute('data-id'); });
              if (t) onOpenTask(t);
            });
          });
          e.onclick = function () { cursor = new Date(day); calView = 'tag'; paint(tasks); };
          w.appendChild(e);
        })(di);
      }
      body.appendChild(w);
    } else if (calView === 'tag') {
      var isToday = sameDay(cursor, today);
      title.textContent =
        (isToday ? _t('sh.cal_today_prefix', 'Heute · ') : '') +
        String(cursor.getDate()).padStart(2, '0') + '.' +
        String(cursor.getMonth() + 1).padStart(2, '0') + '.' +
        cursor.getFullYear();
      var list = tasksOn(cursor);
      var noTime = list.filter(function (t) { return !t.zeit; });
      if (noTime.length) {
        var r0 = document.createElement('div');
        r0.className = 'hourrow';
        r0.innerHTML =
          '<div class="hh">' + esc(_t('sh.cal_no_time', 'ohne Zeit')).replace(/ /g, '<br>') +
          '</div><div class="hc">' +
          noTime.map(function (t) {
            var a = ARTEN[t.art] || {};
            return (
              '<div class="dayev" style="--evc:var(' + (a.cv || '--a-allg') + ')" data-id="' + esc(t.id) + '">' +
              '<b>' + esc(t.titel) + '</b> <small>· ' + esc(t.ref_label || '') + '</small></div>'
            );
          }).join('') + '</div>';
        body.appendChild(r0);
      }
      for (var h = 8; h <= 18; h++) {
        var evs = list.filter(function (t) {
          return t.zeit && parseInt(t.zeit, 10) === h;
        });
        var r = document.createElement('div');
        r.className = 'hourrow';
        r.innerHTML =
          '<div class="hh">' + String(h).padStart(2, '0') + ':00</div><div class="hc">' +
          evs.map(function (t) {
            var a = ARTEN[t.art] || {};
            return (
              '<div class="dayev" style="--evc:var(' + (a.cv || '--a-allg') + ')" data-id="' + esc(t.id) + '">' +
              '<b>' + esc(t.zeit) + ' ' + esc(t.titel) + '</b></div>'
            );
          }).join('') + '</div>';
        body.appendChild(r);
      }
      if (!list.length) {
        body.innerHTML += '<div class="none" style="padding:12px">' +
          esc(_t('sh.cal_no_tasks', 'Keine Aufgaben an diesem Tag')) + '</div>';
      }
      body.querySelectorAll('.dayev').forEach(function (el) {
        el.addEventListener('click', function () {
          var t = tasks.find(function (x) { return String(x.id) === el.getAttribute('data-id'); });
          if (t) onOpenTask(t);
        });
      });
    } else {
      title.textContent = String(cursor.getFullYear());
      var y = document.createElement('div');
      y.style.cssText = 'display:grid;grid-template-columns:repeat(4,1fr);gap:12px;padding:14px';
      for (var mi = 0; mi < 12; mi++) {
        (function (mIdx) {
          var count = tasks.filter(function (t) {
            var td = parseDay(t);
            return td && td.getFullYear() === cursor.getFullYear() && td.getMonth() === mIdx;
          }).length;
          var card = document.createElement('div');
          card.className = 'stat-card';
          card.style.cursor = 'pointer';
          card.innerHTML =
            '<b>' + monthsShort[mIdx] + '</b><div class="stat-value" style="font-size:1.3rem">' +
            (count || '–') + '</div>';
          card.onclick = function () {
            cursor = new Date(cursor.getFullYear(), mIdx, 1);
            calView = 'monat';
            paint(tasks);
          };
          y.appendChild(card);
        })(mi);
      }
      body.appendChild(y);
    }
  }

  global.ShadulerCal = { render: render, paint: paint };
})(window);
