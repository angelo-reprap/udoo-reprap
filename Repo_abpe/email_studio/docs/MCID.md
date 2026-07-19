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

Beispiele (Unicode / HTML-Entity):

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

**Emoji** (z. B. ✅ ⚠️) können funktionieren, sind aber OS-/Client-abhängig und für strenge CI oft ungeeignet.

**Nicht ohne Laden/Einbetten:** PNG/JPG/GIF/WebP, SVG, Font Awesome / Icon-Fonts, `data:`-URIs.

---

## Nächste Schritte (offen)

- [ ] MCID-Mindest-Layout-Set (Header, Text, Liste, Tabelle, CTA, Trenner, Footer …)
- [ ] Mapping bestehende Module → Regel 1
- [ ] Validator / KI-Prompt an Regel 1 binden
- [ ] Icon-Set für abcona final festlegen (Regel 2)
