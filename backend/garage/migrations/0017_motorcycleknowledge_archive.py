from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("garage", "0016_aiconversation_archive_reason_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="motorcycleknowledge",
            name="archived_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="motorcycleknowledge",
            name="archive_reason",
            field=models.TextField(blank=True, max_length=500),
        ),
    ]
