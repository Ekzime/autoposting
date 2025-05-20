from database.dao.posting_target_repository import PostingTargetRepository
from database.dao.parsing_source_repository import ParsingSourceRepository
from database.dao.pars_telegram_acc_repository import ParsingTelegramAccRepository
# Этот файл содержит централизованный доступ к репозиториям базы данных
# Ниже создаются глобальные экземпляры репозиториев для использования во всем приложении
posting_target_repository = PostingTargetRepository()
parsing_source_repository = ParsingSourceRepository()
parsing_telegram_acc_repository = ParsingTelegramAccRepository()