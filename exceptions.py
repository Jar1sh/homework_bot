class CriticalSendError(BaseException):
    """Ошибка отправки сообщения."""


class NotForSending(Exception):
    """Не для пересылки в телеграм."""


class InvalidResponseCode(Exception):
    """Не верный код ответа."""


class ConnectinError(Exception):
    """Ошибка соединения."""


class TelegramError(NotForSending):
    """Ошибка платформы телеграма."""
