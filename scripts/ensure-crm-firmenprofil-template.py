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
    _p("vielen Dank für Ihr Interesse."),
    _p("Angelo Malaguarnera, Inhaber, ist seit 1996 darin tätig, "
       "IT-Experten in Projekte zu bringen. Mehrere Kolleginnen und Kollegen "
       "arbeiten seit fast 25 Jahren mit uns. Dieses lange Miteinander hilft uns, "
       "Ihre Anfrage sehr zielgenau zu verstehen — und Sie bestmöglich zu unterstützen."),
    _p("<strong>Bestand.</strong> "
       "Über 23.000 aktive Berater, die wir im Laufe der Jahre direkt angesprochen haben. "
       "Dieser direkte Bestand trifft rund 90&nbsp;Prozent der Profile in unseren vier "
       "Schwerpunkten. Über Partner und Profilbörsen erreichen wir darüber hinaus "
       "den Großteil der IT-Experten im deutschsprachigen Markt."),
    _p("<strong>Tempo.</strong> "
       "Mit der KI-gestützten Infrastruktur, die wir in diesem Jahr in Betrieb genommen haben, "
       "liegen erste Vorschläge oft noch am selben Tag vor: verfügbare Berater oder Teams, "
       "die Ihre Aufgabe umsetzen können. Jede Anfrage gehen wir mit dem Anspruch an, "
       "den Bedarf vollständig zu verstehen und konkret zu besetzen."),
    _p("<strong>Einsatzmodell.</strong> "
       "Wir richten uns nach Ihrem Bedarf: kurzfristige Verstärkung oder längere "
       "Projektbegleitung; vor Ort, remote oder hybrid; Kontingente, die Sie nach Abruf nutzen. "
       "Vertraglich bilden wir das ab als Dienstvertrag, Werkvertrag, Festpreis, "
       "Paketpreis, Wartung oder Pauschale."),
    _p("Unsere Schwerpunkte:"),
    _focus(
        "1",
        "Netzwerktechnik",
        "Architektur, Konzept, Leitung, Planung, Steuerung, Umsetzung sowie Betrieb "
        "und Organisation. Themen (Auszug): Firewalling, Loadbalancer, Proxy, Routing "
        "und Switching — markenunabhängig und passend zu Ihrer bestehenden Infrastruktur. "
        "Schwerpunkt Carrier und Large-Enterprise-Netze; im Mittelstand beraten und "
        "verstärken wir ebenso.",
    ),
    _focus(
        "2",
        "IT-Infrastruktur und Betrieb",
        "Cloud, Enterprise und Rechenzentrum. Architektur, Konzept, Projektleitung, "
        "Betrieb, Wartung und Monitoring. Themen (Auszug): virtuelle und cloud-basierte "
        "Systeme, Datenbanken, DevOps, Docker, Kubernetes — einschließlich aktueller "
        "System- und Plattformumgebungen.",
    ),
    _focus(
        "3",
        "Softwareentwicklung",
        "Rollen von Architektur und Tech Lead über Entwicklung und Qualitätssicherung "
        "bis Projektleitung. Themenfelder: Web, Fachanwendungen, Schnittstellen, "
        "Berechnung und Datenhaltung. Sprachen und Technik (Auszug): Java, Python, "
        "C#/.NET, Perl, JavaScript, TypeScript, CSS — von der Oberfläche über die "
        "Fachlogik bis zur Persistenz.",
    ),
    _focus(
        "4",
        "Künstliche Intelligenz",
        "KI-gestützte Konzepte, Architekturen und Programmierung: spezifikationsgetriebene "
        "Entwicklung, Assistenz in Entwurf und Review, Integration in bestehende Anwendungen, "
        "Automatisierung im Betrieb (Administration, Monitoring, Wissenssysteme), "
        "Agenten und Retrieval. Dazu Spezialisten aus unserem Bestand, die in KI/AI "
        "Produktionsthemen oft noch tiefer sind als der Werkzeugeinsatz allein.",
    ),
    _p("Haben Sie konkrete Anforderungen? Schreiben Sie uns oder rufen Sie uns an. "
       "Wir stellen Profile oder Teams vor — nach Absprache mit den Beraterinnen und Beratern."),
    _SIGN,
]) + "\n"

TEXT = """Guten Tag {first_name},

vielen Dank für Ihr Interesse.

Angelo Malaguarnera, Inhaber, ist seit 1996 darin tätig, IT-Experten in Projekte zu bringen. Mehrere Kolleginnen und Kollegen arbeiten seit fast 25 Jahren mit uns. Dieses lange Miteinander hilft uns, Ihre Anfrage sehr zielgenau zu verstehen — und Sie bestmöglich zu unterstützen.

Bestand. Über 23.000 aktive Berater, die wir im Laufe der Jahre direkt angesprochen haben. Dieser direkte Bestand trifft rund 90 Prozent der Profile in unseren vier Schwerpunkten. Über Partner und Profilbörsen erreichen wir darüber hinaus den Großteil der IT-Experten im deutschsprachigen Markt.

Tempo. Mit der KI-gestützten Infrastruktur, die wir in diesem Jahr in Betrieb genommen haben, liegen erste Vorschläge oft noch am selben Tag vor: verfügbare Berater oder Teams, die Ihre Aufgabe umsetzen können. Jede Anfrage gehen wir mit dem Anspruch an, den Bedarf vollständig zu verstehen und konkret zu besetzen.

Einsatzmodell. Wir richten uns nach Ihrem Bedarf: kurzfristige Verstärkung oder längere Projektbegleitung; vor Ort, remote oder hybrid; Kontingente, die Sie nach Abruf nutzen. Vertraglich bilden wir das ab als Dienstvertrag, Werkvertrag, Festpreis, Paketpreis, Wartung oder Pauschale.

Unsere Schwerpunkte:

1. Netzwerktechnik
Architektur, Konzept, Leitung, Planung, Steuerung, Umsetzung sowie Betrieb und Organisation. Themen (Auszug): Firewalling, Loadbalancer, Proxy, Routing und Switching — markenunabhängig und passend zu Ihrer bestehenden Infrastruktur. Schwerpunkt Carrier und Large-Enterprise-Netze; im Mittelstand beraten und verstärken wir ebenso.

2. IT-Infrastruktur und Betrieb
Cloud, Enterprise und Rechenzentrum. Architektur, Konzept, Projektleitung, Betrieb, Wartung und Monitoring. Themen (Auszug): virtuelle und cloud-basierte Systeme, Datenbanken, DevOps, Docker, Kubernetes — einschließlich aktueller System- und Plattformumgebungen.

3. Softwareentwicklung
Rollen von Architektur und Tech Lead über Entwicklung und Qualitätssicherung bis Projektleitung. Themenfelder: Web, Fachanwendungen, Schnittstellen, Berechnung und Datenhaltung. Sprachen und Technik (Auszug): Java, Python, C#/.NET, Perl, JavaScript, TypeScript, CSS — von der Oberfläche über die Fachlogik bis zur Persistenz.

4. Künstliche Intelligenz
KI-gestützte Konzepte, Architekturen und Programmierung: spezifikationsgetriebene Entwicklung, Assistenz in Entwurf und Review, Integration in bestehende Anwendungen, Automatisierung im Betrieb (Administration, Monitoring, Wissenssysteme), Agenten und Retrieval. Dazu Spezialisten aus unserem Bestand, die in KI/AI Produktionsthemen oft noch tiefer sind als der Werkzeugeinsatz allein.

Haben Sie konkrete Anforderungen? Schreiben Sie uns oder rufen Sie uns an. Wir stellen Profile oder Teams vor — nach Absprache mit den Beraterinnen und Beratern.

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
    "description": "CRM Unternehmen: Person, 23.000, I&O, KI ausführlich. Kürzen nach Bedarf.",
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
print("OK — crm_firmenprofil (Person / I&O / KI ausführlich)")
