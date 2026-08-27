# -*- coding: utf-8 -*-
"""
apps/abpe_edms/services/scanner.py
================================================================================
Scanner: gleicht das Dateisystem (Samba-Mounts) mit der DB ab.
Leitidee: "DER ORDNER (das Dateisystem) IST DIE QUELLE." Die DB ist dessen
durchsuchbares, korrigierbares Abbild. Bei Widerspruch gewinnt das Dateisystem
für Datei-Existenz/Ort; bei OWNER gewinnt ein bereits BESTÄTIGTER DB-Owner.

Owner-Ableitung (drei Bäume, am Pfad unterschieden):
  Berater/...aktive|passive/{nachname_vorname}/   -> CrmContact  (bestehend)
  Berater/AID_profile/{buchstabe}/{nachname_vorname}/ -> CrmContact
  Kunde/...aktive|passiv/{firmenname}/            -> CrmAccount  (NEU, zweistufig)
  Kunde/...Rechnungen/...                          -> abcona-Self (NEU)

Firmen-Match zweistufig:
  - exact/normalized eindeutig  -> sicherer Owner (is_suggestion=False)
  - nur substring/mehrdeutig    -> VORSCHLAG (is_suggestion=True, needs_review)
  - nichts                      -> Posteingang (kein Owner, name_hint)

Schalter (über dms_scan):
  --berater / --kunde / --administration / --alle : welche Bäume
  --update : bekannte Dateien mitnehmen und Owner NACHTRAGEN/korrigieren
             (nicht nur neue Dateien wie im Grundmodus)
  --execute : echt schreiben (sonst dry-run)
  --limit N : nur N Dateien
================================================================================
"""

import hashlib
import os
import re
import time
import unicodedata

from django.conf import settings
from django.utils import timezone

from apps.abpe_crm.models import CrmContact, CrmAccount
from ..models import (
    CrmDocument, CrmDocumentOwner, CrmDocumentVersion,
    DmsDocType, DmsSyncRun, DmsDocumentEvent,
    StorageVolume, OwnerType, OwnerRole, EventType, DocStatus, DocSource,
)

# ---------------------------------------------------------------------------
# abcona-Self (Administration / Rechnungen)
# ---------------------------------------------------------------------------
ABCONA_CRM_ID = getattr(settings, "DMS_ABCONA_CRM_ID",
                        "51691c10-97fd-2e65-75ef-4b1eb782b729")

# ---------------------------------------------------------------------------
# Scan-Pfade
# ---------------------------------------------------------------------------
DEFAULT_SCAN_PATHS = [
    (StorageVolume.OFFICE, "/mnt/office/Berater"),
    (StorageVolume.OFFICE, "/mnt/office/Kunde"),
    (StorageVolume.PUBLIC, "/mnt/public/Berater/AID_profile"),
]
SCAN_PATHS = getattr(settings, "DMS_SCAN_PATHS", DEFAULT_SCAN_PATHS)

_VOLUME_MOUNT = {
    StorageVolume.OFFICE: "/mnt/office",
    StorageVolume.PUBLIC: "/mnt/public",
}

# Müll-Filter
_IGNORE_EXT = set(getattr(settings, "DMS_IGNORE_EXTENSIONS", [
    ".exe", ".url", ".lnk", ".llcxy", ".tmp", ".db", ".part", ".ini", ".bat",
]))
_IGNORE_PREFIX = ("__", "~$", ".")

_DEFAULT_IGNORE_DIRS = {
    "mustervorlagen", "vorlagen", "vorlage", "templates", "template",
    "muster", "_archiv", "archiv_alt", "papierkorb", "trash", "temp", "tmp",
    "ordnerstruktur", "lieferantennummern", "neuer ordner", "archiv",
}
_IGNORE_DIRS = set(getattr(settings, "DMS_IGNORE_DIRS", _DEFAULT_IGNORE_DIRS))

_BLACKLIST_PATHS = [p.lower() for p in getattr(settings, "DMS_BLACKLIST_PATHS", [])]


def _path_has_ignored_dir(abs_path):
    parts = [p.lower() for p in abs_path.split(os.sep)]
    return any(p in _IGNORE_DIRS for p in parts)


def _is_blacklisted(abs_path):
    low = abs_path.lower()
    return any(frag in low for frag in _BLACKLIST_PATHS)


def _is_ignored(filename):
    low = filename.lower()
    _, ext = os.path.splitext(low)
    if ext in _IGNORE_EXT:
        return True
    if filename.startswith(_IGNORE_PREFIX):
        return True
    return False


# ===========================================================================
# NORMALISIERUNG
# ===========================================================================

def _slug(v):
    """Für Personennamen: ae/oe/ue/ss, ascii, lower, _-getrennt."""
    if not v:
        return ""
    r = {"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss", "Ä": "ae", "Ö": "oe", "Ü": "ue"}
    for k, x in r.items():
        v = v.replace(k, x)
    v = unicodedata.normalize("NFKD", v).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "_", v).strip("_")


# Rechtsform-/Füllwörter, die beim Firmenvergleich rausfliegen.
_COMPANY_STOPWORDS = {
    "gmbh", "ag", "kg", "mbh", "co", "ltd", "se", "ohg", "ug", "und", "u",
    "group", "holding", "deutschland", "service", "services", "consulting", "it",
}


def _norm_company(v):
    """Firmennamen hart normalisieren: Umlaute, Rechtsformen/Füllwörter raus,
    dann alle Nicht-Alphanumerischen entfernen. 'PIRACON GmbH' -> 'piracon'."""
    if not v:
        return ""
    r = {"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"}
    for k, x in r.items():
        v = v.replace(k, x)
    v = unicodedata.normalize("NFKD", v).encode("ascii", "ignore").decode().lower()
    # Wörter splitten, Stopwörter entfernen
    words = re.split(r"[^a-z0-9]+", v)
    words = [w for w in words if w and w not in _COMPANY_STOPWORDS]
    return "".join(words)


# ===========================================================================
# CONTACT-MATCH (Berater) — bestehend
# ===========================================================================

_NAME_DIR_RE = re.compile(r"^[a-zäöüß]+_[a-zäöüß]", re.IGNORECASE)

_NOT_A_SURNAME = {
    "sub", "arbeitnehmer", "rahmenvertrag", "muster", "vorlage", "vorlagen",
    "zeitnachweis", "stundenzettel", "stundennachweis", "rechnung", "angebot",
    "vertrag", "kunde", "kunden", "berater", "anschreiben", "kopie", "aktuelle",
    "ausschreibung", "anfrage", "anfragen", "partner", "schriftverkehr",
    "it", "aid", "tron", "profil", "info", "test", "neu", "alt", "final",
}


def _extract_name_from_path(abs_path):
    parts = abs_path.split(os.sep)
    for seg in reversed(parts[:-1]):
        if "_" in seg and _NAME_DIR_RE.match(seg):
            bits = seg.split("_")
            nach = bits[0]
            if nach.lower() in _NOT_A_SURNAME:
                continue
            vor = "_".join(bits[1:]) if len(bits) > 1 else ""
            return nach, vor
    return None, None


def resolve_owner_crm_id(abs_path):
    """Berater: aus dem Pfad EINDEUTIG einen CrmContact.
    (crm_id, hint) bei 1 Treffer, (None, hint) bei 0/>1, (None, None) ohne Namen."""
    nach, vor = _extract_name_from_path(abs_path)
    if not nach:
        return None, None
    name_hint = f"{nach}_{vor}".strip("_")
    cands = list(CrmContact.objects.filter(last_name__iexact=nach)[:50])
    if vor:
        vslug = _slug(vor)
        cands = [c for c in cands if _slug(c.first_name or "") == vslug]
    if len(cands) == 1:
        return cands[0].crm_id, name_hint
    return None, name_hint


# ===========================================================================
# ACCOUNT-MATCH (Kunde) — NEU, zweistufig
# ===========================================================================

# wird beim ersten Bedarf gefüllt: {norm_name: [(crm_id, name), ...]}
_ACCOUNT_INDEX = None


def _build_account_index():
    global _ACCOUNT_INDEX
    if _ACCOUNT_INDEX is not None:
        return _ACCOUNT_INDEX
    idx = {}
    for a in CrmAccount.objects.exclude(name__isnull=True).only("crm_id", "name"):
        n = _norm_company(a.name)
        if n:
            idx.setdefault(n, []).append((a.crm_id, a.name))
    _ACCOUNT_INDEX = idx
    return idx


# Ordnernamen im Kunde-Baum, die KEINE Firma sind.
_KUNDE_NOT_A_COMPANY = {
    "archiv", "muster", "neuer ordner", "ordnerstruktur", "lieferantennummern",
    "kopfklinik", "rechnungen",
}


def _extract_company_from_path(rel_path):
    """Aus 'Kunde/Kunden_aktive & Passiv/aktive/PiraCon/datei.pdf' -> 'PiraCon'.
    Erwartet den Firmenordner direkt unter aktive|passiv. None wenn nicht dort."""
    parts = rel_path.split("/")
    # Suche das Segment nach 'aktive' oder 'passiv'
    for i, seg in enumerate(parts[:-1]):
        if seg.lower() in ("aktive", "passiv", "passive") and i + 1 < len(parts) - 0:
            firma = parts[i + 1]
            if firma.lower() in _KUNDE_NOT_A_COMPANY:
                return None
            return firma
    return None


def resolve_account_crm_id(rel_path):
    """Kunde: Firmenordner -> CrmAccount, zweistufig.
    Rückgabe: (crm_id, name_hint, is_suggestion, match_source)
      - sicherer Treffer:  (crm_id, name, False, 'exact'/'normalized')
      - Vorschlag:         (crm_id, name, True,  'substring')
      - nichts:            (None,   hint, False, '')
    """
    firma = _extract_company_from_path(rel_path)
    if not firma:
        return None, None, False, ""
    name_hint = firma
    n = _norm_company(firma)
    if not n:
        return None, name_hint, False, ""

    idx = _build_account_index()

    # Stufe 1: exakter normalisierter Treffer, eindeutig
    if n in idx and len(idx[n]) == 1:
        cid, name = idx[n][0]
        return cid, name, False, "normalized"

    # mehrdeutig exakt -> Vorschlag (ersten nehmen, aber unsicher)
    if n in idx and len(idx[n]) > 1:
        cid, name = idx[n][0]
        return cid, name, True, "substring"

    # Stufe 2: Teilstring in beide Richtungen -> Vorschlag
    treffer = []
    for kn, lst in idx.items():
        if kn and (n in kn or kn in n) and abs(len(kn) - len(n)) <= max(4, len(n)//2):
            treffer.extend(lst)
    if len(treffer) >= 1:
        cid, name = treffer[0]
        return cid, name, True, "substring"

    return None, name_hint, False, ""


# ===========================================================================
# DocType-Heuristik
# ===========================================================================

def guess_doctype(abs_path, filename):
    low = (abs_path + "/" + filename).lower()
    if "stundenzettel" in low or "stundennachweis" in low or "timesheet" in low:
        return "leistungsnachweis"
    if "rechnung" in low or "invoice" in low:
        return "rechnung"
    if "vertrag" in low or "contract" in low:
        return "vertrag"
    if "angebot" in low or "ausschreibung" in low:
        return "angebot"
    if "aid" in filename.lower() or "it-profil" in low or "profil" in low:
        return "cv"
    return "sonstiges"


# ===========================================================================
# Hash
# ===========================================================================

def _sha256(abs_path, chunk=1024 * 256):
    h = hashlib.sha256()
    with open(abs_path, "rb") as f:
        for blk in iter(lambda: f.read(chunk), b""):
            h.update(blk)
    return h.hexdigest()


# ===========================================================================
# Owner-Auflösung nach Baum (Weiche)
# ===========================================================================

def resolve_any_owner(abs_path, rel_path, do_berater, do_kunde, do_admin):
    """Zentrale Weiche: bestimmt anhand des Pfades den passenden Owner.
    Rückgabe: dict oder None
       {crm_id, owner_type, role, name_hint, is_suggestion, match_source}
    """
    low = rel_path.lower()

    # PRIORITÄT (einfache Regel): 1. Contact  2. Account  3. abcona-Auffang
    #
    # 1. CONTACT (Berater): Personenordner nachname_vorname
    if do_berater:
        cid, hint = resolve_owner_crm_id(abs_path)
        if cid:
            return {
                "crm_id": cid, "owner_type": OwnerType.CONTACT,
                "role": OwnerRole.PRIMAER, "name_hint": hint,
                "is_suggestion": False, "match_source": "path",
            }

    # 2. ACCOUNT (Kunde): Firmenordner im Kunde-Baum
    if do_kunde and low.startswith("kunde/"):
        cid, name, sugg, src = resolve_account_crm_id(rel_path)
        if cid:
            return {
                "crm_id": cid, "owner_type": OwnerType.ACCOUNT,
                "role": OwnerRole.KUNDE, "name_hint": name,
                "is_suggestion": sugg, "match_source": src,
            }

    # 3. abcona-AUFFANG: NUR fuer echte herrenlose Dokumente im Kunde-Baum
    #    OHNE erkennbaren Firmenordner (lose Dateien, Schriftverkehr direkt
    #    unter Kunde/, zentrale Rechnungen). Steht ein Firmenordner im Pfad
    #    (z.B. DIT, EADS), der aber KEINE CRM-Firma matcht, wird das Dokument
    #    UEBERSPRUNGEN -> Posteingang. So kann die Firma spaeter im CRM
    #    angelegt / der Ordner umbenannt werden, und ein Rescan ordnet sauber
    #    zu (kein abcona-Owner, der den Konflikt-Schutz blockiert).
    if do_admin and low.startswith("kunde/"):
        firma = _extract_company_from_path(rel_path)
        if firma:
            # erkennbarer Firmenordner, aber kein CRM-Treffer -> NICHT abcona
            return None
        return {
            "crm_id": ABCONA_CRM_ID, "owner_type": OwnerType.ACCOUNT,
            "role": OwnerRole.KUNDE, "name_hint": "abcona (Auffang)",
            "is_suggestion": False, "match_source": "fallback",
        }

    # nichts getroffen -> Posteingang (kein Owner)
    return None


# ===========================================================================
# Stats
# ===========================================================================

class ScanStats:
    def __init__(self):
        self.seen = 0
        self.ignored = 0
        self.new = 0
        self.changed = 0
        self.unchanged = 0
        self.owner_resolved = 0
        self.owner_added = 0       # --update: Owner nachgetragen
        self.owner_suggested = 0   # Vorschläge markiert
        self.owner_conflict = 0    # bestätigter Owner != Pfad -> nur geloggt
        self.to_inbox = 0
        self.errors = 0

    def as_dict(self):
        return {
            "seen": self.seen, "ignored": self.ignored, "new": self.new,
            "changed": self.changed, "unchanged": self.unchanged,
            "owner_resolved": self.owner_resolved, "owner_added": self.owner_added,
            "owner_suggested": self.owner_suggested,
            "owner_conflict": self.owner_conflict,
            "to_inbox": self.to_inbox, "errors": self.errors,
        }


def _rel_to_mount(volume, abs_path):
    mount = _VOLUME_MOUNT[volume]
    return os.path.relpath(abs_path, mount)


# ===========================================================================
# Kern: scan_all
# ===========================================================================

def scan_all(dry_run=True, limit=None, logger=print,
             do_berater=True, do_kunde=True, do_admin=True, update=False):
    """Durchläuft SCAN_PATHS. dry_run=True schreibt NICHTS.
    update=True: bekannte Dateien werden mitgenommen, um fehlende/unsichere
    Owner NACHZUTRAGEN (nicht nur neue Dateien anlegen)."""
    stats = ScanStats()
    started = timezone.now()
    t0 = time.time()

    doctypes = {d.key: d for d in DmsDocType.objects.all()}

    logger(f"  Bäume: berater={do_berater} kunde={do_kunde} admin={do_admin} "
           f"| update={update}")

    for volume, base in SCAN_PATHS:
        if not os.path.isdir(base):
            logger(f"  ⚠ Pfad fehlt, übersprungen: {base}")
            continue
        logger(f"  → scanne {base} (volume={volume}) …")

        for root, dirs, files in os.walk(base):
            dirs[:] = [d for d in dirs if d.lower() not in _IGNORE_DIRS
                       and not d.startswith(("__", "."))]
            for fname in files:
                if limit and stats.seen >= limit:
                    logger(f"  (limit {limit} erreicht, Abbruch)")
                    return _finish(stats, started, t0, dry_run, logger)

                stats.seen += 1
                if _is_ignored(fname):
                    stats.ignored += 1
                    continue

                abs_path = os.path.join(root, fname)
                if _BLACKLIST_PATHS and _is_blacklisted(abs_path):
                    stats.ignored += 1
                    continue

                rel_path = _rel_to_mount(volume, abs_path)

                try:
                    st = os.stat(abs_path)
                except OSError:
                    stats.errors += 1
                    continue

                size = st.st_size
                mtime = st.st_mtime

                existing = CrmDocumentVersion.objects.filter(
                    volume=volume, relative_path=rel_path
                ).select_related("document").first()

                # ---------- BEKANNTE Datei ----------
                if existing:
                    if existing.size_bytes == size:
                        stats.unchanged += 1
                        # --update: fehlenden/unsicheren Owner nachtragen
                        if update:
                            _maybe_update_owner(
                                existing.document, abs_path, rel_path,
                                do_berater, do_kunde, do_admin,
                                dry_run, stats, logger)
                        continue
                    else:
                        stats.changed += 1
                        if not dry_run:
                            checksum = _sha256(abs_path)
                            if checksum != existing.checksum:
                                _record_change(existing, size, checksum)
                        if update:
                            _maybe_update_owner(
                                existing.document, abs_path, rel_path,
                                do_berater, do_kunde, do_admin,
                                dry_run, stats, logger)
                        continue

                # ---------- NEUE Datei ----------
                stats.new += 1
                owner = resolve_any_owner(abs_path, rel_path,
                                          do_berater, do_kunde, do_admin)
                has_owner = bool(owner and owner.get("crm_id"))
                if has_owner:
                    if owner["is_suggestion"]:
                        stats.owner_suggested += 1
                    else:
                        stats.owner_resolved += 1
                else:
                    stats.to_inbox += 1

                if dry_run:
                    if stats.new <= 20:
                        if has_owner:
                            tag = "VORSCHLAG" if owner["is_suggestion"] else "OWNER"
                            owner_txt = f"{tag}={owner['name_hint']} ({owner['match_source']})"
                        else:
                            hint = owner["name_hint"] if owner else None
                            owner_txt = f"INBOX (hint={hint})" if hint else "INBOX"
                        logger(f"      NEU: {rel_path[:65]} | {owner_txt}")
                    continue

                try:
                    _create_document(volume, abs_path, rel_path, fname, size,
                                     owner, doctypes, mtime)
                except Exception as exc:
                    stats.errors += 1
                    logger(f"      ✗ Fehler bei {rel_path}: {exc}")

    return _finish(stats, started, t0, dry_run, logger)


def _finish(stats, started, t0, dry_run, logger):
    dur = round(time.time() - t0, 1)
    logger(f"\n  Ergebnis ({'DRY-RUN' if dry_run else 'ECHT'}, {dur}s): {stats.as_dict()}")
    if not dry_run:
        DmsSyncRun.objects.create(
            started_at=started,
            finished_at=timezone.now(),
            status="ok" if stats.errors == 0 else "mit_fehlern",
            files_seen=stats.seen,
            files_new=stats.new,
            files_updated=stats.changed,
            files_removed=0,
            documents_indexed=stats.new,
            triggered_by="dms_scan",
            message=str(stats.as_dict()),
        )
    return stats


# ===========================================================================
# --update: Owner nachtragen / korrigieren (Schutz bestätigter Owner)
# ===========================================================================

def _maybe_update_owner(doc, abs_path, rel_path,
                        do_berater, do_kunde, do_admin,
                        dry_run, stats, logger):
    """Für eine BEKANNTE Datei: Owner nachtragen, wenn keiner da ist, oder
    einen VORSCHLAG durch besseren Match ersetzen. Bestätigte Owner
    (is_suggestion=False) werden NIE überschrieben — nur Konflikt geloggt."""
    owner = resolve_any_owner(abs_path, rel_path, do_berater, do_kunde, do_admin)
    if not owner or not owner.get("crm_id"):
        return  # kein ableitbarer Owner -> nichts tun

    existing_owners = list(doc.owners.all())

    # Gibt es bereits genau diesen Owner?
    same = [o for o in existing_owners
            if o.owner_crm_id == owner["crm_id"] and o.owner_type == owner["owner_type"]]
    if same:
        return  # schon korrekt gesetzt

    # Gibt es einen BESTÄTIGTEN Owner (nicht Vorschlag)?
    confirmed = [o for o in existing_owners if not o.is_suggestion]
    if confirmed:
        # Wahrheit bleibt — nur melden, wenn der Pfad etwas anderes sagt
        stats.owner_conflict += 1
        if logger and stats.owner_conflict <= 20:
            have = ", ".join(f"{o.owner_type}:{o.owner_crm_id[:8]}" for o in confirmed)
            logger(f"      ⚠ Konflikt {rel_path[:55]}: Pfad→{owner['name_hint']} "
                   f"| gesetzt: {have} (bleibt)")
        return

    # Nur Vorschläge (oder gar nichts) vorhanden -> ersetzen/ergänzen
    if dry_run:
        tag = "VORSCHLAG" if owner["is_suggestion"] else "OWNER"
        stats.owner_added += 1
        if stats.owner_added <= 25:
            logger(f"      +{tag} {rel_path[:55]} → {owner['name_hint']} "
                   f"({owner['match_source']})")
        return

    # alte Vorschläge entfernen, neuen setzen
    doc.owners.filter(is_suggestion=True).delete()
    CrmDocumentOwner.objects.create(
        document=doc,
        owner_crm_id=owner["crm_id"],
        owner_type=owner["owner_type"],
        role=owner["role"],
        is_primary=not owner["is_suggestion"],
        is_suggestion=owner["is_suggestion"],
        match_source=owner["match_source"],
    )
    stats.owner_added += 1
    if owner["is_suggestion"]:
        stats.owner_suggested += 1
        doc.needs_review = True
        doc.save(update_fields=["needs_review"])


# ===========================================================================
# DB-Schreiben (neue Dokumente)
# ===========================================================================

def _mime(fname):
    import mimetypes
    mt, _ = mimetypes.guess_type(fname)
    return mt or "application/octet-stream"


def _create_document(volume, abs_path, rel_path, fname, size,
                     owner, doctypes, mtime=None):
    dt_key = guess_doctype(os.path.dirname(abs_path), fname)
    doctype = doctypes.get(dt_key) or doctypes.get("sonstiges")
    title = os.path.splitext(fname)[0]

    has_owner = bool(owner and owner.get("crm_id"))
    is_sugg = bool(owner and owner.get("is_suggestion"))
    name_hint = owner.get("name_hint") if owner else None
    # needs_review, wenn kein sicherer Owner
    needs_review = (not has_owner) or is_sugg

    doc_date = None
    if mtime:
        import datetime as _dt
        doc_date = _dt.date.fromtimestamp(mtime)

    desc = ""
    if needs_review and name_hint:
        prefix = "Kunde-Vorschlag" if is_sugg else "Owner-Hinweis"
        desc = f"[Scanner] {prefix}: {name_hint}"

    doc = CrmDocument.objects.create(
        title=title[:255],
        doctype=doctype,
        status=DocStatus.GUELTIG,
        needs_review=needs_review,
        source=DocSource.GESCANNT,
        document_date=doc_date,
        description=desc,
    )

    if has_owner:
        CrmDocumentOwner.objects.create(
            document=doc,
            owner_crm_id=owner["crm_id"],
            owner_type=owner["owner_type"],
            role=owner["role"],
            is_primary=not is_sugg,
            is_suggestion=is_sugg,
            match_source=owner["match_source"],
        )

    checksum = _sha256(abs_path)
    CrmDocumentVersion.objects.create(
        document=doc,
        version_no=1,
        volume=volume,
        relative_path=rel_path,
        filename=fname,
        mimetype=_mime(fname),
        size_bytes=size,
        checksum=checksum,
        checksum_algo="sha256",
        is_active=True,
        comment="vom Scanner erfasst",
        source_path_original=abs_path,
    )

    DmsDocumentEvent.objects.create(
        document=doc,
        document_uuid=doc.uuid,
        event_type=EventType.ERSTELLT,
        actor_label="scanner",
        detail={"relative_path": rel_path, "owner_resolved": has_owner,
                "is_suggestion": is_sugg, "name_hint": name_hint,
                "match_source": owner.get("match_source") if owner else "",
                "doctype": dt_key},
    )


def _record_change(existing_version, new_size, new_checksum):
    existing_version.size_bytes = new_size
    existing_version.checksum = new_checksum
    existing_version.save(update_fields=["size_bytes", "checksum"])
    DmsDocumentEvent.objects.create(
        document=existing_version.document,
        document_uuid=existing_version.document.uuid,
        event_type=EventType.VERSION_NEU,
        actor_label="scanner",
        detail={"relative_path": existing_version.relative_path,
                "new_size": new_size, "note": "Datei auf Share geändert"},
    )

