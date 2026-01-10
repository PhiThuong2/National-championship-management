"""
AI Prediction Views - Comparison and Analytics
"""
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q, Avg
from quanly.models import AIPrediction, Prediction, Match, User, Season


@login_required(login_url='login')
def ai_vs_fan_comparison(request):
    """
    So sánh accuracy của AI vs Fans
    Hiển thị leaderboard fans có predictions tốt nhất
    """
    # Get active season
    season = Season.objects.filter(is_active=True).first()
    if not season:
        season = Season.objects.order_by('-start_date').first()
    
    # Calculate AI accuracy
    finished_matches = Match.objects.filter(status='FINISHED')
    if season:
        finished_matches = finished_matches.filter(season=season)
    
    ai_predictions = AIPrediction.objects.filter(
        match__in=finished_matches,
        is_correct__isnull=False
    )
    
    ai_total = ai_predictions.count()
    ai_correct = ai_predictions.filter(is_correct=True).count()
    ai_accuracy = (ai_correct / ai_total * 100) if ai_total > 0 else 0
    
    # Calculate top fans accuracy
    user_stats = []
    users_with_predictions = User.objects.filter(
        prediction__match__status='FINISHED'
    ).distinct()
    
    for user in users_with_predictions:
        user_predictions = Prediction.objects.filter(
            user=user,
            match__status='FINISHED'
        )
        
        total = user_predictions.count()
        if total < 3:  # Skip users with < 3 predictions
            continue
            
        correct = 0
        for pred in user_predictions:
            if (pred.predicted_home_score == pred.match.home_score and
                pred.predicted_away_score == pred.match.away_score):
                correct += 1
        
        accuracy = (correct / total * 100) if total > 0 else 0
        
        user_stats.append({
            'user': user,
            'total': total,
            'correct': correct,
            'accuracy': accuracy
        })
    
    # Sort by accuracy, then by total predictions
    user_stats.sort(key=lambda x: (x['accuracy'], x['total']), reverse=True)
    top_fans = user_stats[:10]
    
    # AI vs Average Fan accuracy
    avg_fan_accuracy = sum(u['accuracy'] for u in user_stats) / len(user_stats) if user_stats else 0
    
    # Determine the base template based on user role
    if request.user.role == 'admin':
        base_template = 'quanly/base_admin.html'
    elif request.user.role == 'club_rep':
        base_template = 'quanly/base_club.html'
    else:
        base_template = 'quanly/base_fan.html'
    
    return render(request, 'quanly/ai_vs_fan_comparison.html', {
        'ai_accuracy': ai_accuracy,
        'ai_total': ai_total,
        'ai_correct': ai_correct,
        'avg_fan_accuracy': avg_fan_accuracy,
        'top_fans': top_fans,
        'season': season,
        'base_template': base_template
    })


@login_required(login_url='login')
def ai_prediction_accuracy_dashboard(request):
    """
    Dashboard hiển thị accuracy của AI theo từng vòng đấu
    """
    season = Season.objects.filter(is_active=True).first()
    if not season:
        season = Season.objects.order_by('-start_date').first()
    
    # AI predictions by round
    round_stats = []
    if season:
        rounds = Match.objects.filter(
            season=season,
            status='FINISHED'
        ).values_list('round_number', flat=True).distinct().order_by('round_number')
        
        for round_num in rounds:
            round_matches = Match.objects.filter(
                season=season,
                round_number=round_num,
                status='FINISHED'
            )
            
            round_predictions = AIPrediction.objects.filter(
                match__in=round_matches,
                is_correct__isnull=False
            )
            
            total = round_predictions.count()
            correct = round_predictions.filter(is_correct=True).count()
            accuracy = (correct / total * 100) if total > 0 else 0
            
            round_stats.append({
                'round': round_num,
                'total': total,
                'correct': correct,
                'accuracy': accuracy
            })
    
    # Overall stats
    all_predictions = AIPrediction.objects.filter(
        is_correct__isnull=False
    )
    overall_total = all_predictions.count()
    overall_correct = all_predictions.filter(is_correct=True).count()
    overall_accuracy = (overall_correct / overall_total * 100) if overall_total > 0 else 0
    
    # Determine base template
    if request.user.role == 'admin':
        base_template = 'quanly/base_admin.html'
    elif request.user.role == 'club_rep':
        base_template = 'quanly/base_club.html'
    else:
        base_template = 'quanly/base_fan.html'
    
    return render(request, 'quanly/ai_accuracy_dashboard.html', {
        'round_stats': round_stats,
        'overall_accuracy': overall_accuracy,
        'overall_total': overall_total,
        'overall_correct': overall_correct,
        'season': season,
        'base_template': base_template
    })
