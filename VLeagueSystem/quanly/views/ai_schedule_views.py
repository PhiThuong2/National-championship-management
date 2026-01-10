"""
AI Schedule Generation Views for Admin
Provides feasibility checking, schedule generation, and proposal approval workflow
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import user_passes_test
from django.contrib import messages
from django.db import transaction
from django.utils import timezone
import json

from quanly.models import Season, Match, Team
from quanly.ml.schedule_generator import (
    AIScheduleGenerator,
    FeasibilityChecker,
    get_schedule_config_from_settings
)


def is_admin(user):
    """Check if user is admin"""
    return user.is_authenticated and user.role == 'admin'


@user_passes_test(is_admin, login_url='home')
def ai_schedule_feasibility_check(request):
    """
    Step 1: Check if a season is feasible for AI schedule generation
    """
    seasons = Season.objects.all().order_by('-start_date')
    
    if request.method == 'POST':
        season_id = request.POST.get('season')
        season = get_object_or_404(Season, id=season_id)
        
        # Load config and check feasibility
        config = get_schedule_config_from_settings()
        checker = FeasibilityChecker(season, config)
        is_feasible, message = checker.check()
        
        # Store result in session for next step
        request.session['ai_schedule_season_id'] = str(season.id)
        request.session['ai_schedule_feasible'] = is_feasible
        request.session['ai_schedule_message'] = message
        
        context = {
            'season': season,
            'is_feasible': is_feasible,
            'message': message,
            'config': config,
            'teams': Team.objects.all(),
            'seasons': seasons
        }
        
        return render(request, 'quanly/ai_schedule_feasibility_result.html', context)
    
    context = {
        'seasons': seasons
    }
    return render(request, 'quanly/ai_schedule_feasibility_check.html', context)


@user_passes_test(is_admin, login_url='home')
def ai_generate_schedule_proposal(request):
    """
    Step 2: Generate AI schedule proposal (preview mode)
    """
    # Check if feasibility was done
    season_id = request.session.get('ai_schedule_season_id')
    is_feasible = request.session.get('ai_schedule_feasible', False)
    
    if not season_id or not is_feasible:
        messages.error(request, "Vui lòng kiểm tra tính khả thi trước khi tạo lịch")
        return redirect('ai_schedule_feasibility_check')
    
    season = get_object_or_404(Season, id=season_id)
    
    if request.method == 'POST':
        # Generate schedule
        config = get_schedule_config_from_settings()
        generator = AIScheduleGenerator(season, config)
        
        success, matches_data, gen_message = generator.generate()
        
        if not success:
            messages.error(request, f"Không thể tạo lịch: {gen_message}")
            return redirect('ai_schedule_feasibility_check')
        
        # Store matches data in session (as JSON)
        # Convert to serializable format
        serializable_matches = []
        for match in matches_data:
            serializable_matches.append({
                'home_team_id': str(match['home_team'].id),
                'away_team_id': str(match['away_team'].id),
                'match_date': match['match_date'].isoformat(),
                'round_number': match['round_number']
            })
        
        request.session['ai_schedule_matches'] = serializable_matches
        request.session['ai_schedule_gen_message'] = gen_message
        
        # Group matches by round for display
        rounds = {}
        for match in matches_data:
            r = match['round_number']
            if r not in rounds:
                rounds[r] = []
            rounds[r].append(match)
        
        # Calculate statistics
        stats = {
            'total_matches': len(matches_data),
            'total_rounds': len(rounds),
            'matches_per_round': len(matches_data) // len(rounds) if rounds else 0,
        }
        
        context = {
            'season': season,
            'matches_data': matches_data,
            'rounds': dict(sorted(rounds.items())),
            'stats': stats,
            'gen_message': gen_message
        }
        
        return render(request, 'quanly/ai_schedule_preview.html', context)
    
    context = {
        'season': season
    }
    return render(request, 'quanly/ai_schedule_generate.html', context)


@user_passes_test(is_admin, login_url='home')
def ai_schedule_proposals(request):
    """
    List of generated schedule proposals (for multi-proposal workflow)
    For now, this just shows the current session proposal
    """
    season_id = request.session.get('ai_schedule_season_id')
    matches_data = request.session.get('ai_schedule_matches')
    
    if not season_id or not matches_data:
        messages.info(request, "Không có lịch đề xuất nào. Vui lòng tạo lịch mới.")
        return redirect('ai_schedule_feasibility_check')
    
    season = get_object_or_404(Season, id=season_id)
    
    # Reconstruct matches from session data
    teams_dict = {str(t.id): t for t in Team.objects.all()}
    reconstructed_matches = []
    
    for match_data in matches_data:
        home_team = teams_dict.get(match_data['home_team_id'])
        away_team = teams_dict.get(match_data['away_team_id'])
        
        if home_team and away_team:
            reconstructed_matches.append({
                'home_team': home_team,
                'away_team': away_team,
                'match_date': timezone.datetime.fromisoformat(match_data['match_date']),
                'round_number': match_data['round_number']
            })
    
    context = {
        'season': season,
        'matches_count': len(reconstructed_matches),
        'matches_preview': reconstructed_matches[:10]  # Show first 10
    }
    
    return render(request, 'quanly/ai_schedule_proposals.html', context)


@user_passes_test(is_admin, login_url='home')
def approve_ai_schedule_proposal(request, proposal_id=None):
    """
    Step 3: Approve and save the AI-generated schedule to database
    """
    if request.method != 'POST':
        return redirect('ai_schedule_proposals')
    
    season_id = request.session.get('ai_schedule_season_id')
    matches_data = request.session.get('ai_schedule_matches')
    
    if not season_id or not matches_data:
        messages.error(request, "Không tìm thấy lịch đề xuất")
        return redirect('ai_schedule_feasibility_check')
    
    season = get_object_or_404(Season, id=season_id)
    
    # Option: clear existing matches
    clear_existing = request.POST.get('clear_existing') == 'on'
    
    try:
        with transaction.atomic():
            if clear_existing:
                deleted_count, _ = Match.objects.filter(season=season).delete()
                messages.info(request, f"Đã xóa {deleted_count} trận đấu cũ")
            
            # Reconstruct and save matches
            teams_dict = {str(t.id): t for t in Team.objects.all()}
            created_count = 0
            
            for match_data in matches_data:
                home_team = teams_dict.get(match_data['home_team_id'])
                away_team = teams_dict.get(match_data['away_team_id'])
                
                if home_team and away_team:
                    Match.objects.create(
                        season=season,
                        home_team=home_team,
                        away_team=away_team,
                        match_date=timezone.datetime.fromisoformat(match_data['match_date']),
                        round_number=match_data['round_number'],
                        status='SCHEDULED',
                        home_score=0,
                        away_score=0
                    )
                    created_count += 1
            
            # Clear session
            request.session.pop('ai_schedule_season_id', None)
            request.session.pop('ai_schedule_matches', None)
            request.session.pop('ai_schedule_feasible', None)
            request.session.pop('ai_schedule_message', None)
            request.session.pop('ai_schedule_gen_message', None)
            
            messages.success(request, f"✅ Đã lưu {created_count} trận đấu vào hệ thống!")
            return redirect('manage_matches')
            
    except Exception as e:
        messages.error(request, f"Lỗi khi lưu lịch: {str(e)}")
        return redirect('ai_schedule_proposals')


@user_passes_test(is_admin, login_url='home')
def reject_ai_schedule_proposal(request, proposal_id=None):
    """
    Reject the AI-generated schedule proposal
    """
    # Clear session data
    request.session.pop('ai_schedule_season_id', None)
    request.session.pop('ai_schedule_matches', None)
    request.session.pop('ai_schedule_feasible', None)
    request.session.pop('ai_schedule_message', None)
    request.session.pop('ai_schedule_gen_message', None)
    
    messages.info(request, "Đã từ chối lịch đề xuất. Bạn có thể tạo lại lịch mới.")
    return redirect('ai_schedule_feasibility_check')
