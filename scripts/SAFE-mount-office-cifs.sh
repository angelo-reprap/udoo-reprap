#!/usr/bin/env bash
# O:-Share (office) analog zu X: (public) auf /mnt/office hängen.
#
# Public (bereits gemountet):
#   //172.20.3.150/public  →  /mnt/public   (cifs, username=office)
# Office fehlt: /mnt/office ist nur ein lokales Verzeichnis mit abpe/.
#
# Diagnose (kein Mount):
#   bash scripts/SAFE-mount-office-cifs.sh
# Mounten:
#   bash scripts/SAFE-mount-office-cifs.sh --apply
#
set +e
APPLY=0
for arg in "$@"; do
  case "$arg" in
    --apply) APPLY=1 ;;
    -h|--help) sed -n '2,14p' "$0"; exit 0 ;;
  esac
done

OFFICE_MNT="${DMS_OFFICE_MOUNT:-/mnt/office}"
PUBLIC_MNT="${DMS_PUBLIC_MOUNT:-/mnt/public}"
NAS="${NAS:-172.20.3.150}"
SHARE="${OFFICE_SHARE:-office}"

echo "whoami=$(whoami)"
echo
echo "=== findmnt ==="
findmnt -T "$OFFICE_MNT" -T "$PUBLIC_MNT" -o TARGET,SOURCE,FSTYPE,OPTIONS 2>/dev/null || true
echo
echo "=== fstab (cifs/office/public) ==="
grep -Ei 'cifs|office|public' /etc/fstab 2>/dev/null || echo "(keine Treffer in /etc/fstab)"
echo
echo "=== $OFFICE_MNT ==="
ls -ld "$OFFICE_MNT" 2>&1
ls -lb "$OFFICE_MNT" 2>&1 | head -20
if mountpoint -q "$OFFICE_MNT" 2>/dev/null || awk -v p="$OFFICE_MNT" '$2==p {found=1} END{exit !found}' /proc/mounts; then
  echo "IST GEMOUNTET"
else
  echo "NICHT gemountet (lokales Verzeichnis)"
fi

echo
echo "=== Credentials aus public-Mount/fstab ==="
CRED=""
OPTS=$(findmnt -n -o OPTIONS "$PUBLIC_MNT" 2>/dev/null)
echo "public options: $OPTS"
CRED=$(grep -E "[[:space:]]$PUBLIC_MNT[[:space:]]" /etc/fstab 2>/dev/null | sed -n 's/.*credentials=\([^,[:space:]]*\).*/\1/p' | head -1)
if [[ -z "$CRED" ]]; then
  CRED=$(echo "$OPTS" | tr ',' '\n' | sed -n 's/^credentials=//p' | head -1)
fi
if [[ -n "$CRED" ]]; then
  echo "credentials-Datei: $CRED"
  ls -l "$CRED" 2>&1
else
  echo "keine credentials= Zeile gefunden — Mount braucht dieselbe Auth wie public (username=office)"
fi

echo
echo "=== SMB-Shares auf $NAS ==="
if [[ -n "$CRED" && -f "$CRED" ]] && command -v smbclient >/dev/null; then
  smbclient -L "//$NAS" -A "$CRED" -m SMB3 2>/dev/null | head -40
else
  echo "smbclient -L übersprungen (kein credentials-File oder kein smbclient)"
  echo "Manuell: smbclient -L //$NAS -U office"
fi

TARGET="//${NAS}/${SHARE}"
echo
echo "=== geplanter Mount ==="
echo "  $TARGET  →  $OFFICE_MNT"
MP_OPTS="vers=3.0,uid=0,gid=0,forceuid,forcegid,file_mode=0664,dir_mode=0775,iocharset=utf8,soft,nounix,mapposix,_netdev"
if [[ -n "$CRED" && -f "$CRED" ]]; then
  MP_OPTS="credentials=${CRED},${MP_OPTS}"
else
  MP_OPTS="username=office,${MP_OPTS}"
  echo "HINWEIS: ohne credentials-Datei fragt mount nach dem Passwort von user office"
fi
echo "  mount -t cifs $TARGET $OFFICE_MNT -o $MP_OPTS"

FILE='/mnt/office/Berater/Berater aktive & passive/passive/wollschlaeger_andreas/Rechnungen/Rechnung Hotel Schlossberg Wolli_Dezember2014.pdf'

if [[ "$APPLY" -ne 1 ]]; then
  echo
  echo "Dry-run. Zum Mounten: bash scripts/SAFE-mount-office-cifs.sh --apply"
  echo "Danach: ls -l '$FILE'"
  exit 0
fi

if [[ "$(id -u)" -ne 0 ]]; then
  echo "FAIL: --apply braucht root"
  exit 1
fi

if awk -v p="$OFFICE_MNT" '$2==p && $3=="cifs" {found=1} END{exit !found}' /proc/mounts; then
  echo "Schon CIFS auf $OFFICE_MNT — kein zweites Mount"
else
  if [[ -d "$OFFICE_MNT/abpe" ]]; then
    if [[ -z "$(ls -A "$OFFICE_MNT/abpe" 2>/dev/null)" ]]; then
      rmdir "$OFFICE_MNT/abpe" 2>/dev/null && echo "OK leeres $OFFICE_MNT/abpe entfernt"
    else
      echo "HINWEIS: $OFFICE_MNT/abpe ist nicht leer — CIFS-Mount verdeckt den lokalen Ordner bis umount"
    fi
  fi
  mkdir -p "$OFFICE_MNT"
  echo "mount -t cifs $TARGET $OFFICE_MNT -o $MP_OPTS"
  mount -t cifs "$TARGET" "$OFFICE_MNT" -o "$MP_OPTS"
  rc=$?
  if [[ "$rc" -ne 0 ]]; then
    echo "FAIL mount exit $rc — Share-Name prüfen (office/Office/O) oder Passwort"
    echo "Liste: smbclient -L //$NAS -U office"
    exit "$rc"
  fi
fi

echo
findmnt -T "$OFFICE_MNT" -o TARGET,SOURCE,FSTYPE
echo
echo "=== Testpfad ==="
ls -ld "$OFFICE_MNT/Berater" 2>&1 | head -3
ls -l "$FILE" 2>&1
echo
if [[ -f "$FILE" ]]; then
  echo "OK Datei sichtbar"
else
  echo "Mount ok, Datei noch nicht am erwarteten Relativpfad — ls -lb $OFFICE_MNT | head"
  ls -lb "$OFFICE_MNT" | head -25
fi

if grep -q "$OFFICE_MNT" /etc/fstab 2>/dev/null; then
  echo "fstab hat bereits $OFFICE_MNT"
else
  echo
  echo "Persistenz — Zeile nach Prüfung in /etc/fstab (nicht automatisch geschrieben):"
  if [[ -n "$CRED" && -f "$CRED" ]]; then
    echo "  $TARGET  $OFFICE_MNT  cifs  credentials=$CRED,vers=3.0,uid=0,gid=0,file_mode=0664,dir_mode=0775,iocharset=utf8,_netdev  0  0"
  else
    echo "  $TARGET  $OFFICE_MNT  cifs  username=office,vers=3.0,uid=0,gid=0,file_mode=0664,dir_mode=0775,iocharset=utf8,_netdev  0  0"
  fi
fi
