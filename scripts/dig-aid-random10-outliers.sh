#!/usr/bin/env bash
# Dig Random-10 Ausreißer auf ucs5 (lorenz no_neu, al-kenani Perioden).
#
#   cd /mnt/public/udoo-reprap
#   bash scripts/dig-aid-random10-outliers.sh
#   ARTIFACTS=artifacts/aid-random10-20260814-154835 bash scripts/dig-aid-random10-outliers.sh
#
set -euo pipefail

ROOT="${AID_PROFILE_ROOT:-/mnt/public/Berater/AID_profile}"
BACKEND="${BACKEND:-/opt/abpe/backend}"
REPO="${REPO:-/mnt/public/udoo-reprap}"
ARTIFACTS="${ARTIFACTS:-}"

if [[ -z "$ARTIFACTS" ]]; then
  ARTIFACTS="$(ls -dt "$REPO"/artifacts/aid-random10-* 2>/dev/null | head -1 || true)"
fi

echo "=== Artifacts: ${ARTIFACTS:-'(keine)'} ==="
if [[ -n "${ARTIFACTS}" && -d "$ARTIFACTS" ]]; then
  echo "--- compare-scores ---"
  column -t -s $'\t' "$ARTIFACTS/compare-scores.tsv" 2>/dev/null || cat "$ARTIFACTS/compare-scores.tsv" || true
fi

echo
echo "=== LORENZ: Ordner + falscher Bucket? ==="
ls -la "$ROOT/lll/lorenz_michael/" | head -40
echo "--- neu/cv unter lll ---"
ls -la "$ROOT/lll/lorenz_michael/neu/cv/" 2>/dev/null || echo '(kein neu/cv unter lll)'
echo "--- find neu/cv irgendwo ---"
find "$ROOT" -path '*/lorenz_michael/neu/cv/*' 2>/dev/null | head -20 || echo '(nirgends)'
echo "--- html_out / doc_out ---"
ls -la "$BACKEND/data/html_out/lorenz_michael/" 2>/dev/null | head -20 || echo '(kein html_out)'
ls -la "$BACKEND/data/doc_out/lorenz_michael/" 2>/dev/null | head -20 || echo '(kein doc_out)'

echo
echo "=== LORENZ: DB / letzte Jobs (Django) ==="
cd "$BACKEND"
# shellcheck disable=SC1091
[[ -f /opt/abpe/venv311/bin/activate ]] && source /opt/abpe/venv311/bin/activate
python3 manage.py shell -c "
from apps.cv_extractor.models import Consultant, UploadedPDF, ExtractionJob
cs = list(Consultant.objects.filter(consultant_dir__icontains='lorenz').values(
    'id','aid','first_name','last_name','consultant_dir','language')[:10])
print('consultants:', cs)
ups = list(UploadedPDF.objects.filter(target_directory__icontains='lorenz').order_by('-id').values(
    'id','filename','status','aid','consultant_dir','error_message')[:5])
print('uploads:', ups)
" 2>/dev/null || echo '(shell query fehlgeschlagen)'

echo
echo "=== AL-KENANI: neu/cv + Re-Compare nach Perioden-Fix ==="
ls -la "$ROOT/aaa/al-kenani_muhanned/neu/cv/" 2>/dev/null | head -20 || echo '(kein neu/cv)'
OUT="${REPO}/artifacts/dig-alkenani-$(date +%Y%m%d-%H%M%S)"
python3 manage.py compare_aid_neu_cv \
  --letter aaa --dir al-kenani_muhanned --out "$OUT"
echo "Compare → $OUT"
cat "$OUT/by_dir/al-kenani_muhanned.md" | head -40

echo
echo "=== AL-KENANI: Period-Gap Klassifikation ==="
GAP_OUT="$OUT/period-gaps.md"
python3 "$REPO/scripts/dig-period-gaps.py" \
  --letter aaa --dir al-kenani_muhanned --out "$GAP_OUT" | head -120
echo "(full → $GAP_OUT)"

echo
echo "=== Fertig ==="
echo "Falls Lorenz nur falsch gebucketet: bash scripts/SAFE-cv-extractor-edit.sh deploy"
echo "dann: python3 manage.py publish_neu_cv --dir lorenz_michael"
echo "oder Re-Import: python3 manage.py import_aid_profiles --letter lll --dir lorenz_michael --sync --no-skip-existing"
echo
echo "Artifacts committen (Cloud lesen):"
echo "  cd $REPO && git add $OUT && git commit -m 'chore: dig al-kenani period gaps' && git push origin cursor/cv-extractor-7f07"
