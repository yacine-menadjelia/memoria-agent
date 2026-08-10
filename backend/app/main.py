import os
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from langgraph.checkpoint.postgres import PostgresSaver
from pydantic import BaseModel

from app.agent.graph import build_graph
from app.db import ProfileStore, init_profiles_table

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql://memoria:memoria@localhost:5432/memoria"
)

# state du graphe : session_id sert de thread_id LangGraph, le checkpointer
# Postgres remplace le dict Python en mémoire de l'étape précédente.
# user_id est distinct : il survit aux sessions et alimente load_user_profile.
graph = None
profile_store = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global graph, profile_store
    init_profiles_table(DATABASE_URL)
    profile_store = ProfileStore(DATABASE_URL)
    with PostgresSaver.from_conn_string(DATABASE_URL) as checkpointer:
        checkpointer.setup()
        graph = build_graph(checkpointer=checkpointer, profile_store=profile_store)
        yield


app = FastAPI(lifespan=lifespan)


class StartSessionPayload(BaseModel):
    user_id: str


class AnswerPayload(BaseModel):
    correct: bool
    response_time: float


def _config(session_id: str) -> dict:
    return {"configurable": {"thread_id": session_id}}


def _get_state(session_id: str) -> dict | None:
    snapshot = graph.get_state(_config(session_id))
    return snapshot.values or None


def _public_state(state: dict) -> dict:
    return {
        "session_id": state["session_id"],
        "user_id": state["user_id"],
        "current_exercise": state["current_exercise"],
        "current_difficulty": state["current_difficulty"],
        "exercise_family": state["exercise_family"],
        "history": state["history"],
    }


def _save_profile(state: dict) -> None:
    profile_store.upsert(
        state["user_id"],
        state["current_difficulty"],
        state["avg_response_time"],
        state["error_rate"],
    )


@app.post("/sessions/start")
def start_session(payload: StartSessionPayload):
    session_id = str(uuid.uuid4())
    state = {
        "session_id": session_id,
        "user_id": payload.user_id,
        "history": [],
        "avg_response_time": 0.0,
        "error_rate": 0.0,
        "current_difficulty": 3,
        "exercise_family": "calc",
        "current_exercise": None,
    }
    result = graph.invoke(state, config=_config(session_id))
    _save_profile(result)
    return _public_state(result)


@app.post("/sessions/{session_id}/answer")
def submit_answer(session_id: str, payload: AnswerPayload):
    state = _get_state(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="session not found")
    if state["current_exercise"] is None:
        raise HTTPException(status_code=400, detail="no exercise pending for this session")

    state["history"].append({
        "family": state["current_exercise"]["type"],
        "correct": payload.correct,
        "response_time": payload.response_time,
    })

    result = graph.invoke(state, config=_config(session_id))
    _save_profile(result)
    return _public_state(result)


@app.get("/sessions/{session_id}")
def get_session(session_id: str):
    state = _get_state(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="session not found")
    return _public_state(state)
