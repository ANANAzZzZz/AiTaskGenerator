from typing import Dict, Any, List
from enum import Enum


class CEFRLevel(str, Enum):
    """Уровни по европейской шкале"""
    A1 = "A1"  # Beginner
    A2 = "A2"  # Elementary
    B1 = "B1"  # Intermediate
    B2 = "B2"  # Upper-Intermediate
    C1 = "C1"  # Advanced
    C2 = "C2"  # Proficient


class ExerciseType(str, Enum):
    FILL_BLANKS = "fill_blanks"
    MULTIPLE_CHOICE = "multiple_choice"
    ERROR_CORRECTION = "error_correction"
    SENTENCE_TRANSFORMATION = "sentence_transformation"
    MATCHING = "matching"
    DIALOGUE = "dialogue_completion"


class PromptBuilder:
    """Конструктор промптов для генерации заданий"""

    # Базовый системный промпт
    SYSTEM_PROMPT = """You are an expert English language teacher with 20 years of experience creating educational materials. Your exercises are:
- Pedagogically sound and appropriate for the target CEFR level
- Natural and realistic (avoid artificial or overly academic language)
- Culturally neutral and appropriate for international learners
- Free of grammatical errors
- Engaging and relevant to real-life situations

Always provide clear instructions and, when applicable, answer keys with explanations."""

    # Промпты для разных типов заданий
    EXERCISE_TEMPLATES = {
        ExerciseType.FILL_BLANKS: """Create {count} fill-in-the-blank exercises for {level} level students.

Grammar focus: {grammar_topic}
Vocabulary theme: {theme}
Context: {context}

Requirements:
- Each sentence should have ONE blank to fill
- Provide the correct answer
- Sentences should be 10-20 words long
- Use natural, everyday language appropriate for {level}
- Ensure variety in sentence structure

Return ONLY a valid JSON object with this exact structure:
{{
    "exercises": [
        {{
            "sentence": "I _____ to the gym three times a week.",
            "blank_position": 1,
            "correct_answer": "go",
            "explanation": "Simple present for habits and routines",
            "hint": "verb of movement"
        }}
    ]
}}""",

        ExerciseType.MULTIPLE_CHOICE: """Create {count} multiple-choice questions for {level} level students.

Grammar focus: {grammar_topic}
Vocabulary theme: {theme}

Requirements:
- Each question has 4 options (A, B, C, D)
- Only one correct answer
- Distractors should be plausible but clearly wrong
- Questions should test understanding, not just memorization
- Difficulty appropriate for {level}

Return ONLY a valid JSON object:
{{
    "exercises": [
        {{
            "question": "She _____ in London for five years.",
            "options": {{
                "A": "lives",
                "B": "has lived",
                "C": "is living",
                "D": "lived"
            }},
            "correct_answer": "B",
            "explanation": "Present Perfect for actions that started in the past and continue to the present"
        }}
    ]
}}""",

        ExerciseType.ERROR_CORRECTION: """Create {count} error correction exercises for {level} level students.

Grammar focus: {grammar_topic}
Error types to include: {error_types}

Requirements:
- Each sentence contains EXACTLY ONE error
- Errors should be common mistakes for {level} learners
- Sentences should be realistic and natural
- Provide the corrected version

Return ONLY a valid JSON object:
{{
    "exercises": [
        {{
            "incorrect_sentence": "I am living in London since 2020.",
            "error_type": "verb tense",
            "correct_sentence": "I have lived in London since 2020.",
            "explanation": "Use Present Perfect (have lived) not Present Continuous with 'since'"
        }}
    ]
}}""",

        ExerciseType.DIALOGUE: """Create {count} dialogue completion exercises for {level} level students.

Context: {context}
Functions to practice: {language_functions}

Requirements:
- Realistic conversational situations
- 4-6 turns in each dialogue
- One blank to complete per dialogue
- Multiple plausible options for the blank
- Appropriate formality level for {level}

Return ONLY a valid JSON object:
{{
    "exercises": [
        {{
            "context": "At a restaurant",
            "dialogue": [
                {{"speaker": "Waiter", "text": "Good evening. Table for two?"}},
                {{"speaker": "Customer", "text": "Yes, please. _____"}},
                {{"speaker": "Waiter", "text": "Certainly, right this way."}}
            ],
            "blank_position": 1,
            "options": [
                "Do you have a reservation?",
                "By the window if possible.",
                "What time do you close?",
                "The menu, please."
            ],
            "correct_answer": "By the window if possible.",
            "explanation": "Natural response to offer of a table"
        }}
    ]
}}"""
    }

    @classmethod
    def build_prompt(
            cls,
            exercise_type: ExerciseType,
            level: CEFRLevel,
            count: int = 5,
            grammar_topic: str = None,
            theme: str = "general",
            context: str = "everyday situations",
            **kwargs
    ) -> List[Dict[str, str]]:
        """
        Построить промпт для генерации заданий

        Returns:
            Список сообщений для API в формате [{"role": "...", "content": "..."}]
        """

        # Получаем шаблон для типа задания
        template = cls.EXERCISE_TEMPLATES.get(exercise_type)
        if not template:
            raise ValueError(f"Unknown exercise type: {exercise_type}")

        # Заполняем параметры
        user_prompt = template.format(
            count=count,
            level=level.value,
            grammar_topic=grammar_topic or "mixed grammar",
            theme=theme,
            context=context,
            **kwargs
        )

        # Формируем сообщения для API
        messages = [
            {"role": "system", "content": cls.SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt}
        ]

        return messages

    @classmethod
    def build_custom_prompt(
            cls,
            instructions: str,
            level: CEFRLevel,
            examples: List[str] = None
    ) -> List[Dict[str, str]]:
        """Построить кастомный промпт с примерами (few-shot learning)"""

        messages = [{"role": "system", "content": cls.SYSTEM_PROMPT}]

        # Добавляем примеры, если есть
        if examples:
            for i, example in enumerate(examples):
                messages.extend([
                    {"role": "user", "content": f"Example {i + 1}: {example}"},
                    {"role": "assistant", "content": "Understood. I'll follow this format."}
                ])

        # Добавляем основную инструкцию
        messages.append({
            "role": "user",
            "content": f"Level: {level.value}\n\n{instructions}"
        })

        return messages