from telegram.parser.parser_service import trigger_update as trigger_parser_update
import logging
import asyncio

# Создаем события для сигнализации обновлений
posting_settings_update_event = asyncio.Event()

def trigger_parser_settings_update():
    """Запускает обновление настроек парсера"""
    trigger_parser_update()
    
def trigger_posting_settings_update():
    """
    Вызывает немедленное обновление списка целевых каналов для постинга.
    Эта функция используется для обновления настроек постинга из других модулей.
    """
    global posting_settings_update_event
    posting_settings_update_event.set()
    logging.info("Запущено обновление настроек постинга через trigger_utils")
