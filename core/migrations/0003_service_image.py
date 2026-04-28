from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0002_service_delivery_time'),
    ]

    operations = [
        migrations.AddField(
            model_name='service',
            name='image',
            field=models.ImageField(
                blank=True,
                null=True,
                upload_to='services/',
                help_text='Optional cover image for the service listing'
            ),
        ),
    ]
