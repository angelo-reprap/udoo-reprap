"""
services/versioning.py
Versionierung fuer CVs – ausschliesslich DB-basiert (ConsultantDirectory).

Namensvetter-Logik:
  troschke_thomas      → suffix=0  (erster Eintrag, kein Suffix im Ordnernamen)
  troschke_thomas-2    → suffix=2
  troschke_thomas-3    → suffix=3  usw.
"""

import hashlib
import logging
import re
import uuid
from pathlib import Path
from typing import Dict, List, Tuple

from django.conf import settings
from django.db import IntegrityError, transaction

logger = logging.getLogger(__name__)


class VersionManager:
    """
    Verwaltet Verzeichnisnamen und Versionen ausschliesslich ueber die DB.
    Dateisystem wird nur benutzt um Verzeichnisse anzulegen – nie zum Nachschlagen.
    """

    DEFAULT_VERSION = '1.0.0.0'

    def __init__(self):
        # Basispfad fuer extrahierte Texte (debug=true)
        self.extracted_path = Path(settings.BASE_DIR) / 'data' / 'extracted'
        self.extracted_path.mkdir(parents=True, exist_ok=True)

    # ── Hilfsmethoden ────────────────────────────────────────────────────────

    @staticmethod
    def normalize_name(first_name: str, last_name: str, suffix: int = 0) -> str:
        """
        nachname_vorname           (suffix=0 → kein Suffix)
        nachname_vorname-2         (suffix=2)
        """
        parts = [p.lower().strip() for p in [last_name, first_name] if p and p.strip()]
        base  = "_".join(parts).replace(" ", "_")
        return base if suffix == 0 else f"{base}-{suffix}"

    @staticmethod
    def get_kuerzel(first_name: str, last_name: str) -> str:
        k = ""
        if first_name:
            k += first_name[0].lower()
        if last_name:
            k += last_name[0].lower()
        return k or "xx"

    @staticmethod
    def _parse_version(version: str) -> List[int]:
        try:
            return [int(x) for x in version.split('.')]
        except Exception:
            return [1, 0, 0, 0]

    @staticmethod
    def _version_to_str(parts: List[int]) -> str:
        return ".".join(str(p) for p in parts)

    # ── Verzeichnis-Logik (DB) ───────────────────────────────────────────────

    def get_or_create_directory(self, first_name: str, last_name: str) -> Tuple[str, bool]:
        """
        Gibt das Verzeichnis fuer diesen Namen zurueck.
        Falls noch keins existiert → neuen Eintrag anlegen.
        Falls bereits einer mit diesem Basisnamen existiert → naechsten
        freien Suffix verwenden (Namensvetter).

        Rueckgabe: (directory_name, is_new_person)
        """
        from apps.cv_extractor.models import ConsultantDirectory

        base_name = self.normalize_name(first_name, last_name, suffix=0)

        # Alle vorhandenen Eintraege mit diesem Basisnamen
        existing = list(
            ConsultantDirectory.objects.filter(
                normalized_name=base_name
            ).order_by('suffix')
        )

        if not existing:
            # Erste Person mit diesem Namen
            entry = ConsultantDirectory.objects.create(
                directory_name  = base_name,
                normalized_name = base_name,
                suffix          = 0,
                version         = self.DEFAULT_VERSION,
            )
            return entry.directory_name, True

        # Namensvetter → naechsten freien Suffix suchen
        used_suffixes = {e.suffix for e in existing}
        # Suffix 0 = erster, 2 = zweiter Namensvetter, 3 = dritter …
        next_suffix = 2
        while next_suffix in used_suffixes:
            next_suffix += 1

        dir_name = self.normalize_name(first_name, last_name, suffix=next_suffix)
        entry = ConsultantDirectory.objects.create(
            directory_name  = dir_name,
            normalized_name = base_name,
            suffix          = next_suffix,
            version         = self.DEFAULT_VERSION,
        )
        return entry.directory_name, True

    def get_existing_directory(self, first_name: str,
                               last_name: str) -> Tuple[str, bool]:
        """
        Prueft ob bereits eine Person mit diesem Namen in der DB existiert.
        Gibt (directory_name, found) zurueck.
        Wenn mehrere Eintraege → ersten (aeltesten) zurueckgeben.
        """
        from apps.cv_extractor.models import ConsultantDirectory

        base_name = self.normalize_name(first_name, last_name, suffix=0)
        entry = ConsultantDirectory.objects.filter(
            normalized_name=base_name
        ).order_by('suffix').first()

        if entry:
            return entry.directory_name, True
        return base_name, False

    # ── Versions-Logik (DB) ─────────────────────────────────────────────────

    def get_next_version_for_dir(self, consultant_dir: str) -> str:
        """
        Gibt naechste freie Version fuer ein Verzeichnis zurueck.
        Basiert auf ConsultantVersion in der DB.
        """
        from apps.cv_extractor.models import ConsultantVersion

        versions = list(
            ConsultantVersion.objects.filter(
                consultant_dir=consultant_dir
            ).values_list('version', flat=True)
        )

        if not versions:
            return self.DEFAULT_VERSION

        latest = max(versions, key=self._parse_version)
        parts  = self._parse_version(latest)
        parts[3] += 1
        return self._version_to_str(parts)

    # ── Haupt-API ────────────────────────────────────────────────────────────

    def get_next_version(self, first_name: str, last_name: str,
                         target_directory: str = "",
                         action_type: str = "new_version") -> Dict:
        """
        Vollstaendiger Lookup: Verzeichnis + naechste Version.
        Legt ConsultantVersion-Eintrag an um Version zu reservieren.

        Rueckgabe:
        {
            'version':         '1.0.0.1',
            'consultant_dir':  'troschke_thomas',
            'kuerzel':         'tt',
            'is_new_person':   True,
        }
        """
        kuerzel = self.get_kuerzel(first_name, last_name)

        # Vorgegebenes Verzeichnis direkt verwenden wenn es existiert
        if action_type == 'new_person' and target_directory:
            from apps.cv_extractor.models import ConsultantDirectory
            # Existiert target_directory bereits? → direkt verwenden
            existing_entry = ConsultantDirectory.objects.filter(
                directory_name=target_directory
            ).first()
            if existing_entry:
                consultant_dir = existing_entry.directory_name
                is_new = False
                logger.info(f"Bestehendes Verzeichnis verwendet: {consultant_dir}")
            else:
                # Neues Verzeichnis anlegen
                base_name = self.normalize_name(first_name, last_name, suffix=0)
                existing = ConsultantDirectory.objects.filter(
                    normalized_name=base_name
                ).order_by('suffix')
                used_suffixes = {e.suffix for e in existing}
                import re as _re
                m = _re.search(r'-(\d+)$', target_directory)
                requested_suffix = int(m.group(1)) if m else 0
                suffix = requested_suffix
                while suffix in used_suffixes:
                    suffix += 1
                dir_name = self.normalize_name(first_name, last_name, suffix=suffix)
                ConsultantDirectory.objects.get_or_create(
                    directory_name=dir_name,
                    defaults={
                        'normalized_name': base_name,
                        'suffix':          suffix,
                        'version':         self.DEFAULT_VERSION,
                    }
                )
                consultant_dir = dir_name
                is_new = True
                logger.info(f"Neues Verzeichnis angelegt: {consultant_dir} (suffix={suffix})")
        else:
            # Erst pruefen ob Person schon existiert
            existing_dir, found = self.get_existing_directory(first_name, last_name)
            if found:
                consultant_dir = existing_dir
                is_new = False
            else:
                consultant_dir, is_new = self.get_or_create_directory(first_name, last_name)

        version = self.get_next_version_for_dir(consultant_dir)

        # Version in ConsultantVersion reservieren.
        # Platzhalter-AID muss global unique sein (aid UNIQUE) — der alte
        # Suffix dir[-6:] kollidierte z.B. bei allen *_thomas + Kürzel tb
        # → AID-tb_1.0.0.0_thomas. Hash aus dir+version ist stabil & eindeutig.
        # Echte AID wird später von pipeline / main_db_importer gesetzt.
        self._reserve_version(consultant_dir, version)
        logger.info(f"Version reserviert: {consultant_dir} v{version}")

        # Verzeichnis auf Dateisystem anlegen (fuer debug=true Exporte)
        target = self.extracted_path / consultant_dir
        target.mkdir(parents=True, exist_ok=True)

        return {
            'version':        version,
            'consultant_dir': consultant_dir,
            'kuerzel':        kuerzel,
            'is_new_person':  is_new,
        }

    @staticmethod
    def _placeholder_aid(consultant_dir: str, version: str) -> str:
        """Stable unique placeholder (≤50 chars) for ConsultantVersion.aid."""
        digest = hashlib.sha1(
            f"{consultant_dir}|{version}".encode('utf-8')
        ).hexdigest()[:16]
        # AID-tmp- (8) + 16 hex = 24 chars
        return f"AID-tmp-{digest}"

    def _reserve_version(self, consultant_dir: str, version: str) -> None:
        """
        Reserve (consultant_dir, version). Tolerates:
        - already reserved (same dir+version)
        - leftover aid collision from old placeholder scheme
        - concurrent get_or_create races
        """
        from apps.cv_extractor.models import ConsultantVersion

        existing = ConsultantVersion.objects.filter(
            consultant_dir=consultant_dir,
            version=version,
        ).first()
        if existing:
            return

        placeholder_aid = self._placeholder_aid(consultant_dir, version)

        try:
            with transaction.atomic():
                ConsultantVersion.objects.get_or_create(
                    consultant_dir=consultant_dir,
                    version=version,
                    defaults={'aid': placeholder_aid},
                )
            return
        except IntegrityError:
            # Either race on (dir,version) or unique aid clash.
            existing = ConsultantVersion.objects.filter(
                consultant_dir=consultant_dir,
                version=version,
            ).first()
            if existing:
                return

        # Aid collision with leftover row for another dir — use random aid.
        for _ in range(5):
            alt_aid = f"AID-tmp-{uuid.uuid4().hex[:16]}"
            try:
                with transaction.atomic():
                    ConsultantVersion.objects.create(
                        consultant_dir=consultant_dir,
                        version=version,
                        aid=alt_aid,
                    )
                logger.warning(
                    "Version-Reservierung mit Fallback-AID (%s) für %s v%s "
                    "(Platzhalter-Kollision)",
                    alt_aid, consultant_dir, version,
                )
                return
            except IntegrityError:
                again = ConsultantVersion.objects.filter(
                    consultant_dir=consultant_dir,
                    version=version,
                ).first()
                if again:
                    return
                continue

        raise IntegrityError(
            f"ConsultantVersion konnte nicht reserviert werden: "
            f"{consultant_dir} v{version}"
        )

    def bind_real_aid(self, consultant_dir: str, version: str, aid: str) -> None:
        """Replace placeholder AID with the real consultant AID."""
        from apps.cv_extractor.models import ConsultantVersion

        try:
            with transaction.atomic():
                updated = ConsultantVersion.objects.filter(
                    consultant_dir=consultant_dir,
                    version=version,
                ).update(aid=aid)
                if updated:
                    return
                ConsultantVersion.objects.update_or_create(
                    aid=aid,
                    defaults={
                        'consultant_dir': consultant_dir,
                        'version': version,
                    },
                )
        except IntegrityError:
            # Real AID already owned by another row — retarget that row
            ConsultantVersion.objects.filter(aid=aid).update(
                consultant_dir=consultant_dir,
                version=version,
            )
            ConsultantVersion.objects.filter(
                consultant_dir=consultant_dir,
                version=version,
            ).exclude(aid=aid).delete()

    def list_persons_by_name(self, first_name: str,
                             last_name: str) -> List[Dict]:
        """
        Gibt alle Personen mit diesem Nachnamen+Vornamen aus der DB zurueck.
        Verwendet von check_duplicate_api.
        """
        from apps.cv_extractor.models import ConsultantDirectory, Consultant

        base_name = self.normalize_name(first_name, last_name, suffix=0)
        dirs      = ConsultantDirectory.objects.filter(normalized_name=base_name)

        result = []
        for d in dirs:
            # Zugehoerigen Consultant suchen
            consultant = Consultant.objects.filter(
                consultant_dir=d.directory_name
            ).order_by('-created_at').first()

            result.append({
                'directory':       d.directory_name,
                'suffix':          d.suffix,
                'latest_version':  consultant.version if consultant else d.version,
                'aid':             consultant.aid     if consultant else '',
                'consultant_id':   consultant.id      if consultant else None,
            })
        return result


# Singleton
version_manager = VersionManager()
