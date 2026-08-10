# DeepSeek / KI im Shaduler

## Was sagt die Architektur?

| Stelle | Rolle | Stufe |
|--------|--------|--------|
| Kap. 5.5 i18n | Restsprachen via DeepSeek-Lauf | V1.1 |
| Kap. 6 LLM-Service | Backend-Wahl Ollama/**DeepSeek** + Platzhalter | **V3** |
| Kap. 6 KI-Wizard | `abpe_ki_wiz` für Regeln | V3 |
| Kap. 7 V1 | Ollama direkt für Radar-Skills | V1/V2 |
| WhatsApp Business API | bewusst nicht | — |

## Was ist jetzt (V1-Anbindung)?

- `services/ki_client.py` — liest `settings.json` → `ai_models.deepseek` (gleicher Key wie CRM/ki_wiz)
- `POST /shaduler/api/ki/vorschlag/` — optionale Text-Empfehlung zur Aufgabe (kein Auto-Apply)
- Kern (Aufgaben/Ergebnis/Aktivität) läuft **ohne** DeepSeek

## Live prüfen

```bash
python -c "import json; print(bool(json.load(open('/opt/abpe/backend/settings.json'))['ai_models']['deepseek'].get('api_key')))"
```
