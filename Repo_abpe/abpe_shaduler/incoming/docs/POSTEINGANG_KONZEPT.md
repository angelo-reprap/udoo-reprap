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
Zwei Quellen, klar getrennt (PROBE 04.08.2026):

| Schicht | Quelle | Endpoint / Modul |
|---|---|---|
| **Liste + Suche + Filter** | Elasticsearch `abpe_emails` | Shaduler `api/inbox/` (Muster wie EDMS `api_person_mails`: `multi_match` auf `subject^2`, `body`) |
| **Viewer + Anhänge** | **IMAP live** via EDMS | `api_mail_view` / `api_mail_attachment*` — Parameter `account` + `folder` + (`uid` **oder** `message_id`) |

Kein neuer Mail-Renderer. Der Viewer ruft denselben EDMS-Endpoint wie der
DMS-Mails-Tab; die Liste bleibt Shaduler/ES (Postfach-Überblick, ABpE-Gelesen).

**Wichtig:** `api_mail_view` liest **nicht** den ES-Body — `_imap_fetch_message`.
Deshalb muss die Inbox-Liste `account`, `folder`, `uid` und/oder `message_id`
aus dem ES-Hit mitliefern (Felder liegen schon im Index).

**Seen-Flag:** EDMS-Fetch muss `BODY.PEEK` nutzen (wie Inbox-IMAP). Wenn Live
`FETCH` ohne PEEK setzt → Shaduler-Proxy mit PEEK oder EDMS anpassen; Leitplanke
„kein \\Seen“ gilt weiter.

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

### 6.4 EDMS-Wiederverwendung (Live-Endpoints, PROBE bestätigt)

Mount: `apps/abpe_edms/urls.py` (Pfad-Prefix je nach `urls.py`-Include, oft `/edms/`).

| Endpoint | Query | Rolle |
|---|---|---|
| `GET api/mail/view/` | `account`, `folder`, `uid` **oder** `message_id` | JSON: Header + Body(html/plain) + Anhang-Liste |
| `GET api/mail/attachment/` | dieselben + `index` | Download |
| `GET api/mail/attachment/preview/` | dieselben + `index` | Inline-Vorschau |
| `GET api/person/<crm_id>/mails/` | `q`, `size` | Referenz-Suche ES (Person) — Muster für `?q=` |

**Verdrahtung Shaduler:**
1. `GET /shaduler/api/inbox/?q=&account=&has_attachment=&sort=&unread=` → ES-Liste
2. Jeder Treffer liefert `view_params`: `{account, folder, uid, message_id}`
3. Viewer: `GET <edms>/api/mail/view/?account=…&folder=…&uid=…` (same-origin, Session)
4. Anhänge: gleiche Params + `index` aus der view-Response
5. JS: DMS-Renderer wiederverwenden — **Datei noch unklar** (`mod-dms*.js` unter
   `static/abpe_ui/js/mod/` nicht gefunden; Suche auf Live nötig)

### 6.5 Status v1.1

| Baustein | Status |
|---|---|
| Account-Chips + ABpE-Gelesen | ✅ v1.0 |
| Liste liefert `folder`/`uid`/`message_id`/`has_attachments` | 🔶 |
| Filter Anhang/Datum/Neu + Suche `?q=` | 🔶 |
| Zwei-Spalten-Layout Liste\|Viewer | 🔶 |
| EDMS `api_mail_view` + Attachment verdrahten | 🔶 (Vertrag klar) |
| DMS-JS-Renderer lokalisieren | ⬜ Live-Suche |