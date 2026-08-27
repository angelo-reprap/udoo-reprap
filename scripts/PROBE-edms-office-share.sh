#!/usr/bin/env bash
# Walk O:-Pfad auf ucs5. Leerzeichen und '&' sind in SINGLE QUOTES harmlos.
# Als root ODER als Django-User (www-data) ausführen — Django sieht nur, was
# sein User lesen darf.
#
#   bash scripts/PROBE-edms-office-share.sh
#
set +e
OFFICE="${DMS_OFFICE_MOUNT:-/mnt/office}"
PUBLIC="${DMS_PUBLIC_MOUNT:-/mnt/public}"
FILE='/mnt/office/Berater/Berater aktive & passive/passive/wollschlaeger_andreas/Rechnungen/Rechnung Hotel Schlossberg Wolli_Dezember2014.pdf'

echo "whoami=$(whoami) uid=$(id -u) gid=$(id -g)"
echo "FILE=$FILE"
echo
echo "=== Mounts ==="
mount | grep -Ei 'office|public|cifs|nfs|smb' || echo "(kein cifs/nfs in mount)"
echo
ls -ld "$OFFICE" "$PUBLIC" 2>&1
echo

walk="$OFFICE"
printf '%s\n' 'Berater' 'Berater aktive & passive' 'passive' 'wollschlaeger_andreas' 'Rechnungen' 'Rechnung Hotel Schlossberg Wolli_Dezember2014.pdf' | while IFS= read -r part; do
  echo "======== $walk ========"
  if [[ ! -e "$walk" ]]; then
    echo "FEHLT"
    parent=$(dirname "$walk")
    echo "ls -lb parent:"
    ls -lb "$parent" 2>&1 | head -40
    break
  fi
  ls -ld "$walk" 2>&1
  if [[ -d "$walk" ]]; then
    echo "Inhalt (erste 25, roh inkl. Sonderzeichen):"
    ls -lb "$walk" 2>&1 | head -25
  fi
  echo
  walk="$walk/$part"
done

echo "======== Zieldatei ========"
if [[ -f "$FILE" ]]; then
  ls -l "$FILE"
  echo -n "readable: "; [[ -r "$FILE" ]] && echo YES || echo NO
else
  echo "nicht gefunden als -f"
fi

echo
echo "=== Alternativen (ohne fuehrendes Berater/ bzw. unter abpe/) ==="
for cand in \
  '/mnt/office/Berater aktive & passive/passive/wollschlaeger_andreas/Rechnungen/Rechnung Hotel Schlossberg Wolli_Dezember2014.pdf' \
  '/mnt/office/abpe/Berater/Berater aktive & passive/passive/wollschlaeger_andreas/Rechnungen/Rechnung Hotel Schlossberg Wolli_Dezember2014.pdf'
 do
  echo -n "$cand  ->  "
  if [[ -f "$cand" ]]; then echo "DATEI"; elif [[ -e "$cand" ]]; then echo "existiert, kein file"; else echo "fehlt"; fi
done

echo
echo "=== Dateiname ab letztem existierenden Ordner (maxdepth 4) ==="
cur="$OFFICE"
last="$OFFICE"
for part in 'Berater' 'Berater aktive & passive' 'passive' 'wollschlaeger_andreas' 'Rechnungen'; do
  nxt="$cur/$part"
  if [[ -d "$nxt" ]]; then last="$nxt"; cur="$nxt"; else break; fi
done
echo "suche unter: $last"
find "$last" -maxdepth 4 -iname '*Schlossberg*Wolli*' 2>/dev/null | head -20
echo
echo "=== Django-User (falls gunicorn) ==="
ps -eo user,comm,args 2>/dev/null | grep -Ei 'gunicorn|uwsgi|abpe-django' | grep -v grep | head -5
