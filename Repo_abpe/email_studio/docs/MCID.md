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

## Nächste Schritte (offen)

- [ ] MCID-Mindest-Layout-Set im Detail ausformulieren (HTML-Skizzen je Format-Baustein)
- [ ] Mapping bestehende Module → Regel 1 + Zielbild Format/Inhalt
- [ ] Icon-Set für abcona final festlegen (Regel 2, Unicode bevorzugt)
- [ ] Logo-Strategie festlegen: CID vs. URL (Regel 3)
- [ ] `.ics` / `.vcf` Erzeugung + Anhang am Versand anbinden (Regel 4)
- [ ] Validator / KI-Prompt an Regel 1–2 binden
