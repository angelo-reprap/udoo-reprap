"""
services/assembly_preview.py
=============================
DocPreview — HTML-Vorschau + Editor-Synchronisation.
NEU: content_type='html' Blöcke direkt durchreichen,
     image_refs zu /static/ URLs auflösen,
     TABLE mit columns + extra_rows,
     FOOTER/FIELD korrekt rendern.
"""
import json
import logging
import re

from .variable_engine  import VariableEngine
from .layout_constants import (
    CM_TO_PX, FONT_NAME, CHARS_PER_LINE, LINE_HEIGHT_MM,
    FOOTER_RESERVE_MM, COLOR_BRAND, COLOR_TEXT, COLOR_GRAY,
    COLOR_WHITE, COLOR_ALT_ROW, COLOR_SEPARATOR,
    A4_WIDTH_CM, A4_HEIGHT_CM,
    MARGIN_TOP_CM, MARGIN_BOTTOM_CM, MARGIN_LEFT_CM, MARGIN_RIGHT_CM,
    BLOCK_HEIGHT_FIXED, FOOTER_BLOCK_IDENTIFIER,
)

log = logging.getLogger('abpe_doc_studio.preview')


class DocPreview:

    def __init__(self):
        self.variable_engine = VariableEngine()
        self._footer_cache   = None
        self._image_refs     = {}

    # ── Öffentliche API ────────────────────────────────────────────────────

    def preview_html(self, template, variables=None):
        from apps.abpe_doc_studio.models import DocTemplate

        if isinstance(template, str):
            template = DocTemplate.objects.filter(
                identifier=template
            ).select_related('layout', 'style_kit').prefetch_related(
                'template_blocks__block'
            ).first()

        if not template:
            return '<div class="ds-doc-hint text-danger">Template nicht gefunden</div>'

        all_vars = variables or {}
        lay      = template.layout

        if lay and lay.image_refs:
            self._image_refs = lay.image_refs
        else:
            self._image_refs = {}

        if lay:
            page_h_mm   = float(lay.page_height_cm)  * 10
            margin_t_mm = float(lay.margin_top_cm)    * 10
            margin_b_mm = float(lay.margin_bottom_cm) * 10
            lay_data = {
                'w': float(lay.page_width_cm),
                'h': float(lay.page_height_cm),
                't': float(lay.margin_top_cm),
                'b': float(lay.margin_bottom_cm),
                'l': float(lay.margin_left_cm),
                'r': float(lay.margin_right_cm),
            }
        else:
            page_h_mm   = A4_HEIGHT_CM    * 10
            margin_t_mm = MARGIN_TOP_CM   * 10
            margin_b_mm = MARGIN_BOTTOM_CM * 10
            lay_data = {
                'w': A4_WIDTH_CM,  'h': A4_HEIGHT_CM,
                't': MARGIN_TOP_CM, 'b': MARGIN_BOTTOM_CM,
                'l': MARGIN_LEFT_CM,'r': MARGIN_RIGHT_CM,
            }

        lay_json  = json.dumps(lay_data).replace('"', '&quot;')
        max_h_mm  = page_h_mm - margin_t_mm - margin_b_mm - FOOTER_RESERVE_MM
        footer_html = self._get_footer_html(template, all_vars)

        blocks   = template.template_blocks.filter(slot='body').order_by('order')
        parts    = ['<div class="ds-doc-preview-wrap" data-layout="' + lay_json + '">']
        cur_mm   = 0.0
        page_num = 1

        parts.append('<div class="ds-preview-page" data-page="1">')

        for tb in blocks:
            if tb.conditional:
                if not self.variable_engine.check_condition(tb.conditional, all_vars):
                    continue

            if tb.page_break_before and cur_mm > 0:
                parts.append(footer_html)
                parts.append('</div>')
                page_num += 1
                cur_mm = 0.0
                parts.append('<div class="ds-preview-page" data-page="' + str(page_num) + '">')

            block_mm = self._estimate_height_mm(tb)

            if cur_mm + block_mm > max_h_mm and cur_mm > 20.0:
                parts.append(footer_html)
                parts.append('</div>')
                page_num += 1
                cur_mm = 0.0
                parts.append('<div class="ds-preview-page" data-page="' + str(page_num) + '">')

            parts.append(self._render_block_html(tb, all_vars, tb.pk))
            cur_mm += block_mm

        parts.append(footer_html)
        parts.append('</div>')
        parts.append('</div>')

        return '\n'.join(parts)

    # ── Footer ─────────────────────────────────────────────────────────────

    def _get_footer_html(self, template, variables):
        if self._footer_cache is not None:
            return self._footer_cache

        footer_blocks = template.template_blocks.filter(slot='footer').order_by('order')
        parts = []

        for tb in footer_blocks:
            block   = tb.block
            content = self.variable_engine.render_text(
                tb.content_override or block.content or '', variables
            )
            if block.content_type == 'html':
                parts.append(self._resolve_images(content))
            else:
                parts.append(self._html_footer_block(content))

        if parts:
            result = '<div class="ds-page-footer">' + ''.join(parts) + '</div>'
        else:
            result = self._footer_html_from_db(variables)

        self._footer_cache = result
        return result

    # ── Bild-URLs auflösen ─────────────────────────────────────────────────

    def _resolve_images(self, html_content):
        if not html_content:
            return html_content

        def replace_src(match):
            src = match.group(1)
            if src.startswith('/') or src.startswith('http'):
                return match.group(0)
            if src in self._image_refs:
                file_path = self._image_refs[src]
                url = self._path_to_url(file_path)
                return 'src="' + url + '"'
            return 'src="/static/abpe_ui/img/logo_abcona.png"'

        return re.sub(r'src="([^"]+)"', replace_src, html_content)

    def _path_to_url(self, file_path):
        import os, base64
        from django.conf import settings
        if os.path.isabs(file_path):
            abs_path = file_path
        else:
            abs_path = os.path.join(settings.BASE_DIR, file_path)
        if 'static/abpe_ui/' in file_path:
            idx = file_path.find('static/abpe_ui/')
            return '/' + file_path[idx:]
        if os.path.exists(abs_path):
            try:
                with open(abs_path, 'rb') as img_f:
                    data = base64.b64encode(img_f.read()).decode('utf-8')
                ext = os.path.splitext(abs_path)[1].lower().lstrip('.')
                mime = 'image/png' if ext == 'png' else 'image/jpeg'
                return 'data:' + mime + ';base64,' + data
            except Exception as e:
                log.warning('Base64 Fehler: ' + str(e))
        return '/static/abpe_ui/img/logo_abcona.png' 

    # ── Höhen-Schätzung ────────────────────────────────────────────────────

    def _estimate_height_mm(self, tb):
        bt      = tb.block.block_type
        content = tb.content_override or tb.block.content or ''

        if bt in BLOCK_HEIGHT_FIXED:
            return BLOCK_HEIGHT_FIXED[bt]

        if bt == 'TABLE':
            cols = tb.block.columns or []
            return max(20.0, len(cols) * 6.0 + 15.0)

        if bt in ('PARAGRAPH', 'FOOTER', 'FIELD'):
            text  = re.sub(r'<[^>]+>', '', content)
            chars = len(text)
            lines = max(1.0, chars / (CHARS_PER_LINE + 3.0))
            return lines * LINE_HEIGHT_MM + 5.0

        if bt == 'PARTY_BLOCK':
            lines = len([l for l in content.split('\n') if l.strip()])
            return max(16.0, lines * 5.5 + 4.0)

        if bt == 'CLAUSE':
            lines_total = 0.0
            for line in content.split('\n'):
                chars = len(line.strip())
                lines_total += 0.4 if chars == 0 else max(1.0, chars / CHARS_PER_LINE)
            return max(14.0, lines_total * LINE_HEIGHT_MM + 10.0)

        chars = len(re.sub(r'<[^>]+>', '', content))
        return max(8.0, chars / 65.0 * LINE_HEIGHT_MM + 6.0)

    # ── Block → HTML ───────────────────────────────────────────────────────

    def _render_block_html(self, tb, variables, tb_pk=None):
        block   = tb.block
        content = self.variable_engine.render_text(
            tb.content_override or block.content or '', variables
        )
        bt   = block.block_type
        pid  = tb_pk or 0
        ord_ = getattr(tb, 'order', 0)

        def wrap(inner):
            if not pid:
                return inner or ''
            return (
                '<div class="ds-preview-block"'
                ' data-tb-id="' + str(pid) + '"'
                ' data-block-type="' + bt + '"'
                ' data-order="' + str(ord_) + '">'
                + (inner or '') +
                '</div>'
            )

        # ── HTML content_type → direkt durchreichen ────────────────────
        if block.content_type == 'html':
            if bt == 'TABLE':
                return wrap(self._render_html_table(block, variables))
            if bt == 'FOOTER':
                return ''   # Footer nur im footer-Slot
            if bt == 'FIELD':
                return wrap(self._render_field_block(block, variables))
            resolved = self._resolve_images(content)
            return wrap('<div class="ds-html-block">' + resolved + '</div>')

        # ── Alte Block-Typen ───────────────────────────────────────────
        if bt == 'LOGO':
            return wrap(self._html_logo(variables))

        if bt == 'PAGE_BREAK':
            return wrap('<hr style="border:2px dashed #' + COLOR_SEPARATOR + ';margin:16px 0">')

        if bt == 'SEPARATOR':
            return wrap('<hr style="border:0.5px solid #' + COLOR_SEPARATOR + ';margin:6px 0">')

        if bt == 'FOOTER':
            return wrap(self._html_footer_block(content))

        if bt == 'DOC_TITLE':
            return wrap('<h1 style="font-size:20px;color:#' + COLOR_BRAND + ';margin:0 0 8px;">' + content + '</h1>')

        if bt == 'SECTION_HEAD':
            return wrap(
                '<h2 style="font-size:13px;color:#' + COLOR_BRAND + ';'
                'border-bottom:2px solid #' + COLOR_BRAND + ';'
                'padding-bottom:3px;margin:8px 0 3px;">' + content + '</h2>'
            )

        if bt == 'PARAGRAPH':
            paras = ''.join(
                '<p style="text-align:justify;margin:3px 0;font-size:10px;">' + l + '</p>'
                for l in content.split('\n') if l.strip()
            )
            return wrap(paras)

        if bt == 'CLAUSE':
            lines = content.split('\n')
            hdr   = lines[0] if lines else ''
            body  = ''.join(
                '<p style="text-align:justify;margin:3px 0;font-size:10px;">' + l + '</p>'
                for l in lines[1:] if l.strip()
            )
            inner = (
                '<div style="font-size:12px;font-weight:700;color:#' + COLOR_BRAND + ';'
                'border-bottom:1px solid #' + COLOR_BRAND + ';'
                'padding-bottom:2px;margin-bottom:3px;">' + hdr + '</div>' + body
            )
            return wrap(inner)

        if bt == 'PARTY_BLOCK':
            parts = ''.join(
                '<div style="font-size:9px;font-weight:600;color:#' + COLOR_TEXT + ';'
                'margin-left:16px;line-height:1.8;">' + l + '</div>'
                for l in content.split('\n') if l.strip()
            )
            return wrap(parts)

        if bt == 'LABEL_VALUE':
            lv = content.split('|', 1)
            if len(lv) == 2:
                inner = (
                    '<div style="display:flex;gap:8px;margin:3px 0;font-size:9px;">'
                    '<span style="font-weight:700;color:#' + COLOR_BRAND + ';min-width:140px;">' + lv[0] + '</span>'
                    '<span>' + lv[1] + '</span></div>'
                )
            else:
                inner = '<p style="margin:3px 0;font-size:9px;">' + content + '</p>'
            return wrap(inner)

        if bt == 'SIGNATURE':
            return wrap(self._html_signature(variables))

        if bt == 'INV_HEADER':
            return wrap(self._html_inv_header(variables))

        if bt == 'INV_META':
            inner = (
                '<div style="font-size:11px;font-weight:700;color:#' + COLOR_BRAND + ';'
                'border-bottom:2px solid #' + COLOR_BRAND + ';padding-bottom:3px;margin-bottom:4px;">'
                'Rg.-Nr.: ' + variables.get('rg_nummer', '') + '</div>'
                '<div style="font-size:10px;font-weight:700;color:#' + COLOR_BRAND + ';">'
                + variables.get('rg_datum', '') + '</div>'
            )
            return wrap(inner)

        if bt == 'INV_SUBJECT':
            betreff = content or variables.get('betreff', '')
            return wrap(
                '<div style="font-size:10px;font-weight:700;color:#' + COLOR_BRAND + ';margin:4px 0;">'
                + betreff + '</div>'
            )

        if bt in ('TIME_TABLE', 'AP_TABLE'):
            return wrap(self._html_table_old(block, variables, bt))

        if bt == 'TOTAL_BLOCK':
            return wrap(self._html_total(variables))

        if bt == 'CLOSING':
            return wrap(self._html_closing(variables))

        if content:
            return wrap('<p style="margin:3px 0;font-size:10px;">' + content + '</p>')
        return wrap('')

    # ── HTML TABLE Block ───────────────────────────────────────────────────

    def _render_html_table(self, block, variables):
        cb      = COLOR_BRAND
        columns = block.columns or []
        ev      = block.expected_variables or []
        list_key = ev[0].get('name', 'positionen') if ev else 'positionen'

        if not columns:
            return '<div style="background:#f5f5f5;padding:8px;color:#888;font-size:9px;">[Tabelle — keine Spalten]</div>'

        total_pct = sum(c.get('width_pct', 20) for c in columns) or 100

        # Header
        header_cells = []
        for c in columns:
            w     = str(round(c.get('width_pct', 20) / total_pct * 100, 1))
            align = 'right' if c.get('align') == 'right' else 'left'
            header_cells.append(
                '<th style="background:#' + cb + ';color:white;font-size:8px;'
                'padding:4px 6px;font-weight:600;width:' + w + '%;text-align:' + align + ';">'
                + c.get('label', '') + '</th>'
            )
        header = '<thead><tr>' + ''.join(header_cells) + '</tr></thead>'

        # Daten-Zeilen
        rows = self.variable_engine.expand_table_rows(columns, list_key, variables)
        body_rows = []
        if rows:
            for ri, row in enumerate(rows):
                bg    = COLOR_ALT_ROW if ri % 2 == 0 else COLOR_WHITE
                cells = []
                for ci, val in enumerate(row):
                    align = 'right' if ci < len(columns) and columns[ci].get('align') == 'right' else 'left'
                    cells.append(
                        '<td style="font-size:8px;padding:3px 6px;background:#' + bg + ';text-align:' + align + ';">'
                        + str(val) + '</td>'
                    )
                body_rows.append('<tr>' + ''.join(cells) + '</tr>')
        else:
            n = str(len(columns))
            body_rows.append(
                '<tr><td colspan="' + n + '" style="font-size:8px;padding:8px;'
                'color:#888;text-align:center;font-style:italic;">[Keine Positionen]</td></tr>'
            )

        # Summen-Zeilen
        summe  = variables.get('summe_netto', '')
        mwst_s = variables.get('mwst_satz', '19')
        mwst_e = variables.get('mwst_euro', '')
        gesamt = variables.get('gesamtbetrag', '')
        n_cols = len(columns)
        span   = str(max(1, n_cols - 2))

        if summe or gesamt:
            def sum_row(label, value, bold=False, border_top=False, border_bottom=False):
                fw  = '700' if bold else '400'
                bts = 'border-top:1px solid #163258;' if border_top else ''
                bbs = 'border-bottom:2px double #163258;' if border_bottom else ''
                return (
                    '<tr>'
                    '<td colspan="' + span + '" style="font-size:8px;padding:2px 0;"></td>'
                    '<td style="font-size:8px;padding:3px 6px;font-weight:' + fw + ';' + bts + '">'
                    + label + '</td>'
                    '<td style="font-size:8px;padding:3px 6px;font-weight:' + fw + ';'
                    'text-align:right;' + bts + bbs + '">' + value + '</td>'
                    '</tr>'
                )
            body_rows.append(sum_row('Summe netto:', summe))
            body_rows.append(sum_row('zzgl. MwSt. ' + mwst_s + ' %:', mwst_e))
            body_rows.append(sum_row('Gesamtbetrag:', gesamt, bold=True, border_top=True, border_bottom=True))

        return (
            '<table style="width:100%;border-collapse:collapse;margin:4px 0;">'
            + header
            + '<tbody>' + ''.join(body_rows) + '</tbody>'
            + '</table>'
        )

    # ── FIELD Block ────────────────────────────────────────────────────────

    def _render_field_block(self, block, variables):
        content = block.content or ''
        content = content.replace('{PAGE}', '1').replace('{NUMPAGES}', '?')
        content = self.variable_engine.render_text(content, variables)
        return '<div style="font-size:8px;color:#555;text-align:right;">' + content + '</div>'

    # ── Alte Helfer ────────────────────────────────────────────────────────

    def _footer_html_from_db(self, variables=None):
        if self._footer_cache is not None:
            return self._footer_cache

        cols = []
        try:
            from apps.abpe_doc_studio.models import ContentBlock
            block = ContentBlock.objects.filter(
                identifier=FOOTER_BLOCK_IDENTIFIER, is_active=True
            ).first()
            if block and block.content:
                rendered = self.variable_engine.render_text(block.content, variables or {})
                for line in rendered.strip().split('\n'):
                    parts = [p.strip() for p in line.split('|') if p.strip()]
                    if parts:
                        cols.append(
                            '<div><b style="color:#' + COLOR_TEXT + ';">' + parts[0] + '</b>'
                            '<br>' + '<br>'.join(parts[1:]) + '</div>'
                        )
        except Exception as e:
            log.warning('Footer DB Fehler: ' + str(e))

        if not cols:
            self._footer_cache = ''
            return ''

        grid_cols = ' '.join(['1fr'] * len(cols))
        html = (
            '<div class="ds-page-footer">'
            '<div style="display:grid;grid-template-columns:' + grid_cols + ';'
            'font-size:6px;color:#555;'
            'border-top:1px solid #' + COLOR_BRAND + ';padding-top:4px;">'
            + ''.join(cols) +
            '</div></div>'
        )
        self._footer_cache = html
        return html

    def _html_footer_block(self, content):
        cols = []
        for line in content.strip().split('\n'):
            parts = [p.strip() for p in line.split('|') if p.strip()]
            if parts:
                cols.append(
                    '<div><b style="color:#' + COLOR_TEXT + ';">' + parts[0] + '</b>'
                    '<br>' + '<br>'.join(parts[1:]) + '</div>'
                )
        if not cols:
            return ''
        grid_cols = ' '.join(['1fr'] * len(cols))
        return (
            '<div style="display:grid;grid-template-columns:' + grid_cols + ';'
            'font-size:6.5px;color:#555;'
            'border-top:1px solid #' + COLOR_BRAND + ';padding-top:5px;margin-top:8px;">'
            + ''.join(cols) + '</div>'
        )

    def _html_logo(self, variables):
        cb = COLOR_BRAND
        v  = variables
        return (
            '<div style="display:flex;justify-content:space-between;'
            'align-items:flex-start;margin-bottom:16px;">'
            '<div style="font-size:7px;color:#' + cb + ';">'
            + v.get('ag_firma', 'abcona e.K.') + ' &middot; '
            + v.get('ag_strasse', 'Bornhohl 26') + ' &nbsp; '
            + v.get('ag_plz_ort', '61449 Steinbach/Ts.') +
            '</div>'
            '<img src="/static/abpe_ui/img/logo_abcona.png" style="height:40px;width:auto;">'
            '</div>'
        )

    def _html_signature(self, variables):
        datum  = variables.get('datum_heute', '')
        ag_ort = variables.get('ag_ort', 'Steinbach')
        an_ort = variables.get('an_ort', '')
        return (
            '<div style="display:flex;justify-content:space-between;margin-top:24px;padding-top:6px;">'
            '<div style="font-size:8px;flex:1;">'
            '<div style="margin-bottom:40px;">' + ag_ort + ', den ' + datum + '</div>'
            '<b>Auftraggeber AG</b><br>'
            '<span style="color:#aaa;">Stempel/Unterschrift</span>'
            '</div>'
            '<div style="width:40px;"></div>'
            '<div style="font-size:8px;flex:1;">'
            '<div style="margin-bottom:40px;">' + an_ort + ', den ' + datum + '</div>'
            '<b>Auftragnehmer AN</b><br>'
            '<span style="color:#aaa;">Unterschrift</span>'
            '</div>'
            '</div>'
        )

    def _html_inv_header(self, variables):
        cb    = COLOR_BRAND
        ct    = COLOR_TEXT
        v     = variables
        firma = v.get('empfaenger_firma', '')
        addr  = v.get('empfaenger_adresse', '').replace('\n', '<br>')
        return (
            '<div style="display:flex;justify-content:space-between;margin-bottom:12px;">'
            '<div style="font-size:9px;flex:1;">'
            '<b style="color:#' + ct + ';">' + firma + '</b><br>' + addr +
            '</div>'
            '<div style="font-size:7px;color:#' + cb + ';text-align:right;line-height:1.8;">'
            '<b>' + v.get('ag_firma', 'abcona e.K.') + '</b><br>'
            'Tel: ' + v.get('ag_tel', '') + '<br>'
            'Fax: ' + v.get('ag_fax', '') +
            '</div></div>'
        )

    def _html_table_old(self, block, variables, bt):
        cb       = COLOR_BRAND
        columns  = block.columns or []
        list_key = 'positionen' if bt == 'TIME_TABLE' else 'arbeitspakete'
        rows     = self.variable_engine.expand_table_rows(columns, list_key, variables)

        if not columns:
            return '<div style="background:#f5f5f5;padding:8px;color:#888;font-size:9px;">[Tabelle]</div>'

        header_cells = []
        for c in columns:
            align = 'right' if c.get('align') == 'right' else 'left'
            header_cells.append(
                '<th style="background:#' + cb + ';color:white;font-size:8px;padding:3px 5px;text-align:' + align + ';">'
                + c.get('label', '') + '</th>'
            )

        body_rows = []
        if rows:
            for ri, row in enumerate(rows):
                bg    = COLOR_ALT_ROW if ri % 2 == 0 else COLOR_WHITE
                cells = []
                for ci, val in enumerate(row):
                    align = 'right' if ci < len(columns) and columns[ci].get('align') == 'right' else 'left'
                    cells.append(
                        '<td style="font-size:8px;padding:2px 5px;background:#' + bg + ';text-align:' + align + ';">'
                        + str(val) + '</td>'
                    )
                body_rows.append('<tr>' + ''.join(cells) + '</tr>')
        else:
            n = str(len(columns))
            body_rows.append(
                '<tr><td colspan="' + n + '" style="font-size:8px;padding:4px;color:#888;text-align:center;">[Keine Daten]</td></tr>'
            )

        return (
            '<table style="width:100%;border-collapse:collapse;margin:4px 0;">'
            '<tr>' + ''.join(header_cells) + '</tr>'
            + ''.join(body_rows) +
            '</table>'
        )

    def _html_total(self, variables):
        cb  = COLOR_BRAND
        ct  = COLOR_TEXT
        v   = variables
        rows_data = [
            ('Summe netto:',                              v.get('summe_netto', ''),  False),
            ('zzgl. MwSt. ' + v.get('mwst_satz','19') + ' %:', v.get('mwst_euro', ''),   False),
            ('Gesamtbetrag:',                             v.get('gesamtbetrag', ''), True),
        ]
        html = '<table style="width:100%;border-collapse:collapse;margin:4px 0;">'
        for label, value, bold in rows_data:
            fw = '700' if bold else '400'
            html += (
                '<tr><td style="width:65%;"></td>'
                '<td style="font-size:9px;font-weight:' + fw + ';padding:3px 5px;">' + label + '</td>'
                '<td style="font-size:9px;font-weight:' + fw + ';padding:3px 5px;text-align:right;">' + value + '</td>'
                '</tr>'
            )
        html += '</table>'
        return html

    def _html_closing(self, variables):
        ct = COLOR_TEXT
        v  = variables
        return (
            '<div style="font-size:9px;color:#' + ct + ';margin-top:12px;">Mit freundlichen Grüssen</div>'
            '<div style="font-size:9px;font-weight:700;color:#' + ct + ';text-align:right;margin:4px 0 32px;">'
            'Zahlungsziel: ' + v.get('zahlungsziel_text', '30 Tage netto') + '</div>'
            '<div style="font-size:9px;color:#' + ct + ';">'
            '<b>' + v.get('ag_firma', 'abcona e.K.') + '</b></div>'
        )

