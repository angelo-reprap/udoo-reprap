# ABpE Shaduler — Konzept Reiter "Posteingang"

**Ablage: `apps/abpe_shaduler/docs/POSTEINGANG_KONZEPT.md` · Stand 04.08.2026**
Ergänzt Kap. 9 der Architektur_zielvorlage.md um die Detail-Begründung.

---

## 1. Prinzip: Lese-Überblick, KEIN E-Mail-Client

Der Posteingang beantwortet beim Morgenkaffee genau eine Frage:
**"Was ist an elektronischer Post reingekommen, und was muss daraus werden?"**

Bewusst NICHT enthalten (bleibt Outlook): Ordner sortieren/verschieben,
Threading, Kalender-Einladungen, Löschen, Anhänge-Verwaltung, Regeln.
Diese Abgrenzung ist der Grund, warum der Reiter in 2–4 Sessions baubar
ist statt in Monaten — und warum er nie zum Pflegefall wird.

Kaffee-Reihenfolge im Modul: Aufgaben → Kalender → **Posteingang** →
Radar Anfragen → Radar Berater.

## 2. Datenfluss

### 2.1 Abholen
- Celery-Task `shaduler_inbox_poll`, registriert als `SchedulerJob`
  (scheduler_client, Takt 2 Min)
- IMAP-Verbindung je Postfach (vertrieb@, angelo@, …) — Konfiguration
  aus **`ingest_email.EmailImportConfig`** (existiert, gleiche Infrastruktur
  wie der CV-Import)
- **Read-only**: nur Header (Absender, Betreff, Datum) + ~200 Zeichen
  Vorschau. KEIN \\Seen-Flag setzen, nichts verschieben — Outlook sieht
  das Postfach unverändert
- "neu"-Status ist ein **ABpE-eigenes** Gelesen-Feld (unabhängig vom
  IMAP-Flag), gesetzt beim Öffnen/Bearbeiten im Portal

### 2.2 Zuordnen
- Absenderadresse → **`CrmEmailAddrBeanRel`** (SuiteCRM-Spiegel) →
  Person/Firma → Anzeige "K. Brandt · 🔗 Berater · Anfrage #2477"
- Anfrage-Zuordnung Stufe 1: letzter offener Vorgang des Kontakts im
  Matching. Später optional: Betreff-Erkennung (#2477 im Subject)
- Kein Treffer → Mail erscheint ohne Verknüpfung (z.B. Börsen-Alerts;
  diese laufen parallel ohnehin in den Radar)

### 2.3 Anzeigen
- `api/inbox/`: Liste gruppiert nach Postfach, Ungelesen-Zähler
- Reiter-Badge aus `api/stats/`
- Suche über Alt-Mails: NICHT hier bauen — dafür existiert der
  Elasticsearch-Mail-Index (automail/ingest_email)

## 3. Die vier Aktionen pro Mail

| Button | Verdrahtung | Bemerkung |
|---|---|---|
| **Aufgabe erzeugen** | `api/inbox/<id>/aufgabe/` → `aufgaben_service.erstellen()` mit quelle='mail', ref aus CRM-Zuordnung, Art wählbar (Rückruf/WV/E-Mail); Mail wird Vorgangs-Auszug im Popup; Aktivitaet-Eintrag | **Der eigentliche Gewinn**: aus jeder Mail ein Queue-Eintrag statt eines offenen Outlook-Fensters |
| Im Matching öffnen | Deeplink `/matching/?request=<id>` | trivial |
| Antworten (Email Studio) | Email Studio mit Empfänger + Vorlage vorbelegt; Versand über bestehenden Sendeweg; Aktivitaet-Eintrag | kein eigener Composer |
| In Outlook öffnen | Stufe 1: Outlook in den Vordergrund / `mailto:` für Antwort | Ehrliche Grenze: Deeplink auf GENAU diese Mail ist ohne Exchange/Graph nicht zuverlässig — Erwartung so festgehalten |

## 4. Vorhanden vs. zu bauen

| Baustein | Status |
|---|---|
| IMAP-Zugänge + Konfig (`EmailImportConfig`), Mail-Models | ✅ vorhanden (ingest_email) |
| Absender→Person/Firma (`CrmEmailAddrBeanRel`) | ✅ vorhanden (abpe_crm) |
| ES-Index für Mail-Suche | ✅ vorhanden |
| Email Studio als Antwort-Weg | ✅ vorhanden |
| `inbox_service` (Header-Leser, ABpE-Gelesen-Status, CRM-Zuordnung) | 🔶 bauen |
| `api/inbox/` + `api/inbox/<id>/aufgabe/` + Tab-Frontend | 🔶 bauen (Gerüst liegt) |
| `shaduler_inbox_poll` als SchedulerJob | 🔶 registrieren (Command existiert) |
| Betreff-basierte Vorgangs-Erkennung | ⬜ später, optional |
| Exchange/Graph-Deeplink auf Einzelmail | ⬜ später, optional |

## 5. Leitplanken

- Niemals schreibend aufs IMAP-Postfach (kein Seen, kein Move, kein Delete)
- Zugangsdaten nur aus EmailImportConfig — keine zweite Credential-Ablage
- Vorschau-Text max. ~200 Zeichen speichern; Volltext bleibt auf dem
  Server bzw. im ES-Index
- Alle UI-Texte über `_t()` (i18n-Schlüsselraum `sh.inbox_*`)

**Kurzfassung:** Der Posteingang erfindet nichts — er verdrahtet drei
bestehende Systeme (IMAP-Import, CRM-Zuordnung, Email Studio) zu einer
Leseansicht mit einem einzigen neuen Verhalten: **Mail → Aufgabe.**
