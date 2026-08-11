from app.agent import graph as g
from tests.fakes import (
    FakeExerciseHistoryStore,
    FakeKnowledgeBase,
    FakeProfileStore,
)


def _base_state(**overrides) -> dict:
    state = {
        "session_id": "s1",
        "user_id": "u1",
        "history": [],
        "avg_response_time": 0.0,
        "error_rate": 0.0,
        "current_difficulty": 3,
        "exercise_family": "calc",
        "current_exercise": None,
        "retrieved_context": {},
        "exercise_valid": True,
        "generation_attempts": 0,
    }
    state.update(overrides)
    return state


# --- analyze_performance -----------------------------------------------


def test_analyze_performance_empty_history_defaults_to_zero():
    state = g.analyze_performance(_base_state(history=[]))
    assert state["avg_response_time"] == 0.0
    assert state["error_rate"] == 0.0


def test_analyze_performance_computes_avg_and_error_rate():
    history = [
        {"family": "calc", "correct": True, "response_time": 2.0},
        {"family": "calc", "correct": False, "response_time": 4.0},
    ]
    state = g.analyze_performance(_base_state(history=history))
    assert state["avg_response_time"] == 3.0
    assert state["error_rate"] == 0.5


# --- route_by_family / route_after_validation (routage, lecture seule) -


def test_route_by_family_memory():
    assert g.route_by_family(_base_state(exercise_family="memory")) == "generate_memory"


def test_route_by_family_calc():
    assert g.route_by_family(_base_state(exercise_family="calc")) == "generate_calc"


def test_route_after_validation_valid_goes_to_format_response():
    state = _base_state(exercise_valid=True)
    assert g.route_after_validation(state) == "format_response"


def test_route_after_validation_invalid_within_budget_retries():
    state = _base_state(exercise_valid=False, generation_attempts=1, exercise_family="memory")
    assert g.route_after_validation(state) == "generate_memory"

    state["exercise_family"] = "calc"
    assert g.route_after_validation(state) == "generate_calc"


def test_route_after_validation_invalid_past_budget_falls_back():
    state = _base_state(
        exercise_valid=False, generation_attempts=g.MAX_GENERATION_RETRIES + 1
    )
    assert g.route_after_validation(state) == "fallback_exercise"


# --- load_user_profile (cold start) -------------------------------------


def test_load_user_profile_overrides_difficulty_for_new_session():
    store = FakeProfileStore({"last_difficulty": 8, "avg_response_time": 1.0, "error_rate": 0.1})
    node = g.make_load_user_profile(store)

    state = node(_base_state(history=[], current_difficulty=3))

    assert state["current_difficulty"] == 8
    assert store.calls == ["u1"]


def test_load_user_profile_no_override_when_profile_missing():
    store = FakeProfileStore(None)
    node = g.make_load_user_profile(store)

    state = node(_base_state(history=[], current_difficulty=3))

    assert state["current_difficulty"] == 3


def test_load_user_profile_ignored_when_history_already_present():
    store = FakeProfileStore({"last_difficulty": 8, "avg_response_time": 1.0, "error_rate": 0.1})
    node = g.make_load_user_profile(store)

    history = [{"family": "calc", "correct": True, "response_time": 1.0}]
    state = node(_base_state(history=history, current_difficulty=3))

    assert state["current_difficulty"] == 3
    assert store.calls == []  # ne doit même pas interroger le store


def test_load_user_profile_noop_when_store_is_none():
    node = g.make_load_user_profile(None)
    state = node(_base_state(history=[], current_difficulty=3))
    assert state["current_difficulty"] == 3


# --- retrieve_context -----------------------------------------------------


def test_retrieve_context_assembles_context_and_resets_attempts():
    exercise_store = FakeExerciseHistoryStore(
        recent_contents=["1 + 1"], error_stats={"error_rate": 0.2}
    )
    knowledge_base = FakeKnowledgeBase(tips=["décompose les grands nombres"])
    node = g.make_retrieve_context(exercise_store, knowledge_base)

    state = node(_base_state(exercise_family="calc", current_difficulty=6, generation_attempts=5))

    assert state["retrieved_context"] == {
        "recent_contents": ["1 + 1"],
        "error_stats": {"error_rate": 0.2},
        "pedagogy_tips": ["décompose les grands nombres"],
    }
    assert state["generation_attempts"] == 0
    assert exercise_store.recent_contents_calls == [("u1", "calc", 5)]
    assert knowledge_base.calls == [("calc", 6, 3)]


def test_retrieve_context_resilient_to_knowledge_base_failure():
    exercise_store = FakeExerciseHistoryStore()
    knowledge_base = FakeKnowledgeBase(raises=RuntimeError("rate limited"))
    node = g.make_retrieve_context(exercise_store, knowledge_base)

    state = node(_base_state())

    # la panne du provider d'embeddings ne doit jamais faire planter le noeud
    assert state["retrieved_context"]["pedagogy_tips"] == []


def test_retrieve_context_noop_when_stores_are_none():
    node = g.make_retrieve_context(None, None)
    state = node(_base_state())
    assert state["retrieved_context"] == {
        "recent_contents": [],
        "error_stats": {},
        "pedagogy_tips": [],
    }


# --- decide_next_action / generate_memory / generate_calc -----------------


def test_decide_next_action_updates_state(monkeypatch):
    monkeypatch.setattr(
        g.llm,
        "decide_next_action",
        lambda **kwargs: {"difficulty": 7, "exercise_family": "memory"},
    )
    state = g.decide_next_action(_base_state(current_difficulty=3, exercise_family="calc"))
    assert state["current_difficulty"] == 7
    assert state["exercise_family"] == "memory"


def test_generate_calc_sets_current_exercise(monkeypatch):
    monkeypatch.setattr(
        g.llm, "generate_calc_exercise", lambda difficulty, context=None: {"content": "3 + 4", "answer": 7}
    )
    state = g.generate_calc(_base_state(current_difficulty=5))
    assert state["current_exercise"] == {
        "type": "calc",
        "content": "3 + 4",
        "answer": 7,
        "difficulty": 5,
    }


def test_generate_memory_sets_current_exercise(monkeypatch):
    monkeypatch.setattr(
        g.llm,
        "generate_memory_exercise",
        lambda difficulty, context=None: {"content": ["1", "chat"]},
    )
    state = g.generate_memory(_base_state(current_difficulty=5))
    assert state["current_exercise"] == {
        "type": "memory",
        "content": ["1", "chat"],
        "difficulty": 5,
    }


# --- validate_output / fallback_exercise -----------------------------------


def test_validate_output_marks_valid_calc_exercise():
    state = _base_state(current_exercise={"type": "calc", "answer": 7})
    state = g.validate_output(state)
    assert state["exercise_valid"] is True
    assert state["generation_attempts"] == 0  # inchangé quand c'est valide


def test_validate_output_marks_invalid_and_increments_attempts():
    state = _base_state(
        current_exercise={"type": "calc", "answer": None}, generation_attempts=1
    )
    state = g.validate_output(state)
    assert state["exercise_valid"] is False
    assert state["generation_attempts"] == 2


def test_validate_output_memory_family():
    state = _base_state(current_exercise={"type": "memory", "content": ["1", "1"]})
    state = g.validate_output(state)
    assert state["exercise_valid"] is False


def test_fallback_exercise_memory():
    state = g.fallback_exercise(_base_state(exercise_family="memory", current_difficulty=5))
    assert state["current_exercise"]["content"] == ["1", "2", "3", "4", "5", "6", "7"]


def test_fallback_exercise_calc():
    state = g.fallback_exercise(_base_state(exercise_family="calc", current_difficulty=5))
    assert state["current_exercise"]["content"] == "15 + 10"
    assert state["current_exercise"]["answer"] == 25


# --- boucle complète du graphe (build_graph + monkeypatch du LLM) ---------


def _patch_llm_for_full_graph(monkeypatch, family="calc"):
    monkeypatch.setattr(
        g.llm,
        "decide_next_action",
        lambda **kwargs: {"difficulty": 4, "exercise_family": family},
    )
    monkeypatch.setattr(
        g.llm, "generate_calc_exercise", lambda difficulty, context=None: {"content": "1 + 1", "answer": 2}
    )
    monkeypatch.setattr(
        g.llm, "generate_memory_exercise", lambda difficulty, context=None: {"content": ["1", "2"]}
    )


def test_full_graph_falls_back_after_repeated_invalid_generation(monkeypatch):
    _patch_llm_for_full_graph(monkeypatch, family="calc")
    monkeypatch.setattr(g.llm, "calc_exercise_is_valid", lambda exercise: False)
    monkeypatch.setattr(g.llm, "memory_exercise_is_valid", lambda exercise: False)

    graph = g.build_graph()
    result = graph.invoke(_base_state())

    assert result["generation_attempts"] > g.MAX_GENERATION_RETRIES
    assert result["current_exercise"]["content"] == "12 + 8"  # fallback calc à difficulté 4


def test_full_graph_recovers_without_fallback_after_one_bad_attempt(monkeypatch):
    _patch_llm_for_full_graph(monkeypatch, family="calc")
    call_count = {"n": 0}

    def flaky_valid(exercise):
        call_count["n"] += 1
        return call_count["n"] > 1  # la première validation échoue, les suivantes passent

    monkeypatch.setattr(g.llm, "calc_exercise_is_valid", flaky_valid)
    monkeypatch.setattr(g.llm, "memory_exercise_is_valid", flaky_valid)

    graph = g.build_graph()
    result = graph.invoke(_base_state())

    assert result["generation_attempts"] == 1
    assert result["current_exercise"]["content"] == "1 + 1"  # pas le fallback
