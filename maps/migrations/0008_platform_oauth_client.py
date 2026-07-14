from django.db import migrations, models
import django.db.models.deletion


def seed_shophub_platform_client(apps, schema_editor):
    PlatformOAuthClient = apps.get_model('maps', 'PlatformOAuthClient')
    PlatformOAuthClient.objects.get_or_create(
        client_id='oci_shophub_local',
        defaults={
            'name': 'ShopHub',
            'client_secret': 'ocs_shophub_local_dev_secret',
            'redirect_uris': '\n'.join([
                'http://localhost:8080/api/integrations/MOCK_MAP/oauth/callback',
                'http://127.0.0.1:8080/api/integrations/MOCK_MAP/oauth/callback',
            ]),
            'scopes': 'owner:reviews',
            'is_active': True,
        },
    )


class Migration(migrations.Migration):

    dependencies = [
        ('maps', '0007_oauth_scope'),
    ]

    operations = [
        migrations.CreateModel(
            name='PlatformOAuthClient',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
                ('client_id', models.CharField(max_length=128, unique=True)),
                ('client_secret', models.CharField(max_length=128)),
                ('redirect_uris', models.TextField(help_text='One redirect URI per line (exact match).')),
                ('scopes', models.CharField(default='owner:reviews', max_length=255)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'ordering': ['name'],
            },
        ),
        migrations.AddField(
            model_name='ownerauthorizationcode',
            name='platform_client',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='oauth_codes',
                to='maps.platformoauthclient',
            ),
        ),
        migrations.RunPython(seed_shophub_platform_client, migrations.RunPython.noop),
    ]
