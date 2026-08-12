"""
Schnelltest für fl_doc_classifier.py
Aufruf: python3 apps/cv_extractor/services/fl_doc_classifier_test.py <datei>
"""
import sys
import os

# Django-Umgebung aufbauen
sys.path.insert(0, '/opt/abpe/backend')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'abpe_backend.settings')

import django
django.setup()

from pathlib import Path
from apps.cv_extractor.services.fl_doc_classifier import fl_doc_classifier

path = sys.argv[1] if len(sys.argv) > 1 else None
if not path:
    print("Usage: python3 fl_doc_classifier_test.py <datei.docx|datei.doc|datei.pdf>")
    sys.exit(1)

suffix = Path(path).suffix.lower()

if suffix in ('.docx', '.doc'):
    from apps.cv_extractor.services.master_word_extractor import master_word_extractor
    extract_result = master_word_extractor.extract(path)
    result = fl_doc_classifier.classify_from_result(extract_result)
elif suffix == '.pdf':
    from apps.cv_extractor.services.pdf_extractor import PDFExtractor
    pdf_result = PDFExtractor().extract(path)
    spans = [
        {
            'page': getattr(s, 'page', 1),
            'y':    getattr(s, 'y', 0),
            'x':    getattr(s, 'x', 0),
            'size': getattr(s, 'size', 12.0),
            'bold': getattr(s, 'bold', False),
            'text': s.text,
        }
        for s in (pdf_result.spans or []) if s.text
    ]
    result = fl_doc_classifier.classify_from_spans(
        spans, filename=Path(path).name
    )
else:
    print(f"Format nicht unterstützt: {suffix}")
    sys.exit(1)

print(f"\n{'='*60}")
print(f"Datei:      {result.filename}")
print(f"Typ:        {result.doc_type}")
print(f"Konfidenz:  {result.confidence:.2f}")
print(f"Skip:       {result.skip}")
print(f"Begründung: {result.reason}")
print(f"\nSignale ({len(result.signals)}):")
for s in result.signals[:20]:
    print(f"  • {s}")
print(f"{'='*60}")
