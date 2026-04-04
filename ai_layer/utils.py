import os
import sys


def get_python_executable() -> str:
	"""Возвращает путь к текущему Python интерпретатору."""
	return sys.executable


def is_api_key_configured() -> bool:
	"""Проверяет, задан ли ключ OpenRouter в окружении."""
	return bool(os.getenv("OPENROUTER_API_KEY"))
