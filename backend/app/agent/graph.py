from typing import TypedDict, Literal
from langgraph.graph import StateGraph, END


class SessionState(TypedDict):
    session_id: str
    user_id: str
    history: list[dict]
    avg_response_time: float
    error_rate: float
    current_difficulty: int
    exercise_family: Literal["memory", "calc"]
    current_exercise: dict | None


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
    # version rule-based : le LLM remplacera ce bloc en phase 3, sans changer
    # la forme du graphe (les noeuds voisins ne bougent pas)
    difficulty = state.get("current_difficulty", 3)

    if state["error_rate"] > 0.4:
        difficulty = max(1, difficulty - 1)
    elif state["error_rate"] < 0.15 and state["avg_response_time"] < 3.0:
        difficulty = min(10, difficulty + 1)

    last_family = state["history"][-1]["family"] if state["history"] else "calc"
    next_family = "memory" if last_family == "calc" else "calc"

    state["current_difficulty"] = difficulty
    state["exercise_family"] = next_family
    return state


def route_by_family(state: SessionState) -> str:
    # fonction de routage utilisée par add_conditional_edges : elle ne fait
    # QUE lire le state et renvoyer le nom du prochain noeud, rien d'autre
    return "generate_memory" if state["exercise_family"] == "memory" else "generate_calc"


def generate_memory(state: SessionState) -> SessionState:
    # stub — sera remplacé par un appel LLM (+ retrieve_context) en phase 3
    difficulty = state["current_difficulty"]
    sequence = list(range(1, difficulty + 3))
    state["current_exercise"] = {
        "type": "memory",
        "content": sequence,
        "difficulty": difficulty,
    }
    return state


def generate_calc(state: SessionState) -> SessionState:
    difficulty = state["current_difficulty"]
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


def build_graph(checkpointer=None, profile_store=None):
    graph = StateGraph(SessionState)

    graph.add_node("load_user_profile", make_load_user_profile(profile_store))
    graph.add_node("analyze_performance", analyze_performance)
    graph.add_node("decide_next_action", decide_next_action)
    graph.add_node("generate_memory", generate_memory)
    graph.add_node("generate_calc", generate_calc)
    graph.add_node("format_response", format_response)

    graph.set_entry_point("load_user_profile")
    graph.add_edge("load_user_profile", "analyze_performance")
    graph.add_edge("analyze_performance", "decide_next_action")

    graph.add_conditional_edges(
        "decide_next_action",
        route_by_family,
        {"generate_memory": "generate_memory", "generate_calc": "generate_calc"},
    )

    graph.add_edge("generate_memory", "format_response")
    graph.add_edge("generate_calc", "format_response")
    graph.add_edge("format_response", END)

    return graph.compile(checkpointer=checkpointer)
