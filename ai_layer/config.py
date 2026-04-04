from pydantic_settings import BaseSettings
from typing import Dict, Any


class AIConfig(BaseSettings):
    # API настройки
    OPENROUTER_API_KEY: str
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"

    # Модели для разных задач
    MODELS: Dict[str, str] = {
        "primary": "anthropic/claude-3.5-sonnet",  # Основная модель
        "fast": "openai/gpt-3.5-turbo",  # Быстрая для простых задач
        "advanced": "openai/gpt-4-turbo",  # Сложные задачи
        "local": "meta-llama/llama-3-8b-instruct"  # Бюджетная опция
    }

    # Параметры генерации
    DEFAULT_TEMPERATURE: float = 0.7  # Креативность (0-2)
    DEFAULT_MAX_TOKENS: int = 2000
    DEFAULT_TOP_P: float = 0.9

    # Лимиты и retry
    MAX_RETRIES: int = 3
    TIMEOUT: int = 30
    RATE_LIMIT_PER_MINUTE: int = 60

    class Config:
        env_file = ".env"


config = AIConfig()