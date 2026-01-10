from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Q, Avg, Count, Sum
from django.contrib import messages
from django.http import HttpResponse
import openpyxl
from quanly.forms import FeedbackForm
from django.utils import timezone

# Import các Models cần thiết
from quanly.models import Match, Team, Player, Prediction, User, Feedback, Season, PlayerStat, AIPrediction

# Import hàm tiện ích tìm kiếm & phân trang
from .utils import (
    paginate_and_search, calculate_standings, 
    get_top_scorers, get_top_assists, get_top_goalkeepers, get_top_cards, get_top_interceptions
)
@login_required(login_url='login')
def home_view(request):
    """
    Trang chủ Fan: Lịch thi đấu có LỌC THEO VÒNG & TRẠNG THÁI DỰ ĐOÁN.
    """
    # 1. Lấy mùa giải hiện tại
    try:
        current_season = Season.objects.get(is_active=True)
    except Season.DoesNotExist:
        current_season = Season.objects.order_by('-start_date').first()

    matches = []
    rounds = [] 
    selected_round = request.GET.get('round')
    filter_status = request.GET.get('status')

    # 2. Lấy dự đoán CỦA USER
    user_predictions = Prediction.objects.filter(user=request.user)
    predictions_map = {
        p.match.id: f"{p.predicted_home_score} - {p.predicted_away_score}" 
        for p in user_predictions
    }
    predicted_match_ids = list(predictions_map.keys())

    if current_season:
        base_query = Match.objects.filter(season=current_season).order_by('match_date')
        
        # A. Lấy danh sách vòng
        rounds = base_query.values_list('round_number', flat=True).distinct().order_by('round_number')

        # B. Xử lý lọc theo vòng
        if selected_round and selected_round != 'all':
            base_query = base_query.filter(round_number=selected_round)
        else:
            # Mặc định lấy vòng sắp đá
            next_match = base_query.filter(status='SCHEDULED').first()
            if next_match and not selected_round:
                selected_round = next_match.round_number
                base_query = base_query.filter(round_number=selected_round)
            elif not selected_round and rounds:
                selected_round = rounds[0]

        # C. Xử lý lọc trạng thái
        matches_in_round = list(base_query)
        
        if filter_status == 'predicted':
            matches = [m for m in matches_in_round if m.id in predicted_match_ids]
        elif filter_status == 'not_predicted':
            matches = [m for m in matches_in_round if m.id not in predicted_match_ids]
        else:
            matches = matches_in_round

    # 4. Lấy AI predictions cho các trận đấu
    ai_predictions_query = AIPrediction.objects.filter(
        match__in=matches
    ).select_related('match')
    
    ai_predictions_map = {
        pred.match.id: pred for pred in ai_predictions_query
    }
    
    # 5. Tính BXH và Thống kê
    standings = calculate_standings(season=current_season)
    top_scorers = get_top_scorers(season=current_season, limit=5)
    top_assists = get_top_assists(season=current_season, limit=5)
    top_interceptions = get_top_interceptions(season=current_season, limit=5)
    
    # Cập nhật: Thêm Top Cứu Thua (Găng Tay Vàng)
    top_saves_raw = get_top_goalkeepers(season=current_season, limit=5)
    top_saves = [{'player': stat.player, 'count': stat.saves} for stat in top_saves_raw]
    
    top_cards = get_top_cards(season=current_season, limit=5)
    
    return render(request, 'quanly/home.html', {
        'user': request.user,
        'season': current_season,
        'matches': matches,
        'predictions_map': predictions_map,
        'ai_predictions_map': ai_predictions_map,  # Thêm AI predictions
        'standings': standings,
        
        # Dữ liệu cho bộ lọc
        'rounds': rounds,
        'selected_round': int(selected_round) if selected_round and selected_round != 'all' else None,
        'filter_status': filter_status,
        
        # Thống kê
        'top_scorers': top_scorers,
        'top_assists': top_assists,
        'top_interceptions': top_interceptions,
        'top_saves': top_saves,
        'top_cards': top_cards,
    })

@login_required(login_url='login')
def team_list(request):
    """
    Xem danh sách các đội bóng (Có Tìm kiếm & Phân trang).
    """
    teams = Team.objects.all().order_by('name')
    
    # Áp dụng hàm tiện ích: Tìm theo Tên đội hoặc Thành phố
    context = paginate_and_search(request, teams, ['name', 'city'], items_per_page=8)
    
    return render(request, 'quanly/team_list.html', context)

@login_required(login_url='login')
def team_detail(request, team_id):
    """
    Xem chi tiết một đội bóng và danh sách cầu thủ của đội đó.
    """
    team = get_object_or_404(Team, pk=team_id)
    players = Player.objects.filter(team=team).order_by('jersey_number')
    
    return render(request, 'quanly/team_detail.html', {
        'team': team,
        'players': players
    })

@login_required(login_url='login')
def player_detail(request, player_id):
    """
    Xem hồ sơ chi tiết của một cầu thủ kèm thống kê.
    """
    player = get_object_or_404(Player, pk=player_id)
    
    # Tính tổng thống kê từ bảng PlayerStat (Giả sử bạn đã có model PlayerStat)
    # Nếu chưa có dữ liệu thì trả về 0
    stats = PlayerStat.objects.filter(player=player).aggregate(
        total_goals=Sum('goals'),
        total_assists=Sum('assists'),
        total_yellow=Sum('yellow_cards'),
        total_red=Sum('red_cards'),
        total_matches=Sum('matches_played')
    )
    
    return render(request, 'quanly/player_detail.html', {
        'player': player,
        'stats': stats # Truyền biến stats ra ngoài template
    })

# --- 2. BẢNG XẾP HẠNG (AUTO CALCULATE) ---
# Hàm này dùng cho trang xem full BXH riêng biệt (nếu có)
@login_required(login_url='login')
def standings(request):
    # Get all seasons for dropdown
    seasons = Season.objects.all().order_by('-start_date')
    
    # Determine selected season
    selected_season_id = request.GET.get('season')
    if selected_season_id:
        active_season = Season.objects.filter(id=selected_season_id).first()
    else:
        # Default to active season or most recent
        active_season = Season.objects.filter(is_active=True).first()
        if not active_season:
            active_season = seasons.first()
    
    # Calculate standings for selected season
    standings_list = calculate_standings(season=active_season)
    
    return render(request, 'quanly/standings.html', {
        'standings': standings_list,
        'seasons': seasons,
        'active_season': active_season
    })

# --- 3. FAN ZONE (TƯƠNG TÁC) ---

@login_required(login_url='login')
def prediction_list(request):
    """
    Hiển thị danh sách trận đấu để dự đoán (Trang riêng).
    """
    matches = Match.objects.filter(status='SCHEDULED').order_by('match_date')
    
    # Ở trang này chỉ cần check True/False để disable nút, nên dùng ID list là ok
    predicted_ids = Prediction.objects.filter(user=request.user).values_list('match_id', flat=True)
    
    # Lấy AI predictions cho các trận này
    ai_predictions = AIPrediction.objects.filter(match__in=matches).select_related('match')
    ai_predictions_map = {pred.match.id: pred for pred in ai_predictions}
    
    return render(request, 'quanly/prediction_list.html', {
        'matches': matches,
        'predicted_ids': predicted_ids,
        'ai_predictions_map': ai_predictions_map
    })

@login_required(login_url='login')
def predict_match(request, match_id):
    """
    Xử lý hành động gửi dự đoán tỉ số.
    """
    if request.method == 'POST':
        match = get_object_or_404(Match, pk=match_id)
        
        # Kiểm tra trùng lặp lần cuối
        if not Prediction.objects.filter(user=request.user, match=match).exists():
            Prediction.objects.create(
                user=request.user,
                match=match,
                predicted_home_score=request.POST.get('home_score'),
                predicted_away_score=request.POST.get('away_score')
            )
            messages.success(request, "Dự đoán của bạn đã được ghi nhận! Chúc may mắn.")
        else:
            messages.warning(request, "Bạn đã dự đoán trận này rồi.")
    
    # Quay về trang trước đó (có thể là home hoặc prediction_list)
    next_url = request.POST.get('next') or request.GET.get('next') or 'home'
    return redirect(next_url)

@login_required(login_url='login')
def send_feedback(request):
    """
    Gửi phản hồi/đóng góp ý kiến cho BTC.
    """
    if request.method == 'POST':
        Feedback.objects.create(
            user=request.user,
            title=request.POST.get('title'),
            content=request.POST.get('content'),
            rating=request.POST.get('rating')
        )
        messages.success(request, "Cảm ơn đóng góp quý báu của bạn!")
        return redirect('home')
        
    return render(request, 'quanly/feedback.html')

# --- 4. TIỆN ÍCH XUẤT EXCEL (CHO FAN) ---

def export_player_detail(request, player_id):
    p = get_object_or_404(Player, pk=player_id)
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = f"Ho So {p.name}"
    ws.append(['THÔNG TIN', 'CHI TIẾT'])
    ws.append(['Họ và tên', p.name])
    ws.append(['Câu lạc bộ', p.team.name if p.team else "Cầu thủ tự do"])
    ws.append(['Vị trí thi đấu', p.get_position_display()])
    ws.append(['Số áo', p.jersey_number])
    ws.append(['Quốc tịch', p.nationality])
    ws.append(['Ngày sinh', p.date_of_birth])
    ws.append(['Trạng thái', p.get_status_display()])
    
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="HoSo_{p.name}.xlsx"'
    wb.save(response)
    return response

# --- 5. BXH CÁ NHÂN (Trang xem full) ---
@login_required(login_url='login')
def player_rankings(request):
    active_season = Season.objects.filter(is_active=True).first()
    if not active_season:
        active_season = Season.objects.order_by('-start_date').first()

    # --- LOGIC CHỌN TEMPLATE ---
    if request.user.role == 'admin':
        base_template = 'quanly/base_admin.html'
    elif request.user.role == 'club_rep':
        base_template = 'quanly/base_club.html'
    else:
        base_template = 'quanly/base_fan.html'
    
    # --- LẤY DỮ LIỆU THỐNG KÊ ---
    top_scorers = get_top_scorers(season=active_season, limit=10)
    top_assists = get_top_assists(season=active_season, limit=10)
    top_interceptions = get_top_interceptions(season=active_season, limit=10)
    
    # THAY ĐỔI Ở ĐÂY: Lấy Top Thủ Môn (Cứu thua) thay vì Thẻ Phạt
    top_saves = get_top_goalkeepers(season=active_season, limit=10) 
    
    return render(request, 'quanly/player_rankings.html', {
        'top_scorers': top_scorers,
        'top_assists': top_assists,
        'top_interceptions': top_interceptions,
        'top_saves': top_saves, # Truyền biến này thay vì top_cards
        'active_season': active_season,
        'base_template': base_template
    })

# --- 6. AJAX VIEWS (CHO MODAL POPUP) ---

@login_required(login_url='login')
def team_detail_ajax(request, team_id):
    """Trả về HTML chi tiết đội bóng (Cầu thủ + Lịch thi đấu)"""
    from django.db.models import Q # Import ở đây hoặc đầu file đều được
    team = get_object_or_404(Team, pk=team_id)
    
    # 1. Lấy danh sách cầu thủ
    players = Player.objects.filter(team=team).order_by('jersey_number')
    
    # 2. Lấy lịch thi đấu của đội này
    try:
        current_season = Season.objects.get(is_active=True)
    except Season.DoesNotExist:
        current_season = Season.objects.order_by('-start_date').first()

    team_matches = Match.objects.filter(
        Q(home_team=team) | Q(away_team=team)
    )
    
    if current_season:
        team_matches = team_matches.filter(season=current_season)
        
    team_matches = team_matches.order_by('match_date')
    
    return render(request, 'quanly/partials/team_modal_content.html', {
        'team': team,
        'players': players,
        'team_matches': team_matches
    })

@login_required(login_url='login')
def player_detail_ajax(request, player_id):
    """Trả về HTML chi tiết cầu thủ CHO MODAL"""
    player = get_object_or_404(Player, pk=player_id)
    
    # --- THÊM PHẦN TÍNH TOÁN THỐNG KÊ NÀY ---
    stats = PlayerStat.objects.filter(player=player).aggregate(
        total_goals=Sum('goals'),
        total_assists=Sum('assists'),
        total_yellow=Sum('yellow_cards'),
        total_red=Sum('red_cards'),
        total_matches=Sum('matches_played'),
        total_saves=Sum('saves') # Thêm cứu thua nếu cần
    )
    # ----------------------------------------
    
    return render(request, 'quanly/partials/player_modal_content.html', {
        'player': player,
        'stats': stats  # Truyền biến stats sang template modal
    })

# --- 7. TICKET SHOP (MUA VÉ BẰNG ĐIỂM THƯỞNG) ---
import qrcode
from io import BytesIO
from django.core.files import File
from quanly.models import Ticket

@login_required(login_url='login')
def ticket_shop(request):
    """Hiển thị danh sách các trận đấu sắp tới để mua vé."""
    matches = Match.objects.filter(status='SCHEDULED').order_by('match_date')[:12]
    
    return render(request, 'quanly/ticket_shop.html', {
        'matches': matches
    })

@login_required(login_url='login')
def buy_ticket(request, match_id):
    """Bước 1: Chuyển hướng sang trang Thanh Toán (Payment Gateway)."""
    match = get_object_or_404(Match, pk=match_id)
    
    if request.method == 'POST':
        # Tính toán sơ bộ để hiển thị bên trang thanh toán
        try:
            points_used = int(request.POST.get('points_used', 0))
            quantity = int(request.POST.get('quantity', 1))
        except ValueError:
            points_used = 0
            quantity = 1
            
        if points_used < 0: points_used = 0
        if points_used > request.user.reward_points: points_used = request.user.reward_points
        if quantity < 1: quantity = 1
        
        # Lưu thông tin tạm vào session để sang trang thanh toán dùng
        request.session['ticket_cart'] = {
            'match_id': str(match.id), # UUID to string
            'points_used': points_used,
            'quantity': quantity
        }
        
        return redirect('payment_gateway', match_id=match.id)
    
    return redirect('ticket_shop')

@login_required(login_url='login')
def payment_gateway(request, match_id):
    """Bước 2: Trang giả lập Cổng thanh toán (MoMo/Bank)."""
    match = get_object_or_404(Match, pk=match_id)
    
    # Lấy thông tin từ session (nếu có)
    cart = request.session.get('ticket_cart', {})
    
    # Verify exact match
    if str(cart.get('match_id')) != str(match.id):
        points_used = 0
        quantity = 1
    else:
        points_used = cart.get('points_used', 0)
        quantity = cart.get('quantity', 1)
    
    base_price = 100000
    total_price = base_price * quantity
    
    # Cap points for display consistency
    max_points = total_price // 100
    if points_used > max_points:
        points_used = max_points
        
    discount = points_used * 100
    final_price = total_price - discount
    if final_price < 0: final_price = 0
    
    return render(request, 'quanly/payment_gateway.html', {
        'match': match,
        'points_used': points_used,
        'quantity': quantity,
        'discount': discount,
        'total_price': total_price,
        'final_price': final_price
    })

@login_required(login_url='login')
def process_payment(request, match_id):
    """Bước 3: Xử lý thanh toán thành công & Tạo Vé + QR Code."""
    match = get_object_or_404(Match, pk=match_id)
    
    if request.method == 'POST':
        try:
            points_used = int(request.POST.get('points_used', 0))
            quantity = int(request.POST.get('quantity', 1))
            final_price_total = int(request.POST.get('final_price', 100000))
        except:
            points_used = 0
            quantity = 1
            final_price_total = 100000
            
        # 0. Cap points usage to total order value
        total_value = 100000 * quantity
        max_points = total_value // 100
        if points_used > max_points:
            points_used = max_points

        # 1. Trừ điểm người dùng (nếu có dùng)
        if points_used > 0 and request.user.reward_points >= points_used:
            request.user.reward_points -= points_used
            request.user.save()
            points_deducted = points_used
        else:
            points_deducted = 0
        
        # Calculate price per ticket for recording (simplified)
        # Assuming discount applies to the total order, we can split it or just assign to the first ticket?
        # Or more fairly: distribute discount?
        # Let's simple model: First ticket gets discount or just record total paid.
        # But `Ticket` model has `final_amount`. Let's average it.
        price_per_ticket = final_price_total // quantity
        
        created_tickets = []
        
        # 2. Loop create tickets
        remaining_discount = points_deducted * 100
        
        for i in range(quantity):
            # Calculate discount for this specific ticket
            # We apply discount sequentially until exhausted
            this_ticket_discount = min(100000, remaining_discount)
            remaining_discount -= this_ticket_discount
            
            ticket_final = 100000 - this_ticket_discount
            
            ticket = Ticket.objects.create(
                user=request.user,
                match=match,
                price=100000,
                discount=this_ticket_discount, 
                final_amount=ticket_final,
                payment_method='momo', 
                status='paid'
            )
            created_tickets.append(ticket)
            
            # 3. Tạo QR Code for each ticket
            qr_data = f"TICKET-{ticket.ticket_code}|{match.home_team.name}vs{match.away_team.name}|{match.match_date}|{request.user.username}"
            
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(qr_data)
            qr.make(fit=True)
            
            img = qr.make_image(fill_color="black", back_color="white")
            
            blob = BytesIO()
            img.save(blob, 'PNG')
            ticket.qr_code.save(f'{ticket.ticket_code}.png', File(blob), save=True)
        
        # Xóa session
        if 'ticket_cart' in request.session:
            del request.session['ticket_cart']
            
        messages.success(request, f"✅ Thanh toán thành công! {quantity} vé của bạn đã được khởi tạo.")
        return redirect('ticket_history')
        
    return redirect('ticket_shop')

@login_required(login_url='login')
def ticket_history(request):
    """Danh sách vé đã mua."""
    tickets = Ticket.objects.filter(user=request.user).order_by('-purchase_date')
    return render(request, 'quanly/ticket_history.html', {'tickets': tickets})