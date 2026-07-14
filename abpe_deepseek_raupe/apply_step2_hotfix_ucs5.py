#!/usr/bin/env python3
"""Schritt 2 Hotfix + JS-Patch auf ucs5."""
from __future__ import annotations

import re
import sys
from pathlib import Path

BACKEND = Path('/opt/abpe/backend')


def patch_deepseek_api_pbx(pbx: Path) -> None:
    text = pbx.read_text(encoding='utf-8')
    if 'def suggest_with_key' in text:
        print('= suggest_with_key schon da')
        return
    snippet = Path(__file__).resolve().parent.joinpath(
        'patches/deepseek_api_pbx_suggest_with_key.py'
    ).read_text(encoding='utf-8')
    snippet = re.sub(r'^#.*\n', '', snippet, flags=re.MULTILINE)
    m = re.search(r'\n    def format_note\(', text)
    if not m:
        m = re.search(r'\n    def summarize\(', text)
    if not m:
        raise SystemExit('summarize/format_note nicht gefunden in deepseek_api_pbx.py')
    # nach summarize-Methode einfügen
    m2 = re.search(r'\n    def format_note\(', text[m.end():])
    insert_at = m.end() + m2.start() if m2 else m.end()
    # besser: nach summarize block
    m_sum = re.search(
        r'(    def summarize\(self, text: str.*?)(\n    def \w+\()',
        text,
        re.DOTALL,
    )
    if not m_sum:
        raise SystemExit('summarize-Block nicht parsebar')
    text = text[: m_sum.end(1)] + '\n\n' + snippet.strip() + '\n' + text[m_sum.start(2):]
    pbx.write_text(text, encoding='utf-8')
    print('OK deepseek_api_pbx suggest_with_key')


def patch_deepseek_raupe(svc: Path) -> None:
    text = svc.read_text(encoding='utf-8')
    if 'suggest_with_key' in text and '_chat(system' not in text:
        print('= deepseek_raupe suggest ok')
        return
    new_suggest = '''    def suggest(
        self,
        text: str,
        *,
        prompt_key: str = 'summarize',
        instruction: Optional[str] = None,
    ):
        from apps.abpe_crm.services.deepseek_api_pbx import deepseek_pbx
        if prompt_key == 'summarize':
            from apps.abpe_crm.services.deepseek_api_pbx import get_prompt_config
            instr = instruction or get_prompt_config('summarize').get('instruction_default') or 'Fasse kurz zusammen.'
            return deepseek_pbx.summarize(text, instr)
        if hasattr(deepseek_pbx, 'suggest_with_key'):
            return deepseek_pbx.suggest_with_key(text, prompt_key, instruction)
        return deepseek_pbx.summarize(text, instruction or 'Formuliere den Text um.')
'''
    text = re.sub(
        r'    def suggest\(.*?return deepseek_pbx\._chat\(system, user_prompt\)',
        new_suggest.rstrip(),
        text,
        count=1,
        flags=re.DOTALL,
    )
    svc.write_text(text, encoding='utf-8')
    print('OK deepseek_raupe.py')


def patch_mod_crm_pbx(js: Path) -> None:
    text = js.read_text(encoding='utf-8')
    if '_mmRaupeRequest' in text:
        print('= mod-crm-pbx Raupe JS schon gepatcht')
        return

    helpers = '''
    _mmRaupeVariables() {
        const st = this._mmComposeState || this._mmNotifyState || this._mmReminderState || {};
        const guest = st.guest || st.currentGuest || {};
        const meeting = st.meeting || {};
        return {
            name: guest.name || '',
            title: meeting.title || '',
            termin_datum: st.termin_datum || guest.termin_datum || '',
            termin_uhrzeit: st.termin_uhrzeit || guest.termin_uhrzeit || '',
            raum: meeting.room_extension || guest.raum || st.raum || '',
            einwahl_info: guest.einwahl_info || st.einwahl_info || '',
            teilnehmer_liste: st.teilnehmer_liste || '',
            teilnehmer_liste_html: st.teilnehmer_liste_html || '',
            sender_name: st.sender_name || guest.sender_name || '',
        };
    },
    _mmRaupeRequest(text, extra = {}) {
        const subjEl = this.$('pbx-mm-compose-subject')
            || this.$('pbx-mm-notify-subject')
            || this.$('pbx-mm-reminder-subject');
        return Object.assign({
            text: text || '',
            prompt_key: 'meetme_email',
            format: 'text',
            subject: subjEl ? (subjEl.value || '').trim() : '',
            variables: this._mmRaupeVariables(),
        }, extra);
    },
    _mmRaupeApply(bottomId, editorId) {
        const src = this.$(bottomId);
        const dst = this.$(editorId);
        const val = src ? (src.value || '').trim() : '';
        if (!val) {
            this.toast(this.t('pbx_sa_ds_err', 'DeepSeek konnte keinen Vorschlag liefern'));
            return;
        }
        if (dst) dst.value = val;
        this.toast(this.t('pbx_sa_applied', 'Vorschlag übernommen'));
    },
'''
    anchor = 'async _mmComposeDeepseekSuggest()'
    if anchor not in text:
        raise SystemExit('_mmComposeDeepseekSuggest nicht gefunden')
    text = text.replace(anchor, helpers + '\n    ' + anchor, 1)

    text = text.replace(
        "await this.post('/meetme/api/deepseek-suggest/', { text: current })",
        "await this.post('/meetme/api/deepseek-suggest/', this._mmRaupeRequest(current))",
    )

    apply_btn = (
        '<button class="pbx-act pbx-act-blue" onclick="PBX._mmRaupeApply(\'pbx-mm-compose-ds-bottom\',\'pbx-mm-compose-body\')">'
        '<i class="bi bi-check2-circle"></i> ${this.t(\'pbx_sa_apply\', \'Vorschlag übernehmen\')}</button>'
    )
    if 'pbx_sa_apply' not in text:
        text = text.replace(
            "onclick=\"PBX._mmComposeDeepseekSuggest()\"><i class=\"bi bi-arrow-clockwise\"></i> ${this.t('pbx_sa_suggest', 'Vorschlag generieren')}</button>",
            "onclick=\"PBX._mmComposeDeepseekSuggest()\"><i class=\"bi bi-arrow-clockwise\"></i> ${this.t('pbx_sa_suggest', 'Vorschlag generieren')}</button>\n                        " + apply_btn,
            1,
        )
        text = text.replace(
            "onclick=\"PBX._mmNotifyDeepseekSuggest()\"><i class=\"bi bi-arrow-clockwise\"></i> ${this.t('pbx_sa_suggest', 'Vorschlag generieren')}</button>",
            "onclick=\"PBX._mmNotifyDeepseekSuggest()\"><i class=\"bi bi-arrow-clockwise\"></i> ${this.t('pbx_sa_suggest', 'Vorschlag generieren')}</button>\n                        "
            "<button class=\"pbx-act pbx-act-blue\" onclick=\"PBX._mmRaupeApply('pbx-mm-notify-ds-bottom','pbx-mm-notify-body')\"><i class=\"bi bi-check2-circle\"></i> ${this.t('pbx_sa_apply', 'Vorschlag übernehmen')}</button>",
            1,
        )
        text = text.replace(
            "onclick=\"PBX._mmReminderDeepseekSuggest()\"><i class=\"bi bi-arrow-clockwise\"></i> ${this.t('pbx_sa_suggest', 'Vorschlag generieren')}</button>",
            "onclick=\"PBX._mmReminderDeepseekSuggest()\"><i class=\"bi bi-arrow-clockwise\"></i> ${this.t('pbx_sa_suggest', 'Vorschlag generieren')}</button>\n                        "
            "<button class=\"pbx-act pbx-act-blue\" onclick=\"PBX._mmRaupeApply('pbx-mm-reminder-ds-bottom','pbx-mm-reminder-body')\"><i class=\"bi bi-check2-circle\"></i> ${this.t('pbx_sa_apply', 'Vorschlag übernehmen')}</button>",
            1,
        )

    js.write_text(text, encoding='utf-8')
    print('OK mod-crm-pbx.js')


def main():
    root = BACKEND if BACKEND.exists() else Path.cwd()
    patch_deepseek_api_pbx(root / 'apps/abpe_crm/services/deepseek_api_pbx.py')
    patch_deepseek_raupe(root / 'apps/abpe_email_studio/services/deepseek_raupe.py')
    patch_mod_crm_pbx(root / 'apps/abpe_crm/static/abpe_crm/js/mod-crm-pbx.js')
    print('Fertig — collectstatic + Django restart')


if __name__ == '__main__':
    main()
