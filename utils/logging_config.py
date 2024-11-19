from aiologger import Logger

# Глобальная переменная для логгера
_async_logger = None


def get_logger(name="async_logger"):
    """
    Возвращает настроенный асинхронный логгер. Реализует паттерн Singleton.
    """
    global _async_logger
    if _async_logger is None:
        _async_logger = Logger.with_default_handlers(name=name)
    return _async_logger
