install-dev-deps: dev-deps
	pip-sync requirements.txt dev-requirements.txt

install-deps: deps
	pip-sync requirements.txt

deps:
	pip-compile --resolver=backtracking --output-file=requirements.txt pyproject.toml

dev-deps: deps
	pip-compile --resolver=backtracking --extra=dev --output-file=dev-requirements.txt pyproject.toml

fmt:
	cd src && autoflake --in-place --remove-all-unused-imports --recursive .
	cd src && isort .
	cd src && black .

lint:
	flake8 src
	cd src && mypy

test:
	mkdir -p src/static
	cd src && ./manage.py makemigrations --dry-run --no-input --check
	cd src && ./manage.py compilemessages
	cd src && pytest --dead-fixtures
	cd src && pytest -x

pr: fmt lint test

build:
	docker buildx build --platform linux/amd64 -t locker_api:latest --load .

save:
	docker save locker_api:latest -o locker_api.tar
