import openai
from typing import Optional, List, Dict, Any
import time
from functools import wraps
import logging
from .config import config

logger = logging.getLogger(__name__)


class RateLimiter:
    """Простой rate limiter"""

    def __init__(self, calls_per_minute: int):
        self.calls_per_minute = calls_per_minute
        self.calls = []

    def wait_if_needed(self):
        now = time.time()
        # Удаляем вызовы старше минуты
        self.calls = [call_time for call_time in self.calls
                      if now - call_time < 60]

        if len(self.calls) >= self.calls_per_minute:
            sleep_time = 60 - (now - self.calls[0])
            if sleep_time > 0:
                logger.info(f"Rate limit reached, sleeping {sleep_time:.2f}s")
                time.sleep(sleep_time)

        self.calls.append(now)


class OpenRouterClient:
    """Клиент для работы с OpenRouter API"""

    def __init__(self, api_key: str, base_url: str):
        self.client = openai.OpenAI(
            api_key=api_key,
            base_url=base_url
        )
        self.rate_limiter = RateLimiter(config.RATE_LIMIT_PER_MINUTE)

    def generate(
            self,
            messages: List[Dict[str, str]],
            model: str = None,
            temperature: float = None,
            max_tokens: int = None,
            response_format: Optional[Dict] = None,
            **kwargs
    ) -> str:
        """
        Основной метод для генерации

        Args:
            messages: Список сообщений [{"role": "user", "content": "..."}]
            model: ID модели (по умолчанию из config)
            temperature: Температура генерации (0-2)
            max_tokens: Максимум токенов в ответе
            response_format: {"type": "json_object"} для JSON-ответов

        Returns:
            Текст ответа от модели
        """
        model = model or config.MODELS["primary"]
        temperature = temperature or config.DEFAULT_TEMPERATURE
        max_tokens = max_tokens or config.DEFAULT_MAX_TOKENS

        self.rate_limiter.wait_if_needed()

        try:
            response = self.client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                response_format=response_format,
                **kwargs
            )

            content = response.choices[0].message.content

            # Логирование использования токенов
            usage = response.usage
            logger.info(
                f"Tokens used: {usage.total_tokens} "
                f"(prompt: {usage.prompt_tokens}, "
                f"completion: {usage.completion_tokens})"
            )

            return content

        except openai.APIError as e:
            logger.error(f"OpenRouter API error: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            raise

    def generate_with_retry(
            self,
            messages: List[Dict[str, str]],
            max_retries: int = None,
            **kwargs
    ) -> str:
        """Генерация с автоматическими повторами при ошибках"""
        max_retries = max_retries or config.MAX_RETRIES

        for attempt in range(max_retries):
            try:
                return self.generate(messages, **kwargs)
            except openai.RateLimitError:
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt  # Exponential backoff
                    logger.warning(f"Rate limit hit, waiting {wait_time}s")
                    time.sleep(wait_time)
                else:
                    raise
            except openai.APIError as e:
                if attempt < max_retries - 1 and e.status_code >= 500:
                    wait_time = 2 ** attempt
                    logger.warning(f"Server error, retrying in {wait_time}s")
                    time.sleep(wait_time)
                else:
                    raise

    def generate_streaming(
            self,
            messages: List[Dict[str, str]],
            **kwargs
    ):
        """Генерация с потоковой передачей (для UI в реальном времени)"""
        kwargs['stream'] = True

        response = self.client.chat.completions.create(
            messages=messages,
            **kwargs
        )

        for chunk in response:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content


# Глобальный экземпляр клиента
ai_client = OpenRouterClient(
    api_key=config.OPENROUTER_API_KEY,
    base_url=config.OPENROUTER_BASE_URL
)