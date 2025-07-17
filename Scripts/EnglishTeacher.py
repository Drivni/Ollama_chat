from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton


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

    def simple_converse(self, message):
        answer = self.chat_manager.send_message(
            message.text,
            chat_id=self.chat_manager.current_chat_id,
            system_prompt="You are an English teacher. Respond in English, correct mistakes when you see them."
        )
        return ''.join(answer) if hasattr(answer, '__iter__') else str(answer)