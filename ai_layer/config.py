from typing import List, Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class AIConfig(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    # API настройки
    OPENROUTER_API_KEY: Optional[str] = None
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"

    # Модели (можно переопределить через .env)
    OPENROUTER_PRIMARY_MODEL: str = "openai/gpt-4o-mini"
    OPENROUTER_FALLBACK_MODELS: str = ""

    # Параметры генерации
    DEFAULT_TEMPERATURE: float = 0.7  # Креативность (0-2)
    DEFAULT_MAX_TOKENS: int = 2000
    DEFAULT_TOP_P: float = 0.9

    # Полу-агент пайплайн
    MIN_QUALITY_SCORE_FOR_ACCEPT: float = 0.6
    ENABLE_OPTIONAL_REFINEMENT: bool = True

    # Опциональный кэш/БД упражнений
    ENABLE_EXERCISE_CACHE: bool = False
    EXERCISE_DB_PATH: str = "exercises.db"

    # Лимиты и retry
    MAX_RETRIES: int = 3
    TIMEOUT: int = 30
    RATE_LIMIT_PER_MINUTE: int = 60


    def require_api_key(self) -> str:
        """Возвращает API ключ или выбрасывает понятную ошибку конфигурации."""
        if not self.OPENROUTER_API_KEY:
            raise ValueError("OPENROUTER_API_KEY is not set. Add it to .env or environment variables.")
        return self.OPENROUTER_API_KEY

    def get_model_candidates(self, explicit_model: Optional[str] = None) -> List[str]:
        """Возвращает список моделей по приоритету: explicit -> primary -> fallback list."""
        if explicit_model:
            return [explicit_model]

        candidates = [self.OPENROUTER_PRIMARY_MODEL]
        fallback = [m.strip() for m in self.OPENROUTER_FALLBACK_MODELS.split(",") if m.strip()]
        for model in fallback:
            if model not in candidates:
                candidates.append(model)
        return candidates


config = AIConfig()