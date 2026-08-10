import psycopg


def init_profiles_table(database_url: str) -> None:
    with psycopg.connect(database_url) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS user_profiles (
                user_id TEXT PRIMARY KEY,
                last_difficulty INTEGER NOT NULL,
                avg_response_time DOUBLE PRECISION NOT NULL,
                error_rate DOUBLE PRECISION NOT NULL,
                updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )


class ProfileStore:
    def __init__(self, database_url: str):
        self._database_url = database_url

    def get(self, user_id: str) -> dict | None:
        with psycopg.connect(self._database_url) as conn:
            row = conn.execute(
                "SELECT last_difficulty, avg_response_time, error_rate "
                "FROM user_profiles WHERE user_id = %s",
                (user_id,),
            ).fetchone()
        if row is None:
            return None
        return {
            "last_difficulty": row[0],
            "avg_response_time": row[1],
            "error_rate": row[2],
        }

    def upsert(self, user_id: str, difficulty: int, avg_response_time: float, error_rate: float) -> None:
        with psycopg.connect(self._database_url) as conn:
            conn.execute(
                """
                INSERT INTO user_profiles (user_id, last_difficulty, avg_response_time, error_rate, updated_at)
                VALUES (%s, %s, %s, %s, now())
                ON CONFLICT (user_id) DO UPDATE SET
                    last_difficulty = EXCLUDED.last_difficulty,
                    avg_response_time = EXCLUDED.avg_response_time,
                    error_rate = EXCLUDED.error_rate,
                    updated_at = now()
                """,
                (user_id, difficulty, avg_response_time, error_rate),
            )


def init_exercise_history_table(database_url: str) -> None:
    with psycopg.connect(database_url) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS exercise_history (
                id SERIAL PRIMARY KEY,
                user_id TEXT NOT NULL,
                family TEXT NOT NULL,
                difficulty INTEGER NOT NULL,
                content TEXT NOT NULL,
                correct BOOLEAN NOT NULL,
                response_time DOUBLE PRECISION NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS exercise_history_user_family_idx "
            "ON exercise_history (user_id, family, created_at DESC)"
        )


class ExerciseHistoryStore:
    def __init__(self, database_url: str):
        self._database_url = database_url

    def save(
        self,
        user_id: str,
        family: str,
        difficulty: int,
        content: str,
        correct: bool,
        response_time: float,
    ) -> None:
        with psycopg.connect(self._database_url) as conn:
            conn.execute(
                """
                INSERT INTO exercise_history
                    (user_id, family, difficulty, content, correct, response_time)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (user_id, family, difficulty, content, correct, response_time),
            )

    def recent_contents(self, user_id: str, family: str, limit: int = 5) -> list[str]:
        with psycopg.connect(self._database_url) as conn:
            rows = conn.execute(
                "SELECT content FROM exercise_history "
                "WHERE user_id = %s AND family = %s "
                "ORDER BY created_at DESC LIMIT %s",
                (user_id, family, limit),
            ).fetchall()
        return [row[0] for row in rows]

    def error_stats(self, user_id: str, family: str, window: int = 20) -> dict:
        # points faibles : la difficulté moyenne des tours ratés vs réussis,
        # calculée en Python sur une fenêtre récente — pas besoin de SQL
        # d'agrégation compliqué pour ça
        with psycopg.connect(self._database_url) as conn:
            rows = conn.execute(
                "SELECT difficulty, correct FROM exercise_history "
                "WHERE user_id = %s AND family = %s "
                "ORDER BY created_at DESC LIMIT %s",
                (user_id, family, window),
            ).fetchall()
        if not rows:
            return {}
        incorrect_difficulties = [d for d, correct in rows if not correct]
        correct_difficulties = [d for d, correct in rows if correct]
        return {
            "sample_size": len(rows),
            "error_rate": len(incorrect_difficulties) / len(rows),
            "avg_difficulty_on_errors": (
                sum(incorrect_difficulties) / len(incorrect_difficulties)
                if incorrect_difficulties
                else None
            ),
            "avg_difficulty_on_success": (
                sum(correct_difficulties) / len(correct_difficulties)
                if correct_difficulties
                else None
            ),
        }
