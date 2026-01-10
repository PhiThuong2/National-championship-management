from django.core.paginator import Paginator
from django.db.models import Q
from quanly.models import Team, Match, PlayerStat, Season

def paginate_and_search(request, queryset, search_fields, items_per_page=10):
    # 1. Xử lý Tìm kiếm
    query = request.GET.get('q')
    
    # --- SỬA ĐOẠN NÀY: Chặn chữ 'None' ---
    if query and query != 'None': 
        search_query = Q()
        for field in search_fields:
            search_query |= Q(**{f"{field}__icontains": query})
        queryset = queryset.filter(search_query)
    else:
        query = '' # Nếu là None thì gán về rỗng để giao diện đẹp
    # -------------------------------------

    # 2. Xử lý Phân trang
    paginator = Paginator(queryset, items_per_page)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return {
        'page_obj': page_obj,
        'query': query,
        'paginator': paginator
    }

# ==============================================================================
# HELPER FUNCTIONS - BXH VÀ XẾP HẠNG
# ==============================================================================
def calculate_standings(season=None, before_date=None):
    """Tính BXH các đội bóng (tùy chọn theo mốc thời gian)"""
    teams = Team.objects.all()
    bxh = {t.id: {
        'team': t, 
        'points': 0, 
        'played': 0, 
        'won': 0, 
        'drawn': 0, 
        'lost': 0,
        'goals_for': 0,
        'goals_against': 0,
        'gd': 0  # Hiệu số
    } for t in teams}

    # Lấy tất cả trận đã đấu
    matches = Match.objects.filter(status='FINISHED')
    if season:
        matches = matches.filter(season=season)
    
    if before_date:
        matches = matches.filter(match_date__lt=before_date)
    
    for m in matches:
        # Cộng số trận
        bxh[m.home_team.id]['played'] += 1
        bxh[m.away_team.id]['played'] += 1
        
        # Cộng bàn thắng/bàn thua
        bxh[m.home_team.id]['goals_for'] += m.home_score
        bxh[m.home_team.id]['goals_against'] += m.away_score
        bxh[m.away_team.id]['goals_for'] += m.away_score
        bxh[m.away_team.id]['goals_against'] += m.home_score
        
        # Cộng hiệu số
        bxh[m.home_team.id]['gd'] += (m.home_score - m.away_score)
        bxh[m.away_team.id]['gd'] += (m.away_score - m.home_score)

        # Tính điểm (Thắng 3, Hòa 1, Thua 0)
        if m.home_score > m.away_score:
            bxh[m.home_team.id]['points'] += 3
            bxh[m.home_team.id]['won'] += 1
            bxh[m.away_team.id]['lost'] += 1
        elif m.home_score < m.away_score:
            bxh[m.away_team.id]['points'] += 3
            bxh[m.away_team.id]['won'] += 1
            bxh[m.home_team.id]['lost'] += 1
        else:
            bxh[m.home_team.id]['points'] += 1
            bxh[m.home_team.id]['drawn'] += 1
            bxh[m.away_team.id]['points'] += 1
            bxh[m.away_team.id]['drawn'] += 1

    # Sắp xếp: Điểm cao -> Hiệu số cao -> Bàn thắng cao -> Tên đội A-Z
    standings_list = sorted(
        bxh.values(), 
        key=lambda x: (-x['points'], -x['gd'], -x['goals_for'], x['team'].name)
    )
    
    # Thêm thứ hạng
    for idx, team_data in enumerate(standings_list, 1):
        team_data['rank'] = idx
    
    return standings_list

def get_top_scorers(season=None, limit=10):
    """Lấy Top Vua Phá Lưới: Xếp theo Bàn thắng → Nếu bằng nhau xét số Kiến tạo"""
    stats = PlayerStat.objects.all()
    if season:
        stats = stats.filter(season=season)
    
    # Sắp xếp: goals giảm dần, nếu bằng thì assists giảm dần
    top_scorers = stats.order_by('-goals', '-assists')[:limit]
    return top_scorers

def get_top_assists(season=None, limit=10):
    """Lấy Top Vua Kiến Tạo: Xếp theo số Kiến tạo → Nếu bằng nhau xét Bàn thắng"""
    stats = PlayerStat.objects.all()
    if season:
        stats = stats.filter(season=season)
    
    # Sắp xếp: assists giảm dần, nếu bằng thì goals giảm dần
    top_assists = stats.order_by('-assists', '-goals')[:limit]
    return top_assists

def get_top_goalkeepers(season=None, limit=10):
    """Lấy Top Găng Tay Vàng: Xếp theo Số lần cứu thua"""
    stats = PlayerStat.objects.filter(player__position='Goalkeeper')
    if season:
        stats = stats.filter(season=season)
    
    # Sắp xếp: saves giảm dần
    top_gks = stats.order_by('-saves')[:limit]
    return top_gks

def get_top_cards(season=None, limit=10):
    """Lấy Top Thẻ Phạt: Tính điểm (Vàng = 1, Đỏ = 3) → Điểm cao xếp đầu"""
    stats = PlayerStat.objects.all()
    if season:
        stats = stats.filter(season=season)
    
    # Tính điểm thẻ phạt cho mỗi cầu thủ
    card_scores = []
    for stat in stats:
        card_points = stat.yellow_cards * 1 + stat.red_cards * 3
        if card_points > 0:
            card_scores.append({
                'stat': stat,
                'card_points': card_points,
                'yellow_cards': stat.yellow_cards,
                'red_cards': stat.red_cards
            })
    
    # Sắp xếp theo điểm thẻ phạt giảm dần
    card_scores.sort(key=lambda x: x['card_points'], reverse=True)
    return card_scores[:limit]

def get_top_interceptions(season=None, limit=10):
    """Lấy Top Cản phá - từ MatchEvent"""
    from quanly.models import MatchEvent
    
    events = MatchEvent.objects.filter(event_type='INTERCEPTION')
    if season:
        events = events.filter(match__season=season)
    
    # Đếm số lần cản phá theo cầu thủ
    interception_count = {}
    for event in events:
        if event.player:
            player_id = event.player.id
            if player_id not in interception_count:
                interception_count[player_id] = {
                    'player': event.player,
                    'count': 0
                }
            interception_count[player_id]['count'] += 1
    
    # Sắp xếp và trả về top
    top_list = sorted(interception_count.values(), key=lambda x: x['count'], reverse=True)
    return top_list[:limit]