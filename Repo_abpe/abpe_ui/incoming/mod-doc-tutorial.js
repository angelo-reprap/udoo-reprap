/**
 * mod-doc-tutorial.js — Eingebettetes Daumenkino für Dokumentationsseiten
 * Rendert .doc-tut[data-scenario] Platzhalter mit interaktiven Schritt-Frames
 */
'use strict';

window.DocTut = {

    _lang: 'de',

    init: function() {
        DocTut._lang = (typeof currentLang !== 'undefined' ? currentLang : null)
            || window.ABPE_CONFIG?.current_lang || 'de';
        document.querySelectorAll('.doc-tut[data-scenario]').forEach(el => {
            if (el.dataset.tutInit) return;
            el.dataset.tutInit = '1';
            DocTut._render(el, el.dataset.scenario);
        });
        document.addEventListener('languageChanged', function(e) {
            DocTut._lang = e.detail.language;
            document.querySelectorAll('.doc-tut[data-scenario]').forEach(el => {
                el.dataset.tutInit = '';
                DocTut._render(el, el.dataset.scenario);
            });
        }, {once: false});
    },

    t: function(key) {
        const parts = key.split('.');
        let v = window.i18nData;
        for (const p of parts) v = v?.[p];
        return v || key;
    },

    _render: function(container, scenario) {
        const T = DocTut.t.bind(DocTut);
        const lang = DocTut._lang;

        /* ── CSS einmalig ── */
        if (!document.getElementById('doc-tut-css')) {
            const s = document.createElement('style');
            s.id = 'doc-tut-css';
            s.textContent = `
.doc-tut-wrap{margin:16px 0;border:1px solid var(--border-color,#e0e0e0);border-radius:8px;overflow:hidden;background:#fff;font-family:inherit;}
.doc-tut-hdr{background:#163258;color:#fff;padding:8px 14px;font-size:11px;display:flex;align-items:center;justify-content:space-between;}
.doc-tut-hdr-title{font-weight:600;display:flex;align-items:center;gap:6px;}
.doc-tut-hdr-count{opacity:.7;font-size:10px;}
.doc-tut-frame{min-height:220px;background:#f8f9fa;}
.doc-tut-ctrl{display:flex;align-items:center;gap:8px;padding:8px 14px;border-top:1px solid var(--border-color,#e0e0e0);background:#f8f9fa;}
.doc-tut-btn{padding:4px 12px;border-radius:6px;border:1px solid #ccc;font-size:11px;cursor:pointer;background:#fff;color:#333;}
.doc-tut-btn.primary{background:#163258;color:#fff;border-color:#163258;}
.doc-tut-btn:disabled{opacity:.3;cursor:default;}
.doc-tut-dots{display:flex;gap:4px;flex:1;justify-content:center;}
.doc-tut-dot{width:7px;height:7px;border-radius:50%;background:#ccc;cursor:pointer;transition:background .2s;}
.doc-tut-dot.on{background:#163258;}
.doc-tut-info{padding:10px 14px 14px;}
.doc-tut-ttl{font-size:13px;font-weight:600;color:#163258;margin-bottom:4px;}
.doc-tut-dsc{font-size:12px;color:#555;line-height:1.7;}
.es-tut-sim{font-size:10px;padding:10px 12px;}
.es-tut-topbar{background:#163258;color:#fff;padding:5px 10px;font-size:9px;border-radius:5px 5px 0 0;display:flex;align-items:center;justify-content:space-between;}
.es-tut-editor{background:#1e1e1e;color:#d4d4d4;font-family:monospace;font-size:8px;border-radius:4px;padding:7px;line-height:1.7;white-space:pre;}
.es-tut-inp{border:1px solid #ddd;border-radius:3px;padding:3px 5px;font-size:8px;background:#fff;color:#333;}
.es-tut-lbl{font-size:7px;color:#888;margin-bottom:2px;text-transform:uppercase;}
.es-tut-crd{border:1px solid #e0e0e0;border-radius:5px;padding:6px 8px;background:#fff;}
.es-tut-tab-on{padding:2px 6px;background:#163258;color:#fff;border-radius:3px;font-size:8px;}
.es-tut-tab-off{padding:2px 6px;border:1px solid #ddd;border-radius:3px;font-size:8px;color:#666;}
.es-tut-cur{display:inline-block;width:2px;height:10px;background:#fff;vertical-align:middle;animation:es-tut-blink 1s infinite;}
.es-tut-pulse{border:2px solid #163258;border-radius:4px;animation:es-tut-pulse-anim 1.2s infinite;}
.es-tut-chip{background:#e6f1fb;color:#0c447c;border-radius:3px;padding:2px 5px;font-size:8px;font-family:monospace;display:inline-block;margin:2px;}
.es-tut-chip-g{background:#eaf3de;color:#27500a;}
@keyframes es-tut-blink{0%,100%{opacity:1}50%{opacity:0}}
@keyframes es-tut-pulse-anim{0%,100%{border-color:#163258}50%{border-color:#4a90d9}}
            `;
            document.head.appendChild(s);
        }

        /* ── Szenarien-Daten ── */
        const isDE = lang !== 'en';

        const SCENARIOS = {

            hello_world: {
                title: isDE ? '▶ Interaktiv: Hello World — Erste Vorlage' : '▶ Interactive: Hello World — First Template',
                steps: [
                    {
                        t: isDE ? 'Vorlagen-Übersicht öffnen' : 'Open Template Overview',
                        d: isDE ? 'Klicken Sie in der Sidebar auf "Email Studio". Die Übersicht zeigt alle vorhandenen Vorlagen mit Status, Absender-Modus und letzter Nutzung. Oben rechts finden Sie "+ Neue Vorlage".' : 'Click "Email Studio" in the sidebar. The overview shows all existing templates with status, sender mode and last use. Top right you find "+ New Template".',
                        r: () => `<div class="es-tut-sim">
  <div class="es-tut-topbar">✉ Email Studio
    <span class="es-tut-pulse" style="background:#fff;color:#163258;padding:2px 8px;border-radius:4px;font-size:9px;font-weight:600;">+ ${isDE?'Neue Vorlage':'New Template'}</span>
  </div>
  <div style="display:grid;grid-template-columns:1fr 1fr 1fr 1fr;padding:8px 12px;">
    ${[['6',isDE?'Vorlagen':'Templates','#163258'],['5',isDE?'Aktiv':'Active','#28a745'],['1',isDE?'Entwurf':'Draft','#f59e0b'],['0',isDE?'Archiv':'Archive','#888']].map(([n,l,c])=>`
    <div style="text-align:center;padding:5px;border-right:1px solid #eee;">
      <div style="font-size:16px;font-weight:600;color:${c};">${n}</div>
      <div style="color:#888;font-size:7px;text-transform:uppercase;">${l}</div>
    </div>`).join('')}
  </div>
  <div style="padding:0 12px 8px;">
    <div style="border-radius:4px;overflow:hidden;border:1px solid #eee;">
      <div style="display:grid;grid-template-columns:2fr 1fr 1fr 60px;padding:4px 8px;background:#163258;color:#fff;font-size:8px;">
        <span>${isDE?'Name / Identifier':'Name / Identifier'}</span><span>${isDE?'Absender':'Sender'}</span><span>Status</span><span>${isDE?'Aktionen':'Actions'}</span>
      </div>
      <div style="display:grid;grid-template-columns:2fr 1fr 1fr 60px;padding:5px 8px;font-size:8px;align-items:center;">
        <span><b style="color:#163258;">CV fertig — Berater</b><br><span style="font-family:monospace;color:#888;font-size:7px;">cv_generated_berater</span></span>
        <span style="color:#28a745;">● ${isDE?'User':'User'}</span>
        <span><span style="background:#28a745;color:#fff;border-radius:3px;padding:1px 5px;font-size:7px;">${isDE?'Aktiv':'Active'}</span></span>
        <span style="color:#888;font-size:10px;">✏ 📋 👁 ✈</span>
      </div>
    </div>
  </div>
</div>`
                    },
                    {
                        t: isDE ? 'Startoptionen wählen' : 'Choose Start Option',
                        d: isDE ? 'Nach Klick auf "+ Neue Vorlage" erscheinen drei Optionen. "Leeres Template" startet mit leerer Leinwand. "Corporate Skeleton" hat bereits Header und Footer. "Duplizieren" kopiert eine bestehende Vorlage.' : 'After clicking "+ New Template" three options appear. "Empty Template" starts with a blank canvas. "Corporate Skeleton" already has header and footer. "Duplicate" copies an existing template.',
                        r: () => `<div class="es-tut-sim" style="padding:8px 12px;">
  <div style="font-size:10px;font-weight:600;color:#163258;margin-bottom:8px;">${isDE?'Wie möchten Sie starten?':'How would you like to start?'}</div>
  <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:6px;">
    <div class="es-tut-pulse es-tut-crd" style="background:#e6f1fb;text-align:center;padding:10px 6px;">
      <div style="font-size:18px;margin-bottom:4px;">📄</div>
      <div style="font-weight:600;color:#0c447c;font-size:9px;">${isDE?'Leeres Template':'Empty Template'}</div>
      <div style="color:#185fa5;margin-top:3px;font-size:8px;">${isDE?'HTML von Grund auf':'HTML from scratch'}</div>
    </div>
    <div class="es-tut-crd" style="text-align:center;padding:10px 6px;opacity:.5;">
      <div style="font-size:18px;margin-bottom:4px;">🏗</div>
      <div style="font-weight:600;font-size:9px;">Corporate Skeleton</div>
      <div style="color:#666;margin-top:3px;font-size:8px;">${isDE?'Mit Header + Footer':'With Header + Footer'}</div>
    </div>
    <div class="es-tut-crd" style="text-align:center;padding:10px 6px;opacity:.5;">
      <div style="font-size:18px;margin-bottom:4px;">📋</div>
      <div style="font-weight:600;font-size:9px;">${isDE?'Duplizieren':'Duplicate'}</div>
      <div style="color:#666;margin-top:3px;font-size:8px;">${isDE?'Kopie anlegen':'Create copy'}</div>
    </div>
  </div>
</div>`
                    },
                    {
                        t: isDE ? 'Einstellungen & Identifier' : 'Settings & Identifier',
                        d: isDE ? 'Füllen Sie Anzeigename, Betreff und Identifier aus. Der Identifier ist der technische Code-Name (z.B. cv_generated_berater) — er wird im Python-Code als template=\'cv_generated_berater\' verwendet und kann nach dem ersten Speichern NICHT mehr geändert werden.' : 'Fill in display name, subject and identifier. The identifier is the technical code name (e.g. cv_generated_berater) — used in Python as template=\'cv_generated_berater\' and CANNOT be changed after first save.',
                        r: () => `<div class="es-tut-sim" style="padding:8px 12px;">
  <div style="display:flex;flex-direction:column;gap:5px;font-size:9px;">
    <div><div class="es-tut-lbl">${isDE?'ANZEIGENAME':'DISPLAY NAME'}</div><div class="es-tut-inp">CV fertig — Berater</div></div>
    <div><div class="es-tut-lbl">${isDE?'BETREFF':'SUBJECT'}</div><div class="es-tut-inp">${isDE?'Ihr Berater-Profil ist fertig — {name}':'Your consultant profile is ready — {name}'}</div></div>
    <div><div class="es-tut-lbl">${isDE?'IDENTIFIER (TECHNISCHER NAME) *':'IDENTIFIER (TECHNICAL NAME) *'}</div>
      <div class="es-tut-pulse" style="border:1px solid #4a90d9;border-radius:4px;padding:3px 6px;font-family:monospace;background:#e6f1fb;color:#0c447c;">cv_generated_berater<span class="es-tut-cur"></span></div>
      <div style="font-size:8px;color:#e24b4a;margin-top:2px;">⚠ ${isDE?'Nach erstem Speichern nicht mehr änderbar!':'Cannot be changed after first save!'}</div>
    </div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:5px;">
      <div><div class="es-tut-lbl">${isDE?'APP-BEREICH':'APP SCOPE'}</div><div class="es-tut-inp">Intake / CV Upload ▾</div></div>
      <div><div class="es-tut-lbl">STATUS</div><div class="es-tut-inp">${isDE?'Aktiv':'Active'} ▾</div></div>
    </div>
  </div>
</div>`
                    },
                    {
                        t: isDE ? 'Absender-Modus wählen' : 'Choose Sender Mode',
                        d: isDE ? 'USER: Die E-Mail kommt vom eingeloggten Mitarbeiter (z.B. angelo@abcona.de) mit seiner persönlichen Signatur. Empfohlen für persönliche Berater-Mails. TEMPLATE: Feste Absenderadresse. AUTO: noreply, für automatische System-Mails.' : 'USER: Email comes from the logged-in employee (e.g. angelo@abcona.de) with their personal signature. Recommended for personal consultant mails. TEMPLATE: Fixed sender address. AUTO: noreply, for automated system mails.',
                        r: () => `<div class="es-tut-sim" style="padding:8px 12px;">
  <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:6px;">
    <div class="es-tut-crd" style="text-align:center;padding:8px;opacity:.5;">
      <div style="font-size:16px;">▣</div>
      <div style="font-weight:600;font-size:9px;margin-top:3px;">Template</div>
      <div style="font-size:8px;color:#666;">${isDE?'Feste Adresse':'Fixed address'}</div>
    </div>
    <div class="es-tut-pulse es-tut-crd" style="background:#e6f1fb;text-align:center;padding:8px;">
      <div style="font-size:16px;">👤</div>
      <div style="font-weight:600;color:#0c447c;font-size:9px;margin-top:3px;">User</div>
      <div style="font-size:8px;color:#185fa5;">${isDE?'Eingeloggter Mitarbeiter':'Logged-in employee'}</div>
      <div style="font-size:8px;background:#163258;color:#fff;border-radius:3px;padding:2px 4px;margin-top:4px;">${isDE?'Empfohlen':'Recommended'}</div>
    </div>
    <div class="es-tut-crd" style="text-align:center;padding:8px;opacity:.5;">
      <div style="font-size:16px;">🖨</div>
      <div style="font-weight:600;font-size:9px;margin-top:3px;">Auto</div>
      <div style="font-size:8px;color:#666;">noreply</div>
    </div>
  </div>
  <div style="margin-top:6px;background:#e6f1fb;border-radius:4px;padding:4px 7px;font-size:8px;color:#0c447c;">From = ${isDE?'eingeloggter User · Signatur aus User-Profil':'logged-in user · signature from user profile'}</div>
</div>`
                    },
                    {
                        t: isDE ? 'HTML schreiben & Variablen einfügen' : 'Write HTML & Insert Variables',
                        d: isDE ? 'Im mittleren Bereich schreiben Sie den E-Mail-Inhalt. In der Sidebar links unter "Variablen" sehen Sie alle verfügbaren Platzhalter. Klick auf einen Variablen-Chip fügt ihn an der Cursor-Position ein. {name} wird beim Versand durch den echten Namen ersetzt.' : 'In the middle area you write the email content. In the left sidebar under "Variables" you see all available placeholders. Click on a variable chip to insert it at the cursor position. {name} is replaced by the real name on send.',
                        r: () => `<div class="es-tut-sim" style="padding:8px 10px;">
  <div style="display:grid;grid-template-columns:minmax(0,1.3fr) minmax(0,1fr);gap:8px;">
    <div>
      <div style="display:flex;gap:3px;margin-bottom:4px;">
        <span class="es-tut-tab-on">${isDE?'Visuell':'Visual'}</span>
        <span class="es-tut-tab-off">Code</span>
        <span class="es-tut-tab-off">TXT</span>
      </div>
      <div style="border:1px solid #eee;border-radius:4px;overflow:hidden;">
        <div style="background:#163258;color:#fff;padding:5px 8px;font-size:9px;font-weight:600;text-align:center;">abcona e. K.</div>
        <div style="padding:6px 8px;font-size:9px;">
          <p style="margin:0 0 3px;">${isDE?'Hallo':'Hello'} <span style="background:#dbeafe;color:#1d4ed8;padding:0 3px;border-radius:2px;">{name}</span>,</p>
          <p style="margin:0 0 4px;">${isDE?'Ihr Profil wurde erstellt.':'Your profile has been created.'}</p>
          <div style="display:inline-block;background:#163258;color:#fff;padding:3px 8px;border-radius:3px;font-size:8px;">${isDE?'Profil ansehen':'View Profile'}</div>
        </div>
      </div>
    </div>
    <div>
      <div style="font-size:8px;color:#888;margin-bottom:3px;">{} ${isDE?'Variablen':'Variables'} 13</div>
      <div style="border:1px solid #eee;border-radius:4px;overflow:hidden;">
        <div style="background:#163258;color:#fff;padding:3px 7px;font-size:8px;">${isDE?'Aus Kontext':'From Context'}</div>
        <div style="padding:4px;">
          ${['{name}','{email}','{cv_link}','{cv_version}'].map((v,i)=>`<div class="es-tut-chip${i===0?' es-tut-pulse':''}">${v}</div>`).join('')}
          <div style="font-size:7px;color:#888;margin:3px 0 2px;">User-Profil</div>
          <div class="es-tut-chip es-tut-chip-g">{sender_name}</div>
          <div class="es-tut-chip es-tut-chip-g">{sender_email}</div>
        </div>
      </div>
    </div>
  </div>
</div>`
                    },
                    {
                        t: isDE ? 'Live-Vorschau & Test-E-Mail' : 'Live Preview & Test Email',
                        d: isDE ? 'Die rechte Spalte zeigt die E-Mail in Echtzeit. Wechseln Sie zwischen Outlook, Gmail und TXT. In der Sidebar unter "Test-E-Mail senden" können Sie sofort eine echte Test-E-Mail an sich selbst schicken um das Ergebnis zu prüfen.' : 'The right column shows the email in real time. Switch between Outlook, Gmail and TXT. In the sidebar under "Send Test Email" you can immediately send a real test email to yourself to check the result.',
                        r: () => `<div class="es-tut-sim" style="padding:8px 10px;">
  <div style="display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1.1fr);gap:8px;">
    <div>
      <div style="border:1px solid #eee;border-radius:4px;overflow:hidden;">
        <div style="background:#163258;color:#fff;padding:4px 7px;font-size:8px;">✈ ${isDE?'Test-E-Mail senden':'Send Test Email'}</div>
        <div style="padding:7px;">
          <div class="es-tut-inp" style="font-size:8px;margin-bottom:5px;">${isDE?'Empfänger-E-Mail...':'Recipient email...'}</div>
          <div class="es-tut-pulse" style="background:#163258;color:#fff;border-radius:4px;padding:3px 8px;font-size:8px;text-align:center;">✈ ${isDE?'Senden':'Send'}</div>
        </div>
      </div>
    </div>
    <div>
      <div style="border:1px solid #eee;border-radius:4px;overflow:hidden;">
        <div style="background:#163258;color:#fff;padding:4px 7px;font-size:8px;display:flex;justify-content:space-between;">
          <span>👁 ${isDE?'Live-Vorschau':'Live Preview'}</span>
          <div style="display:flex;gap:2px;">
            <span class="es-tut-tab-on" style="font-size:7px;padding:1px 4px;">Outlook</span>
            <span class="es-tut-tab-off" style="font-size:7px;padding:1px 4px;">Gmail</span>
            <span class="es-tut-tab-off" style="font-size:7px;padding:1px 4px;">TXT</span>
          </div>
        </div>
        <div style="background:#163258;color:#fff;padding:5px 8px;font-size:9px;font-weight:600;">abcona e. K.</div>
        <div style="padding:6px 8px;background:#fff;">
          <p style="margin:0 0 3px;font-size:9px;">${isDE?'Hallo':'Hello'} <b>Max Mustermann</b>,</p>
          <p style="margin:0 0 4px;font-size:9px;">${isDE?'Ihr Profil wurde erfolgreich erstellt.':'Your profile has been successfully created.'}</p>
          <span style="display:inline-block;background:#163258;color:#fff;padding:3px 7px;border-radius:3px;font-size:8px;">${isDE?'Profil ansehen':'View Profile'}</span>
        </div>
      </div>
    </div>
  </div>
</div>`
                    },
                    {
                        t: isDE ? 'Speichern — Version & TXT automatisch' : 'Save — Version & TXT automatically',
                        d: isDE ? 'Klicken Sie oben rechts auf "Speichern". Jedes Speichern legt automatisch eine neue Version mit Zeitstempel an. Die TXT-Version (Plaintext) wird dabei automatisch aus dem HTML generiert — Sie müssen die TXT-Version nie manuell pflegen.' : 'Click "Save" in the top right. Every save automatically creates a new version with timestamp. The TXT version (plaintext) is automatically generated from the HTML — you never need to maintain the TXT version manually.',
                        r: () => `<div class="es-tut-sim" style="padding:8px 12px;text-align:center;">
  <div style="display:flex;justify-content:flex-end;gap:6px;margin-bottom:10px;">
    <div style="border:1px solid #163258;color:#163258;border-radius:4px;padding:4px 10px;font-size:9px;">${isDE?'Speichern unter':'Save as'}</div>
    <div class="es-tut-pulse" style="background:#163258;color:#fff;border-radius:4px;padding:4px 10px;font-size:9px;">${isDE?'Speichern':'Save'}</div>
  </div>
  <div style="display:flex;gap:8px;align-items:center;justify-content:center;flex-wrap:wrap;margin-bottom:8px;">
    <div style="background:#163258;color:#fff;border-radius:5px;padding:5px 10px;font-size:9px;font-weight:600;">📝 HTML</div>
    <span style="color:#163258;font-size:14px;">→</span>
    <div style="background:#faeeda;color:#633806;border-radius:5px;padding:5px 10px;font-size:9px;border:1px solid #ef9f27;">✨ TXT ${isDE?'auto':'auto'}</div>
    <span style="color:#163258;font-size:14px;">→</span>
    <div style="background:#eaf3de;color:#27500a;border-radius:5px;padding:5px 10px;font-size:9px;border:1px solid #97c459;">🔖 Version 1</div>
  </div>
  <div style="background:#163258;color:#fff;border-radius:4px;padding:4px 10px;font-size:9px;display:inline-block;">✓ ${isDE?'Gespeichert — TXT automatisch generiert':'Saved — TXT automatically generated'}</div>
</div>`
                    },
                ],
            },

            versionen: {
                title: isDE ? '▶ Interaktiv: Versionsverlauf & Meilensteine' : '▶ Interactive: Version History & Milestones',
                steps: [
                    {
                        t: isDE ? 'Versionsverlauf öffnen' : 'Open Version History',
                        d: isDE ? 'In der blauen Leiste oben auf "Versionsverlauf X offiziell" klicken. Das Panel öffnet sich und zeigt alle gespeicherten Versionen mit Zeitstempel. Die grün markierte Version ist die aktuell aktive.' : 'Click "Version History X official" in the blue bar at the top. The panel opens and shows all saved versions with timestamps. The green highlighted version is currently active.',
                        r: () => `<div class="es-tut-sim" style="padding:8px 12px;">
  <div style="border:1px solid #eee;border-radius:5px;overflow:hidden;">
    <div style="background:#163258;color:#fff;padding:5px 10px;font-size:9px;display:flex;gap:6px;align-items:center;flex-wrap:wrap;">
      <span class="es-tut-pulse" style="background:rgba(255,255,255,.25);padding:2px 8px;border-radius:3px;">⏱ ${isDE?'Versionsverlauf':'Version History'} 2 ${isDE?'offiziell':'official'}</span>
      <span style="opacity:.6;">⭐ 0 ${isDE?'Meilensteine':'Milestones'}</span>
      <span style="opacity:.6;">↩</span><span style="opacity:.6;">↪</span>
      <span style="opacity:.6;margin-left:auto;">⇄ ${isDE?'Übersetzungen':'Translations'}</span>
    </div>
    <div style="padding:8px;display:flex;gap:8px;align-items:center;">
      <div style="background:#f8f8f8;border:1px solid #eee;border-radius:5px;padding:6px 10px;font-size:8px;text-align:center;opacity:.6;">
        <div style="font-weight:600;">2</div>
        <div style="color:#888;font-size:7px;">${isDE?'Auto-Version':'Auto version'}</div>
        <div style="color:#888;font-size:7px;">01.06. 15:00</div>
      </div>
      <span style="color:#888;">←</span>
      <div class="es-tut-pulse" style="background:#eaf3de;border:2px solid #28a745;border-radius:5px;padding:6px 10px;font-size:8px;text-align:center;">
        <div style="width:18px;height:18px;border-radius:50%;background:#28a745;color:#fff;font-size:8px;font-weight:600;display:flex;align-items:center;justify-content:center;margin:0 auto 3px;">1</div>
        <div style="font-weight:600;color:#27500a;">${isDE?'Initiale Version · Aktiv':'Initial Version · Active'}</div>
        <div style="color:#3b6d11;font-size:7px;">01.06. 13:22</div>
      </div>
      <div style="font-size:8px;color:#888;">← ${isDE?'anklicken zum Wiederherstellen':'click to restore'}</div>
    </div>
  </div>
</div>`
                    },
                    {
                        t: isDE ? 'Änderungsnotiz eingeben' : 'Enter Change Note',
                        d: isDE ? 'Vor dem Speichern können Sie im Textfeld "Änderungsnotiz..." eine kurze Beschreibung eingeben was geändert wurde (z.B. "Logo aktualisiert", "Neuer CTA-Text"). Diese Notiz erscheint im Versionsverlauf und hilft bei der späteren Suche.' : 'Before saving you can enter a short description in the "Change note..." field of what was changed (e.g. "Logo updated", "New CTA text"). This note appears in the version history and helps with later searches.',
                        r: () => `<div class="es-tut-sim" style="padding:8px 12px;">
  <div style="background:#163258;color:#fff;border-radius:5px;padding:6px 10px;font-size:9px;display:flex;align-items:center;gap:6px;flex-wrap:wrap;">
    <span style="opacity:.6;">⏱</span><span style="opacity:.6;">⭐</span><span style="opacity:.6;">↩</span><span style="opacity:.6;">↪</span>
    <span class="es-tut-pulse" style="background:rgba(255,255,255,.3);padding:2px 7px;border-radius:3px;font-size:8px;">⭐ ${isDE?'Merken':'Save Milestone'}</span>
    <input style="flex:1;min-width:100px;background:rgba(255,255,255,.15);border:1px solid rgba(255,255,255,.3);border-radius:3px;padding:2px 6px;color:#fff;font-size:8px;" placeholder="${isDE?'Änderungsnotiz...':'Change note...'}">
  </div>
  <div style="margin-top:6px;background:#eaf3de;border-radius:4px;padding:4px 7px;font-size:8px;color:#27500a;">${isDE?'Tipp: Notiz eingeben → Speichern → Version ist dokumentiert':'Tip: Enter note → Save → Version is documented'}</div>
</div>`
                    },
                    {
                        t: isDE ? 'Meilenstein setzen' : 'Set Milestone',
                        d: isDE ? 'Mit "Merken" markieren Sie die aktuelle Version als wichtigen Meilenstein (z.B. "Stand vor Redesign"). Meilensteine sind im Versionsverlauf mit 📌 gekennzeichnet und bleiben dauerhaft erhalten — ideal für stabile Versionen die Sie jederzeit wiederherstellen möchten.' : 'Use "Save Milestone" to mark the current version as an important milestone (e.g. "Before redesign"). Milestones are marked with 📌 in the version history and are permanently kept — ideal for stable versions you want to restore at any time.',
                        r: () => `<div class="es-tut-sim" style="padding:8px 12px;">
  <div style="border:1px solid #eee;border-radius:5px;overflow:hidden;">
    <div style="background:#163258;color:#fff;padding:4px 8px;font-size:9px;">${isDE?'Meilenstein setzen':'Set Milestone'}</div>
    <div style="padding:8px;">
      <input style="width:100%;border:1px solid #4a90d9;border-radius:4px;padding:4px 8px;font-size:9px;margin-bottom:6px;" value="${isDE?'Stand vor Redesign':'Before redesign'}">
      <div style="display:flex;gap:5px;justify-content:flex-end;">
        <div style="border:1px solid #eee;border-radius:4px;padding:3px 10px;font-size:9px;color:#666;">${isDE?'Abbrechen':'Cancel'}</div>
        <div class="es-tut-pulse" style="background:#163258;color:#fff;border-radius:4px;padding:3px 10px;font-size:9px;">📌 ${isDE?'Merken':'Save Milestone'}</div>
      </div>
    </div>
  </div>
  <div style="margin-top:5px;border:1px solid #eee;border-radius:4px;overflow:hidden;">
    <div style="background:#f8f8f8;padding:3px 8px;font-size:8px;font-weight:500;">${isDE?'Versionsverlauf nach Merken:':'Version history after milestone:'}</div>
    <div style="padding:5px 8px;display:flex;gap:6px;align-items:center;">
      <span style="font-size:14px;">📌</span>
      <div><div style="font-size:9px;font-weight:500;">${isDE?'Stand vor Redesign':'Before redesign'}</div><div style="font-size:8px;color:#888;">01.06.2026 15:30</div></div>
    </div>
  </div>
</div>`
                    },
                    {
                        t: isDE ? 'Version wiederherstellen' : 'Restore Version',
                        d: isDE ? 'Im Versionsverlauf auf eine ältere Version klicken → Bestätigungsdialog erscheint → "Wiederherstellen" klicken. Die aktuelle Version wird dabei automatisch als Backup gespeichert. Sie können also jederzeit wieder zurückwechseln — nichts geht verloren.' : 'Click on an older version in the version history → confirmation dialog appears → click "Restore". The current version is automatically saved as a backup. So you can switch back at any time — nothing is lost.',
                        r: () => `<div class="es-tut-sim" style="padding:8px 12px;">
  <div style="background:#fff;border:1px solid #e24b4a;border-radius:5px;padding:10px;">
    <div style="font-weight:600;color:#e24b4a;margin-bottom:5px;font-size:9px;">⚠ ${isDE?'Version wiederherstellen':'Restore Version'}</div>
    <div style="color:#333;margin-bottom:8px;font-size:9px;line-height:1.6;">${isDE?'Möchten Sie Version 1 (01.06. 13:22) wiederherstellen?<br>Die aktuelle Version bleibt als Backup erhalten.':'Would you like to restore Version 1 (01.06. 13:22)?<br>The current version will be kept as a backup.'}</div>
    <div style="display:flex;gap:6px;justify-content:flex-end;">
      <div style="border:1px solid #eee;border-radius:4px;padding:3px 10px;font-size:9px;color:#666;">${isDE?'Abbrechen':'Cancel'}</div>
      <div class="es-tut-pulse" style="background:#163258;color:#fff;border-radius:4px;padding:3px 10px;font-size:9px;">${isDE?'Wiederherstellen':'Restore'}</div>
    </div>
  </div>
</div>`
                    },
                ],
            },

            module: {
                title: isDE ? '▶ Interaktiv: Module einfügen' : '▶ Interactive: Insert Modules',
                steps: [
                    {
                        t: isDE ? 'Was sind Module?' : 'What are Modules?',
                        d: isDE ? 'Module sind fertige HTML-Bausteine (Header, Footer, Buttons) die zentral verwaltet werden. Einmal ändern — überall aktuell. Syntax: {{block:identifier}}. Beim Versand wird der Platzhalter automatisch durch den Modul-Inhalt ersetzt.' : 'Modules are ready-made HTML building blocks (header, footer, buttons) managed centrally. Change once — updated everywhere. Syntax: {{block:identifier}}. On send, the placeholder is automatically replaced by the module content.',
                        r: () => `<div class="es-tut-sim" style="padding:8px 12px;">
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;">
    ${[['HEADER','abcona_header_blau','#e6f1fb','#0c447c'],['FOOTER','footer_standard','#eaf3de','#27500a'],['BUTTON','button_blau / button_gruen','#faeeda','#633806'],['SECTION','support_kontakt','#f1efe8','#444']].map(([t,n,bg,c])=>`
    <div class="es-tut-crd" style="background:${bg};">
      <div style="font-weight:600;color:${c};font-size:8px;margin-bottom:2px;">${t}</div>
      <div style="font-family:monospace;color:${c};font-size:7px;opacity:.8;">${n}</div>
    </div>`).join('')}
  </div>
  <div style="margin-top:6px;background:#eaf3de;border-radius:4px;padding:4px 7px;font-size:8px;color:#27500a;">${isDE?'Modul ändern → Änderung gilt in ALLEN Vorlagen die es verwenden':'Change module → change applies in ALL templates that use it'}</div>
</div>`
                    },
                    {
                        t: isDE ? 'Module-Sidebar öffnen' : 'Open Module Sidebar',
                        d: isDE ? 'In der linken Sidebar nach unten scrollen bis zum Bereich "Module". Klicken Sie auf den Header um die Modul-Liste zu öffnen. Die Module sind nach Typ gruppiert: BUTTON, FOOTER, HEADER, SECTION.' : 'Scroll down in the left sidebar to the "Modules" section. Click the header to open the module list. Modules are grouped by type: BUTTON, FOOTER, HEADER, SECTION.',
                        r: () => `<div class="es-tut-sim" style="padding:8px 10px;">
  <div style="border:1px solid #eee;border-radius:5px;overflow:hidden;max-width:220px;">
    <div style="background:#163258;color:#fff;padding:5px 10px;font-size:9px;font-weight:500;">⊞ ${isDE?'Module':'Modules'} ∧</div>
    <div style="padding:6px 8px;font-size:8px;">
      <div style="color:#888;text-transform:uppercase;font-size:7px;margin-bottom:3px;">BUTTON</div>
      <div class="es-tut-pulse" style="display:flex;align-items:center;gap:5px;padding:4px 7px;border:1px solid #b5d4f4;border-radius:4px;margin-bottom:2px;cursor:pointer;background:#e6f1fb;">
        <span>✈</span><span style="color:#0c447c;font-weight:500;">Button — ${isDE?'Blau':'Blue'}</span>
      </div>
      <div style="display:flex;align-items:center;gap:5px;padding:4px 7px;border:1px solid #eee;border-radius:4px;margin-bottom:5px;opacity:.7;"><span>✈</span><span>Button — ${isDE?'Grün':'Green'}</span></div>
      <div style="color:#888;text-transform:uppercase;font-size:7px;margin-bottom:3px;">FOOTER</div>
      <div style="display:flex;align-items:center;gap:5px;padding:4px 7px;border:1px solid #eee;border-radius:4px;margin-bottom:2px;opacity:.7;"><span>📋</span><span>Footer Auto-Reply</span></div>
      <div style="display:flex;align-items:center;gap:5px;padding:4px 7px;border:1px solid #eee;border-radius:4px;margin-bottom:5px;opacity:.7;"><span>📋</span><span>Footer Standard</span></div>
      <div style="color:#888;text-transform:uppercase;font-size:7px;margin-bottom:3px;">HEADER</div>
      <div style="display:flex;align-items:center;gap:5px;padding:4px 7px;border:1px solid #eee;border-radius:4px;opacity:.7;"><span>📋</span><span>Header — ${isDE?'Blau':'Blue'}</span></div>
    </div>
  </div>
</div>`
                    },
                    {
                        t: isDE ? 'Modul anklicken → eingefügt' : 'Click Module → Inserted',
                        d: isDE ? 'Cursor im HTML-Editor an die gewünschte Stelle setzen, dann in der Sidebar auf das Modul klicken. Der Platzhalter {{block:modulname}} erscheint sofort im Code. In der Live-Vorschau rechts sehen Sie das aufgelöste Modul.' : 'Position cursor in the HTML editor, then click the module in the sidebar. The placeholder {{block:modulname}} appears immediately in the code. In the live preview on the right you see the resolved module.',
                        r: () => `<div class="es-tut-sim" style="padding:8px 10px;">
  <div style="display:grid;grid-template-columns:minmax(0,1.2fr) minmax(0,1fr);gap:8px;">
    <div>
      <div style="font-size:8px;color:#888;margin-bottom:3px;">${isDE?'HTML nach Einfügen:':'HTML after inserting:'}</div>
      <div class="es-tut-editor"><span style="background:#264f78;">{{block:abcona_header_blau}}</span>
&lt;tr&gt;&lt;td style="padding:24px;"&gt;
  &lt;p&gt;Hallo {name},&lt;/p&gt;
  <span style="background:#264f78;">{{block:button_blau}}</span>
&lt;/td&gt;&lt;/tr&gt;
<span style="background:#264f78;">{{block:footer_standard}}</span><span class="es-tut-cur"></span></div>
    </div>
    <div>
      <div style="font-size:8px;color:#888;margin-bottom:3px;">${isDE?'Live-Vorschau:':'Live Preview:'}</div>
      <div style="border:1px solid #e0e0e0;border-radius:5px;overflow:hidden;">
        <div style="background:#163258;color:#fff;padding:5px 8px;font-size:9px;font-weight:600;">abcona e. K.</div>
        <div style="padding:7px 8px;">
          <p style="margin:0 0 3px;font-size:9px;">${isDE?'Hallo':'Hello'} <b>{name}</b>,</p>
          <span style="display:inline-block;background:#163258;color:#fff;padding:3px 8px;border-radius:3px;font-size:8px;">{button_text}</span>
        </div>
        <div style="background:#f0f0f0;padding:3px 8px;font-size:7px;color:#999;">${isDE?'Impressum · Abmelden':'Imprint · Unsubscribe'}</div>
      </div>
    </div>
  </div>
</div>`
                    },
                ],
            },

            uebersetzungen: {
                title: isDE ? '▶ Interaktiv: Mehrsprachige Vorlagen' : '▶ Interactive: Multilingual Templates',
                steps: [
                    {
                        t: isDE ? 'Sprachen aktivieren' : 'Activate Languages',
                        d: isDE ? 'In der blauen Leiste auf "Sprachen" klicken. Das Panel zeigt alle im Portal installierten Sprachen. DE ist immer Referenz und kann nicht deaktiviert werden. Häkchen bei den gewünschten Sprachen setzen (z.B. EN, IT).' : 'Click "Languages" in the blue bar. The panel shows all languages installed in the portal. DE is always the reference and cannot be deactivated. Check the desired languages (e.g. EN, IT).',
                        r: () => `<div class="es-tut-sim" style="padding:8px 12px;">
  <div style="border:1px solid #eee;border-radius:5px;overflow:hidden;">
    <div style="background:#163258;color:#fff;padding:5px 10px;font-size:9px;font-weight:500;">${isDE?'Übersetzungssprachen für diese Vorlage':'Translation languages for this template'}</div>
    <div style="padding:8px;">
      <div style="display:flex;gap:10px;flex-wrap:wrap;margin-bottom:8px;">
        <label style="display:flex;align-items:center;gap:3px;font-size:9px;"><input type="checkbox"> EN English</label>
        <label style="display:flex;align-items:center;gap:3px;font-size:9px;"><input type="checkbox"> ES Spanish</label>
        <label style="display:flex;align-items:center;gap:3px;font-size:9px;"><input type="checkbox"> FR French</label>
        <label style="display:flex;align-items:center;gap:3px;font-size:9px;" class="es-tut-pulse"><input type="checkbox" checked> IT Italian</label>
      </div>
      <div style="background:#e6f1fb;border-radius:4px;padding:4px 7px;font-size:8px;color:#0c447c;">DE ${isDE?'ist immer Referenz — nie automatisch überschrieben':'is always reference — never automatically overwritten'}</div>
    </div>
  </div>
</div>`
                    },
                    {
                        t: isDE ? 'Auto-Übersetzen starten' : 'Start Auto-Translate',
                        d: isDE ? 'In der blauen Leiste auf "Auto-Übersetzen" klicken. Die KI (Deepseek) übersetzt alle aktivierten Sprachen automatisch. Variablen wie {name} oder {cv_link} werden dabei NIEMALS übersetzt — nur der normale Text.' : 'Click "Auto-Translate" in the blue bar. The AI (Deepseek) automatically translates all activated languages. Variables like {name} or {cv_link} are NEVER translated — only the normal text.',
                        r: () => `<div class="es-tut-sim" style="padding:8px 12px;">
  <div style="display:flex;gap:8px;align-items:center;justify-content:center;flex-wrap:wrap;margin-bottom:8px;">
    <div style="background:#163258;color:#fff;border-radius:5px;padding:5px 10px;font-size:9px;font-weight:600;">🇩🇪 DE ${isDE?'Basis':'Base'}</div>
    <span style="font-size:14px;color:#163258;">→</span>
    <div class="es-tut-pulse" style="background:#faeeda;color:#633806;border-radius:5px;padding:5px 10px;font-size:9px;border:1px solid #ef9f27;">✨ ${isDE?'KI übersetzt':'AI translates'}</div>
    <span style="font-size:14px;color:#163258;">→</span>
    <div style="background:#eaf3de;color:#27500a;border-radius:5px;padding:5px 10px;font-size:9px;border:1px solid #97c459;">🇬🇧 EN · 🇮🇹 IT</div>
  </div>
  <div class="es-tut-editor">
<span style="color:#6a9955;"># DE (${isDE?'Basis':'base'}):</span>
Hallo <span style="background:#264f78;">{name}</span>, ${isDE?'Ihr Profil ist fertig.':'Your profile is ready.'}
<span style="color:#6a9955;"># IT (${isDE?'generiert — {name} unberührt':'generated — {name} unchanged'}):</span>
Ciao <span style="background:#264f78;">{name}</span>, il tuo profilo è pronto.</div>
  <div style="margin-top:5px;background:#eaf3de;border-radius:4px;padding:4px 7px;font-size:8px;color:#27500a;">{name}, {cv_link} ${isDE?'usw. werden NIE übersetzt':'etc. are NEVER translated'}</div>
</div>`
                    },
                    {
                        t: isDE ? 'Übersetzung prüfen & bearbeiten' : 'Check & Edit Translation',
                        d: isDE ? 'Im Übersetzungs-Panel auf das Stift-Symbol (✏) neben einer Sprache klicken → Editor öffnet sich in dieser Sprache → Text direkt bearbeiten → Speichern. So können automatisch übersetzte Texte manuell korrigiert werden.' : 'In the translations panel click the pencil icon (✏) next to a language → editor opens in that language → edit text directly → save. This allows manually correcting automatically translated texts.',
                        r: () => `<div class="es-tut-sim" style="padding:8px 12px;">
  <div style="border:1px solid #eee;border-radius:5px;overflow:hidden;">
    <div style="background:#163258;color:#fff;padding:5px 10px;font-size:9px;display:flex;gap:4px;">
      <span style="background:rgba(255,255,255,.15);padding:2px 7px;border-radius:3px;">🇩🇪 DE ${isDE?'Basis':'Base'}</span>
      <span style="background:rgba(255,255,255,.15);padding:2px 7px;border-radius:3px;">🇬🇧 EN</span>
      <span class="es-tut-pulse" style="background:#fff;color:#163258;padding:2px 7px;border-radius:3px;font-weight:600;">🇮🇹 IT ✏</span>
    </div>
    <div style="padding:8px;">
      <div class="es-tut-editor">Ciao <span style="background:#264f78;">{name}</span>,

Il tuo profilo consulente è pronto.
Clicca qui: <span style="background:#264f78;">{cv_link}</span>

Cordiali saluti, <span style="background:#264f78;">{sender_name}</span><span class="es-tut-cur"></span></div>
      <div style="margin-top:5px;display:flex;gap:4px;">
        <div style="flex:1;background:#163258;color:#fff;border-radius:4px;padding:4px 7px;font-size:8px;text-align:center;">💾 ${isDE?'Speichern':'Save'}</div>
        <div style="background:#f1f1f1;color:#444;border-radius:4px;padding:4px 7px;font-size:8px;">🔒 ${isDE?'Sperren':'Lock'}</div>
      </div>
    </div>
  </div>
</div>`
                    },
                    {
                        t: isDE ? 'Automatischer Versand in richtiger Sprache' : 'Automatic Send in Correct Language',
                        d: isDE ? 'Beim Versand wählt das System automatisch die Sprache des Empfängers (aus seinem Profil). Fehlt eine Übersetzung, wird sie beim ersten Versand automatisch generiert und in der Datenbank gespeichert — beim nächsten Versand ist sie bereits fertig.' : 'On send the system automatically selects the recipient\'s language (from their profile). If a translation is missing, it is automatically generated on the first send and saved in the database — on the next send it is already ready.',
                        r: () => `<div class="es-tut-sim" style="padding:8px 12px;">
  <div style="display:flex;flex-direction:column;gap:0;">
    ${[
      ['1', isDE?'EmailStudio.send() aufgerufen':'EmailStudio.send() called', isDE?'template=cv_generated · recipient=luca@example.it':'template=cv_generated · recipient=luca@example.it', '#163258'],
      ['2', isDE?'Sprache prüfen':'Check language', isDE?'User-Profil: lang=it → suche IT-Übersetzung':'User profile: lang=it → search for IT translation', '#163258'],
      ['3', isDE?'Nicht in DB gefunden':'Not found in DB', isDE?'Keine IT-Übersetzung vorhanden':'No IT translation available', '#f59e0b'],
      ['4', isDE?'KI übersetzt':'AI translates', isDE?'DE → IT · Variablen unberührt':'DE → IT · variables unchanged', '#f59e0b'],
      ['5', isDE?'Gespeichert & gesendet':'Saved & sent', isDE?'Luca erhält E-Mail auf Italienisch 🇮🇹':'Luca receives email in Italian 🇮🇹', '#28a745'],
    ].map(([n,t,d,c])=>`
    <div style="display:flex;gap:6px;align-items:flex-start;padding:4px 0;border-bottom:0.5px solid #eee;">
      <div style="width:16px;height:16px;border-radius:50%;background:${c};color:#fff;display:flex;align-items:center;justify-content:center;font-size:8px;font-weight:600;flex-shrink:0;margin-top:1px;">${n}</div>
      <div><div style="font-size:9px;font-weight:500;color:#333;">${t}</div><div style="font-size:8px;color:#888;">${d}</div></div>
    </div>`).join('')}
  </div>
</div>`
                    },
                ],
            },

            duplizieren: {
                title: isDE ? '▶ Interaktiv: Vorlage duplizieren' : '▶ Interactive: Duplicate Template',
                steps: [
                    {
                        t: isDE ? 'Wann duplizieren?' : 'When to duplicate?',
                        d: isDE ? 'Duplizieren ist ideal wenn eine ähnliche Vorlage bereits existiert. Beispiel: pipeline_success und pipeline_error haben denselben Aufbau — nur einige Texte unterscheiden sich. Sie sparen die gesamte Grundstruktur und ändern nur die Unterschiede.' : 'Duplicating is ideal when a similar template already exists. Example: pipeline_success and pipeline_error have the same structure — only some texts differ. You save the entire base structure and only change the differences.',
                        r: () => `<div class="es-tut-sim" style="padding:8px 12px;">
  ${[['pipeline_success','pipeline_error',isDE?'Gleiche Struktur, Erfolg vs. Fehler':'Same structure, success vs. error'],['upload_received','upload_error',isDE?'Upload-Bestätigung vs. Fehlermeldung':'Upload confirmation vs. error'],['cv_generated_de','cv_generated_en',isDE?'Gleicher Inhalt, andere Sprache':'Same content, different language']].map(([a,b,d])=>`
  <div style="display:flex;align-items:center;gap:6px;padding:4px 0;border-bottom:0.5px solid #eee;font-size:8px;">
    <code style="background:#f1f1f1;padding:1px 4px;border-radius:2px;">${a}</code>
    <span style="color:#163258;font-weight:600;">→</span>
    <code style="background:#e6f1fb;color:#0c447c;padding:1px 4px;border-radius:2px;">${b}</code>
    <span style="color:#888;">${d}</span>
  </div>`).join('')}
  <div style="margin-top:6px;background:#faeeda;border-radius:4px;padding:4px 7px;font-size:8px;color:#633806;">${isDE?'Kopie ist vollständig unabhängig — Änderungen am Original betreffen die Kopie nicht':'Copy is fully independent — changes to the original do not affect the copy'}</div>
</div>`
                    },
                    {
                        t: isDE ? '📋 Symbol klicken' : 'Click 📋 Icon',
                        d: isDE ? 'In der Vorlagen-Übersicht das 📋 Symbol in der Aktionen-Spalte klicken. Es öffnet sich sofort ein Dialog für die neue Vorlage. Alternativ: im Studio oben rechts auf "Speichern unter" klicken.' : 'In the template overview click the 📋 icon in the actions column. A dialog for the new template opens immediately. Alternatively: click "Save as" in the top right of the studio.',
                        r: () => `<div class="es-tut-sim" style="padding:8px 12px;">
  <div style="border:1px solid #eee;border-radius:5px;overflow:hidden;">
    <div style="background:#163258;color:#fff;padding:4px 8px;font-size:8px;display:grid;grid-template-columns:2fr 1fr 1fr 80px;">
      <span>Name / Identifier</span><span>${isDE?'Absender':'Sender'}</span><span>Status</span><span>${isDE?'Aktionen':'Actions'}</span>
    </div>
    <div style="display:grid;grid-template-columns:2fr 1fr 1fr 80px;padding:6px 8px;font-size:8px;align-items:center;">
      <div><b style="color:#163258;">Pipeline ${isDE?'Erfolg':'Success'}</b><br><span style="font-family:monospace;color:#888;font-size:7px;">pipeline_success</span></div>
      <span style="color:#f59e0b;">● Auto</span>
      <span><span style="background:#28a745;color:#fff;border-radius:3px;padding:1px 5px;font-size:7px;">${isDE?'Aktiv':'Active'}</span></span>
      <div style="display:flex;gap:4px;align-items:center;">
        <span style="color:#888;">✏</span>
        <span class="es-tut-pulse" style="background:#e6f1fb;color:#163258;border-radius:3px;padding:2px 5px;font-size:11px;cursor:pointer;">📋</span>
        <span style="color:#888;">👁 ✈</span>
      </div>
    </div>
  </div>
</div>`
                    },
                    {
                        t: isDE ? 'Neuen Identifier vergeben' : 'Assign New Identifier',
                        d: isDE ? 'Geben Sie der Kopie einen neuen Identifier und Anzeigenamen. Der Identifier muss eindeutig sein. Alle Inhalte (HTML, TXT, Variablen, Module, Einstellungen) werden vollständig kopiert — Sie müssen nur die unterschiedlichen Stellen ändern.' : 'Give the copy a new identifier and display name. The identifier must be unique. All contents (HTML, TXT, variables, modules, settings) are fully copied — you only need to change the different parts.',
                        r: () => `<div class="es-tut-sim" style="padding:8px 12px;">
  <div style="font-size:9px;font-weight:600;color:#163258;margin-bottom:5px;">📋 ${isDE?'Dupliziert von':'Duplicated from'}: pipeline_success</div>
  <div style="display:flex;flex-direction:column;gap:5px;">
    <div><div class="es-tut-lbl">${isDE?'NEUER IDENTIFIER *':'NEW IDENTIFIER *'}</div>
      <div class="es-tut-pulse" style="border:1px solid #4a90d9;border-radius:4px;padding:3px 6px;font-family:monospace;background:#e6f1fb;color:#0c447c;">pipeline_error<span class="es-tut-cur"></span></div>
    </div>
    <div><div class="es-tut-lbl">${isDE?'NEUER NAME':'NEW NAME'}</div>
      <div class="es-tut-inp">${isDE?'Pipeline Fehler — Verarbeitung fehlgeschlagen':'Pipeline Error — Processing Failed'}</div>
    </div>
  </div>
  <div style="margin-top:6px;border:1px solid #eee;border-radius:4px;padding:5px 7px;font-size:8px;">
    <div style="font-weight:500;color:#333;margin-bottom:3px;">${isDE?'Was wird kopiert?':'What is copied?'}</div>
    <div style="display:flex;gap:8px;flex-wrap:wrap;">
      ${['HTML','TXT',isDE?'Absender-Modus':'Sender Mode',isDE?'Variablen':'Variables',isDE?'Module':'Modules',isDE?'Einstellungen':'Settings'].map(x=>`<span style="font-size:8px;color:#27500a;">✓ ${x}</span>`).join('')}
    </div>
  </div>
</div>`
                    },
                ],
            },
        };

        const sc = SCENARIOS[scenario];
        if (!sc) { container.innerHTML = ''; return; }

        let cur = 0;
        const uid = 'dt_' + Math.random().toString(36).slice(2,8);

        function render() {
            const s = sc.steps[cur];
            const tot = sc.steps.length;
            const prevTxt = isDE ? '← Zurück' : '← Back';
            const nextTxt = cur === tot-1 ? (isDE ? '✓ Fertig' : '✓ Done') : (isDE ? 'Weiter →' : 'Next →');

            container.innerHTML = `<div class="doc-tut-wrap">
  <div class="doc-tut-hdr">
    <div class="doc-tut-hdr-title">
      <span style="font-size:14px;">🎬</span>
      <span>${sc.title}</span>
    </div>
    <span class="doc-tut-hdr-count">${isDE?'Schritt':'Step'} ${cur+1} ${isDE?'von':'of'} ${tot}</span>
  </div>
  <div class="doc-tut-frame" id="${uid}_frame">${s.r()}</div>
  <div class="doc-tut-ctrl">
    <button class="doc-tut-btn" id="${uid}_prev" ${cur===0?'disabled':''} onclick="window['${uid}_nav'](-1)">${prevTxt}</button>
    <div class="doc-tut-dots">
      ${sc.steps.map((_,i)=>`<div class="doc-tut-dot${i===cur?' on':''}" onclick="window['${uid}_go'](${i})"></div>`).join('')}
    </div>
    <button class="doc-tut-btn primary" id="${uid}_next" onclick="window['${uid}_nav'](1)">${nextTxt}</button>
  </div>
  <div class="doc-tut-info">
    <div class="doc-tut-ttl">${s.t}</div>
    <div class="doc-tut-dsc">${s.d}</div>
  </div>
</div>`;

            window[`${uid}_nav`] = (d) => { const n = cur+d; if(n>=0 && n<tot){cur=n;render();} };
            window[`${uid}_go`]  = (i) => { cur=i; render(); };
        }

        render();
    },
};
