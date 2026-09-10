.DEFAULT_GOAL := help
SHELL := /bin/bash

PY := backend/.venv/bin/python
PIP := backend/.venv/bin/pip

.PHONY: help setup seed dev-api dev-ui test test-backend test-frontend lint bench build clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

setup: ## Install backend and frontend dependencies
	python3 -m venv backend/.venv
	$(PIP) install -q --upgrade pip
	cd backend && .venv/bin/pip install -q -e ".[dev]"
	cd frontend && npm install

seed: ## Drop, recreate and populate the database with 10,000 employees
	cd backend && .venv/bin/python -m app.seed

dev-api: ## Run the backend on :8000
	cd backend && .venv/bin/python -m uvicorn app.main:app --reload --port 8000

dev-ui: ## Run the frontend on :5173
	cd frontend && npm run dev

test: test-backend test-frontend ## Run every test suite

test-backend: ## Run the backend suite
	cd backend && .venv/bin/python -m pytest

test-frontend: ## Run the frontend suite
	cd frontend && npm run test

lint: ## Lint and type-check both sides
	cd backend && .venv/bin/ruff check . && .venv/bin/ruff format --check . && .venv/bin/mypy app
	cd frontend && npm run typecheck

bench: ## Measure endpoint latency (needs the backend running and seeded)
	cd backend && .venv/bin/python scripts/benchmark.py

build: ## Production build of the frontend
	cd frontend && npm run build

clean: ## Remove build artefacts, caches and the database
	rm -rf backend/.venv backend/salary.db* backend/.pytest_cache backend/.ruff_cache \
	       backend/.mypy_cache frontend/node_modules frontend/dist
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
