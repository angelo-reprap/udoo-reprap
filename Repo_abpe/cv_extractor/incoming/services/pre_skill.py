"""
pre_skill.py – Regelbasierte Skill-Kategorisierung (Stufe vor LLM)

Zwei-Stufen-Erkennung:
  1. Überschriften-Match (Heading): DE + EN Begriffe
  2. Inhalt-Match (Content): typische Begriffe im Block-Text

Gibt zurück: Dict[group_index, category_key] für alle erkannten Blöcke.
Unerkannte Blöcke → LLM in block_labeler._stage2_skills()
"""

import re
import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# ── Heading-Map: Überschriften DE + EN ───────────────────────────────────────
# Mindestens 10 Begriffe pro Kategorie (DE + EN + Varianten)

HEADING_MAP = {
    'programming_languages': [
        'programmiersprachen', 'programmierung', 'sprachen', 'coding',
        'programming', 'languages', 'skriptsprachen', 'scriptsprachen',
        'development languages', 'code', 'scripting', 'programmierkenntnisse',
    ],
    'operating_system': [
        'betriebssysteme', 'betriebssystem', 'os', 'operating system',
        'operating systems', 'systeme', 'plattformen', 'server systeme',
        'server-systeme', 'systemplattformen', 'betrieb', 'systemkenntnisse',
    ],
    'hardware': [
        'hardware', 'geräte', 'appliances', 'netzwerkgeräte', 'devices',
        'netzwerk hardware', 'netzwerk-hardware', 'server hardware',
        'infrastruktur hardware', 'equipment', 'komponenten', 'netzwerkkomponenten',
    ],
    'network_protocol': [
        'datenkommunikation', 'netzwerkprotokolle', 'protokolle', 'netzwerke',
        'networking', 'network protocols', 'kommunikation', 'netzwerktechnologien',
        'netzwerktechnologie', 'netzwerk', 'network', 'lan', 'wan',
        'netzwerkkenntnisse',
    ],
    'security_tool': [
        'security', 'sicherheit', 'firewall', 'firewalls', 'security tools',
        'sicherheitstools', 'it security', 'it-security', 'netzwerksicherheit',
        'cybersecurity', 'sicherheitssoftware', 'security software',
    ],
    'database': [
        'datenbanken', 'datenbank', 'database', 'databases', 'datenbankserver',
        'datenbanksysteme', 'db', 'data storage', 'datenspeicher',
        'datenbankmanagement', 'dbms', 'rdbms', 'sql server',
    ],
    'cloud_platform': [
        'cloud', 'cloud plattformen', 'cloud-plattformen', 'cloud platform',
        'cloud platforms', 'cloud services', 'cloud computing', 'iaas',
        'paas', 'saas', 'cloud infrastruktur', 'cloud-infrastruktur',
    ],
    'virtualization': [
        'virtualisierung', 'virtualization', 'virtual machines', 'vm',
        'hypervisor', 'container', 'containerisierung', 'containerization',
        'virtuelle maschinen', 'virtualisierungsplattformen',
    ],
    'devops_tool': [
        'devops', 'devops tools', 'automatisierung', 'automation',
        'deployment', 'build tools', 'ci tools', 'infrastruktur tools',
        'infrastructure tools', 'konfigurationsmanagement', 'configuration management',
    ],
    'ci_cd_tool': [
        'ci/cd', 'cicd', 'continuous integration', 'continuous delivery',
        'continuous deployment', 'build pipeline', 'deployment pipeline',
        'release management', 'build automation',
    ],
    'monitoring_tool': [
        'monitoring', 'überwachung', 'monitoring tools', 'observability',
        'logging', 'alerting', 'performance monitoring', 'system monitoring',
        'netzwerküberwachung', 'network monitoring',
    ],
    'framework': [
        'frameworks', 'framework', 'bibliotheken', 'libraries', 'library',
        'technologien', 'technologies', 'web frameworks', 'entwicklungsframeworks',
        'softwareframeworks', 'komponenten', 'sdk',
    ],
    'development_environment': [
        'entwicklungsumgebungen', 'entwicklungsumgebung', 'ide', 'ides',
        'development environment', 'development tools', 'entwicklungswerkzeuge',
        'werkzeuge', 'tools', 'dev tools', 'software tools',
    ],
    'version_control': [
        'versionsverwaltung', 'versionskontrolle', 'version control',
        'source control', 'scm', 'quellcodeverwaltung', 'code verwaltung',
        'repository', 'repositories',
    ],
    'testing_tool': [
        'testing', 'tests', 'testtools', 'test tools', 'qualitätssicherung',
        'quality assurance', 'qa tools', 'testautomatisierung',
        'test automation', 'unittest', 'unit tests',
    ],
    'methodology': [
        'methoden', 'methodologien', 'methodology', 'methodologies',
        'vorgehensmodelle', 'projektmethoden', 'agile', 'prozesse',
        'processes', 'standards', 'normen',
    ],
    'project_management': [
        'projektmanagement', 'project management', 'projektsteuerung',
        'projektplanung', 'project tools', 'projekttools', 'ticketsysteme',
        'issue tracking', 'project tracking',
    ],
    'identity_management': [
        'identity management', 'identitätsmanagement', 'iam',
        'zugriffsmanagement', 'access management', 'authentifizierung',
        'authentication', 'autorisierung', 'authorization', 'verzeichnisdienste',
    ],
    'business_software': [
        'business software', 'geschäftssoftware', 'erp', 'crm',
        'office software', 'büroanwendungen', 'anwendungen', 'software',
        'applikationen', 'enterprise software',
    ],
    'communication_tool': [
        'kommunikationstools', 'kommunikation', 'communication',
        'collaboration tools', 'collaboration', 'messaging', 'chat tools',
        'videokonferenz', 'video conferencing',
    ],
    'documentation_tool': [
        'dokumentation', 'documentation', 'dokumentationstools',
        'wikis', 'knowledge base', 'wissensdatenbank', 'technische dokumentation',
    ],
    'data_format': [
        'datenformate', 'formate', 'data formats', 'dateiformate',
        'serialisierung', 'serialization', 'datenaustausch', 'data exchange',
    ],
    'data_management': [
        'datenmanagement', 'data management', 'etl', 'data warehouse',
        'datawarehouse', 'datenmigration', 'data migration', 'big data',
        'datenverarbeitung', 'data processing',
    ],
    'architecture_pattern': [
        'architekturmuster', 'architektur', 'architecture', 'design patterns',
        'muster', 'patterns', 'softwarearchitektur', 'systemarchitektur',
        'architectural patterns', 'entwurfsmuster',
    ],
    'special_concept': [
        'spezielle konzepte', 'special concepts', 'konzepte', 'concepts',
        'compliance', 'regulierung', 'regulation', 'normen', 'standards',
        'zertifizierungen', 'branchenspezifisch',
    ],
    'it_infrastructure': [
        'it infrastruktur', 'it-infrastruktur', 'infrastruktur', 'infrastructure',
        'netzwerk infrastruktur', 'netzwerkinfrastruktur', 'it umgebung',
        'systemumgebung', 'technische infrastruktur', 'allgemeine kenntnisse',
    ],
    'special_skill': [
        'sonstige', 'sonstige skills', 'weitere kenntnisse', 'sonstiges',
        'andere kenntnisse', 'diverses', 'verschiedenes', 'other skills',
        'miscellaneous', 'weitere technologien', 'sonstige technologien',
    ],
    'soft_skill': [
        'soft skills', 'soziale kompetenzen', 'persönliche kompetenzen',
        'führung', 'leadership', 'kommunikation', 'teamarbeit', 'teamwork',
        'management', 'beratung', 'consulting',
    ],
}

# ── Content-Map: typische Begriffe im Block-Inhalt ───────────────────────────
# ~10 eindeutige Begriffe pro Kategorie die stark auf die Kategorie hinweisen

CONTENT_MAP = {
    'programming_languages': [
        r'\bc#\b', r'\bjava\b', r'\bpython\b', r'\byaml\b', r'\bbash\b',
        r'\bshell\b', r'\bpowershell\b', r'\bjavascript\b', r'\btypescript\b',
        r'\bcobol\b', r'\bsql\b', r'\br\b', r'\bruby\b', r'\bphp\b',
        r'\bkotlin\b', r'\bswift\b', r'\bscala\b', r'\bperl\b',
    ],
    'operating_system': [
        r'\blinux\b', r'\bwindows server\b', r'\bunix\b', r'\bsolaris\b',
        r'\bfortios\b', r'\bcisco ios\b', r'\bnx-os\b', r'\barubaos\b',
        r'\baix\b', r'\braspbian\b', r'\bcentos\b', r'\bubuntu\b',
        r'\bredhat\b', r'\bdebian\b', r'\bfreebsd\b', r'\bmacos\b',
    ],
    'hardware': [
        r'\bcisco nexus\b', r'\bcisco catalyst\b', r'\bcheckpoint\b',
        r'\bfortigate\b', r'\bfortiswitch\b', r'\bfortiap\b',
        r'\bcisco router\b', r'\bnortel\b', r'\bfoundry\b',
        r'\bextreme\b', r'\bappliance\b', r'\bswitch\b', r'\brouter\b',
        r'\bf5\b', r'\bloopback\b', r'\bchipset\b', r'\bserver\b',
    ],
    'network_protocol': [
        r'\bbgp\b', r'\bospf\b', r'\beigrp\b', r'\brip\b', r'\bmpls\b',
        r'\bvlan\b', r'\bvpn\b', r'\btcp/ip\b', r'\bethernet\b',
        r'\bwifi\b', r'\bwlan\b', r'\bipv4\b', r'\bipv6\b',
        r'\bstp\b', r'\blacp\b', r'\bipsec\b', r'\bssl\b',
    ],
    'security_tool': [
        r'\bfortigate\b', r'\bcheckpoint\b', r'\bpaloalto\b', r'\bzscaler\b',
        r'\bf5 big-ip\b', r'\balgosec\b', r'\btufin\b', r'\bskybox\b',
        r'\bmcafee\b', r'\bopswat\b', r'\bclearswift\b', r'\bsnort\b',
        r'\bwaf\b', r'\bids\b', r'\bips\b', r'\bsiem\b', r'\bsoc\b',
    ],
    'database': [
        r'\boracle\b', r'\bmysql\b', r'\bpostgres\b', r'\bpostgresql\b',
        r'\bmssql\b', r'\bms sql\b', r'\bdb2\b', r'\badabas\b',
        r'\bmongodb\b', r'\bcassandra\b', r'\bred\s*is\b', r'\belasticsearch\b',
        r'\bsqlite\b', r'\bmariadb\b', r'\bsybase\b', r'\bt-sql\b',
    ],
    'cloud_platform': [
        r'\bazure\b', r'\baws\b', r'\bgcp\b', r'\bgoogle cloud\b',
        r'\bamazon web\b', r'\bs3\b', r'\bec2\b', r'\blambda\b',
        r'\bzscaler\b', r'\bcloudflare\b', r'\bheroku\b', r'\bdigitalocean\b',
    ],
    'virtualization': [
        r'\bvmware\b', r'\bhyper-v\b', r'\bxenserver\b', r'\bproxmox\b',
        r'\bkvm\b', r'\bdocker\b', r'\bkubernetes\b', r'\bcontainer\b',
        r'\blxc\b', r'\bvirtualbox\b', r'\bvsphere\b', r'\bvcenter\b',
    ],
    'devops_tool': [
        r'\bansible\b', r'\bterraform\b', r'\bpuppet\b', r'\bchef\b',
        r'\bsalt\b', r'\bhelm\b', r'\bargocd\b', r'\bflux\b',
        r'\bpacker\b', r'\bvagrant\b', r'\bcapistrano\b',
    ],
    'ci_cd_tool': [
        r'\bjenkins\b', r'\bgitlab ci\b', r'\bgithub actions\b',
        r'\bazure devops\b', r'\bbamboo\b', r'\bcircle\s*ci\b',
        r'\btravis\b', r'\bteamcity\b', r'\boctopus\b', r'\bspinnaker\b',
    ],
    'monitoring_tool': [
        r'\bzabbix\b', r'\bnagios\b', r'\bgrafana\b', r'\bprometheus\b',
        r'\belastic\b', r'\bkibana\b', r'\bsplunk\b', r'\bdatadog\b',
        r'\bnewrelic\b', r'\bpagerduty\b', r'\bopsgenie\b', r'\bcontrolup\b',
    ],
    'framework': [
        r'\b\.net\b', r'\bspring\b', r'\bdjango\b', r'\breact\b',
        r'\bangular\b', r'\bvue\b', r'\blaravel\b', r'\brails\b',
        r'\bexpress\b', r'\bfastapi\b', r'\bflask\b', r'\bhibernate\b',
        r'\bwcf\b', r'\basp\.net\b', r'\bwinforms\b', r'\bwpf\b',
    ],
    'development_environment': [
        r'\bvisual studio\b', r'\bvscode\b', r'\beclipse\b', r'\bintellij\b',
        r'\bpycharm\b', r'\bwebstorm\b', r'\bnetbeans\b', r'\bxcode\b',
        r'\bandroid studio\b', r'\bvim\b', r'\bemacs\b', r'\batom\b',
        r'\bsublime\b', r'\bdatagrip\b', r'\bresharper\b',
    ],
    'version_control': [
        r'\bgit\b', r'\bsvn\b', r'\bsubversion\b', r'\bmercurial\b',
        r'\btfs\b', r'\bteam foundation\b', r'\bbitbucket\b', r'\bgithub\b',
        r'\bgitlab\b', r'\bendevor\b', r'\bcvs\b', r'\bperforce\b',
    ],
    'testing_tool': [
        r'\bjunit\b', r'\bselenium\b', r'\bpostman\b', r'\bcypress\b',
        r'\bpytest\b', r'\bnunit\b', r'\bxunit\b', r'\bmoq\b',
        r'\bsonarqube\b', r'\bfxcop\b', r'\bstylecop\b', r'\bjmeter\b',
    ],
    'methodology': [
        r'\bscrum\b', r'\bkanban\b', r'\bagile\b', r'\bitil\b',
        r'\bprince2\b', r'\bsafe\b', r'\bdevops\b', r'\blean\b',
        r'\bsix sigma\b', r'\bwaterfall\b', r'\bv-modell\b',
    ],
    'project_management': [
        r'\bjira\b', r'\bconfluence\b', r'\bms project\b', r'\bservicenow\b',
        r'\basana\b', r'\btrello\b', r'\bmonday\b', r'\bbasecamp\b',
        r'\btopdesk\b', r'\bfreshdesk\b', r'\bzendesk\b',
    ],
    'identity_management': [
        r'\bactive directory\b', r'\bldap\b', r'\bradius\b', r'\bfortiauth\b',
        r'\bfortitoken\b', r'\boauth\b', r'\bsaml\b', r'\boidc\b',
        r'\bkeycloak\b', r'\bokta\b', r'\bazure ad\b', r'\bpam\b',
    ],
    'business_software': [
        r'\bsap\b', r'\bms office\b', r'\boffice 365\b', r'\bdynamics\b',
        r'\bsalesforce\b', r'\btopdesk\b', r'\bservicenow\b',
        r'\bsharepoi?nt\b', r'\blotus\b', r'\bnotes\b',
    ],
    'communication_tool': [
        r'\bteams\b', r'\bslack\b', r'\bzoom\b', r'\bwebex\b',
        r'\bskype\b', r'\bmattermost\b', r'\bdiscord\b', r'\brocket\b',
        r'\bemail\b', r'\boutlook\b',
    ],
    'documentation_tool': [
        r'\bconfluence\b', r'\bwiki\b', r'\bsharepoint\b', r'\bnotion\b',
        r'\breadthedocs\b', r'\bsphinx\b', r'\bdoxygen\b', r'\bmarkdown\b',
    ],
    'data_format': [
        r'\bjson\b', r'\bxml\b', r'\byaml\b', r'\bcsv\b', r'\bedi\b',
        r'\bprotobuf\b', r'\bavro\b', r'\bparquet\b', r'\bxsl\b',
        r'\bxslt\b', r'\bhtml\b', r'\bxmlfo\b',
    ],
    'data_management': [
        r'\betl\b', r'\bdata warehouse\b', r'\bdatawarehouse\b',
        r'\bdata lake\b', r'\bbig data\b', r'\bspark\b', r'\bhadoop\b',
        r'\bkafka\b', r'\bairflow\b', r'\bnifi\b', r'\bssis\b',
    ],
    'architecture_pattern': [
        r'\bmicroservice\b', r'\bsoa\b', r'\brest\b', r'\bapi\b',
        r'\bevent.driven\b', r'\bcqrs\b', r'\bddd\b', r'\bhigh availability\b',
        r'\bzero trust\b', r'\bmesh\b', r'\bserverless\b',
    ],
    'special_concept': [
        r'\bgmp\b', r'\biso\b', r'\bfda\b', r'\bhipaa\b', r'\bgdpr\b',
        r'\bdsgvo\b', r'\bpci\b', r'\bsox\b', r'\bcobit\b', r'\bnist\b',
    ],
    'soft_skill': [
        r'\bteamleitung\b', r'\bprojektleitung\b', r'\bführung\b',
        r'\bcoaching\b', r'\bmentoring\b', r'\bpräsentation\b',
        r'\bverhandlung\b', r'\bkommunikation\b', r'\bteamwork\b',
    ],
}


class PreSkillClassifier:
    """
    Regelbasierte Vorklassifizierung von Skill-Blöcken.
    Läuft vor dem LLM-Call in block_labeler._stage2_skills().
    """

    def __init__(self):
        # Kompilierte Regex für Content-Map
        self._content_patterns = {
            cat: [re.compile(p, re.IGNORECASE) for p in patterns]
            for cat, patterns in CONTENT_MAP.items()
        }
        logger.info("PreSkillClassifier initialisiert")

    def classify(self, groups) -> Dict[int, Optional[str]]:
        """
        Klassifiziert Skill-Blöcke regelbasiert.

        Rückgabe: Dict[group_index, category_key | None]
        None = nicht erkannt → LLM nötig
        """
        result = {}
        for g in groups:
            cat = self._classify_group(g)
            result[g.index] = cat
            if cat:
                logger.debug(f"  PreSkill G{g.index:02d} → {cat} (regelbasiert)")
            else:
                logger.debug(f"  PreSkill G{g.index:02d} → unbekannt → LLM")
        return result

    def _classify_group(self, g) -> Optional[str]:
        """Klassifiziert einen einzelnen Block."""

        # Überschrift extrahieren (erster Span, typisch fett/groß)
        heading = self._get_heading(g)
        text    = g.text.lower()

        # Stufe 1: Überschriften-Match
        if heading:
            cat = self._match_heading(heading)
            if cat:
                return cat

        # Stufe 2: Inhalt-Match
        cat = self._match_content(text)
        if cat:
            return cat

        return None

    def _get_heading(self, g) -> str:
        """Extrahiert die Überschrift eines Blocks (erster Span)."""
        try:
            for block in g.blocks:
                for span in block.spans:
                    text = span.text.strip()
                    if text and len(text) > 2:
                        return text.lower()
        except Exception:
            pass
        # Fallback: erste 50 Zeichen des Block-Texts
        return g.text[:50].lower() if g.text else ''

    def _match_heading(self, heading: str) -> Optional[str]:
        """Prüft Überschrift gegen HEADING_MAP."""
        for cat, keywords in HEADING_MAP.items():
            for kw in keywords:
                if kw in heading:
                    return cat
        return None

    def _match_content(self, text: str) -> Optional[str]:
        """
        Prüft Block-Inhalt gegen CONTENT_MAP.
        Mindestens 2 Treffer für eine Kategorie nötig (Vermeidung False Positives).
        """
        scores = {}
        for cat, patterns in self._content_patterns.items():
            hits = sum(1 for p in patterns if p.search(text))
            if hits >= 2:
                scores[cat] = hits

        if not scores:
            return None

        # Kategorie mit den meisten Treffern
        return max(scores, key=scores.get)

    def get_unclassified(self, groups, classified: Dict) -> list:
        """Gibt Blöcke zurück die nicht regelbasiert erkannt wurden."""
        return [g for g in groups if not classified.get(g.index)]


# Singleton
pre_skill_classifier = PreSkillClassifier()
