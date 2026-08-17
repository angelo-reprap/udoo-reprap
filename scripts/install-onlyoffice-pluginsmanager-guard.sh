#!/usr/bin/env bash
# Installiert systemd Timer: OnlyOffice pluginsmanager-Guard (jede Minute)
#
# Auf ucs5:
#   cd /mnt/public/udoo-reprap
#   git pull --rebase origin cursor/cv-extractor-7f07
#   bash scripts/install-onlyoffice-pluginsmanager-guard.sh
#   systemctl status oo-pluginsmanager-guard.timer
#
set -euo pipefail

REPO="${REPO:-/mnt/public/udoo-reprap}"
GUARD="$REPO/scripts/onlyoffice-pluginsmanager-guard.sh"
UNIT_DIR=/etc/systemd/system

if [[ ! -f "$GUARD" ]]; then
  echo "ERROR: Guard fehlt: $GUARD" >&2
  exit 1
fi
chmod +x "$GUARD"

cat > "$UNIT_DIR/oo-pluginsmanager-guard.service" <<EOF
[Unit]
Description=Kill runaway OnlyOffice pluginsmanager (--update spin)
After=docker.service

[Service]
Type=oneshot
ExecStart=$GUARD
Nice=10
EOF

cat > "$UNIT_DIR/oo-pluginsmanager-guard.timer" <<EOF
[Unit]
Description=Timer: OnlyOffice pluginsmanager guard (every minute)

[Timer]
OnBootSec=2min
OnUnitActiveSec=1min
AccuracySec=15s
Persistent=true

[Install]
WantedBy=timers.target
EOF

# Auch direkt nach OnlyOffice-App-Start (Univention LSB unit)
mkdir -p /etc/systemd/system/docker-app-onlyoffice-ds.service.d
cat > /etc/systemd/system/docker-app-onlyoffice-ds.service.d/pluginsmanager-guard.conf <<EOF
[Service]
# Nach Start kurz warten, dann Update-Spin killen (falls schon da)
ExecStartPost=-/bin/bash -c 'sleep 35; $GUARD; sleep 30; $GUARD'
EOF

systemctl daemon-reload
systemctl enable --now oo-pluginsmanager-guard.timer
systemctl restart oo-pluginsmanager-guard.timer

echo "=== installiert ==="
systemctl status oo-pluginsmanager-guard.timer --no-pager || true
echo
echo "Sofort-Test:"
echo "  $GUARD"
echo "  journalctl -t oo-plugins-guard -n 20 --no-pager"
echo
# einmal ausführen
bash "$GUARD" || true
pgrep -af pluginsmanager || echo 'kein pluginsmanager — gut'
free -h | head -2
