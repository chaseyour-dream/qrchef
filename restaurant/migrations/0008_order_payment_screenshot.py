# Generated by Django 5.1.6 on 2025-04-18 05:07

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('restaurant', '0007_payment_payment_proof_alter_payment_payment_method'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='payment_screenshot',
            field=models.ImageField(blank=True, null=True, upload_to='payment_screenshots/'),
        ),
    ]
