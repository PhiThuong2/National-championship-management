import random
# Import Models
from quanly.models import (
    User, Team, Player, Match, TransferRequest, Contract, Season, MatchStatus,
    PlayerStat, Coach, RegistrationType, MatchEvent, MatchEventType, AIPrediction
)
from django.core.management import call_command
import threading
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import user_passes_test, login_required
from django.contrib import messages
from django.db.models import Sum
from django.http import HttpResponse
from django.core.paginator import Paginator
from django.db.models import Q
from django.db import transaction
import uuid
from django.urls import reverse
import openpyxl
import json
# Tìm dòng import datetime và sửa thành:
from datetime import timedelta, datetime
from django.forms import modelform_factory, DateInput


# Import Forms
from quanly.forms import TeamForm, MatchForm, PlayerForm, PromoteUserForm, GenerateScheduleForm, MatchScoreForm, MatchEventForm

# Import Utils
from .utils import (
    paginate_and_search, calculate_standings, 
    get_top_scorers, get_top_assists, get_top_goalkeepers, get_top_cards
)
def is_admin(user):
    return user.is_authenticated and (user.role == 'admin' or user.is_superuser)
# ==============================================================================
# 1. DASHBOARD ADMIN (TRUNG TÂM ĐIỀU HÀNH)
# ==============================================================================
@user_passes_test(is_admin, login_url='home')
def admin_dashboard_view(request):
    # 1. KPI CƠ BẢN
    total_users = User.objects.count()
    total_players = Player.objects.count()
    
    # Danh sách đội để hiển thị bảng chi tiết
    teams_list = Team.objects.all().order_by('name')
    total_teams = teams_list.count()
    total_stadiums = Team.objects.values('stadium').distinct().count()

    # Thống kê Chuyển nhượng
    completed_transfers = TransferRequest.objects.filter(status='approved')
    total_transfer_count = completed_transfers.count()
    total_money = completed_transfers.aggregate(Sum('transfer_fee'))['transfer_fee__sum'] or 0

    # Lấy 5 giao dịch gần nhất
    recent_transfers = TransferRequest.objects.filter(status='approved').order_by('-request_date')[:5]

    # 2. DỮ LIỆU BIỂU ĐỒ (CHART)
    # Biểu đồ 1: Top chi tiêu
    spending_data = []
    for t in teams_list:
        # Tính tổng tiền đội này đã chi (Là đội MUA - to_team)
        spent = TransferRequest.objects.filter(to_team=t, status='approved').aggregate(Sum('transfer_fee'))['transfer_fee__sum'] or 0
        if spent > 0: 
            spending_data.append({'name': t.name, 'spent': spent})
    
    # Sắp xếp giảm dần và lấy Top 5
    spending_data.sort(key=lambda x: x['spent'], reverse=True)
    top_5 = spending_data[:5]

    # Biểu đồ 2: Cơ cấu cầu thủ (Nội/Ngoại)
    vn_players = Player.objects.filter(nationality='Việt Nam').count()
    foreign_players = total_players - vn_players

    # 3. XÁC ĐỊNH MÙA GIẢI ACTIVE (để tính BXH và Thống kê)
    active_season = Season.objects.filter(is_active=True).first()
    if not active_season:
        active_season = Season.objects.order_by('-start_date').first()

    # 4. BẢNG XẾP HẠNG ĐỘI BÓNG (BXH) - Top 10
    standings = calculate_standings(season=active_season)[:10]
    
    # 5. XẾP HẠNG CÁ NHÂN
    top_scorers = get_top_scorers(season=active_season, limit=5)
    top_assists = get_top_assists(season=active_season, limit=5)
    top_goalkeepers = get_top_goalkeepers(season=active_season, limit=5)
    top_cards = get_top_cards(season=active_season, limit=5)

    return render(request, 'quanly/admin_dashboard.html', {
        # KPIs
        'total_users': total_users,
        'total_teams': total_teams,
        'total_stadiums': total_stadiums,
        'total_players': total_players,
        'total_transfer_count': total_transfer_count,
        'money_value': total_money,
        
        # Lists
        'teams_list': teams_list,
        'recent_transfers': recent_transfers,

        # Chart Data (format JSON cho JavaScript)
        'chart_labels': json.dumps([x['name'] for x in top_5]),
        'chart_values': json.dumps([x['spent'] for x in top_5]),
        'vn_players': vn_players,
        'foreign_players': foreign_players,
        
        # BXH và Xếp hạng
        'standings': standings,
        'top_scorers': top_scorers,
        'top_assists': top_assists,
        'top_goalkeepers': top_goalkeepers,
        'top_cards': top_cards,
        'active_season': active_season
    })

# ==============================================================================
# 2. QUẢN LÝ NGƯỜI DÙNG (USERS)
# ==============================================================================
@user_passes_test(is_admin, login_url='home')
def manage_users(request):
    users = User.objects.all().order_by('-date_joined')

    # Lọc theo vai trò (Role)
    role_filter = request.GET.get('role')
    if role_filter:
        users = users.filter(role=role_filter)

    # Áp dụng Tìm kiếm và Phân trang (dùng hàm tiện ích)
    context = paginate_and_search(request, users, ['email', 'first_name', 'username'])
    
    # Truyền lại role_filter để giữ trạng thái dropdown
    context['role_filter'] = role_filter
    
    return render(request, 'quanly/manage_users.html', context)

@user_passes_test(is_admin, login_url='home')
def toggle_user_status(request, user_id):
    user = get_object_or_404(User, pk=user_id)
    
    if user == request.user:
        messages.error(request, "Bạn không thể khóa chính mình!")
        return redirect('manage_users')

    user.is_active = not user.is_active
    user.save()
    
    status = "Mở khóa" if user.is_active else "Khóa"
    messages.success(request, f"Đã {status} tài khoản {user.email}")
    return redirect('manage_users')

@user_passes_test(is_admin, login_url='home')
def promote_user(request, user_id):
    user = get_object_or_404(User, pk=user_id)
    
    if request.method == 'POST':
        form = PromoteUserForm(request.POST, instance=user)
        if form.is_valid():
            u = form.save(commit=False)
            u.role = 'club_rep' # Thăng chức lên Đại diện CLB
            u.save()
            messages.success(request, f"Đã cấp quyền quản lý {u.team.name} cho {u.email}")
            return redirect('manage_users')
    else:
        form = PromoteUserForm(instance=user)

    return render(request, 'quanly/form_admin.html', {
        'form': form, 
        'title': f'Cấp quyền quản lý cho: {user.first_name}'
    })

# ==============================================================================
# 3. QUẢN LÝ ĐỘI BÓNG (TEAMS)
# ==============================================================================
@user_passes_test(is_admin, login_url='home')
def manage_teams(request):
    teams = Team.objects.all().order_by('name')
    # Tìm kiếm theo tên đội hoặc thành phố
    context = paginate_and_search(request, teams, ['name', 'city', 'stadium'])
    return render(request, 'quanly/manage_teams.html', context)

@user_passes_test(is_admin, login_url='home')
def edit_team(request, team_id=None):
    # 1. Lấy link quay về (Nếu không có thì về trang danh sách mặc định)
    # Ưu tiên lấy từ POST (khi bấm Save), nếu không có thì lấy từ GET (khi vừa vào trang)
    next_url = request.POST.get('next') or request.GET.get('next') or reverse('manage_teams')

    team = get_object_or_404(Team, pk=team_id) if team_id else None
    title = f"Sửa đội: {team.name}" if team else "Thêm Đội Bóng Mới"

    if request.method == "POST":
        form = TeamForm(request.POST, request.FILES, instance=team)
        if form.is_valid():
            form.save()
            messages.success(request, "Lưu dữ liệu thành công!")
            # 2. Quay về đúng cái link đã lưu (bao gồm cả page=..., q=...)
            return redirect(next_url)
    else:
        form = TeamForm(instance=team)

    return render(request, 'quanly/form_admin.html', {
        'form': form, 
        'title': title,
        'next_url': next_url # 3. Truyền biến này ra giao diện để Form lưu lại
    })

@user_passes_test(is_admin, login_url='home')
def edit_player_admin(request, player_id=None):
    # 1. Lấy link quay về
    next_url = request.POST.get('next') or request.GET.get('next') or reverse('manage_players')

    if player_id:
        player = get_object_or_404(Player, pk=player_id)
        title = f"Sửa cầu thủ: {player.name}"
    else:
        player = None
        title = "Thêm Cầu Thủ Mới (Admin)"

    if request.method == "POST":
        form = PlayerForm(request.POST, request.FILES, instance=player)
        if form.is_valid():
            form.save()
            messages.success(request, "Đã lưu thông tin cầu thủ!")
            # 2. Quay về chốn cũ
            return redirect(next_url)
    else:
        form = PlayerForm(instance=player)

    return render(request, 'quanly/form_admin.html', {
        'form': form, 
        'title': title,
        'next_url': next_url # 3. Truyền biến này ra giao diện
    })

# ==============================================================================
# 4. QUẢN LÝ CẦU THỦ (PLAYERS)
# ==============================================================================
@user_passes_test(is_admin, login_url='home')
def manage_players(request):
    players = Player.objects.all().order_by('team', 'name')

    # Lọc theo Đội bóng (Trước khi tìm kiếm)
    team_id = request.GET.get('team')
    
    # Chỉ lọc nếu team_id có giá trị thực sự và KHÔNG PHẢI là chữ 'None'
    if team_id and team_id != 'None': 
        try:
            players = players.filter(team_id=team_id)
            
            # (Phần phân trang lại giữ nguyên)
            from django.core.paginator import Paginator
            paginator = Paginator(players, 15)
            context['page_obj'] = paginator.get_page(request.GET.get('page'))
            context['team_filter'] = team_id
        except:
            pass # Nếu ID lỗi thì bỏ qua, không lọc nữa

    # Tìm kiếm và Phân trang (15 cầu thủ/trang)
# 1. Xử lý lọc Đội bóng trước
    team_id = request.GET.get('team')
    
    # Chỉ lọc nếu có ID thật và KHÔNG PHẢI chữ 'None'
    if team_id and team_id != 'None':
        try:
            players = players.filter(team_id=team_id)
        except:
            pass # Bỏ qua nếu ID lỗi
    else:
        team_id = '' # Reset về rỗng nếu là None

    # 2. Sau đó mới Tìm kiếm & Phân trang
    context = paginate_and_search(request, players, ['name'], items_per_page=15)
    
    # 3. Bổ sung dữ liệu vào context để template dùng
    context['teams'] = Team.objects.all()
    context['team_filter'] = team_id # Truyền giá trị đã làm sạch (không còn chữ None)
    
    return render(request, 'quanly/manage_players.html', context)    # Truyền thêm danh sách đội để làm dropdown lọc
    context['teams'] = Team.objects.all()
    context['team_filter'] = team_id

    return render(request, 'quanly/manage_players.html', context)

@user_passes_test(is_admin, login_url='home')
def edit_player_admin(request, player_id=None):
    if player_id:
        player = get_object_or_404(Player, pk=player_id)
        title = f"Sửa cầu thủ: {player.name}"
    else:
        player = None
        title = "Thêm Cầu Thủ Mới"

    if request.method == "POST":
        form = PlayerForm(request.POST, request.FILES, instance=player)
        if form.is_valid():
            form.save()
            messages.success(request, "Đã lưu thông tin cầu thủ!")
            return redirect('manage_players')
    else:
        form = PlayerForm(instance=player)

    return render(request, 'quanly/form_admin.html', {'form': form, 'title': title})

@user_passes_test(is_admin, login_url='home')
def delete_player_admin(request, player_id):
    player = get_object_or_404(Player, pk=player_id)
    player.delete()
    messages.success(request, "Đã xóa cầu thủ!")
    return redirect('manage_players')

# ==============================================================================
# 4.1. QUẢN LÝ MÙA GIẢI (SEASONS) - NEW
# ==============================================================================
@user_passes_test(is_admin, login_url='home')
def manage_seasons(request):
    seasons = Season.objects.all().order_by('-start_date')
    return render(request, 'quanly/manage_seasons.html', {'seasons': seasons})

# --- Hàm bổ sung để tương thích với URL cũ và Template mới ---
@user_passes_test(is_admin, login_url='home')
def add_season(request):
    return edit_season(request, season_id=None)

@user_passes_test(is_admin, login_url='home')
def create_season(request):
    return edit_season(request, season_id=None)
# -----------------------------------------------------------

@user_passes_test(is_admin, login_url='home')
def edit_season(request, season_id=None):
    # Tạo Form động cho Season
    SeasonForm = modelform_factory(Season, fields=['name', 'start_date', 'end_date', 'is_active'], 
                                   widgets={'start_date': DateInput(attrs={'type': 'date'}), 
                                            'end_date': DateInput(attrs={'type': 'date'})})

    season = get_object_or_404(Season, pk=season_id) if season_id else None
    title = f"Sửa Mùa Giải: {season.name}" if season else "Tạo Mùa Giải Mới"

    if request.method == 'POST':
        form = SeasonForm(request.POST, instance=season)
        if form.is_valid():
            # Nếu user chọn active mùa này, các mùa khác phải inactive
            if form.cleaned_data.get('is_active'):
                Season.objects.update(is_active=False)
            form.save()
            messages.success(request, "Đã lưu thông tin mùa giải!")
            return redirect('manage_seasons')
    else:
        form = SeasonForm(instance=season)

    return render(request, 'quanly/form_admin.html', {'form': form, 'title': title})

@user_passes_test(is_admin, login_url='home')
def delete_season(request, season_id):
    season = get_object_or_404(Season, pk=season_id)
    season.delete()
    messages.success(request, "Đã xóa mùa giải!")
    return redirect('manage_seasons')

# ==============================================================================
# 5. QUẢN LÝ TRẬN ĐẤU (MATCHES)
# ==============================================================================
# --- 13. QUẢN LÝ TRẬN ĐẤU (FIXED: LỌC THEO MÙA GIẢI) ---
# quanly/views/admin_views.py

@user_passes_test(is_admin, login_url='home')
def manage_matches(request):
    # 1. Lấy danh sách mùa giải
    seasons = Season.objects.all().order_by('-start_date')
    
    # --- ĐOẠN CODE DEBUG (KIỂM TRA DỮ LIỆU) ---
    print("================ KIỂM TRA MÙA GIẢI ================")
    print(f"Số lượng mùa giải tìm thấy: {seasons.count()}")
    for s in seasons:
        print(f"- Tên: {s.name} (ID: {s.id})")
    print("===================================================")
    # -------------------------------------------------------

    # 2. Logic xác định mùa giải Active
    selected_season_id = request.GET.get('season')
    active_season = None

    if selected_season_id:
        active_season = Season.objects.filter(id=selected_season_id).first()
    
    if not active_season:
        active_season = Season.objects.filter(is_active=True).first()
        # Nếu không có active, lấy cái đầu tiên trong danh sách
        if not active_season and seasons.exists():
            active_season = seasons.first()

    # 3. Lọc dữ liệu
    matches = Match.objects.all().order_by('match_date')
    teams = Team.objects.all().order_by('name')

    # Lọc theo mùa giải
    if active_season:
        matches = matches.filter(season=active_season)

    # Lọc theo đội
    team_filter = request.GET.get('team_id', '').strip()
    if team_filter and team_filter != 'None':
        matches = matches.filter(Q(home_team_id=team_filter) | Q(away_team_id=team_filter))

    # Tìm kiếm
    query = request.GET.get('q', '').strip()
    if query:
        matches = matches.filter(Q(home_team__name__icontains=query) | Q(away_team__name__icontains=query))

    # 4. Phân trang
    paginator = Paginator(matches, 10)
    page_obj = paginator.get_page(request.GET.get('page'))

    # Fetch AI Predictions for displayed matches
    current_matches = list(page_obj.object_list)
    ai_predictions_query = AIPrediction.objects.filter(
        match__in=current_matches
    ).select_related('match')
    
    ai_predictions_map = {
        pred.match.id: pred for pred in ai_predictions_query
    }

    return render(request, 'quanly/manage_matches.html', {
        'seasons': seasons,             # <--- QUAN TRỌNG: Biến này phải có ở đây
        'active_season': active_season,
        'teams': teams,
        'page_obj': page_obj,
        'query': query,
        'team_filter': team_filter,
        'ai_predictions_map': ai_predictions_map,
    })

# ==============================================================================
# 6. DUYỆT CHUYỂN NHƯỢNG (TRANSFERS)
# ==============================================================================
@user_passes_test(is_admin, login_url='home')
def manage_transfers(request):
    transfers = TransferRequest.objects.all().order_by('-request_date')
    return render(request, 'quanly/manage_transfers.html', {'transfers': transfers})

@user_passes_test(is_admin, login_url='home')
def approve_transfer(request, transfer_id):
    transfer = get_object_or_404(TransferRequest, pk=transfer_id)
    
    if transfer.status != 'approved':
        # 1. Chuyển cầu thủ sang đội mới
        player = transfer.player
        player.team = transfer.to_team
        player.save()
        
        # 2. Cập nhật trạng thái đơn
        transfer.status = 'approved'
        transfer.save()
        messages.success(request, f"Đã duyệt! {player.name} chính thức về {transfer.to_team.name}.")
    
    return redirect('manage_transfers')

@user_passes_test(is_admin, login_url='home')
def reject_transfer(request, transfer_id):
    transfer = get_object_or_404(TransferRequest, pk=transfer_id)
    transfer.status = 'rejected'
    transfer.save()
    messages.warning(request, "Đã từ chối yêu cầu chuyển nhượng.")
    return redirect('manage_transfers')

# ==============================================================================
# 7. TÍNH NĂNG XUẤT EXCEL (ADMIN REPORT)
# ==============================================================================
@user_passes_test(is_admin, login_url='home')
def export_teams_excel(request):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Danh Sach Doi Bong"
    
    # Header
    ws.append(['Tên đội', 'Sân vận động', 'Thành phố'])
    
    # Data
    for t in Team.objects.all():
        ws.append([t.name, t.stadium, t.city])
        
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename="DS_Doi_Bong.xlsx"'
    wb.save(response)
    return response
# --- XUẤT DANH SÁCH CẦU THỦ (Dùng chung cho Admin & Club Rep) ---
@login_required(login_url='login')
def export_players_excel(request):
    # Kiểm tra quyền: Chỉ Admin hoặc Club Rep mới được tải
    if request.user.role == 'fan':
        return redirect('home')

    # Tạo file Excel
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Danh Sach Cau Thu"

    # Header
    ws.append(['Tên cầu thủ', 'Đội bóng', 'Vị trí', 'Số áo', 'Quốc tịch', 'Trạng thái'])

    # Lấy dữ liệu tùy theo vai trò
    if request.user.role == 'admin' or request.user.is_superuser:
        # Admin lấy toàn bộ
        players = Player.objects.all().order_by('team', 'name')
    elif request.user.role == 'club_rep' and request.user.team:
        # Club Rep chỉ lấy đội mình
        players = Player.objects.filter(team=request.user.team).order_by('name')
    else:
        players = []

    # Ghi dữ liệu
    for p in players:
        team_name = p.team.name if p.team else "Tự do"
        ws.append([p.name, team_name, p.get_position_display(), p.jersey_number, p.nationality, p.get_status_display()])

    # Trả về file
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename="Danh_sach_cau_thu.xlsx"'
    
    wb.save(response)
    return response

@user_passes_test(is_admin, login_url='home')
def delete_team(request, team_id):
    team = get_object_or_404(Team, pk=team_id)
    team.delete()
    messages.success(request, "Đã xóa đội bóng thành công!")
    return redirect('manage_teams')

@user_passes_test(is_admin, login_url='home')
def delete_match(request, match_id):
    match = get_object_or_404(Match, pk=match_id)
    match.delete()
    messages.success(request, "Đã xóa trận đấu thành công!")
    return redirect('manage_matches')

# --- CẤP QUYỀN VÀ GÁN ĐỘI BÓNG ---
@user_passes_test(is_admin, login_url='home')
def promote_user(request, user_id):
    user = get_object_or_404(User, pk=user_id)
    
    if request.method == 'POST':
        # Nạp dữ liệu từ form (Đội bóng admin vừa chọn)
        form = PromoteUserForm(request.POST, instance=user)
        
        if form.is_valid():
            u = form.save(commit=False)
            u.role = 'club_rep' # 1. Tự động đổi vai trò thành Đại diện CLB
            # u.team đã được form gán tự động từ dropdown
            u.save() # 2. Lưu cả Role và Team vào Database
            
            messages.success(request, f"Đã bổ nhiệm {u.email} làm quản lý: {u.team.name}")
            return redirect('manage_users')
    else:
        form = PromoteUserForm(instance=user)

    return render(request, 'quanly/form_admin.html', {
        'form': form, 
        'title': f'Cấp quyền quản lý cho: {user.first_name}'
    })

# --- 10. CHỈNH SỬA NGƯỜI DÙNG TOÀN DIỆN ---
@user_passes_test(is_admin, login_url='home')
def edit_user(request, user_id):
    user = get_object_or_404(User, pk=user_id)
    
    # Không cho sửa chính mình (để tránh tự hủy quyền Admin)
    if user == request.user:
        messages.warning(request, "Bạn không thể tự sửa vai trò của chính mình tại đây!")
        return redirect('manage_users')

    if request.method == 'POST':
        form = UserEditForm(request.POST, instance=user)
        if form.is_valid():
            # Logic kiểm tra: Nếu chọn Role là Fan/Admin thì phải xóa Team đi
            user_editing = form.save(commit=False)
            
            if user_editing.role != 'club_rep':
                user_editing.team = None # Xóa đội nếu không phải Club Rep
            
            user_editing.save()
            messages.success(request, f"Đã cập nhật thông tin cho {user_editing.email}")
            return redirect('manage_users')
    else:
        form = UserEditForm(instance=user)

    return render(request, 'quanly/form_admin.html', {
        'form': form, 
        'title': f'Chỉnh sửa thành viên: {user.email}'
    })

# --- 11. XÓA NGƯỜI DÙNG (DELETE PERMANENTLY) ---
@user_passes_test(is_admin, login_url='home')
def delete_user(request, user_id):
    user = get_object_or_404(User, pk=user_id)
    
    # 1. Bảo vệ an toàn: Không cho phép tự xóa chính mình
    if user == request.user:
        messages.error(request, "NGUY HIỂM: Bạn không thể tự xóa tài khoản Admin của chính mình!")
        return redirect('manage_users')

    # 2. Bảo vệ dữ liệu: Nếu là Superuser khác thì cũng nên chặn (tùy chọn)
    if user.is_superuser:
        messages.error(request, "Không thể xóa Superuser khác. Hãy hạ quyền họ trước.")
        return redirect('manage_users')

    # 3. Thực hiện xóa
    try:
        email = user.email
        user.delete()
        messages.success(request, f"Đã xóa vĩnh viễn tài khoản: {email}")
    except Exception as e:
        messages.error(request, f"Lỗi khi xóa: {str(e)}")
        
    return redirect('manage_users')
# --- 12. TẠO LỊCH (PHIÊN BẢN CHUYÊN NGHIỆP - V-LEAGUE) ---
@user_passes_test(is_admin, login_url='home')
def generate_schedule(request):
    if request.method == 'POST':
        form = GenerateScheduleForm(request.POST)
        if form.is_valid():
            try:
                season = form.cleaned_data['season']
                start_date = form.cleaned_data['start_date']

                # 1. Xóa lịch cũ của mùa giải này
                deleted_count, _ = Match.objects.filter(season=season).delete()

                # 2. Lấy danh sách đội bóng
                teams = list(Team.objects.all().order_by('name'))
                
                if len(teams) < 2:
                    messages.error(request, "❌ Lỗi: Cần ít nhất 2 đội bóng để tạo lịch thi đấu! Vui lòng thêm đội bóng trước.")
                    return redirect('manage_matches')

                # 3. Xử lý số đội lẻ (thêm đội "nghỉ" nếu cần)
                num_teams = len(teams)
                has_bye = num_teams % 2 != 0
                if has_bye:
                    num_teams += 1  # Tạm tính với đội nghỉ

                # 4. Tính số vòng đấu (mỗi đội gặp nhau 2 lần: lượt đi và lượt về)
                rounds_per_leg = num_teams - 1
                total_rounds = rounds_per_leg * 2

                # 5. Khung giờ thi đấu chuyên nghiệp V-League (thường đá cuối tuần)
                # Thứ 7: 17:00, 18:00, 19:15
                # Chủ nhật: 17:00, 18:00, 19:15
                time_slots = [
                    {'h': 17, 'm': 0},   # Chiều sớm
                    {'h': 18, 'm': 0},   # Chiều muộn
                    {'h': 19, 'm': 15},  # Tối
                ]

                # 6. Thuật toán Round-Robin chuyên nghiệp
                def generate_round_robin_fixtures(team_list):
                    """Tạo lịch thi đấu vòng tròn (Round-Robin)"""
                    n = len(team_list)
                    if n % 2 == 1:
                        team_list.append(None)  # Đội nghỉ
                        n += 1
                    
                    fixtures = []
                    mid = n // 2
                    
                    for round_num in range(n - 1):
                        round_fixtures = []
                        for i in range(mid):
                            home = team_list[i]
                            away = team_list[n - 1 - i]
                            
                            # Đảo lượt đi/về để công bằng
                            if round_num % 2 == 0:
                                round_fixtures.append((home, away))
                            else:
                                round_fixtures.append((away, home))
                        
                        fixtures.append(round_fixtures)
                        # Xoay vòng: giữ đội đầu, xoay các đội còn lại
                        team_list.insert(1, team_list.pop())
                    
                    return fixtures

                # 7. Tạo lịch lượt đi
                fixtures_leg1 = generate_round_robin_fixtures(teams.copy())
                matches_leg1 = []
                count_created = 0

                # Đảm bảo ngày bắt đầu là cuối tuần (Thứ 7 hoặc Chủ nhật)
                start_weekday = start_date.weekday()  # 5=Thứ 7, 6=Chủ nhật
                if start_weekday < 5:  # Nếu là ngày trong tuần, chuyển sang Thứ 7
                    days_to_saturday = 5 - start_weekday
                    current_date = start_date + timedelta(days=days_to_saturday)
                elif start_weekday == 6:  # Nếu là Chủ nhật, chuyển sang Thứ 7 tuần sau
                    current_date = start_date + timedelta(days=6)
                else:
                    current_date = start_date
                
                first_match_date = current_date  # Lưu ngày trận đầu tiên thực tế

                # Tạo các trận đấu lượt đi
                for round_idx, round_fixtures in enumerate(fixtures_leg1):
                    # Mỗi vòng đấu diễn ra trong 2 ngày (Thứ 7 và Chủ nhật)
                    round_date = current_date
                    
                    # Phân bổ trận đấu cho Thứ 7 và Chủ nhật
                    saturday_matches = round_fixtures[:len(round_fixtures)//2 + 1]
                    sunday_matches = round_fixtures[len(round_fixtures)//2 + 1:]
                    
                    # Thứ 7
                    for home_team, away_team in saturday_matches:
                        if home_team and away_team:  # Bỏ qua đội nghỉ
                            slot = random.choice(time_slots)
                            match_time = datetime(
                                round_date.year, round_date.month, round_date.day,
                                slot['h'], slot['m']
                            )
                            
                            match = Match.objects.create(
                                season=season,
                                home_team=home_team,
                                away_team=away_team,
                                match_date=match_time,
                                round_number=round_idx + 1,
                                status=MatchStatus.SCHEDULED
                            )
                            matches_leg1.append(match)
                            count_created += 1
                    
                    # Chủ nhật
                    if sunday_matches:
                        sunday_date = round_date + timedelta(days=1)
                        for home_team, away_team in sunday_matches:
                            if home_team and away_team:
                                slot = random.choice(time_slots)
                                match_time = datetime(
                                    sunday_date.year, sunday_date.month, sunday_date.day,
                                    slot['h'], slot['m']
                                )
                                
                                match = Match.objects.create(
                                    season=season,
                                    home_team=home_team,
                                    away_team=away_team,
                                    match_date=match_time,
                                    round_number=round_idx + 1,
                                    status=MatchStatus.SCHEDULED
                                )
                                matches_leg1.append(match)
                                count_created += 1
                    
                    # Chuyển sang tuần sau (Thứ 7 tiếp theo)
                    current_date += timedelta(days=7)

                # 8. Tạo lịch lượt về (đảo sân)
                # Khoảng cách giữa lượt đi và lượt về: ít nhất bằng số vòng lượt đi + 2 tuần nghỉ
                break_weeks = 2  # Nghỉ 2 tuần giữa 2 lượt
                return_start_date = current_date + timedelta(days=break_weeks * 7)
                
                for match_leg1 in matches_leg1:
                    # Tính ngày đấu lượt về (giữ nguyên khoảng cách tương đối so với trận đầu tiên)
                    days_since_first = (match_leg1.match_date.date() - first_match_date).days
                    return_date = return_start_date + timedelta(days=days_since_first)
                    
                    # Đảm bảo là cuối tuần
                    return_weekday = return_date.weekday()
                    if return_weekday < 5:
                        days_to_saturday = 5 - return_weekday
                        return_date = return_date + timedelta(days=days_to_saturday)
                    elif return_weekday == 6:
                        return_date = return_date + timedelta(days=6)
                    
                    slot = random.choice(time_slots)
                    return_time = datetime(
                        return_date.year, return_date.month, return_date.day,
                        slot['h'], slot['m']
                    )
                    
                    Match.objects.create(
                        season=season,
                        home_team=match_leg1.away_team,  # Đảo sân
                        away_team=match_leg1.home_team,
                        match_date=return_time,
                        round_number=match_leg1.round_number + rounds_per_leg,
                        status=MatchStatus.SCHEDULED
                    )
                    count_created += 1

                messages.success(
                    request, 
                    f"✅ Đã tạo lịch thi đấu thành công! Tổng số trận: {count_created} trận | "
                    f"Số vòng đấu: {total_rounds} vòng | Số đội tham gia: {len(teams)} đội"
                )
                return redirect('manage_matches')
                
            except Exception as e:
                messages.error(request, f"❌ Lỗi khi tạo lịch: {str(e)}")
                return redirect('manage_matches')
    else:
        form = GenerateScheduleForm()

    return render(request, 'quanly/form_admin.html', {'form': form, 'title': 'Tạo Lịch Thi Đấu Tự Động'})


# --- 14. SỬA TRẬN ĐẤU (GIỮ NGUYÊN TRANG) ---
@user_passes_test(is_admin, login_url='home')
def edit_match(request, match_id=None):
    # Lấy URL trang trước đó để quay về sau khi lưu
    next_url = request.POST.get('next') or request.GET.get('next') or reverse('manage_matches')
    
    match = get_object_or_404(Match, pk=match_id) if match_id else None
    title = "Cập nhật Tỉ số / Giờ đá" if match else "Thêm Trận Đấu"

    if request.method == "POST":
        form = MatchForm(request.POST, instance=match)
        if form.is_valid():
            form.save()
            messages.success(request, "Cập nhật trận đấu thành công!")
            return redirect(next_url)
    else:
        form = MatchForm(instance=match)

    return render(request, 'quanly/form_admin.html', {
        'form': form, 
        'title': title,
        'next_url': next_url
    })

# --- 15. XÓA TRẬN ĐẤU ---
@user_passes_test(is_admin, login_url='home')
def delete_match(request, match_id):
    match = get_object_or_404(Match, pk=match_id)
    match.delete()
    messages.success(request, "Đã xóa trận đấu!")
    return redirect('manage_matches')


# --- 16. CẬP NHẬT TỈ SỐ VÀ SỰ KIỆN (CÓ VALIDATION & TỰ ĐỘNG CHẠY AI) ---
@user_passes_test(is_admin, login_url='home')
def update_match_score(request, match_id):
    """Cập nhật tỉ số, sự kiện và TỰ ĐỘNG chạy AI dự đoán"""
    match = get_object_or_404(Match, pk=match_id)
    next_url = request.GET.get('next') or reverse('manage_matches')
    
    existing_events = MatchEvent.objects.filter(match=match).order_by('minute', 'created_at')
    home_players = Player.objects.filter(team=match.home_team).order_by('name')
    away_players = Player.objects.filter(team=match.away_team).order_by('name')
    all_players = list(home_players) + list(away_players)
    
    if request.method == 'POST':
        score_form = MatchScoreForm(request.POST, instance=match)
        
        if score_form.is_valid():
            # 1. Lấy dữ liệu form
            new_match_data = score_form.cleaned_data
            new_home_score = new_match_data.get('home_score', 0) or 0
            new_away_score = new_match_data.get('away_score', 0) or 0
            
            # 2. Thu thập sự kiện từ request
            event_count = int(request.POST.get('event_count', 0))
            pending_events = [] 
            
            counted_home_goals = 0
            counted_away_goals = 0
            
            # Đếm sự kiện cũ
            if not request.POST.get('clear_events'):
                for e in existing_events:
                    if e.event_type == 'GOAL':
                        if e.team == match.home_team: counted_home_goals += 1
                        elif e.team == match.away_team: counted_away_goals += 1

            # Đếm sự kiện mới
            for i in range(event_count):
                event_type = request.POST.get(f'event_{i}_type')
                player_id = request.POST.get(f'event_{i}_player')
                team_id = request.POST.get(f'event_{i}_team')
                minute = request.POST.get(f'event_{i}_minute')
                notes = request.POST.get(f'event_{i}_notes', '')
                
                if not event_type or not team_id: continue
                
                if event_type == 'GOAL':
                    if str(team_id) == str(match.home_team.id): counted_home_goals += 1
                    elif str(team_id) == str(match.away_team.id): counted_away_goals += 1
                
                pending_events.append({
                    'type': event_type, 'player_id': player_id, 'team_id': team_id,
                    'minute': minute, 'notes': notes
                })

            # 3. Validation
            error_msg = None
            if counted_home_goals != new_home_score:
                error_msg = f"❌ Lỗi: Tỉ số Đội nhà là {new_home_score} nhưng nhập {counted_home_goals} bàn."
            elif counted_away_goals != new_away_score:
                error_msg = f"❌ Lỗi: Tỉ số Đội khách là {new_away_score} nhưng nhập {counted_away_goals} bàn."
            
            if error_msg:
                messages.error(request, error_msg)
                return render(request, 'quanly/update_match_score.html', {
                    'match': match, 'score_form': score_form, 'existing_events': existing_events,
                    'home_players': home_players, 'away_players': away_players, 
                    'all_players': all_players, 'next_url': next_url
                })

            # 4. Lưu dữ liệu & Chạy AI
            try:
                with transaction.atomic():
                    score_form.save()
                    
                    if 'clear_events' in request.POST:
                        MatchEvent.objects.filter(match=match).delete()
                    
                    # Lưu sự kiện mới & update PlayerStat
                    for item in pending_events:
                        try:
                            player = Player.objects.get(pk=item['player_id']) if item['player_id'] else None
                            team = Team.objects.get(pk=item['team_id'])
                            
                            MatchEvent.objects.create(
                                match=match, player=player, team=team,
                                event_type=item['type'],
                                minute=int(item['minute']) if item['minute'] else None,
                                notes=item['notes']
                            )
                            
                            if player:
                                stat, _ = PlayerStat.objects.get_or_create(
                                    player=player, season=match.season,
                                    defaults={'goals': 0, 'assists': 0, 'saves': 0, 'yellow_cards': 0, 'red_cards': 0, 'matches_played': 0}
                                )
                                if item['type'] == 'GOAL': stat.goals += 1
                                elif item['type'] == 'ASSIST': stat.assists += 1
                                elif item['type'] == 'SAVE': stat.saves += 1
                                elif item['type'] == 'YELLOW_CARD': stat.yellow_cards += 1
                                elif item['type'] == 'RED_CARD': stat.red_cards += 1
                                stat.save()
                        except (Player.DoesNotExist, Team.DoesNotExist):
                            continue
                    
                    # Cập nhật trạng thái trận đấu thành FINISHED
                    if match.status != 'FINISHED':
                        match.status = 'FINISHED'
                        match.save()
                        
                        # === [TÍNH ĐIỂM THƯỞNG DỰ ĐOÁN] ===
                        from quanly.models import Prediction
                        predictions = Prediction.objects.filter(match=match)
                        
                        # Kết quả thực tế
                        actual_home = match.home_score
                        actual_away = match.away_score
                        
                        # Xác định kết quả (Thắng/Thua/Hòa)
                        if actual_home > actual_away:
                            actual_result = 'home_win'
                        elif actual_home < actual_away:
                            actual_result = 'away_win'
                        else:
                            actual_result = 'draw'
                        
                        for pred in predictions:
                            # Kết quả dự đoán
                            pred_home = pred.predicted_home_score
                            pred_away = pred.predicted_away_score
                            
                            if pred_home > pred_away:
                                pred_result = 'home_win'
                            elif pred_home < pred_away:
                                pred_result = 'away_win'
                            else:
                                pred_result = 'draw'
                            
                            # Tính điểm
                            if pred_home == actual_home and pred_away == actual_away:
                                # Đúng tỉ số chính xác: 100 điểm
                                points = 100
                            elif pred_result == actual_result:
                                # Đúng kết quả (Thắng/Thua/Hòa): 50 điểm
                                points = 50
                            else:
                                # Sai: 10 điểm (khuyến khích tham gia)
                                points = 10
                            
                            # Lưu điểm
                            pred.points_earned = points
                            pred.save()
                            
                            # Cộng điểm cho user
                            pred.user.reward_points += points
                            pred.user.save()
                        
                        print(f"🎯 [REWARD] Đã tính điểm cho {predictions.count()} dự đoán!")
                        # ================================

                # === [KÍCH HOẠT AI TỰ ĐỘNG] ===
                def run_ai_pipeline():
                    print(f"🤖 [AI AUTO] Đang phân tích lại sau trận {match}...")
                    try:
                        # 1. Học lại (Training nhanh)
                        call_command('train_prediction_model', min_matches=5)
                        # 2. Dự đoán tương lai
                        call_command('generate_predictions')
                        print("✅ [AI AUTO] Đã cập nhật trí tuệ nhân tạo!")
                    except Exception as e:
                        print(f"❌ [AI AUTO] Lỗi: {e}")

                # Chạy ngầm (không làm admin phải chờ)
                threading.Thread(target=run_ai_pipeline).start()
                # ==============================

                messages.success(request, "✅ Đã lưu tỉ số! AI đang tự động phân tích dữ liệu mới...")
                return redirect(next_url)
                    
            except Exception as e:
                messages.error(request, f"Có lỗi xảy ra: {str(e)}")

    else:
        score_form = MatchScoreForm(instance=match)
    
    return render(request, 'quanly/update_match_score.html', {
        'match': match, 'score_form': score_form, 'existing_events': existing_events,
        'home_players': home_players, 'away_players': away_players,
        'all_players': all_players, 'next_url': next_url
    })