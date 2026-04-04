import json
import sqlite3
import logging
from typing import Any, Dict, Optional


logger = logging.getLogger(__name__)


class ExerciseStore:
    """Простое SQLite-хранилище с exact-match кэшем генераций."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS generated_exercises (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    exercise_type TEXT NOT NULL,
                    level TEXT NOT NULL,
                    count INTEGER NOT NULL,
                    grammar_topic TEXT,
                    theme TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    quality_score REAL,
                    created_at REAL NOT NULL
                )
                """
            )
        logger.info("ExerciseStore schema ensured at db_path=%s", self.db_path)

    def get_cached(
        self,
        exercise_type: str,
        level: str,
        count: int,
        grammar_topic: Optional[str],
        theme: str,
    ) -> Optional[Dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                """
                SELECT payload_json
                FROM generated_exercises
                WHERE exercise_type = ?
                  AND level = ?
                  AND count = ?
                  AND COALESCE(grammar_topic, '') = COALESCE(?, '')
                  AND theme = ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (exercise_type, level, count, grammar_topic, theme),
            ).fetchone()

        if not row:
            logger.info(
                "Cache miss: type=%s level=%s count=%s grammar_topic=%s theme=%s",
                exercise_type,
                level,
                count,
                grammar_topic,
                theme,
            )
            return None
        logger.info(
            "Cache hit: type=%s level=%s count=%s grammar_topic=%s theme=%s",
            exercise_type,
            level,
            count,
            grammar_topic,
            theme,
        )
        return json.loads(row[0])

    def save(
        self,
        exercise_type: str,
        level: str,
        count: int,
        grammar_topic: Optional[str],
        theme: str,
        payload: Dict[str, Any],
        quality_score: Optional[float],
        created_at: float,
    ) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO generated_exercises (
                    exercise_type,
                    level,
                    count,
                    grammar_topic,
                    theme,
                    payload_json,
                    quality_score,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    exercise_type,
                    level,
                    count,
                    grammar_topic,
                    theme,
                    json.dumps(payload, ensure_ascii=False),
                    quality_score,
                    created_at,
                ),
            )
        logger.info(
            "Saved generation to cache: type=%s level=%s count=%s grammar_topic=%s theme=%s score=%s",
            exercise_type,
            level,
            count,
            grammar_topic,
            theme,
            quality_score,
        )

    def get_stats(self) -> Dict[str, Any]:
        with sqlite3.connect(self.db_path) as conn:
            total_entries = conn.execute("SELECT COUNT(*) FROM generated_exercises").fetchone()[0]
            unique_keys = conn.execute(
                """
                SELECT COUNT(*)
                FROM (
                    SELECT DISTINCT exercise_type, level, count, COALESCE(grammar_topic, ''), theme
                    FROM generated_exercises
                )
                """
            ).fetchone()[0]
            latest_created_at_row = conn.execute(
                "SELECT MAX(created_at) FROM generated_exercises"
            ).fetchone()

        latest_created_at = latest_created_at_row[0] if latest_created_at_row else None
        stats = {
            "db_path": self.db_path,
            "total_entries": total_entries,
            "unique_request_keys": unique_keys,
            "latest_created_at": latest_created_at,
        }
        logger.info("Cache stats requested: %s", stats)
        return stats

