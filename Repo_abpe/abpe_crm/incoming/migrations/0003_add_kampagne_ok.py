# Generated migration - kampagne_ok field on CrmEmailAddress
from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('abpe_crm', '0002_dynamic_profile_tables'),
    ]
    operations = [
        migrations.AddField(
            model_name='crmemailaddress',
            name='kampagne_ok',
            field=models.BooleanField(default=False, verbose_name='Kampagne erlaubt'),
        ),
    ]
