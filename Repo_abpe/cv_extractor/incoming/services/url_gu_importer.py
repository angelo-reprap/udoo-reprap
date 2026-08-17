"""
url_gu_importer.py — GULP Talentfinder Importer
API: /api/secure/expert-profiles/{hash-id}
"""
import glob
import json
import logging
import re
import time
from datetime import datetime
from pathlib import Path

import requests
import warnings
warnings.filterwarnings('ignore')

logger = logging.getLogger(__name__)
BASE_DIR = Path('data/url/gu')


class GULPImporter:

    def run(self, url: str, cookies: dict = None, **kwargs) -> dict:
        start = time.time()
        self._log(f"START: {url}")

        # 1. Hash-ID + evtl. Name aus URL/gulpId ermitteln
        hash_id, api_first, api_last, gulp_id = self._extract_hash(url)
        if not hash_id:
            return {'error': f'Keine gültige GULP Hash-ID in URL: {url}'}

        # 2. Session-Cookies laden
        if not cookies:
            cookies = self._load_cookies()
        if not cookies:
            return {'error': 'Keine GULP Session-Cookies — bitte einloggen'}

        # 3. API-Call
        self._log("API-Call...")
        profile_data = self._fetch_profile(hash_id, cookies)
        if 'error' in profile_data:
            return profile_data

        # 4. Name ermitteln (4-stufig)
        expert   = profile_data.get('expert', {})
        personal = expert.get('personalData', {})
        pf = personal.get('firstName', '') or api_first or ''
        pl = personal.get('lastName',  '') or api_last  or ''
        gulp_id  = gulp_id or expert.get('mId', '')

        first, last, name_status = self._resolve_name(gulp_id, hash_id, pf, pl)

        # force_dir/first_name/last_name vom Frontend (nach Popup-Bestätigung)
        force_dir   = kwargs.get('force_dir', '')
        force_first = kwargs.get('first_name', '')
        force_last  = kwargs.get('last_name', '')

        if force_first and force_last:
            # User hat Namen eingetragen → direkt verwenden
            first, last, name_status = force_first, force_last, 'real'
        elif force_dir and name_status in ('not_found', 'provisional'):
            # User hat "Ohne Namen" gewählt → provisional_dir als Namen verwenden
            parts = force_dir.split('_gulpId-')
            first = f'GULP-{parts[1]}' if len(parts) == 2 else 'GULP'
            last  = parts[0]
            name_status = 'provisional'

        if name_status in ('not_found', 'provisional') and not force_dir:
            # Kein echter Name gefunden → Popup im Frontend
            provisional_dir = f"{hash_id}"
            if gulp_id:
                provisional_dir = f"{hash_id}_gulpId-{gulp_id}"
            return {
                'name_missing':    True,
                'hash_id':         hash_id,
                'gulp_id':         gulp_id or '',
                'provisional_dir': provisional_dir,
                'url':             url,
            }

        dir_name = force_dir if force_dir else self._make_dir_name(first, last, name_status)
        base     = BASE_DIR / dir_name
        dl_dir   = base / 'download'
        ex_dir   = base / 'extract'
        an_dir   = base / 'analysis'
        for d in [base, dl_dir, ex_dir, an_dir]:
            d.mkdir(parents=True, exist_ok=True)

        # 5. profil.json speichern
        profile_path = base / 'profil.json'
        with open(profile_path, 'w', encoding='utf-8') as f:
            json.dump({
                'url': url, 'hash_id': hash_id,
                'gulp_id': gulp_id,
                'fetched_at': datetime.now().isoformat(),
                'data': profile_data,
            }, f, indent=2, ensure_ascii=False)
        self._log(f"profil.json gespeichert: {profile_path}")

        # 6. PDF herunterladen
        pdf_path = self._download_pdf(hash_id, cookies, dl_dir)

        # 7. PDF Text extrahieren
        if pdf_path:
            self._extract_pdf(pdf_path, ex_dir)

        # 8. pre_json bauen
        pre_json = self._build_pre_json(profile_data, url, hash_id, dir_name, first, last)
        pre_json_path = base / 'profil_pre_json.json'
        with open(pre_json_path, 'w', encoding='utf-8') as f:
            json.dump(pre_json, f, indent=2, ensure_ascii=False)
        self._log("profil_pre_json.json gespeichert")

        duration = round(time.time() - start, 2)
        self._log(f"DONE in {duration}s")

        return {
            'status':    'ok',
            'name':      f"{first} {last}",
            'dir':       str(base),
            'downloaded': 1 if pdf_path else 0,
            'extracted':  1 if pdf_path else 0,
            'keywords':   len(pre_json.get('extracted_data', {}).get('skills', {}).get('special_concept', [])),
            'duration':   duration,
            'pre_json_path': str(pre_json_path),
        }

    def _extract_hash(self, url: str) -> tuple:
        """Gibt (hash_id, first, last, gulp_id) zurück."""
        # Direkte Hash-ID aus URL
        m = re.search(r'/experten/([a-f0-9]{24})', url)
        if m:
            return m.group(1), None, None, None
        # gulpId in URL
        m = re.search(r'gulpId=(\d+)', url)
        if m:
            h, f, l = self._resolve_gulp_id(m.group(1))
            return h, f, l, m.group(1)
        # Reine Zahl = gulpId
        if re.match(r'^\d+$', url.strip()):
            h, f, l = self._resolve_gulp_id(url.strip())
            return h, f, l, url.strip()
        return None, None, None, None

    def _resolve_gulp_id(self, gulp_id: str) -> tuple:
        """Gibt (hash_id, first_name, last_name) zurück."""
        cookies = self._load_cookies()
        if not cookies:
            return None, None, None
        session = requests.Session()
        session.verify = False
        for k, v in cookies.items():
            session.cookies.set(k, v, domain='www.gulp.de')
        headers = {
            'accept': 'application/json',
            'content-type': 'application/json',
            'direkt-language': 'de',
            'x-requested-with': 'XMLHttpRequest',
            'x-xsrf-token': cookies.get('XSRF-TOKEN', ''),
            'user-agent': 'Mozilla/5.0',
        }
        try:
            r = session.post(
                'https://www.gulp.de/talentfinder/app/api/secure/expert-profiles/search?pageIndex=0&pageSize=5',
                headers=headers,
                json={"mId": gulp_id, "sortOrder": "UPDATED_DATE",
                      "availabilityPercent": 20, "remote": False,
                      "searchOnlyInRecentProjects": False, "searchTerm": None},
                timeout=30
            )
            if r.status_code == 200:
                objects = r.json().get('objects', [])
                if objects:
                    obj      = objects[0]
                    hash_id  = obj.get('profile', {}).get('id')
                    personal = obj.get('expert', {}).get('personalData', {})
                    first    = personal.get('firstName', '')
                    last     = personal.get('lastName', '')
                    self._log(f"gulpId {gulp_id} → Hash-ID: {hash_id}, Name: {first} {last}")
                    return hash_id, first, last
        except Exception as e:
            self._log(f"gulpId-Auflösung Fehler: {e}")
        return None, None, None

    def _resolve_name(self, gulp_id: str, hash_id: str,
                      api_first: str, api_last: str) -> tuple:
        """
        Gibt (first, last, status) zurück.
        Stufe 1/2: GULP API
        Stufe 3:   Namazu-Index
        Stufe 4a:  provisorisch hashid_GULP-gulpid
        Stufe 4b:  not_found
        """
        # Stufe 1+2: API
        if api_first and api_last:
            self._log(f"Name Stufe 1/2 (API): {api_first} {api_last}")
            return api_first, api_last, 'real'

        # Stufe 3: Namazu
        if gulp_id:
            search = f'gulpId={gulp_id}'
            for filepath in glob.glob('/var/www/namazu/index/*.html'):
                try:
                    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                        if search in f.read():
                            parts = filepath.split('/')[-1].replace('.html','').split('__')
                            if len(parts) >= 2:
                                self._log(f"Name Stufe 3 (Namazu): {parts[1]} {parts[0]}")
                                return parts[1], parts[0], 'real'
                except: continue

        # Stufe 4a: provisorisch
        if hash_id:
            first = f'GULP-{gulp_id}' if gulp_id else 'GULP'
            last  = hash_id
            self._log(f"Name Stufe 4a (provisorisch): {last}_{first}")
            return first, last, 'provisional'

        # Stufe 4b
        return None, None, 'not_found'

    def _make_dir_name(self, first: str, last: str, status: str) -> str:
        if status == 'provisional':
            return f"{last}_{first}"
        return f"{last.lower()}_{first.lower()}"

    def _load_cookies(self) -> dict:
        cookie_file = Path('data/url/gu/.session_cookies.json')
        if not cookie_file.exists():
            return {}
        try:
            saved = json.loads(cookie_file.read_text())
            cookies = {c['name']: c['value'] for c in saved.get('cookies', [])}
            self._log(f"Session-Cookies geladen: {list(cookies.keys())}")
            return cookies
        except Exception as e:
            self._log(f"Cookie-Fehler: {e}")
            return {}

    def _fetch_profile(self, hash_id: str, cookies: dict) -> dict:
        session = requests.Session()
        session.verify = False
        for k, v in cookies.items():
            session.cookies.set(k, v, domain='www.gulp.de')
        headers = {
            'accept': 'application/json, text/plain, */*',
            'direkt-language': 'de',
            'x-requested-with': 'XMLHttpRequest',
            'user-agent': 'Mozilla/5.0',
        }
        try:
            r = session.get(
                f'https://www.gulp.de/talentfinder/app/api/secure/expert-profiles/{hash_id}',
                headers=headers, timeout=30
            )
            if r.status_code == 401:
                return {'error': 'GULP Session abgelaufen — bitte neu einloggen'}
            if r.status_code != 200:
                return {'error': f'GULP API Status: {r.status_code}'}
            return r.json()
        except Exception as e:
            return {'error': f'GULP API Fehler: {e}'}

    def _download_pdf(self, hash_id: str, cookies: dict, dl_dir: Path) -> Path:
        session = requests.Session()
        session.verify = False
        for k, v in cookies.items():
            session.cookies.set(k, v, domain='www.gulp.de')
        headers = {
            'accept': 'application/json, text/plain, */*',
            'direkt-language': 'de',
            'x-requested-with': 'XMLHttpRequest',
            'user-agent': 'Mozilla/5.0',
        }
        try:
            r = session.get(
                f'https://www.gulp.de/talentfinder/app/api/secure/expert-profiles/{hash_id}/PDF',
                headers=headers, timeout=30
            )
            if r.status_code == 200 and 'pdf' in r.headers.get('content-type', ''):
                path = dl_dir / '01_profil.pdf'
                path.write_bytes(r.content)
                self._log(f"PDF gespeichert: {path} ({len(r.content)//1024} KB)")
                return path
        except Exception as e:
            self._log(f"PDF Download Fehler: {e}")
        return None

    def _extract_pdf(self, pdf_path: Path, ex_dir: Path):
        try:
            from .pdf_extractor import PDFExtractor
            result  = PDFExtractor().extract(str(pdf_path))
            yx_path = ex_dir / (pdf_path.stem + '_yx.txt')
            spans   = result.spans if hasattr(result, 'spans') else []
            import re
            PUA_RE = re.compile(r'[\ue000-\uf8ff]')
            with open(yx_path, 'w', encoding='utf-8') as f:
                for s in spans:
                    s_text = PUA_RE.sub('', s.text).strip()
                    line = str(s).replace(s.text, s_text)
                    f.write(line + '\n')
            self._log(f"yx.txt: {len(spans)} Spans")
        except Exception as e:
            self._log(f"PDF Extraktion Fehler: {e}")

    def _build_pre_json(self, data: dict, url: str, hash_id: str,
                        dir_name: str, first: str, last: str) -> dict:
        from bs4 import BeautifulSoup

        def html2text(html):
            if not html: return ''
            return BeautifulSoup(html, 'html.parser').get_text(' ').strip()

        p = data.get('profile', {})
        e = data.get('expert', {})

        GULP_TO_ABPE = {
            'PROGRAMMING_LANGUAGES':    'programming_languages',
            'OPERATING_SYSTEM':         'operating_system',
            'DATABASE':                 'database',
            'DATA_COMMUNICATION':       'network_protocol',
            'PRODUCTS_STANDARDS_EXP':   'business_software',
            'COMPUTER_AIDED_DESIGN':    'architecture_pattern',
            'MANAGERIAL_EXPERIENCE':    'methodology',
            'PERSONNEL_RESPONSIBILITY': 'soft_skill',
        }
        skills = {k: [] for k in [
            'architecture_pattern','business_software','ci_cd_tool','cloud_platform',
            'communication_tool','database','data_format','data_management',
            'development_environment','devops_tool','documentation_tool','framework',
            'hardware','identity_management','it_infrastructure','methodology',
            'monitoring_tool','network_protocol','operating_system','programming_languages',
            'project_management','security_tool','soft_skill','special_concept',
            'testing_tool','version_control','virtualization'
        ]}
        for cat in p.get('competenceCategories', []):
            key = GULP_TO_ABPE.get(cat['id'])
            if key:
                skills[key] = [c['name'] for c in cat.get('competences', [])]
        skills['special_concept'] = p.get('topSkills', []) + p.get('additionalSkills', [])

        return {
            "_comment": f"GULP Import {first} {last} am {datetime.now().strftime('%Y-%m-%d')}",
            "metadata": {
                "aid": "", "version": "1.0.0.0",
                "consultant_dir": dir_name,
                "first_name": first,
                "last_name":  last,
                "headline":   p.get('coreCompetence',''),
                "source": {
                    "type": "url_import", "platform": "gulp",
                    "filename": url, "filesize": 0,
                    "import_id": e.get('mId',''),
                    "import_date": datetime.now().isoformat(),
                },
                "pipeline": {"version":"5.0","step":"url_import",
                             "extractor":"gulp_importer","model":"direct_api",
                             "self_learning":True},
                "duplicate_check": {"exists":False,"message":""},
                "statistics": {
                    "total_categories": len([v for v in skills.values() if v]),
                    "has_personal":True,"has_skills":True,"has_experience":True
                }
            },
            "extracted_data": {
                "personal": {
                    "first_name":   first,
                    "last_name":    last,
                    "birth_year":   None, "nationality": "",
                    "languages":    [f"{l['name']} ({l.get('comment','')})"
                                     for l in p.get('foreignLanguageSkills',[])],
                    "email":        e.get('contactData',{}).get('email',''),
                    "phone":        (e.get('contactData',{}).get('mobileNumber','') or
                                     e.get('contactData',{}).get('telephoneNumber','')),
                    "location":     f"{e.get('address',{}).get('city','')} "
                                    f"{e.get('address',{}).get('zipcode','')}".strip(),
                    "availability": p.get('availableFrom',''),
                    "degree": "", "edv_experience_since": None,
                    "headline": p.get('coreCompetence',''), "summary": "",
                },
                "professional": {"total_experience_years": 0},
                "skills": skills,
                "certifications": self._parse_education_text(p.get('educationText','')).get('certs',[]),
                "experience": [
                    {
                        "period":       f"{proj.get('from','')} – {proj.get('to','')}",
                        "title":        proj.get('title',''),
                        "company":      proj.get('customerName',''),
                        "industry":     proj.get('industry',''),
                        "role":         proj.get('role',''),
                        "location":     proj.get('location',''),
                        "activities":   [html2text(proj.get('tasks',''))],
                        "technologies": proj.get('skills',[]) + proj.get('tools',[])
                    }
                    for proj in p.get('projects',[])
                ],
                "industries":       self._parse_industries(p.get('industries','')),
                "focus_areas":      [],
                "focus_experience": ([p.get('coreCompetence','')] if p.get('coreCompetence') else []) + self._parse_education_text(p.get('educationText','')).get('focus',[]),
                "education": [
                    {
                        "degree":         edu.get('degree',''),
                        "institution":    edu.get('institution',''),
                        "period":         f"{edu.get('from','')} – {edu.get('to','')}",
                        "description":    html2text(edu.get('description','')),
                        "education_type": "degree", "issuer": ""
                    }
                    for edu in p.get('education',[])
                ] + [
                    {
                        "degree":         c['name'],
                        "institution":    '',
                        "period":         '',
                        "description":    '',
                        "education_type": 'course',
                        "issuer":         ''
                    }
                    for c in self._parse_education_text(p.get('educationText','')).get('courses',[])
                    if c.get('name')
                ],
                "other": ""
            },
            "audit": {
                "created_by": "gulp_importer",
                "created_at": datetime.now().isoformat(),
                "source_file": url,
                "steps_completed": ["url_fetch","api_call","pdf_download","mapping"]
            }
        }

    def _log(self, msg: str):
        logger.info(f"[GULPImporter] {msg}")

    def _parse_industries(self, val) -> list:
        """HTML-String oder Liste → saubere Python-Liste ohne PUA-Zeichen."""
        import re
        PUA_RE = re.compile(r'[-□☐☑☒]')

        def _clean(s):
            return PUA_RE.sub('', str(s)).strip()

        if not val:
            return []
        if isinstance(val, list):
            return [_clean(v) for v in val if _clean(v)]
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(str(val), 'html.parser')
            items = [_clean(li.get_text(' ', strip=True))
                     for li in soup.find_all('li')
                     if _clean(li.get_text(' ', strip=True))]
            if items:
                return items
            return [_clean(x) for x in soup.get_text(',').split(',') if _clean(x)]
        except Exception as e:
            self._log(f"_parse_industries Fehler: {e}")
            return []

    def _parse_education_text(self, html: str) -> dict:
        """
        Parst GULP educationText — zwei Muster:
        A) <ul>/<li> mit <u>Abschnitts-Titeln</u>  (Oliver Glas)
        B) <div>/<u>Datum</u> dann <div>Inhalt</div> (Thomas Troschke)
        Gibt: {certs, courses, degrees, focus}
        """
        import re as _re
        result = {'certs': [], 'courses': [], 'degrees': [], 'focus': []}
        if not html:
            return result
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, 'html.parser')

            CERT_KW   = {'zertifikate','zertifizierungen','certifications',
                         'zertifikat','certification','zertifizierungen/ schulungen'}
            COURSE_KW = {'schulungen','kurse','weiterbildungen',
                         'private weiterbildungen','training'}
            DEGREE_KW = {'ausbildung','studium','grundausbildung'}
            FOCUS_KW  = {'schwerpunkte','schwerpunkt','fachliche schwerpunkte'}
            DATE_RE   = _re.compile(r'^\d{1,2}[./]\d{4}$|^\d{4}\s*[-–]\s*\d{4}$')
            LEHRGANG  = _re.compile(r'^(lehrgang|kurs|schulung)\s+', _re.I)

            # Muster A: strukturiert mit <ul>
            if soup.find('ul'):
                current = None
                for tag in soup.children:
                    name = getattr(tag, 'name', None)
                    if not name:
                        continue
                    text = tag.get_text(' ', strip=True)
                    changed = False
                    for u in (tag.find_all('u') if name != 'u' else [tag]):
                        ut = u.get_text(' ', strip=True).lower().rstrip(':').strip()
                        if ut in CERT_KW:   current = 'cert';   changed = True; break
                        elif ut in COURSE_KW: current = 'course'; changed = True; break
                        elif ut in DEGREE_KW: current = 'degree'; changed = True; break
                        elif ut in FOCUS_KW:  current = 'focus';  changed = True; break
                    if changed:
                        continue
                    if name == 'ul' and current:
                        for li in tag.find_all('li'):
                            item = li.get_text(' ', strip=True).replace('\u25a1','').replace('\u2610','').replace('\u2611','').strip()
                            if not item or len(item) < 2:
                                continue
                            if current == 'cert':
                                issuer, n = (item.split(':',1)[0].strip(), item.split(':',1)[1].strip()) if ':' in item else ('', item)
                                if n: result['certs'].append({'name':n,'issuer':issuer,'date_obtained':'','expiry_date':''})
                            elif current == 'course':
                                result['courses'].append({'name':item,'education_type':'course','institution':'','period':''})
                            elif current == 'degree':
                                result['degrees'].append({'degree':item,'institution':'','period':'','description':'','education_type':'degree','issuer':''})
                    elif name == 'p' and current == 'focus' and text and len(text) > 3:
                        result['focus'].append(text)

            # Muster B: Datum-gelabelt mit <div>
            divs = [t for t in soup.children if getattr(t, 'name', None) == 'div']
            if len(divs) >= 4:
                in_cert = False
                cur_date = ''
                for div in divs:
                    text = div.get_text(' ', strip=True)
                    if not text:
                        continue
                    underlined = bool(div.find_all(['u','span']))
                    if underlined:
                        tl = text.lower().strip()
                        if any(k in tl for k in ['zertif','schulung','weiterbildung']):
                            in_cert = True; cur_date = ''; continue
                        if DATE_RE.match(text.strip()) or _re.match(r'^\d{4}', text.strip()):
                            cur_date = text.strip(); continue
                        in_cert = False; cur_date = ''
                    else:
                        if len(text) < 2:
                            continue
                        if in_cert:
                            if LEHRGANG.match(text):
                                result['courses'].append({'name':LEHRGANG.sub('',text).strip(),'education_type':'course','institution':'','period':cur_date})
                            else:
                                result['certs'].append({'name':text,'issuer':'','date_obtained':cur_date,'expiry_date':''})
                        elif cur_date or any(k in text.lower() for k in ['studium','ausbildung','abschluss','dipl']):
                            result['degrees'].append({'degree':text,'institution':'','period':cur_date,'description':'','education_type':'degree','issuer':''})
                        cur_date = ''

        except Exception as e:
            self._log(f"_parse_education_text Fehler: {e}")
        self._log(f"educationText: {len(result['certs'])} Zert, {len(result['courses'])} Schulungen, {len(result['degrees'])} Abschlüsse")
        return result

