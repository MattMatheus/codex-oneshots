# Dart Board (codex-oneshot)

Source idea: `app.dartboard.io`

## Product Requirements
- Per-user heatmap.
- Computer vision from video source.
- Suggest combinations of darts to win when user can finish.

## Human Task Board
- [ ] Luke: determine `app.dartboard.io` streaming method (HLS / DASH / WebRTC / RTSP / downloadable files / API).

## Target Architecture (Apple Silicon)
- Platform: macOS Apple Silicon (arm64).
- Runtime: Python 3.11+ arm64.
- API: FastAPI + Uvicorn.
- CV: OpenCV local processing.
- Data: SQLite (`dartboard.db`) for MVP.
- Deployment mode: local-first, no external API required.

## Current MVP Capabilities
- Local UI for USB capture operations and heatmap viewing.
- Create users and sessions.
- Store throw points (`x_norm`, `y_norm`, confidence).
- USB camera capture start/stop/status (local OpenCV camera index).
- Generate per-user heatmap PNG locally.
- Checkout recommendation engine with double-out rules.
- Finish advice endpoint (`can_finish` + combinations).

## API Endpoints
- `GET /` (local UI)
- `GET /health`
- `POST /users`
- `POST /sessions`
- `POST /throws`
- `POST /capture/start`
- `POST /capture/stop`
- `GET /capture/status`
- `GET /capture/stream` (MJPEG live video stream)
- `GET /checkout/{score}`
- `GET /advice/{user_id}/{current_score}`
- `GET /heatmap/{user_id}`
- `GET /heatmap/{user_id}.png`

## Project Layout
- `src/dart_board/api.py` - FastAPI app + endpoints.
- `src/dart_board/checkout.py` - checkout combination engine.
- `src/dart_board/storage.py` - SQLite persistence.
- `src/dart_board/heatmap.py` - board heatmap rendering.
- `src/dart_board/cv.py` - CV pipeline interface/stub.
- `tests/` - unit/integration tests for MVP flows.

## Quick Start
```bash
git clone https://github.com/MattMatheus/codex-oneshots.git
cd codex-oneshots/dart-board
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn src.dart_board.api:app --reload
```

Open:
- UI: `http://127.0.0.1:8000/`
- API docs: `http://127.0.0.1:8000/docs`

## Engineering Plan To Complete
1. Streaming integration
   - Finalize source ingestion adapter after Luke confirms stream protocol.
   - Support both live stream and uploaded file mode.
2. CV implementation
   - Board calibration and homography normalization.
   - Dart impact detection and hit-point extraction.
   - Confidence scoring and false-positive suppression.
3. Scoring accuracy
   - Convert normalized hit points to board segments and score values.
   - Validate score consistency vs expected game state.
4. UX/API hardening
   - Session lifecycle controls (start/end/reset).
   - Authn/authz for per-user data.
   - Input validation and rate limits.
5. Production readiness
   - Postgres migration.
   - Containerization and CI.
   - Observability and error telemetry.
