# Generated by Django 5.1.6 on 2025-04-26 17:12

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('restaurant', '0021_cartitem'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='category',
            name='description',
        ),
        migrations.RemoveField(
            model_name='fooditem',
            name='description',
        ),
    ]
