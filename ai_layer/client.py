import openai
from typing import Optional, List, Dict, Any, cast
import time
import logging
from .config import config

logger = logging.getLogger(__name__)


def _is_invalid_model_error(error: Exception) -> bool:
    text = str(error).lower()
    return "model identifier is invalid" in text or "invalid model" in text


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
            model: Optional[str] = None,
            temperature: Optional[float] = None,
            max_tokens: Optional[int] = None,
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
        model = model or config.OPENROUTER_PRIMARY_MODEL
        temperature = temperature or config.DEFAULT_TEMPERATURE
        max_tokens = max_tokens or config.DEFAULT_MAX_TOKENS

        self.rate_limiter.wait_if_needed()
        logger.info("LLM generate call: model=%s temperature=%s max_tokens=%s", model, temperature, max_tokens)

        try:
            request_payload: Dict[str, Any] = {
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                **kwargs,
            }
            if response_format is not None:
                request_payload["response_format"] = response_format

            response = self.client.chat.completions.create(
                **request_payload
            )

            content = response.choices[0].message.content
            if content is None:
                raise ValueError("Model returned empty content")

            # Логирование использования токенов
            usage = response.usage
            if usage:
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
            max_retries: Optional[int] = None,
            **kwargs
    ) -> str:
        """Генерация с автоматическими повторами при ошибках"""
        retries = max_retries or config.MAX_RETRIES
        explicit_model = kwargs.pop("model", None)
        model_candidates = config.get_model_candidates(explicit_model)
        last_error: Optional[Exception] = None

        logger.info("LLM generate_with_retry started: model_candidates=%s retries=%s", model_candidates, retries)

        for model in model_candidates:
            for attempt in range(retries):
                try:
                    logger.info("LLM attempt: model=%s attempt=%s/%s", model, attempt + 1, retries)
                    return self.generate(messages, model=model, **kwargs)
                except openai.RateLimitError as e:
                    last_error = e
                    if attempt < retries - 1:
                        wait_time = 2 ** attempt  # Exponential backoff
                        logger.warning(f"Rate limit hit, waiting {wait_time}s")
                        time.sleep(wait_time)
                    else:
                        raise
                except openai.APIError as e:
                    last_error = e
                    if _is_invalid_model_error(e):
                        logger.warning(f"Model '{model}' is invalid for current provider, trying next candidate")
                        break

                    status_code = getattr(e, "status_code", None)
                    if (
                        attempt < retries - 1
                        and isinstance(status_code, int)
                        and status_code >= 500
                    ):
                        wait_time = 2 ** attempt
                        logger.warning(f"Server error, retrying in {wait_time}s")
                        time.sleep(wait_time)
                    else:
                        raise

        if last_error and _is_invalid_model_error(last_error):
            raise ValueError(
                "No valid model configured for your OpenRouter provider. "
                "Set OPENROUTER_PRIMARY_MODEL (and optional OPENROUTER_FALLBACK_MODELS) in .env."
            )

        raise RuntimeError("Retry loop exited unexpectedly")

    def generate_streaming(
            self,
            messages: List[Dict[str, str]],
            **kwargs
    ):
        """Генерация с потоковой передачей (для UI в реальном времени)"""
        kwargs['stream'] = True
        kwargs.setdefault('model', config.OPENROUTER_PRIMARY_MODEL)

        request_payload: Dict[str, Any] = {"messages": messages, **kwargs}
        response = self.client.chat.completions.create(**request_payload)

        for chunk in response:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content


_ai_client: Optional[OpenRouterClient] = None


def get_ai_client() -> OpenRouterClient:
    """Ленивая инициализация клиента, чтобы импорт модулей не падал без ключа."""
    global _ai_client
    if _ai_client is None:
        _ai_client = OpenRouterClient(
            api_key=config.require_api_key(),
            base_url=config.OPENROUTER_BASE_URL,
        )
    return cast(OpenRouterClient, _ai_client)
