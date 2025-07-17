import sys
import telebot
import time
from telebot.types import ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from API import API_bot
from Scripts import main

API_Bot = API_bot
bot = telebot.TeleBot(API_Bot)


class EnglishTeacher:
    def __init__(self, chat_manager):
        self.chat_manager = chat_manager
        self.modes = {
            'chat': "Свободный чат на английском",
            'correction': "Исправления ошибок",
            'exercises': "Упражнений"
        }
        self.current_mode = 'chat'
        self.exercise_types = ['grammar', 'vocabulary', 'translation']
        self.current_exercise = None
        self.user_level = 'beginner'  # Можно определить через тест

    def get_mode_keyboard(self):
        keyboard = InlineKeyboardMarkup()
        for mode_id, mode_name in self.modes.items():
            keyboard.add(InlineKeyboardButton(
                text=f"{mode_name}{' ✅' if self.current_mode == mode_id else ''}",
                callback_data=f"set_mode_{mode_id}"
            ))
        return keyboard

    def get_exercise_keyboard(self):
        keyboard = InlineKeyboardMarkup()
        for ex_type in self.exercise_types:
            keyboard.add(InlineKeyboardButton(
                text=ex_type.capitalize(),
                callback_data=f"start_exercise_{ex_type}"
            ))
        return keyboard

    def generate_exercise(self, ex_type):
        prompt = f"""
        Generate a {ex_type} exercise for {self.user_level} level English learner.
        Include: 
        1. Clear instructions
        2. The exercise itself
        3. The correct answer (hidden until requested)
        """

        response = self.chat_manager.send_message(
            prompt,
            system_prompt="You are an English teacher creating learning exercises.",
            chat_id=self.chat_manager.current_chat_id
        )

        self.current_exercise = {
            'type': ex_type,
            'content': ''.join(response),
            'answered': False
        }
        return self.current_exercise['content']

    def correct_text(self, text):
        prompt = f"""
        Correct this English text and explain mistakes:
        {text}

        Response format:
        Corrected: [corrected version]
        Errors: [list of mistakes with explanations]
        """

        return self.chat_manager.send_message(
            prompt,
            system_prompt="You are an English teacher correcting student's work.",
            chat_id=self.chat_manager.current_chat_id
        )


class TelegramLogger:
    def __init__(self, bot, chat_id):
        self.bot = bot
        self.chat_id = chat_id
        self.buffer = ""
        self.console_out = sys.stdout
        self.console_err = sys.stderr

    def write_console(self, message):
        if not isinstance(message, str):
            message = str(message)
        self.console_out.write(message)

    def write(self, message):
        self.console_out.write(message)
        self.buffer += message
        if '\n' in message:
            self.flush()

    def flush(self):
        self.console_out.flush()
        if self.buffer.strip():
            try:
                self.bot.send_message(self.chat_id, self.buffer)
            except Exception as e:
                self.console_out.write(f"Ошибка отправки лога: {e}\n")
            finally:
                self.buffer = ""

    def cleanup(self):
        sys.stdout = self.console_out
        sys.stderr = self.console_err


# Инициализация
markup = ReplyKeyboardMarkup(row_width=2, resize_keyboard=True, one_time_keyboard=False)
markup.add("/Start_Game", "/Info", "/English_Mode")

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
                     reply_markup=english_teacher.get_mode_keyboard())


@bot.message_handler(commands=['english_mode'])
def english_mode(message):
    telegram_logger.chat_id = message.chat.id
    bot.send_message(message.chat.id, "Выберите режим изучения английского:",
                     reply_markup=english_teacher.get_mode_keyboard())


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
    bot.send_message(call.message.chat.id, exercise)


@bot.message_handler(content_types=['text'])
def handle_text(message):
    telegram_logger.write_console(f"\nВы: {message.text}\n")
    telegram_logger.chat_id = message.chat.id

    if message.text.startswith('/'):
        chat.do_command(command=message.text)
        return

    if english_teacher.current_mode == 'correction':
        correction = english_teacher.correct_text(message.text)
        bot.send_message(message.chat.id, ''.join(correction))
    else:
        answer = chat.send_message(
            message.text,
            chat_id=chat.current_chat_id,
            system_prompt="You are an English teacher. Respond in English, correct mistakes when you see them."
        )
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