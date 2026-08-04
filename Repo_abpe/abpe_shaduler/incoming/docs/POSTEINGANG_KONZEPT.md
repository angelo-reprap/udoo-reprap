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
| `inbox_service` (Header-Leser, ABpE-Gelesen-Status, CRM-Zuordnung) | ✅ gebaut |
| `api/inbox/` + `api/inbox/<id>/aufgabe/` + `api/inbox/<id>/read/` + Tab-Frontend | ✅ gebaut |
| Account-Filter (`?account=`) + Badge aus `api/stats/` | ✅ gebaut |
| `shaduler_inbox_poll` als SchedulerJob | ✅ registriert |
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

---

## 6. Posteingang v1.1 — Filter · Suche · Zwei-Spalten-Viewer

**Stand 04.08.2026** · Live: 7 Postfächer über ES `abpe_emails`.
Vorbild: CRM/DMS-Mails-Tab (`/crm/dms/` → EDMS).

### 6.1 Leitidee
Kein neuer Mail-Renderer. Volltext + Anhänge kommen aus dem **bestehenden
ES-Mail-Index** über die EDMS-Endpoints; die UI verdrahtet dieselben
Bausteine wie der DMS-Mails-Tab.

### 6.2 Filterleiste (oben)
| Filter | UI | Backend |
|---|---|---|
| Postfach | Chips `Alle (n) · vertrieb · angelo · …` | `?account=` (bereits da) |
| Anhang | Dropdown alle / nur mit / ohne | `?has_attachment=1\|0` → ES-Feld |
| Datum | neueste (Default) / älteste | `?sort=date_desc\|date_asc` |
| Neu | nur Ungelesene (ABpE) | `?unread=1` + `InboxMailRead` |
| Suche | Freitext Betreff/Absender/Body | `?q=` → ES `multi_match` auf Index |

### 6.3 Layout
```
┌─ Filter + Suche ─────────────────────────────┐
│ [Alle][vertrieb]…  📎alle▾  Datum▾  □ nur neu │
│ [Suchen …                         ] [Suchen] │
├──────────────┬───────────────────────────────┤
│ Liste        │ Viewer                        │
│ Betreff      │ Kopf Absender/Empfänger/Datum │
│ Absender     │ Anhänge-Kacheln (öffnen)      │
│ Badge·📎·Age │ Body                          │
│              │ ── Aktionen ──                │
│              │ Aufgabe · Matching · Studio · │
│              │ Outlook                       │
└──────────────┴───────────────────────────────┘
```
- Listenzeile kompakt; Aktions-Buttons **nur im Viewer**
- Klick Liste → mark_read + Viewer laden

### 6.4 EDMS-Wiederverwendung (Live-Endpoints)

Aus `apps/abpe_edms/urls.py` (ucs5):

| Endpoint | Name | Rolle für Posteingang |
|---|---|---|
| `GET …/api/mail/view/` | `api_mail_view` | **Viewer-Payload** (Header, Body, Attachments) per ES-Mail-ID |
| `GET …/api/mail/attachment/` | `api_mail_attachment` | Anhang öffnen/download |
| `GET …/api/mail/attachment/preview/` | `api_mail_attachment_preview` | Anhang-Vorschau |
| `GET …/api/person/<crm_id>/mails/` | `api_person_mails` | Referenz: wie DMS die Liste baut (Filter/ES) — optional für CRM-Deeplink |

JS: `mod-dms*.js` — Funktionen für Mail-Render/Fetch (exakte Namen nach
`PROBE-edms-mail-api.sh` / Import-Slice festnageln).

**Verdrahtung Shaduler:**
1. Liste bleibt `GET /shaduler/api/inbox/` (erweitert um `q`, `has_attachment`, `sort`, `unread`)
2. Viewer ruft **EDMS** `GET /edms/api/mail/view/?…` (bzw. den gemounteten Pfad unter `/crm/dms/`) mit der ES-`_id` aus `mail.id` (`es:<id>` → `<id>`)
3. Anhänge über EDMS attachment-Endpoints
4. Kein Duplikat des Body-Renderers in `mod-shaduler.js` — EDMS-Renderer
   extrahieren/teilen oder per gemeinsamer Helper-Funktion aufrufen

### 6.5 Status v1.1

| Baustein | Status |
|---|---|
| Account-Chips + ABpE-Gelesen | ✅ v1.0 |
| Filter Anhang/Datum/Neu + Suche `?q=` | 🔶 bauen |
| Zwei-Spalten-Layout Liste\|Viewer | 🔶 bauen |
| EDMS `api_mail_view` + Attachment wiederverwenden | 🔶 verdrahten (nach Slice-Import) |
| Gemeinsame JS-Mail-Render-Funktion | 🔶 nach PROBE festlegen |