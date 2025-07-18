# Generated by Django 5.2.1 on 2025-05-18 16:23

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('restaurant', '0043_signupotp'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='signupotp',
            name='email',
            field=models.EmailField(default='temp@example.com', max_length=254, unique=True),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='signupotp',
            name='temp_password',
            field=models.CharField(default=django.utils.timezone.now, max_length=128),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='signupotp',
            name='username',
            field=models.CharField(default=django.utils.timezone.now, max_length=150, unique=True),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='signupotp',
            name='user',
            field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL),
        ),
    ]
