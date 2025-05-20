from database.dao.posting_target_repository import PostingTargetRepository
from database.dao.parsing_source_repository import ParsingSourceRepository
from database.dao.pars_telegram_acc_repository import ParsingTelegramAccRepository
# Этот файл содержит централизованный доступ к репозиториям базы данных

# PostingTargetRepository предоставляет методы для работы с целевыми каналами постинга:
# - Добавление новых целевых каналов
# - Активация/деактивация каналов
# - Получение списка всех каналов
# - Управление активным каналом для публикации

# ParsingSourceRepository предоставляет методы для управления источниками данных, которые будут парситься:
# - add_source_to_target: Добавляет новый источник парсинга к указанной цели постинга
# - get_sources_for_target: Получает список источников для указанного целевого канала
# - delete_source_by_id: Удаляет источник парсинга по его ID из базы данных
# - change_target_for_source: Изменяет целевой канал для указанного источника парсинга
# - get_all_sources: Получает все источники парсинга из базы данных


# Ниже создаются глобальные экземпляры репозиториев для использования во всем приложении
posting_target_repository = PostingTargetRepository()
parsing_source_repository = ParsingSourceRepository()
parsing_telegram_acc_repository = ParsingTelegramAccRepository()