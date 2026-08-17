#!/usr/bin/env bash
# OnlyOffice pluginsmanager-Guard (ucs5)
#
# Problem: documentserver-pluginsmanager --update hängt oft (98% CPU, →5GB+ RAM)
# und legt die Box lahm. Beim Container-Start kommt er zuverlässig wieder.
#
# Dieses Skript killt den Update-Lauf, sobald er spürbar spinnt / zu groß wird.
# Installation: bash scripts/install-onlyoffice-pluginsmanager-guard.sh
#
set -euo pipefail

# Schwellwerte
MAX_RSS_KB="${MAX_RSS_KB:-512000}"      # ~500 MB
MAX_CPU="${MAX_CPU:-50}"                # %CPU (ps)
MAX_AGE_SEC="${MAX_AGE_SEC:-90}"        # Sekunden seit Start → kill Update sowieso
DRY_RUN="${DRY_RUN:-0}"

_log() { logger -t oo-plugins-guard "$*" 2>/dev/null || echo "[oo-plugins-guard] $*"; }

_etime_to_sec() {
  # ps etime: [[DD-]HH:]MM:SS
  local e="$1" d=0 h=0 m=0 s=0
  if [[ "$e" == *-* ]]; then
    d="${e%%-*}"
    e="${e#*-}"
  fi
  IFS=: read -r a b c <<<"$e"
  if [[ -n "${c:-}" ]]; then
    h=$a; m=$b; s=$c
  else
    m=$a; s=$b
  fi
  echo $((10#$d*86400 + 10#$h*3600 + 10#$m*60 + 10#$s))
}

killed=0
while read -r pid rss etime pcpu cmd; do
  [[ -z "${pid:-}" ]] && continue
  # nur der Update-Lauf / pluginsmanager-Tool
  case "$cmd" in
    *tools/pluginsmanager*|*documentserver-pluginsmanager*) ;;
    *) continue ;;
  esac

  age="$(_etime_to_sec "$etime")"
  reason=""
  if [[ "$age" -ge "$MAX_AGE_SEC" ]]; then
    reason="age=${age}s>=${MAX_AGE_SEC}s"
  elif awk -v c="$pcpu" -v m="$MAX_CPU" 'BEGIN{exit !(c+0>=m)}'; then
    reason="cpu=${pcpu}%>=${MAX_CPU}%"
  elif [[ "${rss:-0}" -ge "$MAX_RSS_KB" ]]; then
    reason="rss=${rss}KB>=${MAX_RSS_KB}KB"
  else
    continue
  fi

  _log "KILL pid=$pid $reason cmd=$(echo "$cmd" | cut -c1-120)"
  if [[ "$DRY_RUN" == "1" ]]; then
    continue
  fi
  kill "$pid" 2>/dev/null || true
  sleep 1
  kill -9 "$pid" 2>/dev/null || true
  killed=$((killed + 1))
done < <(ps -eo pid=,rss=,etime=,pcpu=,cmd= | awk '
  /tools\/pluginsmanager|documentserver-pluginsmanager/ {print}
')

# Parent-Wrapper-Skript ebenfalls beenden, sonst startet er neu
if [[ "$DRY_RUN" != "1" ]]; then
  pkill -f 'documentserver-pluginsmanager\.sh' 2>/dev/null || true
fi

[[ "$killed" -gt 0 ]] && _log "killed=$killed" || true
exit 0
