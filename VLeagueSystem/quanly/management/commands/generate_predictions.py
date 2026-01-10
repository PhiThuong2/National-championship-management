"""
Lệnh: python manage.py generate_predictions
Chức năng: Dùng Model đã train để dự đoán tỉ số cho các trận sắp tới (SCHEDULED)
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from quanly.models import Match, MatchStatus, AIPrediction # Giả sử bạn có model AIPrediction
from quanly.ml.prediction_models import EnsemblePredictor
from quanly.ml.feature_engineering import build_match_features

class Command(BaseCommand):
    help = 'Dự đoán tỉ số các trận đấu sắp tới'

    def handle(self, *args, **kwargs):
        self.stdout.write("🔮 Đang bắt đầu dự đoán các trận sắp tới...")

        # 1. Load Model đã train
        predictor = EnsemblePredictor()
        try:
            predictor.load_models() # Hàm này phải có trong class EnsemblePredictor của bạn
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Chưa có model! Hãy chạy lệnh train trước. Lỗi: {e}"))
            return

        # 2. Lấy các trận sắp đá (SCHEDULED)
        future_matches = Match.objects.filter(status=MatchStatus.SCHEDULED).order_by('match_date')
        
        if not future_matches.exists():
            self.stdout.write("⚠️ Không có trận đấu nào sắp tới để dự đoán.")
            return

        count = 0
        for match in future_matches:
            try:
                # 3. Xây dựng dữ liệu (Features) cho trận này
                features = build_match_features(
                    match.home_team, 
                    match.away_team, 
                    match.match_date, 
                    match.season
                )
                
                # 4. Dự đoán
                # Hàm predict trả về dictionary: {'predicted_home_score': 2, 'win_probability': 0.6, ...}
                prediction_result = predictor.predict(
                    match.home_team,
                    match.away_team,
                    match.match_date,
                    match.season
                )
                
                # 5. Lưu vào Database (Cập nhật hoặc Tạo mới)
                AIPrediction.objects.update_or_create(
                    match=match,
                    defaults={
                        'predicted_home_score': prediction_result['predicted_home_score'],
                        'predicted_away_score': prediction_result['predicted_away_score'],
                        'win_probability': prediction_result['win_probability'],
                        'draw_probability': prediction_result['draw_probability'],
                        'loss_probability': prediction_result['loss_probability'],
                        'confidence_score': prediction_result['confidence_score'],
                        'model_version': prediction_result.get('model_version', 'v1.0')
                    }
                )
                
                self.stdout.write(f"✓ Dự đoán: {match.home_team.name} vs {match.away_team.name} ({prediction_result['predicted_home_score']}-{prediction_result['predicted_away_score']})")
                count += 1

            except Exception as e:
                self.stdout.write(self.style.WARNING(f"⚠️ Lỗi dự đoán trận {match}: {e}"))

        self.stdout.write(self.style.SUCCESS(f"✅ Hoàn tất! Đã cập nhật dự đoán cho {count} trận."))