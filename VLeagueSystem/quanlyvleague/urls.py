from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

# IMPORT ĐẦY ĐỦ CÁC FILE VIEW
from quanly import views
from quanly.views import admin_views          # Chứa logic Admin mới (Mùa giải, Lịch thi đấu)
from quanly.views import ai_prediction_views  # Chứa logic AI Dự đoán
from quanly.views import ai_schedule_views    # Chứa logic AI Tạo lịch tự động
from quanly.views import club_views         # Chứa logic Club Dashboard

urlpatterns = [

    # Hỗ trợ đa ngôn ngữ
    path('i18n/', include('django.conf.urls.i18n')),
    path('admin/', admin.site.urls),

    # --- AUTH (Đăng nhập/Đăng ký) ---
    path('', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
    path('home/', views.home_view, name='home'),
    path('logout/', views.logout_view, name='logout'),
    path('settings/', views.edit_profile, name='user_settings'),
    path('profile/edit/', views.edit_profile, name='edit_profile'),

    # --- ADMIN DASHBOARD ---
    path('dashboard-admin/', views.admin_dashboard_view, name='admin_dashboard'),

    # 1. Quản lý Đội bóng
    path('dashboard/teams/', views.manage_teams, name='manage_teams'),
    path('dashboard/teams/add/', views.edit_team, name='add_team'),
    path('dashboard/teams/edit/<uuid:team_id>/', views.edit_team, name='edit_team'),
    path('dashboard/teams/delete/<uuid:team_id>/', views.delete_team, name='delete_team'),

    # 2. Quản lý Trận đấu & Mùa Giải (SỬ DỤNG ADMIN_VIEWS MỚI)
    # Lưu ý: Chúng ta dùng admin_views thay vì views để có chức năng lọc Mùa giải
    # 2. Quản lý Mùa giải (Sử dụng admin_views)
    path('dashboard/seasons/', admin_views.manage_seasons, name='manage_seasons'),
    path('dashboard/seasons/add/', admin_views.add_season, name='add_season'),
    path('dashboard/seasons/edit/<uuid:season_id>/', admin_views.edit_season, name='edit_season'),
    path('dashboard/seasons/delete/<uuid:season_id>/', admin_views.delete_season, name='delete_season'),
    # Đường dẫn cũ để tương thích, trỏ về hàm add_season
    path('dashboard/season/create/', admin_views.add_season, name='create_season'),

    # 3. Quản lý Trận đấu (Sử dụng admin_views)
    path('dashboard/matches/', admin_views.manage_matches, name='manage_matches'),
    
    # >> DÒNG FIX LỖI "NoReverseMatch" <<
    path('dashboard/season/create/', admin_views.create_season, name='create_season'),

    path('dashboard/matches/add/', admin_views.edit_match, name='add_match'),
    path('dashboard/matches/edit/<uuid:match_id>/', admin_views.edit_match, name='edit_match'),
    path('dashboard/matches/score/<uuid:match_id>/', admin_views.update_match_score, name='update_match_score'),
    path('dashboard/matches/delete/<uuid:match_id>/', admin_views.delete_match, name='delete_match'),
    
    # Tạo lịch thủ công (Legacy)
    path('dashboard/matches/auto-generate/', admin_views.generate_schedule, name='generate_schedule'),

    # 3. AI Automatic Scheduling (Xếp lịch tự động - Mới)
    # 4. AI Automatic Scheduling (Xếp lịch tự động - Mới)
    path('admin/ai-schedule/feasibility/', ai_schedule_views.ai_schedule_feasibility_check, name='ai_schedule_feasibility_check'),
    path('admin/ai-schedule/generate/', ai_schedule_views.ai_generate_schedule_proposal, name='ai_generate_schedule_proposal'),
    path('admin/ai-schedule/proposals/', ai_schedule_views.ai_schedule_proposals, name='ai_schedule_proposals'),
    path('admin/ai-schedule/approve/', ai_schedule_views.approve_ai_schedule_proposal, name='approve_ai_schedule_proposal'),
    path('admin/ai-schedule/reject/', ai_schedule_views.reject_ai_schedule_proposal, name='reject_ai_schedule_proposal'),

    # 4. Quản lý Chuyển nhượng
    # 5. Quản lý Chuyển nhượng
    path('dashboard/transfers/', views.manage_transfers, name='manage_transfers'),
    path('dashboard/transfers/approve/<uuid:transfer_id>/', views.approve_transfer, name='approve_transfer'),
    path('dashboard/transfers/reject/<uuid:transfer_id>/', views.reject_transfer, name='reject_transfer'),

    # 5. Quản lý Users
    # 6. Quản lý Users
    path('dashboard/users/', views.manage_users, name='manage_users'),
    path('dashboard/users/toggle/<uuid:user_id>/', views.toggle_user_status, name='toggle_user_status'),
    path('dashboard/users/edit/<uuid:user_id>/', views.edit_user, name='edit_user'),
    path('dashboard/users/promote/<uuid:user_id>/', views.promote_user, name='promote_user'),
    path('dashboard/users/delete/<uuid:user_id>/', views.delete_user, name='delete_user'),

    # 6. Quản lý Cầu thủ (Admin)
    # 7. Quản lý Cầu thủ (Admin)
    path('dashboard/players/', views.manage_players, name='manage_players'),
    path('dashboard/players/add/', views.edit_player_admin, name='add_player_admin'),
    path('dashboard/players/edit/<uuid:player_id>/', views.edit_player_admin, name='edit_player_admin'),
    path('dashboard/players/delete/<uuid:player_id>/', views.delete_player_admin, name='delete_player_admin'),

    # --- CLUB REP ---
    path('club/', views.club_dashboard, name='club_dashboard'),
    path('club/player/<uuid:player_id>/', views.club_player_detail, name='club_player_detail'),
    path('club/market/', views.transfer_market, name='transfer_market'), 
    path('club/buy/<uuid:player_id>/', views.buy_player, name='buy_player'),
    path('club/transfers/', views.club_transfers, name='club_transfers'),
    path('club/respond/<uuid:transfer_id>/<str:action>/', views.respond_offer, name='respond_offer'),
    path('club/add-contract/', views.add_contract, name='add_contract'),
    path('club/players/', views.club_players_list, name='club_players_list'),
    path('club/player/<uuid:player_id>/update-avatar/', club_views.update_player_avatar, name='update_player_avatar'),

    # --- AI PREDICTIONS & ANALYTICS ---
    path('ai-vs-fans/', ai_prediction_views.ai_vs_fan_comparison, name='ai_vs_fans'),
    path('ai-accuracy/', ai_prediction_views.ai_prediction_accuracy_dashboard, name='ai_accuracy'),
    
    # API AI (Định giá)
    path('api/ai-valuation/', views.ai_valuation_api, name='ai_valuation_api'),
    
    # API Chatbot AI
    path('api/chatbot/', views.chatbot_api, name='chatbot_api'),

    # --- FAN ZONE ---
    path('teams/', views.team_list, name='team_list'),
    path('teams/<uuid:team_id>/', views.team_detail, name='team_detail'),
    path('players/<uuid:player_id>/', views.player_detail, name='player_detail'),
    path('standings/', views.standings, name='standings'),
    path('rankings/', views.player_rankings, name='player_rankings'),
    path('predict/', views.prediction_list, name='prediction_list'),
    path('predict/<uuid:match_id>/', views.predict_match, name='predict_match'),
    path('feedback/', views.send_feedback, name='send_feedback'),
    path('ticket-shop/', views.ticket_shop, name='ticket_shop'),
    path('ticket-shop/buy/<uuid:match_id>/', views.buy_ticket, name='buy_ticket'),
    path('ticket-shop/payment/<uuid:match_id>/', views.payment_gateway, name='payment_gateway'),
    path('ticket-shop/process/<uuid:match_id>/', views.process_payment, name='process_payment'),
    path('my-tickets/', views.ticket_history, name='ticket_history'),

    # --- EXPORT EXCEL ---
    path('export/players/', views.export_players_excel, name='export_players_excel'),
    path('export/teams/', views.export_teams_excel, name='export_teams'),
    path('export/contracts/', views.export_contracts_excel, name='export_contracts'),
    path('export/player/<uuid:player_id>/', views.export_player_detail, name='export_player_detail'),

    # --- AJAX ROUTES ---
    path('ajax/team/<uuid:team_id>/', views.team_detail_ajax, name='team_detail_ajax'),
    path('ajax/player/<uuid:player_id>/', views.player_detail_ajax, name='player_detail_ajax'),
    path('ajax/expiring-contracts/', club_views.expiring_contracts_ajax, name='expiring_contracts_ajax'),



]

# Cấu hình hiển thị ảnh
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)