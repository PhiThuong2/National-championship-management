# Generated manually for MatchEvent and User settings updates

from django.db import migrations, models
import uuid
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('quanly', '0007_coach_registration_saves'),
    ]

    operations = [
        # Tạo model MatchEvent
        migrations.CreateModel(
            name='MatchEvent',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('event_type', models.CharField(choices=[('GOAL', 'Ghi bàn'), ('ASSIST', 'Kiến tạo'), ('SAVE', 'Cứu thua'), ('INTERCEPTION', 'Cản phá'), ('YELLOW_CARD', 'Thẻ vàng'), ('RED_CARD', 'Thẻ đỏ')], max_length=20, verbose_name='Loại sự kiện')),
                ('minute', models.IntegerField(blank=True, help_text='Phút xảy ra sự kiện', null=True, verbose_name='Phút')),
                ('notes', models.TextField(blank=True, null=True, verbose_name='Ghi chú')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('match', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='events', to='quanly.match', verbose_name='Trận đấu')),
                ('player', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='quanly.player', verbose_name='Cầu thủ')),
                ('team', models.ForeignKey(help_text='Đội của cầu thủ', on_delete=django.db.models.deletion.CASCADE, to='quanly.team', verbose_name='Đội')),
            ],
            options={
                'verbose_name': 'Sự kiện trận đấu',
                'verbose_name_plural': 'Sự kiện trận đấu',
                'ordering': ['minute', 'created_at'],
            },
        ),
    ]



