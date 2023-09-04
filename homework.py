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

logger = logging.getLogger(__name__)
logger.addHandler(logging.StreamHandler())


def check_tokens():
    """Проверка доступности переменных окружения."""
    return all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID])


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


def get_api_answer(current_timestamp: str) -> dict:
    """Получение данных от API."""
    timestamp = current_timestamp or int(time.time())
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


def check_response(response: dict) -> list:
    """Проверка данных в response."""
    if not isinstance(response, dict):
        raise TypeError('Неверный тип данных ответа')
    if 'homeworks' not in response:
        logger.info('Ключ homeworks или response имеет неправильное значение')
        raise KeyError('Ответ не содержит ключа homeworks')
    list_hw = response['homeworks']
    if not isinstance(list_hw, list):
        raise TypeError('Значение ключа homeworks не является списком')
    return list_hw


def parse_status(homework: dict) -> str:
    """Получение информации о домашней работе и статус этой работы."""
    homework_name = homework.get('homework_name')
    status = homework.get('status')
    if homework_name is None:
        logger.error('Неверная информацию о домашней работе')
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
    update_status = {'name': '', 'state': ''}
    status = {'name': '', 'state': ''}
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    while True:
        try:
            response = get_api_answer(current_timestamp)
            homeworks = check_response(response)
            if not homeworks:
                message = 'Новых работ не обнаружено'
                send_message(bot, message)
            else:
                message = parse_status(homeworks[0])
                current_timestamp = response.get('current_date')
                status[response.get('homework_name')] = response.get('status')
                if status != update_status and status is not None:
                    update_status = status
                    send_message(bot, message)
                else:
                    logger.debug('Статус работы не изменен')
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message)
            send_message(bot, message)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG,
        filename='programm.log',
        encoding='utf-8',
        filemode='w',
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    main()
