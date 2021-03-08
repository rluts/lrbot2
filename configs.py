from enum import Enum

from base_config import BaseConfig


class UkWikiConfig(BaseConfig):
    user_namespace = 'Користувач'
    edit_summary_process = 'Зменшення розміру зображення за запитом користувача [[User:{user}|{user}]]'
    template_name = 'Користувач:LRBot/resize'
    log_section = 'Журнал завантажень'
    message_success = 'Зображення зменшено'
    upload_log_success = '. Доданий журнал завантажень'
    params_error = 'Помилка при завантаженні параметрів шаблону. [[User:LRBot/resize|Дивіться документацію]].'
    download_error = 'Неможливо завантажити зображення з сервера'
    upload_error = 'Неможливо завантажити зображення на сервер'
    width_error = 'Вкажіть ширину файлу, меншу за поточну'
    format_error = 'Формат не підтримується. Доступні формати: {formats}'
    template_regex = r'\{\{\s?(?:User|Користувач)?:LRBot\/resize\s?(?:\|.+|\s.+}})'


class ViWikiConfig(BaseConfig):
    user_namespace = 'Thành viên'
    edit_summary_process = 'Giảm độ phân giải theo yêu cầu của [[Thành viên:{user}|{user}]]'
    template_name = 'Thành viên:LRBot/resize'
    log_section = 'Nhật trình tải lên'
    message_success = 'Hình đã giảm độ phân giải'
    upload_log_success = '. Thêm nhật trình tải lên'
    params_error = 'Có lỗi khi đang tải tham số bản mẫu. Xem tài liệu.'
    download_error = 'Không thể tải hình từ máy chủ xuống'
    upload_error = 'Không thể tải hình lên máy chủ'
    width_error = 'Chiều rộng mới của hình nên nhỏ hơn chiều rộng hiện tại'
    format_error = 'Định dạng tập tin không được hỗ trợ. Các định dạng được hỗ trợ: {formats}'
    template_regex = r'\{\{\s?(?:User|Thành viên)?:LRBot\/resize\s?(?:\|.+|\s.+}})'


WIKIS = {
    'uk.wikipedia': UkWikiConfig,
    'vi.wikipedia': ViWikiConfig,
}
