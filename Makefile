# Canonical developer + CI-parity commands for BioNodulo.
# Mirrors .github/workflows/ci.yml so `make test` / `make lint` / `make build`
# run the same gates locally (and give tooling a single recognised entrypoint).
#
# Python side assumes the project venv at .venv (falls back to `python`).
# Frontend side runs inside web/ via npm, matching the CI `frontend` job.

PY := $(if $(wildcard .venv/bin/python),.venv/bin/python,python)
WEB := web

.DEFAULT_GOAL := help

.PHONY: help test test-py test-web lint lint-py lint-web build build-web \
        typecheck e2e verify install

help: ## List available targets
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) \
	  | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

install: ## Install python (dev) + web dependencies
	$(PY) -m pip install -e ".[dev]"
	cd $(WEB) && npm ci

test: test-py test-web ## Run backend + frontend test suites

test-py: ## Run the Python test suite (CI: pytest tests/)
	$(PY) -m pytest tests/ --tb=short

test-web: ## Run the frontend unit tests (CI: npm test)
	cd $(WEB) && npm test

lint: lint-py lint-web ## Lint backend + frontend

lint-py: ## Ruff lint (CI: ruff check bionodulo tests)
	$(PY) -m ruff check bionodulo tests

lint-web: ## ESLint the web sources (CI: npm run lint)
	cd $(WEB) && npm run lint

typecheck: ## Advisory mypy on the backend (CI: non-blocking)
	$(PY) -m mypy bionodulo --ignore-missing-imports || true

build: build-web ## Type-check + build the frontend (CI: npm run build)

build-web:
	cd $(WEB) && npm run build

e2e: ## Run the Playwright end-to-end suite (auto-starts the dev server)
	cd $(WEB) && npm run test:e2e

verify: lint test build ## Full local gate: lint + tests + build (CI parity)
