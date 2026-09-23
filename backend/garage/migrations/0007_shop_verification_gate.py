from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('garage', '0006_profile_email_verification')]

    operations = [
        migrations.AddField(
            model_name='shop', name='awaiting_owner_verification',
            field=models.BooleanField(default=False),
        ),
    ]
