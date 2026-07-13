import secrets

import django.db.models.deletion
import maps.models
from django.db import migrations, models


def generate_migration_client_id():
    return f'oci_{secrets.token_urlsafe(18)}'


def generate_migration_client_secret():
    return f'ocs_{secrets.token_urlsafe(32)}'


def populate_client_credentials(apps, schema_editor):
    owner_profile = apps.get_model('maps', 'OwnerProfile')
    used_client_ids = set()
    used_client_secrets = set()

    for profile in owner_profile.objects.all().iterator():
        client_id = generate_migration_client_id()
        while client_id in used_client_ids:
            client_id = generate_migration_client_id()

        client_secret = generate_migration_client_secret()
        while client_secret in used_client_secrets:
            client_secret = generate_migration_client_secret()

        profile.client_id = client_id
        profile.client_secret = client_secret
        profile.save(update_fields=['client_id', 'client_secret'])
        used_client_ids.add(client_id)
        used_client_secrets.add(client_secret)


class Migration(migrations.Migration):

    dependencies = [
        ('maps', '0004_alter_reviewreply_review'),
    ]

    operations = [
        migrations.AddField(
            model_name='ownerprofile',
            name='client_id',
            field=models.CharField(max_length=128, null=True, unique=True),
        ),
        migrations.AddField(
            model_name='ownerprofile',
            name='client_secret',
            field=models.CharField(max_length=128, null=True, unique=True),
        ),
        migrations.RunPython(populate_client_credentials, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='ownerprofile',
            name='client_id',
            field=models.CharField(default=maps.models.generate_owner_client_id, max_length=128, unique=True),
        ),
        migrations.AlterField(
            model_name='ownerprofile',
            name='client_secret',
            field=models.CharField(default=maps.models.generate_owner_client_secret, max_length=128, unique=True),
        ),
        migrations.RemoveField(
            model_name='ownerprofile',
            name='api_key',
        ),
        migrations.CreateModel(
            name='OwnerAccessToken',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('token', models.CharField(default=maps.models.generate_owner_access_token, max_length=160, unique=True)),
                ('expires_at', models.DateTimeField(default=maps.models.default_token_expires_at)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('owner', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='oauth_tokens', to='maps.ownerprofile')),
            ],
            options={
                'ordering': ['-created_at'],
                'indexes': [
                    models.Index(fields=['token'], name='maps_ownera_token_4b6af7_idx'),
                    models.Index(fields=['expires_at'], name='maps_ownera_expires_77f2b8_idx'),
                ],
            },
        ),
    ]
