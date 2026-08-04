/* mod-shaduler-kalender.js — Tag/Woche/Monat/Jahr */
(function (global) {
  'use strict';

  var TODAY = 3; // Demo: 03.08.2026
  var calView = 'monat';
  var selDay = TODAY;
  var ARTEN = null;
  var ORDER = null;
  var onOpenTask = null;

  function esc(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }

  function render(root, tasks, opts) {
    if (!root) return;
    opts = opts || {};
    ARTEN = opts.arten || {};
    ORDER = opts.order || Object.keys(ARTEN);
    onOpenTask = opts.onOpenTask || function () {};
    if (opts.view) calView = opts.view;
    if (opts.today != null) TODAY = opts.today;
    if (opts.selDay != null) selDay = opts.selDay;

    root.innerHTML =
      '<div class="sh-card">' +
      '<div class="card-h"><i class="bi bi-calendar3"></i> Kalender' +
      '<div class="viewsw" id="sh-vsw">' +
      '<button type="button" data-v="tag">Tag</button>' +
      '<button type="button" data-v="woche">Woche</button>' +
      '<button type="button" data-v="monat" class="on">Monat</button>' +
      '<button type="button" data-v="jahr">Jahr</button>' +
      '</div></div>' +
      '<div class="cal-nav">' +
      '<button type="button" id="sh-cal-prev"><i class="bi bi-chevron-left"></i></button>' +
      '<b id="sh-cal-title"></b>' +
      '<button type="button" id="sh-cal-next"><i class="bi bi-chevron-right"></i></button>' +
      '<button type="button" id="sh-cal-today" style="padding:0 10px;font-size:.78rem">Heute</button>' +
      '</div><div id="sh-cal-body"></div></div>';

    root.querySelectorAll('#sh-vsw button').forEach(function (b) {
      b.addEventListener('click', function () {
        calView = b.getAttribute('data-v');
        paint(tasks);
      });
    });
    root.querySelector('#sh-cal-prev').onclick = function () {
      if (calView === 'tag') selDay = Math.max(1, selDay - 1);
      paint(tasks);
    };
    root.querySelector('#sh-cal-next').onclick = function () {
      if (calView === 'tag') selDay = Math.min(31, selDay + 1);
      paint(tasks);
    };
    root.querySelector('#sh-cal-today').onclick = function () {
      selDay = TODAY;
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

    if (calView === 'monat') {
      title.textContent = 'August 2026';
      var g = document.createElement('div');
      g.className = 'grid';
      ['Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa', 'So'].forEach(function (d) {
        g.innerHTML += '<div class="dow">' + d + '</div>';
      });
      for (var i = 27; i <= 31; i++) {
        g.innerHTML += '<div class="day other"><span class="num">' + i + '</span></div>';
      }
      for (var d = 1; d <= 31; d++) {
        (function (day) {
          var byArt = {};
          tasks.filter(function (t) { return t.day === day; }).forEach(function (t) {
            byArt[t.art] = (byArt[t.art] || 0) + 1;
          });
          var badges = '';
          ORDER.forEach(function (a) {
            if (byArt[a] && ARTEN[a]) {
              badges +=
                '<span class="bdg" style="background:var(' + ARTEN[a].cv + ')">' +
                '<i class="bi ' + ARTEN[a].icon + '"></i>' + byArt[a] + '</span>';
            }
          });
          var hasOv = tasks.some(function (t) { return t.ueberfaellig && t.day === day; });
          var e = document.createElement('div');
          e.className = 'day' + (day === TODAY ? ' today' : '');
          e.innerHTML =
            '<span class="num">' + day + '</span>' +
            (hasOv ? '<span class="dot-ov"></span>' : '') +
            '<div class="badges">' + badges + '</div>';
          e.onclick = function () { selDay = day; calView = 'tag'; paint(tasks); };
          g.appendChild(e);
        })(d);
      }
      body.appendChild(g);
    } else if (calView === 'woche') {
      title.textContent = 'KW 32 · 03.–09.08.2026';
      var w = document.createElement('div');
      w.className = 'week';
      ['Mo 3', 'Di 4', 'Mi 5', 'Do 6', 'Fr 7', 'Sa 8', 'So 9'].forEach(function (lbl, i) {
        var day = 3 + i;
        var list = tasks.filter(function (t) { return t.day === day; });
        var e = document.createElement('div');
        e.className = 'wday';
        e.innerHTML =
          '<h4>' + lbl + '</h4>' +
          list.map(function (t) {
            var a = ARTEN[t.art] || {};
            return (
              '<div class="wev" style="--evc:var(' + (a.cv || '--a-allg') + ')">' +
              (t.zeit ? esc(t.zeit) + ' ' : '') + esc(t.titel) + '</div>'
            );
          }).join('');
        e.onclick = function () { selDay = day; calView = 'tag'; paint(tasks); };
        w.appendChild(e);
      });
      body.appendChild(w);
    } else if (calView === 'tag') {
      title.textContent = (selDay === TODAY ? 'Heute · ' : '') + String(selDay).padStart(2, '0') + '.08.2026';
      var list = tasks.filter(function (t) { return t.day === selDay; });
      var noTime = list.filter(function (t) { return !t.zeit; });
      if (noTime.length) {
        var r0 = document.createElement('div');
        r0.className = 'hourrow';
        r0.innerHTML =
          '<div class="hh">ohne<br>Zeit</div><div class="hc">' +
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
      body.querySelectorAll('.dayev').forEach(function (el) {
        el.addEventListener('click', function () {
          var t = tasks.find(function (x) { return String(x.id) === el.getAttribute('data-id'); });
          if (t) onOpenTask(t);
        });
      });
    } else {
      title.textContent = '2026';
      var y = document.createElement('div');
      y.style.cssText = 'display:grid;grid-template-columns:repeat(4,1fr);gap:12px;padding:14px';
      ['Jan', 'Feb', 'Mär', 'Apr', 'Mai', 'Jun', 'Jul', 'Aug', 'Sep', 'Okt', 'Nov', 'Dez'].forEach(function (m, i) {
        var card = document.createElement('div');
        card.className = 'stat-card';
        card.style.cursor = 'pointer';
        card.innerHTML =
          '<b>' + m + '</b><div class="stat-value" style="font-size:1.3rem">' +
          (i === 7 ? tasks.length : '–') + '</div>';
        if (i === 7) {
          card.onclick = function () { calView = 'monat'; paint(tasks); };
        }
        y.appendChild(card);
      });
      body.appendChild(y);
    }
  }

  global.ShadulerCal = { render: render, paint: paint };
})(window);
