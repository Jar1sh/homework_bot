import json
import logging
import os
import sys
import time
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv

import exceptions

load_dotenv()


PRACTICUM_TOKEN: str = os.getenv('YP_TOKEN')
TELEGRAM_TOKEN: str = os.getenv('BOT_TOKEN')
TELEGRAM_CHAT_ID: str = os.getenv('CHAT_ID')


RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS: dict[str, str] = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logging.basicConfig(
    level=logging.DEBUG,
    filename='program.log',
    filemode='w',
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
logger.addHandler(logging.StreamHandler())


def check_tokens():
    """Проверка доступности переменных окружения."""
    if not all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID]):
        logger.critical('Отсутствуют обязательные переменные окружения')
        return False
    return True


def send_message(bot: telegram.Bot, message: str) -> None:
    """Отправка сообщения в ТГ."""
    try:
        logger.debug('Начало отправки сообщения')
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.debug('Сообщение отправлено')
    except telegram.error.TelegramError:
        logger.error('Сообщение не отправлено')
        raise AssertionError(
            'Не удалось отправить сообщение'
        )
    else:
        logger.info('Сообщение отправлено успешно')


def get_api_answer(timestamp: str) -> dict:
    """Получение данных от API."""
    payload = {'from_date': timestamp}
    try:
        homework_statuses = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params=payload
        )
        if homework_statuses.status_code != HTTPStatus.OK:
            raise exceptions.InvalidResponseCode(
                'Не удалось получить ответ API, '
                f'ошибка: {homework_statuses.status_code}'
                f'причина: {homework_statuses.reason}'
                f'текст: {homework_statuses.text}')
        logging.info('Сделан запрос к API с получением ответа')
        return homework_statuses.json()
    except requests.exceptions.RequestException as error:
        raise exceptions.ConnectinError(
            f'Ошибка при выполнение запроса к API: {error}'
        )
    except json.JSONDecodeError as error:
        raise exceptions.InvalidResponseCode(
            f'Ошибка при преобразовании ответа API в формат в JSON: {error}'
        )


def check_response(response: dict) -> dict:
    """Проверка данных в response."""
    if not isinstance(response, dict):
        raise TypeError('Неверный тип данных ответа')
    if 'homeworks' not in response:
        logger.info('Ключ homeworks или response имеет неправильное значение')
        raise KeyError('Ответ не содержит ключа homeworks')
    if not isinstance(response['homeworks'], list):
        raise TypeError('Значение ключа homeworks не является списком')
    homeworks = response['homeworks']
    for hw in homeworks:
        status = hw.get('status')
        if status is not None and status not in HOMEWORK_VERDICTS:
            logger.info(f'Получен недокументированный статус: {status}')
    return homeworks


def parse_status(homework: dict) -> str:
    """Получение информации о домашней работе и статус этой работы."""
    homework_name = homework.get('homework_name')
    status = homework.get('status')
    if homework_name is None:
        logger.error('Нет ключа homework_name')
        raise KeyError
    if isinstance(status, str) and status not in HOMEWORK_VERDICTS:
        logger.error(f'Неизвестный статус: {status}')
        raise KeyError
    verdict = HOMEWORK_VERDICTS[status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main() -> None:
    """Основная логика работы бота."""
    logger.info('Вы запустили Бота')
    if not check_tokens():
        er_txt = (
            'Отсутствуют необходимые токены или ID.'
            'Принудительная остановка работы Бота'
        )
        logger.critical(er_txt)
        sys.exit('Принудительное завершение из-за нехватки токенов')
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    while True:
        try:
            response = get_api_answer(0)
            homeworks = check_response(response)
            for hw in homeworks:
                if current_timestamp != hw['status']:
                    message = parse_status(hw)
                    send_message(bot, message)
                    current_timestamp = hw['status']
            if not homeworks:
                logger.info('Новых работ не найдено')
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message)
            send_message(bot, message)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
