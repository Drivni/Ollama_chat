import json
import sqlite3
import requests


class ChatDatabase:
    def __init__(self, db_name='chat_history.db'):
        self.conn = sqlite3.connect(db_name, check_same_thread=False)
        self.create_tables()

    def create_tables(self):
        cursor = self.conn.cursor()
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS chats (
            chat_id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            message_id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER,
            role TEXT CHECK(role IN ('user', 'assistant', 'system')),
            content TEXT,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (chat_id) REFERENCES chats (chat_id)
        )
        ''')
        self.conn.commit()

    def create_chat(self, title="New Chat"):
        cursor = self.conn.cursor()
        cursor.execute('INSERT INTO chats (title) VALUES (?)', (title,))
        self.conn.commit()
        return cursor.lastrowid

    def add_message(self, chat_id, role, content):
        cursor = self.conn.cursor()
        cursor.execute('''
        INSERT INTO messages (chat_id, role, content)
        VALUES (?, ?, ?)
        ''', (chat_id, role, content))
        self.conn.commit()
        return cursor.lastrowid

    def delete_chat(self, chat_id):
        cursor = self.conn.cursor()
        cursor.execute('DELETE FROM messages WHERE chat_id = ?', (chat_id,))
        cursor.execute('DELETE FROM chats WHERE chat_id = ?', (chat_id,))
        self.conn.commit()

    def rename_chat(self, chat_id, new_title):
        cursor = self.conn.cursor()
        cursor.execute('UPDATE chats SET title = ? WHERE chat_id = ?', (new_title, chat_id))
        self.conn.commit()

    def clear_chat_history(self, chat_id):
        cursor = self.conn.cursor()
        cursor.execute('DELETE FROM messages WHERE chat_id = ?', (chat_id,))
        self.conn.commit()

    def get_chat_history(self, chat_id, limit=20, offset=0):
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
            SELECT role, content, timestamp 
            FROM messages 
            WHERE chat_id = ? 
            ORDER BY timestamp DESC 
            LIMIT ? OFFSET ?
            ''', (chat_id, limit, offset))
            return cursor.fetchall()

        except sqlite3.Error as e:
            print(f"Ошибка базы данных: {str(e)}")
            return []
        except ValueError as e:
            print(f"Ошибка параметров: {str(e)}")
            return []
        except Exception as e:
            print(f"Неожиданная ошибка: {str(e)}")
            return []

    def list_chats(self):
        self.conn.row_factory = sqlite3.Row  # Устанавливаем row_factory
        cursor = self.conn.cursor()
        cursor.execute('''SELECT 
            ROW_NUMBER() OVER (ORDER BY chat_id DESC) as "index",
            chat_id, title,
            created_at FROM chats ORDER BY created_at DESC''')

        # Возвращаем словари напрямую
        return [dict(row) for row in cursor.fetchall()]

    def get_message_count(self, chat_id):
        cursor = self.conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM messages WHERE chat_id = ?', (chat_id,))
        return cursor.fetchone()[0]

    def get_last_activity(self, chat_id):
        cursor = self.conn.cursor()
        cursor.execute('''
        SELECT MAX(timestamp) 
        FROM messages 
        WHERE chat_id = ?
        ''', (chat_id,))
        return cursor.fetchone()[0]

    def close(self):
        self.conn.close()


class OllamaChat:
    def __init__(self, model="llama3.1:latest", base_url="http://localhost:11434"):
        self.model = model
        self.base_url = base_url
        self.db = ChatDatabase()
        self.current_chat_id = None

    def start_new_chat(self, title=None):
        if not self.list_chats():
            title = "Новый чат"
        if title is None:
            title = f"Чат {int(self.list_chats()[-1]['chat_id']) + 1}"
        self.current_chat_id = self.db.create_chat(title)
        return self.current_chat_id

    def delete_chat(self, chat_id):
        self.db.delete_chat(chat_id)
        if self.current_chat_id == chat_id:
            self.current_chat_id = None

    def rename_chat(self, chat_id, new_title):
        self.db.rename_chat(chat_id, new_title)

    def send_message(self, message, stream=False, chat_id=None):
        if chat_id is None:
            if self.current_chat_id is None:
                self.start_new_chat()
            chat_id = self.current_chat_id

        # Сохраняем сообщение пользователя
        self.db.add_message(chat_id, 'user', message)

        # Получаем историю чата для контекста
        history = self.db.get_chat_history(chat_id)

        # Формируем сообщения для Ollama API
        messages = [{"role": "user" if role == "user" else "assistant", "content": content}
                    for role, content, _ in reversed(history)]

        # Отправляем запрос к Ollama API с потоковым выводом
        response = requests.post(
            f"{self.base_url}/api/chat",
            json={
                "model": self.model,
                "messages": messages,
                "stream": stream  # Включаем потоковый режим
            },
            stream=stream  # Важно для обработки потокового ответа
        )

        if response.status_code == 200:
            assistant_message = ""
            # Читаем потоковые данные
            for line in response.iter_lines():
                if line:
                    # Декодируем JSON из каждой строки
                    chunk = json.loads(line.decode('utf-8'))
                    if 'message' in chunk and 'content' in chunk['message']:
                        content = chunk['message']['content']
                        assistant_message += content
                        yield content  # Постепенно возвращаем части сообщения

            # После завершения потока сохраняем полное сообщение
            self.db.add_message(chat_id, 'assistant', assistant_message)
            return assistant_message
        else:
            raise Exception(f"Ошибка API: {response.status_code} - {response.text}")

    def list_chats(self):
        return self.db.list_chats()

    def load_chat(self, chat_id):
        self.current_chat_id = chat_id
        return self.db.get_chat_history(chat_id)

    def find_chat_name(self, **criteria):
        for chat in self.list_chats():
            if all(
                    str(chat.get(k)) == str(v)
                    for k, v in criteria.items()
                    if v is not None
            ):
                return chat['title']
        return None

    def close(self):
        self.db.close()


class ChatManager(OllamaChat):
    def print_all_chats(self):
        chat_list = self.list_chats()
        if not chat_list:
            return "Чаты не найдены"

        chats = []
        for el in chat_list:
            chats.append(f"{el['index']}.(ID-{el['chat_id']}): {el['title']} ({el['created_at']})")

        print("\n".join(chats))

    def start_chat(self):
        print("Доступные чаты:")
        self.print_all_chats()

        # Создаем новый чат или используем существующий
        if not self.list_chats():
            self.start_new_chat()
            print("Создан новый чат")
        else:
            self.current_chat_id = self.list_chats()[0]["chat_id"]
            print(f"Используем существующий чат ID: {self.current_chat_id}")

    def do_command(self, command: str):
        words = command.split()

        if len(words) > 1:
            command_text = ' '.join(words[1:]).replace(" ", "")
        else:
            command_text = ""

        if "/show" in command:
            chat_name = self.find_chat_name(chat_id=self.current_chat_id)
            print(f"Выбранный чат: (ID-{self.current_chat_id}): {chat_name}")
            self.print_all_chats()

        if "/delete" in command:
            # Если указан конкретный ID чата для удаления
            if command_text and command_text.isdigit():
                chat_name = self.find_chat_name(chat_id=command_text)
                if not chat_name:
                    print("Чат с таким ID не найден")
                    return

                self.delete_chat(command_text)
                print(f'Чат "{chat_name}" удален!')

                # Если удаляем текущий чат, создаем новый автоматически
                if self.current_chat_id == command_text:
                    self.start_new_chat()
                    new_chat_name = self.find_chat_name(chat_id=self.current_chat_id)
                    print(f"Автоматически создан новый чат: {new_chat_name}")
                return

            # Если пытаемся удалить с нечисловым параметром
            if command_text:
                print("Неправильный параметр - ID чата должен быть числом")
                return

            # Удаление всех чатов (когда command_text пуст)
            confirm = input("Вы уверены, что хотите удалить все чаты? (y/n): ")
            if confirm.lower() != 'y':
                print("Удаление отменено")
                return

            for select_chat in self.list_chats():
                self.delete_chat(select_chat["chat_id"])
            print("Все чаты удалены!")

            # Создаем новый чат после удаления всех
            self.start_new_chat()
            print("Автоматически создан новый чат")

        if "/new" in command:
            if command_text == "":
                self.start_new_chat()
                chat_name = self.find_chat_name(chat_id=self.current_chat_id)
                print(f"Создан и выбран новый чат: {chat_name}")
            else:
                self.start_new_chat(command_text)
                print(f"Создан и выбран новый чат: {command_text}")

        if "/select" in command:
            if not command_text:
                print("Укажите ID чата для выбора")
                return

            chat_name = self.find_chat_name(chat_id=command_text)

            if command_text.isdigit() and chat_name:
                self.current_chat_id = command_text
                print(f'Выбран чат (ID-{command_text}): "{chat_name}"')
            else:
                print("Чат с таким ID не найден")

        if "/history" in command:
            # Обработка флага удаления истории
            if command_text == "-d":
                confirm = input("Вы уверены, что хотите удалить всю историю? (y/n): ")
                if confirm.lower() != 'y':
                    print("Удаление отменено")
                    return
                self.db.clear_chat_history(chat_id=self.current_chat_id)
                print("История текущего чата удалена!")
                return

            # Получение истории
            limit = 20
            if command_text.isdigit():
                limit = int(command_text)
                if limit <= 0:
                    print("Количество сообщений должно быть положительным числом")
                    return

            history = self.db.get_chat_history(self.current_chat_id, limit=limit)

            if not history:
                print("История сообщений пуста")
                return

            messages = [{"role": "user" if role == "user" else "assistant", "content": content}
                        for role, content, _ in reversed(history)]

            print(f"\nИстория сообщений (всего: {len(messages)}):")
            for message in messages:
                print(f"{message['role']}: {message['content']}")

        if "/help" in command or "/?" in command:
            print("\nДоступные команды:")
            print("/help или /? - показать это сообщение")
            print("/new [имя] - создать новый чат (с именем или без)")
            print("/select <ID> - выбрать чат по ID")
            print("/show - показать информацию о текущем чате и список всех чатов")
            print("/delete [ID] - удалить конкретный чат или все чаты")
            print("/history [N/-d] - показать историю сообщений (N последних или всю), -d - удалить историю")

        if "/try" in command:
            print(self.find_chat_name(chat_id=input("Number: ")))


# Пример использования
if __name__ == "__main__":
    chat = ChatManager()
    chat.start_chat()
    # Пример диалога
    while True:
        user_input = input("\nВы: ")
        if user_input.lower() in ['/exit', '/quit', '/выход']:
            break
        if user_input[0] == "/":
            chat.do_command(command=user_input)
            continue

        try:
            print("Ассистент: ", end="")
            for chunk in chat.send_message(user_input, stream=True):
                print(chunk, end='', flush=True)
        except Exception as e:
            print(f"Произошла ошибка: {e}")

    chat.close()
    print("Чат завершен. История сохранена.")