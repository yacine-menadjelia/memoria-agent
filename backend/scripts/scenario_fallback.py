"""
Force le déclenchement de la boucle de régénération et du fallback
déterministe de validate_output.

Impossible à obtenir de façon fiable en pilotant l'API en HTTP (on ne
contrôle pas le vrai LLM) : ce script est volontairement boîte blanche — il
monkeypatch app.llm.calc_exercise_is_valid / memory_exercise_is_valid pour
simuler un LLM qui échoue la validation, puis invoque le graphe directement.

À exécuter dans le conteneur backend (a besoin d'ANTHROPIC_API_KEY pour
decide_next_action, qui tourne avant retrieve_context/génération) :

    docker compose exec backend python scripts/scenario_fallback.py
"""

import sys
import uuid

sys.stdout.reconfigure(encoding="utf-8")

from app import llm
from app.agent.graph import MAX_GENERATION_RETRIES, build_graph


def _fresh_state(user_id: str) -> dict:
    return {
        "session_id": str(uuid.uuid4()),
        "user_id": user_id,
        "history": [],
        "avg_response_time": 0.0,
        "error_rate": 0.0,
        "current_difficulty": 4,
        "exercise_family": "calc",
        "current_exercise": None,
        "retrieved_context": {},
        "exercise_valid": True,
        "generation_attempts": 0,
    }


def _expected_fallback_content(family: str, difficulty: int):
    if family == "memory":
        return [str(n) for n in range(1, difficulty + 3)]
    a, b = difficulty * 3, difficulty * 2
    return f"{a} + {b}"


def scenario_always_invalid():
    print("== Scénario : le LLM rate systématiquement la validation ==")
    original_calc_valid = llm.calc_exercise_is_valid
    original_memory_valid = llm.memory_exercise_is_valid
    llm.calc_exercise_is_valid = lambda exercise: False
    llm.memory_exercise_is_valid = lambda exercise: False
    try:
        graph = build_graph()
        result = graph.invoke(_fresh_state("scenario-fallback-always"))
        family = result["exercise_family"]
        difficulty = result["current_difficulty"]
        expected = _expected_fallback_content(family, difficulty)

        print(f"  famille choisie par decide_next_action : {family}, difficulté {difficulty}")
        print(f"  tentatives de génération : {result['generation_attempts']}")
        print(f"  exercice final : {result['current_exercise']}")

        assert result["generation_attempts"] > MAX_GENERATION_RETRIES, (
            f"attendu generation_attempts > {MAX_GENERATION_RETRIES}, "
            f"obtenu {result['generation_attempts']}"
        )
        assert result["current_exercise"]["content"] == expected, (
            f"le fallback déterministe attendu ({expected!r}) n'a pas été utilisé"
        )
        print("  -> OK : fallback déterministe déclenché après échec répété de validation.")
    finally:
        llm.calc_exercise_is_valid = original_calc_valid
        llm.memory_exercise_is_valid = original_memory_valid
    print()


def scenario_recovers_after_one_retry():
    print("== Scénario : le LLM rate une fois puis se rattrape ==")
    call_count = {"n": 0}
    original_calc_valid = llm.calc_exercise_is_valid
    original_memory_valid = llm.memory_exercise_is_valid

    def flaky(original):
        def wrapped(exercise):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return False  # seule la toute première validation échoue
            return original(exercise)

        return wrapped

    llm.calc_exercise_is_valid = flaky(original_calc_valid)
    llm.memory_exercise_is_valid = flaky(original_memory_valid)
    try:
        graph = build_graph()
        result = graph.invoke(_fresh_state("scenario-fallback-recover"))
        family = result["exercise_family"]
        difficulty = result["current_difficulty"]
        fallback_content = _expected_fallback_content(family, difficulty)

        print(f"  tentatives de génération : {result['generation_attempts']}")
        print(f"  exercice final : {result['current_exercise']}")

        assert result["generation_attempts"] == 1, (
            f"attendu exactement 1 tentative invalide avant récupération, "
            f"obtenu {result['generation_attempts']}"
        )
        is_fallback = result["current_exercise"]["content"] == fallback_content
        assert not is_fallback, "le fallback n'aurait pas dû se déclencher ici"
        print("  -> OK : le LLM s'est rattrapé au 2e essai, pas de fallback déclenché.")
    finally:
        llm.calc_exercise_is_valid = original_calc_valid
        llm.memory_exercise_is_valid = original_memory_valid
    print()


if __name__ == "__main__":
    scenario_always_invalid()
    scenario_recovers_after_one_retry()
