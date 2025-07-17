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
            1. Clear instructions (in English only)
            2. The exercise itself (in English only)
            3. The correct answer (hidden until requested)
            
            Important restrictions:
            - Use ONLY English for all exercise content (instructions, questions, answers)
            - You may use Russian ONLY for meta-commentary or explanations about the exercise structure if absolutely necessary
            - Never mix languages within the exercise materials
            - Never provide translations unless explicitly requested
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
            **Task:** Correct this English text and provide detailed explanations for all errors.  
    
            **Text to correct:**  
            "{text}"  
    
            **Response format requirements:**  
            1. **Corrected Text:**  
               - Provide the fully corrected version of the text with proper grammar, spelling, punctuation, and word choice.  
               - Preserve the original meaning unless it is ambiguous.  
    
            2. **Error Analysis:**  
               - List each mistake in the order they appear in the text.  
               - For each error, specify:  
                 - **Type of error** (grammar, spelling, word order, tense, article usage, etc.)  
                 - **Incorrect form** (quote the exact problematic part)  
                 - **Corrected form** (provide the fixed version)  
                 - **Explanation** (briefly explain why it's wrong and the rule applied)  
    
            3. **Additional Notes (if needed):**  
               - If the text has stylistic issues (awkward phrasing, unnatural word choice), suggest improvements.  
               - If a sentence is ambiguous, provide possible interpretations.  
    
            **Important:**  
            - Be precise—do not invent mistakes that don’t exist.  
            - If the text is already correct, state: "No errors found."  
            - Use clear, simple English in explanations.  
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