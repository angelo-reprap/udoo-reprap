"""EDMS-Datei für den CRM-Viewer streamen.

/edms/api/file/ 404 + X-Frame-Options:deny im iframe → graues Sad-Face.
Dieser Endpoint:
- sucht Dokument ODER Version per UUID
- nimmt aktive Version, sonst die neueste
- löst den Share-Pfad über EDMS-Storage und bekannte Mounts auf
- setzt X-Frame-Options: SAMEORIGIN (falls doch per iframe)
- liefert Originalbytes, ohne LibreOffice-Konvertierung
"""
import logging
import os
from urllib.parse import quote

from django.conf import settings as django_settings
from django.http import FileResponse, JsonResponse
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.views.decorators.http import require_http_methods

logger = logging.getLogger(__name__)

_UUID_LEN = 36


def _mounts():
    office = getattr(django_settings, 'DMS_OFFICE_MOUNT', '/mnt/office')
    public = getattr(django_settings, 'DMS_PUBLIC_MOUNT', '/mnt/public')
    seen = []
    for p in (office, public, '/mnt/office', '/mnt/public'):
        if p and p not in seen:
            seen.append(p)
    return {
        'office': office,
        'public': public,
        'all': seen,
    }


def _join_under(root, rel):
    if not root or not rel:
        return None
    norm_rel = os.path.normpath(str(rel).replace('\\', '/')).lstrip('/')
    if norm_rel in ('.', ''):
        return None
    abs_path = os.path.normpath(os.path.join(root, norm_rel))
    mount_norm = os.path.normpath(root)
    if abs_path == mount_norm or abs_path.startswith(mount_norm + os.sep):
        return abs_path
    return None


def _existing_file(path):
    try:
        if path and os.path.isfile(path):
            return path
    except OSError:
        return None
    return None


def _resolve_abs_path(version):
    """Mehrere Kandidaten: EDMS-Storage, Originalpfad, Volume-Mounts."""
    if version is None:
        return None
    candidates = []

    try:
        from apps.abpe_edms.services import storage as edms_storage
        p = edms_storage.absolute_path(version)
        if p:
            candidates.append(p)
    except Exception as exc:
        logger.debug('edms storage.absolute_path: %s', exc)

    src = getattr(version, 'source_path_original', '') or ''
    if src:
        candidates.append(src)
        # Windows-Pfad → nur den Relativteil nach dem Share-Buchstaben
        unixish = src.replace('\\', '/')
        if len(unixish) >= 3 and unixish[1] == ':':
            candidates.append(unixish[2:])

    rel = getattr(version, 'relative_path', '') or ''
    filename = getattr(version, 'filename', '') or ''
    volume = (getattr(version, 'volume', '') or '').lower()
    mounts = _mounts()

    if rel:
        if rel.startswith('/'):
            candidates.append(rel)
        vol_root = mounts.get(volume) if volume in ('office', 'public') else None
        if vol_root:
            p = _join_under(vol_root, rel)
            if p:
                candidates.append(p)
        for root in mounts['all']:
            p = _join_under(root, rel)
            if p:
                candidates.append(p)
            if filename:
                p = _join_under(root, os.path.join(os.path.dirname(rel), filename))
                if p:
                    candidates.append(p)

    seen = set()
    for c in candidates:
        if not c or c in seen:
            continue
        seen.add(c)
        found = _existing_file(c)
        if found:
            return found
    return None


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


@xframe_options_sameorigin
@require_http_methods(['GET'])
def _api_edms_file(request, uuid):
    """Originaldatei streamen — für Blob-Viewer und Download."""
    uid = str(uuid)
    if len(uid) != _UUID_LEN:
        return JsonResponse({'ok': False, 'error': 'Ungültige UUID'}, status=400)

    try:
        doc, version = _get_doc_and_version(uid)
    except Exception as exc:
        logger.exception('edms file lookup: %s', exc)
        return JsonResponse({'ok': False, 'error': 'Dokument-Lookup fehlgeschlagen'}, status=500)

    if doc is None:
        return JsonResponse({'ok': False, 'error': 'Dokument nicht gefunden'}, status=404)
    if version is None:
        return JsonResponse({'ok': False, 'error': 'Keine Version vorhanden'}, status=404)

    abs_path = _resolve_abs_path(version)
    if not abs_path:
        logger.warning(
            'edms file missing uuid=%s volume=%s rel=%s name=%s',
            uid,
            getattr(version, 'volume', ''),
            getattr(version, 'relative_path', ''),
            getattr(version, 'filename', ''),
        )
        return JsonResponse({
            'ok': False,
            'error': 'Datei auf dem Share nicht gefunden',
            'volume': getattr(version, 'volume', '') or '',
            'filename': getattr(version, 'filename', '') or '',
        }, status=404)

    download = request.GET.get('download') == '1'
    return _file_response(abs_path, version, download)
