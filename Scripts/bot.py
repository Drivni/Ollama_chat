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

chat = main.ChatManager()

@bot.message_handler(commands=['start'])
def send_welcome(message):
    telegram_logger.chat_id = message.chat.id
    chat.start_chat()

# Обработчик всех текстовых сообщений
@bot.message_handler(content_types=['text'])
def echo_message(message):
    telegram_logger.write_console(f"\nВы: {message.text}\n")
    telegram_logger.chat_id = message.chat.id
    user_input = message.text
    if user_input.lower() in ['/exit', '/quit', '/выход']:
        return
    if user_input[0] == "/":
        chat.do_command(command=user_input)
        return
    answer = chat.send_message(message.text, chat_id=chat.current_chat_id)
    answer_str = ''.join(answer) if hasattr(answer, '__iter__') else str(answer)
    print(f"Ассиситент: {answer_str}")

while True:
    try:
        bot.infinity_polling(timeout=60, long_polling_timeout=30)
    except Exception as e:
        print(f"An error occurred: {e}")
        time.sleep(5)  # Подождите перед перезапуском
    finally:
        telegram_logger.cleanup()
        chat.close()