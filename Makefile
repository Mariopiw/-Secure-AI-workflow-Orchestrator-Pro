up:
	docker compose up --build

down:
	docker compose down

reset:
	docker compose down -v

test:
	pytest -q

lint:
	ruff check .

logs:
	docker compose logs -f api worker beat
