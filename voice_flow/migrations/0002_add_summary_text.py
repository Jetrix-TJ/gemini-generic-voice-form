from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('voice_flow', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='magiclinksession',
            name='summary_text',
            field=models.TextField(blank=True),
        ),
    ]


