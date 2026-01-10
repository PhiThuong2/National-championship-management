# Generated manually for Coach, RegistrationType, and saves field

from django.db import migrations, models
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('quanly', '0006_systemsetting'),
    ]

    operations = [
        # Thêm trường registration_type vào Player
        migrations.AddField(
            model_name='player',
            name='registration_type',
            field=models.CharField(blank=True, choices=[('NoiBinh', 'Nội binh'), ('NhapTich', 'Nhập tịch'), ('NgoaiBinh', 'Ngoại binh')], max_length=20, null=True, verbose_name='Suất đăng ký'),
        ),
        # Cập nhật trường nationality để hỗ trợ nhiều quốc tịch
        migrations.AlterField(
            model_name='player',
            name='nationality',
            field=models.CharField(default='Việt Nam', help_text='Có thể nhập nhiều quốc tịch, cách nhau bởi dấu phẩy', max_length=100, verbose_name='Quốc tịch'),
        ),
        # Thêm trường saves vào PlayerStat
        migrations.AddField(
            model_name='playerstat',
            name='saves',
            field=models.IntegerField(default=0, verbose_name='Số lần cứu thua'),
        ),
        # Tạo model Coach
        migrations.CreateModel(
            name='Coach',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=100, verbose_name='Tên HLV')),
                ('nationality', models.CharField(default='Việt Nam', max_length=50, verbose_name='Quốc tịch')),
                ('date_of_birth', models.DateField(blank=True, null=True, verbose_name='Ngày sinh')),
                ('license_type', models.CharField(blank=True, help_text='VD: Pro License, A License', max_length=50, null=True, verbose_name='Bằng cấp HLV')),
                ('contract_start', models.DateField(blank=True, null=True, verbose_name='Ngày bắt đầu hợp đồng')),
                ('contract_end', models.DateField(blank=True, null=True, verbose_name='Ngày kết thúc hợp đồng')),
                ('photo', models.ImageField(blank=True, null=True, upload_to='coaches/photos/', verbose_name='Ảnh')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('team', models.ForeignKey(blank=True, null=True, on_delete=models.SET_NULL, related_name='coaches', to='quanly.team', verbose_name='Đội bóng')),
            ],
        ),
    ]



