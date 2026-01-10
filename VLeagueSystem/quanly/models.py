import uuid
from django.db import models
from django.db.models import Q
from django.contrib.auth.models import AbstractUser

# --- CÁC DANH SÁCH LỰA CHỌN (ENUMS) ---
class Position(models.TextChoices):
    GK = 'Goalkeeper', 'Thủ môn'
    DF = 'Defender', 'Hậu vệ'
    MF = 'Midfielder', 'Tiền vệ'
    FW = 'Forward', 'Tiền đạo'

class PlayerStatus(models.TextChoices):
    ACTIVE = 'Active', 'Đang thi đấu'
    INJURED = 'Injured', 'Chấn thương'
    SUSPENDED = 'Suspended', 'Treo giò'
    FREE_AGENT = 'Free Agent', 'Cầu thủ tự do'

class RegistrationType(models.TextChoices):
    NOI_BINH = 'NoiBinh', 'Nội binh'
    NHAP_TICH = 'NhapTich', 'Nhập tịch'
    NGOAI_BINH = 'NgoaiBinh', 'Ngoại binh'

# --- 1. BẢNG ĐỘI BÓNG (Team) - Giữ nguyên ---
class Team(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, verbose_name="Tên đội bóng")
    stadium = models.CharField(max_length=100, verbose_name="Sân vận động", null=True, blank=True)
    city = models.CharField(max_length=100, verbose_name="Thành phố", null=True, blank=True)
    logo = models.ImageField(upload_to='teams/logos/', null=True, blank=True)

    def __str__(self):
        return self.name

    @property
    def current_coach(self):
        from django.utils import timezone
        today = timezone.now().date()
        return self.coaches.filter(
            Q(contract_end__gte=today) | Q(contract_end__isnull=True)
        ).order_by('-contract_start', '-created_at').first()

# --- 2. BẢNG NGƯỜI DÙNG (User) - Giữ nguyên ---
class User(AbstractUser):
    ROLE_CHOICES = (
        ('admin', 'Quản trị viên'),
        ('club_rep', 'Đại diện CLB'),
        ('fan', 'Người hâm mộ'),
    )
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True, verbose_name="Email")
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='fan')
    team = models.ForeignKey(Team, on_delete=models.SET_NULL, null=True, blank=True, related_name='managers')
    avatar = models.ImageField(upload_to='users/avatars/', null=True, blank=True)
    reward_points = models.IntegerField(default=0, verbose_name="Điểm thưởng")
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    def __str__(self):  
        return self.email

# --- 3. BẢNG MÙA GIẢI (Season) - MỚI ---
class Season(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=50, verbose_name="Tên mùa giải") # VD: V-League 2023-2024
    start_date = models.DateField(verbose_name="Ngày bắt đầu")
    end_date = models.DateField(verbose_name="Ngày kết thúc")
    is_active = models.BooleanField(default=False, verbose_name="Đang diễn ra")

    def __str__(self):
        return self.name

# --- 4. BẢNG CẦU THỦ (Player) - MỚI ---
class Player(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, verbose_name="Tên cầu thủ")
    
    # Một cầu thủ thuộc về một đội bóng (Link tới bảng Team)
    team = models.ForeignKey(Team, on_delete=models.SET_NULL, null=True, blank=True, related_name='players', verbose_name="Đội bóng")
    
    position = models.CharField(max_length=20, choices=Position.choices, verbose_name="Vị trí")
    nationality = models.CharField(max_length=100, verbose_name="Quốc tịch", default="Việt Nam", help_text="Có thể nhập nhiều quốc tịch, cách nhau bởi dấu phẩy")
    registration_type = models.CharField(max_length=20, choices=RegistrationType.choices, null=True, blank=True, verbose_name="Suất đăng ký")
    date_of_birth = models.DateField(null=True, blank=True, verbose_name="Ngày sinh")
    jersey_number = models.IntegerField(verbose_name="Số áo", null=True, blank=True)
    status = models.CharField(max_length=20, choices=PlayerStatus.choices, default=PlayerStatus.ACTIVE, verbose_name="Trạng thái")
    avatar = models.ImageField(upload_to='players/', null=True, blank=True, verbose_name="Ảnh đại diện")
    height = models.IntegerField(null=True, blank=True, help_text="Đơn vị: cm", verbose_name="Chiều cao")
    weight = models.IntegerField(null=True, blank=True, help_text="Đơn vị: kg", verbose_name="Cân nặng")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.jersey_number})"
    # ... (Giữ nguyên code cũ bên trên) ...

# --- 5. BẢNG TRẬN ĐẤU (Match) - MỚI ---
class MatchStatus(models.TextChoices):
    SCHEDULED = 'SCHEDULED', 'Sắp đá'
    FINISHED = 'FINISHED', 'Đã kết thúc'

class Match(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    season = models.ForeignKey(Season, on_delete=models.CASCADE, verbose_name="Mùa giải")
    
    # Đội nhà và Đội khách (Liên kết 2 lần tới bảng Team)
    home_team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='home_matches', verbose_name="Đội nhà")
    away_team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='away_matches', verbose_name="Đội khách")
    
    home_score = models.IntegerField(default=0, verbose_name="Bàn thắng đội nhà")
    away_score = models.IntegerField(default=0, verbose_name="Bàn thắng đội khách")
    
    match_date = models.DateTimeField(verbose_name="Ngày giờ đá")
    round_number = models.IntegerField(verbose_name="Vòng đấu")
    
    status = models.CharField(max_length=20, choices=MatchStatus.choices, default=MatchStatus.SCHEDULED, verbose_name="Trạng thái")

    def __str__(self):
        return f"Vòng {self.round_number}: {self.home_team} vs {self.away_team}"

    # Kiểm tra tính hợp lệ: Đội nhà không được trùng đội khách
    def clean(self):
        from django.core.exceptions import ValidationError
        if self.home_team == self.away_team:
            raise ValidationError("Đội nhà và Đội khách không được trùng nhau.")
        
        # ... (Giữ nguyên code cũ bên trên) ...

# --- 6. BẢNG HỢP ĐỒNG (Contract) - MỚI ---
class ContractType(models.TextChoices):
    PERMANENT = 'Permanent', 'Hợp đồng dài hạn'
    LOAN = 'Loan', 'Cho mượn'

class ContractStatus(models.TextChoices):
    ACTIVE = 'Active', 'Đang hiệu lực'
    EXPIRED = 'Expired', 'Đã hết hạn'
    TERMINATED = 'Terminated', 'Đã chấm dứt'
    PENDING = 'Pending', 'Chờ hiệu lực'

class Contract(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    player = models.ForeignKey(Player, on_delete=models.CASCADE, verbose_name="Cầu thủ")
    team = models.ForeignKey(Team, on_delete=models.CASCADE, verbose_name="Đội bóng")
    
    start_date = models.DateField(verbose_name="Ngày hiệu lực")
    end_date = models.DateField(verbose_name="Ngày hết hạn")
    salary = models.BigIntegerField(verbose_name="Lương (VND)")
    contract_type = models.CharField(max_length=20, choices=ContractType.choices, default=ContractType.PERMANENT, verbose_name="Loại hợp đồng")
    status = models.CharField(max_length=20, choices=ContractStatus.choices, default=ContractStatus.PENDING, verbose_name="Trạng thái")
    clauses = models.TextField(verbose_name="Điều khoản chi tiết", null=True, blank=True) # Nơi Gemini AI sẽ điền vào sau này
    
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"HĐ: {self.player.name} - {self.team.name}"

    @property
    def is_active(self):
        from datetime import date
        return self.end_date >= date.today()

    @property
    def is_expiring_soon(self):
        from datetime import date, timedelta
        # Sắp hết hạn trong vòng 6 tháng
        return date.today() <= self.end_date <= date.today() + timedelta(days=30*6)

# --- 7. BẢNG CHUYỂN NHƯỢNG (Transfer Request) - MỚI ---
class TransferStatus(models.TextChoices):
    PENDING = 'pending_approval', 'Chờ phê duyệt'
    APPROVED = 'approved', 'Đã chấp thuận'
    REJECTED = 'rejected', 'Bị từ chối'
    NEGOTIATING = 'negotiating', 'Đang thương lượng'

class TransferRequest(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    player = models.ForeignKey(Player, on_delete=models.CASCADE, verbose_name="Cầu thủ")
    
    # Đội bán và Đội mua
    from_team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='transfers_out', verbose_name="Đội bán")
    to_team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='transfers_in', verbose_name="Đội mua")
    
    transfer_fee = models.BigIntegerField(verbose_name="Phí chuyển nhượng (VND)")
    status = models.CharField(max_length=20, choices=TransferStatus.choices, default=TransferStatus.PENDING, verbose_name="Trạng thái")
    
    request_date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.player.name}: {self.from_team.name} -> {self.to_team.name}"
    # ... (Giữ nguyên code cũ bên trên) ...

# --- 8. BẢNG THỐNG KÊ CẦU THỦ (Player Stats) - MỚI ---
class PlayerStat(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    player = models.ForeignKey(Player, on_delete=models.CASCADE, verbose_name="Cầu thủ")
    season = models.ForeignKey(Season, on_delete=models.CASCADE, verbose_name="Mùa giải")
    
    goals = models.IntegerField(default=0, verbose_name="Bàn thắng")
    assists = models.IntegerField(default=0, verbose_name="Kiến tạo")
    saves = models.IntegerField(default=0, verbose_name="Số lần cứu thua")
    yellow_cards = models.IntegerField(default=0, verbose_name="Thẻ vàng")
    red_cards = models.IntegerField(default=0, verbose_name="Thẻ đỏ")
    matches_played = models.IntegerField(default=0, verbose_name="Số trận ra sân")

    def __str__(self):
        return f"Stats: {self.player.name} ({self.season.name})"

# --- 9. BẢNG PHẢN HỒI (Feedback) - MỚI ---
class Feedback(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Người gửi")
    title = models.CharField(max_length=200, verbose_name="Tiêu đề")
    content = models.TextField(verbose_name="Nội dung")
    rating = models.IntegerField(default=5, verbose_name="Đánh giá (Sao)")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title

# --- 10. BẢNG DỰ ĐOÁN (Prediction) - MỚI ---
class PredictionSource(models.TextChoices):
    USER = 'USER', 'Người dùng'
    AI = 'AI', 'Trí tuệ nhân tạo'

class Prediction(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Người dự đoán")
    match = models.ForeignKey(Match, on_delete=models.CASCADE, verbose_name="Trận đấu")
    
    predicted_home_score = models.IntegerField(verbose_name="Dự đoán chủ nhà")
    predicted_away_score = models.IntegerField(verbose_name="Dự đoán đội khách")
    points_earned = models.IntegerField(default=0, verbose_name="Điểm thưởng")
    
    # AI Enhancement Fields
    prediction_source = models.CharField(
        max_length=10, 
        choices=PredictionSource.choices, 
        default=PredictionSource.USER,
        verbose_name="Nguồn dự đoán"
    )
    confidence_score = models.FloatField(
        null=True, 
        blank=True, 
        verbose_name="Độ tin cậy",
        help_text="Điểm tin cậy từ 0-1 (chỉ dành cho AI)"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'match') # Mỗi người chỉ dự đoán 1 lần cho 1 trận

    def __str__(self):
        return f"{self.user.email} dự đoán {self.match}"

# --- 13. VÉ NGƯỜI DÙNG (TICKET) ---
class Ticket(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Người mua")
    match = models.ForeignKey(Match, on_delete=models.CASCADE, verbose_name="Trận đấu")
    
    price = models.IntegerField(default=100000, verbose_name="Giá vé")
    discount = models.IntegerField(default=0, verbose_name="Giảm giá (Điểm)")
    final_amount = models.IntegerField(verbose_name="Thực trả")
    
    payment_method = models.CharField(max_length=20, default='bank', verbose_name="Phương thức thanh toán")
    # 'momo', 'bank', 'points'
    
    status = models.CharField(max_length=20, default='paid', verbose_name="Trạng thái")
    # 'paid', 'pending', 'cancelled'
    
    ticket_code = models.CharField(max_length=20, unique=True, verbose_name="Mã vé")
    qr_code = models.ImageField(upload_to='tickets/qr/', null=True, blank=True, verbose_name="Mã QR")
    
    purchase_date = models.DateTimeField(auto_now_add=True, verbose_name="Ngày mua")

    def __str__(self):
        return f"Vé {self.ticket_code} - {self.user.email}"
    
    def save(self, *args, **kwargs):
        if not self.ticket_code:
            import random, string
            # Tạo mã vé ngẫu nhiên 8 ký tự
            chars = string.ascii_uppercase + string.digits
            self.ticket_code = ''.join(random.choice(chars) for _ in range(8))
        super().save(*args, **kwargs)
    # --- 11. CẤU HÌNH HỆ THỐNG (System Settings) ---
class SystemSetting(models.Model):
    key = models.CharField(max_length=50, primary_key=True, verbose_name="Mã cài đặt")
    value = models.CharField(max_length=255, verbose_name="Giá trị")
    description = models.TextField(verbose_name="Mô tả", blank=True)

    def __str__(self):
        return f"{self.key}: {self.value}"

# --- 12. BẢNG HUẤN LUYỆN VIÊN (Coach) - MỚI ---
class Coach(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, verbose_name="Tên HLV")
    team = models.ForeignKey(Team, on_delete=models.SET_NULL, null=True, blank=True, related_name='coaches', verbose_name="Đội bóng")
    nationality = models.CharField(max_length=50, verbose_name="Quốc tịch", default="Việt Nam")
    date_of_birth = models.DateField(null=True, blank=True, verbose_name="Ngày sinh")
    license_type = models.CharField(max_length=50, verbose_name="Bằng cấp HLV", null=True, blank=True, help_text="VD: Pro License, A License")
    contract_start = models.DateField(null=True, blank=True, verbose_name="Ngày bắt đầu hợp đồng")
    contract_end = models.DateField(null=True, blank=True, verbose_name="Ngày kết thúc hợp đồng")
    photo = models.ImageField(upload_to='coaches/photos/', null=True, blank=True, verbose_name="Ảnh")
    
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} - {self.team.name if self.team else 'Chưa có đội'}"

# --- 13. BẢNG SỰ KIỆN TRẬN ĐẤU (Match Event) - MỚI ---
class MatchEventType(models.TextChoices):
    GOAL = 'GOAL', 'Ghi bàn'
    ASSIST = 'ASSIST', 'Kiến tạo'
    SAVE = 'SAVE', 'Cứu thua'
    INTERCEPTION = 'INTERCEPTION', 'Cản phá'
    YELLOW_CARD = 'YELLOW_CARD', 'Thẻ vàng'
    RED_CARD = 'RED_CARD', 'Thẻ đỏ'

class MatchEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    match = models.ForeignKey(Match, on_delete=models.CASCADE, related_name='events', verbose_name="Trận đấu")
    player = models.ForeignKey(Player, on_delete=models.CASCADE, null=True, blank=True, verbose_name="Cầu thủ")
    event_type = models.CharField(max_length=20, choices=MatchEventType.choices, verbose_name="Loại sự kiện")
    minute = models.IntegerField(null=True, blank=True, verbose_name="Phút", help_text="Phút xảy ra sự kiện")
    team = models.ForeignKey(Team, on_delete=models.CASCADE, verbose_name="Đội", help_text="Đội của cầu thủ")
    notes = models.TextField(null=True, blank=True, verbose_name="Ghi chú")
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['minute', 'created_at']
        verbose_name = "Sự kiện trận đấu"
        verbose_name_plural = "Sự kiện trận đấu"

    def __str__(self):
        return f"{self.match} - {self.get_event_type_display()} - {self.player.name if self.player else 'N/A'}"

# --- 14. BẢNG DỰ ĐOÁN AI (AI Prediction) - MỚI ---
class AIPrediction(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    match = models.ForeignKey(Match, on_delete=models.CASCADE, related_name='ai_predictions', verbose_name="Trận đấu")
    
    # Predicted Score
    predicted_home_score = models.IntegerField(verbose_name="Dự đoán bàn thắng chủ nhà")
    predicted_away_score = models.IntegerField(verbose_name="Dự đoán bàn thắng đội khách")
    
    # Probabilities (Win/Draw/Loss from home team perspective)
    win_probability = models.FloatField(verbose_name="Xác suất thắng", help_text="Xác suất đội nhà thắng (0-1)")
    draw_probability = models.FloatField(verbose_name="Xác suất hòa", help_text="Xác suất hòa (0-1)")
    loss_probability = models.FloatField(verbose_name="Xác suất thua", help_text="Xác suất đội nhà thua (0-1)")
    
    # Metadata
    confidence_score = models.FloatField(verbose_name="Độ tin cậy tổng thể", help_text="Điểm tin cậy từ 0-1")
    model_version = models.CharField(max_length=50, verbose_name="Phiên bản mô hình", default="v1.0")
    
    # Tracking
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Ngày tạo")
    is_correct = models.BooleanField(null=True, blank=True, verbose_name="Dự đoán đúng?", help_text="Cập nhật sau khi trận đấu kết thúc")
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = "Dự đoán AI"
        verbose_name_plural = "Dự đoán AI"
    
    def __str__(self):
        return f"AI dự đoán: {self.match} - {self.predicted_home_score}:{self.predicted_away_score}"
    
    def update_correctness(self):
        """Cập nhật is_correct sau khi trận đấu kết thúc"""
        if self.match.status == 'FINISHED':
            self.is_correct = (
                self.predicted_home_score == self.match.home_score and
                self.predicted_away_score == self.match.away_score
            )
            self.save()

# --- 15. BẢNG THỐNG KÊ ĐỘI BÓNG (Team Statistics) - MỚI ---
class TeamStatistics(models.Model):
    """Cache thống kê đội bóng để tối ưu hiệu năng AI"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='statistics', verbose_name="Đội bóng")
    season = models.ForeignKey(Season, on_delete=models.CASCADE, verbose_name="Mùa giải")
    
    # Overall Statistics
    matches_played = models.IntegerField(default=0, verbose_name="Số trận đã đá")
    wins = models.IntegerField(default=0, verbose_name="Số trận thắng")
    draws = models.IntegerField(default=0, verbose_name="Số trận hòa")
    losses = models.IntegerField(default=0, verbose_name="Số trận thua")
    
    # Goals
    goals_for = models.IntegerField(default=0, verbose_name="Bàn thắng ghi được")
    goals_against = models.IntegerField(default=0, verbose_name="Bàn thua")
    
    # Home/Away Split
    home_wins = models.IntegerField(default=0, verbose_name="Thắng sân nhà")
    home_draws = models.IntegerField(default=0, verbose_name="Hòa sân nhà")
    home_losses = models.IntegerField(default=0, verbose_name="Thua sân nhà")
    away_wins = models.IntegerField(default=0, verbose_name="Thắng sân khách")
    away_draws = models.IntegerField(default=0, verbose_name="Hòa sân khách")
    away_losses = models.IntegerField(default=0, verbose_name="Thua sân khách")
    
    # Calculated Fields
    avg_goals_scored = models.FloatField(default=0.0, verbose_name="Trung bình bàn thắng/trận")
    avg_goals_conceded = models.FloatField(default=0.0, verbose_name="Trung bình bàn thua/trận")
    recent_form = models.CharField(max_length=10, blank=True, verbose_name="Phong độ gần đây", help_text="VD: WWDLL (5 trận gần nhất)")
    
    # Timestamps
    last_updated = models.DateTimeField(auto_now=True, verbose_name="Cập nhật lần cuối")
    
    class Meta:
        unique_together = ('team', 'season')
        verbose_name = "Thống kê đội bóng"
        verbose_name_plural = "Thống kê đội bóng"
    
    def __str__(self):
        return f"Thống kê {self.team.name} - {self.season.name}"

# --- 16. BẢNG TIN NHẮN CHATBOT (ChatMessage) - MỚI ---
class ChatMessage(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='chat_messages', verbose_name="Người dùng")
    message = models.TextField(verbose_name="Tin nhắn người dùng")
    response = models.TextField(verbose_name="Phản hồi từ AI", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Thời gian")

    class Meta:
        ordering = ['created_at']
        verbose_name = "Lịch sử Chat AI"
        verbose_name_plural = "Lịch sử Chat AI"

    def __str__(self):
        return f"Chat: {self.user.email} - {self.created_at.strftime('%Y-%m-%d %H:%M')}"