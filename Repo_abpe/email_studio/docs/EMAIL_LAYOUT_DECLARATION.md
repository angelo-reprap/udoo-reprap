# Email Studio — Layout-Deklaration (abcona)

Stand: **2026-07-18** · Quelle: Abstimmung mit Produkt  
Gilt für: Mensch (Baukasten), KI (`abpe_ki_wiz` / `layout_rules`), Validator

---

## Pflicht-Aufbau

```
{{block:abcona_header_blau}}     ← immer, nur blau (Marke)
{{block:label_*}}                ← optional Event-Badge (siehe §2)
… Body (Fließtext, Module) …
{{block:signature}}  ODER  {{block:footer_*}}   ← XOR, siehe §1
```

Plus immer: **TXT-Fallback**, 1:1 aus dem sichtbaren HTML-Text abgeleitet (§6).

---

## 1. Signatur XOR Footer (Impressum)

| Situation | Pflicht-Block |
|---|---|
| Signatur gewählt (USER / TEAM / FIXED / DYNAMIC mit Inhalt) | `{{block:signature}}` — **kein** Firmen-Footer |
| Keine Signatur (`NONE` / nicht gewählt) | `{{block:footer_standard}}` oder `footer_auto_reply` |

**Grund:** In DE brauchen Geschäftsmails Firmen-/Impressumsangaben. Die Signatur enthält sie (Person + Firma); ohne Signatur liefert der Footer das Impressum.

Nicht beides gleichzeitig (sonst doppeltes Impressum → Signatur müsste gekürzt werden).

### Signatur-Defaults

| Wahl | Verhalten |
|---|---|
| Keine Signatur | `signature_mode=NONE`, Footer Pflicht |
| System / Team | Textlich: **„Ihr abcona e. K. Team“** (Team-Signatur) |
| User | Signatur des Absenders |

---

## 2. Header + Event-Badge

### Header (Marke) — immer blau

- Modul: **nur** `{{block:abcona_header_blau}}`
- Text: „abcona e. K.“
- Hintergrund: `#163258`
- Grün/Rot-Header **nicht** mehr für Marken-Kopf nutzen

### Event-Badge darunter (Status)

Direkt unter dem blauen Header (oder am Body-Anfang):

| Modul | Farbe | Bedeutung |
|---|---|---|
| `{{block:label_info}}` | blau | Info |
| `{{block:label_bestaetigt}}` | grün | Bestätigung / Erfolg |
| `{{block:label_warnung}}` | rot | Alert / Warnung / Abbruch |

Das sind die bestehenden Label-Module in der DB — **nicht** die alten Header-Farben und **nicht** `button_blau`.

---

## 3. Footer-Inhalt (wenn keine Signatur)

Vorschlag (finaler Wortlaut nach Freigabe ins Modul `footer_standard`):

```
abcona e. K. | active business consulting agency
Bornhohl 26
D-61449 Steinbach/Ts.

USt-ID: DE813519516
Amtsgericht: Bad Homburg v.d.H. HRA 3662
Inhaber: Angelo Malaguarnera
```

`footer_auto_reply`: gleicher Block + Zeile „Bitte nicht auf diese E-Mail antworten.“

---

## 4. Typografie & Layout (Body)

| Eigenschaft | Soll |
|---|---|
| Breite | 600px Tabellen-Layout |
| Schrift | Arial, Helvetica, sans-serif |
| Größe Body | 14px |
| Farbe Body | `#333333` |
| Ausrichtung | `text-align: left` |
| CSS | nur inline, kein JS, kein externes CSS |
| Outlook | Tabellen + `role="presentation"` |

---

## 5. Design Header (kein reines Rechteck-Zwang)

E-Mail-Clients: kein volles CSS/JS. `border-radius` oft in Outlook Desktop wirkungslos.

**Empfehlung (client-sicher):**

1. **Basis:** blauer Tabellen-Balken, linksbündig, 18px, Padding `16px 24px`
2. **Optional „weicher“:** äußerer Wrapper mit hellgrauem Seitenrand (`#eef2f5`), innere weiße 600px-Karte — wirkt weniger „harter Balken“, funktioniert ohne Radius
3. **Nice-to-have:** `border-radius:8px` am inneren Header-`<td>` — schön in Apple Mail/Gmail, in Outlook eckig (akzeptabel)

Keine Abhängigkeit von JS oder modernen CSS-Features.

---

## 6. TXT-Fallback

- Jede Vorlage **muss** `text_body` haben
- Inhalt = sichtbarer Text aus HTML **1:1** (keine Marketing-Abweichung)
- Ableitung: HTML → Plaintext (Blöcke aufgelöst, Links als `Text: URL`)
- KI und Editor: TXT immer mitliefern / mitgenerieren

---

## 7. Module / Orchestrierung

Getestete Bausteine stecken Vorlagen zusammen:

| Rolle | Module |
|---|---|
| Kopf | `abcona_header_blau` |
| Event | `label_info` / `label_bestaetigt` / `label_warnung` |
| CTA | `cta_blau` / `cta_gruen` / `cta_with_secondary` |
| Abschluss | `signature` **oder** `footer_standard` / `footer_auto_reply` |
| Inhalt | `fakten_box`, `support_kontakt`, … (email-client-tauglich) |

KI-Generator und menschlicher Baukasten teilen dieselbe Deklaration (`layout_rules` in `abpe_ki_wiz`).

---

## 8. Arbeitsregel (Sync & Backup)

Nach **jedem** funktionierenden Zwischenschritt:

1. Auf ucs5: `backup_restore.py -save … -m "vor: …"` vor Live-Änderungen  
2. Code + DB-Snapshot nach Git:  
   `bash Repo_abpe/email_studio/incoming/RUN-phase1-iststand.sh --commit --push`  
3. Agent arbeitet nur gegen den Git-Stand — nicht gegen ungesicherte Live-Dateien

Voll-rsync (alles Email Studio + KI-Wiz) vor größeren Konzept-Schritten wiederholen.

---

## Offen / nächste Schritte (nach deinem Check)

1. Live-Stand per Voll-rsync ins Git sichern  
2. Info-Popover `(i)` + Clipboard für Module/Vars **chirurgisch** in den aktuellen KI-Stand einfügen (kein Branch-Overwrite)  
3. `footer_standard` HTML auf §3-Text bringen (nach Freigabe, mit Backup)  
4. `layout_rules` + Validator an diese Deklaration anbinden  
