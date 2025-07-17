import sys
import telebot
import time
from telebot.types import ReplyKeyboardMarkup
from API import API_bot
from Scripts import main
from Scripts.EnglishTeacher import EnglishTeacher
from Scripts.TelegramLogger import TelegramLogger

API_Bot = API_bot
bot = telebot.TeleBot(API_Bot)

# Инициализация
markup = ReplyKeyboardMarkup(row_width=2, resize_keyboard=True, one_time_keyboard=False)
markup.add("/simple" ,"/english", "/help")

telegram_logger = TelegramLogger(bot, None)
sys.stdout = telegram_logger
sys.stderr = telegram_logger

chat = main.ChatManager()
english_teacher = EnglishTeacher(chat)


@bot.message_handler(commands=['start'])
def send_welcome(message):
    telegram_logger.chat_id = message.chat.id
    chat.start_chat()
    bot.send_message(message.chat.id, "Добро пожаловать! Выберите режим:",
                     reply_markup=markup)


@bot.message_handler(commands=['english'])
def english_mode(message):
    telegram_logger.chat_id = message.chat.id
    chat.do_command("/history -d")
    bot.send_message(message.chat.id, "Выберите режим изучения английского:",
                     reply_markup=english_teacher.get_mode_keyboard())


@bot.message_handler(commands=['simple'])
def english_mode(message):
    telegram_logger.chat_id = message.chat.id
    english_teacher.current_mode = None
    bot.send_message(message.chat.id, "Быбран обычный режим общения с ИИ")


@bot.callback_query_handler(func=lambda call: call.data.startswith('set_mode_'))
def set_mode(call):
    mode = call.data.split('_')[-1]
    english_teacher.current_mode = mode

    bot.edit_message_reply_markup(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        reply_markup=None
    )

    if mode == 'exercises':
        bot.send_message(call.message.chat.id, "Выберите тип упражнений:",
                         reply_markup=english_teacher.get_exercise_keyboard())
    else:
        bot.send_message(call.message.chat.id, f"Режим установлен: {english_teacher.modes[mode]}")


@bot.callback_query_handler(func=lambda call: call.data.startswith('start_exercise_'))
def start_exercise(call):
    bot.edit_message_reply_markup(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        reply_markup=None
    )

    ex_type = call.data.split('_')[-1]
    exercise = english_teacher.generate_exercise(ex_type)
    english_teacher.current_mode = 'chat'
    bot.send_message(call.message.chat.id, exercise)


@bot.message_handler(content_types=['text'])
def handle_text(message):
    telegram_logger.chat_id = message.chat.id
    telegram_logger.write_console(f"\nВы: {message.text}\n")

    if message.text.startswith('/'):
        chat.do_command(command=message.text)
        return

    if english_teacher.current_mode == 'correction':
        correction = english_teacher.correct_text(message.text)
        bot.send_message(message.chat.id, ''.join(correction))
    elif english_teacher.current_mode == 'chat':
        answer = english_teacher.simple_converse(message)
        bot.send_message(message.chat.id, answer)
    else:
        answer = chat.send_message(message.text, chat_id=chat.current_chat_id)
        answer_str = ''.join(answer) if hasattr(answer, '__iter__') else str(answer)
        bot.send_message(message.chat.id, answer_str)

while True:
    try:
        bot.infinity_polling(timeout=60, long_polling_timeout=30)
    except Exception as e:
        print(f"An error occurred: {e}")
        time.sleep(5)
    finally:
        telegram_logger.cleanup()
        chat.close()
