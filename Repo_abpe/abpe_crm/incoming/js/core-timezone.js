// core-timezone.js — IANA-Zeitzonen (Default: Europe/Berlin), i18n via timezone.json
(function () {
    const DEFAULT_TZ = 'Europe/Berlin';
    const STORAGE_KEY = 'crm_timezone';
    const I18N_BASE = '/static/abpe_crm/i18n/';

    let _base = null;
    let _i18n = null;
    let _lang = window.ABPE_CONFIG?.current_lang || 'de';
    let _loadPromise = null;

    function csrf() {
        return (document.cookie.match(/csrftoken=([^;]+)/) || [])[1] || '';
    }

    function apiBase() {
        return (window.ABPE_CONFIG && window.ABPE_CONFIG.crm_api_url) || '/crm/api/';
    }

    function currentLang() {
        return window.ABPE_CONFIG?.current_lang || _lang || 'de';
    }

    async function _fetchJson(url) {
        const res = await fetch(url + '?v=' + Date.now());
        if (!res.ok) throw new Error('HTTP ' + res.status);
        return res.json();
    }

    async function loadI18n(lang) {
        lang = lang || currentLang();
        _lang = lang;
        if (!_base) {
            _base = await _fetchJson(I18N_BASE + 'timezone.base.json');
        }
        try {
            _i18n = await _fetchJson(I18N_BASE + lang + '/timezone.json');
        } catch (e) {
            if (lang !== 'de') {
                _i18n = await _fetchJson(I18N_BASE + 'de/timezone.json');
            } else {
                throw e;
            }
        }
        return _i18n;
    }

    function ensureLoaded(lang) {
        if (!_loadPromise || lang) {
            _loadPromise = loadI18n(lang).catch(function (err) {
                console.warn('timezone i18n:', err);
                _loadPromise = null;
            });
        }
        return _loadPromise;
    }

    function groupIds() {
        if (!_base || !_base.groups) return [];
        return Object.keys(_base.groups);
    }

    function zonesForGroup(groupId) {
        if (!_base || !_base.groups) return [];
        return (_base.groups[groupId] || []).slice();
    }

    function findGroupForTimezone(tzId) {
        if (!tzId) return null;
        if (tzId === 'UTC') return 'UTC';
        if (!_base || !_base.groups) return tzId.split('/')[0] || null;
        for (const g of Object.keys(_base.groups)) {
            if ((_base.groups[g] || []).includes(tzId)) return g;
        }
        return tzId.includes('/') ? tzId.split('/')[0] : null;
    }

    function groupLabel(groupId) {
        if (_i18n && _i18n.groups && _i18n.groups[groupId]) return _i18n.groups[groupId];
        return groupId;
    }

    function zoneLabel(tzId) {
        if (_i18n && _i18n.zones && _i18n.zones[tzId]) return _i18n.zones[tzId];
        if (tzId === 'UTC') return 'UTC';
        return tzId.split('/').slice(1).join(' / ').replace(/_/g, ' ') || tzId;
    }

    function uiText(key) {
        if (_i18n && _i18n.ui && _i18n.ui[key]) return _i18n.ui[key];
        const fb = { title: 'Zeitzone', region: 'Region', zone: 'Zeitzone', hint: '', search: 'Suchen…', custom: 'Gespeichert' };
        return fb[key] || key;
    }

    function groupedOptions() {
        return groupIds().map(function (gid) {
            return {
                group: gid,
                groupLabel: groupLabel(gid),
                options: zonesForGroup(gid).map(function (id) {
                    return { id: id, label: zoneLabel(id) };
                }),
            };
        });
    }

    function flatOptions() {
        return groupedOptions().flatMap(function (g) { return g.options; });
    }

    function applyUiLabels() {
        const map = {
            'tz-ui-title': 'title',
            'tz-ui-region-label': 'region',
            'tz-ui-zone-label': 'zone',
            'tz-ui-hint': 'hint',
        };
        Object.keys(map).forEach(function (id) {
            const el = document.getElementById(id);
            if (el) el.textContent = uiText(map[id]);
        });
        const search = document.getElementById('settings-timezone-search');
        if (search) search.placeholder = uiText('search');
    }

    class TimezoneManager {
        constructor() {
            this.timezone = localStorage.getItem(STORAGE_KEY) || DEFAULT_TZ;
        }

        init() {
            const self = this;
            ensureLoaded().then(function () {
                self.loadFromServer();
            });
        }

        getTimezone() {
            return this.timezone || DEFAULT_TZ;
        }

        setTimezone(tz, opts) {
            opts = opts || {};
            if (!tz) tz = DEFAULT_TZ;
            this.timezone = tz;
            localStorage.setItem(STORAGE_KEY, tz);
            document.dispatchEvent(new CustomEvent('timezoneChanged', {
                detail: { timezone: tz },
            }));
            if (!opts.skipServer) this.persistToServer(tz);
        }

        persistToServer(tz) {
            fetch(apiBase() + 'user-settings/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrf(),
                    'X-Requested-With': 'XMLHttpRequest',
                },
                body: JSON.stringify({ timezone: tz }),
            }).catch(function () {});
        }

        loadFromServer() {
            const self = this;
            fetch(apiBase() + 'user-settings/', { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
                .then(function (r) { return r.json(); })
                .then(function (d) {
                    if (d.success && d.data && d.data.timezone) {
                        self.setTimezone(d.data.timezone, { skipServer: true });
                    }
                })
                .catch(function () {});
        }

        formatDateTime(iso, opts) {
            if (!iso) return '';
            opts = opts || {};
            const d = new Date(iso);
            if (Number.isNaN(d.getTime())) return '';
            return new Intl.DateTimeFormat(opts.locale || currentLang(), {
                timeZone: this.getTimezone(),
                year: 'numeric',
                month: opts.shortDate ? '2-digit' : 'numeric',
                day: opts.shortDate ? '2-digit' : 'numeric',
                hour: '2-digit',
                minute: '2-digit',
                ...(opts.withTz ? { timeZoneName: 'short' } : {}),
            }).format(d);
        }

        formatDate(iso) {
            if (!iso) return '';
            const d = new Date(iso);
            if (Number.isNaN(d.getTime())) return '';
            return new Intl.DateTimeFormat(currentLang(), {
                timeZone: this.getTimezone(),
                day: '2-digit',
                month: '2-digit',
                hour: '2-digit',
                minute: '2-digit',
            }).format(d);
        }

        toLocalInput(iso) {
            if (!iso) return '';
            const d = new Date(iso);
            if (Number.isNaN(d.getTime())) return '';
            const parts = new Intl.DateTimeFormat('en-CA', {
                timeZone: this.getTimezone(),
                year: 'numeric',
                month: '2-digit',
                day: '2-digit',
                hour: '2-digit',
                minute: '2-digit',
                hour12: false,
            }).formatToParts(d);
            const g = (t) => (parts.find((p) => p.type === t) || {}).value || '00';
            return `${g('year')}-${g('month')}-${g('day')}T${g('hour')}:${g('minute')}`;
        }

        fromLocalInput(localStr) {
            if (!localStr) return null;
            const [datePart, timePart = '00:00'] = localStr.split('T');
            const [y, m, d] = datePart.split('-').map(Number);
            const [hh, mm] = timePart.split(':').map(Number);
            const utcGuess = Date.UTC(y, m - 1, d, hh, mm, 0);
            const offset = this._offsetMsAt(utcGuess);
            return new Date(utcGuess - offset).toISOString();
        }

        _offsetMsAt(utcMs) {
            const tz = this.getTimezone();
            const d = new Date(utcMs);
            const inTz = new Date(d.toLocaleString('en-US', { timeZone: tz }));
            const inUtc = new Date(d.toLocaleString('en-US', { timeZone: 'UTC' }));
            return inTz.getTime() - inUtc.getTime();
        }

        tzLabel() {
            try {
                const parts = new Intl.DateTimeFormat(currentLang(), {
                    timeZone: this.getTimezone(),
                    timeZoneName: 'short',
                }).formatToParts(new Date());
                return (parts.find(function (p) { return p.type === 'timeZoneName'; }) || {}).value
                    || zoneLabel(this.getTimezone());
            } catch (e) {
                return zoneLabel(this.getTimezone());
            }
        }

        static options() {
            return flatOptions();
        }

        static groupedOptions() {
            return groupedOptions();
        }
    }

    window.timezoneManager = new TimezoneManager();
    window.tzLoadI18n = loadI18n;
    window.tzEnsureLoaded = ensureLoaded;
    window.tzFindGroup = findGroupForTimezone;
    window.tzOptionsForGroup = function (groupId, filter) {
        let list = zonesForGroup(groupId).map(function (id) {
            return { id: id, label: zoneLabel(id) };
        });
        if (filter) {
            const q = filter.toLowerCase();
            list = list.filter(function (o) {
                return o.id.toLowerCase().includes(q) || o.label.toLowerCase().includes(q);
            });
        }
        return list;
    };
    window.tzGroupLabel = groupLabel;
    window.tzZoneLabel = zoneLabel;
    window.tzUiText = uiText;
    window.tzApplyUiLabels = applyUiLabels;
    window.tzGroupIds = groupIds;

    document.addEventListener('DOMContentLoaded', function () {
        if (window.timezoneManager) timezoneManager.init();
    });

    document.addEventListener('languageChanged', function (e) {
        const lang = (e.detail && e.detail.lang) || currentLang();
        loadI18n(lang).then(function () {
            applyUiLabels();
            if (typeof window._populateTimezoneCascade === 'function' && window.timezoneManager) {
                window._populateTimezoneCascade(window.timezoneManager.getTimezone());
            }
            document.dispatchEvent(new CustomEvent('timezoneI18nLoaded', { detail: { lang: lang } }));
        });
    });
})();
