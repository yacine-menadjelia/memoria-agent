import ast
import json
import operator
from typing import Callable

import anthropic

# Haiku plutôt qu'Opus 5 : ces trois appels sont des tâches simples
# (classification de difficulté, génération d'une expression/séquence
# courte), pas du raisonnement profond. Mesuré : Opus 5 prend ~5-6s par
# appel sur cette charge, Haiku ~2s — sur un tour qui enchaîne deux
# appels (décision + génération), ça change complètement le ressenti
# côté app. Haiku ne supporte ni `effort` ni `thinking` (400 si envoyés),
# d'où leur absence dans les appels ci-dessous.
MODEL = "claude-haiku-4-5"

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

DECISION_SYSTEM_PROMPT = (
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
        output_config={"format": {"type": "json_schema", "schema": DECISION_SCHEMA}},
        system=DECISION_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_content}],
    )
    text = next(block.text for block in response.content if block.type == "text")
    decision = json.loads(text)
    decision["difficulty"] = _clamp_difficulty(decision["difficulty"])
    return decision


def _clamp_difficulty(value: int) -> int:
    return max(1, min(10, int(value)))


CALC_SCHEMA = {
    "type": "object",
    "properties": {
        "content": {
            "type": "string",
            "description": (
                "Une expression arithmétique pure (chiffres, +, -, *, /, "
                "parenthèses), sans mot ni symbole additionnel. Ex: '23 + 47', "
                "'(12 - 3) * 4'."
            ),
        },
    },
    "required": ["content"],
    "additionalProperties": False,
}

CALC_SYSTEM_PROMPT = (
    "Tu génères un exercice de calcul mental pour la difficulté demandée "
    "(1 = très facile, 10 = très difficile). Difficultés basses : addition ou "
    "soustraction à un ou deux chiffres. Difficultés moyennes : multiplication, "
    "nombres à deux ou trois chiffres. Difficultés hautes : opérations "
    "combinées avec parenthèses, plus grands nombres. Les divisions doivent "
    "toujours tomber juste (résultat entier). Réponds uniquement avec "
    "l'expression, jamais le résultat. Si on te donne les exercices récents de "
    "l'utilisateur, ne reproduis pas la même expression. Si on te donne des "
    "statistiques d'erreurs ou des repères pédagogiques, utilise-les pour "
    "ajuster le type d'opération (ex: éviter les divisions si l'utilisateur "
    "échoue déjà beaucoup dessus, ou au contraire les retravailler légèrement "
    "en dessous de sa difficulté actuelle)."
)

MEMORY_SCHEMA = {
    "type": "object",
    "properties": {
        "content": {
            "type": "array",
            "items": {"type": "string"},
            "description": "La séquence d'éléments à mémoriser, dans l'ordre.",
        },
    },
    "required": ["content"],
    "additionalProperties": False,
}

MEMORY_SYSTEM_PROMPT = (
    "Tu génères un exercice de mémorisation pour la difficulté demandée "
    "(1 = très facile, 10 = très difficile). La longueur de la séquence et la "
    "nature des éléments doivent croître avec la difficulté : quelques chiffres "
    "pour les difficultés basses, puis des mots courts, puis des séquences plus "
    "longues mélangeant chiffres et mots pour les difficultés hautes. Chaque "
    "élément de la séquence est une chaîne courte. Si on te donne les exercices "
    "récents de l'utilisateur, ne réutilise pas les mêmes éléments. Si on te "
    "donne des statistiques d'erreurs ou des repères pédagogiques, utilise-les "
    "pour ajuster la nature des éléments (ex: revenir temporairement à des "
    "séquences plus courtes si le taux d'erreur récent est élevé)."
)


# Opérateurs autorisés dans les expressions générées — volontairement restreint
# à l'arithmétique de base, jamais un eval() général sur du texte venant du LLM.
_ARITHMETIC_OPS: dict[type, Callable[..., float]] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.USub: operator.neg,
}


def _eval_arithmetic_node(node: ast.AST) -> float:
    if isinstance(node, ast.BinOp) and type(node.op) in _ARITHMETIC_OPS:
        return _ARITHMETIC_OPS[type(node.op)](
            _eval_arithmetic_node(node.left), _eval_arithmetic_node(node.right)
        )
    if isinstance(node, ast.UnaryOp) and type(node.op) in _ARITHMETIC_OPS:
        return _ARITHMETIC_OPS[type(node.op)](_eval_arithmetic_node(node.operand))
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    raise ValueError(f"expression arithmétique non supportée : {ast.dump(node)}")


def _evaluate_expression(expression: str) -> float:
    return _eval_arithmetic_node(ast.parse(expression, mode="eval").body)


def _context_message(difficulty: int, context: dict | None) -> str:
    parts = [f"Difficulté demandée : {difficulty}/10."]
    if context:
        recent = context.get("recent_contents")
        if recent:
            parts.append(
                "Exercices récents de cet utilisateur, à ne pas reproposer à "
                "l'identique : " + json.dumps(recent, ensure_ascii=False) + "."
            )
        stats = context.get("error_stats")
        if stats:
            parts.append(
                "Statistiques d'erreurs récentes de l'utilisateur sur cette "
                "famille : " + json.dumps(stats, ensure_ascii=False) + "."
            )
        tips = context.get("pedagogy_tips")
        if tips:
            parts.append("Repères pédagogiques pertinents : " + " ".join(tips))
    return " ".join(parts)


def generate_calc_exercise(difficulty: int, context: dict | None = None) -> dict:
    response = _get_client().messages.create(
        model=MODEL,
        max_tokens=256,
        output_config={"format": {"type": "json_schema", "schema": CALC_SCHEMA}},
        system=CALC_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": _context_message(difficulty, context)}],
    )
    text = next(block.text for block in response.content if block.type == "text")
    exercise = json.loads(text)
    try:
        exercise["answer"] = _normalize_answer(_evaluate_expression(exercise["content"]))
    except (ValueError, SyntaxError, ZeroDivisionError, TypeError):
        # le LLM n'a pas respecté le format demandé (mot dans l'expression,
        # syntaxe invalide...) — laissé à answer=None, validate_output décide
        # s'il faut régénérer
        exercise["answer"] = None
    return exercise


def _normalize_answer(value: float) -> int | float:
    return int(value) if value.is_integer() else value


def calc_exercise_is_valid(exercise: dict) -> bool:
    # une réponse non entière signifie que la division ne tombait pas juste,
    # ce que le prompt interdit explicitement — traité comme invalide plutôt
    # que d'exposer un résultat à virgule
    return isinstance(exercise.get("answer"), int)


def memory_exercise_is_valid(exercise: dict) -> bool:
    content = exercise.get("content")
    if not isinstance(content, list) or len(content) < 2:
        return False
    cleaned = [item.strip() for item in content if isinstance(item, str) and item.strip()]
    if len(cleaned) != len(content):
        return False
    return len(set(item.lower() for item in cleaned)) == len(cleaned)


def generate_memory_exercise(difficulty: int, context: dict | None = None) -> dict:
    response = _get_client().messages.create(
        model=MODEL,
        max_tokens=512,
        output_config={"format": {"type": "json_schema", "schema": MEMORY_SCHEMA}},
        system=MEMORY_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": _context_message(difficulty, context)}],
    )
    text = next(block.text for block in response.content if block.type == "text")
    return json.loads(text)
