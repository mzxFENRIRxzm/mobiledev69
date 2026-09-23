from django.db import migrations
from django.db.models import Count
from django.db.models.functions import Lower


def add_index(apps, schema_editor):
    # Keep Django's existing User model. Empty emails remain allowed for legacy/demo users.
    user = apps.get_model('auth', 'User')
    duplicate = (user.objects.using(schema_editor.connection.alias).exclude(email='')
        .annotate(normalized=Lower('email')).values('normalized')
        .annotate(total=Count('pk')).filter(total__gt=1).exists())
    if duplicate:
        raise RuntimeError('Duplicate user emails exist (case-insensitive). Review them before applying migration 0004; no user data was changed.')
    schema_editor.execute('CREATE UNIQUE INDEX the_x_user_email_unique ON auth_user (LOWER(email)) WHERE email <> \'\'')


def drop_index(apps, schema_editor):
    schema_editor.execute('DROP INDEX the_x_user_email_unique')


class Migration(migrations.Migration):
    dependencies = [
        ('garage', '0003_booking_cancellation_reason_booking_shop_name_shop_and_more'),
        ('auth', '0012_alter_user_first_name_max_length'),
    ]
    operations = [migrations.RunPython(add_index, drop_index)]
