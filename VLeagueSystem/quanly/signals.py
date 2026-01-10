from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.management import call_command
from .models import Match, MatchStatus
import threading

@receiver(post_save, sender=Match)
def update_predictions_on_match_finish(sender, instance, created, **kwargs):
    """
    Khi một trận đấu kết thúc (status='FINISHED'), 
    tự động chạy lại dự đoán cho các trận chưa đấu để cập nhật phong độ mới nhất.
    """
    if instance.status == MatchStatus.FINISHED:
        # Sử dụng threading để không làm block request của người dùng (mua vé, cập nhật tỉ số...)
        # Lưu ý: Threading trong Django đơn giản có thể gặp vấn đề với transaction nếu không cẩn thận,
        # nhưng với management command đọc dữ liệu thì ổn.
        
        def run_prediction_command():
            try:
                # Chạy command với flag --force để cập nhật lại cả những trận đã dự đoán trước đó
                # vì phong độ các đội đã thay đổi sau trận đấu vừa xong.
                print(f"🔄 Auto-updating predictions after match {instance} finished...")
                call_command('generate_ai_predictions', force=True)
            except Exception as e:
                print(f"⚠️ Failed to auto-update predictions: {e}")

        # Chỉ chạy nếu trận đấu thực sự vừa kết thúc (logic này chạy mỗi lần save FINISHED, 
        # có thể tối ưu hơn nhưng tạm thời ok cho MVP)
        thread = threading.Thread(target=run_prediction_command)
        thread.start()
