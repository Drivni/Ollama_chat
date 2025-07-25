import json
import os
from googleapiclient.discovery import build
from urllib.parse import urlparse
import requests
from typing import Dict, Any, Callable, Optional, List, Union, Generator
from Scripts.main import OllamaChat
import time
from API import Key_google, Search_ID


class GoogleAPISearch:
    def __init__(self, api_key=None, search_engine_id=None):
        """
        :param api_key: Ваш API ключ (можно через переменную окружения GOOGLE_API_KEY)
        :param search_engine_id: ID поисковой системы (можно через GOOGLE_SEARCH_ENGINE_ID)
        """
        self.api_key = api_key or os.getenv('GOOGLE_API_KEY')
        self.search_engine_id = search_engine_id or os.getenv('GOOGLE_SEARCH_ENGINE_ID')
        self.service = build("customsearch", "v1", developerKey=self.api_key)

    def search(self, query, num_results=1, lang='ru', **kwargs):
        if not self.api_key or not self.search_engine_id:
            raise ValueError("Требуется API ключ и ID поисковой системы")

        try:
            res = self.service.cse().list(
                q=query,
                cx=self.search_engine_id,
                num=min(num_results, 10),  # Официальное API ограничивает num <= 10
                hl=lang,
                **kwargs
            ).execute()

            return [{
                'title': item.get('title', ''),
                'link': item.get('link', ''),
                'snippet': item.get('snippet', ''),
                'domain': urlparse(item.get('link', '')).netloc
            } for item in res.get('items', [])]

        except Exception as e:
            print(f"Ошибка Google API: {e}")
            return []


class AgentFunctions:
    @staticmethod
    def get_weather(latitude: float, longitude: float) -> Dict[str, Any]:
        try:
            response_weather = requests.get(
                f"https://api.open-meteo.com/v1/forecast?latitude={latitude}&longitude={longitude}&timezone=auto"
                f"&current=temperature_2m,wind_speed_10m&hourly=temperature_2m,relative_humidity_2m,wind_speed_10m",
                timeout=10
            )
            response_weather.raise_for_status()
            return response_weather.json()["current"]
        except requests.RequestException as e:
            return {"error": str(e)}

    @staticmethod
    def get_nbrb_currency_rate(currency_code):
        """Получает курс валюты по отношению к BYN."""
        try:
            url = f"https://api.nbrb.by/exrates/rates/{currency_code}?parammode=2"
            response = requests.get(url)
            response.raise_for_status()  # Проверка на ошибки HTTP

            data = response.json()
            rate = data["Cur_OfficialRate"]
            scale = data["Cur_Scale"]  # Например, для USD scale=1, а для JPY scale=100

            return rate / scale  # Возвращаем курс за 1 единицу валюты

        except requests.exceptions.RequestException as e:
            print(f"Ошибка при запросе к API: {e}")
            return None
        except KeyError:
            print(f"Валюта {currency_code} не найдена или API изменилось.")
            return None

    @staticmethod
    def convert_currency(from_currency: str, to_currency: str, amount: float = 1) -> float or None:
        """Конвертирует сумму из одной валюты в другую."""
        if from_currency.upper() == "BYN":
            rate_to = AgentFunctions.get_nbrb_currency_rate(to_currency)
            if rate_to is None:
                return None
            converted_amount = amount / rate_to
        elif to_currency.upper() == "BYN":
            rate_from = AgentFunctions.get_nbrb_currency_rate(from_currency)
            if rate_from is None:
                return None
            converted_amount = amount * rate_from
        else:
            # Конвертация через BYN (например, USD → EUR)
            rate_from = AgentFunctions.get_nbrb_currency_rate(from_currency)
            rate_to = AgentFunctions.get_nbrb_currency_rate(to_currency)

            if rate_from is None or rate_to is None:
                return None

            converted_amount = (amount * rate_from) / rate_to

        return round(converted_amount, 4)


def init_func(ai_agent):
    # Register base tools
    ai_agent.register_tool(
        name="get_weather",
        description="Get current weather for provided coordinates in celsius.",
        parameters={
            "type": "object",
            "properties": {
                "latitude": {"type": "number", "description": "Latitude in decimal degrees"},
                "longitude": {"type": "number", "description": "Longitude in decimal degrees"},
            },
            "required": ["latitude", "longitude"],
        },
        function=AgentFunctions.get_weather
    )
    ai_agent.register_tool(
        name="convert_currency",
        description="Convert amount from one currency to another",
        parameters={
            "type": "object",
            "properties": {
                "from_currency": {"type": "string",
                                  "description": "Currency code to convert from (e.g., USD, EUR, RUB)"},
                "to_currency": {"type": "string", "description": "Currency code to convert to (e.g., BYN, EUR, USD)"},
                "amount": {"type": "number", "description": "Amount to convert", "default": 1}
            },
            "required": ["amount", "from_currency", "to_currency"],
        },
        function=AgentFunctions.convert_currency
    )


class Agent(OllamaChat):
    def __init__(
            self,
            model: str = "llama3.1:latest",
            base_url: str = "http://localhost:11434",
            system_prompt: str = "You are a helpful AI assistant.",
            temperature: float = 0.7,
            verbose: bool = False,
            tool_call_prefix: str = "TOOL:"
    ):
        super().__init__(model=model, base_url=base_url)
        self.system_prompt = system_prompt
        self.temperature = temperature
        self.verbose = verbose
        self.tool_call_prefix = tool_call_prefix
        self.tools: Dict[str, Dict] = {}

    def register_tool(
            self,
            name: str,
            description: str,
            parameters: Dict[str, Any],
            function: Callable
    ) -> None:

        if not isinstance(parameters, dict):
            raise ValueError("Parameters must be a valid JSON schema dictionary")

        self.tools[name] = {
            "description": description,
            "parameters": parameters,
            "function": function
        }

        if self.verbose:
            print(f"Registered tool: {name}")

    def _generate_tools_prompt(self) -> str:
        """Generate prompt section describing available tools."""
        if not self.tools:
            return ""

        tools_prompt = "\n\nAVAILABLE TOOLS:\n"
        tools_prompt += f"To call a tool, respond with exactly:\n{self.tool_call_prefix} tool_name\n"
        tools_prompt += "```json\n{\"arg1\": value1, \"arg2\": value2}\n```\nDON'T ADD ANYTHING EXTRA\n\n"

        tools_prompt += "TOOLS:\n"
        for tool_name, tool_info in self.tools.items():
            tools_prompt += f"- {tool_name}: {tool_info['description']}\n"
            tools_prompt += f"  Parameters: {json.dumps(tool_info['parameters'], indent=2)}\n\n"

        return tools_prompt

    def _extract_tool_calls(self, response: str) -> List[Dict[str, Any]]:
        """Extract multiple tool call information from LLM response."""
        if self.tool_call_prefix not in response:
            return []

        tool_calls = []
        # Split the response by the tool call prefix to find all tool calls
        parts = response.split(self.tool_call_prefix)[1:]  # Skip the first part (before first prefix)

        for part in parts:
            try:
                part = part.strip()
                if not part:
                    continue

                # Split tool name and JSON args
                tool_part, *json_parts = part.split("\n", 1)
                tool_name = tool_part.strip()

                args = {}
                if json_parts:
                    args_part = json_parts[0].strip()
                    try:
                        args = json.loads(args_part)
                    except json.JSONDecodeError:
                        if self.verbose:
                            print(f"Invalid JSON in tool call: {args_part}")
                        continue  # Skip this tool call but try others

                if tool_name in self.tools:
                    tool_calls.append({"name": tool_name, "arguments": args})

            except Exception as e:
                if self.verbose:
                    print(f"Error parsing tool call: {e}")
                continue  # Skip this tool call but try others

        return tool_calls

    def _call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Execute a registered tool with provided arguments."""
        if tool_name not in self.tools:
            raise ValueError(f"Tool '{tool_name}' not found in registered tools")

        # Validate arguments against schema
        tool_params = self.tools[tool_name]["parameters"]
        # Add schema validation here if needed

        return self.tools[tool_name]["function"](**arguments)

    @staticmethod
    def _format_tool_result(tool_name: str, result: Any) -> str:
        """Format tool result for LLM consumption."""
        try:
            result_str = json.dumps(result, indent=2)
        except TypeError:
            result_str = str(result)

        return f"RESULT FROM {tool_name}:\n```json\n{result_str}\n```"

    def chat(
            self,
            message: str,
            max_attempts: int = 3
    ):
        global response
        attempts = 0
        last_response = message

        while attempts < max_attempts:
            chat_id = self.current_chat_id
            # Generate full prompt with tools
            full_system_prompt = f"{self.system_prompt}{self._generate_tools_prompt()}"

            # Get LLM response
            response = super().send_message(
                message=last_response,
                chat_id=chat_id,
                stream=False,  # Need complete response for tool parsing
                system_prompt=full_system_prompt,
                temperature=self.temperature,
                limit=attempts * 2 + 5
            )

            # Check for tool call
            tool_calls = self._extract_tool_calls(response)

            if not tool_calls:
                return response

            error_tool = None
            # Execute tool
            try:
                tool_result_msg = ""
                for tool_call in tool_calls:
                    error_tool = tool_call
                    tool_result = self._call_tool(tool_call["name"], tool_call["arguments"])
                    tool_result_msg += self._format_tool_result(tool_call["name"], tool_result) + "\n"
                self.db.add_message(chat_id, 'user', tool_result_msg)

                last_response = ("Попробуй собрать еще информацию, но только если это необходимо "
                                 "или выведи ответ в доступной форме согласно условию запроса")
                attempts += 1
                time.sleep(1)

            except Exception as e:
                error_msg = f"Error calling tool {error_tool['name']}: {str(e)}"
                if chat_id is not None:
                    self.db.add_message(chat_id, 'assistant', error_msg)
                return error_msg

        return response


# Пример использования
if __name__ == "__main__":
    agent = Agent(
        model="llama3.1:latest",
        temperature=0.7,
        system_prompt="You are a helpful assistant.",
        verbose=True)
    init_func(agent)

    while True:
        user_input = input("\nYou: ")

        if user_input.lower() in ('exit', 'quit'):
            break

        # Для демонстрации вызова инструмента можно использовать пример:
        # "What's the weather at latitude 48.8566 and longitude 2.3522?"
        response1 = agent.chat(user_input)

        print(response1)
