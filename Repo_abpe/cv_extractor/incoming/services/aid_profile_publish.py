"""
aid_profile_publish.py — Neue CV-Outputs nach /mnt/public/Berater/AID_profile/…/neu/cv/

Zielstruktur (wie Archiv, aber Unterordner neu/cv):
  /mnt/public/Berater/AID_profile/ttt/troschke_thomas/neu/cv/AID-tt_1.2.4.2.pdf
  /mnt/public/Berater/AID_profile/ttt/troschke_thomas/neu/cv/AID-tt_1.2.4.2.docx
  /mnt/public/Berater/AID_profile/ttt/troschke_thomas/neu/cv/AID-tt_1.2.4.2.html

Rechte: Verzeichnisse 0777, Dateien 0666 (lesen+schreiben für alle).
chown optional via settings.json → aid_profile.chown_user / chown_group.

Kein Crash wenn Share fehlt — nur Warning.
"""
from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Optional

from django.conf import settings

logger = logging.getLogger(__name__)

_DEFAULT_ROOTS = (
    '/mnt/public/Berater/AID_profile',
    '/var/share/public/Berater/AID_profile',
)


def _cfg() -> dict:
    try:
        path = os.path.join(settings.BASE_DIR, 'settings.json')
        with open(path, encoding='utf-8') as f:
            return (json.load(f).get('aid_profile') or {})
    except Exception:
        return {}


def resolve_aid_profile_root() -> Optional[Path]:
    """Ersten existierenden (oder anlegbaren) Root wählen."""
    cfg = _cfg()
    candidates = []
    if cfg.get('root'):
        candidates.append(cfg['root'])
    candidates.extend(_DEFAULT_ROOTS)
    env = os.environ.get('AID_PROFILE_ROOT', '').strip()
    if env:
        candidates.insert(0, env)

    for raw in candidates:
        p = Path(raw)
        try:
            if p.exists() and p.is_dir():
                return p
            # Root anlegen wenn Parent existiert (z.B. /mnt/public/Berater)
            if p.parent.exists():
                p.mkdir(parents=True, exist_ok=True)
                _chmod_path(p, is_dir=True)
                return p
        except OSError as e:
            logger.warning(f'AID_profile Root nicht nutzbar ({p}): {e}')
    return None


def letter_bucket(consultant_dir: str, last_name: str = '') -> str:
    """troschke_thomas / Troschke → ttt (wie Archiv aaa/bbb/…).

    Prefer consultant_dir (`nachname_vorname`): last_name allein kann bei
    vertauschten Feldern in den falschen Letter-Bucket schreiben
    (z.B. Michael → mmm statt lorenz_michael → lll).
    """
    cdir = (consultant_dir or '').strip()
    if '_' in cdir:
        src = cdir.split('_', 1)[0]
    else:
        src = (last_name or '').strip() or cdir
    ch = ''
    for c in src.lower():
        if 'a' <= c <= 'z':
            ch = c
            break
        if c in 'äöüß':
            ch = {'ä': 'a', 'ö': 'o', 'ü': 'u', 'ß': 's'}[c]
            break
    if not ch:
        return 'zzzSONSTIGES'
    return ch * 3


def _chmod_path(path: Path, is_dir: bool = False) -> None:
    mode = 0o777 if is_dir else 0o666
    try:
        os.chmod(path, mode)
    except OSError as e:
        logger.debug(f'chmod {path}: {e}')


def _chown_path(path: Path) -> None:
    cfg = _cfg()
    user = cfg.get('chown_user') or os.environ.get('AID_PROFILE_CHOWN_USER')
    group = cfg.get('chown_group') or os.environ.get('AID_PROFILE_CHOWN_GROUP')
    if not user and not group:
        return
    try:
        import pwd
        import grp
        uid = pwd.getpwnam(user).pw_uid if user else -1
        gid = grp.getgrnam(group).gr_gid if group else -1
        os.chown(path, uid, gid)
    except Exception as e:
        logger.debug(f'chown {path}: {e}')


def ensure_neu_cv_dir(consultant_dir: str, last_name: str = '') -> Optional[Path]:
    """
    …/AID_profile/{lll}/{consultant_dir}/neu/cv/
    Alle Zwischenordner 0777.
    """
    root = resolve_aid_profile_root()
    if not root:
        logger.warning('AID_profile Root fehlt — Publish übersprungen')
        return None
    dir_name = (consultant_dir or '').strip().strip('/')
    if not dir_name:
        logger.warning('consultant_dir leer — Publish übersprungen')
        return None
    bucket = letter_bucket(dir_name, last_name=last_name)
    target = root / bucket / dir_name / 'neu' / 'cv'
    try:
        # Eltern schrittweise anlegen + chmod
        cur = root
        for part in (bucket, dir_name, 'neu', 'cv'):
            cur = cur / part
            cur.mkdir(parents=True, exist_ok=True)
            _chmod_path(cur, is_dir=True)
            _chown_path(cur)
        return target
    except OSError as e:
        logger.warning(f'neu/cv nicht anlegbar ({target}): {e}')
        return None


def _copy_into(src: Path, dest_dir: Path) -> Optional[Path]:
    if not src.is_file():
        return None
    dest = dest_dir / src.name
    try:
        shutil.copy2(src, dest)
        _chmod_path(dest, is_dir=False)
        _chown_path(dest)
        return dest
    except OSError as e:
        logger.warning(f'Copy {src} → {dest}: {e}')
        return None


def _publish_html_offline(src: Path, dest_dir: Path, language: str = 'de') -> Optional[Path]:
    """
    HTML nach neu/cv schreiben — immer offline-fähig (CSS/JS/Logo eingebettet).
    Auch wenn die Quelle in data/html_out noch /static-Links hat.
    """
    if not src.is_file():
        return None
    dest = dest_dir / src.name
    try:
        from apps.cv_extractor.generator.cv_display_utils import (
            is_html_offline,
            make_html_offline_friendly,
        )
        html = src.read_text(encoding='utf-8')
        if not is_html_offline(html):
            html = make_html_offline_friendly(
                html, base_dir=str(settings.BASE_DIR), language=language,
            )
        dest.write_text(html, encoding='utf-8')
        _chmod_path(dest, is_dir=False)
        _chown_path(dest)
        if not is_html_offline(html):
            logger.warning(
                'Publish HTML noch nicht offline (%s) — CSS/Logo ggf. fehlend',
                dest.name,
            )
        else:
            logger.info('Publish HTML offline-fähig: %s', dest)
        return dest
    except Exception as e:
        logger.warning(f'Offline-HTML Publish fehlgeschlagen, Fallback Copy: {e}')
        return _copy_into(src, dest_dir)


def _libreoffice_to_pdf(src: Path, out_dir: Path, timeout_sec: int = 90) -> Optional[Path]:
    """DOCX/HTML → PDF via LibreOffice headless.

    Eigenes UserInstallation-Profil + Kill der Prozessgruppe bei Timeout,
    sonst bleiben soffice.bin-Zombies und blockieren den nächsten Convert.
    """
    if not src.is_file():
        return None
    import signal
    import tempfile
    import time as _time

    profile_dir = Path(tempfile.mkdtemp(prefix='lo-profile-'))
    profile_uri = profile_dir.as_uri()
    cmd = [
        'libreoffice', '--headless', '--nofirststartwizard',
        '--norestore', f'-env:UserInstallation={profile_uri}',
        '--convert-to', 'pdf',
        str(src), '--outdir', str(out_dir),
    ]
    proc = None
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
        )
        try:
            stdout, stderr = proc.communicate(timeout=timeout_sec)
        except subprocess.TimeoutExpired:
            logger.warning(
                'LibreOffice PDF Timeout (%ss) für %s — kill Prozessgruppe',
                timeout_sec, src.name,
            )
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError, OSError):
                try:
                    proc.kill()
                except Exception:
                    pass
            try:
                proc.communicate(timeout=5)
            except Exception:
                pass
            # Nachzügler
            subprocess.run(
                ['pkill', '-9', '-f', f'soffice.bin.*{src.name}'],
                capture_output=True, timeout=10,
            )
            return None

        if proc.returncode != 0:
            logger.warning(
                'LibreOffice PDF (%s): %s',
                src.name, (stderr or stdout or '').strip()[:500],
            )
            return None
        pdf = out_dir / (src.stem + '.pdf')
        # kurzes Warten auf NFS/CIFS flush
        for _ in range(10):
            if pdf.is_file():
                break
            _time.sleep(0.2)
        if pdf.is_file():
            _chmod_path(pdf, is_dir=False)
            _chown_path(pdf)
            return pdf
        logger.warning(f'LibreOffice: PDF fehlt nach Convert: {pdf}')
    except FileNotFoundError:
        logger.warning('LibreOffice nicht installiert — kein PDF-Publish')
    except Exception as e:
        logger.warning(f'LibreOffice PDF Fehler: {e}')
        if proc and proc.poll() is None:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except Exception:
                pass
    finally:
        shutil.rmtree(profile_dir, ignore_errors=True)
    return None


def publish_file(src_path: str | Path, consultant_dir: str, last_name: str = '') -> Optional[Path]:
    """Einzeldatei nach neu/cv kopieren."""
    dest_dir = ensure_neu_cv_dir(consultant_dir, last_name=last_name)
    if not dest_dir:
        return None
    return _copy_into(Path(src_path), dest_dir)


def publish_consultant_outputs(
    consultant,
    *,
    make_word: bool = True,
    make_pdf: bool = True,
) -> dict[str, Any]:
    """
    Nach Pipeline / Editor: HTML (+ Word + PDF) nach neu/cv legen.

    Liest vorhandene data/html_out / data/doc_out und kopiert;
    erzeugt Word bei Bedarf; PDF aus DOCX per LibreOffice.
    """
    out: dict[str, Any] = {
        'success': False,
        'neu_cv': None,
        'files': [],
        'error': None,
    }
    try:
        aid = getattr(consultant, 'aid', '') or ''
        cdir = getattr(consultant, 'consultant_dir', '') or ''
        last = getattr(consultant, 'last_name', '') or ''
        lang = (getattr(consultant, 'language', 'de') or 'de').lower()

        # EN-Profile nicht nach neu/cv spiegeln (sonst AID-…-en.pdf + Doppelung)
        if lang == 'en' or str(aid).lower().endswith('-en'):
            out['error'] = f'EN-Skip: {aid} (nur data/html_out, kein neu/cv)'
            logger.info(out['error'])
            return out

        if not cdir:
            first = (getattr(consultant, 'first_name', '') or '').lower()
            last_l = last.lower()
            cdir = f'{last_l}_{first}'.strip('_') or aid.lower()

        dest_dir = ensure_neu_cv_dir(cdir, last_name=last)
        if not dest_dir:
            out['error'] = 'AID_profile Root / neu/cv nicht verfügbar'
            return out
        out['neu_cv'] = str(dest_dir)

        base = Path(settings.BASE_DIR)
        html_dir = base / 'data' / 'html_out' / cdir
        doc_dir = base / 'data' / 'doc_out' / cdir

        # HTML → neu/cv (offline-fähig, auch wenn html_out noch /static hat)
        for name in (f'{aid}.html', f'{aid}-short.html', f'{aid}-en.html', f'{aid}-en-short.html'):
            src_html = html_dir / name
            if not src_html.is_file():
                continue
            p = _publish_html_offline(src_html, dest_dir, language=lang)
            if p:
                out['files'].append(str(p))

        # Word: vorhandenes kopieren oder erzeugen
        docx_path = doc_dir / f'{aid}.docx'
        if make_word and not docx_path.is_file():
            try:
                from apps.cv_extractor.generator.word.word_generator import WordGenerator
                res = WordGenerator(template_key='aid-word').generate(
                    consultant, skip_publish=True,
                )
                docx_path = Path(res.get('filepath') or docx_path)
            except Exception as e:
                logger.warning(f'Word-Generate für Publish: {e}')

        if docx_path.is_file():
            p = _copy_into(docx_path, dest_dir)
            if p:
                out['files'].append(str(p))
            published_docx = dest_dir / f'{aid}.docx'
            if make_pdf and published_docx.is_file():
                pdf = _libreoffice_to_pdf(published_docx, dest_dir)
                if pdf:
                    out['files'].append(str(pdf))

        # Fallback: wenn Word fehlschlägt / kein DOCX → HTML → PDF (Batch braucht AID-*.pdf)
        if make_pdf and not any(f.endswith('.pdf') for f in out['files']):
            html_pub = dest_dir / f'{aid}.html'
            if not html_pub.is_file():
                # ggf. gerade erst publiziert unter anderem Namen
                for f in dest_dir.glob(f'{aid}*.html'):
                    html_pub = f
                    break
            if html_pub.is_file():
                pdf = _libreoffice_to_pdf(html_pub, dest_dir, timeout_sec=60)
                if pdf:
                    # LibreOffice benennt nach HTML-Stem; sicherstellen AID-*.pdf
                    want = dest_dir / f'{aid}.pdf'
                    if pdf != want and pdf.is_file():
                        try:
                            pdf.rename(want)
                            pdf = want
                            _chmod_path(pdf, is_dir=False)
                            _chown_path(pdf)
                        except OSError:
                            pass
                    out['files'].append(str(pdf))
                    logger.info('Publish PDF via HTML-Fallback: %s', pdf)

        # Nochmal Rechte auf Ordner
        _chmod_path(dest_dir, is_dir=True)
        out['success'] = bool(out['files'])
        if out['success']:
            logger.info(f'Publish neu/cv: {aid} → {dest_dir} ({len(out["files"])} Dateien)')
        else:
            out['error'] = 'Keine Dateien zum Publishen gefunden (HTML/DOCX fehlt?)'
        return out
    except Exception as e:
        logger.warning(f'publish_consultant_outputs: {e}')
        out['error'] = str(e)
        return out
