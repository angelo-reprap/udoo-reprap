from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('abpe_shaduler', '0006_matchingberaterterms'),
    ]

    operations = [
        migrations.AddField(
            model_name='aufgabe',
            name='delegiert_an',
            field=models.ManyToManyField(
                blank=True,
                help_text='Kollegen, die die Aufgabe mitbearbeiten (Eigentümer bleibt zugewiesen_an).',
                related_name='shaduler_delegierte_aufgaben',
                to=settings.AUTH_USER_MODEL,
                verbose_name='Delegiert an',
            ),
        ),
    ]
