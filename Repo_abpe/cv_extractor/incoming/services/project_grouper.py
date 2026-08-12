"""
project_grouper.py - Gruppiert Lebenslauf-Zeilen automatisch in Projekte mit LLM
Erkennt selbstständig Muster: Datum, Firma, Rolle, etc.
"""

import json
import re
import requests
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field


@dataclass
class Project:
    """Ein Projekt aus der Berufserfahrung"""
    period: str = ""
    title: str = ""
    company: str = ""
    role: str = ""
    activities: List[str] = field(default_factory=list)
    technologies: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            "period": self.period,
            "title": self.title,
            "company": self.company,
            "role": self.role,
            "activities": self.activities,
            "technologies": self.technologies
        }


class ProjectGrouper:
    """
    Gruppiert Zeilen aus einem Lebenslauf automatisch in Projekte.
    Verwendet LLM zur Mustererkennung - keine harten Regeln.
    """
    
    def __init__(self, model: str = "qwen2.5:7b", ollama_url: str = "http://localhost:11434/api/generate"):
        self.model = model
        self.ollama_url = ollama_url
        self.timeout = 180
    
    def group(self, lines: List[str]) -> List[Project]:
        if not lines:
            return []
        
        prompt = self._build_prompt(lines)
        response = self._call_ollama(prompt)
        projects = self._parse_response(response)
        
        return projects
    
    def _build_prompt(self, lines: List[str]) -> str:
        """Baut den Prompt für das LLM - allgemein, nicht auf spezifisches PDF bezogen"""
        
        # Nimm alle Zeilen (max 150)
        relevant_lines = lines[:150]
        
        return f"""Analysiere die folgenden Zeilen aus einem Lebenslauf (Berufserfahrung).

Zeilen:
{chr(10).join([f'{i}: {line[:120]}' for i, line in enumerate(relevant_lines)])}

Aufgabe: Erkenne die einzelnen Berufserfahrungen/Projekte.

MERKMALE für einen Projekt-Beginn (eines davon reicht):
- Ein Datum (z.B. "11/2025 – dato", "01/2020 – 12/2021", "seit 2019", "2005-2010")
- Ein Firmenname (z.B. "Bank Hessen", "Siemens", "Microsoft")
- Eine Positionsbezeichnung (z.B. "Projektleiter", "Entwickler")
- Ein Projektname

Sammle alle folgenden Zeilen bis zum nächsten Projekt-Beginn.

Extrahiere für jedes Projekt:
- period: Das Datum/der Zeitraum (wenn vorhanden)
- company: Firmenname/Kunde (wenn vorhanden)
- role: Position/Rolle (wenn vorhanden)
- title: Projektname/Titel (wenn vorhanden)
- activities: Aufgaben, Tätigkeiten, Beschreibungen (als Liste)
- technologies: Technologien, Tools, Frameworks (als Liste)

Gib NUR JSON zurück:
{{"experience": [{{"period": "", "company": "", "role": "", "title": "", "activities": [], "technologies": []}}]}}"""
    
    def _call_ollama(self, prompt: str) -> str:
        try:
            response = requests.post(
                self.ollama_url,
                json={"model": self.model, "prompt": prompt, "stream": False},
                timeout=self.timeout
            )
            if response.status_code == 200:
                return response.json().get('response', '')
            return ""
        except Exception as e:
            print(f"Ollama Exception: {e}")
            return ""
    
    def _parse_response(self, response: str) -> List[Project]:
        if not response:
            return []
        
        json_match = re.search(r'\{.*\}', response, re.DOTALL)
        if not json_match:
            print("Kein JSON in der Antwort gefunden")
            return []
        
        try:
            data = json.loads(json_match.group())
            projects = []
            for exp in data.get('experience', []):
                projects.append(Project(
                    period=exp.get('period', ''),
                    title=exp.get('title', ''),
                    company=exp.get('company', ''),
                    role=exp.get('role', ''),
                    activities=exp.get('activities', []),
                    technologies=exp.get('technologies', [])
                ))
            return projects
        except json.JSONDecodeError as e:
            print(f"JSON Parse Fehler: {e}")
            return []


project_grouper = ProjectGrouper()
