import uuid

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from app.agent.graph import build_graph

app = FastAPI()
graph = build_graph()

# stockage temporaire en mémoire — remplacé par le checkpointer Postgres de
# LangGraph à l'étape suivante (session_id devient le thread_id)
sessions: dict[str, dict] = {}


class AnswerPayload(BaseModel):
    correct: bool
    response_time: float


def _public_state(state: dict) -> dict:
    return {
        "session_id": state["session_id"],
        "current_exercise": state["current_exercise"],
        "current_difficulty": state["current_difficulty"],
        "exercise_family": state["exercise_family"],
        "history": state["history"],
    }


@app.post("/sessions/start")
def start_session():
    session_id = str(uuid.uuid4())
    state = {
        "session_id": session_id,
        "history": [],
        "avg_response_time": 0.0,
        "error_rate": 0.0,
        "current_difficulty": 3,
        "exercise_family": "calc",
        "current_exercise": None,
    }
    result = graph.invoke(state)
    sessions[session_id] = result
    return _public_state(result)


@app.post("/sessions/{session_id}/answer")
def submit_answer(session_id: str, payload: AnswerPayload):
    state = sessions.get(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="session not found")
    if state["current_exercise"] is None:
        raise HTTPException(status_code=400, detail="no exercise pending for this session")

    state["history"].append({
        "family": state["current_exercise"]["type"],
        "correct": payload.correct,
        "response_time": payload.response_time,
    })

    result = graph.invoke(state)
    sessions[session_id] = result
    return _public_state(result)


@app.get("/sessions/{session_id}")
def get_session(session_id: str):
    state = sessions.get(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="session not found")
    return _public_state(state)
