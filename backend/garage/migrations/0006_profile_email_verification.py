from django.db import migrations, models
from django.db.models.functions import Lower


class Migration(migrations.Migration):
    dependencies = [('garage', '0005_registration_profile_shop_location')]

    operations = [
        migrations.AddField(
            model_name='userprofile', name='pending_email',
            field=models.EmailField(blank=True, max_length=254),
        ),
        migrations.AddField(
            model_name='userprofile', name='email_verified_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='userprofile', name='awaiting_signup_verification',
            field=models.BooleanField(default=False),
        ),
        migrations.AddConstraint(
            model_name='userprofile',
            constraint=models.UniqueConstraint(
                Lower('pending_email'), condition=~models.Q(pending_email=''),
                name='the_x_pending_email_unique',
            ),
        ),
    ]
