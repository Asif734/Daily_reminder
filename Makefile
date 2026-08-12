.PHONY: config up down logs test lint

config:
	docker compose config --quiet

up:
	docker compose up --build

down:
	docker compose down

logs:
	docker compose logs -f

test:
	@set -e; for service in api-gateway auth-service user-service reminder-service scheduler-worker; do \
		docker compose run --rm --no-deps $$service pytest -q -p no:cacheprovider; \
	done

lint:
	@set -e; for service in api-gateway auth-service user-service reminder-service scheduler-worker; do \
		docker compose run --rm --no-deps $$service ruff check --no-cache app tests; \
	done
