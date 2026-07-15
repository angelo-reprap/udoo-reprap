/* ============================================================
   ABpE CRM — mod-crm-reporting.js
   Reporting & Sync Dashboard
   ============================================================ */

const CRM_Reporting = {
    _data: null,
    _loading: false,

    t(key, fallback) {
        const v = (window.i18nData && window.i18nData[key]) || fallback;
        return v == null ? key : v;
    },

    esc(s) {
        return String(s == null ? '' : s).replace(/[&<>"']/g, c => ({
            '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
        }[c]));
    },

    init() {
        this._ensureStyles();
        this.load();
    },

    _ensureStyles() {
        if (document.getElementById('crm-reporting-styles')) return;
        const s = document.createElement('style');
        s.id = 'crm-reporting-styles';
        s.textContent = [
            '.crm-rpt-kpis{margin:12px 12px 0}',
            '.crm-rpt-meta{display:flex;flex-wrap:wrap;gap:12px 24px;align-items:center;padding:12px 16px}',
            '.crm-rpt-badge{display:inline-flex;align-items:center;gap:5px;font-size:11px;font-weight:600;padding:4px 10px;border-radius:999px}',
            '.crm-rpt-badge.ok{background:var(--status-green-bg,#d1e7dd);color:#0f5132}',
            '.crm-rpt-badge.warn{background:#fff3cd;color:#664d03}',
            '.crm-rpt-badge.neutral{background:var(--abcona-gray-bg,#f8f9fa);color:var(--text-secondary,#666)}',
            '.crm-rpt-badge.err{background:#f8d7da;color:#842029}',
            '.crm-rpt-table{width:100%;border-collapse:collapse;font-size:13px}',
            '.crm-rpt-table td{padding:8px 16px;border-bottom:1px solid var(--border-color,#eee)}',
            '.crm-rpt-table td:first-child{color:var(--text-secondary,#666);width:55%}',
            '.crm-rpt-table td:last-child{text-align:right;font-weight:600;color:var(--text-primary,#222)}',
            '.crm-rpt-warn{display:flex;justify-content:space-between;align-items:center;padding:10px 16px;border-bottom:1px solid var(--border-color,#eee);font-size:13px}',
            '.crm-rpt-warn:last-child{border-bottom:none}',
            '.crm-rpt-warn-val{font-weight:700;min-width:48px;text-align:right}',
            '.crm-rpt-warn.ok .crm-rpt-warn-val{color:var(--status-green,#28a745)}',
            '.crm-rpt-warn.mid .crm-rpt-warn-val{color:#b58105}',
            '.crm-rpt-warn.bad .crm-rpt-warn-val{color:var(--status-red,#dc3545)}',
            '.crm-rpt-actions{display:flex;gap:8px;margin-left:auto}',
            '.crm-rpt-foot{padding:8px 16px 14px;font-size:11px;color:var(--text-muted,#999)}',
            '.crm-rpt-empty{padding:16px;color:var(--text-muted,#999);font-size:13px}',
            '.crm-full-panel .section-content{display:none}',
            '.crm-full-panel .section-header.open+.section-content{display:block}',
        ].join('');
        document.head.appendChild(s);
    },

    _headers(json) {
        const h = { 'X-Requested-With': 'XMLHttpRequest' };
        if (json) h['Content-Type'] = 'application/json';
        const csrf = this._csrf();
        if (csrf) h['X-CSRFToken'] = csrf;
        return h;
    },

    _csrf() {
        return document.cookie.split(';').find(c => c.trim().startsWith('csrftoken='))?.split('=')[1] || '';
    },

    async load() {
        const root = document.getElementById('crm-reporting-root');
        if (!root || this._loading) return;
        this._loading = true;
        root.innerHTML = `<div class="crm-list-loading"><i class="bi bi-arrow-repeat matching-spinner"></i> ${this.esc(this.t('rep_loading', 'Lade Reporting…'))}</div>`;

        try {
            let data = null;
            try {
                const r = await fetch('/crm/api/reporting/dashboard/', { headers: this._headers() });
                if (r.ok) {
                    data = await r.json();
                } else if (r.status >= 500) {
                    console.warn('reporting dashboard HTTP', r.status);
                }
            } catch (e) {
                console.warn('reporting dashboard fetch failed', e);
            }

            if (!data) {
                const r2 = await fetch('/crm/api/sync/status/', { headers: this._headers() });
                if (!r2.ok) throw new Error('sync status failed');
                const legacy = await r2.json();
                data = this._legacyPayload(legacy);
            }

            this._data = data;
            this.render();
        } catch (e) {
            root.innerHTML = `<div class="crm-list-loading"><i class="bi bi-exclamation-triangle"></i> ${this.esc(this.t('rep_load_err', 'Reporting konnte nicht geladen werden'))}</div>`;
        } finally {
            this._loading = false;
        }
    },

    _legacyPayload(legacy) {
        return {
            generated_at: '',
            sync: { status: legacy.last_sync ? 'ok' : 'unknown', last_sync: legacy.last_sync || '' },
            totals: {
                contacts: legacy.contacts_total || 0,
                accounts: legacy.accounts_total || 0,
                emails: legacy.emails_total || 0,
                documents: legacy.documents_total || 0,
                notes: legacy.notes_total || 0,
            },
            growth_30d: {},
            quality: {},
            meetme: {},
            _legacy: true,
        };
    },

    _num(n) {
        if (n == null || n === '') return '—';
        return Number(n).toLocaleString();
    },

    _fmtDate(iso) {
        if (!iso) return this.t('rep_never', 'Noch nie');
        try {
            const d = new Date(iso);
            if (Number.isNaN(d.getTime())) return iso;
            return d.toLocaleString(undefined, {
                day: '2-digit', month: '2-digit', year: 'numeric',
                hour: '2-digit', minute: '2-digit',
            });
        } catch (e) {
            return iso;
        }
    },

    _syncBadge(status) {
        const map = {
            ok: ['ok', this.t('rep_sync_ok', 'OK')],
            unknown: ['warn', this.t('rep_sync_unknown', 'Unbekannt')],
            empty: ['neutral', this.t('rep_sync_empty', 'Leer')],
        };
        const [cls, label] = map[status] || map.unknown;
        return `<span class="crm-rpt-badge ${cls}"><i class="bi bi-circle-fill" style="font-size:7px"></i> ${this.esc(label)}</span>`;
    },

    _panel(title, icon, bodyHtml, actionsHtml) {
        return `
        <div class="crm-full-panel">
            <div class="section-header">
                <span><i class="bi ${icon}"></i> ${this.esc(title)}</span>
                ${actionsHtml || ''}
                <i class="bi bi-chevron-down crm-rpt-chevron"></i>
            </div>
            <div class="section-content">${bodyHtml}</div>
        </div>`;
    },

    _bindPanels(root) {
        if (!root) return;
        root.querySelectorAll('.crm-full-panel').forEach(panel => {
            const hdr = panel.querySelector('.section-header');
            const body = panel.querySelector('.section-content');
            if (!hdr || !body || hdr.dataset.rptBound === '1') return;
            hdr.dataset.rptBound = '1';
            hdr.style.cursor = 'pointer';
            const chev = hdr.querySelector('.crm-rpt-chevron');
            const setOpen = (open) => {
                hdr.classList.toggle('open', open);
                body.classList.toggle('open', open);
                if (chev) chev.className = 'bi crm-rpt-chevron ' + (open ? 'bi-chevron-up' : 'bi-chevron-down');
            };
            setOpen(false);
            hdr.addEventListener('click', (e) => {
                if (e.target.closest('button, a, input, select, textarea')) return;
                setOpen(!hdr.classList.contains('open'));
            });
        });
    },

    _tableRows(rows) {
        if (!rows.length) return `<div class="crm-rpt-empty">${this.esc(this.t('rep_no_data', 'Keine Daten'))}</div>`;
        return `<table class="crm-rpt-table"><tbody>${rows.map(([l, v]) =>
            `<tr><td>${this.esc(l)}</td><td>${this.esc(String(v))}</td></tr>`
        ).join('')}</tbody></table>`;
    },

    _qualityRow(label, val, level) {
        const disp = val == null ? '—' : this._num(val);
        return `<div class="crm-rpt-warn ${level || 'ok'}"><span>${this.esc(label)}</span><span class="crm-rpt-warn-val">${disp}</span></div>`;
    },

    _qualityLevel(val, warnAt, badAt) {
        if (val == null) return 'ok';
        if (val >= badAt) return 'bad';
        if (val >= warnAt) return 'mid';
        return 'ok';
    },

    render() {
        const root = document.getElementById('crm-reporting-root');
        if (!root || !this._data) return;
        const d = this._data;
        const t = d.totals || {};
        const q = d.quality || {};
        const g = d.growth_30d || {};
        const m = d.meetme || {};
        const sync = d.sync || {};

        const kpis = `
        <div class="crm-stats-bar crm-rpt-kpis">
            <div class="crm-stat"><span class="crm-stat-val">${this._num(t.contacts)}</span><span class="crm-stat-lbl">${this.esc(this.t('rep_kpi_contacts', 'Kontakte'))}</span></div>
            <div class="crm-stat"><span class="crm-stat-val">${this._num(t.accounts)}</span><span class="crm-stat-lbl">${this.esc(this.t('rep_kpi_accounts', 'Accounts'))}</span></div>
            <div class="crm-stat"><span class="crm-stat-val">${this._num(t.emails)}</span><span class="crm-stat-lbl">${this.esc(this.t('rep_kpi_emails', 'E-Mails'))}</span></div>
            <div class="crm-stat"><span class="crm-stat-val">${this._num(t.documents)}</span><span class="crm-stat-lbl">${this.esc(this.t('rep_kpi_documents', 'Dokumente'))}</span></div>
            <div class="crm-stat"><span class="crm-stat-val">${this._num(t.notes)}</span><span class="crm-stat-lbl">${this.esc(this.t('rep_kpi_notes', 'Notizen'))}</span></div>
        </div>`;

        const syncActions = `
            <div class="crm-rpt-actions">
                <button class="crm-new-btn" type="button" onclick="CRM_Reporting.refresh()" title="${this.esc(this.t('rep_refresh', 'Aktualisieren'))}">
                    <i class="bi bi-arrow-clockwise"></i>
                </button>
                <button class="crm-new-btn" type="button" onclick="CRM_Reporting.startSync()">
                    <i class="bi bi-arrow-repeat"></i> <span>${this.esc(this.t('sync_starten', 'Sync starten'))}</span>
                </button>
            </div>`;

        const syncPanel = this._panel(
            this.t('reporting_sync', 'Reporting & Sync'),
            'bi-bar-chart',
            `<div class="crm-rpt-meta">
                <div><span class="crm-section-label">${this.esc(this.t('rep_last_sync', 'Letzter Sync'))}</span>
                <div style="font-size:14px;color:var(--abcona-blue,#1a5fb4);margin-top:2px">${this.esc(this._fmtDate(sync.last_sync))}</div></div>
                <div>${this._syncBadge(sync.status)}</div>
            </div>
            ${d._legacy ? `<div class="crm-rpt-foot"><i class="bi bi-info-circle"></i> ${this.esc(this.t('rep_legacy_api', 'Erweiterte API noch nicht installiert — Basis-Zähler aus /crm/api/sync/status/'))}</div>` : ''}`,
            syncActions,
        );

        const overviewPanel = this._panel(
            this.t('rep_section_overview', 'Datenübersicht'),
            'bi-table',
            this._tableRows([
                [this.t('rep_kpi_contacts', 'Kontakte gesamt'), this._num(t.contacts)],
                [this.t('rep_kpi_accounts', 'Accounts gesamt'), this._num(t.accounts)],
                [this.t('rep_kpi_emails', 'E-Mail-Adressen'), this._num(t.emails)],
                [this.t('rep_kpi_documents', 'Dokumente (EDMS)'), this._num(t.documents)],
                [this.t('rep_kpi_notes', 'Kontaktnotizen'), this._num(t.notes)],
            ]),
        );

        const qualityItems = [
            this._qualityRow(
                this.t('rep_q_no_email', 'Kontakte ohne E-Mail'),
                q.contacts_without_email,
                this._qualityLevel(q.contacts_without_email, 10, 100),
            ),
            this._qualityRow(
                this.t('rep_q_opt_out', 'E-Mails Opt-out'),
                q.emails_opt_out,
                this._qualityLevel(q.emails_opt_out, 1, 50),
            ),
            this._qualityRow(
                this.t('rep_q_invalid', 'Ungültige E-Mail-Adressen'),
                q.emails_invalid,
                this._qualityLevel(q.emails_invalid, 1, 20),
            ),
            this._qualityRow(this.t('rep_q_active_emails', 'Aktive E-Mail-Adressen'), q.emails_active, 'ok'),
            this._qualityRow(this.t('rep_q_linked', 'Primäre Kontakt-E-Mails'), q.emails_linked_contacts, 'ok'),
        ].join('');

        const qualityPanel = Object.keys(q).length
            ? this._panel(this.t('rep_section_quality', 'Datenqualität'), 'bi-shield-check', qualityItems)
            : '';

        const growthRows = [];
        if (g.contacts != null) growthRows.push([this.t('rep_growth_contacts', 'Neue Kontakte (30 Tage)'), this._num(g.contacts)]);
        if (g.accounts != null) growthRows.push([this.t('rep_growth_accounts', 'Neue Accounts (30 Tage)'), this._num(g.accounts)]);
        if (g.documents != null) growthRows.push([this.t('rep_growth_documents', 'Neue Dokumente (30 Tage)'), this._num(g.documents)]);

        const growthPanel = growthRows.length
            ? this._panel(this.t('rep_section_growth', 'Wachstum (30 Tage)'), 'bi-graph-up-arrow', this._tableRows(growthRows))
            : '';

        let meetmePanel = '';
        if (m && m.meetings_total != null) {
            meetmePanel = this._panel(
                this.t('rep_section_meetme', 'Konferenz / MeetMe'),
                'bi-calendar-event',
                this._tableRows([
                    [this.t('rep_mm_meetings', 'Termine gesamt'), this._num(m.meetings_total)],
                    [this.t('rep_mm_upcoming', 'Anstehende Termine'), this._num(m.meetings_upcoming)],
                    [this.t('rep_mm_cancelled', 'Abgesagte Termine'), this._num(m.meetings_cancelled)],
                    [this.t('rep_mm_guests', 'Aktive Gäste'), this._num(m.guests_total)],
                    [this.t('rep_mm_reminders', 'Offene Erinnerungen'), this._num(m.reminders_open)],
                ]),
            );
        }

        const foot = d.generated_at
            ? `<div class="crm-rpt-foot">${this.esc(this.t('rep_generated', 'Stand'))}: ${this.esc(this._fmtDate(d.generated_at))}</div>`
            : '';

        root.innerHTML = kpis + syncPanel + overviewPanel + qualityPanel + growthPanel + meetmePanel + foot;
        this._bindPanels(root);
    },

    refresh() {
        this.load();
    },

    async startSync() {
        try {
            const r = await fetch('/crm/api/reporting/sync/start/', {
                method: 'POST',
                headers: this._headers(true),
                body: '{}',
            });
            let data = {};
            try { data = await r.json(); } catch (e) { /* HTML error page */ }
            const msg = data.message || data.error
                || (r.status === 404
                    ? this.t('rep_sync_unavailable', 'Sync-Endpoint nicht verfügbar.')
                    : this.t('sync_gestartet', 'Sync wird gestartet — bitte warten...'));
            if (typeof window.showToast === 'function') window.showToast(msg);
            else alert(msg);
            if (data.ok) setTimeout(() => this.refresh(), 1500);
        } catch (e) {
            const msg = this.t('rep_sync_unavailable', 'Sync-Endpoint nicht verfügbar.');
            if (typeof window.showToast === 'function') window.showToast(msg);
            else alert(msg);
        }
    },
};

window.CRM_Reporting = CRM_Reporting;
window.crmStartSync = () => CRM_Reporting.startSync();
window.crmReportingRefresh = () => CRM_Reporting.refresh();

document.addEventListener('DOMContentLoaded', () => {
    if (window.CRM_TAB === 'reporting') CRM_Reporting.init();
});

document.addEventListener('languageChanged', () => {
    if (window.CRM_TAB === 'reporting' && CRM_Reporting._data) CRM_Reporting.render();
});
