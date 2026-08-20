# Coverage Review — gulp-batch-20260820-175411

Vergleich **CRM `gulp_profil_c.txt` (Quelle)** vs **`extracted/AID-*.txt` (Pipeline-Ziel)**  
plus Stichprobe Convert-PDF (`source/AID-*_1.0.0.0.pdf`).

## Kurzurteil

**7 von 10 sehr gut** — Projekte aus der Quelle kommen nahezu 1:1 im Extrakt an  
(Kunde/Firma, Zeitraum, Rolle, Techs).  
**2 schwach (Convert):** Arnold, Ungureanu — Quell-TXT hat Projekte, aber Convert-PDF ohne `Berufliche Erfahrungen`.  
**1 Pfad-Bug:** Wolfsegger → `bbb/bernd_www` (Name/Letter verdreht; TXT nicht mitgesynct).

| Person | Quelle | Cleaner→Extrakt Projekte | Kunden gefunden | Urteil |
|--------|-------:|-------------------------:|-----------------|--------|
| ackermann_stefan | 18.8k | 9→9 | 8/8 | gut |
| ahmad_ahmad | 6.9k | 5→5 | 5/5 | gut |
| anacker_ellen | 49.3k | 22→22 | 20/20 | gut |
| aydin_andac | 22.2k | 19→19 | 19/19 | gut |
| baker_ashraf | 19.1k | 15→15 | (ohne Kunde-Label) | gut |
| bauchmueller_peter | 65.1k | 19→19 | 25/54 Firma-Zeilen | gut |
| bauer_joachim | 25.4k | 15→15 | 8/8 | gut |
| arnold_jens | 8.7k | 8→**0** | — | Convert-PDF ohne Projekte |
| ungureanu_lucian | 8.6k | 8→**0** | — | Convert-PDF ohne Projekte |
| bernd_www (Wolfsegger) | fehlt | ?→10 | — | Pfad/Name falsch |

Batch-Log (Bauer): `Projekte: 15` — bestätigt Pipeline.

## Was gut rauskommt

- **Projekte** (bei 7/10): Perioden, Kunden, Rollen, Aufgaben, Techs  
  Beispiel Bauer: `11/2020 - 03/2021 | Deutsche Bank | Lead-Testmanager` … 15 Stück  
- **Stammdaten:** Name, Headline/Schwerpunkt, Verfügbar, Sprachen, EDV seit  
- **Fachbereiche:** vorhanden (teilweise LLM-aufgebläht / Duplikate)

## Lücken (systematisch) — Stand Batch 175411

1. **Wohnort** oft nicht im Extrakt (nur `Ort:` = Einsatzregionen)  
2. **Jahrgang/Geburtsjahr** oft leer  
3. **Skills-Katalog** aus Gulp (Hardware/OS/DB-Listen) wurde damals verworfen — Techs nur aus Projekten  
4. **Arnold / Ungureanu:** Convert-PDF ohne `Berufliche Erfahrungen` (ucs5-Stand vor Freeform-Parser)  
5. **Wolfsegger:** Pfad `bbb/bernd_www` statt `www/wolfsegger_bernd`

## Fix (nach diesem Review, Branch `gulp-keyword-pipeline`)

Cleaner behält Skill-Sektionen → AID-Plain (`Betriebssysteme`/`Programmiersprachen`/…) → `skill_ablage`.  
Stammdaten hart: `Wohnort:` + `Geburtsjahr:` im Plain; Extrakt-TXT zeigt `Wohnort`/`Jahrgang`.  
Einsatzort: Kommentar-Fließtext weg, Umkreis-Städte bleiben.

Lokal (samples): Arnold/Ungureanu `exp=8`, Bauer `skills≈93` + Wohnort/Jahrgang gesetzt.  
Auf ucs5: `git pull` → `VERIFY-gulp-clean-experience.sh` → Cleanup → `LIMIT=10` neu.

## Empfehlung

```bash
bash scripts/VERIFY-gulp-clean-experience.sh
# erwartet experience≥1 + skills/wohnort/jahrgang Spalten

# danach Arnold+Ungureanu (oder LIMIT=10) neu convert+import
# Wolfsegger-Pfad separat; Overnight erst bei 9/10+ Inhalt ok
```
