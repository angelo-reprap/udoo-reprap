#!/usr/bin/env python3
"""Offline-Proof: Zertifikat/Schulung-Daten werden nicht mehr verworfen."""
from __future__ import annotations

import re
import sys


def extract_cert_dates(block: str) -> list[dict]:
    """Spiegel der Fix-Logik in aid_regex_extractor._extract_zertifikate."""
    certs = []
    seen = set()
    for line in block.splitlines():
        line = re.sub(r'^[•\-\u2022\*]+\s*', '', line).strip()
        if not line or len(line) < 3:
            continue
        date_obtained = ''
        dm = re.match(r'^(\d{1,2}/\d{4})\s+(.*)$', line)
        if dm:
            mm, yy = dm.group(1).split('/')
            date_obtained = f'{int(mm):02d}/{yy}'
            line = dm.group(2).strip()
        lw = line.lower()
        if lw in seen:
            continue
        seen.add(lw)
        certs.append({'name': line, 'date_obtained': date_obtained})
    return certs


def main() -> int:
    block = """
01/2015 Introduction to JUNOS, JUNOS Routing Essentials
02/2006 updated MCSE 2003
06/2018 Blue Coat Certified Proxy Administrator (BCCPA)
CCNA Cisco Certified Network Associate
"""
    certs = extract_cert_dates(block)
    by_date = {c['date_obtained']: c['name'][:30] for c in certs if c['date_obtained']}
    assert by_date['01/2015'].startswith('Introduction to JUNOS'), by_date
    assert by_date['02/2006'].startswith('updated MCSE'), by_date
    assert by_date['06/2018'].startswith('Blue Coat'), by_date
    undated = [c for c in certs if not c['date_obtained']]
    assert any('CCNA' in c['name'] for c in undated), undated
    print('OK: cert dates preserved', certs)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
