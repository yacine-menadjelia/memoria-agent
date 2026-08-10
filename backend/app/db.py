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
