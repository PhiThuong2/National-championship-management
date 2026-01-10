from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.db.models import Q
import google.generativeai as genai
import openpyxl
import json

# --- ĐÂY LÀ DÒNG QUAN TRỌNG BẠN ĐANG THIẾU ---
from quanly.models import Player, Contract, TransferRequest, Team
# ---------------------------------------------

from quanly.forms import ContractForm, TransferOfferForm, PlayerForm
from .utils import paginate_and_search, calculate_standings
from django.db.models import Q
from quanly.models import Contract, Season, Match

GOOGLE_API_KEY = "AIzaSyCkBH3DBWmvoz0jW-tUd5sgON99BdWSpVw"

# --- 1. DASHBOARD CLB ---
@login_required(login_url='login')
def club_dashboard(request):
    if request.user.role != 'club_rep': return redirect('home')
    team = request.user.team
    if not team: return render(request, 'quanly/error.html', {'message': 'Chưa được gán đội bóng!'})

    total_players = Player.objects.filter(team=team).count()
    expiring_soon = Contract.objects.filter(team=team, end_date__year=2025).count()
    
    players = Player.objects.filter(team=team).order_by('jersey_number')
    contracts = Contract.objects.filter(team=team).order_by('end_date')
    
    # Tính BXH
    # 3. XÁC ĐỊNH MÙA GIẢI ACTIVE (để tính BXH)
    active_season = Season.objects.filter(is_active=True).first()
    if not active_season:
        active_season = Season.objects.order_by('-start_date').first()

    standings = calculate_standings(season=active_season)

    # Lấy lịch thi đấu của CLB
    matches = Match.objects.filter(
        Q(home_team=team) | Q(away_team=team), 
        season=active_season
    ).order_by('match_date')

    return render(request, 'quanly/club_dashboard.html', {
        'team': team,
        'total_players': total_players,
        'expiring_soon': expiring_soon,
        'matches': matches,
        'contracts': contracts,
        'standings': standings,
        'active_season': active_season
    })

# --- 2. THỊ TRƯỜNG CHUYỂN NHƯỢNG ---
@login_required(login_url='login')
def transfer_market(request):
    if request.user.role != 'club_rep': return redirect('home')
    
    my_team = request.user.team
    
    # Lấy danh sách gốc: Tất cả cầu thủ KHÔNG thuộc đội mình
    market_players = Player.objects.exclude(team=my_team).select_related('team').order_by('name')

    # --- LOGIC LỌC RIÊNG CHO TEAM ---
    team_id = request.GET.get('team') # Lấy ID đội từ thanh địa chỉ
    if team_id and team_id != 'None':
        try:
            market_players = market_players.filter(team_id=team_id)
        except:
            pass # Bỏ qua nếu ID lỗi
    
    # Sau khi lọc xong mới đưa vào hàm tìm kiếm chung (Tên, Vị trí)
    # Lưu ý: Hàm paginate_and_search sẽ xử lý tiếp phần tìm kiếm theo tên và phân trang
    context = paginate_and_search(request, market_players, ['name', 'position'], items_per_page=24)
    
    # Bổ sung danh sách tất cả các đội để hiện trong Dropdown lọc (Trừ đội mình ra)
    context['teams'] = Team.objects.exclude(id=my_team.id).order_by('name')
    context['current_team_filter'] = team_id # Để giữ lại lựa chọn trên giao diện

    return render(request, 'quanly/market.html', context)
# --- API AI ĐỊNH GIÁ CẦU THỦ (TUÂN THỦ FIFA RSTP) ---
@login_required(login_url='login')
def ai_valuation_api(request):
    """
    API định giá cầu thủ dựa trên:
    - Dữ liệu thống kê thực tế (PlayerStat, MatchEvent)
    - Tuổi, vị trí, kinh nghiệm
    - Thời hạn hợp đồng còn lại
    - Protected period theo FIFA Article 17
    """
    if request.method == 'POST':
        try:
            from datetime import datetime, timedelta
            from django.db.models import Sum, Avg, Count
            from quanly.models import PlayerStat, Contract, Season
            
            # 1. Lấy dữ liệu từ Frontend
            data = json.loads(request.body)
            player_id = data.get('player_id')
            player = Player.objects.get(pk=player_id)
            
            today = datetime.now().date()

            # 2. Thu thập dữ liệu cầu thủ chi tiết
            # Tuổi
            player_age = (today.year - player.date_of_birth.year) if player.date_of_birth else None
            
            # Thống kê tổng hợp
            player_stats = PlayerStat.objects.filter(player=player).aggregate(
                total_goals=Sum('goals'),
                total_assists=Sum('assists'),
                total_matches=Sum('matches_played'),
                total_yellows=Sum('yellow_cards'),
                total_reds=Sum('red_cards'),
                avg_goals_per_match=Avg('goals')
            )
            
            total_matches = player_stats['total_matches'] or 0
            total_goals = player_stats['total_goals'] or 0
            total_assists = player_stats['total_assists'] or 0
            
            # Tính hiệu suất
            goals_per_match = total_goals / total_matches if total_matches > 0 else 0
            
            # 3. Phân tích hợp đồng hiện tại
            current_contract = Contract.objects.filter(
                player=player,
                end_date__gte=today
            ).order_by('-end_date').first()
            
            contract_info = ""
            protected_period_status = "Không có hợp đồng hiện tại"
            contract_remaining_months = 0
            
            if current_contract:
                contract_remaining_days = (current_contract.end_date - today).days
                contract_remaining_months = contract_remaining_days / 30
                contract_age_days = (today - current_contract.start_date).days
                contract_age_years = contract_age_days / 365.25
                
                # FIFA Protected Period Check
                protected_years = 3 if (player_age and player_age < 28) else 2
                is_protected = contract_age_years < protected_years
                
                contract_info = f"""
HỢP ĐỒNG HIỆN TẠI:
- Ngày hết hạn: {current_contract.end_date.strftime('%d/%m/%Y')}
- Thời gian còn lại: {contract_remaining_months:.1f} tháng
- Tuổi hợp đồng: {contract_age_years:.1f} năm
"""
                
                if is_protected:
                    protected_period_status = f"⚠️ PROTECTED PERIOD (FIFA Article 17): Cầu thủ đang trong giai đoạn bảo vệ. Chuyển nhượng trước hạn yêu cầu bồi thường cao."
                else:
                    protected_period_status = "✓ Ngoài protected period, có thể chuyển nhượng tự do hơn"
            
            # 4. Xác định team name
            team_name = player.team.name if player.team else 'Cầu thủ tự do'
            
            # 5. Cấu hình AI
            genai.configure(api_key=GOOGLE_API_KEY)
            
            # Tìm model phù hợp
            chosen_model = 'models/gemini-1.5-flash'
            try:
                for m in genai.list_models():
                    if 'generateContent' in m.supported_generation_methods:
                        if 'flash' in m.name:
                            chosen_model = m.name
                            break
                        elif 'pro' in m.name:
                            chosen_model = m.name
            except:
                pass
            
            model = genai.GenerativeModel(chosen_model)
            
            # 6. Tạo prompt AI chi tiết
            prompt = f"""
Bạn là chuyên gia định giá cầu thủ bóng đá V-League, tuân thủ FIFA Regulations on the Status and Transfer of Players (RSTP).

THÔNG TIN CẦU THỦ:
- Tên: {player.name}
- Tuổi: {player_age if player_age else 'Chưa rõ'}
- Vị trí: {player.get_position_display()}
- Quốc tịch: {player.nationality}
- Đội hiện tại: {team_name}
- Chiều cao/Cân nặng: {player.height}cm / {player.weight}kg

THỐNG KÊ THI ĐẤU:
- Tổng số trận: {total_matches}
- Bàn thắng: {total_goals}
- Kiến tạo: {total_assists}
- Hiệu suất ghi bàn: {goals_per_match:.2f} bàn/trận
- Thẻ vàng/đỏ: {player_stats['total_yellows'] or 0}/{player_stats['total_reds'] or 0}

{contract_info}

TÌNH TRẠNG PHÁP LÝ FIFA:
{protected_period_status}

YÊU CẦU ĐỊNH GIÁ:
Dựa trên dữ liệu trên và thị trường V-League hiện tại, hãy ước tính giá trị chuyển nhượng của cầu thủ.

LƯU Ý:
1. Nếu cầu thủ trong PROTECTED PERIOD, giá trị phải CAO HƠN để bù đắp bồi thường FIFA Article 17
2. Nếu hợp đồng sắp hết (<6 tháng), giá trị có thể THẤP HƠN do CLB có thể đàm phán tự do
3. Cầu thủ trẻ (<23 tuổi) với phong độ tốt thường có giá trị TĂNG
4. Vị trí khan hiếm (GK, CF chất lượng) có giá trị CAO HƠN

TRẢ LỜI ĐÚNG FORMAT:
[GIA_MIN]: <Số VND tối thiểu>
[GIA_MAX]: <Số VND tối đa>
[NHAN_DINH]: <Phân tích chi tiết 3-4 câu về: điểm mạnh, yếu, ảnh hưởng hợp đồng, khuyến nghị>
"""
            
            response = model.generate_content(prompt)
            text = response.text
            
            # 7. Parse kết quả
            if "[GIA_MIN]:" in text and "[GIA_MAX]:" in text:
                parts = text.split("[GIA_MAX]:")
                min_part = parts[0].split("[GIA_MIN]:")[1].strip()
                
                max_analysis = parts[1].split("[NHAN_DINH]:")
                max_part = max_analysis[0].strip()
                analysis = max_analysis[1].strip() if len(max_analysis) > 1 else "Phân tích từ AI"
                
                # Làm sạch số tiền
                min_value = min_part.replace(".", "").replace(",", "").replace("VND", "").replace("₫", "").strip()
                max_value = max_part.replace(".", "").replace(",", "").replace("VND", "").replace("₫", "").strip()
                
                # Format kết quả
                result = f"""
💰 GIÁ TRỊ ƯỚC TÍNH:
   Tối thiểu: {min_value} VND
   Tối đa: {max_value} VND

📊 PHÂN TÍCH:
{analysis}

{protected_period_status}

⚖️ LƯU Ý PHÁP LÝ:
Giá trị này chỉ là tham khảo dựa trên dữ liệu thống kê. Giá trị thực tế phụ thuộc vào đàm phán giữa các CLB và tuân thủ quy định FIFA về chuyển nhượng.
"""
                
                return JsonResponse({
                    'success': True, 
                    'result': result,
                    'min_value': min_value,
                    'max_value': max_value,
                    'protected_period': is_protected if current_contract else False
                })
            else:
                # Fallback nếu AI không trả về đúng format
                response_text = f"""
💰 ĐỊNH GIÁ TỪ AI:
{text}

{protected_period_status}
"""
                return JsonResponse({'success': True, 'result': response_text})

        except Exception as e:
            return JsonResponse({'success': False, 'error': f'Lỗi định giá: {str(e)}'})

    return JsonResponse({'success': False, 'error': 'Invalid request'})
# --- 3. MUA CẦU THỦ (AJAX MODAL VERSION) ---
@login_required(login_url='login')
def buy_player(request, player_id):
    if request.user.role != 'club_rep': 
        return JsonResponse({'success': False, 'error': 'Unauthorized'}) if request.headers.get('X-Requested-With') == 'XMLHttpRequest' else redirect('home')
    
    target_player = get_object_or_404(Player, pk=player_id)
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    
    # AJAX GET: Return modal content with player data
    if request.method == 'GET' and is_ajax:
        from datetime import datetime
        from django.db.models import Sum
        from quanly.models import PlayerStat, Contract
        
        # Calculate player age
        today = datetime.now().date()
        player_age = (today.year - target_player.date_of_birth.year) if target_player.date_of_birth else None
        
        # Get player stats
        player_stats = PlayerStat.objects.filter(player=target_player).aggregate(
            total_goals=Sum('goals'),
            total_assists=Sum('assists'),
            total_matches=Sum('matches_played')
        )
        
        total_goals = player_stats['total_goals'] or 0
        total_assists = player_stats['total_assists'] or 0
        total_matches = player_stats['total_matches'] or 0
        goals_per_match = (total_goals / total_matches) if total_matches > 0 else 0
        
        # Get current contract
        current_contract = Contract.objects.filter(
            player=target_player,
            end_date__gte=today
        ).order_by('-end_date').first()
        
        contract_remaining_months = 0
        is_protected = False
        
        if current_contract:
            contract_remaining_days = (current_contract.end_date - today).days
            contract_remaining_months = contract_remaining_days / 30
            contract_age_days = (today - current_contract.start_date).days
            contract_age_years = contract_age_days / 365.25
            
            # FIFA Protected Period
            protected_years = 3 if (player_age and player_age < 28) else 2
            is_protected = contract_age_years < protected_years
        
        context = {
            'player': target_player,
            'player_age': player_age,
            'total_goals': total_goals,
            'total_assists': total_assists,
            'total_matches': total_matches,
            'goals_per_match': goals_per_match,
            'current_contract': current_contract,
            'contract_remaining_months': contract_remaining_months,
            'is_protected': is_protected
        }
        
        return render(request, 'quanly/partials/buy_player_modal.html', context)
    
    # POST: Process the offer
    if request.method == 'POST':
        # Check for duplicate offers
        if TransferRequest.objects.filter(
            player=target_player, 
            to_team=request.user.team, 
            status__in=['pending_approval', 'negotiating']
        ).exists():
            if is_ajax:
                return JsonResponse({'success': False, 'error': 'Đã gửi yêu cầu mua cầu thủ này rồi!'})
            messages.warning(request, "Đã gửi yêu cầu rồi!")
            return redirect('transfer_market')
        
        # Get form data
        transfer_fee = request.POST.get('transfer_fee')
        notes = request.POST.get('notes', '')
        
        if not transfer_fee:
            if is_ajax:
                return JsonResponse({'success': False, 'error': 'Vui lòng nhập mức giá đề nghị!'})
            messages.error(request, "Vui lòng nhập mức giá đề nghị!")
            return redirect('transfer_market')
        
        # Create transfer request
        try:
            offer = TransferRequest.objects.create(
                player=target_player,
                from_team=target_player.team,
                to_team=request.user.team,
                transfer_fee=int(transfer_fee),
                status='negotiating'
            )
            
            if is_ajax:
                return JsonResponse({
                    'success': True, 
                    'message': f'✅ Đã gửi đề nghị mua {target_player.name} với giá {int(transfer_fee):,} VND!'
                })
            
            messages.success(request, f"Đã gửi đề nghị mua {target_player.name}!")
            return redirect('club_transfers')
            
        except Exception as e:
            if is_ajax:
                return JsonResponse({'success': False, 'error': f'Lỗi: {str(e)}'})
            messages.error(request, f"Lỗi: {str(e)}")
            return redirect('transfer_market')
    
    # Non-AJAX GET: Fallback to old form page
    form = TransferOfferForm()
    return render(request, 'quanly/form_generic.html', {'form': form, 'title': f'Hỏi mua: {target_player.name}'})

# --- 4. QUẢN LÝ GIAO DỊCH ---
@login_required(login_url='login')
def club_transfers(request):
    if request.user.role != 'club_rep': return redirect('home')
    my_team = request.user.team
    return render(request, 'quanly/club_transfers.html', {
        'incoming': TransferRequest.objects.filter(from_team=my_team).order_by('-request_date'),
        'outgoing': TransferRequest.objects.filter(to_team=my_team).order_by('-request_date')
    })

# --- 5. TRẢ LỜI ĐỀ NGHỊ ---
@login_required(login_url='login')
def respond_offer(request, transfer_id, action):
    transfer = get_object_or_404(TransferRequest, pk=transfer_id)
    if request.user.team != transfer.from_team: return redirect('club_transfers')
    if action == 'accept':
        transfer.status = 'pending_approval'
        transfer.save()
        messages.success(request, "Đã đồng ý bán! Chờ Admin duyệt.")
    elif action == 'reject':
        transfer.status = 'rejected'
        transfer.save()
        messages.warning(request, "Đã từ chối bán.")
    return redirect('club_transfers')

# --- 6. TẠO HỢP ĐỒNG (AI THÔNG MINH - TUÂN THỦ FIFA & LUẬT VIỆT NAM) ---
@login_required(login_url='login')
def add_contract(request):
    if request.user.role != 'club_rep': return redirect('home')
    
    # Biến để điền vào form khi AI trả về
    initial_data = {}
    ai_suggestion_text = None

    if request.method == 'POST':
        action = request.POST.get('action')
        
        # Lấy dữ liệu cơ bản từ form (dù chưa save)
        player_id = request.POST.get('player')
        start = request.POST.get('start_date')
        end = request.POST.get('end_date')
        c_type = request.POST.get('contract_type')
        
        if action == 'ask_ai':
            # --- GỌI AI VỚI KIỂM TRA FIFA & LUẬT VIỆT NAM ---
            try:
                from datetime import datetime, timedelta
                
                player = Player.objects.get(pk=player_id) if player_id else None
                if not player:
                    messages.error(request, "Vui lòng chọn cầu thủ trước!")
                    return redirect('add_contract')
                
                # Tính tuổi cầu thủ
                today = datetime.now().date()
                player_age = (today.year - player.date_of_birth.year) if player.date_of_birth else None
                
                # Parse ngày hợp đồng
                start_date = datetime.strptime(start, '%Y-%m-%d').date() if start else today
                end_date = datetime.strptime(end, '%Y-%m-%d').date() if end else None
                
                # KIỂM TRA FIFA & LUẬT VIỆT NAM
                warnings = []
                
                # 1. Kiểm tra thời hạn hợp đồng
                if end_date:
                    contract_duration_days = (end_date - start_date).days
                    contract_duration_years = contract_duration_days / 365.25
                    
                    # Lấy mùa giải hiện tại
                    active_season = Season.objects.filter(is_active=True).first()
                    
                    # FIFA: Hợp đồng phải ít nhất đến hết mùa giải
                    if active_season and end_date < active_season.end_date:
                        warnings.append(f"⚠️ FIFA RSTP: Hợp đồng phải kéo dài ít nhất đến hết mùa giải ({active_season.end_date.strftime('%d/%m/%Y')})")
                    
                    # FIFA: Hợp đồng không nên quá 5 năm
                    if contract_duration_years > 5:
                        warnings.append(f"⚠️ FIFA RSTP: Hợp đồng không nên vượt quá 5 năm (hiện tại: {contract_duration_years:.1f} năm)")
                    
                    # Luật Việt Nam: Cầu thủ dưới 18 tuổi tối đa 3 năm
                    if player_age and player_age < 18 and contract_duration_years > 3:
                        warnings.append(f"⚠️ Luật Lao động VN: Cầu thủ dưới 18 tuổi chỉ được ký hợp đồng tối đa 3 năm")
                    
                    # Cảnh báo hợp đồng quá ngắn
                    if contract_duration_days < 30:
                        warnings.append(f"⚠️ Hợp đồng quá ngắn ({contract_duration_days} ngày), không phù hợp với hợp đồng chuyên nghiệp")
                
                # 2. Lấy thống kê cầu thủ để AI đánh giá
                player_stats = PlayerStat.objects.filter(player=player).aggregate(
                    total_goals=models.Sum('goals'),
                    total_assists=models.Sum('assists'),
                    total_matches=models.Sum('matches_played')
                )
                
                # 3. Kiểm tra Protected Period (FIFA Article 17)
                existing_contracts = Contract.objects.filter(
                    player=player,
                    end_date__gte=today
                ).order_by('-end_date').first()
                
                protected_period_info = ""
                if existing_contracts:
                    contract_age = (today - existing_contracts.start_date).days / 365.25
                    # Protected period: 3 năm cho cầu thủ <28 tuổi, 2 năm cho >=28 tuổi
                    protected_years = 3 if (player_age and player_age < 28) else 2
                    
                    if contract_age < protected_years:
                        protected_period_info = f"⚠️ Cầu thủ đang trong PROTECTED PERIOD (FIFA Article 17). Chuyển nhượng trước hạn có thể phát sinh bồi thường."
                
                # 4. Tạo prompt AI chi tiết
                genai.configure(api_key=GOOGLE_API_KEY)
                
                # Auto-detect model khả dụng
                chosen_model = 'gemini-1.5-flash'
                try:
                    for m in genai.list_models():
                        if 'generateContent' in m.supported_generation_methods:
                            if 'flash' in m.name or 'pro' in m.name:
                                chosen_model = m.name
                                break
                except:
                    pass
                
                model = genai.GenerativeModel(chosen_model)
                
                prompt = f"""
Bạn là chuyên gia luật bóng đá và hợp đồng lao động, tuân thủ FIFA Regulations on Status and Transfer of Players (RSTP) và Luật Lao động Việt Nam.

THÔNG TIN CẦU THỦ:
- Tên: {player.name}
- Tuổi: {player_age if player_age else 'Chưa rõ'}
- Vị trí: {player.get_position_display()}
- Quốc tịch: {player.nationality}
- Thống kê: {player_stats['total_matches'] or 0} trận, {player_stats['total_goals'] or 0} bàn thắng, {player_stats['total_assists'] or 0} kiến tạo

THÔNG TIN HỢP ĐỒNG:
- Loại: {c_type} ({'Mua đứt' if c_type == 'Permanent' else 'Cho mượn'})
- Thời hạn: {start} đến {end}
- Thời gian: {contract_duration_years:.1f} năm

{'CẢNH BÁO: ' + ', '.join(warnings) if warnings else '✓ Hợp đồng phù hợp với quy định FIFA và luật Việt Nam'}
{protected_period_info}

YÊU CẦU SOẠN THẢO:
1. Đề xuất mức lương CHÍNH XÁC (VND/tháng) phù hợp với:
   - Thị trường V-League hiện tại
   - Vị trí và kinh nghiệm của cầu thủ
   - Loại hợp đồng (Loan thường 60-70% so với Permanent)

2. Soạn các điều khoản HỢP ĐỒNG bao gồm:
   - Điều 1: Thông tin hai bên (CLB và cầu thủ)
   - Điều 2: Trách nhiệm cầu thủ (tập luyện, thi đấu, chấp hành nội quy)
   - Điều 3: Trách nhiệm CLB (trả lương đúng hạn, bảo hiểm, chăm sóc y tế)
   - Điều 4: Chế độ lương thưởng và phụ cấp
   - Điều 5: Điều khoản đặc biệt (nếu Loan: không được đá với đội chủ quản, nếu U18: bảo vệ quyền lợi vị thành niên)
   - Điều 6: Chấm dứt hợp đồng (tuân thủ FIFA Article 13-17, bồi thường nếu phá hợp đồng không chính đáng)
   - Điều 7: Giải quyết tranh chấp (trọng tài VFF, FIFA DRC nếu quốc tế)

TRẢ LỜI ĐÚNG ĐỊNH DẠNG:
[LUONG]: <Số VND không dấu>
[NOIDUNG]: <Toàn bộ điều khoản hợp đồng chi tiết>
"""
                
                # ... (Keep existing AI logic) ...
                res = model.generate_content(prompt)
                text = res.text
                
                if "[LUONG]:" in text:
                    parts = text.split("[NOIDUNG]:")
                    salary_clean = parts[0].replace("[LUONG]:", "").strip().replace(".", "").replace(",", "").replace("VND", "").strip()
                    ai_suggestion_text = parts[1].strip()
                    
                    # Thêm cảnh báo vào đầu nội dung nếu có
                    if warnings or protected_period_info:
                        warning_text = "⚠️ CẢNH BÁO TUÂN THỦ PHÁP LUẬT:\n" + "\n".join(warnings)
                        if protected_period_info:
                            warning_text += f"\n{protected_period_info}"
                        warning_text += "\n\n--- NỘI DUNG HỢP ĐỒNG ---\n\n"
                        ai_suggestion_text = warning_text + ai_suggestion_text
                    
                    # --- XỬ LÝ AJAX RESPONSE ---
                    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                        return JsonResponse({
                            'success': True,
                            'salary': salary_clean,
                            'clauses': ai_suggestion_text,
                            'message': "✅ AI đã soạn hợp đồng tuân thủ FIFA RSTP và Luật Việt Nam!" if not warnings else "⚠️ AI phát hiện vi phạm quy định! Xem chi tiết trong nội dung.",
                            'message_tag': 'success' if not warnings else 'warning'
                        })
                    
                    # Fallback for non-AJAX (Traditional Submit)
                    initial_data = {
                        'player': player_id, 
                        'start_date': start, 
                        'end_date': end, 
                        'contract_type': c_type,
                        'salary': salary_clean,
                        'clauses': ai_suggestion_text
                    }
                    
                    if warnings:
                        messages.warning(request, "⚠️ AI phát hiện vi phạm quy định! Vui lòng xem chi tiết trong nội dung hợp đồng.")
                    else:
                        messages.success(request, "✅ AI đã soạn hợp đồng tuân thủ FIFA RSTP và Luật Việt Nam!")
                else:
                    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                         return JsonResponse({'success': False, 'error': "AI trả lời không đúng định dạng."})
                    messages.warning(request, "AI trả lời không đúng định dạng, vui lòng thử lại.")

            except Exception as e:
                if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                    return JsonResponse({'success': False, 'error': f"Lỗi AI: {str(e)}"})
                messages.error(request, f"Lỗi AI: {str(e)}")
            
            # Re-render form với dữ liệu AI
            form = ContractForm(request.user, initial=initial_data)
        
        else:
            # --- LƯU HỢP ĐỒNG (SAVE) ---
            form = ContractForm(request.user, request.POST)
            if form.is_valid():
                contract = form.save(commit=False)
                
                # Kiểm tra bảo mật: Cầu thủ phải thuộc đội mình
                if contract.player.team != request.user.team:
                    messages.error(request, "Cầu thủ này không thuộc đội bóng của bạn!")
                    return redirect('club_dashboard')
                
                contract.team = request.user.team
                contract.save()
                messages.success(request, "✅ Ký hợp đồng thành công!")
                return redirect('club_dashboard')
    else:
        form = ContractForm(request.user)

    # Lấy danh sách hợp đồng đã ký của CLB
    contracts = Contract.objects.filter(team=request.user.team).select_related('player').order_by('-created_at')

    return render(request, 'quanly/form_contract.html', {
        'form': form,
        'contracts': contracts
    })

# --- 7. XUẤT EXCEL HỢP ĐỒNG ---
@login_required(login_url='login')
def export_contracts_excel(request):
    if request.user.role != 'club_rep': return redirect('home')
    wb = openpyxl.Workbook(); ws = wb.active; ws.title = "Hop Dong"
    ws.append(['Cầu thủ', 'Lương', 'Ngày BD', 'Ngày KT', 'Loại'])
    for c in Contract.objects.filter(team=request.user.team):
        ws.append([c.player.name, c.salary, c.start_date, c.end_date, c.get_contract_type_display()])
    
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename="DS_Hop_Dong.xlsx"'
    wb.save(response)
    return response

# --- 8. CHI TIẾT CẦU THỦ CHO QUẢN LÝ CLB ---
@login_required(login_url='login')
def club_player_detail(request, player_id):
    # ... (code lấy player giữ nguyên) ...
    player = get_object_or_404(Player, pk=player_id)
    
    # Tính thống kê (để hiển thị ra giao diện mới)
    from django.db.models import Sum
    from quanly.models import PlayerStat # Nhớ import
    
    stats = PlayerStat.objects.filter(player=player).aggregate(
        total_goals=Sum('goals'),
        total_assists=Sum('assists'),
        total_yellow=Sum('yellow_cards'),
        total_red=Sum('red_cards'),
        total_matches=Sum('matches_played')
    )

    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'edit':
            # QUAN TRỌNG: Phải có request.FILES để nhận ảnh
            form = PlayerForm(request.POST, request.FILES, instance=player) 
            if form.is_valid():
                form.save()
                messages.success(request, "Đã cập nhật hồ sơ cầu thủ thành công!")
                return redirect('club_player_detail', player_id=player.id)
        
        elif action == 'delete':
            player.delete()
            messages.success(request, "Đã xóa cầu thủ khỏi danh sách.")
            return redirect('club_dashboard')

    else:
        form = PlayerForm(instance=player)
    
    return render(request, 'quanly/club_player_detail.html', {
        'player': player,
        'form': form,
        'contracts': player.contract_set.all().order_by('-start_date'),
        'stats': stats
    })

# --- 9. VIEW DANH SÁCH CẦU THỦ (MỚI) ---
@login_required(login_url='login')
def club_players_list(request):
    if request.user.role != 'club_rep': return redirect('home')
    team = request.user.team
    if not team: return render(request, 'quanly/error.html', {'message': 'Chưa được gán đội bóng!'})

    # Lấy danh sách cầu thủ của đội
    players = Player.objects.filter(team=team).order_by('jersey_number')

    # --- 1. TÌM KIẾM ---
    query = request.GET.get('q', '')
    if query:
        players = players.filter(name__icontains=query)

    # --- 2. LỌC CẦU THỦ ---
    # Lọc nội/ngoại binh dựa trên quốc tịch
    p_type = request.GET.get('type', '')
    if p_type == 'noibinh':
        # Cầu thủ có quốc tịch Việt Nam (có thể có nhiều quốc tịch, kiểm tra có chứa "Việt Nam")
        players = players.filter(nationality__icontains='Việt Nam')
    elif p_type == 'ngoaibinh':
        # Cầu thủ KHÔNG có quốc tịch Việt Nam
        players = players.exclude(nationality__icontains='Việt Nam')
    
    # Lọc hợp đồng sắp hết hạn (trong vòng 6 tháng)
    contract_status = request.GET.get('contract', '')
    if contract_status == 'expiring':
        from datetime import date, timedelta
        six_months_later = date.today() + timedelta(days=30*6)
        
        # Chỉ lấy những cầu thủ có hợp đồng còn hiệu lực và hết hạn trong 6 tháng tới
        # Lưu ý: Một cầu thủ có thể có nhiều hợp đồng, cần lấy hợp đồng mới nhất hoặc đang active
        # Ở đây ta filter ngược từ Contract
        expiring_player_ids = Contract.objects.filter(
            team=team, 
            end_date__lte=six_months_later, 
            end_date__gte=date.today()
        ).values_list('player_id', flat=True)
        
        players = players.filter(id__in=expiring_player_ids)

    # --- 3. PHÂN TRANG & LAZY LOADING ---
    from django.core.paginator import Paginator
    
    paginator = Paginator(players, 12) # 12 items per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # AJAX: Return JSON for Lazy Loading
    if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.GET.get('ajax'):
        from django.template.loader import render_to_string
        html_content = ""
        for player in page_obj:
            html_content += render_to_string('quanly/partials/club_player_card.html', {'player': player})
            
        return JsonResponse({
            'html': html_content,
            'has_next': page_obj.has_next(),
            'next_page_number': page_obj.next_page_number() if page_obj.has_next() else None
        })

    # Standard Request: Return Full Template
    context = {
        'team': team,
        'page_obj': page_obj,
        'players': page_obj, # Fallback/Alias
        'current_query': query,
        'current_type': p_type,
        'current_contract': contract_status
    }
    return render(request, 'quanly/club_players.html', context)

# --- 10. AJAX VIEW CHO HỢP ĐỒNG SẮP HẾT HẠN ---
@login_required(login_url='login')
def expiring_contracts_ajax(request):
    """Trả về HTML danh sách cầu thủ có hợp đồng sắp hết hạn"""
    if request.user.role != 'club_rep': 
        return render(request, 'quanly/partials/expiring_contracts_modal.html', {
            'error': 'Bạn không có quyền truy cập'
        })
    
    team = request.user.team
    if not team:
        return render(request, 'quanly/partials/expiring_contracts_modal.html', {
            'error': 'Chưa được gán đội bóng'
        })
    
    # Lấy danh sách hợp đồng sắp hết hạn (năm 2025)
    expiring_contracts = Contract.objects.filter(
        team=team, 
        end_date__year=2025
    ).select_related('player').order_by('end_date')
    
    return render(request, 'quanly/partials/expiring_contracts_modal.html', {
        'contracts': expiring_contracts,
        'team': team
    })

# --- 11. AJAX VIEW CẬP NHẬT ẢNH CẦU THỦ ---
@login_required(login_url='login')
def update_player_avatar(request, player_id):
    if request.user.role != 'club_rep':
        return JsonResponse({'success': False, 'error': 'Permission denied'})
    
    if request.method == 'POST' and request.FILES.get('avatar'):
        player = get_object_or_404(Player, pk=player_id)
        
        # Verify ownership
        if player.team != request.user.team:
            return JsonResponse({'success': False, 'error': 'Permission denied'})
            
        try:
            player.avatar = request.FILES['avatar']
            player.save()
            return JsonResponse({
                'success': True, 
                'image_url': player.avatar.url,
                'message': 'Cập nhật ảnh thành công!'
            })
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
            
    return JsonResponse({'success': False, 'error': 'Invalid request'})