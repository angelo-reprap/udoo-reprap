# In apps/abpe_crm/services/deepseek_api_pbx.py einfügen — direkt NACH def summarize(...)


    def suggest_with_key(
        self,
        text: str,
        prompt_key: str,
        instruction: Optional[str] = None,
    ) -> PbxAIResult:
        """DeepSeek mit beliebigem AiPrompt-Key (DB oder DEFAULT_PROMPTS)."""
        cfg = get_prompt_config(prompt_key)
        instr = (instruction or cfg.get('instruction_default') or '').strip() or 'Formuliere den Text um.'
        system = cfg.get('system') or ''
        user_tpl = cfg.get('user_template') or '[[INSTRUCTION]]\n\n[[TEXT]]'
        user_prompt = _fill(user_tpl, INSTRUCTION=instr, TEXT=text)
        t0 = time.time()
        if not self.is_available():
            return PbxAIResult(success=False, error='DeepSeek API-Key fehlt', processing_time=time.time() - t0)
        try:
            out = self._chat(system, user_prompt)
            if isinstance(out, PbxAIResult):
                out.processing_time = time.time() - t0
                return out
            if isinstance(out, tuple):
                if len(out) >= 2 and isinstance(out[0], bool):
                    return PbxAIResult(
                        success=out[0],
                        text=(out[1] or '') if out[0] else '',
                        error=out[2] if len(out) > 2 else None,
                        processing_time=time.time() - t0,
                    )
                content = (out[0] or '') if out else ''
                txt = str(content).strip()
                return PbxAIResult(success=bool(txt), text=txt, processing_time=time.time() - t0)
            if isinstance(out, str):
                txt = out.strip()
                return PbxAIResult(success=bool(txt), text=txt, processing_time=time.time() - t0)
            return PbxAIResult(success=False, error='DeepSeek: unbekanntes Antwortformat', processing_time=time.time() - t0)
        except Exception as exc:
            logger.exception('suggest_with_key(%s) fehlgeschlagen', prompt_key)
            return PbxAIResult(success=False, error=str(exc), processing_time=time.time() - t0)
