from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('maps', '0006_authorization_code_refresh_tokens'),
    ]

    operations = [
        migrations.AddField(
            model_name='ownerauthorizationcode',
            name='scope',
            field=models.CharField(default='owner:reviews', max_length=255),
        ),
        migrations.AddField(
            model_name='owneraccesstoken',
            name='scope',
            field=models.CharField(default='owner:reviews', max_length=255),
        ),
    ]
