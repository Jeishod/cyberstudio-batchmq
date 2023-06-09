#!make

dev:
	@uvicorn --reload --use-colors --host 0.0.0.0 --port 8000 --log-level debug "app.main:app"

format:
	black app
	pflake8 app

up-dev:
	@docker compose -f docker-compose.local.yaml up -d --build
