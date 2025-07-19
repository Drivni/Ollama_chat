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


def _get_weather(latitude: float, longitude: float) -> Dict[str, Any]:
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
        tools_prompt += "```json\n{\"arg1\": value1, \"arg2\": value2}\n```\n\n"

        tools_prompt += "TOOLS:\n"
        for tool_name, tool_info in self.tools.items():
            tools_prompt += f"- {tool_name}: {tool_info['description']}\n"
            tools_prompt += f"  Parameters: {json.dumps(tool_info['parameters'], indent=2)}\n\n"

        return tools_prompt

    def _extract_tool_call(self, response: str) -> Optional[Dict[str, Any]]:
        """Extract tool call information from LLM response."""
        if self.tool_call_prefix not in response:
            return None

        try:
            # Split on the tool call prefix
            parts = response.split(self.tool_call_prefix, 1)[1].strip()

            # Split tool name and JSON args
            tool_part, *json_parts = parts.split("\n", 1)
            tool_name = tool_part.strip()

            args = {}
            if json_parts:
                args_part = str(json_parts[0].strip())
                try:
                    args = json.loads(args_part)
                except json.JSONDecodeError:
                    if self.verbose:
                        print(f"Invalid JSON in tool call: {args_part}")
                    return None

            if tool_name in self.tools:
                return {"name": tool_name, "arguments": args}

        except Exception as e:
            if self.verbose:
                print(f"Error parsing tool call: {e}")

        return None

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
            chat_id: int = 1,
            max_attempts: int = 3,
    ):
        chat_id = self.get_current_chat_id()
        global response
        attempts = 0
        last_response = message

        while attempts < max_attempts:
            # Generate full prompt with tools
            full_system_prompt = f"{self.system_prompt}{self._generate_tools_prompt()}"

            # Get LLM response
            response = super().send_message(
                message=last_response,
                chat_id=chat_id,
                stream=False,  # Need complete response for tool parsing
                system_prompt=full_system_prompt,
                temperature=self.temperature,
                limit=attempts * 2 + 1
            )

            # Check for tool call
            tool_call = self._extract_tool_call(response)

            if not tool_call:
                return response

            # Execute tool
            try:
                tool_result = self._call_tool(tool_call["name"], tool_call["arguments"])
                tool_result_msg = self._format_tool_result(tool_call["name"], tool_result)
                self.db.add_message(chat_id, 'user', tool_result_msg)

                last_response = "Выведи результат в человеческом виде"
                attempts += 1
                time.sleep(1)

            except Exception as e:
                error_msg = f"Error calling tool {tool_call['name']}: {str(e)}"
                if chat_id is not None:
                    self.db.add_message(chat_id, 'assistant', error_msg)
                return error_msg

        return response


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
        function=_get_weather
    )


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
        response = agent.chat(user_input)

        print(response)
