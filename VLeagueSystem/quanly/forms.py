# quanly/forms.py
from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import User
from .models import Player, Contract # Import thêm model
from .models import Team, Match, Season
from .models import TransferRequest, Feedback # Import thêm Feedback
from django.contrib.auth.forms import PasswordChangeForm
# Form đăng ký dành cho Fan
class RegisterForm(UserCreationForm):
    # Thêm các trường muốn hiển thị
    email = forms.EmailField(required=True, label="Email")
    first_name = forms.CharField(required=True, label="Họ tên")

    class Meta:
        model = User
        fields = ('email', 'first_name') # Chỉ cho nhập Email và Tên, Password tự có

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.username = self.cleaned_data['email'] # Lấy Email làm Username luôn
        user.role = 'fan' # MẶC ĐỊNH LÀ FAN
        if commit:
            user.save()
        return user
    # Form thêm cầu thủ (Dành cho Club Rep)
class PlayerForm(forms.ModelForm):
    class Meta:
        model = Player
        # Thêm 'avatar' vào danh sách fields
        fields = ['name', 'team', 'nationality', 'position', 'jersey_number', 
                  'date_of_birth', 'height', 'weight', 'avatar', 'registration_type'] 
        
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date'}),
            'registration_type': forms.Select(attrs={'class': 'form-select'}),
            # ... các widget khác giữ nguyên
        }

# Form tạo hợp đồng
class ContractForm(forms.ModelForm):
    class Meta:
        model = Contract
        fields = ['player', 'start_date', 'end_date', 'salary', 'contract_type', 'status', 'clauses']
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'end_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'clauses': forms.Textarea(attrs={'rows': 12, 'class': 'form-control', 'placeholder': 'AI sẽ tự động điền các điều khoản hợp đồng vào đây...'}),
            'salary': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'AI sẽ gợi ý mức lương phù hợp'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, user, *args, **kwargs):
        super(ContractForm, self).__init__(*args, **kwargs)
        
        # Đặt giá trị mặc định cho lương là 0 (nếu chưa có giá trị)
        if not self.initial.get('salary'):
            self.initial['salary'] = 0
        
        # --- LỚP BẢO MẬT 1: LỌC DANH SÁCH ---
        if user.role == 'club_rep' and user.team:
            # Chỉ hiển thị cầu thủ thuộc đội của người dùng đang đăng nhập
            self.fields['player'].queryset = Player.objects.filter(team=user.team)
        elif user.role == 'admin':
            # Admin thì được thấy hết
            self.fields['player'].queryset = Player.objects.all()
        else:
            # Nếu không có quyền thì không thấy ai cả (trả về rỗng)
            self.fields['player'].queryset = Player.objects.none()
            
        # Thêm class CSS cho đẹp
        self.fields['player'].widget.attrs.update({'class': 'form-select'})
        self.fields['contract_type'].widget.attrs.update({'class': 'form-select'})
            # 1. Form Đội bóng
class TeamForm(forms.ModelForm):
    class Meta:
        model = Team
        fields = ['name', 'stadium', 'city', 'logo']

# 2. Form Trận đấu (Để Admin nhập tỉ số)
class MatchForm(forms.ModelForm):
    class Meta:
        model = Match
        fields = ['season', 'home_team', 'away_team', 'match_date', 'round_number', 'status', 'home_score', 'away_score']
        widgets = {
            'match_date': forms.DateTimeInput(attrs={'type': 'datetime-local'}), # Chọn ngày giờ đẹp
        }

# 3. Form Mùa giải
class SeasonForm(forms.ModelForm):
    class Meta:
        model = Season
        fields = ['name', 'start_date', 'end_date', 'is_active']
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
        }

        # Form cấp quyền Fan -> Club Rep
class PromoteUserForm(forms.ModelForm):
    # Chọn đội bóng để quản lý
    team = forms.ModelChoiceField(queryset=Team.objects.all(), label="Chọn Đội bóng quản lý", required=True)

    class Meta:
        model = User
        fields = ['team'] # Chỉ cần chọn đội, role sẽ tự set trong code
        # Form gửi yêu cầu chuyển nhượng
class TransferOfferForm(forms.ModelForm):
    class Meta:
        model = TransferRequest
        fields = ['transfer_fee'] # Chỉ cần nhập số tiền muốn mua
        labels = {'transfer_fee': 'Mức giá đề nghị (VND)'}

        # Form cấp quyền: Bắt buộc chọn Đội bóng
class PromoteUserForm(forms.ModelForm):
    # Dùng ModelChoiceField để hiện Dropdown danh sách đội
    team = forms.ModelChoiceField(
        queryset=Team.objects.all(), 
        label="Chọn Đội bóng để quản lý", 
        required=True, # Bắt buộc phải chọn
        empty_label="-- Chọn CLB --",
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    class Meta:
        model = User
        fields = ['team'] # Chỉ hiển thị ô chọn team, role sẽ tự gán trong code

class UserEditForm(forms.ModelForm):
    team = forms.ModelChoiceField(
        queryset=Team.objects.all(),
        label="Đội bóng quản lý (Nếu là Đại diện CLB)",
        required=False,
        empty_label="-- Không quản lý --",
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'role', 'team', 'is_active']
        labels = {
            'first_name': 'Tên', 'last_name': 'Họ', 'email': 'Email',
            'role': 'Vai trò', 'is_active': 'Hoạt động'
        }
        widgets = {
            'email': forms.TextInput(attrs={'readonly': 'readonly', 'class': 'form-control-plaintext'}),
            # Role dùng Select
            'role': forms.Select(attrs={'class': 'form-select'})
        }

    # --- SỬA ĐOẠN NÀY ĐỂ CHẶN QUYỀN ADMIN ---
    def __init__(self, *args, **kwargs):
        super(UserEditForm, self).__init__(*args, **kwargs)
        
        # Chỉ cho phép chọn 2 quyền này thôi
        SAFE_ROLES = [
            ('fan', 'Người hâm mộ (Fan)'),
            ('club_rep', 'Đại diện CLB'),
        ]
        self.fields['role'].choices = SAFE_ROLES
        # Form cấu hình tạo lịch tự động
class GenerateScheduleForm(forms.Form):
    season = forms.ModelChoiceField(
        queryset=Season.objects.all(), 
        label="Chọn Mùa giải",
        empty_label="-- Chọn mùa giải --",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    start_date = forms.DateField(
        label="Ngày bắt đầu mùa giải", 
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )

# Form cài đặt thông tin người dùng (Fan và Club Rep)
class UserProfileForm(forms.ModelForm):
    new_password = forms.CharField(
        required=False,
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        label="Mật khẩu mới (để trống nếu không đổi)",
        help_text="Để trống nếu không muốn thay đổi mật khẩu"
    )
    confirm_password = forms.CharField(
        required=False,
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        label="Xác nhận mật khẩu mới"
    )

    class Meta:
        model = User
        fields = ['first_name', 'email', 'avatar']
        labels = {
            'first_name': 'Họ và tên',
            'email': 'Email',
            'avatar': 'Ảnh đại diện'
        }
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'avatar': forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'})
        }

    def __init__(self, *args, **kwargs):
        user_role = kwargs.pop('user_role', None)
        super(UserProfileForm, self).__init__(*args, **kwargs)
        
        # Club Rep không được đổi avatar
        if user_role == 'club_rep':
            self.fields.pop('avatar')

    def clean(self):
        cleaned_data = super().clean()
        new_password = cleaned_data.get('new_password')
        confirm_password = cleaned_data.get('confirm_password')

        if new_password or confirm_password:
            if new_password != confirm_password:
                raise forms.ValidationError("Mật khẩu mới và xác nhận mật khẩu không khớp!")
            if len(new_password) < 8:
                raise forms.ValidationError("Mật khẩu phải có ít nhất 8 ký tự!")

        return cleaned_data

# Form cập nhật tỉ số với đầy đủ thông tin
class MatchScoreForm(forms.ModelForm):
    class Meta:
        model = Match
        fields = ['home_score', 'away_score', 'status']
        labels = {
            'home_score': 'Bàn thắng đội nhà',
            'away_score': 'Bàn thắng đội khách',
            'status': 'Trạng thái'
        }
        widgets = {
            'home_score': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'away_score': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'status': forms.Select(attrs={'class': 'form-select'})
        }

# Form cho từng sự kiện trong trận đấu
class MatchEventForm(forms.Form):
    event_type = forms.ChoiceField(
        choices=[
            ('GOAL', 'Ghi bàn'),
            ('ASSIST', 'Kiến tạo'),
            ('SAVE', 'Cứu thua'),
            ('INTERCEPTION', 'Cản phá'),
            ('YELLOW_CARD', 'Thẻ vàng'),
            ('RED_CARD', 'Thẻ đỏ'),
        ],
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    player = forms.ModelChoiceField(
        queryset=Player.objects.none(),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    team = forms.ModelChoiceField(
        queryset=Team.objects.all(),
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    minute = forms.IntegerField(
        required=False,
        min_value=0,
        max_value=120,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Phút'})
    )
    notes = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ghi chú'})
    )

# Form gửi phản hồi
class FeedbackForm(forms.ModelForm):
    class Meta:
        model = Feedback
        fields = ['title', 'content', 'rating']
        widgets = {
             'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Tiêu đề góp ý'}),
             'content': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Nội dung chi tiết...'}),
             'rating': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 5}),
        }