#!/usr/bin/env python3
"""Live-Patch: Email Studio kann PDF-Anhänge senden.

Idempotent. Backup neben der Datei.
  - EmailSender.send(..., attachments=[{filename, path|content}])
  - EmailStudio.send(..., attachments=...)
  - Bei template cv_generated_berater: PDF aus Variablen / lokalem Pfad zu cv_link

ucs5 (nach fetch):
  python3 scripts/live_patch_email_studio_attachments.py
oder über SAFE-cv-generated-berater.sh
"""
from __future__ import annotations

import re
import shutil
from datetime import datetime
from pathlib import Path

ROOT = Path("/opt/abpe/backend/apps/abpe_email_studio")
SENDER = ROOT / "services" / "sender.py"
API = ROOT / "api.py"
TS = datetime.now().strftime("%Y%m%d-%H%M%S")
MARKER = "ABPE_CV_PDF_ATTACH"


HELPER = r'''
def _abpe_collect_cv_pdfs(variables: dict) -> list:
    """Lokale PDF-Pfade aus Variablen — kein HTTP, kein WAN→LAN."""
    from pathlib import Path
    from urllib.parse import urlparse
    variables = variables or {}
    cands = []
    for key in ("cv_pdf_path", "pdf_path", "cv_file", "cv_pdf", "attachment_path"):
        val = variables.get(key)
        if val:
            cands.append(str(val))
    link = str(variables.get("cv_link") or "").strip()
    if link.startswith("/") and not link.startswith("//"):
        cands.append(link)
    if link.startswith("http://") or link.startswith("https://"):
        path = urlparse(link).path or ""
        if path:
            try:
                from django.conf import settings
                media = getattr(settings, "MEDIA_ROOT", "") or ""
            except Exception:
                media = ""
            if media:
                cands.append(str(Path(media) / path.lstrip("/")))
            cands.append("/opt/abpe/backend" + path)
            cands.append("/opt/abpe" + path)
            cands.append(path)
    out = []
    seen = set()
    for raw in cands:
        p = Path(raw)
        if not p.is_file():
            continue
        key = str(p.resolve())
        if key in seen:
            continue
        seen.add(key)
        out.append({"filename": p.name, "path": str(p)})
    return out


def _abpe_attach_files(outer_msg, attachments: list):
    from email.mime.application import MIMEApplication
    from pathlib import Path
    n = 0
    for att in attachments or []:
        filename = (att.get("filename") or "profil.pdf").strip() or "profil.pdf"
        content = att.get("content")
        if content is None and att.get("path"):
            p = Path(att["path"])
            if p.is_file():
                content = p.read_bytes()
        if not content:
            continue
        part = MIMEApplication(content, _subtype="pdf" if filename.lower().endswith(".pdf") else "octet-stream")
        part.add_header("Content-Disposition", "attachment", filename=filename)
        outer_msg.attach(part)
        n += 1
    return n
'''


def _backup(path: Path) -> Path:
    bak = path.with_name(path.name + f".bak-cvattach-{TS}")
    shutil.copy2(path, bak)
    print("BACKUP", bak)
    return bak


def patch_sender(src: str) -> str:
    if MARKER in src:
        print("sender.py: Patch schon drin")
        return src
    if "attachments" in src and "MIMEApplication" in src:
        print("sender.py: attachments scheinen schon zu existieren")
        return src

    src = src.rstrip() + "\n\n# " + MARKER + "\n" + HELPER + "\n"

    # Signatur: attachments-Parameter
    old_sig = (
        "    def send(self, template, to_emails: list, variables: dict = None,\n"
        "             user=None, cc_extra: list = None, bcc_extra: list = None,\n"
        "             task_reference: str = '', app_reference: str = '') -> dict:"
    )
    new_sig = (
        "    def send(self, template, to_emails: list, variables: dict = None,\n"
        "             user=None, cc_extra: list = None, bcc_extra: list = None,\n"
        "             task_reference: str = '', app_reference: str = '',\n"
        "             attachments: list = None) -> dict:"
    )
    if old_sig not in src:
        # einzeilige / leicht andere Variante
        src2, n = re.subn(
            r"(def send\(self, template, to_emails: list, variables: dict = None,)",
            r"\1 attachments: list = None,",
            src,
            count=1,
        )
        if n != 1:
            raise SystemExit("FAIL: sender.py Signatur nicht erkannt — nicht gepatcht")
        src = src2
        print("sender.py: attachments-Param (regex)")
    else:
        src = src.replace(old_sig, new_sig, 1)
        print("sender.py: attachments-Param")

    needle = "            msg.attach(MIMEText(html_body, 'html', 'utf-8'))"
    insert = needle + """

            # """ + MARKER + """
            _atts = list(attachments or [])
            try:
                _ident = getattr(template, "identifier", "") or ""
            except Exception:
                _ident = ""
            if _ident == "cv_generated_berater" and not _atts:
                _atts = _abpe_collect_cv_pdfs(variables)
            if _atts:
                from email.mime.multipart import MIMEMultipart as _MM
                _mixed = _MM("mixed")
                _mixed["Subject"] = msg["Subject"]
                _mixed["From"] = msg["From"]
                _mixed["To"] = msg["To"]
                if msg.get("Cc"):
                    _mixed["Cc"] = msg["Cc"]
                if msg.get("Reply-To"):
                    _mixed["Reply-To"] = msg["Reply-To"]
                for _h in ("X-Auto-Response-Suppress", "Auto-Submitted"):
                    if msg.get(_h):
                        _mixed[_h] = msg[_h]
                _mixed.attach(msg)
                _n = _abpe_attach_files(_mixed, _atts)
                msg = _mixed
                log.info("Anhänge: %s Datei(en) an %s", _n, _ident or "mail")
"""
    if needle not in src:
        raise SystemExit("FAIL: sender.py attach-Stelle nicht gefunden")
    src = src.replace(needle, insert, 1)
    print("sender.py: PDF-Attach-Block")
    return src


def patch_api(src: str) -> str:
    if MARKER in src:
        print("api.py: Patch schon drin")
        return src

    old = (
        "    def send(template: str, recipient: str | list,\n"
        "             variables: dict = None, user=None,\n"
        "             cc: list = None, bcc: list = None,\n"
        "             task_reference: str = '', app_reference: str = '',\n"
        "             async_send: bool = False,\n"
        "             lang: str = 'de') -> dict:"
    )
    new = (
        "    def send(template: str, recipient: str | list,\n"
        "             variables: dict = None, user=None,\n"
        "             cc: list = None, bcc: list = None,\n"
        "             task_reference: str = '', app_reference: str = '',\n"
        "             async_send: bool = False,\n"
        "             lang: str = 'de',\n"
        "             attachments: list = None) -> dict:"
    )
    if old in src:
        src = src.replace(old, new, 1)
        print("api.py: attachments-Param")
    else:
        src2, n = re.subn(
            r"(def send\(template: str, recipient: str \| list,)",
            r"\1 attachments: list = None,",
            src,
            count=1,
        )
        if n != 1:
            print("WARN: api.py Signatur nicht erkannt — Sender-Patch reicht für direkten EmailSender")
            return src
        src = src2
        print("api.py: attachments-Param (regex)")

    # durchreichen an sender.send
    call = """        return sender.send(
            template       = tpl,
            to_emails      = to_emails,
            variables      = variables,
            user           = user,
            cc_extra       = cc or [],
            bcc_extra      = bcc or [],
            task_reference = task_reference,
            app_reference  = app_reference,
        )"""
    call_new = """        if not attachments and (template == "cv_generated_berater"):
            try:
                from apps.abpe_email_studio.services.sender import _abpe_collect_cv_pdfs
                attachments = _abpe_collect_cv_pdfs(variables or {})
            except Exception:
                attachments = attachments or []
        return sender.send(
            template       = tpl,
            to_emails      = to_emails,
            variables      = variables,
            user           = user,
            cc_extra       = cc or [],
            bcc_extra      = bcc or [],
            task_reference = task_reference,
            app_reference  = app_reference,
            attachments    = attachments,
        )"""
    if call in src:
        src = src.replace(call, call_new, 1)
        print("api.py: attachments durchgereicht")
    else:
        print("WARN: api.py sender.send-Aufruf weicht ab — Param ist gesetzt, Aufruf prüfen")
    src = src.rstrip() + f"\n\n# {MARKER}\n"
    return src


def grep_callers():
    apps = Path("/opt/abpe/backend/apps")
    print("=== Aufrufer cv_generated_berater ===")
    if not apps.is_dir():
        print("SKIP: ", apps)
        return
    hits = 0
    for p in apps.rglob("*.py"):
        if "email_studio" in str(p):
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        if "cv_generated_berater" not in text:
            continue
        hits += 1
        print("---", p)
        for i, line in enumerate(text.splitlines(), 1):
            if "cv_generated_berater" in line or "EmailStudio.send" in line:
                print(f"{i:5} {line.rstrip()}")
    if not hits:
        print("(keine Treffer außerhalb email_studio)")


def main():
    if not SENDER.is_file():
        raise SystemExit(f"FAIL: {SENDER} fehlt")
    _backup(SENDER)
    SENDER.write_text(patch_sender(SENDER.read_text(encoding="utf-8")), encoding="utf-8")
    if API.is_file():
        _backup(API)
        API.write_text(patch_api(API.read_text(encoding="utf-8")), encoding="utf-8")
    else:
        print("WARN:", API, "fehlt")
    grep_callers()
    print("OK — live_patch_email_studio_attachments")
    print("Danach: supervisorctl restart abpe-django abpe-celery")


if __name__ == "__main__":
    main()
