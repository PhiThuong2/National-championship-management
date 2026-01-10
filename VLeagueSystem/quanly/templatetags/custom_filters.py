from django import template

register = template.Library()

@register.filter
def get_attr(obj, attr_name):
    """
    Lấy thuộc tính của object hoặc value của dict.
    Sử dụng: {{ object|get_attr:"name" }}
    """
    if isinstance(obj, dict):
        return obj.get(attr_name)
    if obj:
        return getattr(obj, attr_name, None)
    return None

@register.filter
def get_item(dictionary, key):
    """
    Lấy value từ dictionary bằng key (dùng cho ID dạng số).
    Sử dụng: {{ mydict|get_item:key }}
    """
    if dictionary:
        return dictionary.get(key)
    return None

@register.filter
def mul(value, arg):
    """
    Nhân giá trị với arg. Dùng để chuyển 0.5 -> 50.
    Sử dụng: {{ value|mul:100 }}
    """
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0

@register.filter
def vi_date(value):
    """
    Chuyển đổi ngày sang định dạng tiếng Việt: Thứ Bảy, 27/12/2025
    """
    if not value:
        return ""
    
    days = {
        'Monday': 'Thứ Hai',
        'Tuesday': 'Thứ Ba',
        'Wednesday': 'Thứ Tư',
        'Thursday': 'Thứ Năm',
        'Friday': 'Thứ Sáu',
        'Saturday': 'Thứ Bảy',
        'Sunday': 'Chủ Nhật'
    }
    
    try:
        # Lấy tên thứ tiếng Anh
        day_name = value.strftime('%A')
        # Lấy ngày tháng năm
        date_str = value.strftime('%d/%m/%Y')
        
        # Chuyển đổi sang tiếng Việt
        vi_day = days.get(day_name, day_name)
        
        return f"{vi_day}, {date_str}"
    except Exception:
        return value
