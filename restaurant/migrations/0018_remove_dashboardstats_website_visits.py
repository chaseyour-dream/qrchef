# Generated by Django 5.1.6 on 2025-04-26 06:50

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('restaurant', '0017_dashboardstats'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='dashboardstats',
            name='website_visits',
        ),
    ]
