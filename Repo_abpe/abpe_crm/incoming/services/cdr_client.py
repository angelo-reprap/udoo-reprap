import mysql.connector
import logging
from datetime import datetime, timedelta
from django.conf import settings

logger = logging.getLogger(__name__)

CDR_DB = getattr(settings, 'CDR_DB', {
    'host': '172.20.3.120',
    'port': 3306,
    'user': 'asteriskuser',
    'password': '0f1f0f621c60dd949d58',
    'database': 'asteriskcdrdb',
    'connect_timeout': 5,
    'charset': 'utf8mb4',
})


def _get_conn():
    return mysql.connector.connect(**CDR_DB)


SORTABLE_FIELDS = {
    'calldate': 'calldate',
    'billsec':  'billsec',
}

SYSTEM_EXCLUDE_DST = ('*8', '*97', '*96', 's', '', 'STARTMEETME')
SYSTEM_EXCLUDE_PARK_PREFIX = '70'

def get_cdr_for_extension(extension, mode='all', days=30, limit=None,
                           sort_by='calldate', sort_dir='DESC', hide_system=False,
                           date_from=None, date_to=None):
    """
    Holt CDR-Einträge für eine Nebenstelle.

    mode:
        'all'       — alle Anrufe
        'incoming'  — eingehend (dst = extension)
        'outgoing'  — ausgehend (src = extension)
        'missed'    — verpasst (dst = extension, disposition != ANSWERED)
        'answered'  — angenommen

    sort_by:  'calldate' (Zeitpunkt) oder 'billsec' (Gespraechsdauer)
    sort_dir: 'ASC' oder 'DESC'
    hide_system: True -> Park-Slots (70x) und Konferenz-/System-Eintraege
                 (STARTMEETME, Feature-Codes) werden ausgeblendet

    Rückgabe: Liste von dicts mit allen relevanten Feldern.
    """
    base_conditions = []
    params = []
    if date_from or date_to:
        if date_from:
            base_conditions.append('calldate >= %s')
            params.append(f'{date_from} 00:00:00')
        if date_to:
            base_conditions.append('calldate <= %s')
            params.append(f'{date_to} 23:59:59')
    else:
        since = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d 00:00:00')
        base_conditions.append('calldate >= %s')
        params.append(since)

    if mode == 'all':
        base_conditions.append('(src = %s OR dst = %s)')
        params += [extension, extension]
    elif mode == 'incoming':
        base_conditions.append('dst = %s')
        params.append(extension)
    elif mode == 'outgoing':
        base_conditions.append('src = %s')
        params.append(extension)
    elif mode == 'missed':
        base_conditions.append('dst = %s')
        base_conditions.append("disposition IN ('NO ANSWER', 'BUSY', 'CONGESTION')")
        params.append(extension)
    elif mode == 'answered':
        base_conditions.append('(src = %s OR dst = %s)')
        base_conditions.append("disposition = 'ANSWERED'")
        params += [extension, extension]

    if hide_system:
        placeholders = ','.join(['%s'] * len(SYSTEM_EXCLUDE_DST))
        base_conditions.append(
            f"(dst NOT IN ({placeholders}) AND src NOT IN ({placeholders}))"
        )
        params += list(SYSTEM_EXCLUDE_DST) + list(SYSTEM_EXCLUDE_DST)
        base_conditions.append("dst NOT LIKE %s")
        params.append(SYSTEM_EXCLUDE_PARK_PREFIX + '%')

    order_col = SORTABLE_FIELDS.get(sort_by, 'calldate')
    order_dir = 'ASC' if str(sort_dir).upper() == 'ASC' else 'DESC'

    where = ' AND '.join(base_conditions)
    limit_clause = 'LIMIT %s' if limit else ''
    sql = f"""
        SELECT
            calldate,
            src,
            dst,
            clid,
            cnam,
            dst_cnam,
            disposition,
            billsec,
            duration,
            did,
            recordingfile,
            uniqueid,
            CASE
                WHEN src = %s THEN 'outgoing'
                ELSE 'incoming'
            END AS direction
        FROM cdr
        WHERE {where}
        ORDER BY {order_col} {order_dir}
        {limit_clause}
    """
    params = [extension] + params
    if limit:
        params = params + [limit]

    rows = []
    try:
        conn = _get_conn()
        cur = conn.cursor(dictionary=True)
        cur.execute(sql, params)
        rows = cur.fetchall()
        cur.close()
        conn.close()

        # datetime → string für JSON-Serialisierung
        for row in rows:
            if isinstance(row.get('calldate'), datetime):
                row['calldate'] = row['calldate'].strftime('%Y-%m-%d %H:%M:%S')
            row['billsec_fmt'] = _fmt_duration(row.get('billsec', 0))

    except Exception as e:
        logger.error(f'CDR get_cdr_for_extension Fehler: {e}')

    return rows


def get_stats_for_extension(extension):
    """Dashboard-Statistik für eine Nebenstelle."""
    stats = {
        'heute': {},
        'woche': {},
        'monat': {},
        'top_anrufer': [],
        'top_angerufen': [],
        'stunden': [],
    }
    try:
        conn = _get_conn()
        cur = conn.cursor(dictionary=True)

        # Heute
        cur.execute("""
            SELECT
                COUNT(*) as total,
                SUM(disposition='ANSWERED') as answered,
                SUM(disposition='NO ANSWER') as missed,
                SUM(src=%s) as outgoing,
                SUM(dst=%s) as incoming,
                COALESCE(SUM(CASE WHEN disposition='ANSWERED' THEN billsec END), 0) as talk_sec
            FROM cdr
            WHERE (src=%s OR dst=%s) AND DATE(calldate)=CURDATE()
        """, [extension, extension, extension, extension])
        stats['heute'] = cur.fetchone()

        # Diese Woche
        cur.execute("""
            SELECT
                COUNT(*) as total,
                SUM(disposition='ANSWERED') as answered,
                SUM(disposition='NO ANSWER') as missed,
                COALESCE(SUM(CASE WHEN disposition='ANSWERED' THEN billsec END), 0) as talk_sec
            FROM cdr
            WHERE (src=%s OR dst=%s) AND calldate >= DATE_SUB(NOW(), INTERVAL 7 DAY)
        """, [extension, extension])
        stats['woche'] = cur.fetchone()

        # Dieser Monat
        cur.execute("""
            SELECT
                COUNT(*) as total,
                SUM(disposition='ANSWERED') as answered,
                SUM(disposition='NO ANSWER') as missed,
                SUM(src=%s) as outgoing,
                SUM(dst=%s) as incoming,
                COALESCE(SUM(CASE WHEN disposition='ANSWERED' THEN billsec END), 0) as talk_sec
            FROM cdr
            WHERE (src=%s OR dst=%s) AND MONTH(calldate)=MONTH(CURDATE()) AND YEAR(calldate)=YEAR(CURDATE())
        """, [extension, extension, extension, extension])
        stats['monat'] = cur.fetchone()

        # Top 10 Anrufer (eingehend)
        cur.execute("""
            SELECT src as nummer, COUNT(*) as anzahl,
                   SUM(disposition='ANSWERED') as answered
            FROM cdr
            WHERE dst=%s AND src != 'anonymous' AND src != ''
            GROUP BY src ORDER BY anzahl DESC LIMIT 10
        """, [extension])
        stats['top_anrufer'] = cur.fetchall()

        # Top 10 Angerufene (ausgehend)
        cur.execute("""
            SELECT dst as nummer, COUNT(*) as anzahl,
                   SUM(billsec) as talk_sec
            FROM cdr
            WHERE src=%s AND dst NOT IN ('*8','*97','s','','STARTMEETME')
            GROUP BY dst ORDER BY anzahl DESC LIMIT 10
        """, [extension])
        stats['top_angerufen'] = cur.fetchall()

        # Anrufe nach Stunde
        cur.execute("""
            SELECT HOUR(calldate) as stunde,
                   COUNT(*) as anrufe,
                   SUM(src=%s) as ausgehend,
                   SUM(dst=%s) as eingehend
            FROM cdr
            WHERE (src=%s OR dst=%s)
            GROUP BY HOUR(calldate) ORDER BY stunde
        """, [extension, extension, extension, extension])
        stats['stunden'] = cur.fetchall()

        # Pro-Tag letzte 30 Tage
        cur.execute("""
            SELECT DATE(calldate) as datum,
                   COUNT(*) as anrufe,
                   SUM(src=%s) as ausgehend,
                   SUM(dst=%s) as eingehend,
                   SUM(disposition='ANSWERED') as answered
            FROM cdr
            WHERE (src=%s OR dst=%s) AND calldate >= DATE_SUB(NOW(), INTERVAL 30 DAY)
            GROUP BY DATE(calldate) ORDER BY datum DESC
        """, [extension, extension, extension, extension])
        rows = cur.fetchall()
        for r in rows:
            if hasattr(r.get('datum'), 'strftime'):
                r['datum'] = r['datum'].strftime('%Y-%m-%d')
        stats['tage'] = rows

        cur.close()
        conn.close()

    except Exception as e:
        logger.error(f'CDR get_stats_for_extension Fehler: {e}')

    return stats


def lookup_number_in_cdr(phone_norm, limit=20):
    """Alle CDR-Einträge für eine normalisierte Nummer (alle Formate)."""
    # Verschiedene Formate erzeugen: 004917..., 017..., +4917...
    variants = _phone_variants(phone_norm)
    if not variants:
        return []

    placeholders = ','.join(['%s'] * len(variants))
    sql = f"""
        SELECT calldate, src, dst, disposition, billsec, uniqueid
        FROM cdr
        WHERE src IN ({placeholders}) OR dst IN ({placeholders})
        ORDER BY calldate DESC LIMIT %s
    """
    try:
        conn = _get_conn()
        cur = conn.cursor(dictionary=True)
        cur.execute(sql, variants * 2 + [limit])
        rows = cur.fetchall()
        cur.close()
        conn.close()
        for row in rows:
            if isinstance(row.get('calldate'), datetime):
                row['calldate'] = row['calldate'].strftime('%Y-%m-%d %H:%M:%S')
        return rows
    except Exception as e:
        logger.error(f'CDR lookup_number Fehler: {e}')
        return []


def _phone_variants(phone_norm):
    """Erzeugt alle möglichen Schreibweisen einer Nummer."""
    if not phone_norm:
        return []
    variants = {phone_norm}
    # 0049... → 017...
    if phone_norm.startswith('0049'):
        variants.add('0' + phone_norm[4:])
        variants.add('+49' + phone_norm[4:])
    # 017... → 0049...
    elif phone_norm.startswith('0') and not phone_norm.startswith('00'):
        variants.add('0049' + phone_norm[1:])
        variants.add('+49' + phone_norm[1:])
    return list(variants)


def _fmt_duration(seconds):
    """Sekunden → 'MM:SS' oder 'H:MM:SS'"""
    if not seconds:
        return '0:00'
    seconds = int(seconds)
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    if h:
        return f'{h}:{m:02d}:{s:02d}'
    return f'{m}:{s:02d}'
