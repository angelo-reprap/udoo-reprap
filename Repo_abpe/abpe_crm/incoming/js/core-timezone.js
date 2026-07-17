// core-timezone.js — Benutzer-Zeitzone (Default: Europe/Berlin / MESZ)
(function () {
    const DEFAULT_TZ = 'Europe/Berlin';
    const STORAGE_KEY = 'crm_timezone';

    const TZ_OPTIONS = [
        { id: 'Europe/Berlin', label: 'Mitteleuropa (Berlin, MESZ/MEZ)' },
        { id: 'Europe/Vienna', label: 'Österreich (Wien)' },
        { id: 'Europe/Zurich', label: 'Schweiz (Zürich)' },
        { id: 'UTC', label: 'UTC' },
    ];

    function csrf() {
        return (document.cookie.match(/csrftoken=([^;]+)/) || [])[1] || '';
    }

    function apiBase() {
        return (window.ABPE_CONFIG && window.ABPE_CONFIG.crm_api_url) || '/crm/api/';
    }

    class TimezoneManager {
        constructor() {
            this.timezone = localStorage.getItem(STORAGE_KEY) || DEFAULT_TZ;
        }

        init() {
            this.loadFromServer();
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
            return new Intl.DateTimeFormat(opts.locale || 'de-DE', {
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
            return new Intl.DateTimeFormat('de-DE', {
                timeZone: this.getTimezone(),
                day: '2-digit',
                month: '2-digit',
                hour: '2-digit',
                minute: '2-digit',
            }).format(d);
        }

        /** datetime-local value in Benutzer-Zeitzone */
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

        /** datetime-local → ISO UTC (Wandzeit in Benutzer-Zeitzone) */
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
            const map = {
                'Europe/Berlin': 'MESZ/MEZ',
                'Europe/Vienna': 'Mitteleuropa',
                'Europe/Zurich': 'Mitteleuropa',
                UTC: 'UTC',
            };
            return map[this.getTimezone()] || this.getTimezone();
        }

        static options() {
            return TZ_OPTIONS.slice();
        }
    }

    window.timezoneManager = new TimezoneManager();
    window.TZ_OPTIONS = TZ_OPTIONS;

    document.addEventListener('DOMContentLoaded', function () {
        if (window.timezoneManager) timezoneManager.init();
    });
})();
