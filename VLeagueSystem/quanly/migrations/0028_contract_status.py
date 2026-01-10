# Generated migration file for adding status field to Contract model

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('quanly', '0015_alter_chatmessage_options_alter_chatmessage_message'),
    ]

    operations = [
        migrations.AddField(
            model_name='contract',
            name='status',
            field=models.CharField(
                choices=[
                    ('Active', 'Đang hiệu lực'), 
                    ('Expired', 'Đã hết hạn'), 
                    ('Terminated', 'Đã chấm dứt'), 
                    ('Pending', 'Chờ hiệu lực')
                ],
                default='Pending',
                max_length=20,
                verbose_name='Trạng thái'
            ),
        ),
    ]
