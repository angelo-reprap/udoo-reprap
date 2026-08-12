"""
Shaduler-Einstellungen (Key/Value in DB) — Gulp/FM/Hays-Pfade editierbar ohne Code-Deploy.

Lesen: get_setting(key) → DB-Wert oder Katalog-Default.
Schreiben: set_settings({key: value}) / ensure_defaults().
"""
from __future__ import annotations

from typing import Any, Optional

# Katalog: key → {group, label, value, description}
SETTING_CATALOG: dict[str, dict[str, str]] = {
    'radar.fm.base_url': {
        'group': 'freelancermap',
        'label': 'Freelancermap Basis-URL',
        'value': 'https://www.freelancermap.de',
        'description': 'Basis für Profil- und Projekt-Links',
    },
    'radar.fm.list_url': {
        'group': 'freelancermap',
        'label': 'Freelancermap Projektliste',
        'value': 'https://www.freelancermap.de/projekte',
        'description': 'Anfragen-Radar: Projektliste',
    },
    'radar.fm.profil_url_tpl': {
        'group': 'freelancermap',
        'label': 'FM Profil-URL (Slug)',
        'value': 'https://www.freelancermap.de/profil/{slug}',
        'description': 'Platzhalter: {slug}',
    },
    'radar.fm.freelancer_id_url_tpl': {
        'group': 'freelancermap',
        'label': 'FM Freelancer-URL (ID)',
        'value': 'https://www.freelancermap.de/freelancer?id={id}',
        'description': 'Platzhalter: {id}',
    },
    'radar.gulp.base_url': {
        'group': 'gulp',
        'label': 'Gulp Basis-URL',
        'value': 'https://www.gulp.de',
        'description': 'Origin / Referer',
    },
    'radar.gulp.list_url': {
        'group': 'gulp',
        'label': 'Gulp Projektliste',
        'value': 'https://www.gulp.de/gulp2/g/projekte?order=DATE_DESC&query=&page=1',
        'description': 'Anfragen-Radar: Gulp-Projekte',
    },
    'radar.gulp.csrf_url': {
        'group': 'gulp',
        'label': 'Gulp CSRF-URL',
        'value': 'https://www.gulp.de/gulp2/rest/internal/system/csrf',
        'description': '',
    },
    'radar.gulp.search_url': {
        'group': 'gulp',
        'label': 'Gulp Projekte-Search',
        'value': 'https://www.gulp.de/gulp2/rest/internal/projects/search',
        'description': '',
    },
    'radar.gulp.tf_base': {
        'group': 'gulp',
        'label': 'Gulp Talentfinder Basis',
        'value': 'https://www.gulp.de/talentfinder/app',
        'description': 'Berater-Radar / Experten',
    },
    'radar.gulp.profiles_search': {
        'group': 'gulp',
        'label': 'Gulp Profiles-Search',
        'value': 'https://www.gulp.de/gulp2/rest/internal/profiles/search',
        'description': 'Verfügbare Berater',
    },
    'radar.gulp.experten_url_tpl': {
        'group': 'gulp',
        'label': 'Gulp Experten-URL',
        'value': 'https://www.gulp.de/talentfinder/app/experten/{mongo}',
        'description': 'Platzhalter: {mongo} oder Query gulpId=',
    },
    'radar.hays.list_url': {
        'group': 'hays',
        'label': 'Hays Jobsuche',
        'value': (
            'https://www.hays.de/jobsuche/stellenangebote-jobs/'
            's/IT/1/j/Contracting/3/p/1?e=false&pt=false&ij=false&sortOrder=createdAt'
        ),
        'description': 'Anfragen-Radar: Hays',
    },
}

_GROUP_LABELS = {
    'freelancermap': 'Freelancermap',
    'gulp': 'Gulp',
    'hays': 'Hays',
}


def ensure_defaults() -> int:
    """Legt fehlende Keys mit Katalog-Defaults an. Returns Anzahl neu angelegt."""
    from apps.abpe_shaduler.models import ShadulerSetting

    created = 0
    for key, meta in SETTING_CATALOG.items():
        obj, was_new = ShadulerSetting.objects.get_or_create(
            key=key,
            defaults={
                'value': meta['value'],
                'label': meta['label'],
                'group': meta['group'],
                'description': meta.get('description') or '',
            },
        )
        if was_new:
            created += 1
        else:
            # Meta nachziehen, Wert unverändert lassen
            dirty = False
            if not obj.label and meta['label']:
                obj.label = meta['label']
                dirty = True
            if not obj.group and meta['group']:
                obj.group = meta['group']
                dirty = True
            if dirty:
                obj.save(update_fields=['label', 'group', 'updated_at'])
    return created


def get_setting(key: str, default: Optional[str] = None) -> str:
    """DB-Wert, sonst Katalog-Default, sonst default-Argument."""
    catalog_default = SETTING_CATALOG.get(key, {}).get('value')
    fallback = default if default is not None else (catalog_default or '')
    try:
        from apps.abpe_shaduler.models import ShadulerSetting
        row = ShadulerSetting.objects.filter(key=key).only('value').first()
        if row and row.value is not None and str(row.value).strip() != '':
            return str(row.value).strip()
    except Exception:
        pass
    return fallback


def list_settings() -> list[dict[str, Any]]:
    ensure_defaults()
    from apps.abpe_shaduler.models import ShadulerSetting

    rows = {
        r.key: r
        for r in ShadulerSetting.objects.filter(key__in=SETTING_CATALOG.keys())
    }
    out = []
    for key, meta in SETTING_CATALOG.items():
        row = rows.get(key)
        out.append({
            'key': key,
            'group': meta['group'],
            'group_label': _GROUP_LABELS.get(meta['group'], meta['group']),
            'label': (row.label if row and row.label else meta['label']),
            'description': (row.description if row and row.description else meta.get('description') or ''),
            'value': (row.value if row else meta['value']),
            'default': meta['value'],
        })
    return out


def set_settings(updates: dict[str, str]) -> dict[str, Any]:
    """updates: {key: value}. Unbekannte Keys werden ignoriert."""
    ensure_defaults()
    from apps.abpe_shaduler.models import ShadulerSetting

    saved = []
    for key, value in (updates or {}).items():
        if key not in SETTING_CATALOG:
            continue
        meta = SETTING_CATALOG[key]
        obj, _ = ShadulerSetting.objects.get_or_create(
            key=key,
            defaults={
                'value': meta['value'],
                'label': meta['label'],
                'group': meta['group'],
                'description': meta.get('description') or '',
            },
        )
        obj.value = str(value if value is not None else '')
        if not obj.label:
            obj.label = meta['label']
        if not obj.group:
            obj.group = meta['group']
        obj.save()
        saved.append(key)
    return {'ok': True, 'saved': saved, 'results': list_settings()}


def reset_to_defaults(keys: Optional[list[str]] = None) -> dict[str, Any]:
    ensure_defaults()
    from apps.abpe_shaduler.models import ShadulerSetting

    target = keys or list(SETTING_CATALOG.keys())
    for key in target:
        meta = SETTING_CATALOG.get(key)
        if not meta:
            continue
        ShadulerSetting.objects.update_or_create(
            key=key,
            defaults={
                'value': meta['value'],
                'label': meta['label'],
                'group': meta['group'],
                'description': meta.get('description') or '',
            },
        )
    return {'ok': True, 'results': list_settings()}
