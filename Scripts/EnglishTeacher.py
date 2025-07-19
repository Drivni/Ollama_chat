from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton


class EnglishTeacher:
    def __init__(self, chat_manager):
        self.chat_manager = chat_manager
        self.modes = {
            'chat': "Свободный чат на английском",
            'correction': "Исправления ошибок",
            'exercises': "Упражнения"
        }
        self.current_mode = None
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
            You are an AI that generates English language learning exercises.

            Follow these instructions carefully:
            
            1. **EXERCISE TYPE**: {ex_type}  
               - Example types: Fill-in-the-blanks, Multiple Choice, Sentence Building, Error Correction, Reading Comprehension, Dialogue Completion, etc.
            
            2. **LEVEL**: {self.user_level}  
               - The level is based on the CEFR (Common European Framework of Reference for Languages), e.g., A1, A2, B1, B2, C1, C2. Tailor the vocabulary, grammar, and complexity to this level.
            
            3. Always write your answer in **English**.
            
            4. If you want to explain something that may be difficult to understand, you may add a note **in Russian using Cyrillic** (for example: "Слово 'however' означает 'однако'").
            
            5. Use clear formatting with titles and indentation if necessary.
            
            6. Be creative and vary the structure of tasks when possible. Do **not** always follow the same output format unless asked.
            
            7. **Do NOT provide the correct answers in your response.** The goal is for the learner to complete the exercise independently.
            
            Your response must include:
            - A brief title of the exercise.
            - Clear instructions.
            - The exercise itself (questions, sentences, etc.).
            - (Optional) Explanations or hints in Russian using Cyrillic, only when truly needed.
            
            Now generate an exercise with:
            - **EXERCISE TYPE**: {ex_type}  
            - **LEVEL**: {self.user_level}
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
            **Task:** Please correct the English text and explain all detected errors in detail.
            
            **Text to correct:** "{text}"
            
            **Instructions for the response:**
            
            1. **Corrected Text:**
               - Write the corrected version of the entire text.
               - Fix all grammar, spelling, punctuation, and word choice issues.
               - Keep the original meaning unless the sentence is ambiguous.
            
            2. **Error Analysis:**
               - List all errors in the order they appear in the original text.
               - For each error, include:
                 - **Error Type** (e.g., grammar, spelling, word order, verb tense, article usage, etc.)
                 - **Incorrect Form** (quote the original mistake)
                 - **Corrected Form** (show the correct version)
                 - **Explanation** (briefly explain what was wrong and what rule was applied)
            
            3. **Additional Notes (if applicable):**
               - Suggest style improvements (e.g., unnatural phrases or awkward wording).
               - If any part of the text is ambiguous, explain possible meanings.
            
            **Important:**
            - Be accurate. Do NOT make up errors that are not in the text.
            - If the text is completely correct, simply write: "No errors found."
            - Use simple, clear English for all explanations.
            - **If the answer is in Russian, write everything using the Cyrillic alphabet (кириллица). Do NOT use Latin letters in Russian text.**
        """

        return self.chat_manager.send_message(
            prompt,
            system_prompt="You are an English teacher correcting student's work.",
            chat_id=self.chat_manager.current_chat_id,
            temperature=0.4
        )

    def simple_converse(self, message):
        answer = self.chat_manager.send_message(
            message.text,
            chat_id=self.chat_manager.current_chat_id,
            system_prompt="You are an English teacher. Respond in English, correct mistakes when you see them."
        )
        return ''.join(answer) if hasattr(answer, '__iter__') else str(answer)