import secrets

import django.db.models.deletion
import maps.models
from django.db import migrations, models


def generate_migration_refresh_token():
    return f'ort_{secrets.token_urlsafe(48)}'


def populate_refresh_tokens(apps, schema_editor):
    owner_access_token = apps.get_model('maps', 'OwnerAccessToken')
    used_refresh_tokens = set()

    for token in owner_access_token.objects.all().iterator():
        refresh_token = generate_migration_refresh_token()
        while refresh_token in used_refresh_tokens:
            refresh_token = generate_migration_refresh_token()

        token.refresh_token = refresh_token
        token.refresh_expires_at = maps.models.default_refresh_expires_at()
        token.save(update_fields=['refresh_token', 'refresh_expires_at'])
        used_refresh_tokens.add(refresh_token)


class Migration(migrations.Migration):

    dependencies = [
        ('maps', '0005_owner_oauth_credentials'),
    ]

    operations = [
        migrations.CreateModel(
            name='OwnerAuthorizationCode',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.CharField(default=maps.models.generate_owner_authorization_code, max_length=160, unique=True)),
                ('redirect_uri', models.URLField(max_length=500)),
                ('state', models.CharField(blank=True, max_length=255)),
                ('expires_at', models.DateTimeField(default=maps.models.default_authorization_code_expires_at)),
                ('used_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddField(
            model_name='owneraccesstoken',
            name='refresh_expires_at',
            field=models.DateTimeField(default=maps.models.default_refresh_expires_at),
        ),
        migrations.AddField(
            model_name='owneraccesstoken',
            name='refresh_token',
            field=models.CharField(max_length=180, null=True, unique=True),
        ),
        migrations.AddField(
            model_name='owneraccesstoken',
            name='revoked_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.RunPython(populate_refresh_tokens, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='owneraccesstoken',
            name='refresh_token',
            field=models.CharField(default=maps.models.generate_owner_refresh_token, max_length=180, unique=True),
        ),
        migrations.AlterField(
            model_name='owneraccesstoken',
            name='expires_at',
            field=models.DateTimeField(default=maps.models.default_token_expires_at),
        ),
        migrations.AddIndex(
            model_name='owneraccesstoken',
            index=models.Index(fields=['refresh_token'], name='maps_ownera_refresh_c6437d_idx'),
        ),
        migrations.AddIndex(
            model_name='owneraccesstoken',
            index=models.Index(fields=['refresh_expires_at'], name='maps_ownera_refresh_96a49d_idx'),
        ),
        migrations.AddField(
            model_name='ownerauthorizationcode',
            name='owner',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='oauth_codes', to='maps.ownerprofile'),
        ),
        migrations.AddIndex(
            model_name='ownerauthorizationcode',
            index=models.Index(fields=['code'], name='maps_ownera_code_00e4b9_idx'),
        ),
        migrations.AddIndex(
            model_name='ownerauthorizationcode',
            index=models.Index(fields=['expires_at'], name='maps_ownera_expires_120467_idx'),
        ),
    ]
