# Generated by Django 5.1.6 on 2025-04-30 06:20

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('restaurant', '0028_remove_room_number'),
    ]

    operations = [
        migrations.AddField(
            model_name='roomorder',
            name='room_number',
            field=models.CharField(blank=True, max_length=10, null=True),
        ),
        migrations.AlterField(
            model_name='roomorder',
            name='room',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='restaurant.room'),
        ),
    ]
