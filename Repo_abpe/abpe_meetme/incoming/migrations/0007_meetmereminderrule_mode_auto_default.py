from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('abpe_meetme', '0006_meetmereminderrule_attachment_refs_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='meetmereminderrule',
            name='mode',
            field=models.CharField(
                choices=[('MANUAL', 'Manuell pruefen'), ('AUTO', 'Automatisch senden')],
                default='AUTO',
                max_length=10,
                verbose_name='Modus',
            ),
        ),
    ]
