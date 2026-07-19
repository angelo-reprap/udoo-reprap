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

## Regel 8 — CI-Tokens *(Vorschlag — zur Freigabe)*

Aus bestehenden abcona-Modulen abgeleitet:

### Farben

| Token | Wert | Nutzung |
|---|---|---|
| `color.brand` | `#163258` | Header, CTA, Links, Akzente |
| `color.brand-soft` | `#e8f0f8` | Label Info-Hintergrund |
| `color.text` | `#333333` | Fließtext |
| `color.text-muted` | `#6c757d` | Footer, Meta |
| `color.surface` | `#f8f9fa` / `#f8fafc` | Boxen, Footer-BG |
| `color.border` | `#dee2e6` | Linien, Tabellen |
| `color.ok` | `#28a745` | Erfolg / Label Bestätigt |
| `color.warn` | `#dc3545` | Warnung / Label Handlungsbedarf |
| `color.white` | `#ffffff` | Text auf Brand |
| `color.page-bg` | `#eef2f5` | äußere Mail-Hülle (optional) |

### Typo

| Token | Wert |
|---|---|
| `font.stack` | `Arial, Helvetica, sans-serif` |
| `font.size-body` | `13px`–`14px` |
| `font.size-small` | `11px`–`12px` |
| `font.size-h` | `18px`–`19px` (Header-Marke) |
| `font.weight-bold` | `600` / `bold` |
| `line.height` | `1.5`–`1.7` |

### Layout

| Token | Wert |
|---|---|
| `layout.width` | `600px` (Inhalt), mobil `width:100%` + `max-width:600px` |
| `space.block` | `14px`–`18px` Innenabstand Boxen |
| `space.section` | `20px`–`28px` horizontal (Header/Footer-Padding) |
| `space.stack` | `8px`–`12px` zwischen Zeilen in Listen |

Nur Werte aus **Regel 1** (inline CSS). Kein `border-radius` in der MCID-Basis.

---

## Konfigurator — Deklarationsstand

| Status | Thema |
|---|---|
| ✅ da | R1 Tags/CSS · R2 Icons · R3 Logo · R4 ICS/VCF · R5 Modul-Soll · R6 Block-Syntax · R7 Studio-Rollen |
| ✅ da | Format × Inhalt, XOR Signatur/Footer (Layout-Deklaration) |
| 🟡 Vorschlag | **R8 CI-Tokens** — Freigabe ausstehend |
| ⬜ fehlt | **HTML/TXT-Skizzen** je Format-Baustein (`{{content}}`) |
| ⬜ fehlt | **Identifier-Namen** final |
| ⬜ fehlt | **Validator** gegen Regel 1 |
| ⬜ fehlt | **KI-Prompt / layout_rules** an R1–R7 |
| ⬜ fehlt | **UI-Konfigurator** (Verfeinerung Reiter Modul) |
| ⬜ fehlt | **Versand** `.ics`/`.vcf` + Logo-CID |
| ⬜ fehlt | **Ist→Soll-Migration** |

---

## Nächste Schritte (offen)

- [ ] **CI-Tokens freigeben** (Regel 8) oder anpassen
- [ ] HTML/TXT-Hüllen-Skizzen je Format-Baustein (`{{content}}`-Slot)
- [ ] Finale Identifier-Namen
- [ ] Renderer: `{{block:id}}…{{/block}}` + Selbstschließer
- [ ] Visual als Source of Truth (R6)
- [ ] Validator + Rechte am Modul-Reiter (R7)
- [ ] Signatur-Formular statt Roh-HTML (R7)
- [ ] Ist→Soll-Migration Module
- [ ] Logo CID vs. URL (R3) · `.ics`/`.vcf` (R4)
- [ ] KI-Prompt an R1–R8
- [ ] MCID-Konfigurator-UI verfeinern
