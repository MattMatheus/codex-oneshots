.PHONY: dev build up down logs ps

dev:
	uvicorn src.dart_board.api:app --host 0.0.0.0 --port 8000 --reload

build:
	podman build -t dart-board-api:local -f Containerfile .

up:
	podman compose -f podman-compose.yml up -d --build

down:
	podman compose -f podman-compose.yml down

logs:
	podman compose -f podman-compose.yml logs -f

ps:
	podman compose -f podman-compose.yml ps
