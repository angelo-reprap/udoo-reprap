# Generated manually — Education/Experience.period war varchar(50),
# CV-Import schreibt oft längere Zeiträume (→ DataError StringDataRightTruncation).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cv_extractor', '0015_alter_uploadedpdf_from_email'),
    ]

    operations = [
        migrations.AlterField(
            model_name='education',
            name='period',
            field=models.CharField(blank=True, max_length=200),
        ),
        migrations.AlterField(
            model_name='experience',
            name='period',
            field=models.CharField(blank=True, max_length=200),
        ),
    ]
