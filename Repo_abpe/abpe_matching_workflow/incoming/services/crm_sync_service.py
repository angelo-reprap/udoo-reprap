"""
ABpE Matching Workflow — CRM Sync Service
Synchronisiert ProjectRequest ↔ SuiteCRM opportunities/contacts/emails
"""
import logging
import json
from typing import Dict, Optional
from django.utils import timezone

logger = logging.getLogger(__name__)


def _crm_cfg() -> Dict:
    from pathlib import Path
    try:
        p = Path(__file__).resolve().parent.parent.parent.parent / 'settings.json'
        return json.loads(p.read_text(encoding='utf-8')).get('matching', {}).get('crm_sync', {})
    except Exception:
        return {}


class CRMSyncService:
    """Bidirektionaler Sync zwischen Matching-Workflow und SuiteCRM"""

    def __init__(self):
        self.cfg     = _crm_cfg()
        self.enabled = self.cfg.get('enabled', True)
        self.stage_map = self.cfg.get('opportunity_sales_stage_map', {})

    # ──────────────────────────────────────────────────────
    # PROJEKT SYNC
    # ──────────────────────────────────────────────────────

    def sync_project(self, project) -> Dict:
        """Synchronisiert ein ProjectRequest zu SuiteCRM"""
        if not self.enabled:
            return {'skipped': True, 'reason': 'CRM Sync deaktiviert'}

        try:
            if project.crm_opportunity_id:
                result = self._update_opportunity(project)
            else:
                result = self._create_opportunity(project)

            project.crm_synced_at = timezone.now()
            project.save(update_fields=['crm_synced_at', 'crm_opportunity_id'])

            logger.info(f"CRM Sync OK: {project.project_number} → {project.crm_opportunity_id}")
            return {'success': True, **result}

        except Exception as e:
            logger.error(f"CRM Sync fehlgeschlagen: {project.project_number} — {e}")
            return {'success': False, 'error': str(e)}

    def _create_opportunity(self, project) -> Dict:
        """Legt neue Opportunity in SuiteCRM an"""
        from apps.crm_bridge.connectors.suitecrm_api import SuiteCRMAPI
        api = SuiteCRMAPI()

        sales_stage = self.stage_map.get(project.status, 'Prospecting')

        data = {
            'data': {
                'type': 'Opportunities',
                'attributes': {
                    'name':        f"{project.project_number}: {project.title}",
                    'description': project.description[:500] if project.description else '',
                    'sales_stage': sales_stage,
                    'amount':      str(project.rate_max or 0),
                    'date_closed': project.placed_end.isoformat() if project.placed_end else '2099-12-31',
                }
            }
        }

        response = api._make_request(
            'POST',
            api.endpoints.get('OPPORTUNITIES', '/Api/V8/module/Opportunities'),
            data=data
        )

        if response and 'data' in response:
            opp_id = response['data'].get('id', '')
            project.crm_opportunity_id = opp_id
            return {'created': True, 'opportunity_id': opp_id}

        return {'created': False}

    def _update_opportunity(self, project) -> Dict:
        """Aktualisiert bestehende Opportunity"""
        from apps.crm_bridge.connectors.suitecrm_api import SuiteCRMAPI
        api = SuiteCRMAPI()

        sales_stage = self.stage_map.get(project.status, 'Prospecting')

        data = {
            'data': {
                'type': 'Opportunities',
                'id':   project.crm_opportunity_id,
                'attributes': {
                    'sales_stage': sales_stage,
                    'name': f"{project.project_number}: {project.title}",
                }
            }
        }

        api._make_request(
            'PATCH',
            f"{api.endpoints.get('OPPORTUNITIES', '/Api/V8/module/Opportunities')}/{project.crm_opportunity_id}",
            data=data
        )
        return {'updated': True, 'opportunity_id': project.crm_opportunity_id}

    # ──────────────────────────────────────────────────────
    # PROJECT CONSULTANT SYNC
    # ──────────────────────────────────────────────────────

    def sync_project_consultant(self, pc) -> Dict:
        """Schreibt Status-Änderung als Note in SuiteCRM"""
        if not self.enabled:
            return {'skipped': True}

        try:
            from apps.crm_bridge.connectors.suitecrm_api import SuiteCRMAPI
            api = SuiteCRMAPI()

            note_text = (
                f"Matching Status: {pc.status}\n"
                f"Berater: {pc.consultant_cv.full_name}\n"
                f"Score: {pc.match_score:.2f}\n"
                f"Projekt: {pc.project.project_number}"
            )

            data = {
                'data': {
                    'type': 'Notes',
                    'attributes': {
                        'name':        f"Matching: {pc.consultant_cv.full_name} — {pc.status}",
                        'description': note_text,
                        'parent_type': 'Opportunities',
                        'parent_id':   pc.project.crm_opportunity_id or '',
                    }
                }
            }

            api.create_note(data)
            logger.info(f"CRM Note erstellt: {pc.consultant_cv.full_name} → {pc.status}")
            return {'success': True}

        except Exception as e:
            logger.warning(f"CRM PC Sync fehlgeschlagen: {e}")
            return {'success': False, 'error': str(e)}

    # ──────────────────────────────────────────────────────
    # EMAIL SYNC
    # ──────────────────────────────────────────────────────

    def sync_email(self, email_history) -> Dict:
        """Schreibt versendete E-Mail nach SuiteCRM emails Tabelle"""
        if not self.enabled:
            return {'skipped': True}

        try:
            from apps.crm_bridge.connectors.suitecrm_api import SuiteCRMAPI
            api = SuiteCRMAPI()

            data = {
                'data': {
                    'type': 'Emails',
                    'attributes': {
                        'name':       email_history.subject,
                        'status':     'sent',
                        'type':       'out',
                        'date_sent':  email_history.sent_at.isoformat() if email_history.sent_at else None,
                        'description': email_history.body[:500] if email_history.body else '',
                    }
                }
            }

            response = api._make_request('POST', '/Api/V8/module/Emails', data=data)

            if response and 'data' in response:
                crm_id = response['data'].get('id', '')
                email_history.crm_email_id = crm_id
                email_history.save(update_fields=['crm_email_id'])
                return {'success': True, 'crm_email_id': crm_id}

            return {'success': False}

        except Exception as e:
            logger.warning(f"CRM E-Mail Sync fehlgeschlagen: {e}")
            return {'success': False, 'error': str(e)}
