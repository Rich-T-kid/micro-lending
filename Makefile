.PHONY: up down logs migrate reset dump

up:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f db

migrate:
	bash db/scripts/migrate.sh

reset:
	bash db/scripts/reset_local.sh

dump:
	bash db/scripts/dump.sh
