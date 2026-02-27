# Dart Board (codex-oneshot)

Source idea: `app.dartboard.io`

## Product Requirements
- Per-user heatmap.
- Computer vision from video source.
- Suggest combinations of darts to win when user can finish.

## Human Task Board
- [ ] Luke: determine `app.dartboard.io` streaming method (HLS / DASH / WebRTC / RTSP / downloadable files / API).

## Local-First Architecture (Podman Target)
Primary deployment target is local Podman, with host-native mode for USB camera capture.

### Mode A: Podman API (default)
- Container: `dart-board-api`
- Runtime: FastAPI + Uvicorn
- Persistence: named volume `dart_board_data` with SQLite DB at `/data/dartboard.db`
- Capture mode: disabled by default (`DARTBOARD_CAPTURE_ENABLED=false`)
- Use this for: API, UI, heatmaps, checkout advice, and non-camera workflows.

### Mode B: Host Native (USB capture)
- Run API directly on macOS for local USB camera access via OpenCV.
- Set `DARTBOARD_CAPTURE_ENABLED=true` (default in host mode).
- Use this for: `POST /capture/start` with local camera index.

## Current MVP Capabilities
- Local UI for capture operations and heatmap viewing.
- Create users and sessions.
- Store throw points (`x_norm`, `y_norm`, confidence).
- USB camera capture start/stop/status (when capture enabled).
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
- `GET /checkout/{score}`
- `GET /advice/{user_id}/{current_score}`
- `GET /heatmap/{user_id}`
- `GET /heatmap/{user_id}.png`

## Project Layout
- `src/dart_board/api.py` - FastAPI app + endpoints.
- `src/dart_board/ingest.py` - USB capture manager.
- `src/dart_board/cv.py` - motion-based hit detector stub.
- `src/dart_board/storage.py` - SQLite persistence.
- `src/dart_board/heatmap.py` - board heatmap rendering.
- `src/dart_board/checkout.py` - checkout combination engine.
- `Containerfile` - Podman image definition.
- `podman-compose.yml` - local stack orchestration.
- `Makefile` - standard local/PODMAN commands.

## Deploy: Podman (default)
```bash
cd AthenaWorkQueue/Untrusted/codex-oneshots/dart-board
make up
```

Then open:
- UI: `http://127.0.0.1:8000/`
- API docs: `http://127.0.0.1:8000/docs`

Useful commands:
```bash
make ps
make logs
make down
```

## Deploy: Host Native (USB capture)
```bash
cd AthenaWorkQueue/Untrusted/codex-oneshots/dart-board
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export DARTBOARD_CAPTURE_ENABLED=true
uvicorn src.dart_board.api:app --host 0.0.0.0 --port 8000 --reload
```

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
   - CI pipeline for Podman image build/test.
   - Observability and error telemetry.

## License
MIT. See [LICENSE](LICENSE).
