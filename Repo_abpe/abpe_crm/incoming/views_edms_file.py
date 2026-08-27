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
    for p in (office, public, '/mnt/office', '/mnt/public', '/mnt/O', '/mnt/o'):
        if p and p not in ordered:
            ordered.append(p)
    for extra in ('abpe', 'abcona'):
        p = os.path.join(office, extra)
        if p not in ordered:
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


def _rel_variants(rest):
    """Typische Abweichungen: Share-Root ist schon Berater/, oder abpe/-Prefix."""
    if not rest:
        return []
    out = []

    def add(x):
        x = (x or '').strip().strip('/')
        if x and x not in out:
            out.append(x)

    add(rest)
    parts = [p for p in rest.split('/') if p]
    if parts and parts[0].lower() == 'berater' and len(parts) > 1:
        add('/'.join(parts[1:]))
    for pre in ('abpe', 'abcona', 'Dokumente', 'DMS', 'office'):
        add(pre + '/' + rest)
        if parts:
            add(pre + '/' + '/'.join(parts[1:] if parts[0].lower() == 'berater' else parts))
    return out


def _match_child(current, part):
    try:
        names = os.listdir(current)
    except OSError:
        return None, []
    match = next((n for n in names if n == part), None)
    if match is None:
        match = next((n for n in names if n.lower() == part.lower()), None)
    if match is None:
        want = _norm_part(part)
        match = next((n for n in names if _norm_part(n) == want), None)
    interesting = [n for n in names if _norm_part(n)[:8] == _norm_part(part)[:8] or '&' in n or 'aktiv' in n.lower()]
    siblings = interesting[:15] or names[:15]
    return match, siblings


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
        match, _sib = _match_child(current, part)
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


def _diagnose_walk(root, rest):
    """Welches Pfadstück bricht ab? Siblings helfen bei '&'/Tippvarianten."""
    info = {
        'root': root,
        'last_ok': root,
        'missing': '',
        'siblings': [],
    }
    current = os.path.normpath(root)
    mount_norm = current
    parts = [p for p in (rest or '').replace('\\', '/').split('/') if p and p != '.']
    for i, part in enumerate(parts):
        match, siblings = _match_child(current, part)
        if match is None:
            info['missing'] = part
            info['siblings'] = siblings
            info['last_ok'] = current
            return info
        nxt = os.path.normpath(os.path.join(current, match))
        if not (nxt == mount_norm or nxt.startswith(mount_norm + os.sep)):
            info['missing'] = part
            info['last_ok'] = current
            return info
        current = nxt
        info['last_ok'] = current
        last = i == len(parts) - 1
        if last and not os.path.isfile(current):
            info['missing'] = part
            info['siblings'] = siblings
            return info
        if not last and not os.path.isdir(current):
            info['missing'] = part
            return info
    return info


def _find_filename_under(start, filename, mount_root, max_depth=4):
    if not start or not filename or not os.path.isdir(start):
        return None
    start = os.path.normpath(start)
    mount_norm = os.path.normpath(mount_root or start)
    target = filename.lower()
    try:
        rel_depth = os.path.relpath(start, mount_norm).count(os.sep) + (0 if os.path.relpath(start, mount_norm) == '.' else 1)
    except ValueError:
        rel_depth = 0
    if rel_depth < 2:
        return None
    for dirpath, dirnames, filenames in os.walk(start):
        dnorm = os.path.normpath(dirpath)
        if not (dnorm == mount_norm or dnorm.startswith(mount_norm + os.sep)):
            dirnames[:] = []
            continue
        depth = os.path.relpath(dnorm, start).count(os.sep)
        if os.path.relpath(dnorm, start) == '.':
            depth = 0
        if depth >= max_depth:
            dirnames[:] = []
            continue
        for fn in filenames:
            if fn.lower() == target:
                return os.path.join(dnorm, fn)
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
            variants = _rel_variants(rest) if rest else []
            if not variants and raw:
                variants = _rel_variants(raw) or [raw]
            for var in variants:
                candidates.append(_join_under(root, var))
                traces.append((root, var))

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

    filename = getattr(version, 'filename', '') or ''
    for root, rest in traces:
        diag = _diagnose_walk(root, rest)
        found = _find_filename_under(diag.get('last_ok'), filename, root)
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
    walk = None
    rest = None
    off = os.path.normpath(mounts['office'])
    if guess:
        g = os.path.normpath(guess)
        if g == off or g.startswith(off + os.sep):
            rel = os.path.relpath(g, off)
            rest = None if rel == '.' else rel
        else:
            rest, _hint = _parse_win_or_rel(guess)
    if not rest:
        for raw in _collect_raw_paths(version):
            r, _h = _parse_win_or_rel(raw)
            if r:
                rest = r
                break
    if rest:
        walk = _diagnose_walk(mounts['office'], rest)
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
    elif walk and walk.get('missing'):
        hint = (
            'Pfad bricht ab bei %r — nicht wegen Leerzeichen, sondern der Ordner '
            'heißt auf Linux anders oder sitzt woanders. Letzter Treffer: %s'
            % (walk.get('missing'), walk.get('last_ok') or '')
        )
        status = 404
        error = 'Datei auf dem Share nicht gefunden'
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
        'walk_last_ok': (walk or {}).get('last_ok') or '',
        'walk_missing': (walk or {}).get('missing') or '',
        'walk_siblings': (walk or {}).get('siblings') or [],
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
