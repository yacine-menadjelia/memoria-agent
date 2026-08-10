from typing import TypedDict, Literal
from langgraph.graph import StateGraph, END

from app import llm


class SessionState(TypedDict):
    session_id: str
    user_id: str
    history: list[dict]
    avg_response_time: float
    error_rate: float
    current_difficulty: int
    exercise_family: Literal["memory", "calc"]
    current_exercise: dict | None
    retrieved_context: dict
    exercise_valid: bool
    generation_attempts: int


def make_load_user_profile(profile_store):
    def load_user_profile(state: SessionState) -> SessionState:
        if state["history"] or profile_store is None:
            # session déjà en cours, ou pas de store (tests) : le profil ne
            # doit pas écraser un état qui a déjà bougé
            return state
        profile = profile_store.get(state["user_id"])
        if profile is not None:
            # cold start problem (cf README) : un utilisateur connu reprend
            # à sa difficulté précédente plutôt qu'à la valeur par défaut (3)
            state["current_difficulty"] = profile["last_difficulty"]
        return state

    return load_user_profile


def analyze_performance(state: SessionState) -> SessionState:
    history = state["history"]
    if not history:
        # premier tour de la session : pas encore d'historique
        state["avg_response_time"] = 0.0
        state["error_rate"] = 0.0
        return state

    response_times = [h["response_time"] for h in history]
    errors = [h for h in history if not h["correct"]]

    state["avg_response_time"] = sum(response_times) / len(response_times)
    state["error_rate"] = len(errors) / len(history)
    return state


def decide_next_action(state: SessionState) -> SessionState:
    decision = llm.decide_next_action(
        history=state["history"],
        current_difficulty=state.get("current_difficulty", 3),
        avg_response_time=state["avg_response_time"],
        error_rate=state["error_rate"],
    )
    state["current_difficulty"] = decision["difficulty"]
    state["exercise_family"] = decision["exercise_family"]
    return state


def make_retrieve_context(exercise_store, knowledge_base):
    def retrieve_context(state: SessionState) -> SessionState:
        family = state["exercise_family"]
        difficulty = state["current_difficulty"]

        recent_contents: list[str] = []
        error_stats: dict = {}
        if exercise_store is not None:
            recent_contents = exercise_store.recent_contents(state["user_id"], family)
            error_stats = exercise_store.error_stats(state["user_id"], family)

        pedagogy_tips: list[str] = []
        if knowledge_base is not None:
            try:
                pedagogy_tips = knowledge_base.search(family, difficulty)
            except Exception as exc:
                # la recherche vectorielle est un bonus, pas une dépendance dure :
                # un provider d'embeddings externe indisponible (rate limit,
                # panne...) ne doit pas casser la génération de l'exercice
                print(f"[retrieve_context] recherche pédagogique indisponible : {exc}")

        state["retrieved_context"] = {
            "recent_contents": recent_contents,
            "error_stats": error_stats,
            "pedagogy_tips": pedagogy_tips,
        }
        # remis à zéro à chaque tour : le compteur de tentatives ne doit pas
        # s'accumuler d'un tour à l'autre, seulement au sein d'une génération
        state["generation_attempts"] = 0
        return state

    return retrieve_context


def route_by_family(state: SessionState) -> str:
    # fonction de routage utilisée par add_conditional_edges : elle ne fait
    # QUE lire le state et renvoyer le nom du prochain noeud, rien d'autre
    return "generate_memory" if state["exercise_family"] == "memory" else "generate_calc"


def generate_memory(state: SessionState) -> SessionState:
    difficulty = state["current_difficulty"]
    exercise = llm.generate_memory_exercise(difficulty, context=state.get("retrieved_context"))
    state["current_exercise"] = {
        "type": "memory",
        "content": exercise["content"],
        "difficulty": difficulty,
    }
    return state


def generate_calc(state: SessionState) -> SessionState:
    difficulty = state["current_difficulty"]
    exercise = llm.generate_calc_exercise(difficulty, context=state.get("retrieved_context"))
    state["current_exercise"] = {
        "type": "calc",
        "content": exercise["content"],
        "answer": exercise["answer"],
        "difficulty": difficulty,
    }
    return state


# nombre de régénérations tolérées avant de basculer sur le fallback
# déterministe — au-delà, on considère que le LLM ne convergera pas
MAX_GENERATION_RETRIES = 2


def validate_output(state: SessionState) -> SessionState:
    exercise = state["current_exercise"]
    is_valid = (
        llm.calc_exercise_is_valid(exercise)
        if exercise["type"] == "calc"
        else llm.memory_exercise_is_valid(exercise)
    )
    state["exercise_valid"] = is_valid
    if not is_valid:
        state["generation_attempts"] = state.get("generation_attempts", 0) + 1
        print(
            f"[validate_output] exercice invalide (tentative "
            f"{state['generation_attempts']}) -> {exercise}"
        )
    return state


def route_after_validation(state: SessionState) -> str:
    # fonction de routage : lecture seule, comme route_by_family
    if state["exercise_valid"]:
        return "format_response"
    if state["generation_attempts"] > MAX_GENERATION_RETRIES:
        return "fallback_exercise"
    return "generate_memory" if state["exercise_family"] == "memory" else "generate_calc"


def fallback_exercise(state: SessionState) -> SessionState:
    # dernier recours déterministe : si le LLM échoue plusieurs fois de suite
    # à produire un exercice valide, l'utilisateur reçoit quand même quelque
    # chose plutôt qu'une erreur 500
    difficulty = state["current_difficulty"]
    if state["exercise_family"] == "memory":
        state["current_exercise"] = {
            "type": "memory",
            "content": [str(n) for n in range(1, difficulty + 3)],
            "difficulty": difficulty,
        }
    else:
        a, b = difficulty * 3, difficulty * 2
        state["current_exercise"] = {
            "type": "calc",
            "content": f"{a} + {b}",
            "answer": a + b,
            "difficulty": difficulty,
        }
    return state


def format_response(state: SessionState) -> SessionState:
    print(f"[format_response] exercice prêt -> {state['current_exercise']}")
    return state


def build_graph(checkpointer=None, profile_store=None, exercise_store=None, knowledge_base=None):
    graph = StateGraph(SessionState)

    graph.add_node("load_user_profile", make_load_user_profile(profile_store))
    graph.add_node("analyze_performance", analyze_performance)
    graph.add_node("decide_next_action", decide_next_action)
    graph.add_node("retrieve_context", make_retrieve_context(exercise_store, knowledge_base))
    graph.add_node("generate_memory", generate_memory)
    graph.add_node("generate_calc", generate_calc)
    graph.add_node("validate_output", validate_output)
    graph.add_node("fallback_exercise", fallback_exercise)
    graph.add_node("format_response", format_response)

    graph.set_entry_point("load_user_profile")
    graph.add_edge("load_user_profile", "analyze_performance")
    graph.add_edge("analyze_performance", "decide_next_action")
    graph.add_edge("decide_next_action", "retrieve_context")

    graph.add_conditional_edges(
        "retrieve_context",
        route_by_family,
        {"generate_memory": "generate_memory", "generate_calc": "generate_calc"},
    )

    graph.add_edge("generate_memory", "validate_output")
    graph.add_edge("generate_calc", "validate_output")

    graph.add_conditional_edges(
        "validate_output",
        route_after_validation,
        {
            "format_response": "format_response",
            "generate_memory": "generate_memory",
            "generate_calc": "generate_calc",
            "fallback_exercise": "fallback_exercise",
        },
    )

    graph.add_edge("fallback_exercise", "format_response")
    graph.add_edge("format_response", END)

    return graph.compile(checkpointer=checkpointer)
