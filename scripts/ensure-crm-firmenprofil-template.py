#!/usr/bin/env python
"""Upsert Email-Studio-Vorlage crm_firmenprofil.

An Unternehmen: Was wir tun, warum Tempo, seit 2002.
Kein „vermitteln“, kein Gruß im Body (Signatur).

Live (ucs5), Datei von origin:
  cd /opt/abpe/backend
  git -C /mnt/public/udoo-reprap fetch origin cursor/crm-profilupdate-text-ee01
  python manage.py shell < <(
    git -C /mnt/public/udoo-reprap show origin/cursor/crm-profilupdate-text-ee01:scripts/ensure-crm-firmenprofil-template.py
  )
"""
from apps.abpe_email_studio.models import EmailTemplate, TemplateStatus, SenderMode

IDENT = "crm_firmenprofil"

_FONT = (
    "font-family:Arial,sans-serif;font-size:14px;line-height:1.5;"
    "color:#333333;"
)
_HEADER = "{{block:abcona_header_blau}}"
_SIGN = "{{block:signature}}"


def _p(inner: str) -> str:
    return f'<p style="{_FONT}margin:0 0 12px 0;">{inner}</p>'


def _ul(items: list[str]) -> str:
    lis = "".join(
        f'<li style="{_FONT}margin:0 0 4px 0;">{item}</li>' for item in items
    )
    return f'<ul style="margin:0 0 14px 18px;padding:0;">{lis}</ul>'


def _facts(rows: list[tuple[str, str]]) -> str:
    lines = "<br>\n".join(
        f"<strong>{label}:</strong> {value}" for label, value in rows
    )
    return (
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0"'
        ' border="0" style="margin:0 0 14px 0;">'
        f'<tr><td style="background-color:#e8f0f8;padding:12px 14px;{_FONT}">'
        f"{lines}</td></tr></table>"
    )


def _focus(num: str, title: str, body: str) -> str:
    return _p(f"<strong>{num}. {title}</strong><br>{body}")


HTML = "\n".join([
    _HEADER,
    _p("Guten Tag {first_name},"),
    _p("vielen Dank für Ihr Interesse. "
       "Wir bringen IT-Experten in Ihre Projekte — "
       "schnell, zuverlässig und auf Augenhöhe."),
    _p("Was Sie von uns erwarten können:"),
    _facts([
        ("Bestand", "rund 23.000 aktive Berater; Zugriff auf den Großteil "
                    "des deutschsprachigen Marktes"),
        ("Tempo", "erste Profile meist noch am selben Tag "
                  "(CV-Pipeline, Matching, Aufgaben)"),
        ("Einsatz", "kurz- und langfristig"),
    ]),
    _p("Unsere Schwerpunkte:"),
    _focus(
        "1",
        "Netzwerktechnik",
        "Architektur, Planung und Umsetzung — markenunabhängig. "
        "Firewall, Loadbalancer, Proxy, Switching und Routing, "
        "inkl. Konzept, Betrieb und der dazugehörigen Organisation.",
    ),
    _focus(
        "2",
        "Infrastruktur, Plattformen und Betrieb",
        "Unix-/Linux-Herkunft, Enterprise und Rechenzentrum. "
        "Konzept, Architektur, Betrieb, Organisation und Projektleitung — "
        "inkl. DevOps, Container (Docker, Kubernetes) und aktueller Plattformthemen.",
    ),
    _focus(
        "3",
        "Softwareentwicklung",
        "Individualentwicklung in Java, Python, C#/.NET, Perl "
        "sowie Web (JavaScript, TypeScript, CSS). "
        "Von der Oberfläche über Fachlogik und Berechnung bis zur Datenhaltung.",
    ),
    _focus(
        "4",
        "Künstliche Intelligenz",
        "Spezifikationsgetriebene Architektur und Entwicklung, KI im Betrieb. "
        "Für Ihre Projekte stellen wir Spezialisten, die in KI/AI oft noch tiefer sind.",
    ),
    _p("Warum das zählt: Bei uns gehen täglich Anfragen ein. "
       "Nennen Sie uns Ihre Anforderungen, schlagen wir zügig passende "
       "Profile vor — ohne Umwege."),
    _p("Seit 2002 arbeiten wir mit Unternehmen und IT-Experten zusammen. "
       "Gerne stellen wir Ihnen Profile für aktuelle oder geplante Projekte vor."),
    _p("Haben Sie konkrete Anforderungen? Schreiben Sie uns oder rufen Sie uns an."),
    _SIGN,
]) + "\n"

TEXT = """Guten Tag {first_name},

vielen Dank für Ihr Interesse. Wir bringen IT-Experten in Ihre Projekte — schnell, zuverlässig und auf Augenhöhe.

Was Sie von uns erwarten können:
- Bestand: rund 23.000 aktive Berater; Zugriff auf den Großteil des deutschsprachigen Marktes
- Tempo: erste Profile meist noch am selben Tag (CV-Pipeline, Matching, Aufgaben)
- Einsatz: kurz- und langfristig

Unsere Schwerpunkte:

1. Netzwerktechnik
Architektur, Planung und Umsetzung — markenunabhängig. Firewall, Loadbalancer, Proxy, Switching und Routing, inkl. Konzept, Betrieb und der dazugehörigen Organisation.

2. Infrastruktur, Plattformen und Betrieb
Unix-/Linux-Herkunft, Enterprise und Rechenzentrum. Konzept, Architektur, Betrieb, Organisation und Projektleitung — inkl. DevOps, Container (Docker, Kubernetes) und aktueller Plattformthemen.

3. Softwareentwicklung
Individualentwicklung in Java, Python, C#/.NET, Perl sowie Web (JavaScript, TypeScript, CSS). Von der Oberfläche über Fachlogik und Berechnung bis zur Datenhaltung.

4. Künstliche Intelligenz
Spezifikationsgetriebene Architektur und Entwicklung, KI im Betrieb. Für Ihre Projekte stellen wir Spezialisten, die in KI/AI oft noch tiefer sind.

Warum das zählt: Bei uns gehen täglich Anfragen ein. Nennen Sie uns Ihre Anforderungen, schlagen wir zügig passende Profile vor — ohne Umwege.

Seit 2002 arbeiten wir mit Unternehmen und IT-Experten zusammen. Gerne stellen wir Ihnen Profile für aktuelle oder geplante Projekte vor.

Haben Sie konkrete Anforderungen? Schreiben Sie uns oder rufen Sie uns an.

Mit freundlichen Grüßen
"""

defaults = {
    "name": "CRM — Firmenprofil & Leistungen",
    "subject": "IT-Experten für Ihre Projekte",
    "html_body": HTML.strip(),
    "text_body": TEXT.strip(),
    "status": TemplateStatus.ACTIVE,
    "sender_mode": SenderMode.USER,
    "include_signature": True,
    "description": "CRM Unternehmen: 23.000 Berater, selben Tag, 4 Schwerpunkte.",
}
try:
    from apps.abpe_email_studio.models import SignatureMode
    defaults["signature_mode"] = SignatureMode.USER
except Exception:
    pass
try:
    from apps.abpe_email_studio.models import AppScope
    if hasattr(AppScope, "CRM"):
        defaults["app_scope"] = AppScope.CRM
    elif hasattr(AppScope, "GENERAL"):
        defaults["app_scope"] = AppScope.GENERAL
except Exception:
    pass

field_names = {f.name for f in EmailTemplate._meta.get_fields()}
defaults = {k: v for k, v in defaults.items() if k in field_names}

tpl, created = EmailTemplate.objects.update_or_create(
    identifier=IDENT, defaults=defaults,
)
print(("CREATED" if created else "UPDATED"), IDENT, "pk=", tpl.pk, "|", tpl.name)
print("OK — crm_firmenprofil (Schwerpunkte / 23.000 / selben Tag)")
