import os

import cv2
import numpy as np
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response

from .calibration import BoardCalibrator
from .checkout import suggest_checkout
from .heatmap import render_heatmap
from .ingest import USBCaptureManager
from .models import (
    CalibrationSetRequest,
    CalibrationStatusOut,
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

app = FastAPI(title="Dart Board MVP", version="0.4.0")
store = DartBoardStore(db_path=os.getenv("DARTBOARD_DB_PATH", "dartboard.db"))
calibrator = BoardCalibrator(state_path=os.getenv("DARTBOARD_CALIB_PATH", "calibration.json"))
capture_enabled = os.getenv("DARTBOARD_CAPTURE_ENABLED", "true").lower() == "true"
capture_manager = USBCaptureManager(store=store, calibrator=calibrator) if capture_enabled else None
api_key = os.getenv("DARTBOARD_API_KEY")


@app.middleware("http")
async def api_key_middleware(request: Request, call_next):
    if not api_key:
        return await call_next(request)

    public_paths = {"/health", "/docs", "/openapi.json", "/redoc"}
    if request.url.path in public_paths:
        return await call_next(request)

    supplied = request.headers.get("x-api-key") or request.query_params.get("api_key")
    if supplied != api_key:
        return JSONResponse(status_code=401, content={"detail": "invalid or missing api key"})

    return await call_next(request)


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
    .row { display: flex; gap: 0.75rem; flex-wrap: wrap; margin-bottom: 0.75rem; align-items: center; }
    input, button { padding: 0.55rem; border-radius: 8px; border: 1px solid #2d3340; background: #151922; color: #eceff4; }
    button { cursor: pointer; }
    .card { border: 1px solid #2d3340; border-radius: 10px; padding: 1rem; margin-bottom: 1rem; background: #131722; }
    img { max-width: 100%; border: 1px solid #2d3340; border-radius: 10px; display: block; }
    .grid { display: grid; grid-template-columns: repeat(2, minmax(320px, 1fr)); gap: 1rem; }
    .pane-title { margin: 0 0 0.5rem 0; font-size: 0.95rem; color: #9ea7b8; }
    .camera-wrap { position: relative; }
    .reticle {
      position: absolute;
      inset: 0;
      pointer-events: none;
    }
    .reticle::before, .reticle::after {
      content: "";
      position: absolute;
      background: rgba(57, 255, 20, 0.75);
    }
    .reticle::before { width: 2px; height: 100%; left: 50%; top: 0; transform: translateX(-1px); }
    .reticle::after { height: 2px; width: 100%; left: 0; top: 50%; transform: translateY(-1px); }
    .reticle-circle {
      position: absolute;
      left: 50%;
      top: 50%;
      width: 34%;
      aspect-ratio: 1 / 1;
      border: 2px solid rgba(57, 255, 20, 0.65);
      border-radius: 50%;
      transform: translate(-50%, -50%);
    }
    pre { background: #0d1117; padding: 0.75rem; border-radius: 8px; overflow: auto; }
  </style>
</head>
<body>
  <h1>Dart Board Local UI</h1>
  <div class="card">
    <div class="row">
      <input id="userId" placeholder="user_id" value="u1" />
      <input id="userName" placeholder="name" value="Matt" />
      <input id="apiKey" placeholder="api key (optional)" />
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
      <button onclick="refreshVisuals()">Preview Camera</button>
      <button onclick="startCapture()">Start Capture</button>
      <button onclick="stopCapture()">Stop Capture</button>
      <button onclick="refresh()">Refresh</button>
    </div>
    <pre id="status"></pre>
    <div class="row">
      <input id="calibrationPoints" style="min-width: 720px;" placeholder="x1,y1;x2,y2;x3,y3;x4,y4 (TL;TR;BR;BL)" />
      <button onclick="setCalibration()">Set Calibration</button>
      <button onclick="clearCalibration()">Clear Calibration</button>
    </div>
    <pre id="calibrationStatus"></pre>
  </div>

  <div class="card">
    <div class="grid">
      <div>
        <div class="pane-title">Camera Preview (placement check)</div>
        <div class="camera-wrap">
          <img id="camera" src="" alt="camera preview" />
          <div class="reticle"><div class="reticle-circle"></div></div>
        </div>
      </div>
      <div>
        <div class="pane-title">Per-User Heatmap</div>
        <img id="heatmap" src="" alt="heatmap" />
      </div>
      <div>
        <div class="pane-title">Warped Board Preview (homography)</div>
        <img id="calibrationPreview" src="" alt="calibration preview" />
      </div>
    </div>
  </div>

  <script>
    async function api(path, method="GET", body=null) {
      const apiKey = document.getElementById("apiKey").value.trim();
      const headers = { "Content-Type": "application/json" };
      if (apiKey) headers["x-api-key"] = apiKey;
      const r = await fetch(path, {
        method,
        headers,
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

    function parseCalibrationPoints() {
      const raw = document.getElementById("calibrationPoints").value.trim();
      if (!raw) throw new Error("Provide four points: x1,y1;x2,y2;x3,y3;x4,y4");
      const pts = raw.split(";").map(part => part.trim()).filter(Boolean).map(pair => {
        const vals = pair.split(",").map(v => Number(v.trim()));
        if (vals.length !== 2 || Number.isNaN(vals[0]) || Number.isNaN(vals[1])) {
          throw new Error(`Invalid point: ${pair}`);
        }
        return [vals[0], vals[1]];
      });
      if (pts.length !== 4) throw new Error("Exactly 4 points are required");
      return pts;
    }

    async function setCalibration() {
      const src_points = parseCalibrationPoints();
      await api("/calibration/set", "POST", { src_points });
      await refresh();
    }

    async function clearCalibration() {
      await api("/calibration/clear", "POST");
      await refresh();
    }

    async function refreshVisuals() {
      const u = ids().user_id;
      const camera_index = Number(document.getElementById("cameraIndex").value);
      const key = encodeURIComponent(document.getElementById("apiKey").value.trim());
      const keyQuery = key ? `&api_key=${key}` : "";
      document.getElementById("camera").src = `/camera/frame.jpg?camera_index=${camera_index}${keyQuery}&t=${Date.now()}`;
      document.getElementById("heatmap").src = `/heatmap/${u}.png?${key ? `api_key=${key}&` : ""}t=${Date.now()}`;
      document.getElementById("calibrationPreview").src = `/calibration/preview.jpg?camera_index=${camera_index}${keyQuery}&t=${Date.now()}`;
    }

    async function refresh() {
      const st = await api("/capture/status");
      document.getElementById("status").textContent = JSON.stringify(st, null, 2);
      const cal = await api("/calibration/status");
      document.getElementById("calibrationStatus").textContent = JSON.stringify(cal, null, 2);
      await refreshVisuals();
    }

    setInterval(() => { refreshVisuals().catch(() => {}); }, 1000);
    refresh().catch(err => { document.getElementById("status").textContent = String(err); });
  </script>
</body>
</html>"""


@app.get("/camera/frame.jpg")
def camera_frame(camera_index: int = 0) -> Response:
    cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        cap.release()
        raise HTTPException(status_code=503, detail=f"failed to open camera index {camera_index}")

    ok, frame = cap.read()
    cap.release()
    if not ok:
        raise HTTPException(status_code=503, detail="failed to read camera frame")

    h, w = frame.shape[:2]
    cx, cy = w // 2, h // 2
    color = (0, 255, 0)
    cv2.line(frame, (cx, 0), (cx, h), color, 1)
    cv2.line(frame, (0, cy), (w, cy), color, 1)
    cv2.circle(frame, (cx, cy), int(min(w, h) * 0.17), color, 2)
    cal_status = calibrator.status()
    src_points = cal_status.get("src_points")
    if isinstance(src_points, list) and len(src_points) == 4:
        poly = cv2.convexHull(np.array(src_points, dtype=np.float32)).astype(np.int32)
        cv2.polylines(frame, [poly], isClosed=True, color=(0, 165, 255), thickness=2)

    ok, encoded = cv2.imencode(".jpg", frame)
    if not ok:
        raise HTTPException(status_code=500, detail="failed to encode camera frame")

    return Response(content=encoded.tobytes(), media_type="image/jpeg")


@app.get("/calibration/status", response_model=CalibrationStatusOut)
def calibration_status() -> CalibrationStatusOut:
    return CalibrationStatusOut(**calibrator.status())


@app.post("/calibration/set", response_model=CalibrationStatusOut)
def calibration_set(payload: CalibrationSetRequest) -> CalibrationStatusOut:
    try:
        calibrator.set_src_points(payload.src_points)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return CalibrationStatusOut(**calibrator.status())


@app.post("/calibration/clear", response_model=CalibrationStatusOut)
def calibration_clear() -> CalibrationStatusOut:
    calibrator.clear()
    return CalibrationStatusOut(**calibrator.status())


@app.get("/calibration/preview.jpg")
def calibration_preview(camera_index: int = 0) -> Response:
    cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        cap.release()
        raise HTTPException(status_code=503, detail=f"failed to open camera index {camera_index}")

    ok, frame = cap.read()
    cap.release()
    if not ok:
        raise HTTPException(status_code=503, detail="failed to read camera frame")

    warped = calibrator.warp_frame(frame)
    ok, encoded = cv2.imencode(".jpg", warped)
    if not ok:
        raise HTTPException(status_code=500, detail="failed to encode preview frame")
    return Response(content=encoded.tobytes(), media_type="image/jpeg")


@app.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "capture_enabled": "true" if capture_enabled else "false",
    }


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
    if capture_manager is None:
        raise HTTPException(status_code=503, detail="capture disabled in current deployment")
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
    if capture_manager is None:
        raise HTTPException(status_code=503, detail="capture disabled in current deployment")
    status = capture_manager.stop_capture()
    return CaptureStatusOut(**status)


@app.get("/capture/status", response_model=CaptureStatusOut)
def capture_status() -> CaptureStatusOut:
    if capture_manager is None:
        return CaptureStatusOut(
            running=False,
            user_id=None,
            session_id=None,
            camera_index=None,
            fps=10,
            frames_processed=0,
            throws_detected=0,
            last_error="capture disabled in current deployment",
        )
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
