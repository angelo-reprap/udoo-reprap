"""
bin/init_fixtures.py
====================
Liest alle JSON-Dateien aus generator/templates/*/
und schreibt PageLayout, StyleKit, ContentBlock und DocTemplate
in die PostgreSQL-Datenbank.

Regel:
  Jedes Template-Verzeichnis ist vollständig eigenständig.
  Dateinamen haben den Template-Prefix:
    rv/rv_template.json
    rv/rv_layout.json
    rv/rv_styles.json
    rv/rv_blocks.json

  Kein _shared. Kein Fallback auf andere Templates.
  Jede Vorlage besitzt ihre eigenen DB-Einträge.

Aufruf:
    cd /opt/abpe/backend
    python apps/abpe_doc_studio/bin/init_fixtures.py
    python apps/abpe_doc_studio/bin/init_fixtures.py --template rv
    python apps/abpe_doc_studio/bin/init_fixtures.py --reset
    python apps/abpe_doc_studio/bin/init_fixtures.py --check
"""
import os
import sys
import json
import argparse
import django


def setup_django():
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))
    )))
    sys.path.insert(0, BASE_DIR)
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'abpe_backend.settings')
    django.setup()

if __name__ == '__main__' and 'django' not in sys.modules:
    setup_django()


TEMPLATES_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'generator', 'templates'
)


def find_template_dirs() -> dict:
    """
    Findet alle Template-Verzeichnisse.
    Erkennt Verzeichnis als Template wenn {name}_template.json existiert.
    Ignoriert _shared und alle _ prefixed Verzeichnisse.
    """
    result = {}
    for d in sorted(os.listdir(TEMPLATES_DIR)):
        full_path = os.path.join(TEMPLATES_DIR, d)
        if not os.path.isdir(full_path):
            continue
        if d.startswith('_'):
            continue
        # Prüfe ob {name}_template.json existiert
        tpl_file = os.path.join(full_path, f'{d}_template.json')
        if os.path.exists(tpl_file):
            result[d] = full_path
        else:
            # Fallback: altes Format template.json noch vorhanden
            old_tpl = os.path.join(full_path, 'template.json')
            if os.path.exists(old_tpl):
                print(f'  ⚠  {d}: noch altes Format (template.json) — überspringe')
    return result


def load_json(path: str) -> dict | list:
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def backup_json(path: str) -> None:
    """Sichert JSON-Datei als .bak vor dem Überschreiben."""
    if os.path.exists(path):
        bak = path + '.bak'
        import shutil
        shutil.copy2(path, bak)


def init_layout(layout_data: dict) -> object:
    """PageLayout anlegen oder aktualisieren."""
    from apps.abpe_doc_studio.models import PageLayout
    layout, created = PageLayout.objects.update_or_create(
        identifier=layout_data['identifier'],
        defaults={
            'name':                       layout_data.get('name', ''),
            'page_width_cm':              layout_data.get('page_width_cm', 21.0),
            'page_height_cm':             layout_data.get('page_height_cm', 29.7),
            'margin_left_cm':             layout_data.get('margin_left_cm', 3.0),
            'margin_right_cm':            layout_data.get('margin_right_cm', 3.0),
            'margin_top_cm':              layout_data.get('margin_top_cm', 4.2),
            'margin_bottom_cm':           layout_data.get('margin_bottom_cm', 5.2),
            'header_distance_cm':         layout_data.get('header_distance_cm', 1.5),
            'footer_distance_cm':         layout_data.get('footer_distance_cm', 1.5),
            'columns':                    layout_data.get('columns', 1),
            'column_widths_cm':           layout_data.get('column_widths_cm', []),
            'show_page_numbers':          layout_data.get('show_page_numbers', True),
            'page_number_format':         layout_data.get('page_number_format', 'Seite {page} von {total}'),
            'page_number_position':       layout_data.get('page_number_position', 'top_right'),
            'slot_order':                 layout_data.get('slot_order', []),
            'is_active':                  layout_data.get('is_active', True),
            'table_alt_row_color':        layout_data.get('table_alt_row_color', 'F8FAFC'),
            'table_white_row_color':      layout_data.get('table_white_row_color', 'FFFFFF'),
            'normal_font_size_pt':        layout_data.get('normal_font_size_pt', 10.0),
            'layout_refs':                layout_data.get('layout_refs', {}),
            'image_refs':                 layout_data.get('image_refs', {}),
            'orientation':                layout_data.get('orientation', 'portrait'),
        }
    )
    action = 'angelegt' if created else 'aktualisiert'
    print(f'  PageLayout [{layout.identifier}] {action}')
    return layout


def init_style_kit(styles_data: dict) -> object:
    """StyleKit + StyleDefinitions anlegen oder aktualisieren."""
    from apps.abpe_doc_studio.models import StyleKit, StyleDefinition

    kit, created = StyleKit.objects.update_or_create(
        identifier=styles_data['identifier'],
        defaults={
            'name':       styles_data.get('name', ''),
            'is_default': styles_data.get('is_default', False),
            'is_active':  True,
        }
    )
    action = 'angelegt' if created else 'aktualisiert'
    print(f'  StyleKit [{kit.identifier}] {action}')

    for sdef in styles_data.get('definitions', []):
        StyleDefinition.objects.update_or_create(
            style_kit=kit,
            style_key=sdef['style_key'],
            defaults={
                'style_type':            sdef.get('style_type', 'TEXT'),
                'name':                  sdef.get('name', ''),
                'font_family':           sdef.get('font_family', 'Arial'),
                'font_size_pt':          sdef.get('font_size_pt', 10.0),
                'bold':                  sdef.get('bold', False),
                'italic':                sdef.get('italic', False),
                'underline':             sdef.get('underline', False),
                'color_hex':             sdef.get('color_hex', '1A1A1A'),
                'alignment':             sdef.get('alignment', 'left'),
                'space_before_pt':       sdef.get('space_before_pt', 0.0),
                'space_after_pt':        sdef.get('space_after_pt', 6.0),
                'line_spacing':          sdef.get('line_spacing', 1.15),
                'indent_left_cm':        sdef.get('indent_left_cm', 0.0),
                'border_bottom':         sdef.get('border_bottom', False),
                'border_bottom_color':   sdef.get('border_bottom_color', '163258'),
                'border_bottom_pt':      sdef.get('border_bottom_pt', 0.5),
                'border_bottom_style':   sdef.get('border_bottom_style', 'single'),
                'table_header_bg_hex':   sdef.get('table_header_bg_hex', '163258'),
                'table_header_text_hex': sdef.get('table_header_text_hex', 'FFFFFF'),
                'table_row_alt_bg_hex':  sdef.get('table_row_alt_bg_hex', 'F8FAFC'),
                'table_border_color_hex':sdef.get('table_border_color_hex', 'E5E7EB'),
                'table_border_pt':       sdef.get('table_border_pt', 0.5),
                'bg_color_hex':          sdef.get('bg_color_hex', ''),
            }
        )
    print(f'    {len(styles_data.get("definitions", []))} Style-Definitionen sync.')
    return kit


def init_blocks(blocks_data: list, style_kit) -> dict:
    """ContentBlocks anlegen oder aktualisieren."""
    from apps.abpe_doc_studio.models import ContentBlock

    result = {}
    for bdef in blocks_data:
        block, created = ContentBlock.objects.update_or_create(
            identifier=bdef['identifier'],
            defaults={
                'name':               bdef.get('name', ''),
                'block_type':         bdef.get('block_type', 'PARAGRAPH'),
                'style_kit':          style_kit,
                'style_key':          bdef.get('style_key', ''),
                'content':            bdef.get('content', ''),
                'columns':            bdef.get('columns', []),
                'expected_variables': bdef.get('expected_variables', []),
                'repeatable':         bdef.get('repeatable', False),
                'conditional':        bdef.get('conditional', ''),
                'is_active':          bdef.get('is_active', True),
                'row_styles':         bdef.get('row_styles', []),
                'col_styles':         bdef.get('col_styles', []),
                'col_alignments':     bdef.get('col_alignments', []),
                'row_border_bottom':  bdef.get('row_border_bottom', []),
                'row_borders':        bdef.get('row_borders', {}),
                'row_bg':             bdef.get('row_bg', {}),
                'col_borders':        bdef.get('col_borders', {}),
                'layout_ref':         bdef.get('layout_ref', ''),
                'image_ref':          bdef.get('image_ref', ''),
                'field_type':         bdef.get('field_type', ''),
                'control_title':      bdef.get('control_title', ''),
                'control_id':         bdef.get('control_id', ''),
                'url':                bdef.get('url', ''),
                'bookmark_name':      bdef.get('bookmark_name', ''),
                'bookmark_id':        bdef.get('bookmark_id', ''),
            }
        )
        action = 'angelegt' if created else 'aktualisiert'
        print(f'  ContentBlock [{block.identifier}] {action}')
        result[block.identifier] = block

    return result


def init_template(tpl_data: dict, layout, style_kit, blocks: dict) -> object:
    """DocTemplate + DocTemplateBlocks anlegen oder aktualisieren."""
    from apps.abpe_doc_studio.models import DocTemplate, DocTemplateBlock, ContentBlock

    tpl, created = DocTemplate.objects.update_or_create(
        identifier=tpl_data['identifier'],
        defaults={
            'name':            tpl_data.get('name', ''),
            'description':     tpl_data.get('description', ''),
            'scope':           tpl_data.get('scope', 'general'),
            'engine':          tpl_data.get('engine', 'BOTH'),
            'status':          tpl_data.get('status', 'DRAFT'),
            'layout':          layout,
            'style_kit':       style_kit,
            'variables':       tpl_data.get('variables', []),
            'logo_block_id':   tpl_data.get('logo_block_id', ''),
            'footer_block_id': tpl_data.get('footer_block_id', ''),
            'header_block_id': tpl_data.get('header_block_id', ''),
            'template_dir':    tpl_data.get('template_dir', ''),
        }
    )
    action = 'angelegt' if created else 'aktualisiert'
    print(f'  DocTemplate [{tpl.identifier}] {action}')

    # Blöcke — löschen und neu anlegen
    DocTemplateBlock.objects.filter(template=tpl).delete()
    missing = []
    for bref in tpl_data.get('blocks', []):
        block_id = bref['block']
        block = blocks.get(block_id)
        if not block:
            block = ContentBlock.objects.filter(identifier=block_id).first()
        if not block:
            missing.append(block_id)
            print(f'    ⚠  Block [{block_id}] nicht gefunden — überspringe')
            continue

        DocTemplateBlock.objects.create(
            template          = tpl,
            block             = block,
            slot              = bref.get('slot', 'body'),
            order             = bref.get('order', 10),
            style_override    = bref.get('style_override', {}),
            content_override  = bref.get('content_override', ''),
            conditional       = bref.get('conditional', ''),
            page_break_before = bref.get('page_break_before', False),
            anchor_to_block   = bref.get('anchor_to_block', ''),
        )

    block_count = DocTemplateBlock.objects.filter(template=tpl).count()
    print(f'    {block_count} Blöcke zugewiesen', end='')
    if missing:
        print(f' — ⚠ {len(missing)} fehlend: {missing}')
    else:
        print()
    return tpl


def process_template_dir(name: str, path: str) -> None:
    """
    Verarbeitet ein Template-Verzeichnis.
    Erwartet: {name}_template.json, {name}_layout.json,
              {name}_styles.json, {name}_blocks.json
    """
    print(f'\n── {name.upper()} ──')

    layout_path = os.path.join(path, f'{name}_layout.json')
    styles_path = os.path.join(path, f'{name}_styles.json')
    blocks_path = os.path.join(path, f'{name}_blocks.json')
    tpl_path    = os.path.join(path, f'{name}_template.json')

    # Alle 4 Dateien müssen vorhanden sein
    errors = []
    for p, label in [
        (layout_path, f'{name}_layout.json'),
        (styles_path, f'{name}_styles.json'),
        (blocks_path, f'{name}_blocks.json'),
        (tpl_path,    f'{name}_template.json'),
    ]:
        if not os.path.exists(p):
            errors.append(label)

    if errors:
        print(f'  ✗ Fehlende Dateien: {errors}')
        print(f'  Template {name} wird übersprungen.')
        return

    layout    = init_layout(load_json(layout_path))
    style_kit = init_style_kit(load_json(styles_path))
    blocks    = init_blocks(load_json(blocks_path), style_kit)
    init_template(load_json(tpl_path), layout, style_kit, blocks)


def check_status() -> None:
    """Zeigt Status aller Templates in der DB."""
    from apps.abpe_doc_studio.models import (
        PageLayout, StyleKit, ContentBlock, DocTemplate, DocLog
    )
    print('\n═══ ABpE Doc Studio Status ═══\n')
    print(f'  PageLayouts:    {PageLayout.objects.count()}')
    print(f'  StyleKits:      {StyleKit.objects.count()}')
    print(f'  ContentBlocks:  {ContentBlock.objects.count()}')
    print(f'  DocTemplates:   {DocTemplate.objects.count()}')
    print(f'  DocLogs:        {DocLog.objects.count()}')
    print()

    print('  Verfügbare Template-Verzeichnisse:')
    dirs = find_template_dirs()
    for name in dirs:
        print(f'    ✓ {name}')

    print()
    print('  Templates in DB:')
    for tpl in DocTemplate.objects.all().order_by('scope', 'name'):
        bc = tpl.template_blocks.count()
        mark = '✓' if tpl.status == 'ACTIVE' else '○'
        print(f'    {mark} [{tpl.status}] {tpl.identifier:40s} → {bc} Blöcke  (StyleKit: {tpl.style_kit.identifier})')


def main():
    parser = argparse.ArgumentParser(
        description='ABpE Doc Studio — Fixture Import'
    )
    parser.add_argument('--template', '-t',
                        help='Nur dieses Template laden (Ordnername)')
    parser.add_argument('--reset', action='store_true',
                        help='Löscht alle bestehenden Daten vor dem Import')
    parser.add_argument('--check', action='store_true',
                        help='Nur Status anzeigen')
    args = parser.parse_args()

    if args.check:
        check_status()
        return

    if args.reset:
        from apps.abpe_doc_studio.models import (
            DocTemplate, DocTemplateBlock, ContentBlock,
            StyleKit, StyleDefinition, PageLayout
        )
        print('⚠  RESET: Lösche alle bestehenden Doc Studio Daten...')
        DocTemplateBlock.objects.all().delete()
        DocTemplate.objects.all().delete()
        ContentBlock.objects.all().delete()
        StyleDefinition.objects.all().delete()
        StyleKit.objects.all().delete()
        PageLayout.objects.all().delete()
        print('   Gelöscht.\n')

    print('\n═══ ABpE Doc Studio — Fixture Import ═══')

    all_dirs = find_template_dirs()

    if args.template:
        if args.template not in all_dirs:
            print(f'\n✗ Unbekanntes Template: {args.template}')
            print(f'  Verfügbar: {list(all_dirs.keys())}')
            sys.exit(1)
        dirs = {args.template: all_dirs[args.template]}
    else:
        dirs = all_dirs

    for name, path in dirs.items():
        process_template_dir(name, path)

    print('\n✅ Import abgeschlossen.\n')

    from apps.abpe_doc_studio.models import DocTemplate
    print('Vorlagen in DB:')
    for t in DocTemplate.objects.all().order_by('scope', 'name'):
        bc = t.template_blocks.count()
        print(f'  [{t.status}] {t.identifier:40s} → {bc} Blöcke')


if __name__ == '__main__':
    main()

