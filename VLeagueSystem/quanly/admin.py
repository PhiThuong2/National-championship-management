from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.html import format_html
from django.contrib import messages
from .models import (
    User, Team, Season, Player, Match, 
    Contract, TransferRequest, PlayerStat, 
    Feedback, Prediction, SystemSetting, Coach, Ticket
)

# 1. QUẢN LÝ NGƯỜI DÙNG (Nâng cao)
# Cho phép Admin khóa/mở khóa tài khoản ngay danh sách
@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ('email', 'first_name', 'role', 'team', 'is_active')
    list_filter = ('role', 'is_active', 'team')
    search_fields = ('email', 'first_name')
    ordering = ('email',)
    
    actions = ['lock_users', 'unlock_users']

    @admin.action(description='🔒 Khóa tài khoản đã chọn')
    def lock_users(self, request, queryset):
        queryset.update(is_active=False)
        self.message_user(request, "Đã khóa các tài khoản được chọn.")

    @admin.action(description='🔓 Mở khóa tài khoản đã chọn')
    def unlock_users(self, request, queryset):
        queryset.update(is_active=True)
        self.message_user(request, "Đã mở khóa các tài khoản được chọn.")

    # Cấu hình fieldsets để hiển thị trường role, team trong trang chi tiết
    fieldsets = UserAdmin.fieldsets + (
        ('Thông tin V-League', {'fields': ('role', 'team', 'avatar')}),
    )

# 2. QUẢN LÝ CHUYỂN NHƯỢNG (Core Business)
@admin.register(TransferRequest)
class TransferRequestAdmin(admin.ModelAdmin):
    list_display = ('player', 'from_team', 'to_team', 'transfer_fee_display', 'status_colored', 'request_date')
    list_filter = ('status', 'from_team', 'to_team')
    actions = ['approve_transfer', 'reject_transfer']

    # Hiển thị phí chuyển nhượng định dạng tiền Việt
    def transfer_fee_display(self, obj):
        return f"{obj.transfer_fee:,.0f} VND"
    transfer_fee_display.short_description = "Phí chuyển nhượng"

    # Tô màu trạng thái cho dễ nhìn
    def status_colored(self, obj):
        colors = {
            'pending_approval': 'orange',
            'approved': 'green',
            'rejected': 'red',
            'negotiating': 'blue'
        }
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            colors.get(obj.status, 'black'),
            obj.get_status_display()
        )
    status_colored.short_description = "Trạng thái"

    # HÀNH ĐỘNG 1: PHÊ DUYỆT (Tự động chuyển cầu thủ sang đội mới)
    @admin.action(description='✅ Phê duyệt thương vụ (Chuyển cầu thủ)')
    def approve_transfer(self, request, queryset):
        count = 0
        for transfer in queryset:
            if transfer.status != 'approved':
                # 1. Chuyển cầu thủ sang đội mới
                player = transfer.player
                player.team = transfer.to_team
                player.save()
                
                # 2. Cập nhật trạng thái đơn
                transfer.status = 'approved'
                transfer.save()
                count += 1
        self.message_user(request, f"Đã phê duyệt {count} thương vụ. Cầu thủ đã về đội mới!", messages.SUCCESS)

    # HÀNH ĐỘNG 2: TỪ CHỐI
    @admin.action(description='❌ Từ chối thương vụ')
    def reject_transfer(self, request, queryset):
        queryset.update(status='rejected')
        self.message_user(request, "Đã từ chối các yêu cầu được chọn.")

# 3. QUẢN LÝ TRẬN ĐẤU & TỈ SỐ
@admin.register(Match)
class MatchAdmin(admin.ModelAdmin):
    list_display = ('season', 'round_number', 'match_date', 'get_match_name', 'score_input', 'status')
    list_filter = ('season', 'round_number', 'status')
    list_editable = ('status',) # Cho phép sửa trạng thái nhanh ngay bên ngoài

    def get_match_name(self, obj):
        return f"{obj.home_team} vs {obj.away_team}"
    get_match_name.short_description = "Cặp đấu"

    def score_input(self, obj):
        if obj.status == 'FINISHED':
            return f"Result: {obj.home_score} - {obj.away_score}"
        return "(Chưa đá)"
    score_input.short_description = "Kết quả"

# 4. CẤU HÌNH HỆ THỐNG (Bật/Tắt thị trường CN)
@admin.register(SystemSetting)
class SystemSettingAdmin(admin.ModelAdmin):
    list_display = ('key', 'value', 'description')
    list_editable = ('value',) # Cho phép sửa nhanh True/False

# --- ĐĂNG KÝ CÁC BẢNG CÒN LẠI (Cơ bản) ---
@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ('name', 'stadium', 'city')

@admin.register(Season)
class SeasonAdmin(admin.ModelAdmin):
    list_display = ('name', 'start_date', 'end_date', 'is_active')
    list_editable = ('is_active',) # Admin kích hoạt mùa giải nhanh

@admin.register(Player)
class PlayerAdmin(admin.ModelAdmin):
    list_display = ('name', 'team', 'position', 'registration_type', 'nationality', 'status')
    list_filter = ('team', 'position', 'status', 'registration_type')
    search_fields = ('name', 'nationality')
    list_editable = ('registration_type',)

@admin.register(Coach)
class CoachAdmin(admin.ModelAdmin):
    list_display = ('name', 'team', 'nationality', 'license_type')
    list_filter = ('team', 'nationality')
    search_fields = ('name', 'nationality')

admin.site.register(Contract)
admin.site.register(PlayerStat)
admin.site.register(Feedback)
admin.site.register(Prediction)

@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ('ticket_code', 'user', 'match', 'price', 'discount', 'final_amount', 'status', 'purchase_date')
    list_filter = ('match', 'status', 'purchase_date')
    search_fields = ('ticket_code', 'user__email', 'user__username')
    readonly_fields = ('ticket_code', 'qr_code', 'purchase_date')