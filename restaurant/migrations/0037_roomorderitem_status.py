# Generated by Django 5.1.6 on 2025-04-30 18:51

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('restaurant', '0036_roomorder_status'),
    ]

    operations = [
        migrations.AddField(
            model_name='roomorderitem',
            name='status',
            field=models.CharField(choices=[('confirmed', 'Confirmed'), ('completed', 'Completed'), ('cancelled', 'Cancelled')], default='confirmed', max_length=20),
        ),
    ]
