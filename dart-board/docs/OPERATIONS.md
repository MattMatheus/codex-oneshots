# Dart Board Operations Guide

## Scope
Runbook for local operators working on USB camera placement, calibration, capture, QA, and security modes.

## Prerequisites
- macOS Apple Silicon
- Python 3.11+ (host-native mode)
- Podman (container mode)
- USB camera for live capture workflows

## Run Modes

### Host Native (USB capture enabled)
```bash
cd /Users/mattmatheus/AgenticEngineering/AthenaWorkQueue/Untrusted/codex-oneshots/dart-board
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export DARTBOARD_CAPTURE_ENABLED=true
uvicorn src.dart_board.api:app --host 0.0.0.0 --port 8000 --reload
```

### Podman (capture disabled by default)
```bash
cd /Users/mattmatheus/AgenticEngineering/AthenaWorkQueue/Untrusted/codex-oneshots/dart-board
make up
```

## UI Workflow
1. Open `http://127.0.0.1:8000/`.
2. Create user and session.
3. Use **Camera Preview** to align board center with aiming reticle.
4. Enter calibration points in order:
   - top-left, top-right, bottom-right, bottom-left
5. Click **Set Calibration** and verify **Warped Board Preview** looks square.
6. Start capture.
7. Watch heatmap update side by side with camera preview.

## Calibration Input Format
- `x1,y1;x2,y2;x3,y3;x4,y4`
- Example:
  - `120,80;1020,90;1030,980;110,970`

## API Key Security Mode
Enable shared-key protection:
```bash
export DARTBOARD_API_KEY=change-me
```

Behavior:
- API requests require `x-api-key: <value>`.
- For image endpoints in browser, `api_key=<value>` query is accepted.

## QA Checklist
```bash
cd /Users/mattmatheus/AgenticEngineering/AthenaWorkQueue/Untrusted/codex-oneshots/dart-board
source .venv/bin/activate
pytest -q
```

Expected:
- All tests pass.

## Known Limits
- Current hit detection is motion-based and can false-trigger with hands/body movement.
- USB capture from containerized Podman on macOS is typically not available by default.
- No per-user auth model yet (shared API key only).
