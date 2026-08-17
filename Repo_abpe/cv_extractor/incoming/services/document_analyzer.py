"""
document_analyzer.py - Analysiert Dokument und ermittelt dynamische Werte
"""

from collections import Counter
from typing import Dict, Tuple


class DocumentAnalyzer:
    """Analysiert ein Dokument und ermittelt dynamische Werte (keine fixen Zahlen)"""
    
    def __init__(self, spans):
        self.spans = spans
        self.label_x = 71
        self.value_x = 212
        self.normal_gap = 14
        self.max_size = 18.0
        self.heading_threshold = 15.3
    
    def analyze(self) -> Dict:
        """Führt die vollständige Analyse durch"""
        if not self.spans:
            return self._get_defaults()
        
        # X-Positionen analysieren
        all_x = [s['x'] for s in self.spans]
        x_counter = Counter(all_x)
        most_common_x = [x for x, count in x_counter.most_common(4)]
        self.label_x = min(most_common_x) if most_common_x else 71
        self.value_x = max(most_common_x) if most_common_x else 212
        
        # Schriftgrößen analysieren
        all_sizes = [s['size'] for s in self.spans]
        size_counter = Counter(all_sizes)
        self.normal_size = size_counter.most_common(1)[0][0] if size_counter else 12
        self.max_size = max(all_sizes) if all_sizes else 18
        self.heading_threshold = self.max_size * 0.85
        
        # Y-Abstände analysieren
        y_gaps = []
        spans_sorted = sorted(self.spans, key=lambda s: (s['page'], s['y']))
        for i in range(1, len(spans_sorted)):
            if spans_sorted[i]['page'] == spans_sorted[i-1]['page']:
                gap = spans_sorted[i]['y'] - spans_sorted[i-1]['y']
                if 0 < gap < 100:
                    y_gaps.append(gap)
        
        if y_gaps:
            gap_counter = Counter(y_gaps)
            self.normal_gap = gap_counter.most_common(1)[0][0]
        
        return {
            'label_x': self.label_x,
            'value_x': self.value_x,
            'normal_size': self.normal_size,
            'max_size': self.max_size,
            'heading_threshold': self.heading_threshold,
            'normal_gap': self.normal_gap,
            'block_threshold': self.normal_gap * 2
        }
    
    def _get_defaults(self) -> Dict:
        return {
            'label_x': 71,
            'value_x': 212,
            'normal_size': 12,
            'max_size': 18,
            'heading_threshold': 15.3,
            'normal_gap': 14,
            'block_threshold': 28
        }
