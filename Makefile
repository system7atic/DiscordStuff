.PHONY: build-up pull-up down dev-db dev push

IMAGE := ghcr.io/system7atic/discordstuff:latest

build-up:
	docker compose up --build -d

pull-up:
	docker compose pull app
	docker compose up -d

down:
	docker compose down

dev-db:
	docker compose up db -d

dev:
	pip install -e ".[dev]"
	python -m discordstuff.main

push:
	docker build -t $(IMAGE) .
	docker push $(IMAGE)
