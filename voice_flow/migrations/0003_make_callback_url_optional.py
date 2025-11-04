from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('voice_flow', '0002_add_summary_text'),
    ]

    operations = [
        migrations.AlterField(
            model_name='voiceformconfig',
            name='callback_url',
            field=models.URLField(blank=True, null=True, help_text='Webhook URL to send completed data'),
        ),
    ]


