// core-timezone.js — Benutzer-Zeitzone (Default: Europe/Berlin / MESZ)
(function () {
    const DEFAULT_TZ = 'Europe/Berlin';
    const STORAGE_KEY = 'crm_timezone';

    /** Gruppierte IANA-Zeitzonen — erweiterbar, Backend speichert freien String */
    const TZ_OPTIONS = [
        {
            group: 'Europa',
            options: [
                { id: 'Europe/Berlin', label: 'Deutschland (Berlin, MESZ/MEZ)' },
                { id: 'Europe/Vienna', label: 'Österreich (Wien)' },
                { id: 'Europe/Zurich', label: 'Schweiz (Zürich)' },
                { id: 'Europe/London', label: 'Großbritannien (London)' },
                { id: 'Europe/Paris', label: 'Frankreich (Paris)' },
                { id: 'Europe/Amsterdam', label: 'Niederlande (Amsterdam)' },
                { id: 'Europe/Rome', label: 'Italien (Rom)' },
                { id: 'Europe/Madrid', label: 'Spanien (Madrid)' },
                { id: 'Europe/Stockholm', label: 'Schweden (Stockholm)' },
                { id: 'Europe/Warsaw', label: 'Polen (Warschau)' },
                { id: 'Europe/Athens', label: 'Griechenland (Athen)' },
                { id: 'Europe/Istanbul', label: 'Türkei (Istanbul)' },
            ],
        },
        {
            group: 'USA & Kanada',
            options: [
                { id: 'America/New_York', label: 'USA — Ostküste (New York, ET)' },
                { id: 'America/Chicago', label: 'USA — Mitte (Chicago, CT)' },
                { id: 'America/Denver', label: 'USA — Rocky Mountains (Denver, MT)' },
                { id: 'America/Los_Angeles', label: 'USA — Westküste (Los Angeles, PT)' },
                { id: 'America/Phoenix', label: 'USA — Arizona (Phoenix, keine Sommerzeit)' },
                { id: 'America/Anchorage', label: 'USA — Alaska (Anchorage)' },
                { id: 'Pacific/Honolulu', label: 'USA — Hawaii (Honolulu)' },
                { id: 'America/Toronto', label: 'Kanada — Toronto (ET)' },
                { id: 'America/Vancouver', label: 'Kanada — Vancouver (PT)' },
            ],
        },
        {
            group: 'Australien & Neuseeland',
            options: [
                { id: 'Australia/Sydney', label: 'Australien — Sydney (AEST/AEDT)' },
                { id: 'Australia/Melbourne', label: 'Australien — Melbourne' },
                { id: 'Australia/Brisbane', label: 'Australien — Brisbane (keine Sommerzeit)' },
                { id: 'Australia/Perth', label: 'Australien — Perth' },
                { id: 'Australia/Adelaide', label: 'Australien — Adelaide' },
                { id: 'Australia/Darwin', label: 'Australien — Darwin' },
                { id: 'Pacific/Auckland', label: 'Neuseeland (Auckland)' },
            ],
        },
        {
            group: 'Asien & Naher Osten',
            options: [
                { id: 'Asia/Dubai', label: 'VAE (Dubai)' },
                { id: 'Asia/Kolkata', label: 'Indien (Kolkata)' },
                { id: 'Asia/Singapore', label: 'Singapur' },
                { id: 'Asia/Hong_Kong', label: 'Hongkong' },
                { id: 'Asia/Shanghai', label: 'China (Shanghai)' },
                { id: 'Asia/Tokyo', label: 'Japan (Tokio)' },
                { id: 'Asia/Seoul', label: 'Südkorea (Seoul)' },
                { id: 'Asia/Bangkok', label: 'Thailand (Bangkok)' },
                { id: 'Asia/Jerusalem', label: 'Israel (Jerusalem)' },
            ],
        },
        {
            group: 'Afrika & Südamerika',
            options: [
                { id: 'Africa/Cairo', label: 'Ägypten (Kairo)' },
                { id: 'Africa/Johannesburg', label: 'Südafrika (Johannesburg)' },
                { id: 'America/Sao_Paulo', label: 'Brasilien (São Paulo)' },
                { id: 'America/Buenos_Aires', label: 'Argentinien (Buenos Aires)' },
                { id: 'America/Mexico_City', label: 'Mexiko (Mexico City)' },
            ],
        },
        {
            group: 'Sonstiges',
            options: [
                { id: 'UTC', label: 'UTC (koordinierte Weltzeit)' },
            ],
        },
    ];

    function flatTzOptions() {
        return TZ_OPTIONS.flatMap(function (g) { return g.options; });
    }

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
            try {
                const parts = new Intl.DateTimeFormat('de-DE', {
                    timeZone: this.getTimezone(),
                    timeZoneName: 'short',
                }).formatToParts(new Date());
                return (parts.find(function (p) { return p.type === 'timeZoneName'; }) || {}).value
                    || this.getTimezone();
            } catch (e) {
                return this.getTimezone();
            }
        }

        static options() {
            return flatTzOptions();
        }

        static groupedOptions() {
            return TZ_OPTIONS.slice();
        }
    }

    window.timezoneManager = new TimezoneManager();
    window.TZ_OPTIONS = TZ_OPTIONS;
    window.flatTzOptions = flatTzOptions;

    document.addEventListener('DOMContentLoaded', function () {
        if (window.timezoneManager) timezoneManager.init();
    });
})();
