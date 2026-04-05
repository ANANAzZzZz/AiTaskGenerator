from __future__ import annotations

import json
import re
from typing import Dict, List


class FakeBenchmarkClient:
    """Deterministic stub for local/CI benchmark runs without OpenRouter."""

    def __init__(self) -> None:
        self.generation_calls = 0

    def generate_with_retry(self, messages: List[Dict[str, str]], **kwargs) -> str:  # noqa: ARG002
        user_content = "\n".join(m.get("content", "") for m in messages if m.get("role") == "user")

        if "Improve this generated JSON" in user_content:
            exercise_type = self._extract_refine_type(user_content)
            count = self._extract_count(user_content, fallback=5)
            return json.dumps({"exercises": self._make_exercises(exercise_type, count, valid=True)})

        if "Please improve it based on this feedback" in user_content:
            return json.dumps(
                {
                    "exercise": {
                        "sentence": "I went to school yesterday.",
                        "correct_answer": "went",
                        "explanation": "Use the irregular past form 'went'.",
                    }
                }
            )

        self.generation_calls += 1
        exercise_type = self._extract_generation_type(user_content)
        count = self._extract_count(user_content, fallback=5)

        # Every odd generation call returns one item less to trigger optional refinement.
        valid = self.generation_calls % 2 == 0
        produced_count = count if valid else max(1, count - 1)

        return json.dumps({"exercises": self._make_exercises(exercise_type, produced_count, valid=valid)})

    @staticmethod
    def _extract_count(text: str, fallback: int) -> int:
        match = re.search(r"Create\s+(\d+)\s+", text)
        if not match:
            return fallback
        return int(match.group(1))

    @staticmethod
    def _extract_refine_type(text: str) -> str:
        match = re.search(r"Exercise type:\s*([a-z_]+)", text)
        if match:
            return match.group(1)
        return "fill_blanks"

    @staticmethod
    def _extract_generation_type(text: str) -> str:
        markers = {
            "fill_blanks": "fill-in-the-blank",
            "multiple_choice": "multiple-choice",
            "error_correction": "error correction",
            "sentence_transformation": "sentence transformation",
            "matching": "matching exercises",
            "dialogue_completion": "dialogue completion",
        }
        lowered = text.lower()
        for key, marker in markers.items():
            if marker in lowered:
                return key
        return "fill_blanks"

    @staticmethod
    def _make_exercises(exercise_type: str, count: int, valid: bool) -> List[Dict]:
        result = []
        for index in range(count):
            if exercise_type == "multiple_choice":
                correct = "B"
                options = {"A": "go", "B": "went", "C": "gone", "D": "going"}
                if not valid:
                    options = {"A": "go", "B": "went"}
                result.append(
                    {
                        "question": f"Yesterday I ____ to work by bus ({index + 1}).",
                        "options": options,
                        "correct_answer": correct,
                    }
                )
            elif exercise_type == "error_correction":
                result.append(
                    {
                        "incorrect_sentence": "She don't like coffee.",
                        "correct_sentence": "She doesn't like coffee.",
                    }
                )
            elif exercise_type == "sentence_transformation":
                result.append(
                    {
                        "original_sentence": "I started learning English in 2020.",
                        "instruction": "Rewrite using present perfect continuous.",
                        "transformed_sentence": "I have been learning English since 2020.",
                    }
                )
            elif exercise_type == "matching":
                result.append(
                    {
                        "prompts": ["book a flight", "check in"],
                        "matches": ["reserve a seat", "register at the desk"],
                        "answer_key": {
                            "book a flight": "reserve a seat",
                            "check in": "register at the desk",
                        },
                    }
                )
            elif exercise_type == "dialogue_completion":
                result.append(
                    {
                        "dialogue": [
                            {"speaker": "A", "text": "Hi, can I help you?"},
                            {"speaker": "B", "text": "___"},
                        ],
                        "correct_answer": "Yes, I'd like a coffee.",
                    }
                )
            else:
                sentence = f"I ___ to the office every day ({index + 1})."
                if not valid:
                    sentence = f"I go to office ({index + 1})."
                result.append(
                    {
                        "sentence": sentence,
                        "correct_answer": "go",
                    }
                )
        return result

