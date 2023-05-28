import json
import logging
import os
import time
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv

import exceptions

load_dotenv()


PRACTICUM_TOKEN = os.getenv('YP_TOKEN')
TELEGRAM_TOKEN = os.getenv('BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('CHAT_ID')


RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
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
    """Проверка наличия токенов и ID."""
    return all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID])


def send_message(bot, message):
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


def get_api_answer(timestamp):
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


def check_response(response):
    """Проверка данных в response."""
    if not isinstance(response, dict):
        raise TypeError('Неверный тип данных ответа')
    if 'homeworks' not in response:
        logger.error('Ключ homeworks или response имеет неправильное значение')
        raise KeyError('Ответ не содержит ключа homeworks')
    if not isinstance(response['homeworks'], list):
        raise TypeError('Значение ключа homeworks не является списком')
    status = response['homeworks'][0].get('status')
    if status is not None and status not in HOMEWORK_VERDICTS:
        logger.error(f'Получен недокументированный статус: {status}')
    return response['homeworks'][0]


def parse_status(homework):
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


def main():
    """Основная логика работы бота."""
    logger.info('Вы запустили Бота')
    if check_tokens() is False:
        er_txt = (
            'Отсутствуют необходимые токены или ID.'
            'Принудительная остановка работы Бота'
        )
        logger.critical(er_txt)
        return None
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    tmp_status = 'reviewing'
    while True:
        try:
            response = get_api_answer(0)
            homework = check_response(response)
            if homework and tmp_status != homework['status']:
                message = parse_status(homework)
                send_message(bot, message)
                tmp_status = homework['status']
                logger.error('Изменений нет')
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message)
            send_message(bot, message)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
