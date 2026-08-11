import os
import sys
import uuid

import requests

sys.stdout.reconfigure(encoding="utf-8")

BASE_URL = os.environ.get("MEMORIA_BASE_URL", "http://localhost:8000")


def start(user_id):
    r = requests.post(f"{BASE_URL}/sessions/start", json={"user_id": user_id})
    r.raise_for_status()
    return r.json()


def answer(session_id, correct, response_time):
    r = requests.post(
        f"{BASE_URL}/sessions/{session_id}/answer",
        json={"correct": correct, "response_time": response_time},
    )
    return r


def show(label, state):
    ex = state["current_exercise"]
    print(
        f"  {label}: diff={state['current_difficulty']} "
        f"family={state['exercise_family']} content={ex['content']!r}"
    )


def scenario_progression():
    print("== Scénario 1 : utilisateur qui progresse (correct + rapide) ==")
    user_id = f"scenario-progress-{uuid.uuid4().hex[:6]}"
    state = start(user_id)
    show("start", state)
    for i in range(5):
        state = answer(state["session_id"], True, 1.0).json()
        show(f"tour {i+1}", state)
    print()


def scenario_regression():
    print("== Scénario 2 : utilisateur qui régresse (erreurs + lent) ==")
    user_id = f"scenario-regress-{uuid.uuid4().hex[:6]}"
    state = start(user_id)
    show("start", state)
    for i in range(5):
        state = answer(state["session_id"], False, 9.0).json()
        show(f"tour {i+1}", state)
    print()


def scenario_returning_user():
    print("== Scénario 3 : utilisateur connu qui revient (cold start) ==")
    user_id = f"scenario-return-{uuid.uuid4().hex[:6]}"
    state = start(user_id)
    show("session 1 - start", state)
    for i in range(4):
        state = answer(state["session_id"], True, 1.0).json()
        show(f"session 1 - tour {i+1}", state)
    reached = state["current_difficulty"]

    state2 = start(user_id)
    show("session 2 - start (même user)", state2)
    print(
        f"  -> difficulté atteinte en session 1: {reached}, "
        f"reprise en session 2: {state2['current_difficulty']}"
    )
    print()


def scenario_no_repeat():
    print("== Scénario 4 : pas de répétition d'exercice sur la même famille ==")
    user_id = f"scenario-norepeat-{uuid.uuid4().hex[:6]}"
    state = start(user_id)
    contents = []
    if state["exercise_family"] == "calc":
        contents.append(state["current_exercise"]["content"])
    for i in range(6):
        state = answer(state["session_id"], True, 1.0).json()
        if state["exercise_family"] == "calc":
            contents.append(state["current_exercise"]["content"])
    print(f"  expressions calc générées: {contents}")
    print(f"  doublons: {len(contents) != len(set(contents))}")
    print()


def scenario_errors():
    print("== Scénario 5 : erreurs API (session inconnue) ==")
    r = requests.get(f"{BASE_URL}/sessions/{uuid.uuid4()}")
    print(f"  GET session inconnue -> {r.status_code}")

    r = requests.post(
        f"{BASE_URL}/sessions/{uuid.uuid4()}/answer",
        json={"correct": True, "response_time": 1.0},
    )
    print(f"  POST answer sur session inconnue -> {r.status_code}")
    print()


if __name__ == "__main__":
    scenario_progression()
    scenario_regression()
    scenario_returning_user()
    scenario_no_repeat()
    scenario_errors()
