import pytest

from app import llm
from tests.fakes import FakeAnthropicClient


# --- _evaluate_expression : évaluateur arithmétique restreint --------------


@pytest.mark.parametrize(
    "expression, expected",
    [
        ("2 + 3", 5),
        ("10 - 4", 6),
        ("3 * 4", 12),
        ("12 / 4", 3.0),
        ("(2 + 3) * 4", 20),
        ("-3 + 5", 2),
        ("2 + 3 * 4", 14),  # priorité des opérateurs standard Python
    ],
)
def test_evaluate_expression_basic_arithmetic(expression, expected):
    assert llm._evaluate_expression(expression) == expected


def test_evaluate_expression_rejects_non_arithmetic_nodes():
    # syntaxiquement valide en Python (un appel de fonction), mais ce n'est
    # pas de l'arithmétique — doit être rejeté, jamais exécuté
    with pytest.raises(ValueError):
        llm._evaluate_expression("__import__('os').system('echo pwned')")


def test_evaluate_expression_rejects_invalid_syntax():
    with pytest.raises(SyntaxError):
        llm._evaluate_expression("six plus sept")


def test_evaluate_expression_zero_division_raises():
    with pytest.raises(ZeroDivisionError):
        llm._evaluate_expression("1 / 0")


# --- _normalize_answer / _clamp_difficulty ---------------------------------


def test_normalize_answer_integer_division_becomes_int():
    assert llm._normalize_answer(5.0) == 5
    assert isinstance(llm._normalize_answer(5.0), int)


def test_normalize_answer_keeps_float_when_not_integer():
    assert llm._normalize_answer(5.5) == 5.5
    assert isinstance(llm._normalize_answer(5.5), float)


@pytest.mark.parametrize(
    "value, expected",
    [(0, 1), (-5, 1), (1, 1), (5, 5), (10, 10), (15, 10), (10.9, 10)],
)
def test_clamp_difficulty(value, expected):
    assert llm._clamp_difficulty(value) == expected


# --- calc_exercise_is_valid / memory_exercise_is_valid ---------------------


@pytest.mark.parametrize(
    "exercise, expected",
    [
        ({"answer": 5}, True),
        ({"answer": 0}, True),
        ({"answer": -3}, True),
        ({"answer": 5.5}, False),  # division qui ne tombe pas juste
        ({"answer": None}, False),
        ({}, False),
    ],
)
def test_calc_exercise_is_valid(exercise, expected):
    assert llm.calc_exercise_is_valid(exercise) is expected


@pytest.mark.parametrize(
    "exercise, expected",
    [
        ({"content": ["1", "chat", "2"]}, True),
        ({"content": ["1", "1", "2"]}, False),  # doublon exact
        ({"content": ["1", "Chat", "chat"]}, False),  # doublon insensible à la casse
        ({"content": ["1", "", "2"]}, False),  # élément vide
        ({"content": ["1"]}, False),  # trop court
        ({"content": []}, False),
        ({"content": [1, "chat"]}, False),  # élément non-string
        ({}, False),
        ({"content": "1,2,3"}, False),  # pas une liste
    ],
)
def test_memory_exercise_is_valid(exercise, expected):
    assert llm.memory_exercise_is_valid(exercise) is expected


# --- decide_next_action / generate_*_exercise : client Anthropic mocké -----


def test_decide_next_action_clamps_out_of_range_difficulty(monkeypatch):
    fake_client = FakeAnthropicClient(
        {"difficulty": 15, "exercise_family": "calc"}
    )
    monkeypatch.setattr(llm, "_get_client", lambda: fake_client)

    decision = llm.decide_next_action(
        history=[], current_difficulty=5, avg_response_time=1.0, error_rate=0.0
    )

    assert decision["difficulty"] == 10
    assert decision["exercise_family"] == "calc"


def test_decide_next_action_sends_recent_history_in_request(monkeypatch):
    fake_client = FakeAnthropicClient(
        {"difficulty": 4, "exercise_family": "memory"}
    )
    monkeypatch.setattr(llm, "_get_client", lambda: fake_client)

    history = [{"family": "calc", "correct": True, "response_time": 1.0}]
    llm.decide_next_action(
        history=history, current_difficulty=4, avg_response_time=1.0, error_rate=0.0
    )

    sent = fake_client.messages.calls[0]
    assert "calc" in sent["messages"][0]["content"]
    # Haiku ne supporte pas le paramètre thinking (400 si envoyé) — on ne
    # doit jamais le mettre dans la requête
    assert "thinking" not in sent


def test_generate_calc_exercise_computes_answer_serverside(monkeypatch):
    # le schema n'a même pas de champ "answer" : le serveur ne fait jamais
    # confiance au calcul du modèle, il ne peut fournir que l'expression
    fake_client = FakeAnthropicClient({"content": "6 * 7"})
    monkeypatch.setattr(llm, "_get_client", lambda: fake_client)

    exercise = llm.generate_calc_exercise(difficulty=4)

    assert exercise["content"] == "6 * 7"
    assert exercise["answer"] == 42


def test_generate_calc_exercise_invalid_expression_sets_answer_none(monkeypatch):
    fake_client = FakeAnthropicClient({"content": "six plus sept"})
    monkeypatch.setattr(llm, "_get_client", lambda: fake_client)

    exercise = llm.generate_calc_exercise(difficulty=4)

    assert exercise["answer"] is None
    assert llm.calc_exercise_is_valid(exercise) is False


def test_generate_calc_exercise_includes_context_in_prompt(monkeypatch):
    fake_client = FakeAnthropicClient({"content": "3 + 4"})
    monkeypatch.setattr(llm, "_get_client", lambda: fake_client)

    context = {
        "recent_contents": ["1 + 1"],
        "error_stats": {"error_rate": 0.5},
        "pedagogy_tips": ["décompose les grands nombres"],
    }
    llm.generate_calc_exercise(difficulty=6, context=context)

    sent_content = fake_client.messages.calls[0]["messages"][0]["content"]
    assert "1 + 1" in sent_content
    assert "décompose les grands nombres" in sent_content


def test_generate_memory_exercise_returns_content_list(monkeypatch):
    fake_client = FakeAnthropicClient({"content": ["1", "chat", "2"]})
    monkeypatch.setattr(llm, "_get_client", lambda: fake_client)

    exercise = llm.generate_memory_exercise(difficulty=3)

    assert exercise["content"] == ["1", "chat", "2"]
