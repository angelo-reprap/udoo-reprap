# Generated manually for InboxMailRead (ABpE-Gelesen-Status)

import django.db.models.deletion
import django.utils.timezone
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('abpe_shaduler', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='InboxMailRead',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('mail_id', models.CharField(db_index=True, max_length=255)),
                ('read_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='shaduler_inbox_reads',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'verbose_name': 'Posteingang gelesen',
                'verbose_name_plural': 'Posteingang gelesen',
            },
        ),
        migrations.AddConstraint(
            model_name='inboxmailread',
            constraint=models.UniqueConstraint(
                fields=('user', 'mail_id'),
                name='shaduler_inboxread_user_mail',
            ),
        ),
        migrations.AddIndex(
            model_name='inboxmailread',
            index=models.Index(fields=['user', 'read_at'], name='abpe_shadul_user_id_read_at_idx'),
        ),
    ]
