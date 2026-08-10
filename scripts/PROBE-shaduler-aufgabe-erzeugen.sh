#!/usr/bin/env bash
# Funktionstest: Workflow „Aufgabe erzeugen“ (Posteingang → Aufgabe → Aktionen)
#
# Auf ucs5:
#   cd /mnt/public/udoo-reprap && git fetch origin cursor/abpe-shaduler-scaffold-7f07
#   bash scripts/PROBE-shaduler-aufgabe-erzeugen.sh
#   # oder ohne Checkout:
#   bash <(git show origin/cursor/abpe-shaduler-scaffold-7f07:scripts/PROBE-shaduler-aufgabe-erzeugen.sh)
#
# Optional:
#   CLEANUP=0                              — Test-Aufgaben behalten
#   CRM_EMAIL=brahim.abbady@hotmail.de     — CRM-Notiz + Lookup mittesten
set -u

BACKEND="${BACKEND:-/opt/abpe/backend}"
PYBIN="${PYBIN:-/opt/abpe/venv311/bin/python}"
LIVE_UI="${LIVE_UI:-/opt/abpe/backend/apps/abpe_ui}"
STATICFILES="${STATICFILES:-/opt/abpe/backend/staticfiles}"
CLEANUP="${CLEANUP:-1}"

PASS=0
FAIL=0
WARN=0

ok()   { echo "  OK  $*"; PASS=$((PASS+1)); }
fail() { echo "  FAIL $*"; FAIL=$((FAIL+1)); }
warn() { echo "  WARN $*"; WARN=$((WARN+1)); }

_has() { command -v "$1" >/dev/null 2>&1; }
_grep() {
  if _has rg; then rg "$@"
  else grep -E "$@"
  fi
}

echo "======== PROBE Aufgabe erzeugen $(date -Iseconds) ========"
echo "CLEANUP=$CLEANUP  CRM_EMAIL=${CRM_EMAIL:-<leer>}"
echo

# ─── 1) Static / UI-Checkliste ───────────────────────────────────────────────
echo "=== 1) UI-Static: Pflicht-Strings ==="
JS_APP="$LIVE_UI/static/abpe_ui/js/mod/mod-shaduler.js"
JS_SF="$STATICFILES/abpe_ui/js/mod/mod-shaduler.js"
CSS_APP="$LIVE_UI/static/abpe_ui/css/mod/mod-shaduler.css"

check_js() {
  local file="$1" label="$2"
  if [[ ! -f "$file" ]]; then
    fail "$label fehlt: $file"
    return
  fi
  ok "$label vorhanden ($(stat -c %y "$file" 2>/dev/null | cut -d. -f1 || echo '?'))"
  local n
  for n in \
    openMailTaskChooser \
    sms_messenger \
    'data-art=.post.|id: .post.' \
    sh-mt-crm \
    crm_notiz \
    sh-m-erledigt \
    sh-m-verschieben \
    sh-m-wa-phone \
    sh-m-wa-text \
    'normalizeWaPhone|0049' \
    'crmDetailUrl|CRM Notizen' \
    setupWhatsAppCompose
  do
    if _grep -q "$n" "$file"; then
      ok "$label: /$n/"
    else
      fail "$label: fehlt /$n/ → SYNC-abpe-shaduler-files.sh"
    fi
  done
}

check_js "$JS_APP" "App-JS"
check_js "$JS_SF" "staticfiles-JS"

if [[ -f "$JS_APP" && -f "$JS_SF" ]]; then
  if cmp -s "$JS_APP" "$JS_SF"; then
    ok "App-JS ≡ staticfiles"
  else
    fail "App-JS ≠ staticfiles — Browser sieht ggf. alte Version"
  fi
fi

if [[ -f "$CSS_APP" ]] && _grep -q 'sh-m-wa-phone|sh-m-quick' "$CSS_APP"; then
  ok "CSS WA/Quick-Styles"
else
  warn "CSS WA/Quick-Styles nicht gefunden"
fi
echo

# ─── 2) Art-Buttons ──────────────────────────────────────────────────────────
echo "=== 2) Art-Auswahl vollständig? ==="
EXPECTED_ARTS="anruf sms_messenger wiedervorlage email post termin dokument intern"
if [[ -f "$JS_APP" ]]; then
  for art in $EXPECTED_ARTS; do
    if _grep -q "data-art=.${art}.|id: '${art}'" "$JS_APP"; then
      ok "Art-Button $art"
    else
      fail "Art-Button $art fehlt"
    fi
  done
else
  fail "kein JS für Art-Check"
fi
echo

# ─── 3) Backend ──────────────────────────────────────────────────────────────
echo "=== 3) Backend ==="
if [[ ! -x "$PYBIN" ]]; then
  fail "Python fehlt: $PYBIN"
  echo "======== SUMMARY: PASS=$PASS FAIL=$FAIL WARN=$WARN ========"
  exit 2
fi
ok "Python $PYBIN"
cd "$BACKEND" || { fail "BACKEND $BACKEND"; exit 2; }
echo

# ─── 4) Django Funktionstest ─────────────────────────────────────────────────
echo "=== 4) Django-Workflow ==="
export CLEANUP CRM_EMAIL="${CRM_EMAIL:-}"
"$PYBIN" - <<'PY'
import os, sys, uuid
from datetime import timedelta

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'abpe_backend.settings')
import django
django.setup()

from django.contrib.auth import get_user_model
from django.utils import timezone
from apps.abpe_shaduler.models import Aufgabe, Aktivitaet
from apps.abpe_shaduler.services import inbox_service, aufgaben_service, ergebnis_service

PASS = FAIL = WARN = 0
created_ids = []

def ok(msg):
    global PASS
    print('  OK ', msg); PASS += 1

def fail(msg):
    global FAIL
    print('  FAIL', msg); FAIL += 1

def warn(msg):
    global WARN
    print('  WARN', msg); WARN += 1

User = get_user_model()
user = (
    User.objects.filter(is_superuser=True).first()
    or User.objects.filter(is_staff=True).first()
    or User.objects.first()
)
if not user:
    fail('kein Django-User vorhanden')
    print(f'\nDJANGO_SUMMARY PASS={PASS} FAIL={FAIL} WARN={WARN}')
    sys.exit(1)
ok(f'User={user.username}')

# Phone-Normalisierung
for raw, expect_ok in [
    ('+49 172 6734154', True),
    ('01726734154', True),
    ('00491726734154', True),
    ('123', False),
    ('', False),
]:
    norm, good = aufgaben_service.normalize_de_phone(raw)
    if good == expect_ok and (not expect_ok or norm.startswith('0049')):
        ok(f'normalize_de_phone({raw!r}) → {norm!r} ok={good}')
    else:
        fail(f'normalize_de_phone({raw!r}) → {norm!r} ok={good} (erwartet ok={expect_ok})')

crm_email = (os.environ.get('CRM_EMAIL') or '').strip()
from_addr = crm_email or 'probe.aufgabe@example.invalid'
probe_tag = uuid.uuid4().hex[:10]

crm_info = {}
if crm_email:
    try:
        crm_info = inbox_service.crm_lookup(from_addr) or {}
        if crm_info.get('found') and crm_info.get('crm_bean_id'):
            ok(f'CRM-Lookup {from_addr} → {crm_info.get("crm_name")} ({crm_info.get("crm_bean_id")})')
        else:
            warn(f'CRM-Lookup ohne Treffer für {from_addr}')
            crm_info = {}
    except Exception as exc:
        warn(f'CRM-Lookup Fehler: {exc}')
        crm_info = {}
else:
    warn('CRM_EMAIL nicht gesetzt — CRM-Notiz nur eingeschränkt')

_orig_es = inbox_service._get_es_mail

def _fake_es_mail(mid):
    mid = str(mid)
    if mid.startswith('es:probe-'):
        return {
            'id': mid,
            'subj': f'PROBE JULI {probe_tag}',
            'from': from_addr,
            'prev': 'Funktionstest Aufgabe erzeugen',
            'box': 'Probe',
            'crm_bean_id': crm_info.get('crm_bean_id') or '',
            'crm_bean_module': crm_info.get('crm_bean_module') or '',
            'crm_name': crm_info.get('crm_name') or '',
            'crm_url': crm_info.get('crm_url') or '',
            'matching_url': crm_info.get('matching_url') or '',
        }
    return _orig_es(mid)

inbox_service._get_es_mail = _fake_es_mail

arts = [
    'anruf', 'sms_messenger', 'wiedervorlage', 'email',
    'post', 'termin', 'dokument', 'intern',
]

print()
print('  -- mail_to_aufgabe je Art --')
try:
    for art in arts:
        try:
            mid = f'es:probe-{probe_tag}-{art}'
            res = inbox_service.mail_to_aufgabe(
                mid,
                user,
                art=art,
                faellig_am=timezone.localdate().isoformat(),
                faellig_zeit='12:00',
                notiz=f'PROBE {art} Funktionstest',
                crm_notiz=True,
                dauer_min=30,
            )
            created = res.get('created') or {}
            tid = created.get('id')
            if not tid:
                fail(f'{art}: keine Aufgabe-ID in Response')
                continue
            created_ids.append(tid)
            a = Aufgabe.objects.filter(pk=tid).first()
            if not a:
                fail(f'{art}: nicht in DB')
                continue
            if a.art != art:
                fail(f'{art}: DB art={a.art}')
            else:
                ok(f'{art}: angelegt {str(tid)[:8]}…')
            if 'PROBE' not in (a.beschreibung or ''):
                fail(f'{art}: Notiz fehlt in Beschreibung')
            else:
                ok(f'{art}: Notiz in Beschreibung')
            if a.faellig_zeit is None:
                warn(f'{art}: faellig_zeit leer')
            else:
                ok(f'{art}: Zeit={a.faellig_zeit}')
            if crm_info.get('crm_bean_id') and art == 'anruf':
                if res.get('crm_notiz'):
                    ok(f'{art}: crm_notiz=True')
                else:
                    fail(f'{art}: crm_notiz erwartet True, got {res.get("crm_notiz")}')
        except Exception as exc:
            fail(f'{art}: {exc}')
finally:
    inbox_service._get_es_mail = _orig_es

print()
print('  -- CRM-Notiz Direktpfad --')
if crm_info.get('crm_bean_id'):
    try:
        written = inbox_service._write_crm_note(
            bean_module=crm_info.get('crm_bean_module') or 'Contacts',
            bean_id=crm_info['crm_bean_id'],
            note_text='PROBE CRM-Notiz Funktionstest (löschen ok)',
            note_type='email',
            user=user,
        )
        if written:
            ok('CrmContactNote geschrieben')
        else:
            fail('_write_crm_note → False')
    except Exception as exc:
        fail(f'CRM-Notiz: {exc}')
else:
    warn('CRM-Notiz-Schreibtest übersprungen (CRM_EMAIL=… setzen)')

print()
print('  -- WhatsApp serialize --')
wa = Aufgabe.objects.filter(pk__in=created_ids, art=Aufgabe.Art.SMS_MESSENGER).first()
if wa:
    wa.ref_type = 'berater'
    wa.ref_id = 'lorenz'
    wa.beschreibung = 'Interview morgen 10:00 bei Bechtle.\ntel:+491711234567'
    wa.save(update_fields=['ref_type', 'ref_id', 'beschreibung'])
    ser = aufgaben_service.serialize(wa)
    for key in ('phone', 'phones', 'wa_text', 'whatsapp_url', 'crm_url'):
        if key in ser:
            ok(f'serialize.{key}={str(ser.get(key))[:90]!r}')
        else:
            fail(f'serialize fehlt {key}')
    if ser.get('wa_text'):
        ok('wa_text gesetzt')
    else:
        fail('wa_text leer')
    if ser.get('phone'):
        ok(f'phone={ser["phone"]}')
    else:
        warn('phone leer')
else:
    fail('keine sms_messenger Aufgabe')

print()
print('  -- Erledigt / Snooze --')
anruf = Aufgabe.objects.filter(pk__in=created_ids, art=Aufgabe.Art.ANRUF).first()
if anruf:
    try:
        r = ergebnis_service.anwenden(
            aufgabe=anruf, ergebnis_code='erledigt', daten={}, user=user,
        )
        anruf.refresh_from_db()
        if anruf.erledigt_am or anruf.status == Aufgabe.Status.ERLEDIGT:
            ok(f'erledigt action={r.get("action")}')
        else:
            fail(f'erledigt status={anruf.status}')
    except Exception as exc:
        fail(f'erledigt: {exc}')
else:
    fail('kein Anruf für Erledigt')

post = Aufgabe.objects.filter(
    pk__in=created_ids, art=Aufgabe.Art.POST, status=Aufgabe.Status.OFFEN,
).first()
if post:
    try:
        before = post.faellig_am
        r = ergebnis_service.anwenden(
            aufgabe=post, ergebnis_code='snooze', daten={'days': 2}, user=user,
        )
        post.refresh_from_db()
        if r.get('action') == 'snooze' and post.faellig_am and post.faellig_am >= before:
            ok(f'snooze +2d → {post.faellig_am} (vorher {before})')
        else:
            fail(f'snooze unerwartet: {r}')
    except Exception as exc:
        fail(f'snooze: {exc}')
else:
    warn('kein Post offen für Snooze')

print()
print('  -- Aktivitäten --')
n_akt = Aktivitaet.objects.filter(
    details__aufgabe_id__in=[str(x) for x in created_ids],
).count()
if n_akt:
    ok(f'Aktivitaeten zu Probe-Aufgaben: {n_akt}')
else:
    warn('keine Aktivitäten mit aufgabe_id in details')

print()
cleanup = os.environ.get('CLEANUP', '1') not in ('0', 'false', 'no')
if cleanup and created_ids:
    deleted, _ = Aufgabe.objects.filter(pk__in=created_ids).delete()
    ok(f'Cleanup: {deleted} Objekte ({len(created_ids)} Aufgaben)')
elif created_ids:
    warn(f'Cleanup aus — IDs: {created_ids}')
else:
    warn('nichts zu cleanen')

print()
print(f'DJANGO_SUMMARY PASS={PASS} FAIL={FAIL} WARN={WARN}')
sys.exit(1 if FAIL else 0)
PY
DJ_RC=$?
if [[ $DJ_RC -ne 0 ]]; then
  fail "Django-Workflow Exit=$DJ_RC"
else
  ok "Django-Workflow Exit=0"
fi
echo

# ─── 5) Manuelle Checkliste ──────────────────────────────────────────────────
echo "=== 5) Browser-Checkliste (manuell) ==="
cat <<'EOF'
  [ ] Posteingang → Aufgabe erzeugen öffnet Dialog
  [ ] Arten: Anruf, WhatsApp, Wiedervorlage, E-Mail, Post, Termin, Dokument, Intern
  [ ] CRM-Zeile + Checkbox Notiz + „Datensatz öffnen“ → Berater-Detail
  [ ] Notiz anlegen → Aufgabe erscheint; CRM Notizen-Reiter hat Eintrag
  [ ] WhatsApp-Aufgabe: Telefon 0049-OK + Mobil-Vorschlag + Versenden → Ergebnis
  [ ] Anruf: Anrufen + Erledigt / Verschieben
  [ ] Nach Erledigt: Weiter öffnet CRM Notizen (neues Fenster)
EOF
echo

echo "======== SUMMARY: PASS=$PASS FAIL=$FAIL WARN=$WARN ========"
if [[ $FAIL -gt 0 ]]; then
  echo "Ergebnis: LÜCKEN / FEHLER"
  exit 1
fi
echo "Ergebnis: automatische Checks OK — §5 noch manuell"
exit 0
