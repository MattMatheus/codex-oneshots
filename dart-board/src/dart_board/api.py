import os

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, Response

from .checkout import suggest_checkout
from .heatmap import render_heatmap
from .ingest import USBCaptureManager
from .models import (
    CaptureStartRequest,
    CaptureStatusOut,
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

app = FastAPI(title="Dart Board MVP", version="0.3.0")
store = DartBoardStore(db_path=os.getenv("DARTBOARD_DB_PATH", "dartboard.db"))
capture_manager = USBCaptureManager(store=store)


@app.get("/", response_class=HTMLResponse)
def ui_home() -> str:
    return """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Dart Board Local UI</title>
  <style>
    body { font-family: -apple-system, sans-serif; margin: 1.5rem; background: #0f1115; color: #eceff4; }
    .row { display: flex; gap: 0.75rem; flex-wrap: wrap; margin-bottom: 0.75rem; }
    input, button { padding: 0.55rem; border-radius: 8px; border: 1px solid #2d3340; background: #151922; color: #eceff4; }
    button { cursor: pointer; }
    .card { border: 1px solid #2d3340; border-radius: 10px; padding: 1rem; margin-bottom: 1rem; background: #131722; }
    img { max-width: 420px; border: 1px solid #2d3340; border-radius: 10px; }
    pre { background: #0d1117; padding: 0.75rem; border-radius: 8px; overflow: auto; }
  </style>
</head>
<body>
  <h1>Dart Board Local UI</h1>
  <div class="card">
    <div class="row">
      <input id="userId" placeholder="user_id" value="u1" />
      <input id="userName" placeholder="name" value="Matt" />
      <button onclick="createUser()">Create User</button>
    </div>
    <div class="row">
      <input id="sessionId" placeholder="session_id" value="s1" />
      <input id="sourceRef" placeholder="source_ref" value="usb-local" />
      <button onclick="createSession()">Create Session</button>
    </div>
  </div>

  <div class="card">
    <div class="row">
      <input id="cameraIndex" type="number" min="0" value="0" />
      <input id="fps" type="number" min="1" max="60" value="10" />
      <button onclick="startCapture()">Start Capture</button>
      <button onclick="stopCapture()">Stop Capture</button>
      <button onclick="refresh()">Refresh</button>
    </div>
    <pre id="status"></pre>
  </div>

  <div class="card">
    <h3>Heatmap</h3>
    <img id="heatmap" src="" alt="heatmap" />
  </div>

  <script>
    async function api(path, method="GET", body=null) {
      const r = await fetch(path, {
        method,
        headers: { "Content-Type": "application/json" },
        body: body ? JSON.stringify(body) : null
      });
      const text = await r.text();
      let data = {};
      try { data = text ? JSON.parse(text) : {}; } catch { data = { raw: text }; }
      if (!r.ok) throw new Error(JSON.stringify(data));
      return data;
    }

    function ids() {
      return {
        user_id: document.getElementById("userId").value,
        session_id: document.getElementById("sessionId").value,
        name: document.getElementById("userName").value,
        source_ref: document.getElementById("sourceRef").value
      };
    }

    async function createUser() { await api("/users", "POST", { user_id: ids().user_id, name: ids().name }); await refresh(); }
    async function createSession() { await api("/sessions", "POST", { user_id: ids().user_id, session_id: ids().session_id, source_ref: ids().source_ref }); await refresh(); }
    async function startCapture() {
      const camera_index = Number(document.getElementById("cameraIndex").value);
      const fps = Number(document.getElementById("fps").value);
      await api("/capture/start", "POST", { user_id: ids().user_id, session_id: ids().session_id, camera_index, fps });
      await refresh();
    }
    async function stopCapture() { await api("/capture/stop", "POST"); await refresh(); }

    async function refresh() {
      const st = await api("/capture/status");
      document.getElementById("status").textContent = JSON.stringify(st, null, 2);
      const u = ids().user_id;
      document.getElementById("heatmap").src = `/heatmap/${u}.png?t=${Date.now()}`;
    }

    refresh().catch(err => { document.getElementById("status").textContent = String(err); });
  </script>
</body>
</html>"""


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


@app.post("/capture/start", response_model=CaptureStatusOut)
def start_capture(payload: CaptureStartRequest) -> CaptureStatusOut:
    if store.get_user(payload.user_id) is None:
        raise HTTPException(status_code=404, detail="user not found")

    sess = store.get_session(payload.session_id)
    if sess is None:
        raise HTTPException(status_code=404, detail="session not found")
    if sess.user_id != payload.user_id:
        raise HTTPException(status_code=400, detail="session does not belong to user")

    try:
        status = capture_manager.start_capture(
            user_id=payload.user_id,
            session_id=payload.session_id,
            camera_index=payload.camera_index,
            fps=payload.fps,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return CaptureStatusOut(**status)


@app.post("/capture/stop", response_model=CaptureStatusOut)
def stop_capture() -> CaptureStatusOut:
    status = capture_manager.stop_capture()
    return CaptureStatusOut(**status)


@app.get("/capture/status", response_model=CaptureStatusOut)
def capture_status() -> CaptureStatusOut:
    status = capture_manager.status()
    return CaptureStatusOut(**status)


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
