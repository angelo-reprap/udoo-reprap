"""
KORRIGIERTE _save_attachment Funktion - OHNE file Field
"""

def _save_attachment_fixed(self, email_message, attachment_data):
    """Speichert Attachment in DB UND Dateisystem (korrigierte Version)"""
    try:
        import os
        from django.core.files.base import ContentFile
        from django.conf import settings
        from .models import EmailAttachment
        
        # 1. Upload-Verzeichnis erstellen
        upload_dir = os.path.join(settings.MEDIA_ROOT, f"email_attachments/{email_message.id}/")
        os.makedirs(upload_dir, exist_ok=True)
        
        # 2. Dateipfad
        filename = attachment_data['filename']
        file_path = os.path.join(upload_dir, filename)
        
        # 3. Datei auf Disk speichern
        with open(file_path, 'wb') as f:
            f.write(attachment_data['payload'])
        
        # 4. Relativen Pfad für DB (MEDIA_ROOT abgeschnitten)
        relative_path = file_path.replace(settings.MEDIA_ROOT, '').lstrip('/')
        
        # 5. EmailAttachment OHNE file Field erstellen
        attachment = EmailAttachment.objects.create(
            email=email_message,
            filename=filename,
            content_type=attachment_data['content_type'],
            size=attachment_data['size'],
            file_path=relative_path,  # Nur der Pfad, kein file Field
            storage_backend='local',
            is_processed=False,
            metadata={
                'original_filename': filename,
                'imported_at': timezone.now().isoformat(),
                'source': 'imap_import',
                'content_type': attachment_data['content_type'],
                'size_bytes': attachment_data['size'],
                'file_exists': os.path.exists(file_path),
                'file_path_absolute': file_path,
            }
        )
        
        logger.info(f"✅ Attachment gespeichert: {filename} -> {relative_path}")
        return attachment
        
    except Exception as e:
        logger.error(f"❌ _save_attachment Fehler für {attachment_data.get('filename', 'unknown')}: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return None
