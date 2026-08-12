from django.db import migrations, models
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('abpe_shaduler', '0004_radarconsultantitem_deleted_at'),
    ]

    operations = [
        migrations.CreateModel(
            name='ShadulerSetting',
            fields=[
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('key', models.CharField(db_index=True, max_length=120, unique=True)),
                ('value', models.TextField(blank=True)),
                ('label', models.CharField(blank=True, max_length=160)),
                ('group', models.CharField(blank=True, db_index=True, max_length=40)),
                ('description', models.CharField(blank=True, max_length=255)),
            ],
            options={
                'verbose_name': 'Einstellung',
                'verbose_name_plural': 'Einstellungen',
                'ordering': ['group', 'key'],
            },
        ),
    ]
