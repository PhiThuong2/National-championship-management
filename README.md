# National Championship Management (VLeagueSystem)

## Giới thiệu
Hệ thống quản lý giải vô địch quốc gia (V-League): quản lý đội bóng, cầu thủ, mùa giải, lịch thi đấu/trận đấu, hợp đồng, chuyển nhượng, dự đoán,…

## Tài liệu / Báo cáo
- Báo cáo PDF: docs/BaoCaoDoAn.pdf

## Công nghệ sử dụng
- Python / Django
- (DB: SQLite / PostgreSQL / MySQL — điền cái bạn dùng)
- (Thư viện khác nếu có)

## Cài đặt & Chạy dự án (local)
```bash
cd VLeagueSystem
python -m venv venv
# Windows: venv\Scripts\activate
# Mac/Linux: source venv/bin/activate

pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

## Tài khoản (tuỳ chọn)
- Admin: (điền nếu có) / hoặc tạo bằng:
```bash
python manage.py createsuperuser
```

## Chức năng chính
- Quản lý đội bóng / cầu thủ
- Quản lý mùa giải / trận đấu
- Hợp đồng / chuyển nhượng
- Dự đoán / vé / phản hồi
