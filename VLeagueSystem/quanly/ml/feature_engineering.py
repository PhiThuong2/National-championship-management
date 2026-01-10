"""
Feature Engineering Module for AI Match Prediction
Extracts features from historical match data for ML models
"""
import pandas as pd
from django.db.models import Q, Avg, Count, Sum
from django.utils import timezone
from datetime import timedelta
from quanly.models import Match, Team, Season, PlayerStat, MatchEvent, MatchEventType


def calculate_team_form(team, season, num_matches=5, before_date=None):
    # Lấy các trận của team (cả home và away) đã kết thúc
    matches_query = Match.objects.filter(
        Q(home_team=team) | Q(away_team=team),
        status='FINISHED' # Chỉ lấy trận đã đá
    ).order_by('-match_date')
    
    if before_date:
        matches_query = matches_query.filter(match_date__lt=before_date)
    
    # --- SỬA LỖI INDENTATION TẠI ĐÂY ---
    recent_matches = list(matches_query[:num_matches])    
    
    if not recent_matches:
        return {
            'points': 0,
            'form_string': '',
            'goals_scored': 0,
            'goals_conceded': 0,
            'avg_goals': 0.0,
            'matches_count': 0
        }
    
    points = 0
    form_list = []
    goals_scored = 0
    goals_conceded = 0
    
    for match in recent_matches:
        is_home = match.home_team == team
        team_score = match.home_score if is_home else match.away_score
        opponent_score = match.away_score if is_home else match.home_score
        
        goals_scored += team_score
        goals_conceded += opponent_score
        
        if team_score > opponent_score:
            points += 3
            form_list.append('W')
        elif team_score == opponent_score:
            points += 1
            form_list.append('D')
        else:
            form_list.append('L')
    
    return {
        'points': points,
        'form_string': ''.join(form_list),
        'goals_scored': goals_scored,
        'goals_conceded': goals_conceded,
        'avg_goals': goals_scored / len(recent_matches) if recent_matches else 0.0,
        'matches_count': len(recent_matches)
    }


def get_head_to_head_stats(home_team, away_team, season=None, num_matches=5):
    """
    Lấy lịch sử đối đầu giữa 2 đội
    """
    # Lấy các trận đối đầu giữa 2 đội
    h2h_query = Match.objects.filter(
        Q(home_team=home_team, away_team=away_team) | 
        Q(home_team=away_team, away_team=home_team),
        status='FINISHED'
    ).order_by('-match_date')
    
    if season:
        # Lấy các trận trong cùng mùa giải hoặc mùa trước
        h2h_query = h2h_query.filter(season__start_date__lte=season.start_date)
    
    h2h_matches = list(h2h_query[:num_matches])
    
    if not h2h_matches:
        return {
            'home_wins': 0,
            'draws': 0,
            'away_wins': 0,
            'avg_home_goals': 0.0,
            'avg_away_goals': 0.0,
            'total_matches': 0
        }
    
    home_wins = 0
    draws = 0
    away_wins = 0
    total_home_goals = 0
    total_away_goals = 0
    
    for match in h2h_matches:
        # Chuẩn hóa: luôn xem theo góc nhìn home_team parameter
        if match.home_team == home_team:
            home_score = match.home_score
            away_score = match.away_score
        else:
            home_score = match.away_score
            away_score = match.home_score
        
        total_home_goals += home_score
        total_away_goals += away_score
        
        if home_score > away_score:
            home_wins += 1
        elif home_score == away_score:
            draws += 1
        else:
            away_wins += 1
    
    total_matches = len(h2h_matches)
    
    return {
        'home_wins': home_wins,
        'draws': draws,
        'away_wins': away_wins,
        'avg_home_goals': total_home_goals / total_matches,
        'avg_away_goals': total_away_goals / total_matches,
        'total_matches': total_matches
    }


def calculate_home_advantage(team, season, before_date=None):
    """
    Tính lợi thế sân nhà của đội
    """
    home_matches_query = Match.objects.filter(
        home_team=team,
        season=season,
        status='FINISHED'
    )
    
    if before_date:
        home_matches_query = home_matches_query.filter(match_date__lt=before_date)
    
    home_matches = list(home_matches_query)
    
    if not home_matches:
        return {
            'home_win_rate': 0.0,
            'avg_home_goals': 0.0,
            'avg_home_conceded': 0.0,
            'home_matches_count': 0
        }
    
    wins = sum(1 for m in home_matches if m.home_score > m.away_score)
    total_goals = sum(m.home_score for m in home_matches)
    total_conceded = sum(m.away_score for m in home_matches)
    
    return {
        'home_win_rate': wins / len(home_matches),
        'avg_home_goals': total_goals / len(home_matches),
        'avg_home_conceded': total_conceded / len(home_matches),
        'home_matches_count': len(home_matches)
    }


def calculate_away_form(team, season, before_date=None):
    """
    Tính phong độ sân khách của đội
    """
    away_matches_query = Match.objects.filter(
        away_team=team,
        season=season,
        status='FINISHED'
    )
    
    if before_date:
        away_matches_query = away_matches_query.filter(match_date__lt=before_date)
    
    away_matches = list(away_matches_query)
    
    if not away_matches:
        return {
            'away_win_rate': 0.0,
            'avg_away_goals': 0.0,
            'avg_away_conceded': 0.0,
            'away_matches_count': 0
        }
    
    wins = sum(1 for m in away_matches if m.away_score > m.home_score)
    total_goals = sum(m.away_score for m in away_matches)
    total_conceded = sum(m.home_score for m in away_matches)
    
    return {
        'away_win_rate': wins / len(away_matches),
        'avg_away_goals': total_goals / len(away_matches),
        'avg_away_conceded': total_conceded / len(away_matches),
        'away_matches_count': len(away_matches)
    }


def get_recent_cards(team, season, num_matches=5, before_date=None):
    """
    Đếm thẻ phạt gần đây của đội
    """
    # Lấy các trận gần nhất
    matches_query = Match.objects.filter(
        Q(home_team=team) | Q(away_team=team),
        season=season,
        status='FINISHED'
    ).order_by('-match_date')
    
    if before_date:
        matches_query = matches_query.filter(match_date__lt=before_date)
    
    recent_matches = list(matches_query[:num_matches])
    
    if not recent_matches:
        return {
            'yellow_cards': 0,
            'red_cards': 0,
            'avg_cards_per_match': 0.0
        }
    
    yellow_cards = 0
    red_cards = 0
    
    for match in recent_matches:
        # Đếm thẻ của team trong trận này
        yellow_cards += MatchEvent.objects.filter(
            match=match,
            team=team,
            event_type=MatchEventType.YELLOW_CARD
        ).count()
        
        red_cards += MatchEvent.objects.filter(
            match=match,
            team=team,
            event_type=MatchEventType.RED_CARD
        ).count()
    
    return {
        'yellow_cards': yellow_cards,
        'red_cards': red_cards,
        'avg_cards_per_match': (yellow_cards + red_cards) / len(recent_matches) if recent_matches else 0.0
    }


from quanly.views.utils import calculate_standings

def build_match_features(home_team, away_team, match_date, season):
    """
    Tổng hợp tất cả features cho một trận đấu
    """
    # Lấy BXH tại thời điểm trước trận đấu
    standings = calculate_standings(season=season, before_date=match_date)
    
    # Tìm rank và points của 2 đội
    home_rank = next((item['rank'] for item in standings if item['team'].id == home_team.id), 14) # Default rank low
    away_rank = next((item['rank'] for item in standings if item['team'].id == away_team.id), 14)
    
    home_points = next((item['points'] for item in standings if item['team'].id == home_team.id), 0)
    away_points = next((item['points'] for item in standings if item['team'].id == away_team.id), 0)

    # Lấy các features cũ
    home_form = calculate_team_form(home_team, season, num_matches=5, before_date=match_date)
    away_form = calculate_team_form(away_team, season, num_matches=5, before_date=match_date)
    
    h2h = get_head_to_head_stats(home_team, away_team, season=season)
    
    home_advantage = calculate_home_advantage(home_team, season, before_date=match_date)
    away_away_form = calculate_away_form(away_team, season, before_date=match_date)
    
    home_cards = get_recent_cards(home_team, season, before_date=match_date)
    away_cards = get_recent_cards(away_team, season, before_date=match_date)
    
    # Tổng hợp thành feature dict
    features = {
        # Ranking features (Priority)
        'home_rank': home_rank,
        'away_rank': away_rank,
        'rank_diff': home_rank - away_rank, # Âm tốt cho Home (Rank 1 vs 10 => 1-10 = -9)
        'points_diff': home_points - away_points,
        
        # Home team features
        'home_form_points': home_form['points'],
        'home_goals_scored_recent': home_form['goals_scored'],
        'home_goals_conceded_recent': home_form['goals_conceded'],
        'home_avg_goals': home_form['avg_goals'],
        'home_win_rate_home': home_advantage['home_win_rate'],
        'home_avg_goals_home': home_advantage['avg_home_goals'],
        'home_yellow_cards': home_cards['yellow_cards'],
        'home_red_cards': home_cards['red_cards'],
        
        # Away team features
        'away_form_points': away_form['points'],
        'away_goals_scored_recent': away_form['goals_scored'],
        'away_goals_conceded_recent': away_form['goals_conceded'],
        'away_avg_goals': away_form['avg_goals'],
        'away_win_rate_away': away_away_form['away_win_rate'],
        'away_avg_goals_away': away_away_form['avg_away_goals'],
        'away_yellow_cards': away_cards['yellow_cards'],
        'away_red_cards': away_cards['red_cards'],
        
        # Head-to-head features
        'h2h_home_wins': h2h['home_wins'],
        'h2h_draws': h2h['draws'],
        'h2h_away_wins': h2h['away_wins'],
        'h2h_avg_home_goals': h2h['avg_home_goals'],
        'h2h_avg_away_goals': h2h['avg_away_goals'],
    }
    
    return features


def build_training_dataset(season=None, min_matches=10):
    """
    Xây dựng dataset để training ML model
    """
    # Lấy các trận đã kết thúc
    matches_query = Match.objects.filter(status='FINISHED').select_related(
        'home_team', 'away_team', 'season'
    ).order_by('match_date')
    
    if season:
        matches_query = matches_query.filter(season=season)
    
    matches = list(matches_query)
    
    if len(matches) < min_matches:
        raise ValueError(f"Không đủ dữ liệu! Cần ít nhất {min_matches} trận, hiện có {len(matches)}")
    
    data = []
    
    for match in matches:
        try:
            features = build_match_features(
                match.home_team,
                match.away_team,
                match.match_date,
                match.season
            )
            
            # Thêm labels (kết quả thực tế)
            features['home_score'] = match.home_score
            features['away_score'] = match.away_score
            
            # Thêm result label (1=Home win, 0=Draw, -1=Away win)
            if match.home_score > match.away_score:
                features['result'] = 1
            elif match.home_score == match.away_score:
                features['result'] = 0
            else:
                features['result'] = -1
            
            data.append(features)
        except Exception as e:
            # Bỏ qua trận không đủ data
            print(f"Skipping match {match.id}: {str(e)}")
            continue
    
    df = pd.DataFrame(data)
    return df