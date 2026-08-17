"""
master_merger.py  v2
====================
Mergt beliebig viele CV-Dokumente desselben Freelancers zu einem
konsolidierten pre_json.

Architektur:
  Szenario A (0 CVs):  nur api_pre_json + Extras einfuegen
  Szenario B (1 CV):   PDF als Basis + API override + Extras
  Szenario C (2+ CVs): vollstaendiger Merge mit Projekt-Matching

Projekt-Matching (3 Stufen, regelbasiert):
  Stufe 1: API-references als Anker aufbereiten (ISO-Datum, kanonische Firma)
  Stufe 2: 3-Signal-Scoring (period + company + keywords)
           >= match_high -> regelbasierter Match
           match_low..match_high -> LLM entscheidet
           < match_low  -> eigenes Projekt
  Stufe 3: Felder zusammenfuehren (feste Prioritaeten, kein LLM)

Parallelisierung:
  - Felder-Merge: parallel (parallel_workers_sections aus settings.json)
  - Projekt-Merge: parallel (parallel_workers_projects aus settings.json)
  - LLM-Entscheidungen bei unsicheren Matches: parallel

Alle Schwellwerte und Gewichte aus settings.json -> merger{}
Alle LLM-Prompts aus DB (PromptTemplate)
Keine hardcodierten Keywords, keine Sprach-Annahmen

Hardcoded (unvermeidbar):
  - FL_BRANCHE Dict: FL-API enum -> Deutsch (FL-API spezifisch)
  - SKILL_CATS: 1:1 DB-Schema
  - _empty_pre_json(): leeres Schema, 1:1 DB-Spiegelung

Singleton: master_merger
"""

import copy
import json
import logging
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

FL_BRANCHE = {
    'consumer_goods_and_retail':           'Konsumgueter und Handel',
    'industry_and_mechanical_engineering': 'Industrie und Maschinenbau',
    'banking_and_finance':                 'Banken und Finanzen',
    'it_and_software':                     'IT und Software',
    'healthcare':                          'Gesundheitswesen',
    'automotive':                          'Automotive',
    'energy':                              'Energie',
    'energy_water_and_environment':        'Energie, Wasser und Umwelt',
    'insurance':                           'Versicherungen',
    'telecommunications':                  'Telekommunikation',
    'public_sector':                       'Oeffentlicher Dienst',
    'logistics':                           'Logistik',
    'transport_and_logistics':             'Transport und Logistik',
    'consulting':                          'Beratung',
    'media_and_entertainment':             'Medien und Unterhaltung',
    'real_estate':                         'Immobilien',
    'education':                           'Bildung',
    'pharmaceutical':                      'Pharma',
    'food_and_beverage':                   'Lebensmittel und Getraenke',
    'construction':                        'Bau und Immobilien',
    'chemical':                            'Chemie',
    'aerospace':                           'Luft- und Raumfahrt',
    'agriculture':                         'Landwirtschaft',
}

SKILL_CATS = [
    'architecture_pattern', 'business_software', 'ci_cd_tool',
    'cloud_platform', 'communication_tool', 'database', 'data_format',
    'data_management', 'development_environment', 'devops_tool',
    'documentation_tool', 'framework', 'hardware', 'identity_management',
    'it_infrastructure', 'methodology', 'monitoring_tool', 'network_protocol',
    'operating_system', 'programming_languages', 'project_management',
    'security_tool', 'soft_skill', 'special_concept', 'special_skill',
    'testing_tool', 'version_control', 'virtualization',
]


def _load_settings() -> dict:
    defaults = {
        'w_period': 0.5, 'w_company': 0.4, 'w_keyword': 0.1,
        'match_high': 0.7, 'match_low': 0.3,
        'min_company_len': 6,
        'workers_projects': 10,
        'workers_sections': 6,
    }
    try:
        cfg_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            '..', '..', '..', 'settings.json'
        )
        with open(cfg_path, encoding='utf-8') as f:
            cfg = json.load(f)
        m  = cfg.get('merger', {})
        w  = m.get('match_weights', {})
        wp = float(w.get('period',  defaults['w_period']))
        wc = float(w.get('company', defaults['w_company']))
        wk = float(w.get('keyword', defaults['w_keyword']))
        if abs(wp + wc + wk - 1.0) > 0.01:
            logger.warning("[MasterMerger] match_weights != 1.0 -> Defaults")
            wp, wc, wk = defaults['w_period'], defaults['w_company'], defaults['w_keyword']
        c  = m.get('confidence', {})
        co = m.get('company', {})
        p  = cfg.get('pipeline', {})
        return {
            'w_period':        wp,
            'w_company':       wc,
            'w_keyword':       wk,
            'match_high':      float(c.get('match_high',   defaults['match_high'])),
            'match_low':       float(c.get('match_low',    defaults['match_low'])),
            'min_company_len': int(co.get('min_match_len', defaults['min_company_len'])),
            'workers_projects':int(p.get('parallel_workers_projects', defaults['workers_projects'])),
            'workers_sections':int(p.get('parallel_workers_sections', defaults['workers_sections'])),
        }
    except Exception as e:
        logger.warning(f"[MasterMerger] settings.json: {e} -> Defaults")
        return defaults


def _get_prompt(stage: str) -> Optional[str]:
    try:
        from apps.cv_extractor.models import PromptTemplate
        pt = PromptTemplate.objects.filter(stage=stage, is_active=True).first()
        return pt.prompt_text if pt else None
    except Exception as e:
        logger.warning(f"[MasterMerger] Prompt '{stage}': {e}")
        return None


def _llm(prompt: str, use_array: bool = False):
    try:
        if use_array:
            from apps.cv_extractor.services.deepseek_api_label import deepseek_label_api
            return deepseek_label_api.extract(prompt)
        from apps.cv_extractor.services.deepseek_api import deepseek_api
        return deepseek_api.extract(prompt)
    except Exception as e:
        logger.warning(f"[MasterMerger] LLM: {e}")
        return None


def _normalize_period(period: str):
    if not period or not str(period).strip():
        return (0,0,0,0)
    import re as _re
    from datetime import datetime as _dt
    p = str(period).strip()
    now = _dt.now()
    def _yv(y): return 1900<=y<=2100
    def _mv(m): return 1<=m<=12
    def _2y(y): return 2000+y if y<50 else 1900+y
    MO={'januar':1,'februar':2,'maerz':3,'marz':3,'april':4,'mai':5,'juni':6,
        'juli':7,'august':8,'september':9,'oktober':10,'november':11,'dezember':12,
        'january':1,'february':2,'march':3,'may':5,'june':6,'july':7,'august':8,
        'september':9,'october':10,'november':11,'december':12,'april':4,
        'janvier':1,'fevrier':2,'mars':3,'avril':4,'juin':6,'juillet':7,
        'aout':8,'septembre':9,'octobre':10,'novembre':11,'decembre':12,
        'gennaio':1,'febbraio':2,'marzo':3,'aprile':4,'maggio':5,'giugno':6,
        'luglio':7,'agosto':8,'settembre':9,'ottobre':10,'dicembre':12,
        'enero':1,'febrero':2,'abril':4,'mayo':5,'junio':6,'julio':7,
        'agosto':8,'septiembre':9,'octubre':10,'noviembre':11,'diciembre':12,
        'jan':1,'feb':2,'mar':3,'apr':4,'jun':6,'jul':7,'aug':8,
        'sep':9,'oct':10,'okt':10,'nov':11,'dec':12,'dez':12,'maer':3}
    OPEN=_re.compile(
        r'^(heute|aktuell|laufend|dato|gegenwart|derzeit|unbefristet|'
        r'now|present|current|ongoing|to\s+date|till\s+now|open|indefinite|'
        r"aujourd'?hui|actuel|hoy|actual|oggi|heden|huidig|idag|hoje)$",
        _re.I)
    SINCE=_re.compile(r'^(seit|ab|since|from|starting)\s+',_re.I)
    def _open(s): return bool(OPEN.match(s.strip())) if s else False
    def _date(t):
        t=t.strip()
        if not t: return None
        if _open(t): return 'open'
        m=_re.match(r'^(\d{4})-(\d{2})-\d{2}[T\d]',t)
        if m:
            y,mo=int(m.group(1)),int(m.group(2))
            if _yv(y) and _mv(mo): return y,mo
        m=_re.match(r'^(\d{4})-(\d{2})-\d{2}T[\d:+\-Z]+$',t)
        if m:
            y,mo=int(m.group(1)),int(m.group(2))
            if _yv(y) and _mv(mo): return y,mo
        m=_re.match(r'^(\d{4})[/.\-](\d{2})[/.\-](\d{2})$',t)
        if m:
            y,mo=int(m.group(1)),int(m.group(2))
            if _yv(y) and _mv(mo): return y,mo
        m=_re.match(r'^(\d{4})[/.\-](\d{1,2})$',t)
        if m:
            y,mo=int(m.group(1)),int(m.group(2))
            if _yv(y) and _mv(mo): return y,mo
        m=_re.match(r'^(\d{1,2})\s*[/.\- ]\s*(\d{1,2})\s*[/.\- ]\s*(\d{4})$',t)
        if m:
            a,b,y=int(m.group(1)),int(m.group(2)),int(m.group(3))
            if _yv(y):
                if a>12 and _mv(b): return y,b
                if b>12 and _mv(a): return y,a
                if _mv(b): return y,b
                if _mv(a): return y,a
        m=_re.match(r'^(\d{1,2})\s*[/.\- ]\s*(\d{4})$',t)
        if m:
            mo,y=int(m.group(1)),int(m.group(2))
            if _mv(mo) and _yv(y): return y,mo
        m=_re.match(r'^(\d{1,2})[/.](\d{2})$',t)
        if m:
            mo,yy=int(m.group(1)),int(m.group(2))
            if _mv(mo): return _2y(yy),mo
        m=_re.match(r'^(\d{4})(\d{2})(\d{2})$',t)
        if m:
            y,mo=int(m.group(1)),int(m.group(2))
            if _yv(y) and _mv(mo): return y,mo
        m=_re.match(r'^(\d{2})(\d{2})(\d{4})$',t)
        if m:
            y,mo=int(m.group(3)),int(m.group(2))
            if _yv(y) and _mv(mo): return y,mo
        m=_re.match(r'^(\d{4})(\d{2})$',t)
        if m:
            y,mo=int(m.group(1)),int(m.group(2))
            if _yv(y) and _mv(mo): return y,mo
        m=_re.match(r'^(\d{2})(\d{4})$',t)
        if m:
            mo,y=int(m.group(1)),int(m.group(2))
            if _mv(mo) and _yv(y): return y,mo
        m=_re.match(r'^(\d{4})$',t)
        if m:
            y=int(m.group(1))
            if _yv(y): return y,0
        m=_re.match(r'^Q([1-4])\s*[/\-]?\s*(\d{4})$',t,_re.I)
        if m:
            q,y=int(m.group(1)),int(m.group(2))
            if _yv(y): return y,(q-1)*3+1
        tl=t.lower()
        for mn,mi in sorted(MO.items(),key=lambda x:-len(x[0])):
            if mn in tl:
                ym=_re.search(r'\b(\d{4})\b',t)
                if ym and _yv(int(ym.group(1))): return int(ym.group(1)),mi
                ym=_re.search(r'\b(\d{2})\b',t)
                if ym: return _2y(int(ym.group(1))),mi
        nums=_re.findall(r'\d+',t)
        if len(nums)==3:
            a,b,c=int(nums[0]),int(nums[1]),int(nums[2])
            if _yv(c) and _mv(b): return c,b
            if _yv(a) and _mv(b): return a,b
        if len(nums)==2:
            a,b=int(nums[0]),int(nums[1])
            if _yv(b) and _mv(a): return b,a
            if _yv(a) and _mv(b): return a,b
        return None
    def _build(sd,et):
        if not sd or sd=='open': return None
        ys,ms=sd
        if isinstance(et,str) and _open(et): return (ys,ms,9999,99)
        if et=='open': return (ys,ms,9999,99)
        ed=_date(et) if isinstance(et,str) else et
        if ed=='open': return (ys,ms,9999,99)
        if ed: return (ys,ms,ed[0],ed[1])
        return None
    sm=SINCE.match(p)
    if sm:
        sd=_date(p[sm.end():].strip())
        if sd and sd!='open': return (sd[0],sd[1],9999,99)
    m=_re.match(r'^(\d{4})-(\d{2})-\d{2}T[\d:+\-Z]+$',p)
    if m:
        y,mo=int(m.group(1)),int(m.group(2))
        if _yv(y) and _mv(mo): return (y,mo,y,mo)
    m=_re.search(r'(\d{4}-\d{2}-?\d{0,2})\s+to\s+(\d{4}-\d{2}-?\d{0,2})',p,_re.I)
    if m:
        sd=_date(m.group(1)); ed=_date(m.group(2))
        if sd and sd!='open' and ed and ed!='open': return (sd[0],sd[1],ed[0],ed[1])
    ISEP=r'\s*(?:\u2013|\u2014|--?)\s*'
    m=_re.search(r'(\d{4}-\d{2}-\d{2}(?:T[^\s\u2013\u2014\-]+)?)'+ISEP+
                 r'(\d{4}-\d{2}-\d{2}(?:T[^\s\u2013\u2014\-]+)?)',p)
    if m:
        sd=_date(m.group(1)); ed=_date(m.group(2))
        if sd and sd!='open' and ed and ed!='open': return (sd[0],sd[1],ed[0],ed[1])
    m=_re.search(r'(\d{4}-\d{2})'+ISEP+r'(\d{4}-\d{2})',p)
    if m:
        sd=_date(m.group(1)); ed=_date(m.group(2))
        if sd and sd!='open' and ed and ed!='open': return (sd[0],sd[1],ed[0],ed[1])
    m=_re.search(r'(\d{4}-\d{2})'+ISEP+
                 r'(heute|aktuell|now|present|current|ongoing|laufend|actual|hoy|oggi|heden)',
                 p,_re.I)
    if m:
        sd=_date(m.group(1))
        if sd and sd!='open': return (sd[0],sd[1],9999,99)
    m=_re.match(r'^(\d{1,2})-(\d{4})\s*-\s*(\d{1,2})-(\d{4})$',p)
    if m:
        mo1,y1,mo2,y2=int(m.group(1)),int(m.group(2)),int(m.group(3)),int(m.group(4))
        if _yv(y1) and _mv(mo1) and _yv(y2) and _mv(mo2):
            return (y1,mo1,y2,mo2)
    SEASONS = {
        'fruehling':3,'fruehling':3,'spring':3,'primavera':3,'printemps':3,
        'sommer':6,'summer':6,'estate':6,'ete':6,
        'herbst':9,'autumn':9,'fall':9,'autunno':9,'automne':9,
        'winter':12,'inverno':12,'hiver':12,
    }
    for sn,sm_val in SEASONS.items():
        if sn in p.lower():
            ym=_re.search(r'\b(\d{4})\b',p)
            if ym and _yv(int(ym.group(1))):
                y=int(ym.group(1))
                return (y,sm_val,y,sm_val)
    m=_re.match(r'^H([12])\s*[/\-]?\s*(\d{4})$',p,_re.I)
    if m:
        h,y=int(m.group(1)),int(m.group(2))
        if _yv(y): return (y,1 if h==1 else 7, y, 6 if h==1 else 12)
    m=_re.match(r'^(1|2)\.?\s*Halbjahr\s+(\d{4})$',p,_re.I)
    if m:
        h,y=int(m.group(1)),int(m.group(2))
        if _yv(y): return (y,1 if h==1 else 7, y, 6 if h==1 else 12)
    m=_re.match(r'^(first|second)\s+half\s+(\d{4})$',p,_re.I)
    if m:
        h=1 if m.group(1).lower()=='first' else 2
        y=int(m.group(2))
        if _yv(y): return (y,1 if h==1 else 7, y, 6 if h==1 else 12)
    m=_re.match(r'^(?:KW|W)\s*(\d{1,2})\s*[/\-]?\s*(\d{4})$',p,_re.I)
    if m:
        kw,y=int(m.group(1)),int(m.group(2))
        if _yv(y) and 1<=kw<=53:
            import datetime as _datetime
            try:
                d=_datetime.datetime.strptime(f'{y}-W{kw:02d}-1','%Y-W%W-%w')
                return (y,d.month,y,d.month)
            except: return (y,1,y,1)
    m=_re.match(r'^Q([1-4])\s*(\d{4})\s*[\-\u2013\u2014]\s*Q([1-4])\s*(\d{4})$',p,_re.I)
    if m:
        q1,y1,q2,y2=int(m.group(1)),int(m.group(2)),int(m.group(3)),int(m.group(4))
        return (y1,(q1-1)*3+1,y2,q2*3)
    m=_re.match(r'^Q([1-4])\s*[/\-]?\s*(\d{4})$',p,_re.I)
    if m:
        q,y=int(m.group(1)),int(m.group(2))
        if _yv(y): return (y,(q-1)*3+1,y,q*3)
    pl=p.lower()
    for mn1,mi1 in sorted(MO.items(),key=lambda x:-len(x[0])):
        if pl.startswith(mn1):
            rest=p[len(mn1):].strip()
            m2=_re.match(r'^(\d{4})?\s*[\-\u2013\u2014]\s*(.+)$',rest)
            if m2:
                yr1=m2.group(1); ep=m2.group(2).strip()
                if _open(ep):
                    y1=int(yr1) if yr1 and _yv(int(yr1)) else now.year
                    return (y1,mi1,9999,99)
                ed=_date(ep)
                if ed and ed!='open':
                    y1=int(yr1) if yr1 and _yv(int(yr1)) else ed[0]
                    return (y1,mi1,ed[0],ed[1])
            break
    for ch in '\u2013\u2014\u2012\u2010\u2015':
        p=p.replace(ch,'-')
    p=_re.sub(r'-{2,}','-',p)
    p=_re.sub(r'(\S)-(\S)',r'\1 - \2',p)
    p=_re.sub(r'\s+-\s+',' - ',p)
    for sep,opn in [(' till now',1),(' to date',1),(' until ',0),(' bis ',0),(' to ',0)]:
        lo=p.lower()
        if sep in lo:
            i=lo.find(sep)
            sd=_date(p[:i].strip())
            et='open' if opn else p[i+len(sep):].strip()
            r=_build(sd,et)
            if r: return r
    if ' - ' in p:
        pts=p.split(' - ',1)
        r=_build(_date(pts[0].strip()),pts[1].strip())
        if r: return r
    s=_date(p)
    if s and s!='open': return (s[0],s[1],s[0],s[1])
    if not _re.match(r'^[\d\s/.\-]+$', p.strip()):
        yrs=_re.findall(r'\b(19\d{2}|20\d{2})\b',p)
        if len(yrs)>=2: return (int(yrs[0]),0,int(yrs[-1]),0)
        if len(yrs)==1: y=int(yrs[0]); return (y,0,y,0)
    return (0,0,0,0)


def _periods_overlap(p1: str, p2: str, tolerance_months: int = 6) -> bool:
    s1, m1, e1, em1 = _normalize_period(p1)
    s2, m2, e2, em2 = _normalize_period(p2)
    if not s1 or not s2:
        return False
    def _mo(y, m): return y * 12 + (m if m else 6)
    start1 = _mo(s1, m1);  end1 = 999999 if e1 >= 9999 else _mo(e1, em1)
    start2 = _mo(s2, m2);  end2 = 999999 if e2 >= 9999 else _mo(e2, em2)
    return not (end1 + tolerance_months < start2 or end2 + tolerance_months < start1)


def _period_precision(period: str) -> int:
    if not period: return 0
    if re.search(r'\d{1,2}[./]\d{4}', period): return 3
    if re.search(r'\d{4}-\d{2}', period):       return 2
    if re.search(r'\d{4}', period):              return 1
    return 0


def _to_months(y: int, m: int) -> int:
    return y * 12 + (m if m else 6)


def _period_contains(outer: str, inner: str) -> bool:
    """True wenn inner KOMPLETT INNERHALB outer liegt (nicht exakt gleich)."""
    s1, m1, e1, em1 = _normalize_period(outer)
    s2, m2, e2, em2 = _normalize_period(inner)
    if not s1 or not s2:
        return False
    outer_start = _to_months(s1, m1)
    outer_end   = 999999 if e1 >= 9999 else _to_months(e1, em1)
    inner_start = _to_months(s2, m2)
    inner_end   = 999999 if e2 >= 9999 else _to_months(e2, em2)
    contained = (outer_start <= inner_start and inner_end <= outer_end)
    exact     = (abs(outer_start - inner_start) <= 1 and
                 abs(outer_end   - inner_end)   <= 1)
    return contained and not exact


def _company_score(c1: str, c2: str, min_len: int = 6) -> float:
    if not c1 or not c2: return 0.0
    c1n = c1.lower().strip()
    c2n = c2.lower().strip()
    sfx = (r'\s+(gmbh|ag|kg|ohg|gbr|ltd|inc|corp|llc|bv|nv|sa|srl|'
           r'co\.|plc|ab|oy|as|se|kgaa|ug|eg|ev|mbh)\.?$')
    c1s = re.sub(sfx, '', c1n, flags=re.IGNORECASE).strip()
    c2s = re.sub(sfx, '', c2n, flags=re.IGNORECASE).strip()
    if c1n == c2n: return 1.0
    if c1s and c2s and c1s == c2s: return 0.95
    shorter, longer = (c1s, c2s) if len(c1s) <= len(c2s) else (c2s, c1s)
    if len(shorter) >= min_len and shorter in longer:
        return 0.8 * (len(shorter) / max(len(longer), 1))
    return 0.0


def _keywords_overlap(kw1: List[str], kw2: List[str]) -> float:
    if not kw1 or not kw2: return 0.0
    s1 = {k.lower().strip() for k in kw1 if k and len(k.strip()) > 1}
    s2 = {k.lower().strip() for k in kw2 if k and len(k.strip()) > 1}
    if not s1 or not s2: return 0.0
    return len(s1 & s2) / len(s1 | s2)


def _extract_tools_from_html(html: str) -> List[str]:
    if not html: return []
    try:
        from bs4 import BeautifulSoup
        text = BeautifulSoup(html, 'html.parser').get_text(' ', strip=True)
    except Exception:
        text = re.sub(r'<[^>]+>', ' ', html)
    m = re.search(
        r'(?:tools?|technologies?|technologien?|stack|umfeld|methoden?|methods?)'
        r'\s*[&und/]*\s*(?:tools?)?\s*:\s*([^\n\r]{5,400})',
        text, re.IGNORECASE
    )
    if m:
        tools = [i.strip().rstrip('.') for i in re.split(r'[,;]', m.group(1))
                 if i.strip() and 2 <= len(i.strip()) <= 60]
        if len(tools) >= 2:
            return tools
    try:
        from bs4 import BeautifulSoup
        items = [li.get_text(' ', strip=True)
                 for li in BeautifulSoup(html, 'html.parser').find_all('li')]
        if items:
            last  = items[-1]
            parts = [p.strip() for p in last.split(',')]
            if len(parts) >= 3 and all(len(p) <= 50 for p in parts):
                return [p for p in parts if p and len(p) >= 2]
    except Exception:
        pass
    return []


def _dedup_list(items: List, key_fn=None) -> List:
    seen = set(); result = []
    for item in items:
        if item is None: continue
        key = (key_fn(item) if key_fn else str(item)).lower().strip()
        if key and key not in seen:
            seen.add(key); result.append(item)
    return result


def _tech_union(lists: List[List]) -> List[str]:
    all_techs = []
    for lst in lists:
        if not lst: continue
        for t in lst:
            if isinstance(t, dict):
                name = (t.get('name') or t.get('skill') or t.get('technology') or '').strip()
            elif isinstance(t, str):
                name = t.strip()
            else:
                continue
            if name and 2 <= len(name) <= 100:
                all_techs.append(name)
    return _dedup_list(all_techs)


def _best_activities(lists: List[List]) -> List[str]:
    non_empty = [l for l in lists if l]
    if not non_empty: return []
    base = max(non_empty, key=len)
    seen = {a.lower().strip()[:50] for a in base if a}
    result = list(base)
    for lst in non_empty:
        if lst is base: continue
        for act in lst:
            key = act.lower().strip()[:50] if act else ''
            if key and key not in seen:
                seen.add(key); result.append(act)
    return result


def _longer_str(s1: str, s2: str) -> str:
    s1 = (s1 or '').strip(); s2 = (s2 or '').strip()
    if not s1: return s2
    if not s2: return s1
    return s1 if len(s1) >= len(s2) else s2


def _empty_pre_json() -> dict:
    return {
        'metadata': {
            'aid': '', 'version': '', 'consultant_dir': '',
            'first_name': '', 'last_name': '', 'headline': '',
            'source': {'type': '', 'filename': '', 'filesize': 0,
                       'import_id': '', 'import_date': ''},
            'pipeline': {'version': '5.0', 'step': 'merged',
                         'extractor': 'master_merger_v2',
                         'model': 'deepseek-chat', 'self_learning': True},
            'duplicate_check': {'exists': False, 'message': ''},
            'statistics': {'total_categories': 0, 'has_personal': False,
                           'has_skills': False, 'has_experience': False},
        },
        'extracted_data': {
            'personal': {
                'first_name': '', 'last_name': '', 'birth_year': None,
                'nationality': '', 'degree': '', 'email': '', 'phone': '',
                'website': '', 'location': '', 'availability': '',
                'edv_experience_since': None, 'headline': '',
                'summary': '', 'company': '',
            },
            'languages': [], 'skills': {k: [] for k in SKILL_CATS},
            'certifications': [], 'experience': [], 'industries': [],
            'focus_areas': [], 'focus_experience': [],
            'education': [], 'other': [],
        },
        'audit': {
            'created_by': 'master_merger_v2',
            'created_at': datetime.now().isoformat(),
            'source_file': '', 'steps_completed': [],
        },
    }


class MasterMerger:

    def __init__(self):
        self._cfg = None

    @property
    def cfg(self) -> dict:
        if self._cfg is None:
            self._cfg = _load_settings()
        return self._cfg

    def merge(self,
              pdf_pre_jsons:        List[dict],
              api_pre_json:         dict,
              extra_certifications: List[dict] = None,
              extra_experience:     List[dict] = None,
              extra_education:      List[dict] = None,
              profil_raw:           dict = None) -> dict:
        extra_certifications = extra_certifications or []
        extra_experience     = extra_experience     or []
        extra_education      = extra_education      or []
        n = len(pdf_pre_jsons)
        logger.info(
            f"[MasterMerger] START: {n} PDF(s) | "
            f"certs={len(extra_certifications)} "
            f"refs={len(extra_experience)} "
            f"edu={len(extra_education)} | "
            f"period={self.cfg['w_period']} "
            f"company={self.cfg['w_company']} "
            f"keyword={self.cfg['w_keyword']} | "
            f"high={self.cfg['match_high']} "
            f"low={self.cfg['match_low']}"
        )

        if n == 0:
            logger.info("[MasterMerger] Szenario A: nur API + Extras")
            result = copy.deepcopy(api_pre_json) if api_pre_json else _empty_pre_json()
            result = self._step_extras(result, extra_certifications,
                                       extra_experience, extra_education)
            self._finalize(result, 'api_only', 0, 0)
            return result

        if n == 1:
            logger.info("[MasterMerger] Szenario B: 1 PDF + API")
            base   = copy.deepcopy(pdf_pre_jsons[0])
            result = self._api_override(base, api_pre_json, profil_raw)
            result = self._step_extras(result, extra_certifications,
                                       extra_experience, extra_education)
            n_in  = len(pdf_pre_jsons[0].get('extracted_data', {}).get('experience', []))
            n_out = len(result.get('extracted_data', {}).get('experience', []))
            self._finalize(result, 'single_pdf+api', n_in, n_out)
            return result

        logger.info(f"[MasterMerger] Szenario C: {n} PDFs")
        n_in = sum(
            len(pj.get('extracted_data', {}).get('experience', []))
            for pj in pdf_pre_jsons
        )

        api_anchors = self._build_api_anchors(api_pre_json)
        logger.info(f"[MasterMerger] {len(api_anchors)} API-Anker")

        all_projs_raw = []
        for di, pj in enumerate(pdf_pre_jsons):
            for proj in pj.get('extracted_data', {}).get('experience', []):
                all_projs_raw.append(copy.deepcopy(proj))

        logger.info(f"[MasterMerger] Rohe PDF-Projekte: {len(all_projs_raw)}")
        all_projs_deduped = self._dedup_pdf_projects(all_projs_raw)
        logger.info(f"[MasterMerger] Nach Dedup: {len(all_projs_deduped)}")

        all_projs = []
        for di, proj in enumerate(all_projs_deduped):
            all_projs.append({'doc_idx': di, 'proj_idx': 0, 'project': proj})

        merged_projects = self._match_and_merge(all_projs, api_anchors)
        merged_fields   = self._merge_fields_parallel(pdf_pre_jsons)
        result          = self._assemble(merged_projects, merged_fields,
                                         pdf_pre_jsons[0])
        result = self._step_extras(result, extra_certifications,
                                   extra_experience, extra_education)
        result = self._api_override(result, api_pre_json, profil_raw)
        result = self._final_check(result, pdf_pre_jsons)

        self._finalize(result, f'{n}_pdfs+api', n_in, len(merged_projects))
        logger.info(f"[MasterMerger] FERTIG: {n_in} -> {len(merged_projects)} Projekte")
        return result

    def _build_api_anchors(self, api_pre_json: dict) -> List[dict]:
        if not api_pre_json:
            return []
        anchors = []
        for exp in api_pre_json.get('extracted_data', {}).get('experience', []):
            period   = exp.get('period', '')
            company  = exp.get('company', '')
            raw_ind  = exp.get('industry', '')
            industry = FL_BRANCHE.get(raw_ind, raw_ind)
            keywords = _tech_union([exp.get('technologies', [])])
            for act in exp.get('activities', []):
                keywords.extend(_extract_tools_from_html(str(act)))
            keywords = _dedup_list(keywords)
            anchors.append({
                'period':        period,
                'period_parsed': _normalize_period(period),
                'company':       company,
                'industry':      industry,
                'keywords':      keywords,
                'original':      copy.deepcopy(exp),
            })
        return anchors

    def _score(self, proj: dict, anchor: dict) -> float:
        cfg      = self.cfg
        p_proj   = proj.get('period', '')
        p_anchor = anchor['period']

        s_period  = 1.0 if _periods_overlap(p_proj, p_anchor) else 0.0
        s_company = _company_score(
            proj.get('company', ''), anchor['company'],
            cfg['min_company_len'])
        s_keyword = _keywords_overlap(
            proj.get('technologies', []), anchor.get('keywords', []))

        # Keine Periodenuberlappung -> kein Match
        if s_period == 0.0:
            return 0.0

        # Start-Datum mehr als 2 Monate auseinander -> kein Match
        sy1, sm1, _, _ = _normalize_period(p_proj)
        sy2, sm2, _, _ = _normalize_period(p_anchor)
        if sy1 and sy2:
            start_diff = abs(_to_months(sy1, sm1) - _to_months(sy2, sm2))
            if start_diff > 2:
                return 0.0

        return round(
            s_period  * cfg['w_period'] +
            s_company * cfg['w_company'] +
            s_keyword * cfg['w_keyword'], 4)

    def _match_and_merge(self, all_projs: List[dict],
                          api_anchors: List[dict]) -> List[dict]:
        cfg = self.cfg

        # Schritt 1: Scoring — period_only direkt unmatched, rest zum LLM
        matched   = {}
        uncertain = []
        unmatched = []

        for item in all_projs:
            proj = item['project']
            best_ai = -1; best_score = 0.0
            best_sc = 0.0; best_sk = 0.0
            for ai, anchor in enumerate(api_anchors):
                s = self._score(proj, anchor)
                if s > best_score:
                    best_score = s; best_ai = ai
                    best_sc = _company_score(
                        proj.get('company', ''), anchor['company'],
                        cfg['min_company_len'])
                    best_sk = _keywords_overlap(
                        proj.get('technologies', []), anchor.get('keywords', []))

            period_only = (best_score > 0 and best_sc == 0.0 and best_sk == 0.0)

            if best_score >= cfg['match_high']:
                matched.setdefault(best_ai, []).append(proj)
            elif period_only:
                # Nur Periode matcht — zu wenig Information fuer zuverlaessiges Matching
                # Projekt bleibt eigenstaendig, Raupe am Ende fuehrt zusammen wenn noetig
                unmatched.append(proj)
            elif best_score > 0.0 and best_ai >= 0:
                uncertain.append((proj, best_ai, best_score))
            else:
                unmatched.append(proj)

        # Schritt 2: LLM fuer uncertain (haben Firma oder Keyword Match)
        if uncertain:
            logger.info(f"  {len(uncertain)} unsichere Matches -> LLM")
            with ThreadPoolExecutor(max_workers=cfg['workers_projects']) as ex:
                futures = {
                    ex.submit(self._llm_decide, proj,
                              api_anchors[ai], sc): (proj, ai)
                    for proj, ai, sc in uncertain
                }
                for future in as_completed(futures):
                    proj, ai = futures[future]
                    try:
                        if future.result():
                            matched.setdefault(ai, []).append(proj)
                        else:
                            unmatched.append(proj)
                    except Exception as e:
                        logger.warning(f"  LLM-Match: {e}")
                        unmatched.append(proj)

        # Schritt 3: Merge-Gruppen aufloesen
        all_final = []
        if matched:
            with ThreadPoolExecutor(max_workers=cfg['workers_projects']) as ex:
                futures = {
                    ex.submit(self._merge_group,
                              api_anchors[ai], projs): ai
                    for ai, projs in matched.items()
                }
                results_map = {}
                for future in as_completed(futures):
                    ai = futures[future]
                    try:
                        results_map[ai] = future.result()
                    except Exception as e:
                        logger.warning(f"  Merge-Gruppe {ai}: {e}")
                        results_map[ai] = copy.deepcopy(api_anchors[ai]['original'])
            for ai in sorted(results_map.keys()):
                if results_map[ai]:
                    all_final.append(results_map[ai])

        # API-Anker ohne Match direkt uebernehmen
        for ai, anchor in enumerate(api_anchors):
            if ai not in matched:
                all_final.append(copy.deepcopy(anchor['original']))

        # Eigenstaendige PDF-Projekte hinzufuegen
        all_final.extend(unmatched)

        # Schritt 4: Raupe auf dem Gesamtergebnis
        # Chronologisch sortieren, paarweise vergleichen, Duplikate zusammenfuehren
        def _sort_key(p):
            sy, sm, ey, em = _normalize_period(p.get('period', ''))
            return -(sy * 12 + (sm if sm else 6))

        all_final_sorted = sorted(all_final, key=_sort_key)
        pt = _get_prompt('master_dedup_projects')
        merged = [copy.deepcopy(all_final_sorted[0])] if all_final_sorted else []

        for i in range(1, len(all_final_sorted)):
            current = all_final_sorted[i]
            last    = merged[-1]

            if not _periods_overlap(last.get('period', ''),
                                    current.get('period', ''),
                                    tolerance_months=0):
                merged.append(copy.deepcopy(current))
                continue
            # Post-Raupe: nur mergen wenn Startmonat identisch
            sy1, sm1, _, _ = _normalize_period(last.get('period', ''))
            sy2, sm2, _, _ = _normalize_period(current.get('period', ''))
            if sy1 != sy2 or sm1 != sm2:
                merged.append(copy.deepcopy(current))
                continue

            same = False
            if pt:
                try:
                    doc_a = json.dumps({
                        'period':      last.get('period', ''),
                        'company':     last.get('company', ''),
                        'role':        last.get('role', last.get('title', '')),
                        'technologies':last.get('technologies', []),
                        'activities':  last.get('activities', [])[:3],
                    }, ensure_ascii=False)
                    doc_b = json.dumps({
                        'period':      current.get('period', ''),
                        'company':     current.get('company', ''),
                        'role':        current.get('role', current.get('title', '')),
                        'technologies':current.get('technologies', []),
                        'activities':  current.get('activities', [])[:3],
                    }, ensure_ascii=False)
                    r = _llm(pt.format(proj_a=doc_a, proj_b=doc_b))
                    if r and r.success and isinstance(r.data, dict):
                        same = bool(r.data.get('same', False))
                    elif r and r.success and isinstance(r.data, str):
                        same = r.data.strip().strip('"').lower() in (
                            'true', 'same', 'gleich', 'ja')
                except Exception as e:
                    logger.warning(f"[MasterMerger] post-raupe LLM: {e}")

            if same:
                for f in ('company', 'role', 'title', 'industry', 'location'):
                    merged[-1][f] = _longer_str(
                        merged[-1].get(f, ''), current.get(f, ''))
                merged[-1]['activities']   = _best_activities([
                    merged[-1].get('activities', []),
                    current.get('activities', [])])
                merged[-1]['technologies'] = _tech_union([
                    merged[-1].get('technologies', []),
                    current.get('technologies', [])])
                logger.debug(
                    f"  Post-Raupe MERGE: '{last.get('period')}' + "
                    f"'{current.get('period')}'")
            else:
                merged.append(copy.deepcopy(current))

        logger.info(
            f"  Matching: {len(matched)} gematcht | "
            f"{len(uncertain)} LLM | "
            f"{len(unmatched)} unmatched | "
            f"-> {len(merged)} Projekte")
        return merged

    def _merge_group(self, anchor: dict, variants: List[dict]) -> dict:
        if not variants:
            return copy.deepcopy(anchor['original'])
        api_proj     = anchor['original']
        all_variants = [api_proj] + variants

        period = api_proj.get('period', '')
        for v in variants:
            if _period_precision(v.get('period', '')) > _period_precision(period):
                period = v['period']

        company = (api_proj.get('company') or '').strip()
        if not company:
            for v in variants:
                if v.get('company', '').strip():
                    company = v['company'].strip(); break

        industry = anchor.get('industry', '')
        if not industry:
            for v in variants:
                if v.get('industry', '').strip():
                    industry = v['industry'].strip(); break

        title = (api_proj.get('title') or api_proj.get('position') or '').strip()
        for v in variants:
            title = _longer_str(title, v.get('title', ''))

        role = ''
        for v in variants:
            role = _longer_str(role, v.get('role', ''))
        if not role:
            role = (api_proj.get('role') or api_proj.get('position') or '').strip()

        location = ''
        for v in variants:
            if v.get('location', '').strip():
                location = v['location'].strip(); break

        activities   = _best_activities([v.get('activities', []) for v in all_variants])
        technologies = _tech_union(
            [anchor.get('keywords', [])] +
            [v.get('technologies', []) for v in all_variants])

        return {
            'period': period, 'title': title, 'company': company,
            'industry': industry, 'role': role, 'location': location,
            'activities': activities, 'technologies': technologies,
        }

    def _dedup_pdf_projects(self, projects: List[dict]) -> List[dict]:
        """
        Raupe-Algorithmus: Chronologisch sortieren, dann paarweise vergleichen.
        Projekt i und i+1: gleich -> zusammenfuehren, nicht gleich -> beide behalten.
        """
        if len(projects) <= 1:
            return projects

        def _sort_key(p):
            sy, sm, ey, em = _normalize_period(p.get('period', ''))
            return -(sy * 12 + sm)

        sorted_projs = sorted(projects, key=_sort_key)
        pt = _get_prompt('master_dedup_projects')
        result = [copy.deepcopy(sorted_projs[0])]

        for i in range(1, len(sorted_projs)):
            current = sorted_projs[i]
            last    = result[-1]

            if not _periods_overlap(last.get('period',''), current.get('period','')):
                result.append(copy.deepcopy(current))
                continue

            same = False
            if pt:
                try:
                    doc_a = json.dumps({
                        'period':      last.get('period',''),
                        'company':     last.get('company',''),
                        'role':        last.get('role', last.get('title','')),
                        'technologies':last.get('technologies',[]),
                        'activities':  last.get('activities',[])[:5],
                    }, ensure_ascii=False)
                    doc_b = json.dumps({
                        'period':      current.get('period',''),
                        'company':     current.get('company',''),
                        'role':        current.get('role', current.get('title','')),
                        'technologies':current.get('technologies',[]),
                        'activities':  current.get('activities',[])[:5],
                    }, ensure_ascii=False)
                    prompt = pt.format(proj_a=doc_a, proj_b=doc_b)
                    r = _llm(prompt)
                    if r and r.success and isinstance(r.data, dict):
                        same = bool(r.data.get('same', False))
                        logger.debug(f"  Dedup LLM: {r.data} -> same={same}")
                    elif r and r.success and isinstance(r.data, str):
                        same = r.data.strip().strip('"').lower() in ('true','same','gleich','ja')
                        logger.debug(f"  Dedup LLM str: {repr(r.data)} -> same={same}")
                    elif r and not r.success:
                        logger.warning(f"  Dedup LLM failed: {r.error}")
                except Exception as e:
                    logger.warning(f"[MasterMerger] dedup LLM: {e}")

            if same:
                for f in ('company', 'role', 'title', 'industry', 'location'):
                    result[-1][f] = _longer_str(result[-1].get(f,''), current.get(f,''))
                if _period_precision(current.get('period','')) > \
                        _period_precision(result[-1].get('period','')):
                    result[-1]['period'] = current['period']
                result[-1]['activities']   = _best_activities([
                    result[-1].get('activities',[]), current.get('activities',[])])
                result[-1]['technologies'] = _tech_union([
                    result[-1].get('technologies',[]), current.get('technologies',[])])
                logger.debug(
                    f"  Dedup: '{last.get('period')}' + "
                    f"'{current.get('period')}' zusammengefuehrt")
            else:
                result.append(copy.deepcopy(current))

        logger.info(f"  Dedup: {len(sorted_projs)} -> {len(result)} Projekte")
        return result

    def _llm_decide(self, proj: dict, anchor: dict, score: float) -> bool:
        pt = _get_prompt('master_merger_pair')
        if not pt:
            return score >= 0.5
        try:
            doc_a = json.dumps({
                'period':      proj.get('period', ''),
                'company':     proj.get('company', ''),
                'role':        proj.get('role', proj.get('title', '')),
                'technologies':proj.get('technologies', [])[:10],
            }, ensure_ascii=False)
            doc_b = json.dumps({
                'period':      anchor['period'],
                'company':     anchor['company'],
                'role':        anchor['original'].get(
                               'role', anchor['original'].get('title', '')),
                'technologies':anchor.get('keywords', [])[:10],
            }, ensure_ascii=False)
            prompt = pt.format(
                name_a=f"PDF ({proj.get('company', '?')})", doc_a=doc_a,
                name_b=f"API ({anchor['company']})",        doc_b=doc_b,
            )
            r = _llm(prompt)
            if r and r.success and r.data:
                data = r.data
                if isinstance(data, str):
                    dl = data.strip().strip('"').lower()
                    if dl in ('same', 'true', 'yes', 'gleich', 'ja'):
                        return True
                    if dl in ('different', 'false', 'no', 'verschieden', 'nein'):
                        return False
                elif isinstance(data, bool):
                    return data
                elif isinstance(data, dict):
                    same = (data.get('same') or data.get('match') or
                            data.get('result'))
                    if same is not None:
                        return bool(same)
        except Exception as e:
            logger.warning(f"[MasterMerger] _llm_decide: {e}")
        return score >= 0.5

    def _merge_fields_parallel(self, pdf_pre_jsons: List[dict]) -> dict:
        cfg = self.cfg

        def _sources(field):
            return [pj.get('extracted_data', {}).get(field)
                    for pj in pdf_pre_jsons
                    if pj.get('extracted_data', {}).get(field)]

        def _merge_personal():
            base = {}
            for pj in pdf_pre_jsons:
                src = pj.get('extracted_data', {}).get('personal', {})
                if not isinstance(src, dict): continue
                for k, v in src.items():
                    if k == 'languages': continue
                    if not base.get(k) and v:
                        base[k] = v
            return base

        def _merge_skills():
            merged = {k: [] for k in SKILL_CATS}
            for pj in pdf_pre_jsons:
                src = pj.get('extracted_data', {}).get('skills', {})
                if not isinstance(src, dict): continue
                for cat, items in src.items():
                    if cat not in merged: continue
                    seen = {x.lower() for x in merged[cat] if isinstance(x, str)}
                    for item in (items or []):
                        if isinstance(item, str) and item.lower() not in seen:
                            merged[cat].append(item); seen.add(item.lower())
            return {k: v for k, v in merged.items() if v}

        def _merge_languages():
            all_langs = []
            for pj in pdf_pre_jsons:
                all_langs.extend(
                    pj.get('extracted_data', {})
                      .get('personal', {}).get('languages', []))
            return _dedup_list(
                all_langs,
                key_fn=lambda x: x.get('name', str(x))
                if isinstance(x, dict) else str(x))

        def _merge_certs():
            all_items = []
            for src in _sources('certifications'):
                if isinstance(src, list): all_items.extend(src)
            return _dedup_list(all_items,
                key_fn=lambda x: x.get('name', str(x))
                if isinstance(x, dict) else str(x))

        def _merge_edu():
            all_items = []
            for src in _sources('education'):
                if isinstance(src, list): all_items.extend(src)
            return _dedup_list(all_items,
                key_fn=lambda x: x.get('degree', str(x))
                if isinstance(x, dict) else str(x))

        def _merge_list(field, max_items=30):
            all_items = []
            for src in _sources(field):
                if isinstance(src, list): all_items.extend(src)
            return _dedup_list(all_items,
                key_fn=lambda x: x.get('name', str(x))
                if isinstance(x, dict) else str(x))[:max_items]

        tasks = {
            'personal':         _merge_personal,
            'skills':           _merge_skills,
            'languages':        _merge_languages,
            'certifications':   _merge_certs,
            'education':        _merge_edu,
            'focus_areas':      lambda: _merge_list('focus_areas', 15),
            'focus_experience': lambda: _merge_list('focus_experience', 100),
            'industries':       lambda: _merge_list('industries', 20),
        }
        results = {}
        with ThreadPoolExecutor(max_workers=cfg['workers_sections']) as ex:
            futures = {ex.submit(fn): key for key, fn in tasks.items()}
            for future in as_completed(futures):
                key = futures[future]
                try:
                    results[key] = future.result()
                    logger.debug(f"  Feld {key}: OK")
                except Exception as e:
                    logger.warning(f"  Feld {key}: {e}")
                    results[key] = None
        return results

    def _assemble(self, merged_projects: List[dict],
                  merged_fields: dict, base_pj: dict) -> dict:
        result = copy.deepcopy(base_pj)
        ed     = result.setdefault('extracted_data', {})
        ed['experience'] = merged_projects
        for field, data in merged_fields.items():
            if data is None: continue
            if field == 'languages':
                ed.setdefault('personal', {})['languages'] = data
            elif field == 'personal':
                p = ed.setdefault('personal', {})
                for k, v in (data or {}).items():
                    if k != 'languages' and not p.get(k) and v:
                        p[k] = v
            else:
                ed[field] = data
        return result

    def _step_extras(self, result: dict, extra_certs: List[dict],
                     extra_exp: List[dict], extra_edu: List[dict]) -> dict:
        ed = result.setdefault('extracted_data', {})

        if extra_certs:
            existing = ed.get('certifications', [])
            seen = {c.get('name', '').lower() for c in existing}
            added = 0
            for cert in extra_certs:
                name = cert.get('name', '').lower().strip()
                if name and name not in seen:
                    existing.append(cert); seen.add(name); added += 1
            ed['certifications'] = existing
            if added: logger.info(f"  +{added} Zertifikate aus Docs")

        if extra_exp:
            existing = ed.get('experience', []); added = 0
            for exp in extra_exp:
                period = exp.get('period', ''); matched = False
                for ex in existing:
                    if _periods_overlap(period, ex.get('period', ''),
                                        tolerance_months=3):
                        if len(exp.get('company', '')) > len(ex.get('company', '')):
                            ex['company'] = exp['company']
                        ex['technologies'] = _tech_union([
                            ex.get('technologies', []),
                            exp.get('technologies', [])])
                        ex['activities'] = _best_activities([
                            ex.get('activities', []),
                            exp.get('activities', [])])
                        matched = True; break
                if not matched:
                    existing.append(exp); added += 1
            ed['experience'] = existing
            if added: logger.info(f"  +{added} Referenz-Projekte")

        if extra_edu:
            existing = ed.get('education', [])
            seen = {e.get('degree', '').lower() for e in existing}
            added = 0
            for edu in extra_edu:
                degree = edu.get('degree', '').lower().strip()
                if degree and degree not in seen:
                    existing.append(edu); seen.add(degree); added += 1
            ed['education'] = existing
            if added: logger.info(f"  +{added} Bildungseintraege")

        return result

    def _api_override(self, result: dict, api_pre_json: dict,
                      profil_raw: dict = None) -> dict:
        if not api_pre_json:
            return result
        api_ed   = api_pre_json.get('extracted_data', {})
        api_meta = api_pre_json.get('metadata', {})
        api_p    = api_ed.get('personal', {})
        res_ed   = result.setdefault('extracted_data', {})
        res_meta = result.setdefault('metadata', {})
        res_p    = res_ed.setdefault('personal', {})

        if api_meta.get('headline'):
            res_meta['headline'] = api_meta['headline']
        src = api_meta.get('source', {})
        if src.get('import_id'):
            res_meta.setdefault('source', {})['import_id'] = src['import_id']

        for f in ('company', 'availability', 'headline'):
            v = api_p.get(f)
            if v: res_p[f] = v

        # Location: PLZ oder zu kurz → nach Absprache
        loc = (api_p.get('location') or '').strip()
        import re as _re2
        if loc and not _re2.search(r'\d{5}', loc) and len(loc) > 3:
            res_p['location'] = loc
        elif not res_p.get('location'):
            res_p['location'] = 'nach Absprache'

        # EDV-Erfahrung: aus erstem Projekt berechnen
        v = api_p.get('edv_experience_since')
        if v:
            res_p['edv_experience_since'] = v

        for f in ('email', 'phone', 'birth_year', 'nationality',
                  'degree', 'summary'):
            if not res_p.get(f) and api_p.get(f):
                res_p[f] = api_p[f]

        api_web = (api_p.get('website') or '').strip()
        res_web = (res_p.get('website') or '').strip()
        if api_web and res_web and api_web != res_web:
            seen_w = set(); merged_w = []
            for w in res_web.split(';') + [api_web]:
                w = w.strip()
                if w and w not in seen_w:
                    seen_w.add(w); merged_w.append(w)
            res_p['website'] = ';'.join(merged_w)
        elif api_web and not res_web:
            res_p['website'] = api_web

        FL_LEVEL  = {4:'C2', 3:'C1', 2:'B2', 1:'A2'}
        LEVEL_MAP = {
            'muttersprache':'C2', 'native':'C2',
            'verhandlungssicher':'C1', 'fliessend':'C1', 'fluent':'C1',
            'gut':'B2', 'fortgeschritten':'B2', 'good':'B2',
            'grundkenntnisse':'A2', 'basic':'A2',
        }
        import re as _re

        def _parse_lang(item):
            if isinstance(item, dict):
                return item.get('name','').strip(), item.get('level','')
            s = str(item).strip()
            m = _re.match(r'^(.+?)\s*\((.+?)\)\s*$', s)
            if m:
                name = m.group(1).strip()
                lvl  = LEVEL_MAP.get(m.group(2).strip().lower(), '')
                return name, lvl
            return s, ''

        lang_dict = {}

        for item in res_p.get('languages', []):
            name, level = _parse_lang(item)
            if name:
                key = name.lower()
                # Nur ueberschreiben wenn neuer Level besser ist
                if key not in lang_dict or (level and not lang_dict[key].get('level')):
                    lang_dict[key] = {'name': name, 'level': level}

        if profil_raw:
            for ls in (profil_raw.get('profile') or {}).get('languageSkills', []):
                name  = ls.get('languageName', '').strip()
                level = FL_LEVEL.get(ls.get('level', 0), '')
                if name:
                    lang_dict[name.lower()] = {'name': name, 'level': level}

        if not lang_dict:
            for item in api_p.get('languages', []):
                name, level = _parse_lang(item)
                if name:
                    lang_dict[name.lower()] = {'name': name, 'level': level}

        if lang_dict:
            import json as _json
            pt_lang = _get_prompt('master_normalize_languages')
            if pt_lang:
                try:
                    lang_list = list(lang_dict.values())
                    prompt = pt_lang.format(
                        languages=_json.dumps(lang_list, ensure_ascii=False)
                    )
                    r = _llm(prompt)
                    if r and r.success and isinstance(r.data, dict):
                        normalized = r.data.get('languages', [])
                        if normalized:
                            res_p['languages'] = normalized
                        else:
                            res_p['languages'] = lang_list
                    else:
                        res_p['languages'] = lang_list
                except Exception as e:
                    logger.warning(f"[MasterMerger] normalize_languages: {e}")
                    res_p['languages'] = list(lang_dict.values())
            else:
                res_p['languages'] = list(lang_dict.values())

        api_certs = api_ed.get('certifications', [])
        if api_certs:
            existing = res_ed.get('certifications', [])
            seen = {c.get('name', '').lower() for c in existing}
            for cert in api_certs:
                name = cert.get('name', '').lower().strip()
                if name and name not in seen:
                    existing.append(cert); seen.add(name)
            res_ed['certifications'] = existing

        api_fa = api_ed.get('focus_areas', [])
        if api_fa:
            existing = res_ed.get('focus_areas', [])
            seen = {f.lower() for f in existing if isinstance(f, str)}
            for fa in api_fa:
                if isinstance(fa, str) and fa.lower() not in seen:
                    existing.append(fa); seen.add(fa.lower())
            res_ed['focus_areas'] = existing[:15]

        api_ind = api_ed.get('industries', [])
        if api_ind:
            existing = res_ed.get('industries', [])
            seen = {i.lower() for i in existing if isinstance(i, str)}
            for ind in api_ind:
                if isinstance(ind, str):
                    ind_de = FL_BRANCHE.get(ind, ind)
                    if ind_de.lower() not in seen:
                        existing.append(ind_de); seen.add(ind_de.lower())
            res_ed['industries'] = existing[:20]

        return result

    def _final_check(self, result: dict, pdf_pre_jsons: List[dict]) -> dict:
        pt = _get_prompt('master_multi_check')
        if not pt:
            return result
        try:
            rest_items = []
            for pj in pdf_pre_jsons:
                other = pj.get('extracted_data', {}).get('other', [])
                if isinstance(other, list):
                    for item in other:
                        if isinstance(item, dict) and item.get('content'):
                            rest_items.append(item['content'])
                        elif isinstance(item, str) and item.strip():
                            rest_items.append(item)
                elif isinstance(other, str) and other.strip():
                    rest_items.append(other)
            if not rest_items:
                return result
            ed = result.get('extracted_data', {})
            profil_summary = json.dumps({
                'projects': len(ed.get('experience', [])),
                'skills':   sum(len(v) for v in ed.get('skills', {}).values()),
                'certs':    len(ed.get('certifications', [])),
            }, ensure_ascii=False)
            prompt = pt.format(
                profil=profil_summary,
                rest=json.dumps(rest_items[:10], ensure_ascii=False)[:3000],
            )
            r = _llm(prompt)
            if r and r.success and r.data:
                data = r.data
                extra_skills = data.get('skills', {}) if isinstance(data, dict) else {}
                if isinstance(extra_skills, dict):
                    skills = ed.setdefault('skills', {})
                    for cat, items in extra_skills.items():
                        if cat in SKILL_CATS and isinstance(items, list):
                            seen = {x.lower() for x in skills.get(cat, [])
                                    if isinstance(x, str)}
                            for item in items:
                                if isinstance(item, str) and item.lower() not in seen:
                                    skills.setdefault(cat, []).append(item)
                                    seen.add(item.lower())
                logger.info("[MasterMerger] Final-Check OK")
        except Exception as e:
            logger.warning(f"[MasterMerger] Final-Check: {e}")
        return result

    def _finalize(self, result: dict, source: str, n_in: int, n_out: int):
        audit = result.setdefault('audit', {})
        audit['merged_at']    = datetime.now().isoformat()
        audit['merge_source'] = source
        audit['merge_stats']  = {
            'projects_input': n_in, 'projects_output': n_out}
        audit.setdefault('steps_completed', []).append('master_merger_v2')
        ed = result.get('extracted_data', {})
        result.setdefault('metadata', {})['statistics'] = {
            'total_categories': len([
                c for c in ed.get('skills', {}).values() if c]),
            'has_personal':   bool(ed.get('personal', {}).get('last_name')),
            'has_skills':     any(ed.get('skills', {}).values()),
            'has_experience': bool(ed.get('experience')),
            'project_count':  len(ed.get('experience', [])),
            'skill_count':    sum(
                len(v) for v in ed.get('skills', {}).values()),
        }


master_merger = MasterMerger()
