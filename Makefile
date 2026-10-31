.PHONY: build-up down dev-db dev

build-up:
	docker compose up --build -d

down:
	docker compose down

dev-db:
	docker compose up db -d

dev:
	pip install -e ".[dev]"
	python -m discordstuff.main
