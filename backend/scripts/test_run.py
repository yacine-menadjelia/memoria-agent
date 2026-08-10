from app.agent.graph import build_graph

app = build_graph()

state = {
    "session_id": "test-session-1",
    "history": [],
    "avg_response_time": 0.0,
    "error_rate": 0.0,
    "current_difficulty": 3,
    "exercise_family": "calc",
    "current_exercise": None,
}

print("--- Tour 1 (aucun historique) ---")
result = app.invoke(state)
print("Exercice :", result["current_exercise"])
print("Difficulté :", result["current_difficulty"])

# on simule une bonne réponse, rapide -> la difficulté devrait monter au tour suivant
result["history"].append({
    "family": result["current_exercise"]["type"],
    "correct": True,
    "response_time": 1.5,
})

print("\n--- Tour 2 (une bonne réponse rapide) ---")
result2 = app.invoke(result)
print("Exercice :", result2["current_exercise"])
print("Difficulté :", result2["current_difficulty"])

# on simule ensuite deux erreurs -> la difficulté devrait redescendre
result2["history"].append({"family": result2["current_exercise"]["type"], "correct": False, "response_time": 6.0})
result2["history"].append({"family": result2["current_exercise"]["type"], "correct": False, "response_time": 7.0})

print("\n--- Tour 3 (deux erreurs récentes) ---")
result3 = app.invoke(result2)
print("Exercice :", result3["current_exercise"])
print("Difficulté :", result3["current_difficulty"])
