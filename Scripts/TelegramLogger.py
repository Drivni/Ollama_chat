import sys

import main
import telebot
import time
from telebot.types import ReplyKeyboardMarkup
from API import API_bot

API_Bot = API_bot
bot = telebot.TeleBot(API_Bot)

class TelegramLogger:
    def __init__(self, bot, chat_id):
        self.bot = bot
        self.chat_id = chat_id
        self.buffer = ""
        # Сохраняем оригинальный stdout для консольного вывода
        self.console_out = sys.stdout
        self.console_err = sys.stderr

    def write_console(self, message):
        if not isinstance(message, str):
            message = str(message)
        self.console_out.write(message)

    def write(self, message):
        # Выводим в консоль
        self.console_out.write(message)

        # Добавляем сообщение в буфер для Telegram
        self.buffer += message

        # Если есть перевод строки - отправляем сообщение
        if '\n' in message:
            self.flush()

    def flush(self):
        # Сохраняем flush для консоли
        self.console_out.flush()

        # Отправляем в Telegram
        if self.buffer.strip():
            try:
                # Отправляем содержимое буфера
                self.bot.send_message(self.chat_id, self.buffer)
            except Exception as e:
                # Если ошибка - выводим в консоль
                self.console_out.write(f"Ошибка отправки лога: {e}\n")
            finally:
                self.buffer = ""

    # Восстанавливаем потоки при завершении
    def cleanup(self):
        sys.stdout = self.console_out
        sys.stderr = self.console_err


markup = ReplyKeyboardMarkup(row_width=2, resize_keyboard=True, one_time_keyboard=False)
markup.add("/Start_Game", "/Info")


telegram_logger = TelegramLogger(bot, None)
sys.stdout = telegram_logger
sys.stderr = telegram_logger