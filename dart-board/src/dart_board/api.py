import os
import time

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, Response, StreamingResponse

from .checkout import suggest_checkout
from .heatmap import render_heatmap
from .ingest import USBCaptureManager
from .models import (
    CaptureStartRequest,
    CaptureStatusOut,
    CheckoutSuggestion,
    FinishAdviceOut,
    PreviewStartRequest,
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
    .video-container { position: relative; display: inline-block; overflow: hidden; }
    .video-container img { border-radius: 10px; }
    .video-container .heatmap { position: absolute; opacity: 0.5; z-index: 2; pointer-events: none; transform-origin: center center; }
    .video-container .live-feed { z-index: 1; display: block; }
    .views { display: flex; gap: 1.5rem; flex-wrap: wrap; }
    .view-card { flex: 1; min-width: 300px; }
    .slider-row { display: flex; align-items: center; gap: 0.5rem; margin-top: 0.5rem; }
    .slider-row input[type="range"] { flex: 1; }
    .slider-row label { min-width: 120px; }
    .preview-badge { background: #d97706; color: #000; padding: 2px 8px; border-radius: 4px; font-size: 0.8em; margin-left: 8px; }
    .recording-badge { background: #dc2626; color: #fff; padding: 2px 8px; border-radius: 4px; font-size: 0.8em; margin-left: 8px; }
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
      <button onclick="startPreview()" style="background: #92400e;">Preview</button>
      <button onclick="startCapture()">Start Capture</button>
      <button onclick="stopCapture()">Stop</button>
      <button onclick="clearData()" style="background: #8b2635;">Clear Data</button>
      <button onclick="refresh()">Refresh</button>
      <span id="modeBadge"></span>
    </div>
    <pre id="status"></pre>
  </div>

  <div class="card">
    <h3>Live View</h3>
    <div class="views">
      <div class="view-card">
        <h4>Camera Feed</h4>
        <img id="liveFeed" src="" alt="Live feed (start preview or capture)" style="background: #1a1f2e; min-height: 240px;" />
      </div>
      <div class="view-card">
        <h4>Heatmap Overlay <small>(adjust to align with board)</small></h4>
        <div class="video-container">
          <img id="liveOverlay" class="live-feed" src="" alt="Live overlay" style="background: #1a1f2e; min-height: 240px; width: 420px; height: 420px; object-fit: cover;" />
          <img id="heatmapOverlay" class="heatmap" src="" alt="heatmap overlay" />
        </div>
        <div class="slider-row">
          <label>Opacity:</label>
          <input type="range" id="opacitySlider" min="0" max="100" value="50" oninput="updateOverlay()" />
          <span id="opacityValue">50%</span>
        </div>
        <div class="slider-row">
          <label>Size:</label>
          <input type="range" id="sizeSlider" min="50" max="150" value="100" oninput="updateOverlay()" />
          <span id="sizeValue">100%</span>
        </div>
        <div class="slider-row">
          <label>X Offset:</label>
          <input type="range" id="xOffsetSlider" min="-50" max="50" value="0" oninput="updateOverlay()" />
          <span id="xOffsetValue">0%</span>
        </div>
        <div class="slider-row">
          <label>Y Offset:</label>
          <input type="range" id="yOffsetSlider" min="-50" max="50" value="0" oninput="updateOverlay()" />
          <span id="yOffsetValue">0%</span>
        </div>
      </div>
    </div>
  </div>

  <div class="card">
    <h3>Heatmap Only</h3>
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
    async function startPreview() {
      const camera_index = Number(document.getElementById("cameraIndex").value);
      const fps = Number(document.getElementById("fps").value);
      await api("/capture/preview", "POST", { camera_index, fps });
      await refresh();
    }
    async function startCapture() {
      const camera_index = Number(document.getElementById("cameraIndex").value);
      const fps = Number(document.getElementById("fps").value);
      await api("/capture/start", "POST", { user_id: ids().user_id, session_id: ids().session_id, camera_index, fps });
      await refresh();
    }
    async function stopCapture() { await api("/capture/stop", "POST"); await refresh(); }
    async function clearData() {
      if (!confirm("Clear all throw data for this user? This will reset the heatmap.")) return;
      await api(`/throws/${ids().user_id}`, "DELETE");
      await refresh();
    }

    let autoRefreshInterval = null;

    function startAutoRefresh() {
      if (autoRefreshInterval) return;
      autoRefreshInterval = setInterval(() => {
        const u = ids().user_id;
        const heatmapUrl = `/heatmap/${u}.png?t=${Date.now()}`;
        document.getElementById("heatmap").src = heatmapUrl;
        document.getElementById("heatmapOverlay").src = heatmapUrl;
      }, 1000); // Update heatmap every second
    }

    function stopAutoRefresh() {
      if (autoRefreshInterval) {
        clearInterval(autoRefreshInterval);
        autoRefreshInterval = null;
      }
    }

    function updateOverlay() {
      const opacity = document.getElementById("opacitySlider").value;
      const size = document.getElementById("sizeSlider").value;
      const xOffset = document.getElementById("xOffsetSlider").value;
      const yOffset = document.getElementById("yOffsetSlider").value;

      document.getElementById("opacityValue").textContent = opacity + "%";
      document.getElementById("sizeValue").textContent = size + "%";
      document.getElementById("xOffsetValue").textContent = xOffset + "%";
      document.getElementById("yOffsetValue").textContent = yOffset + "%";

      const heatmapEl = document.getElementById("heatmapOverlay");
      heatmapEl.style.opacity = opacity / 100;
      heatmapEl.style.width = size + "%";
      heatmapEl.style.height = size + "%";
      heatmapEl.style.left = (50 - size/2 + Number(xOffset)) + "%";
      heatmapEl.style.top = (50 - size/2 + Number(yOffset)) + "%";
    }

    async function refresh() {
      const st = await api("/capture/status");
      document.getElementById("status").textContent = JSON.stringify(st, null, 2);
      const u = ids().user_id;
      const heatmapUrl = `/heatmap/${u}.png?t=${Date.now()}`;
      document.getElementById("heatmap").src = heatmapUrl;
      document.getElementById("heatmapOverlay").src = heatmapUrl;

      // Update mode badge
      const badge = document.getElementById("modeBadge");
      if (st.running && st.preview_only) {
        badge.innerHTML = '<span class="preview-badge">PREVIEW</span>';
      } else if (st.running) {
        badge.innerHTML = '<span class="recording-badge">● RECORDING</span>';
        startAutoRefresh();
      } else {
        badge.innerHTML = '';
        stopAutoRefresh();
      }

      // Update live feed sources based on capture status
      if (st.running) {
        const streamUrl = "/capture/stream";
        document.getElementById("liveFeed").src = streamUrl;
        document.getElementById("liveOverlay").src = streamUrl;
      } else {
        document.getElementById("liveFeed").src = "";
        document.getElementById("liveOverlay").src = "";
      }

      // Apply current overlay settings
      updateOverlay();
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


@app.delete("/throws/{user_id}")
def clear_throws(user_id: str) -> dict[str, object]:
    """Clear all throws for a user (resets their heatmap)."""
    if store.get_user(user_id) is None:
        raise HTTPException(status_code=404, detail="user not found")
    deleted = store.clear_throws_for_user(user_id)
    return {"user_id": user_id, "deleted": deleted}


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


@app.post("/capture/preview", response_model=CaptureStatusOut)
def start_preview(payload: PreviewStartRequest) -> CaptureStatusOut:
    """Start camera preview without recording data (for alignment)."""
    try:
        status = capture_manager.start_preview(
            camera_index=payload.camera_index,
            fps=payload.fps,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return CaptureStatusOut(**status)


@app.get("/capture/status", response_model=CaptureStatusOut)
def capture_status() -> CaptureStatusOut:
    status = capture_manager.status()
    return CaptureStatusOut(**status)


def _generate_mjpeg_stream():
    """Generator that yields MJPEG frames for live streaming."""
    while True:
        frame = capture_manager.get_latest_frame()
        if frame is not None:
            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n" + frame + b"\r\n"
            )
        else:
            # No frame available, send a small delay
            time.sleep(0.1)
        # Small delay to avoid overwhelming the client
        time.sleep(0.03)


@app.get("/capture/stream")
def capture_stream():
    """MJPEG live video stream from the capture camera."""
    status = capture_manager.status()
    if not status.get("running"):
        raise HTTPException(status_code=404, detail="Capture not running")
    return StreamingResponse(
        _generate_mjpeg_stream(),
        media_type="multipart/x-mixed-replace; boundary=frame",
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
