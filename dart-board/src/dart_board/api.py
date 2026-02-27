import os

from fastapi import FastAPI, HTTPException
from fastapi.responses import Response

from .checkout import suggest_checkout
from .heatmap import render_heatmap
from .models import (
    CheckoutSuggestion,
    FinishAdviceOut,
    SessionCreate,
    SessionOut,
    ThrowCreate,
    ThrowOut,
    UserCreate,
    UserOut,
)
from .storage import DartBoardStore

app = FastAPI(title="Dart Board MVP", version="0.2.0")
store = DartBoardStore(db_path=os.getenv("DARTBOARD_DB_PATH", "dartboard.db"))


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/users", response_model=UserOut)
def create_user(payload: UserCreate) -> UserOut:
    if store.get_user(payload.user_id) is not None:
        raise HTTPException(status_code=409, detail="user_id already exists")
    user = store.create_user(user_id=payload.user_id, name=payload.name)
    return UserOut(user_id=user.id, name=user.name, created_at=user.created_at)


@app.post("/sessions", response_model=SessionOut)
def create_session(payload: SessionCreate) -> SessionOut:
    if store.get_user(payload.user_id) is None:
        raise HTTPException(status_code=404, detail="user not found")
    if store.get_session(payload.session_id) is not None:
        raise HTTPException(status_code=409, detail="session_id already exists")

    sess = store.create_session(
        session_id=payload.session_id,
        user_id=payload.user_id,
        source_ref=payload.source_ref,
    )
    return SessionOut(
        session_id=sess.id,
        user_id=sess.user_id,
        started_at=sess.started_at,
        ended_at=sess.ended_at,
        source_ref=sess.source_ref,
    )


@app.post("/throws", response_model=ThrowOut)
def create_throw(payload: ThrowCreate) -> ThrowOut:
    if store.get_user(payload.user_id) is None:
        raise HTTPException(status_code=404, detail="user not found")
    sess = store.get_session(payload.session_id)
    if sess is None:
        raise HTTPException(status_code=404, detail="session not found")
    if sess.user_id != payload.user_id:
        raise HTTPException(status_code=400, detail="session does not belong to user")

    throw = store.add_throw(
        user_id=payload.user_id,
        session_id=payload.session_id,
        x_norm=payload.x_norm,
        y_norm=payload.y_norm,
        confidence=payload.confidence,
    )
    return ThrowOut(
        id=throw.id,
        user_id=throw.user_id,
        session_id=throw.session_id,
        ts=throw.ts,
        x_norm=throw.x_norm,
        y_norm=throw.y_norm,
        confidence=throw.confidence,
    )


@app.get("/checkout/{score}", response_model=CheckoutSuggestion)
def checkout(score: int) -> CheckoutSuggestion:
    combos = suggest_checkout(score)
    if not combos:
        raise HTTPException(status_code=404, detail="No checkout combinations for score")
    return CheckoutSuggestion(score=score, combinations=combos)


@app.get("/advice/{user_id}/{current_score}", response_model=FinishAdviceOut)
def finish_advice(user_id: str, current_score: int) -> FinishAdviceOut:
    if store.get_user(user_id) is None:
        raise HTTPException(status_code=404, detail="user not found")
    combos = suggest_checkout(current_score)
    return FinishAdviceOut(
        user_id=user_id,
        current_score=current_score,
        can_finish=bool(combos),
        combinations=combos,
    )


@app.get("/heatmap/{user_id}.png")
def user_heatmap_png(user_id: str) -> Response:
    if store.get_user(user_id) is None:
        raise HTTPException(status_code=404, detail="user not found")

    throws = store.list_throws_for_user(user_id)
    points = [(t.x_norm, t.y_norm) for t in throws]
    image = render_heatmap(points)
    return Response(content=image, media_type="image/png")


@app.get("/heatmap/{user_id}")
def user_heatmap(user_id: str) -> dict[str, object]:
    if store.get_user(user_id) is None:
        raise HTTPException(status_code=404, detail="user not found")

    throws = store.list_throws_for_user(user_id)
    points = [
        {
            "x_norm": t.x_norm,
            "y_norm": t.y_norm,
            "confidence": t.confidence,
            "session_id": t.session_id,
            "ts": t.ts,
        }
        for t in throws
    ]
    return {
        "user_id": user_id,
        "throw_count": len(points),
        "points": points,
        "heatmap_png": f"/heatmap/{user_id}.png",
    }
