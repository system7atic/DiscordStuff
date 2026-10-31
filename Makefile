.PHONY: build-up down

build-up:
	docker compose up --build -d

down:
	docker compose down
