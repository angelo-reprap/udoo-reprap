# MCID — Corporate Identity / Corporate Design UI Layout (E-Mail)

**MCID** = Corporate Identity / Corporate Design UI Layout Template für HTML-E-Mails.

Stand: **2026-07-19**  
Gilt für: Module (`EmailModule` / `{{block:…}}`), KI-Layout-Regeln, Validator (später)

Dieses Dokument wird schrittweise erweitert.

---

## Regel 1 — Erlaubte HTML-Tags und CSS (Zuverlässigkeit ~90 %)

Bausteine (Module) dürfen **nur** aus den folgenden Elementen bestehen.

### Zuverlässige HTML-Tags

| Tags | Rolle |
|---|---|
| `table` · `tr` · `td` · `th` · `tbody` | Layout und Datentabellen |
| `img` · `a` · `p` · `br` · `span` | Medien, Links, Fließtext |
| `strong` · `b` · `em` · `i` · `u` | Textauszeichnung |
| `h1` · `h2` · `h3` | Überschriften |
| `ul` · `ol` · `li` | Aufzählungen |
| `div` | nur Inhalt, **nicht** als Hauptlayout |
| `hr` | einfacher Trenner |

### Hilfsattribute

`width` · `height` · `align` · `bgcolor` · `cellpadding` · `cellspacing` · `border` · `role="presentation"` · `alt` · `href` · `target` · inline `style`

### Zuverlässiges CSS (nur inline)

**Text:**  
`font-family` · `font-size` · `font-weight` · `font-style` · `line-height` · `text-align` · `text-decoration` · `color`

**Box:**  
`padding` · `padding-top` / `padding-right` / `padding-bottom` / `padding-left` · `width` · `height` · `background-color` · `border` · `border-top` / `border-right` / `border-bottom` / `border-left` · `border-collapse` · `vertical-align`

**Bild / Link:**  
`display: block` (Bilder) · `max-width: 100%` (Bilder, mit fester `width`)

### Kurzregel

- Layout über **Tabellen** + **inline styles**
- Kein Flexbox, Grid, `position`, `float` für Kernlayout
- Kein `border-radius`, Schatten, Hintergrundbilder, externe CSS in der MCID-Basis

---

## Regel 2 — Icons ohne Embed / ohne Download *(Entwurf)*

Nur Zeichen, die als **Text** im Client-Font liegen — kein `img`, kein CID, keine Remote-URL, kein SVG, keine Icon-Fonts.

### Übersicht

| Typ | Beispiele | OK? |
|---|---|---|
| Unicode / Entities | `•` `&bull;` · `▸` · `→` · `✓` · `✗` · `●` · `–` | **ja** |
| Emoji (ältere, einfache) | siehe Liste unten | **oft ja** |
| PNG / JPG / GIF / WebP / SVG / Icon-Fonts / `data:` | — | **nein** (Laden oder Einbetten nötig) |

### Unicode / Entities (zuverlässig)

| Zeichen | Entity / Unicode | typische Nutzung |
|---|---|---|
| • | `&bull;` | Aufzählung |
| ▸ | `&#9656;` | Listenpfeil |
| → | `&rarr;` | Pfeil |
| ✓ | `&#10003;` | OK / Check |
| ✗ | `&#10007;` | Fehler / Nein |
| ● ○ | `&#9679;` `&#9675;` | Statuspunkt |
| ■ □ | `&#9632;` `&#9633;` | Marker |
| – — | `&ndash;` `&mdash;` | Trennstrich |

### Emoji — die zuverlässigeren („oft ja“)

Früh in Unicode, ein Codepoint, keine Skin-Tones / keine ZWJ-Sequenzen. Darstellung bleibt OS-/Client-abhängig (Apple ≠ Windows ≠ Android), aber Ausfall ist selten.

| Emoji | Nutzung |
|---|---|
| ✅ | OK / Erfolg |
| ❌ | Fehler / Abbruch |
| ⚠️ | Warnung |
| ℹ️ | Info |
| ❗ | Hinweis / wichtig |
| ✔️ | Check (Textvariante) |
| ➡️ | Pfeil / weiter |
| ⭐ | Hervorhebung |
| 📧 | E-Mail |
| 📅 | Termin / Kalender |
| 📎 | Anhang |
| 🔗 | Link |
| 👍 | Bestätigung (informell) |
| 🟢 🟡 🔴 | Statusampel (Farbe je OS unterschiedlich) |

**Für strenge MCID / CI bevorzugen:** Unicode/Entities aus der Tabelle oben (`✓` `✗` `•` `→`), nicht Emoji.

**Vermeiden:** neue Emoji, Flaggen, Personen mit Hautton, kombinierte Sequenzen (👨‍💻), Marken-Logos als Emoji.

---

## Zielbild — Baukasten (Format × Inhalt)

Zwei Ebenen, klarer Bezug:

| Ebene | Bedeutung | Beispiele |
|---|---|---|
| **Format-Bausteine** | *wie* es aussieht (MCID-Kern) | Aufzählung, Key-Value, Tabelle, 2-Spalten, Hinweisbox, CTA, Trenner |
| **Inhalts-Bausteine** | *was* hineinkommt — nutzen ein Format | Termin, Anhangsliste, Teilnehmer, Status, Fakten, Header, Signatur |

Beispiel: Inhalts-Baustein **Termin** → Format **Key-Value** oder **2-Spalten**.

### Geplantes Mindest-Set

**Format (8):** Fließtext · Überschrift · Aufzählung · Key-Value · Tabelle · 2-Spalten · Hinweisbox · CTA  

**Rahmen (4):** Header · Badge · Signatur · Footer  

**Inhalt (6):** Termin · Anhangsliste · Teilnehmerliste · Status · Fakten · Schritte  

---

## Regel 3 — Logo / Bild (Header)

| Variante | Bedeutung | Für Header-Logo |
|---|---|---|
| `<img>` Remote-URL | Client lädt Bild (oft erst nach „Bilder anzeigen“) | üblich |
| **CID / eingebettet** | Bild hängt an der Mail (`multipart/related`) | üblich, offline sichtbar |
| Download-Link (`<a href>`) | Nutzer klickt → Datei | **nicht** für Logo |

- MCID-Header: Logo als **Bild** (URL oder CID), plus Text-Fallback „abcona e. K.“
- **CID umgeht den Spamfilter nicht.** Entscheidend bleiben Auth (SPF/DKIM/DMARC), Reputation, Textmenge, Links, Volumen.
- Risiko bei CID: große eingebettete Bilder + wenig Text → schlechter Score. Logo klein halten.

---

## Regel 4 — Kalender (.ics) und Kontakt (.vcf) *(Ziel, später)*

Wir sollen beides anbieten können:

| Format | Datei | Zweck |
|---|---|---|
| **iCalendar** | `.ics` | Termin in Outlook / Apple / Google übernehmen |
| **vCard** | `.vcf` | Kontakt speichern (Person/Firma) — **kein** Termin |

### Spam / Zustellung

- `.ics` / `.vcf` sind **nicht von sich aus Spam** — normale Business-Anhänge.
- Risiko steigt durch: fehlende Absender-Auth, Massenversand, viele/große Anhänge, falscher MIME-Type, seltsame Dateinamen, Mail fast nur Bild/HTML.
- Praxis: eine MeetMe-Mail mit **einer** `.ics` (+ optional einer `.vcf`) an bekannte Empfänger ist unkritisch bei korrekter Auth.
- MIME korrekt: `text/calendar` bzw. `text/vcard` (oder sauberer Attachment-Type), nicht generisches `.bin`.
- Technisch: Inhalts-Baustein **Termin** (sichtbar in der Mail) + Versand-Logik für `.ics`-Anhang oder -Link; vCard optional getrennt.

---

## Regel 5 — Modul-Soll-Set (Baukasten)

Bezug: **Format-Bausteine** × **Inhalts-Bausteine** (siehe Zielbild).  
Fließtext / Überschrift leben im Vorlagen-Body — kein eigenes Modul.

### Was wir brauchen (Soll)

| Rolle | Baustein | Pflicht? |
|---|---|---|
| Rahmen | Header Marke (nur blau) | ja |
| Rahmen | Badge/Label (Info · OK · Warnung) | ja |
| Rahmen | Signatur (auswählbar) | ja |
| Rahmen | Footer Standard / Auto-Reply | ja (XOR Signatur, siehe Layout-Deklaration) |
| Format | Aufzählung / Key-Value | ja |
| Format | Datentabelle | ja |
| Format | 2-Spalten | ja |
| Format | Hinweisbox / Zitat | ja |
| Format | CTA (+ optional Sekundärlink) | ja |
| Inhalt | Termin / Kalender | ja |
| Inhalt | Anhangsliste | ja |
| Inhalt | Kontakt / Support | ja |
| Inhalt | Fakten / Schritte | sinnvoll |
| Inhalt | Status (Ampel/Tabelle) | später (Variable + Format) |
| Anhang | `.ics` / `.vcf` | später (Versand, kein HTML-Modul) |

### Bestehende Module — Übernehmen / Streichen / Umbauen

| Modul (Ist) | Entscheidung | Begründung |
|---|---|---|
| Header — Blau | **übernehmen** | MCID-Marke |
| Header — Grün / Rot | **löschen** (als Header) | Event-Farbe nur über Labels |
| Label — Information / Bestätigt / Handlungsbedarf | **übernehmen** | Badge-Set |
| Signatur (auswählbar) | **übernehmen** | Pflicht-Rahmen |
| Unterschriften-Block | **prüfen → eher streichen** oder in Signatur aufgehen | Doppelung |
| Footer Standard / Auto-Reply | **übernehmen** | XOR Signatur |
| Button — Blau / Grün | **übernehmen, auf 1 Primär-CTA verdichten** | Grün optional oder weg |
| CTA mit Sekundärlink | **übernehmen** | sinnvoll |
| Dokumenten-Anhang-Liste | **übernehmen** | Inhalt Anhänge |
| Fakten-Box | **übernehmen** | Highlights |
| Nummerierte Schritte | **übernehmen** | Prozess-Mails |
| Hervorhebungs-Zitat | **übernehmen** | Hinweisbox-Variante |
| Kalender-Karte | **übernehmen** | Termin-Inhalt |
| Kontakt-Karte / Support Kontakt | **übernehmen → zu 1 Kontakt-Baustein** | Doppelung vermeiden |
| Zwei-Spalten-Vergleich | **übernehmen** | 2-Spalten-Format |
| Kennzahl-Box | **optional** | selten; später generisches Key-Value |
| Skill-Tag-Liste | **nur bei CV/CRM-Bedarf** | sonst streichen |
| Preis-Leistungs-Tabelle | **nur bei Angebot-Mails** | sonst streichen |
| Fortschritts-Leiste | **streichen / zurückstellen** | Client-unzuverlässig, geringer MCID-Wert |

### Ergänzen (fehlt)

| Neu | Typ | Wofür |
|---|---|---|
| Aufzählung (Bullet-Liste) | Format | generische Listen |
| Key-Value-Liste | Format | Label + Wert |
| Datentabelle (n×m) | Format | z. B. Check \| Wert \| Status |
| Hinweisbox Info/Warn/OK | Format | einheitlicher Kasten (Zitat = Variante) |
| Teilnehmerliste | Inhalt | MeetMe |

### Kompaktes Soll-Set (~12–14 Kernmodule)

**Kern:** Header blau · 3 Labels · Signatur · 2 Footer · CTA (+ Sekundär) · Anhangsliste · Fakten · Schritte · Zitat/Hinweis · Kalender/Termin · Kontakt · 2-Spalten  

**Neu:** Aufzählung · Key-Value · Datentabelle · ggf. Teilnehmerliste  

**Zurückstellen:** Header grün/rot · Fortschritts-Leiste · Skill-Tags / Preis-Tabelle / Kennzahl (nutzungsabhängig)

---

## Regel 6 — Block-Syntax und Editor-Modell

**Lösung:** Format-Baustein mit Inhalt = öffnendes + schließendes Token.

```text
{{block:hinweisbox}}
Hier freier Text und {disk_free}.
{{/block}}
```

Selbstschließende Module ohne Inhalt bleiben erlaubt (Header, Label, Footer, Signatur):

```text
{{block:abcona_header_blau}}
{{block:label_info}}
…
{{block:signature}}
```

### Regeln

| Thema | Festlegung |
|---|---|
| Syntax Inhalt | `{{block:<id>}}` … Inhalt … `{{/block}}` |
| Syntax ohne Inhalt | `{{block:<id>}}` (wie bisher) |
| Inhalt darf | Freitext + `{variablen}` + Inline-Format (Editor-Toolbar, Regel 1) |
| Inhalt darf nicht | verschachtelte `{{block:…}}` in v1 (später optional) |
| Wahrheit | **Visual / Block-Liste** = Source of Truth |
| HTML-Ansicht | gerendert bzw. serialisierte Tokens + Inner-HTML |
| TXT-Ansicht | aus derselben Block-Struktur; jedes Modul liefert `html_body` **und** `text_body`-Hülle |
| TXT „1:1“ | gleicher Inhalt/Reihenfolge — **nicht** gleiches HTML-Markup |
| HTML-Editor-Toolbar | nur Inline (B/I/U/Link/Farbe/Ausrichtung) im Freitext / Inner-Content |
| Format-Bausteine | als Module einfügen, **nicht** als Toolbar-Buttons |

### Render-Skizze

1. Vorlage als geordnete Blöcke parsen  
2. Pro Block: Hülle aus Modul (`html_body` / `text_body`) + Inner-Content einsetzen  
3. Danach `{variablen}` ersetzen  
4. HTML- und TXT-Ausgabe getrennt aus Schritt 2–3  

### Migration

- Bestehende `{{block:x}}` ohne Paar bleiben gültig (kein Inner-Content).  
- Neue Format-Bausteine mit Inhalt nutzen `{{block:x}}…{{/block}}`.  
- Renderer und KI-Prompts müssen beide Formen verstehen.

---

## Regel 7 — Studio-Rollen und Editor-Orte

**Entscheidung:** Modul- und Signatur-Editor im Studio **behalten und verfeinern** — nicht alles in den Django Admin schieben.

| Aufgabe | Rolle | Ort im Studio |
|---|---|---|
| Vorlage schreiben, Blöcke setzen, Variablen | Sachbearbeiter | Reiter **Vorlage** |
| Signatur pflegen (Tel, Name, Mail …) | Sachbearbeiter | Reiter **Signatur** (formbasiert) |
| Module / MCID-Hüllen anpassen oder neu | CI-/Technik (`email_studio_mcid` o. Ä.) | Reiter **Modul** → später MCID-Konfigurator |
| Roh-DB / Notfall | Admin | Django Admin |

### Signatur (verfeinern)

- Primär **Formularfelder:** Name, Titel, Tel, Mobil, E-Mail, optionale Frei-Zeile  
- HTML nur unter „Erweitert“  
- Speichern → DB  
- Alltag: z. B. Telefonnummer einer Mitarbeiterin ändern ohne Admin

### Modul (verfeinern, absichern)

- Nicht jeder Sachbearbeiter ändert MCID-Hüllen  
- Speichern nur wenn **Validator (Regel 1)** ok  
- Immer HTML- + TXT-Vorschau  
- Später optisch/rechtlich getrennt als **MCID-Konfigurator** (gleiche Studio-Oberfläche, erhöhte Rechte)

### Nicht tun

- Modul-Editor entfernen und nur Admin + Studio-Vorschau → schlechter Workflow für CI-Fixes (z. B. Bullet-Liste / Spam)

---

## Regel 9 — Variable · Modul · Block (Architektur)

**Freigegeben als Zielbild.** Klare Trennung, ein Render-Kern mit zwei Spezialisierungen.

| Ebene | Syntax | Aufgabe | Speicher |
|---|---|---|---|
| **Variable** | `{name}` | nur Rohdaten, kein Layout | Registry + Aufrufer / System-Services |
| **Modul** | `{{block:id}}` oder `{{block:id}}…{{/block}}` | nur Format/Hülle (MCID) | DB `EmailModule` (+ Git-Staging sync) |
| **Block** | benannte Komposition z. B. einfügen als Block | **Modul + gebundene Variablen/Inhalt** | DB (neu) bzw. Konfiguration — nicht als HTML-Variable |

### Namenskonflikt UI

Im Visual gibt es heute „**Block hinzufügen**“ (Text-Block, Button-Block, Signatur, Trennlinie). Das sind **Canvas-Abschnitte** (Editor-UI), **nicht** MCID-**Blöcke** aus dieser Regel.

| Heute UI | MCID-Begriff |
|---|---|
| Text-Block / Button-Block / … | Canvas-**Abschnitt** (später umbenennen) |
| `{{block:cta_blau}}` | **Modul** |
| `{teilnehmer_liste_html}` (Zwischenvariante) | später **Block** `teilnehmer` |
| `{system_status_html}` (Zwischenvariante) | später **Block** `system_status` |

### Renderer

```text
Variable     → einfacher Replace
Modul        → Modul-Renderer   (Hülle + optional {{content}} / Inner)
Block        → Block-Renderer   (wählt Modul, bindet Variablen, ruft Modul-Renderer)
```

- Kein fertiges Layout mehr in HTML-Variablen (Ziel).  
- Zwischenvariante `{…_html}` darf vorerst bleiben, wird schrittweise zu Blöcken.

### Erstellen & Einfügen

| Was | Wie erstellen | Wie einfügen |
|---|---|---|
| Variable | Registry / Service | Sidebar Variablen |
| Modul | Studio Reiter **Modul** (R7), Validator R1 | Sidebar Module oder Canvas |
| Block | Studio: Block definieren = Modul + Variablen-Mapping | „Block einfügen“ (neuer Menüpunkt) / Sidebar |

**Nicht** primär per `cat >>` Datei für jeden neuen Block.  
Git-Dateien unter `Repo_abpe/email_studio/incoming/` = **Staging/Sync** für Entwickler — Runtime-Wahrheit bleibt die **DB** (wie Module/Signaturen heute).

### Modul-Hülle (Skizze)

```html
<!-- Modul: aufzaehlung — html_body -->
<table role="presentation" width="100%" …>
  <tr><td style="…">{{content}}</td></tr>
</table>
```

```text
{{block:aufzaehlung}}
{punkt_1}
{punkt_2}
{{/block}}
```

Block `teilnehmer` könnte intern Modul `aufzaehlung` + Variable `{teilnehmer_liste}` (Rohdaten) nutzen — statt `{teilnehmer_liste_html}`.

---

## Regel 8 — CI-Tokens *(freigegeben 2026-07-19)*

Verständlich für Sachbearbeitung und Technik. Eine Schriftart: **Arial**.  
Farben freigegeben (siehe auch `mcid-ci-farben.png`).

### Farben (Name · Code · wofür)

| Name | Farbe | Code | Wofür |
|---|---|---|---|
| **Dunkelblau** | sehr dunkles Blau (Marke) | `#163258` | Header, Button, Links |
| **Hellblau** | sehr helles Blau | `#e8f0f8` | Label „Information“-Hintergrund |
| **Dunkelgrau** | fast schwarz | `#333333` | normaler Text |
| **Mittelgrau** | gedämpftes Grau | `#6c757d` | Footer, Nebentext |
| **Hellgrau** | leichter Grau-Ton | `#f8f9fa` | Boxen, Flächen |
| **Randgrau** | helles Linien-Grau | `#dee2e6` | Trennlinien, Tabellenränder |
| **Grün** | kräftiges Grün | `#28a745` | Erfolg / Label „Bestätigt“ |
| **Rot** | kräftiges Rot | `#dc3545` | Warnung / Label „Handlungsbedarf“ |
| **Weiß** | weiß | `#ffffff` | Schrift auf Dunkelblau |

### Schrift

| | Festlegung |
|---|---|
| Schriftart | **Arial** (nur diese) |
| Fließtext | **14px** |
| Klein (Footer, Meta) | **12px** |
| Header „abcona e. K.“ | **18px**, fett |
| Zeilenabstand | normal (~1,5) |

### Maße

| | Festlegung |
|---|---|
| Mail-Breite | **600px** (auf dem Handy volle Breite, max. 600px) |
| Innenabstand Box | **16px** |
| Innenabstand Header/Footer | **24px** links/rechts |
| Abstand zwischen Zeilen in Listen | **8px** |

Kein abgerundete Ecken (`border-radius`) in der MCID-Basis.

---

## Regel 10 — Identifier und Hüllen-Skizzen *(Konzept komplett)*

Slot in Hüllen: **`{{content}}`** (Inner aus `{{block:id}}…{{/block}}`).  
Selbstschließende Module ohne Slot.

### Module — Identifier (Soll)

| Identifier | Rolle | Ist-Mapping | Paar? |
|---|---|---|---|
| `abcona_header_blau` | Rahmen Header | gleich | nein |
| `label_info` | Badge Info | gleich | nein |
| `label_bestaetigt` | Badge OK | gleich | nein |
| `label_warnung` | Badge Warn | gleich (`label_warnung` / Handlungsbedarf) | nein |
| `footer_standard` | Footer | gleich | nein |
| `footer_auto_reply` | Footer Auto | gleich | nein |
| `signature` | Signatur (virtuell) | gleich | nein |
| `cta_blau` | CTA primär | gleich (`cta_gruen` optional/zurück) | nein |
| `cta_with_secondary` | CTA + Zweitlink | gleich | nein |
| `fmt_aufzaehlung` | Format Liste | **neu** | ja |
| `fmt_key_value` | Format Label+Wert | **neu** (ersetzt teils `stat_box`) | ja |
| `fmt_tabelle` | Format Datentabelle | **neu** | ja |
| `fmt_zwei_spalten` | Format 2-Spalten | aus `compare_two_col` | ja |
| `fmt_hinweis` | Format Hinweisbox | aus `quote_highlight` | ja |
| `fmt_trenner` | Trenner | **neu** / Canvas-Linie | nein |
| `calendar_card` | Inhalt Termin | gleich | nein / später ja |
| `doc_attachment_list` | Inhalt Anhänge | gleich | nein / später ja |
| `contact_card` | Inhalt Kontakt | + `support_kontakt` zusammenführen | nein |
| `fakten_box` | Inhalt Fakten | gleich | nein / später ja |
| `steps_numbered` | Inhalt Schritte | gleich | nein / später ja |

**Zurück / nicht Kern:** `abcona_header_gruen`, `abcona_header_rot`, `progress_bar`, `skill_tags`, `price_table`, `signature_lines` (→ Signatur), `cta_gruen` (optional).

### Blöcke — Identifier (Soll, nutzen Module)

| Block-ID | Modul | gebunden / Inhalt | ersetzt heute |
|---|---|---|---|
| `block_teilnehmer` | `fmt_aufzaehlung` | Teilnehmer-Rohdaten | `{teilnehmer_liste_html}` |
| `block_system_status` | `fmt_tabelle` | Status-Zeilen (Check/Wert/Flag) | `{system_status_html}` |
| `block_termin` | `fmt_key_value` oder `calendar_card` | `{termin_datum}`, `{termin_uhrzeit}`, `{raum}`, … | Fließtext-Mix |
| `block_anhaenge` | `doc_attachment_list` / `fmt_aufzaehlung` | Dokumentnamen | wie bisher Modul |

### Hüllen-Skizzen (HTML + TXT)

Gemeinsamer Textstil: Arial 14px, Dunkelgrau `#333333`, Breite im äußeren Mail-Wrapper 600px.

#### `fmt_aufzaehlung`

```html
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
  <tr><td style="padding:16px 24px;font-family:Arial;font-size:14px;color:#333333;line-height:1.5;">
    {{content}}
  </td></tr>
</table>
```

```text
{{content}}
```

Inhalt typisch: `<ul><li>…</li></ul>` bzw. TXT-Zeilen mit `• `.

#### `fmt_key_value`

```html
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
  <tr><td style="padding:16px 24px;font-family:Arial;font-size:14px;color:#333333;">
    {{content}}
  </td></tr>
</table>
```

```text
{{content}}
```

Inhalt: Zeilen `<strong>Label:</strong> Wert<br>` / TXT `Label: Wert`.

#### `fmt_tabelle`

```html
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
  <tr><td style="padding:16px 24px;">
    {{content}}
  </td></tr>
</table>
```

```text
{{content}}
```

Inhalt: Datentabelle (z. B. Check \| Wert \| Status) — gebaut vom **Block-Renderer**, nicht als HTML-Variable.

#### `fmt_zwei_spalten`

```html
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
  <tr><td style="padding:16px 24px;background-color:#f8f9fa;">
    {{content}}
  </td></tr>
</table>
```

```text
{{content}}
```

#### `fmt_hinweis`

```html
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
  <tr><td style="padding:16px 24px;background-color:#f8f9fa;border-left:3px solid #163258;font-family:Arial;font-size:14px;color:#333333;">
    {{content}}
  </td></tr>
</table>
```

```text
{{content}}
```

#### `cta_blau` (ohne Content-Slot, Variablen)

```html
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
  <tr><td style="padding:16px 24px;text-align:center;">
    <a href="{button_url}" style="font-family:Arial;font-size:14px;font-weight:bold;color:#ffffff;background-color:#163258;padding:12px 24px;text-decoration:none;">{button_text}</a>
  </td></tr>
</table>
```

```text
{button_text}: {button_url}
```

---

## Konfigurator — Deklarationsstand

### Konzept (Dokumentation) — komplett

| Status | Thema |
|---|---|
| ✅ | R1 Tags/CSS · R2 Icons · R3 Logo · R4 ICS/VCF · R5 Modul-Soll |
| ✅ | R6 Paar-Syntax · R7 Studio-Rollen · R8 CI-Tokens · R9 Variable/Modul/Block |
| ✅ | **R10 Identifier + Hüllen-Skizzen** |

### Umsetzung (Code/UI)

| Status | Thema |
|---|---|
| ✅ | Modul-Renderer + Block-Renderer (`blocks_registry.py`, `renderer.py`) |
| ✅ | KI-Katalog `blocks` + Prompt + Fragen I4/M2/L4 |
| ✅ | KI-Vorschau: Layout-Vorschläge (Nachfrage Aufzählung/Tabelle) |
| ✅ | HTML-Editor: Align + Listen; i18n de/en Tooltips |
| ✅ | Sidebar: Format- + Block-Chips mit Paar-Syntax |
| ⬜ | Validator Regel 1 (Tags/CSS) |
| ⬜ | Volle Migration `{…_html}` → nur noch Blöcke |
| ⬜ | Signatur-Formular · Rechte Modul-Reiter |
| ⬜ | Logo CID/URL · Versand `.ics`/`.vcf` |
| ⬜ | DB-Module `fmt_*` anlegen (Hüllen-Fallback aktiv) |

---

## Nächste Schritte (Umsetzung)

- [x] Konzept R1–R10
- [x] Modul-Renderer (`{{block:id}}…{{/block}}`, `{{content}}`)
- [x] Block-Renderer (`block_teilnehmer`, `block_system_status`, `block_termin`)
- [x] KI: Blocks im Catalog/Prompt + Vorschlags-UI
- [x] HTML-Editor Align/Listen + i18n de/en
- [ ] DB-Module `fmt_*` speichern (optional, Fallback vorhanden)
- [ ] Validator Regel 1 (Tags/CSS)
- [ ] Signatur-Formular (R7)
- [ ] Logo CID/URL (R3) · `.ics`/`.vcf` (R4)
