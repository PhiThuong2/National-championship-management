from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth import update_session_auth_hash, authenticate, login, logout
from django.contrib.auth.forms import AuthenticationForm
from quanly.forms import UserProfileForm, RegisterForm # <-- Sửa UserRegisterForm thành RegisterForm
def login_view(request):
    # Nếu người dùng đã đăng nhập, chuyển hướng họ về trang phù hợp
    if request.user.is_authenticated:
        if request.user.role == 'admin' or request.user.is_superuser:
            return redirect('admin_dashboard')
        elif request.user.role == 'club_rep':
            return redirect('club_dashboard')
        return redirect('home')

    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                # Chuyển hướng sau khi đăng nhập thành công
                if user.role == 'admin' or user.is_superuser:
                    return redirect('admin_dashboard')
                elif user.role == 'club_rep':
                    return redirect('club_dashboard')
                return redirect('home')
            else:
                messages.error(request, "Tên đăng nhập hoặc mật khẩu không hợp lệ.")
        else:
            messages.error(request, "Dữ liệu nhập không hợp lệ.")
    else:
        form = AuthenticationForm()
    return render(request, 'quanly/login.html', {'form': form, 'title': 'Đăng Nhập'})

def register_view(request):
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Đăng ký tài khoản thành công! Vui lòng đăng nhập.")
            return redirect('login')
    else:
        form = RegisterForm()
    return render(request, 'quanly/register.html', {'form': form, 'title': 'Đăng Ký Tài Khoản'})

def logout_view(request):
    logout(request)
    messages.info(request, "Bạn đã đăng xuất thành công.")
    return redirect('login')

@login_required(login_url='login')
def edit_profile(request):
    user = request.user
    
    if request.method == 'POST':
        # Truyền user_role vào form để xử lý logic (ví dụ: Club Rep không được đổi avatar nếu muốn chặn)
        form = UserProfileForm(request.POST, request.FILES, instance=user, user_role=user.role)
        
        if form.is_valid():
            # 1. Lưu thông tin cơ bản
            user = form.save(commit=False)
            
            # 2. Xử lý đổi mật khẩu (nếu có nhập)
            new_password = form.cleaned_data.get('new_password')
            if new_password:
                user.set_password(new_password)
                update_session_auth_hash(request, user) # Giữ trạng thái đăng nhập
                messages.success(request, "Đã cập nhật thông tin và đổi mật khẩu thành công!")
            else:
                messages.success(request, "Đã cập nhật thông tin hồ sơ!")
            
            user.save()
            return redirect('edit_profile')
    else:
        form = UserProfileForm(instance=user, user_role=user.role)

    # Xác định template base dựa trên quyền
    base_template = 'quanly/base_admin.html' if user.role == 'admin' else \
                    'quanly/base_club.html' if user.role == 'club_rep' else \
                    'quanly/base_fan.html'

    return render(request, 'quanly/edit_profile.html', {
        'form': form,
        'base_template': base_template
    })