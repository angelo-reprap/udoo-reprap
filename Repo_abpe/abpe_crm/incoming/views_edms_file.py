"""EDMS-Datei für den CRM-Viewer streamen.

O:  = /mnt/office  (Rechnungen, Verträge)
X:  = /mnt/public  (AID-CVs / Profile)

Windows-Pfade (O:\\Berater\\… mit '&' in Ordnernamen) werden auf den
Linux-Mount gelegt, inkl. case-insensitiver Suche. Fehlende Rechte
(chmod/chown) werden von 'Datei fehlt' unterschieden.
"""
from __future__ import annotations

import logging
import os
from urllib.parse import quote

logger = logging.getLogger(__name__)

_UUID_LEN = 36
_DRIVE_VOLUME = {
    'o': 'office',
    'x': 'public',
}
_SHARE_VOLUME = {
    'office': 'office',
    'o': 'office',
    'public': 'public',
    'x': 'public',
}


def _settings_mounts():
    office = '/mnt/office'
    public = '/mnt/public'
    try:
        from django.conf import settings as django_settings
        office = getattr(django_settings, 'DMS_OFFICE_MOUNT', office) or office
        public = getattr(django_settings, 'DMS_PUBLIC_MOUNT', public) or public
    except Exception:
        pass
    ordered = []
    for p in (office, public, '/mnt/office', '/mnt/public'):
        if p and p not in ordered:
            ordered.append(p)
    return {'office': office, 'public': public, 'all': ordered}


def _parse_win_or_rel(raw):
    """Zerlegt O:\\foo, //server/office/foo oder Relativpfad.

    Rueckgabe: (rest_mit_slash, volume_hint|None)
    """
    if not raw:
        return None, None
    s = str(raw).strip().replace('\\', '/')
    if not s:
        return None, None
    if s.startswith('//'):
        parts = [p for p in s.split('/') if p]
        if len(parts) >= 3:
            vol = _SHARE_VOLUME.get(parts[1].lower())
            return '/'.join(parts[2:]), vol
        return None, None
    if len(s) >= 2 and s[1] == ':':
        vol = _DRIVE_VOLUME.get(s[0].lower())
        return s[2:].lstrip('/'), vol
    return s.lstrip('/'), None


def _norm_part(name):
    return (
        (name or '')
        .lower()
        .replace('\uff06', '&')
        .replace('&amp;', '&')
        .replace(' und ', ' & ')
        .replace(' and ', ' & ')
        .replace('+', '&')
        .replace('_', ' ')
        .replace('  ', ' ')
        .strip()
    )


def _join_under(root, rel):
    if not root or not rel:
        return None
    rest, _hint = _parse_win_or_rel(rel)
    if not rest:
        rest = str(rel).replace('\\', '/').lstrip('/')
    rest = os.path.normpath(rest)
    if rest in ('.', '', os.pardir) or rest.startswith('..'):
        return None
    abs_path = os.path.normpath(os.path.join(root, rest))
    mount_norm = os.path.normpath(root)
    if abs_path == mount_norm or abs_path.startswith(mount_norm + os.sep):
        return abs_path
    return None


def _ci_resolve(root, rel):
    """Pfad unter root finden, Ordnernamen case-insensitive / '&' vs 'und'."""
    joined = _join_under(root, rel)
    if joined and os.path.isfile(joined):
        return joined
    rest, _hint = _parse_win_or_rel(rel)
    if not rest:
        return None
    current = os.path.normpath(root)
    mount_norm = current
    parts = [p for p in rest.replace('\\', '/').split('/') if p and p != '.']
    if any(p == '..' for p in parts):
        return None
    for i, part in enumerate(parts):
        try:
            names = os.listdir(current)
        except OSError:
            return None
        match = next((n for n in names if n == part), None)
        if match is None:
            match = next((n for n in names if n.lower() == part.lower()), None)
        if match is None:
            want = _norm_part(part)
            match = next((n for n in names if _norm_part(n) == want), None)
        if match is None:
            return None
        nxt = os.path.normpath(os.path.join(current, match))
        if not (nxt == mount_norm or nxt.startswith(mount_norm + os.sep)):
            return None
        current = nxt
        last = i == len(parts) - 1
        if last:
            return current if os.path.isfile(current) else None
        if not os.path.isdir(current):
            return None
    return None


def _probe_mount(path):
    info = {
        'path': path,
        'exists': False,
        'isdir': False,
        'readable': False,
        'listdir_ok': False,
    }
    try:
        info['exists'] = os.path.exists(path)
        info['isdir'] = os.path.isdir(path)
        info['readable'] = os.access(path, os.R_OK | os.X_OK)
        if info['isdir']:
            os.listdir(path)
            info['listdir_ok'] = True
    except OSError as exc:
        info['error'] = str(exc)
    return info


def _collect_raw_paths(version):
    raw = []
    for attr in ('relative_path', 'source_path_original', 'filename'):
        val = getattr(version, attr, None) or ''
        if val:
            raw.append(str(val))
    try:
        from apps.abpe_edms.services import storage as edms_storage
        for fn in ('absolute_path', 'win_path', 'unc_path'):
            func = getattr(edms_storage, fn, None)
            if not callable(func):
                continue
            try:
                p = func(version)
            except Exception as exc:
                logger.debug('edms storage.%s: %s', fn, exc)
                continue
            if p:
                raw.append(str(p))
    except Exception as exc:
        logger.debug('edms storage import: %s', exc)
    return raw


def _resolve_abs_path(version):
    """Mehrere Kandidaten: Storage, O:/X:-Mapping, case-insensitive Walk."""
    if version is None:
        return None, [], None
    mounts = _settings_mounts()
    volume = (getattr(version, 'volume', '') or '').lower()
    candidates = []
    traces = []

    for raw in _collect_raw_paths(version):
        rest, hint = _parse_win_or_rel(raw)
        vol = hint or (volume if volume in ('office', 'public') else None)
        roots = []
        if vol:
            roots.append(mounts[vol])
        roots.extend(mounts['all'])
        seen_roots = []
        for root in roots:
            if root in seen_roots:
                continue
            seen_roots.append(root)
            if rest:
                candidates.append(_join_under(root, rest))
            candidates.append(_join_under(root, raw))
            if rest:
                traces.append((root, rest))

    seen = set()
    ordered = []
    for c in candidates:
        if not c or c in seen:
            continue
        seen.add(c)
        ordered.append(c)
        try:
            if os.path.isfile(c):
                return c, ordered, None
        except OSError as exc:
            return None, ordered, exc

    for root, rest in traces:
        found = _ci_resolve(root, rest)
        if found:
            return found, ordered, None

    return None, ordered[:12], None


def _get_doc_and_version(uuid):
    from apps.abpe_edms.models import CrmDocument

    doc = CrmDocument.objects.filter(uuid=uuid).first()
    if doc is not None:
        version = (
            doc.versions.filter(is_active=True).order_by('-version_no').first()
            or doc.versions.order_by('-version_no').first()
        )
        return doc, version

    try:
        from apps.abpe_edms.models import CrmDocumentVersion
        version = (
            CrmDocumentVersion.objects.filter(uuid=uuid)
            .select_related('document')
            .first()
        )
    except Exception:
        version = None
    if version is None:
        return None, None
    return version.document, version


def _file_response(abs_path, version, download):
    filename = (getattr(version, 'filename', None) or os.path.basename(abs_path) or 'datei')
    mime = getattr(version, 'mimetype', None) or 'application/octet-stream'
    if filename.lower().endswith('.pdf'):
        mime = 'application/pdf'
    fh = open(abs_path, 'rb')
    from django.http import FileResponse
    resp = FileResponse(fh, content_type=mime)
    resp['Accept-Ranges'] = 'bytes'
    resp['X-Content-Type-Options'] = 'nosniff'
    disposition = 'attachment' if download else 'inline'
    ascii_name = filename.encode('ascii', 'replace').decode('ascii').replace('"', '')
    resp['Content-Disposition'] = (
        f'{disposition}; filename="{ascii_name}"; '
        f"filename*=UTF-8''{quote(filename)}"
    )
    return resp


def _linux_guess(version):
    mounts = _settings_mounts()
    volume = (getattr(version, 'volume', '') or '').lower()
    raws = _collect_raw_paths(version)
    for raw in raws:
        rest, hint = _parse_win_or_rel(raw)
        vol = hint or (volume if volume in ('office', 'public') else 'office')
        if rest:
            p = _join_under(mounts.get(vol, mounts['office']), rest)
            if p:
                return p
    return None


def _missing_payload(version, tried, access_exc=None):
    mounts = _settings_mounts()
    office = _probe_mount(mounts['office'])
    public = _probe_mount(mounts['public'])
    guess = _linux_guess(version)
    perm = isinstance(access_exc, PermissionError) or (
        office['exists'] and not office['listdir_ok']
    )
    if perm:
        hint = (
            'O: liegt unter /mnt/office. Der Django-User kann den Office-Share '
            'nicht lesen — Rechte pruefen (chmod a+rx Verzeichnisse, Datei a+r) '
            'bzw. CIFS-Mount mit tauglichem uid/gid.'
        )
        status = 403
        error = 'Keine Leserechte auf dem Office-Share'
    elif not office['exists']:
        hint = 'Mount /mnt/office fehlt. O:-Rechnungen sind ohne diesen Mount nicht erreichbar.'
        status = 404
        error = 'Office-Share nicht gemountet'
    else:
        hint = (
            'Datei unter dem gemappten Linux-Pfad nicht gefunden. '
            'Vergleich: Windows-Pfad vs. ls auf /mnt/office/…'
        )
        status = 404
        error = 'Datei auf dem Share nicht gefunden'
    return status, {
        'ok': False,
        'error': error,
        'hint': hint,
        'volume': getattr(version, 'volume', '') or '',
        'filename': getattr(version, 'filename', '') or '',
        'relative_path': getattr(version, 'relative_path', '') or '',
        'linux_guess': guess or '',
        'mount_office': office,
        'mount_public': public,
        'tried': tried[:8],
    }


def _api_edms_file(request, uuid):
    """Originaldatei streamen — fuer Blob-Viewer und Download."""
    from django.http import JsonResponse
    from django.views.decorators.clickjacking import xframe_options_sameorigin
    from django.views.decorators.http import require_http_methods

    @xframe_options_sameorigin
    @require_http_methods(['GET'])
    def inner(req, uid):
        if len(str(uid)) != _UUID_LEN:
            return JsonResponse({'ok': False, 'error': 'Ungueltige UUID'}, status=400)
        try:
            doc, version = _get_doc_and_version(str(uid))
        except Exception as exc:
            logger.exception('edms file lookup: %s', exc)
            return JsonResponse({'ok': False, 'error': 'Dokument-Lookup fehlgeschlagen'}, status=500)
        if doc is None:
            return JsonResponse({'ok': False, 'error': 'Dokument nicht gefunden'}, status=404)
        if version is None:
            return JsonResponse({'ok': False, 'error': 'Keine Version vorhanden'}, status=404)

        abs_path, tried, access_exc = _resolve_abs_path(version)
        if not abs_path:
            status, payload = _missing_payload(version, tried, access_exc)
            logger.warning('edms file miss uuid=%s %s', uid, payload.get('linux_guess'))
            return JsonResponse(payload, status=status)

        if not os.access(abs_path, os.R_OK):
            status, payload = _missing_payload(version, tried, PermissionError('EACCES'))
            payload['linux_path'] = abs_path
            payload['error'] = 'Keine Leserechte auf der Datei'
            payload['hint'] = (
                'Datei liegt unter %s, Django darf sie nicht oeffnen '
                '(chmod/chown bzw. CIFS uid).' % abs_path
            )
            return JsonResponse(payload, status=403)

        download = req.GET.get('download') == '1'
        try:
            return _file_response(abs_path, version, download)
        except PermissionError:
            status, payload = _missing_payload(version, tried, PermissionError('EACCES'))
            payload['linux_path'] = abs_path
            return JsonResponse(payload, status=403)

    return inner(request, uuid)
