"""
Ollama-Integration für Matching und Textgenerierung
OPTIMIERT für bessere Extraktion und Media-Integration
"""
import json
import logging
import re
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from pathlib import Path

from django.conf import settings

from apps.ai_cv_processor.services import ollama_service

logger = logging.getLogger(__name__)


class OllamaMatcher:
    """Service für KI-gestütztes Matching und Textgenerierung"""

    # Prompt-Templates für verschiedene Anwendungsfälle
    PROMPT_TEMPLATES = {
        'project_analysis': """
Analysiere diese Projektanfrage für einen IT-Berater und extrahiere strukturierte Informationen:

{text}

EXTRAHIERE FOLGENDE INFORMATIONEN:
- titel: Kurzer, prägnanter Projekttitel (max. 10 Wörter)
- required_skills: Liste der zwingend benötigten Technologien/Skills
- preferred_skills: Liste der optionalen/gewünschten Skills
- min_experience: Minimale Berufserfahrung in Jahren (0 wenn nicht genannt)
- start_date: Gewünschter Starttermin (JJJJ-MM-TT Format, wenn genannt)
- duration_months: Gewünschte Projektdauer in Monaten
- location: Einsatzort (Stadt/Region)
- remote_possible: true/false (ob Remote möglich)
- workload_percent: Gewünschte Auslastung in Prozent
- rate_min: Minimaler Stundensatz (wenn genannt)
- rate_max: Maximaler Stundensatz (wenn genannt)
- rate_type: "hourly", "daily", oder "fixed"
- industry: Branche des Kunden
- project_type: Art des Projekts (Entwicklung, Beratung, Support, etc.)
- team_size: Teamgröße (wenn genannt)
- key_responsibilities: Liste der Hauptaufgaben
- required_certifications: Liste benötigter Zertifikate
- languages: Liste benötigter Sprachen mit Level

AUSGABE FORMAT:
Gib NUR das JSON-Objekt zurück, ohne Erklärungen oder Markdown.
""",

        'consultant_email': """
Erstelle eine persönliche E-Mail an einen IT-Berater für eine Projektanfrage.

PROJEKTDATEN:
- Titel: {projekt_titel}
- Beschreibung: {projekt_beschreibung}
- Start: {start}
- Dauer: {dauer} Monate
- Ort: {ort}
- Remote: {remote}
- Auslastung: {auslastung}%

BERATERDATEN:
- Name: {berater_name}
- Titel: {berater_titel}
- Skills: {berater_skills}
- Erfahrung: {erfahrung} Jahre

MATCH-INFORMATIONEN:
- Match-Score: {match_score}%
- Passende Skills: {match_skills}
- Besondere Stärken: {match_staerken}

AUFGABE:
Generiere eine professionelle, persönliche E-Mail mit:

1. Betreff: Kurz, prägnant (max. 10 Wörter)
2. Anrede: Persönlich mit korrekter Anrede (Frau/Herr)
3. Einleitung: Bezug auf das Projekt
4. Projektvorstellung: Kurze, ansprechende Beschreibung
5. Begründung: 2-3 Sätze, warum der Berater besonders gut passt
6. Details: Nennung der wichtigsten passenden Skills
7. Nächste Schritte: Bitte um Rückmeldung und Verfügbarkeitsprüfung
8. Abschluss: Freundliche Grußformel mit Kontaktdaten

STIL: Professionell, wertschätzend, nicht zu lang (max. 300 Wörter)
""",

        'client_offer': """
Erstelle ein professionelles Angebot an einen Kunden mit passenden Beratern.

KUNDE:
- Name: {kunde_name}
- Branche: {kunde_branche}

PROJEKT:
- Titel: {projekt_titel}
- Beschreibung: {projekt_beschreibung}
- Start: {start}
- Dauer: {dauer} Monate
- Ort: {ort}
- Remote: {remote}

GEFUNDENE BERATER:
{berater_liste}

AUFGABE:
Generiere ein überzeugendes Angebot mit:

1. Betreff: "Angebot: {projekt_titel}"
2. Einleitung: Bezug auf die Anfrage, Dank für das Interesse
3. Beratervorstellung: Jeden Berater kurz vorstellen (Name, Titel, Erfahrung)
4. Matching-Begründung: Pro Berater 2-3 Sätze, warum er/sie ideal passt
5. Highlights: Besondere Stärken und relevante Projekterfahrungen
6. Nächste Schritte: Interviews, Entscheidungsprozess, Zeitplan
7. Abschluss: Professionelle Grußformel, Kontaktdaten, Bereitschaft für Fragen

STIL: Überzeugend, strukturiert, professionell, max. 600 Wörter
""",

        'rejection_consultant': """
Erstelle eine wertschätzende Absage an einen Berater.

BERATER:
- Name: {berater_name}
- Projekt: {projekt_titel}
- Kunde: {kunde_name}
- Grund: {grund}

AUFGABE:
Generiere eine E-Mail mit:

1. Betreff: "Rückmeldung zu Projekt {projekt_titel}"
2. Einleitung: Dank für Interesse und Engagement
3. Information: Mitteilung der Entscheidung
4. Begründung: Kurze, ehrliche Erklärung des Grundes
5. Zukunft: Tür für zukünftige Projekte offen lassen
6. Abschluss: Freundliche Grüße, Kontaktdaten

STIL: Wertschätzend, professionell, nicht entmutigend
""",

        'rejection_client': """
Erstelle eine höfliche Absage an einen Kunden.

KUNDE:
- Name: {kunde_name}
- Projekt: {projekt_titel}
- Berater: {berater_name}
- Grund: {grund}
- Alternative: {alternative}

AUFGABE:
Generiere eine E-Mail mit:

1. Betreff: "Status zu Projekt {projekt_titel}"
2. Einleitung: Bezug auf die Anfrage
3. Information: Mitteilung, dass der Berater nicht verfügbar ist
4. Begründung: Kurze Erklärung (falls angemessen)
5. Alternativen: Angebot weiterer passender Kandidaten
6. Nächste Schritte: Frage nach weiteren Anforderungen
7. Abschluss: Freundliche Grüße, Kontaktdaten

STIL: Höflich, lösungsorientiert, professionell
""",

        'skill_extraction': """
Extrahiere alle Skills aus diesem Text und kategorisiere sie:

{text}

EXTRAHIERE:
- programming_languages: Programmiersprachen
- frameworks: Frameworks und Bibliotheken
- databases: Datenbanken
- cloud_platforms: Cloud-Plattformen
- devops_tools: DevOps-Tools
- methodologies: Methodiken (Agile, Scrum, etc.)
- certifications: Zertifikate
- soft_skills: Soft Skills
- languages: Sprachkenntnisse mit Level

AUSGABE FORMAT:
{{
    "programming_languages": ["Python", "Java"],
    "frameworks": ["Django", "Spring"],
    "databases": ["PostgreSQL"],
    "cloud_platforms": ["AWS"],
    "devops_tools": ["Docker"],
    "methodologies": ["Agile"],
    "certifications": ["AWS Certified"],
    "soft_skills": ["Teamfähigkeit"],
    "languages": [{{"language": "Deutsch", "level": "Muttersprache"}}]
}}

NUR JSON!
""",

        'experience_extraction': """
Extrahiere die Berufserfahrung aus diesem Text:

{text}

EXTRAHIERE JEDE POSITION MIT:
- role: Position/Rolle
- company: Firma/Arbeitgeber
- start_date: Startdatum (YYYY-MM)
- end_date: Enddatum (YYYY-MM oder "present")
- duration_months: Dauer in Monaten
- description: Kurze Beschreibung
- technologies_used: Eingesetzte Technologien
- achievements: Wichtigste Erfolge (max. 3)

AUSGABE FORMAT: Array von Positionen
""",
    }

    def __init__(self):
        """Initialisiert den OllamaMatcher"""
        logger.info("✅ OllamaMatcher initialisiert mit erweiterten Templates")

    def analyze_project_request(self, text: str, save_result: bool = False, 
                               project_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Analysiert eine Projektanfrage und extrahiert strukturierte Daten

        Args:
            text: Originaler Anfrage-Text
            save_result: Ob Ergebnis in Media-Struktur gespeichert werden soll
            project_id: Projekt-ID für Speicherung

        Returns:
            Dict mit extrahierten Daten
        """
        prompt = self.PROMPT_TEMPLATES['project_analysis'].format(text=text)

        try:
            result = ollama_service.extract_cv_data(prompt, mode="full")

            if result.success:
                data = result.data
                
                # Daten validieren und ergänzen
                data = self._validate_project_analysis(data)
                
                # Optional speichern
                if save_result:
                    storage = self._save_analysis_result(data, project_id)
                    data['_storage'] = storage
                
                logger.info(f"✅ Projektanalyse erfolgreich: {len(data.get('required_skills', []))} Skills gefunden")
                return data
            else:
                logger.error(f"❌ Ollama-Fehler bei Projektanalyse: {result.error}")
                return self._get_empty_project_analysis()

        except Exception as e:
            logger.exception(f"❌ Fehler bei Projektanalyse: {e}")
            return self._get_empty_project_analysis()

    def _validate_project_analysis(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validiert und ergänzt die Projektdaten"""
        defaults = {
            'titel': 'Unbekanntes Projekt',
            'required_skills': [],
            'preferred_skills': [],
            'min_experience': 0,
            'start_date': None,
            'duration_months': 0,
            'location': '',
            'remote_possible': True,
            'workload_percent': 100,
            'rate_min': 0,
            'rate_max': 0,
            'rate_type': 'hourly',
            'industry': '',
            'project_type': '',
            'team_size': 0,
            'key_responsibilities': [],
            'required_certifications': [],
            'languages': [],
        }
        
        # Defaults für fehlende Felder einsetzen
        for key, default_value in defaults.items():
            if key not in data or data[key] is None:
                data[key] = default_value
        
        return data

    def _get_empty_project_analysis(self) -> Dict[str, Any]:
        """Gibt leere Projektanalyse zurück"""
        return {
            'titel': 'Analyse fehlgeschlagen',
            'required_skills': [],
            'preferred_skills': [],
            'min_experience': 0,
            'start_date': None,
            'duration_months': 0,
            'location': '',
            'remote_possible': True,
            'workload_percent': 100,
            'rate_min': 0,
            'rate_max': 0,
            'rate_type': 'hourly',
            'error': True
        }

    def _save_analysis_result(self, data: Dict[str, Any], project_id: Optional[str]) -> Dict[str, str]:
        """
        Speichert Analyse-Ergebnis in Media-Struktur
        media/cv/extracted/project_analysis/{project_id}_analysis.json
        """
        try:
            import uuid
            from pathlib import Path
            import json
            
            if not project_id:
                project_id = f"analysis_{uuid.uuid4().hex[:8]}"
            
            # Verzeichnis anlegen
            analysis_dir = Path(settings.MEDIA_ROOT) / 'cv' / 'extracted' / 'project_analysis'
            analysis_dir.mkdir(parents=True, exist_ok=True)
            
            # Datei speichern
            filename = f"{project_id}_analysis.json"
            filepath = analysis_dir / filename
            
            save_data = {
                'project_id': project_id,
                'analyzed_at': datetime.now().isoformat(),
                'analysis': data,
                'model': 'qwen2.5:7b',
            }
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(save_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"💾 Analyse gespeichert: {filepath}")
            
            return {
                'path': str(filepath),
                'url': f"/media/cv/extracted/project_analysis/{filename}",
            }
            
        except Exception as e:
            logger.error(f"❌ Fehler beim Speichern der Analyse: {e}")
            return {}

    def generate_consultant_email(self, project: Any, consultant: Any, 
                                  match_details: Dict, save_result: bool = False) -> str:
        """
        Generiert personalisierte E-Mail an Berater

        Args:
            project: ProjectRequest-Objekt
            consultant: Consultant-Objekt
            match_details: Details zum Match (Score, passende Skills)
            save_result: Ob E-Mail gespeichert werden soll

        Returns:
            Generierter E-Mail-Text
        """
        # Match-Punkte aus den Details extrahieren
        matching_skills = match_details.get('matching_skills', [])
        missing_skills = match_details.get('missing_skills', [])
        
        # Besondere Stärken identifizieren
        staerken = []
        if matching_skills:
            top_skills = matching_skills[:3]
            staerken.append(f"Starke Expertise in: {', '.join(top_skills)}")
        
        if missing_skills:
            staerken.append(f"Kann fehlende Skills ({', '.join(missing_skills[:2])}) schnell lernen")
        
        # Anrede bestimmen
        anrede = self._get_anrede(consultant)
        
        prompt = self.PROMPT_TEMPLATES['consultant_email'].format(
            projekt_titel=project.title,
            projekt_beschreibung=project.description[:300],
            start=project.start_date or "kurzfristig",
            dauer=project.duration_months,
            ort=project.location or "Remote möglich",
            remote="Ja" if project.remote_possible else "Nein",
            auslastung=project.workload_percent,
            berater_name=f"{anrede} {consultant.last_name}",
            berater_titel=consultant.title or "Berater",
            berater_skills=', '.join(consultant.skills_list[:8]),
            erfahrung=consultant.experience_years,
            match_score=int(match_details.get('score', 0) * 100),
            match_skills=', '.join(matching_skills[:5]),
            match_staerken='\n'.join(staerken) if staerken else "Profil passt sehr gut"
        )

        try:
            result = ollama_service.extract_cv_data(prompt, mode="quick", max_tokens=800)

            if result.success:
                email_text = result.raw_response
                
                # Optional speichern
                if save_result:
                    self._save_email_to_media(email_text, project, consultant, 'consultant')
                
                return email_text
            else:
                logger.error(f"❌ Ollama-Fehler bei E-Mail-Generierung: {result.error}")
                return self._get_fallback_consultant_email(project, consultant, match_details)

        except Exception as e:
            logger.exception(f"❌ Fehler bei E-Mail-Generierung: {e}")
            return self._get_fallback_consultant_email(project, consultant, match_details)

    def _get_anrede(self, consultant: Any) -> str:
        """Ermittelt korrekte Anrede"""
        if consultant.first_name and consultant.first_name.lower() in ['frau', 'fr']:
            return "Frau"
        # Hier könnte später eine Logik für Geschlechtserkennung eingebaut werden
        return "Herr"

    def _get_fallback_consultant_email(self, project: Any, consultant: Any, 
                                       match_details: Dict) -> str:
        """Fallback-E-Mail wenn Ollama nicht verfügbar"""
        anrede = self._get_anrede(consultant)
        matching_skills = ', '.join(match_details.get('matching_skills', [])[:5])
        
        return f"""Sehr geehrte/r {anrede} {consultant.last_name},

für einen unserer Kunden benötigen wir einen erfahrenen Berater:

{project.title} – {project.location or 'Remote'} – {project.start_date or 'ab sofort'} – {project.duration_months} Monate

{project.description[:300]}

Ihr Profil passt sehr gut (Match: {int(match_details.get('score', 0) * 100)}%). 
Besonders Ihre Kenntnisse in: {matching_skills}

Wenn Sie Interesse haben, freue ich mich über Ihre Rückmeldung.

Mit freundlichen Grüßen

[Ihr Name]
abcona e. K.
"""

    def generate_client_offer(self, project: Any, consultants: List[Any], 
                              matches: List[Dict], save_result: bool = False) -> str:
        """
        Generiert Matching-Angebot an Kunden mit mehreren Beratern

        Args:
            project: ProjectRequest-Objekt
            consultants: Liste von Consultant-Objekten
            matches: Liste von Match-Details pro Berater
            save_result: Ob Angebot gespeichert werden soll

        Returns:
            Generierter Angebots-Text
        """
        # Berater-Liste für Prompt erstellen
        berater_liste = ""
        for i, (consultant, match) in enumerate(zip(consultants, matches), 1):
            matching_skills = match.get('matching_skills', [])
            skills_text = ', '.join(matching_skills[:5]) if matching_skills else ', '.join(consultant.skills_list[:3])
            
            berater_liste += f"""
Berater {i}: {consultant.first_name} {consultant.last_name}
- Titel: {consultant.title}
- Match: {match.get('score', 0)*100:.0f}%
- Skills: {skills_text}
- Erfahrung: {consultant.experience_years} Jahre
- Verfügbar: {consultant.available_from or 'kurzfristig'}
- Satz: {consultant.hourly_rate_min or '?'}-{consultant.hourly_rate_max or '?'}€/h
"""

        prompt = self.PROMPT_TEMPLATES['client_offer'].format(
            kunde_name=project.customer_name,
            kunde_branche="",
            projekt_titel=project.title,
            projekt_beschreibung=project.description[:300],
            start=project.start_date or "kurzfristig",
            dauer=project.duration_months,
            ort=project.location or "Remote möglich",
            remote="Ja" if project.remote_possible else "Nein",
            berater_liste=berater_liste
        )

        try:
            result = ollama_service.extract_cv_data(prompt, mode="full", max_tokens=1500)

            if result.success:
                offer_text = result.raw_response
                
                # Optional speichern
                if save_result:
                    self._save_email_to_media(offer_text, project, None, 'client_offer')
                
                return offer_text
            else:
                logger.error(f"❌ Ollama-Fehler bei Angebots-Generierung: {result.error}")
                return self._get_fallback_client_offer(project, consultants, matches)

        except Exception as e:
            logger.exception(f"❌ Fehler bei Angebots-Generierung: {e}")
            return self._get_fallback_client_offer(project, consultants, matches)

    def _get_fallback_client_offer(self, project: Any, consultants: List[Any], 
                                   matches: List[Dict]) -> str:
        """Fallback-Angebot wenn Ollama nicht verfügbar"""
        berater_text = ""
        for consultant, match in zip(consultants, matches):
            berater_text += f"\n• {consultant.full_name} - {consultant.title}\n"
            berater_text += f"  Match: {match.get('score', 0)*100:.0f}% - Skills: {', '.join(consultant.skills_list[:5])}\n"

        return f"""Sehr geehrte/r {project.customer_contact_person or project.customer_name},

für Ihr Projekt **„{project.title}“** (Projekt-ID {project.project_number}) reiche ich Ihnen folgende Berater ein:

{berater_text}
Alle Berater haben langjährige Erfahrung in relevanten Technologien und sind kurzfristig verfügbar.

**Nächste Schritte:**
• Ich sende Ihnen auf Wunsch gerne die vollständigen Profile
• Wir können kurzfristig Interviews koordinieren

Mit freundlichen Grüßen

[Ihr Name]
abcona e. K.
"""

    def generate_rejection(self, project: Any, consultant: Any, reason: str, 
                          recipient_type: str = 'consultant', save_result: bool = False) -> str:
        """
        Generiert Absage-E-Mail

        Args:
            project: ProjectRequest-Objekt
            consultant: Consultant-Objekt
            reason: Absagegrund
            recipient_type: 'consultant' oder 'client'
            save_result: Ob Absage gespeichert werden soll

        Returns:
            Generierter Absage-Text
        """
        template = 'rejection_consultant' if recipient_type == 'consultant' else 'rejection_client'
        
        if recipient_type == 'consultant':
            prompt = self.PROMPT_TEMPLATES['rejection_consultant'].format(
                berater_name=f"{consultant.first_name} {consultant.last_name}",
                projekt_titel=project.title,
                kunde_name=project.customer_name,
                grund=reason
            )
        else:
            # Für Kunde: alternative Berater vorschlagen
            from ..models import ProjectConsultant
            alternatives = ProjectConsultant.objects.filter(
                project=project
            ).exclude(consultant=consultant).select_related('consultant')[:3]
            
            alternative_text = ""
            if alternatives:
                alternative_text = "Alternativ könnte ich Ihnen folgende Berater vorschlagen:\n"
                for alt in alternatives:
                    alternative_text += f"• {alt.consultant.full_name} (Match: {alt.match_score*100:.0f}%)\n"
            
            prompt = self.PROMPT_TEMPLATES['rejection_client'].format(
                kunde_name=project.customer_name,
                projekt_titel=project.title,
                berater_name=f"{consultant.first_name} {consultant.last_name}",
                grund=reason,
                alternative=alternative_text or "Ich suche gerne nach alternativen Kandidaten."
            )

        try:
            result = ollama_service.extract_cv_data(prompt, mode="quick", max_tokens=500)

            if result.success:
                rejection_text = result.raw_response
                
                # Optional speichern
                if save_result:
                    self._save_email_to_media(rejection_text, project, consultant, 
                                            f'rejection_{recipient_type}')
                
                return rejection_text
            else:
                logger.error(f"❌ Ollama-Fehler bei Absage-Generierung: {result.error}")
                return self._get_fallback_rejection(project, consultant, reason, recipient_type)

        except Exception as e:
            logger.exception(f"❌ Fehler bei Absage-Generierung: {e}")
            return self._get_fallback_rejection(project, consultant, reason, recipient_type)

    def _get_fallback_rejection(self, project: Any, consultant: Any, reason: str,
                                recipient_type: str) -> str:
        """Fallback-Absage wenn Ollama nicht verfügbar"""
        if recipient_type == 'consultant':
            return f"""Sehr geehrte/r {consultant.full_name},

vielen Dank für Ihr Interesse am Projekt **„{project.title}“**.

Der Kunde hat sich leider für einen anderen Kandidaten entschieden.
Grund: {reason}

Wir kommen gerne bei passenden Projekten wieder auf Sie zu.

Mit freundlichen Grüßen

[Ihr Name]
abcona e. K.
"""
        else:
            return f"""Sehr geehrte/r {project.customer_contact_person or project.customer_name},

zu Ihrem Projekt **„{project.title}“** habe ich folgende Information:

Der Berater {consultant.full_name} steht für dieses Projekt leider nicht zur Verfügung.
Grund: {reason}

Ich suche gerne nach alternativen Kandidaten für Sie.

Mit freundlichen Grüßen

[Ihr Name]
abcona e. K.
"""

    def _save_email_to_media(self, email_text: str, project: Any, 
                              consultant: Optional[Any], email_type: str) -> None:
        """
        Speichert generierte E-Mail in Media-Struktur
        media/email/generated/{email_type}_{project_id}_{consultant_id}.txt
        """
        try:
            from pathlib import Path
            import uuid
            
            email_dir = Path(settings.MEDIA_ROOT) / 'email' / 'generated'
            email_dir.mkdir(parents=True, exist_ok=True)
            
            filename = f"{email_type}_{project.project_number}"
            if consultant:
                filename += f"_{consultant.last_name}"
            filename += f"_{uuid.uuid4().hex[:4]}.txt"
            
            filepath = email_dir / filename
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(email_text)
            
            logger.info(f"💾 E-Mail gespeichert: {filepath}")
            
        except Exception as e:
            logger.error(f"❌ Fehler beim Speichern der E-Mail: {e}")

    def extract_skills_from_text(self, text: str) -> Dict[str, Any]:
        """
        Extrahiert Skills aus beliebigem Text

        Args:
            text: Text mit Skills

        Returns:
            Kategorisierte Skills
        """
        prompt = self.PROMPT_TEMPLATES['skill_extraction'].format(text=text[:3000])

        try:
            result = ollama_service.extract_cv_data(prompt, mode="skills_only")
            
            if result.success:
                return result.data
            else:
                logger.error(f"❌ Ollama-Fehler bei Skill-Extraktion: {result.error}")
                return {}

        except Exception as e:
            logger.exception(f"❌ Fehler bei Skill-Extraktion: {e}")
            return {}

    def extract_experience_from_text(self, text: str) -> List[Dict[str, Any]]:
        """
        Extrahiert Berufserfahrung aus Text

        Args:
            text: Text mit Berufserfahrung

        Returns:
            Liste von Erfahrungspositionen
        """
        prompt = self.PROMPT_TEMPLATES['experience_extraction'].format(text=text[:3000])

        try:
            result = ollama_service.extract_cv_data(prompt, mode="full")
            
            if result.success and isinstance(result.data, list):
                return result.data
            elif result.success and isinstance(result.data, dict):
                return result.data.get('experience', [])
            else:
                logger.error(f"❌ Ollama-Fehler bei Erfahrungs-Extraktion: {result.error}")
                return []

        except Exception as e:
            logger.exception(f"❌ Fehler bei Erfahrungs-Extraktion: {e}")
            return []

    def match_project_description(self, cv_text: str, project_description: str) -> Dict[str, Any]:
        """
        Vergleicht CV mit Projektbeschreibung und berechnet Match

        Args:
            cv_text: CV-Text
            project_description: Projektbeschreibung

        Returns:
            Dict mit Match-Analyse
        """
        prompt = f"""
Analysiere den folgenden Lebenslauf und die Projektbeschreibung und berechne den Match.

LEBENSLAUF:
{cv_text[:2000]}

PROJEKTBESCHREIBUNG:
{project_description[:1000]}

Extrahiere als JSON:
- match_score: Match-Score in Prozent (0-100)
- matching_skills: Liste der Skills, die im Lebenslauf vorkommen und im Projekt benötigt werden
- missing_skills: Liste der im Projekt benötigten Skills, die im Lebenslauf fehlen
- experience_match: Erfahrungs-Match (1-5)
- role_match: Rollen-Match (1-5)
- recommendations: Empfehlungen für nächste Schritte
- summary: Kurze Zusammenfassung des Matches (max. 100 Wörter)

NUR JSON!
"""

        try:
            result = ollama_service.extract_cv_data(prompt, mode="full")

            if result.success:
                return result.data
            else:
                logger.error(f"❌ Ollama-Fehler bei Match-Analyse: {result.error}")
                return {
                    'match_score': 0,
                    'matching_skills': [],
                    'missing_skills': [],
                    'experience_match': 0,
                    'role_match': 0,
                    'error': True
                }

        except Exception as e:
            logger.exception(f"❌ Fehler bei Match-Analyse: {e}")
            return {'error': True, 'message': str(e)}


# Singleton-Instanz
ollama_matcher = OllamaMatcher()
