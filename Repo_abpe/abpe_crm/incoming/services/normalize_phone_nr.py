"""
apps/abpe_crm/services/normalize_phone_nr.py
Telefonnummer-Normalisierung für CrmPhoneNumber.phone_norm
Alle Formate → 0049XXXXXXXXX (nur Ziffern, deutsche Vorwahl)
"""
import re


def normalize_phone(nr):
    """
    Normalisiert eine Telefonnummer auf das Format 0049XXXXXXXXX.

    Beispiele:
      "0178 88867 22"        -> "00491788886722"
      "+49 178 88867 22"     -> "00491788886722"
      "0049 (0) 178 88867 22"-> "00491788886722"
      "0178/888-67 22"       -> "00491788886722"
      "49 178 88867 22"      -> "00491788886722"
    """
    if not nr or not nr.strip():
        return ''
    nr = nr.strip()
    nr = re.sub(r'[\(\[]\s*0\s*[\)\]]', '', nr)  # (0) entfernen
    nr = re.sub(r'^\+', '00', nr)                  # + -> 00
    nr = re.sub(r'\D', '', nr)                     # Nicht-Ziffern weg
    if nr.startswith('0049'):
        return nr
    if nr.startswith('00'):
        return nr
    if nr.startswith('49') and len(nr) > 10:
        return '00' + nr
    if nr.startswith('0'):
        return '0049' + nr[1:]
    return nr
