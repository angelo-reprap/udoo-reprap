#!/usr/bin/env python3
"""Schritt 2 Hotfix + JS-Patch auf ucs5."""
from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

BACKEND = Path('/opt/abpe/backend')
PKG = Path(__file__).resolve().parent


def patch_deepseek_api_pbx(pbx: Path) -> None:
    text = pbx.read_text(encoding='utf-8')
    if 'def suggest_with_key' in text:
        print('= suggest_with_key schon da')
        return
    snippet = PKG.joinpath('patches/deepseek_api_pbx_suggest_with_key.py').read_text(encoding='utf-8')
    snippet = re.sub(r'^#.*\n', '', snippet, flags=re.MULTILINE).strip()
    if not snippet.startswith('    def suggest_with_key'):
        raise SystemExit('suggest_with_key-Snippet hat falsche Einrückung (4 Leerzeichen erwartet)')
    m_sum = re.search(
        r'(    def summarize\(self, text: str.*?)(\n    def \w+\()',
        text,
        re.DOTALL,
    )
    if not m_sum:
        raise SystemExit('summarize-Block nicht parsebar in deepseek_api_pbx.py')
    text = text[: m_sum.end(1)] + '\n\n' + snippet + '\n' + text[m_sum.start(2):]
    pbx.write_text(text, encoding='utf-8')
    print('OK deepseek_api_pbx suggest_with_key')


def patch_deepseek_raupe(svc: Path) -> None:
    src = PKG / 'services' / 'deepseek_raupe.py'
    text = svc.read_text(encoding='utf-8')
    if '_coerce_pbx_result' in text and '_chat(system' not in text:
        print('= deepseek_raupe ok')
        return
    if '_chat(system' in text or 'return deepseek_pbx._chat' in text:
        shutil.copy2(src, svc)
        print('OK deepseek_raupe.py (ersetzt — _chat-Fallback entfernt)')
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
            return _coerce_pbx_result(deepseek_pbx.summarize(text, instr))
        if hasattr(deepseek_pbx, 'suggest_with_key'):
            return _coerce_pbx_result(deepseek_pbx.suggest_with_key(text, prompt_key, instruction))
        return _coerce_pbx_result(deepseek_pbx.summarize(text, instruction or 'Formuliere den Text um.'))
'''
    text = re.sub(
        r'    def suggest\(.*?return deepseek_pbx\._chat\(system, user_prompt\)',
        new_suggest.rstrip(),
        text,
        count=1,
        flags=re.DOTALL,
    )
    if '_coerce_pbx_result' not in text:
        shutil.copy2(src, svc)
        print('OK deepseek_raupe.py (ersetzt aus Paket)')
        return
    svc.write_text(text, encoding='utf-8')
    print('OK deepseek_raupe.py (suggest gepatcht)')


def patch_mod_crm_pbx(js: Path) -> None:
    text = js.read_text(encoding='utf-8')
    changed = False

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
    _mmRaupeApplyNotify() {
        const st = this._mmNotifyState || {};
        const editorId = st.mode === 'all' ? 'pbx-mm-notify-body-all' : 'pbx-mm-notify-body-ind';
        this._mmRaupeApply('pbx-mm-notify-ds-bottom', editorId);
    },
'''
    anchor = 'async _mmComposeDeepseekSuggest()'
    if '_mmRaupeRequest' not in text:
        if anchor not in text:
            raise SystemExit('_mmComposeDeepseekSuggest nicht gefunden')
        text = text.replace(anchor, helpers + '\n    ' + anchor, 1)
        changed = True
        print('OK mod-crm-pbx.js Raupe-Helper')

    if "await this.post('/meetme/api/deepseek-suggest/', { text: current })" in text:
        text = text.replace(
            "await this.post('/meetme/api/deepseek-suggest/', { text: current })",
            "await this.post('/meetme/api/deepseek-suggest/', this._mmRaupeRequest(current))",
        )
        changed = True

    apply_btn_compose = (
        '<button class="pbx-act pbx-act-blue" onclick="PBX._mmRaupeApply(\'pbx-mm-compose-ds-bottom\',\'pbx-mm-compose-body\')">'
        '<i class="bi bi-check2-circle"></i> ${this.t(\'pbx_sa_apply\', \'Vorschlag übernehmen\')}</button>'
    )
    apply_btn_notify = (
        '<button class="pbx-act pbx-act-blue" onclick="PBX._mmRaupeApplyNotify()">'
        '<i class="bi bi-check2-circle"></i> ${this.t(\'pbx_sa_apply\', \'Vorschlag übernehmen\')}</button>'
    )
    apply_btn_reminder = (
        '<button class="pbx-act pbx-act-blue" onclick="PBX._mmRaupeApply(\'pbx-mm-reminder-ds-bottom\',\'pbx-mm-reminder-body\')">'
        '<i class="bi bi-check2-circle"></i> ${this.t(\'pbx_sa_apply\', \'Vorschlag übernehmen\')}</button>'
    )

    if 'pbx_sa_apply' not in text:
        text = text.replace(
            "onclick=\"PBX._mmComposeDeepseekSuggest()\"><i class=\"bi bi-arrow-clockwise\"></i> ${this.t('pbx_sa_suggest', 'Vorschlag generieren')}</button>",
            "onclick=\"PBX._mmComposeDeepseekSuggest()\"><i class=\"bi bi-arrow-clockwise\"></i> ${this.t('pbx_sa_suggest', 'Vorschlag generieren')}</button>\n                        " + apply_btn_compose,
            1,
        )
        text = text.replace(
            "onclick=\"PBX._mmNotifyDeepseekSuggest()\"><i class=\"bi bi-arrow-clockwise\"></i> ${this.t('pbx_sa_suggest', 'Vorschlag generieren')}</button>",
            "onclick=\"PBX._mmNotifyDeepseekSuggest()\"><i class=\"bi bi-arrow-clockwise\"></i> ${this.t('pbx_sa_suggest', 'Vorschlag generieren')}</button>\n                        " + apply_btn_notify,
            1,
        )
        text = text.replace(
            "onclick=\"PBX._mmReminderDeepseekSuggest()\"><i class=\"bi bi-arrow-clockwise\"></i> ${this.t('pbx_sa_suggest', 'Vorschlag generieren')}</button>",
            "onclick=\"PBX._mmReminderDeepseekSuggest()\"><i class=\"bi bi-arrow-clockwise\"></i> ${this.t('pbx_sa_suggest', 'Vorschlag generieren')}</button>\n                        " + apply_btn_reminder,
            1,
        )
        changed = True

    # Alte falsche Notify-ID korrigieren
    if "PBX._mmRaupeApply('pbx-mm-notify-ds-bottom','pbx-mm-notify-body')" in text:
        text = text.replace(
            "PBX._mmRaupeApply('pbx-mm-notify-ds-bottom','pbx-mm-notify-body')",
            "PBX._mmRaupeApplyNotify()",
        )
        changed = True
        print('OK mod-crm-pbx.js Notify-Apply-ID korrigiert')

    if changed:
        js.write_text(text, encoding='utf-8')
    else:
        print('= mod-crm-pbx Raupe JS schon ok')


def main():
    root = BACKEND if BACKEND.exists() else Path.cwd()
    patch_deepseek_api_pbx(root / 'apps/abpe_crm/services/deepseek_api_pbx.py')
    patch_deepseek_raupe(root / 'apps/abpe_email_studio/services/deepseek_raupe.py')
    patch_mod_crm_pbx(root / 'apps/abpe_crm/static/abpe_crm/js/mod-crm-pbx.js')
    print('Fertig — collectstatic + supervisorctl restart abpe-django')


if __name__ == '__main__':
    main()
