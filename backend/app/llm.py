import json

import anthropic

MODEL = "claude-opus-5"

_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic()
    return _client


DECISION_SCHEMA = {
    "type": "object",
    "properties": {
        "difficulty": {
            "type": "integer",
            "description": "Prochaine difficulté, entre 1 et 10.",
        },
        "exercise_family": {
            "type": "string",
            "enum": ["memory", "calc"],
            "description": "Type du prochain exercice.",
        },
        "reasoning": {
            "type": "string",
            "description": "Une phrase expliquant la décision.",
        },
    },
    "required": ["difficulty", "exercise_family", "reasoning"],
    "additionalProperties": False,
}

SYSTEM_PROMPT = (
    "Tu es le moteur de décision d'un agent d'entraînement cognitif. À chaque tour, "
    "choisis la difficulté (1 à 10) et le type du prochain exercice (memory ou calc) "
    "à partir de l'historique récent de l'utilisateur. Monte la difficulté si "
    "l'utilisateur réussit vite et sans erreur, baisse-la s'il se trompe souvent ou "
    "met du temps. Alterne les familles d'exercice sauf si l'historique montre "
    "qu'une famille précise pose particulièrement problème et mérite d'être retravaillée."
)


def decide_next_action(
    history: list[dict],
    current_difficulty: int,
    avg_response_time: float,
    error_rate: float,
) -> dict:
    user_content = json.dumps(
        {
            "current_difficulty": current_difficulty,
            "avg_response_time": avg_response_time,
            "error_rate": error_rate,
            "recent_history": history[-10:],
        },
        ensure_ascii=False,
    )

    response = _get_client().messages.create(
        model=MODEL,
        max_tokens=1024,
        thinking={"type": "disabled"},
        output_config={
            "effort": "low",
            "format": {"type": "json_schema", "schema": DECISION_SCHEMA},
        },
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_content}],
    )
    text = next(block.text for block in response.content if block.type == "text")
    decision = json.loads(text)
    decision["difficulty"] = max(1, min(10, int(decision["difficulty"])))
    return decision
