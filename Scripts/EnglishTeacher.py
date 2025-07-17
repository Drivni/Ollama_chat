from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton


class EnglishTeacher:
    def __init__(self, chat_manager):
        self.chat_manager = chat_manager
        self.modes = {
            'chat': "Свободный чат на английском",
            'correction': "Исправления ошибок",
            'exercises': "Упражнения"
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
            Your task is to generate an **English language learning exercise**. Follow all rules carefully.
            
            ===========================
            🔹 BASIC PARAMETERS
            ===========================
            
            - **EXERCISE TYPE**: {ex_type}
            - **LEVEL**: {self.user_level} (based on CEFR: A1–C2)
            - **LANGUAGE**: Use **ENGLISH ONLY** in the task and answers.
            
            ===========================
            🔹 REQUIRED STRUCTURE
            ===========================
            
            1. [Instructions]  
               - Write 1–2 clear, short sentences.  
               - Start with a **verb** (e.g. "Choose", "Match", "Rewrite").  
               - Indicate how the learner should respond.
            
            2. [Exercise]  
               - Include **3 to 5** items  
               - Each item must:  
                 • Be self-contained  
                 • Use vocabulary and grammar appropriate for {self.user_level}  
                 • Include context if needed for understanding
            
            3. [Answer]  
               - Provide only the correct answers  
               - Use the same numbering  
               - No explanations unless asked
            
            ===========================
            🔴 STRICT RULES
            ===========================
            
            - No translations or mixed languages.
            - Do not use Russian in the main content.
            - If absolutely needed: use short teacher notes in Cyrillic in square brackets  
              Example: [Для отработки вопросов в Past Simple]
            
            ===========================
            🟦 OPTIONAL EXPLANATION
            ===========================
            
            If appropriate, you may add an [Explanation] section:  
            - Use **simple English**  
            - Max 3–4 sentences  
            - Only if it adds value or clarifies tricky items
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
            chat_id=self.chat_manager.current_chat_id
        )

    def simple_converse(self, message):
        answer = self.chat_manager.send_message(
            message.text,
            chat_id=self.chat_manager.current_chat_id,
            system_prompt="You are an English teacher. Respond in English, correct mistakes when you see them."
        )
        return ''.join(answer) if hasattr(answer, '__iter__') else str(answer)