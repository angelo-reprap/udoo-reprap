from django.db import migrations

class Migration(migrations.Migration):
    dependencies = [
        ('abpe_crm', '0003_add_kampagne_ok'),
    ]
    operations = [
        migrations.DeleteModel(name='CrmContactPhone'),
    ]
