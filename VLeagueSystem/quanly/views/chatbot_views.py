import json
import google.generativeai as genai
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from quanly.models import ChatMessage, Season, Match, Team, Player
from django.db.models import Q
from datetime import datetime, timedelta

# Configure Gemini
GOOGLE_API_KEY = "AIzaSyCkBH3DBWmvoz0jW-tUd5sgON99BdWSpVw"

# === HELPER FUNCTIONS - Truy vấn Database ===

def get_upcoming_matches(team_name=None, limit=5):
    """Lấy lịch thi đấu sắp tới"""
    matches = Match.objects.filter(status='SCHEDULED').order_by('match_date')[:limit]
    
    if team_name:
        matches = matches.filter(
            Q(home_team__name__icontains=team_name) | 
            Q(away_team__name__icontains=team_name)
        )[:limit]
    
    result = []
    for m in matches:
        result.append(
            f"- {m.match_date.strftime('%d/%m/%Y %H:%M')}: "
            f"{m.home_team.name} vs {m.away_team.name} (Vòng {m.round_number})"
        )
    return "\n".join(result) if result else "Không có lịch thi đấu sắp tới."

def get_standings(season=None):
    """Lấy bảng xếp hạng"""
    from quanly.views.utils import calculate_standings
    
    if not season:
        season = Season.objects.filter(is_active=True).first()
    
    standings = calculate_standings(season=season)
    result = []
    for idx, team in enumerate(standings[:10], 1):
        result.append(
            f"{idx}. {team['team'].name}: {team['points']} điểm "
            f"({team['won']}T-{team['drawn']}H-{team['lost']}B)"
        )
    return "\n".join(result) if result else "Chưa có dữ liệu bảng xếp hạng."

def get_team_info(team_name):
    """Lấy thông tin về đội bóng"""
    try:
        team = Team.objects.filter(name__icontains=team_name).first()
        if not team:
            return f"Không tìm thấy đội bóng '{team_name}'."
        
        player_count = Player.objects.filter(team=team).count()
        return (
            f"Thông tin {team.name}:\n"
            f"- Sân nhà: {team.stadium or 'N/A'}\n"
            f"- Thành phố: {team.city or 'N/A'}\n"
            f"- Số cầu thủ: {player_count}"
        )
    except Exception as e:
        return f"Lỗi khi truy vấn: {str(e)}"

def get_recent_matches(team_name=None, limit=5):
    """Lấy kết quả các trận đấu gần đây"""
    matches = Match.objects.filter(status='FINISHED').order_by('-match_date')[:limit]
    
    if team_name:
        matches = matches.filter(
            Q(home_team__name__icontains=team_name) | 
            Q(away_team__name__icontains=team_name)
        )[:limit]
    
    result = []
    for m in matches:
        result.append(
            f"- {m.match_date.strftime('%d/%m/%Y')}: "
            f"{m.home_team.name} {m.home_score}-{m.away_score} {m.away_team.name}"
        )
    return "\n".join(result) if result else "Không có dữ liệu trận đấu."

def get_player_info(player_name):
    """Lấy thông tin cầu thủ (bao gồm lương/giá trị chuyển nhượng)"""
    from quanly.models import Contract, TransferRequest
    try:
        # Tìm chính xác hoặc gần đúng
        players = Player.objects.filter(name__icontains=player_name)
        if not players.exists():
            return None
        
        info_list = []
        for p in players[:3]: # Lấy tối đa 3 cầu thủ trùng tên
            # 1. Thông tin cơ bản
            basic_info = f"- Cầu thủ: {p.name} ({p.get_position_display()})\n  + Đội bóng: {p.team.name if p.team else 'Tự do'}\n  + Quốc tịch: {p.nationality}"
            
            # 2. Lương (từ Hợp đồng mới nhất)
            latest_contract = Contract.objects.filter(player=p, status='Active').order_by('-start_date').first()
            salary_str = "Chưa công bố"
            if latest_contract:
                salary_str = f"{latest_contract.salary:,.0f} VND/tháng"
                
            # 3. Phí chuyển nhượng (gần nhất)
            latest_transfer = TransferRequest.objects.filter(player=p, status='approved').order_by('-request_date').first()
            transfer_fee_str = "Chưa có dữ liệu"
            if latest_transfer:
                transfer_fee_str = f"{latest_transfer.transfer_fee:,.0f} VND"
            
            player_details = (
                f"{basic_info}\n"
                f"  + Lương hiện tại: {salary_str}\n"
                f"  + Giá trị chuyển nhượng gần nhất: {transfer_fee_str}"
            )
            info_list.append(player_details)
            
        return "\n".join(info_list)
    except Exception as e:
        return f"Lỗi truy vấn cầu thủ: {str(e)}"

# === MAIN API ===

@login_required(login_url='login')
def chatbot_api(request):
    """API xử lý tin nhắn chatbot và trả về phản hồi từ AI"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            user_message = data.get('message', '').strip().lower()
            
            if not user_message:
                return JsonResponse({'success': False, 'error': 'Tin nhắn trống'})

            # Ngữ cảnh hệ thống
            active_season = Season.objects.filter(is_active=True).first()
            if not active_season:
                active_season = Season.objects.order_by('-start_date').first()
            
            role_name = request.user.get_role_display()
            user_team_name = request.user.team.name if request.user.team else "Không thuộc CLB nào"
            
            # === PHÂN TÍCH CÂU HỎI & NẠP DỮ LIỆU ===
            context_data = ""
            
            # Detect intent và lấy dữ liệu từ DB
            if any(kw in user_message for kw in ['lịch thi đấu', 'lịch đấu', 'trận sắp tới', 'khi nào đá']):
                # Tìm tên đội trong câu hỏi
                team_name = None
                for team in Team.objects.all():
                    if team.name.lower() in user_message:
                        team_name = team.name
                        break
                
                context_data = f"\n**LỊCH THI ĐẤU SẮP TỚI:**\n{get_upcoming_matches(team_name)}"
            
            if any(kw in user_message for kw in ['bxh', 'xếp hạng', 'bảng xếp hạng', 'đứng thứ mấy', 'vị trí']):
                context_data += f"\n\n**BẢNG XẾP HẠNG HIỆN TẠI:**\n{get_standings(active_season)}"
            
            if any(kw in user_message for kw in ['kết quả', 'trận gần đây', 'đã đá']):
                team_name = None
                for team in Team.objects.all():
                    if team.name.lower() in user_message:
                        team_name = team.name
                        break
                
                context_data += f"\n\n**KẾT QUẢ GẦN ĐÂY:**\n{get_recent_matches(team_name)}"
            
            if any(kw in user_message for kw in ['thông tin đội', 'đội bóng', 'clb']):
                for team in Team.objects.all():
                    if team.name.lower() in user_message:
                        context_data += f"\n\n{get_team_info(team.name)}"
                        break

            # MỚI: Detect thông tin cầu thủ
            if any(kw in user_message for kw in ['cầu thủ', 'giá', 'lương', 'tiền', 'contract', 'hợp đồng', 'chuyển nhượng']):
                found_player_data = None
                # Tìm tên cầu thủ trong câu hỏi (duyệt qua tất cả cầu thủ - có thể tối ưu bằng Full Text Search sau này)
                # Cách đơn giản: Duyệt qua các từ trong câu hỏi xem có khớp tên cầu thủ nào không?
                # Cách tốt hơn: Lấy tất cả player name và check.
                # Tuy nhiên để nhanh, ta giả định người dùng nhập tên.
                
                # Để đơn giản: Thử tìm tất cả cầu thủ có tên nằm trong message
                # Lưu ý: Điều này có thể chậm nếu DB lớn.
                potential_players = Player.objects.all()
                for p in potential_players:
                    if p.name.lower() in user_message:
                        found_player_data = get_player_info(p.name)
                        break # Chỉ lấy 1 người đầu tiên tìm thấy
                
                if found_player_data:
                    context_data += f"\n\n**THÔNG TIN CẦU THỦ:**\n{found_player_data}"
            
            # System Prompt cho Gemini
            system_prompt = f"""
Bạn là **Trợ lý ảo V-League**, chuyên gia về giải đấu bóng đá vô địch quốc gia Việt Nam.

**Thông tin người dùng:**
- Vai trò: {role_name}
- Đội bóng: {user_team_name}
- Mùa giải hiện tại: {active_season.name if active_season else 'N/A'}

**DỮ LIỆU THỰC TẾ TỪ HỆ THỐNG:**{context_data}

**Quy tắc trả lời:**
1. Sử dụng dữ liệu thực tế phía trên để trả lời chính xác.
2. Luôn dùng tiếng Việt, giọng điệu chuyên nghiệp nhưng thân thiện.
3. **QUAN TRỌNG:** Tất cả giá trị tiền tệ (lương, phí chuyển nhượng, giá vé) **PHẢI** dùng đơn vị **VND (Việt Nam Đồng)**. Tuyệt đối **KHÔNG** dùng EUR, USD hay đơn vị tiền tệ khác.
4. Nếu dữ liệu tiền tệ không có trong phần "DỮ LIỆU THỰC TẾ", hãy trả lời là "Chưa có thông tin về giá trị", KHÔNG ĐƯỢC tự bịa ra con số hoặc dùng đơn vị EUR.
5. Trả lời ngắn gọn, súc tích (100-150 từ).
"""
            
            # Lịch sử chat
            history = ChatMessage.objects.filter(user=request.user).order_by('-created_at')[:3]
            history_text = "\n".join([f"User: {h.message}\nAI: {h.response}" for h in reversed(history)])

            full_prompt = f"{system_prompt}\n\nLịch sử:\n{history_text}\n\nCâu hỏi mới: {data.get('message', '').strip()}\n\nTrả lời:"

            # Gọi Gemini
            genai.configure(api_key=GOOGLE_API_KEY)
            
            chosen_model_name = None
            try:
                for m in genai.list_models():
                    if 'generateContent' in m.supported_generation_methods:
                        chosen_model_name = m.name
                        break
            except Exception:
                for fallback in ['gemini-1.5-flash', 'gemini-1.5-pro', 'gemini-pro']:
                    try:
                        test_model = genai.GenerativeModel(fallback)
                        chosen_model_name = fallback
                        break
                    except:
                        continue
            
            if not chosen_model_name:
                return JsonResponse({'success': False, 'error': 'Không tìm thấy model Gemini khả dụng'})
            
            model = genai.GenerativeModel(chosen_model_name)
            response = model.generate_content(full_prompt)
            ai_response = response.text.strip()

            # Lưu vào Database
            ChatMessage.objects.create(
                user=request.user,
                message=data.get('message', '').strip(),
                response=ai_response
            )

            return JsonResponse({
                'success': True, 
                'response': ai_response
            })

        except Exception as e:
            return JsonResponse({'success': False, 'error': f'Lỗi: {str(e)}'})

    return JsonResponse({'success': False, 'error': 'Invalid request method'})
