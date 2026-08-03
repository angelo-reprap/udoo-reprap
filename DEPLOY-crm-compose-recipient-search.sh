#!/usr/bin/env bash
# Deploy CRM Compose Empfänger-Suche (Elasticsearch fuzzy suggest)
# Auf ucs5 ausführen, Repo-Root = /mnt/public/udoo-reprap (oder lokal angepasste Pfade).
set -euo pipefail

ROOT="${1:-/mnt/public/udoo-reprap}"
LIVE="${LIVE_BACKEND:-/opt/abpe/backend}"
CRM_APP="${LIVE}/apps/abpe_crm"

echo "==> Source: $ROOT"
echo "==> Live:   $LIVE"

install -v -m 644 \
  "$ROOT/Repo_abpe/abpe_crm/incoming/views.py" \
  "$CRM_APP/incoming/views.py"

install -v -m 644 \
  "$ROOT/Repo_abpe/abpe_crm/incoming/urls.py" \
  "$CRM_APP/incoming/urls.py"

install -d -m 755 "$CRM_APP/incoming/templates/abpe_crm"
install -v -m 644 \
  "$ROOT/Repo_abpe/abpe_crm/incoming/templates/abpe_crm/email_compose.html" \
  "$CRM_APP/incoming/templates/abpe_crm/email_compose.html"

echo "==> Reload uWSGI / gunicorn (falls vorhanden) …"
if systemctl is-active --quiet abpe-backend 2>/dev/null; then
  systemctl reload abpe-backend || systemctl restart abpe-backend
elif [[ -x "$LIVE/venv311/bin/uwsgi" ]] && [[ -f /etc/uwsgi/apps-enabled/abpe.ini ]]; then
  touch /etc/uwsgi/apps-enabled/abpe.ini
else
  echo "    (kein Auto-Reload — Backend manuell neu starten)"
fi

echo "OK — Compose Empfänger-Suche deployed."
echo "Hard-Reload im Browser, dann /crm/email/compose/ testen:"
echo "  Tippen: Name / Firma / Tel / E-Mail → Dropdown mit Treffern"
