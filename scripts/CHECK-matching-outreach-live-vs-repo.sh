#!/usr/bin/env bash
# Prüft Live-Dateien vs. Git-Branch (Outreach-Wizard) — 1:1 Guard.
#
#   cd /mnt/public/udoo-reprap
#   git fetch origin cursor/matching-outreach-wizard-1532
#   bash <(git show origin/cursor/matching-outreach-wizard-1532:scripts/CHECK-matching-outreach-live-vs-repo.sh)
#
# Exit 0 = Dateien gleich (oder Live fehlt = frischer Deploy ok)
# Exit 2 = Live hat Markierungen die Repo nicht hat → zuerst PULL
# Exit 1 = Diff / Live hinter Branch → SYNC ok, oder Konflikt
#
set -euo pipefail

BRANCH="${BRANCH:-cursor/matching-outreach-wizard-1532}"
LIVE_MW="${LIVE_MW:-/opt/abpe/backend/apps/abpe_matching_workflow}"
LIVE_UI="${LIVE_UI:-/opt/abpe/backend/apps/abpe_ui}"
LIVE_JS="${LIVE_JS:-$LIVE_UI/static/abpe_ui/js/mod/mod-matching.js}"

echo "=== CHECK Outreach Live ↔ origin/$BRANCH ==="

git fetch origin "$BRANCH" >/dev/null 2>&1 || true

_sha() { sha256sum "$1" 2>/dev/null | awk '{print $1}'; }
_sha_git() {
  git show "origin/$BRANCH:$1" 2>/dev/null | sha256sum | awk '{print $1}'
}

differs=0
live_ahead=0
repo_ahead=0

check_pair() {
  local rel="$1" live="$2" marker_new="${3:-}"
  local gs ls
  gs="$(_sha_git "$rel" || true)"
  if [[ -z "$gs" || "$gs" == "$(echo -n | sha256sum | awk '{print $1}')" ]]; then
    # empty/missing in git
    if [[ ! -f "$live" ]]; then
      echo "  SKIP  $rel (weder Live noch Git)"
      return
    fi
    echo "  WARN  $rel nur Live — fehlt im Branch"
    live_ahead=1
    return
  fi
  if [[ ! -f "$live" ]]; then
    echo "  BEHIND Live fehlt: $live  → SYNC ok"
    repo_ahead=1
    return
  fi
  ls="$(_sha "$live")"
  if [[ "$ls" == "$gs" ]]; then
    echo "  OK    $rel"
    return
  fi
  differs=1
  echo "  DIFF  $rel"
  echo "        live=$ls"
  echo "        git =$gs"
  if [[ -n "$marker_new" ]]; then
    local lm rm
    lm=$(grep -c "$marker_new" "$live" 2>/dev/null || echo 0)
    rm=$(git show "origin/$BRANCH:$rel" 2>/dev/null | grep -c "$marker_new" || echo 0)
    lm=${lm//$'\n'/}; rm=${rm//$'\n'/}
    if [[ "$lm" -gt "$rm" ]]; then
      echo "        → Live hat mehr '$marker_new' ($lm>$rm) — PULL zuerst!"
      live_ahead=1
    elif [[ "$rm" -gt "$lm" ]]; then
      echo "        → Repo neuer ($rm>$lm) — SYNC ok"
      repo_ahead=1
    else
      echo "        → gleicher Marker-Count, Inhalt anders — manuell prüfen"
    fi
  fi
}

check_pair "Repo_abpe/abpe_ui/incoming/mod-matching.js" "$LIVE_JS" "outreachUnifiedSearch"
check_pair "Repo_abpe/abpe_matching_workflow/incoming/views.py" "$LIVE_MW/views.py" "api_outreach_deep_reason"
check_pair "Repo_abpe/abpe_matching_workflow/incoming/urls.py" "$LIVE_MW/urls.py" "api_outreach_letter_draft"
check_pair "Repo_abpe/abpe_matching_workflow/incoming/services/outreach_wizard.py" \
  "$LIVE_MW/services/outreach_wizard.py" "build_letter_draft"
LIVE_CRM="${LIVE_CRM:-/opt/abpe/backend/apps/abpe_crm}"
check_pair "Repo_abpe/abpe_crm/incoming/views.py" "$LIVE_CRM/views.py" "orm_emergency"

echo
if [[ "$live_ahead" -eq 1 ]]; then
  echo "ERGEBNIS: Live voraus / hat Extra → zuerst Live→Repo pullen, sonst Feature-Verlust."
  echo "  bash <(git show origin/$BRANCH:scripts/PULL-matching-from-live.sh) --push"
  exit 2
fi
if [[ "$differs" -eq 0 ]]; then
  echo "ERGEBNIS: 1:1 — Erweiterung/SYNC sicher."
  exit 0
fi
if [[ "$repo_ahead" -eq 1 ]]; then
  echo "ERGEBNIS: Repo neuer als Live — SYNC erlaubt."
  exit 0
fi
echo "ERGEBNIS: Diff ohne klare Richtung — Dateien vergleichen bevor SYNC."
exit 1
