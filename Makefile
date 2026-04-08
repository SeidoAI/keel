.PHONY: install sync test lint format check clean build pre-commit-install pre-commit-run

# ==============================================================================
# Installation
# ==============================================================================

install:
	@command -v uv >/dev/null 2>&1 || { echo "uv is not installed. Install from https://docs.astral.sh/uv/"; exit 1; }
	uv sync

sync: install

# ==============================================================================
# Testing
# ==============================================================================

test:
	uv run pytest

test-unit:
	uv run pytest tests/unit -v

test-integration:
	uv run pytest tests/integration -v

# ==============================================================================
# Code Quality
# ==============================================================================

lint:
	uv run ruff check src tests
	uv run codespell src tests

format:
	uv run ruff format src tests

format-check:
	uv run ruff format --check src tests

# Run every quality gate (lint + format + tests)
check: lint format-check test

# ==============================================================================
# Build
# ==============================================================================

build:
	uv build

clean:
	rm -rf .pytest_cache .ruff_cache dist build *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} +

# ==============================================================================
# Pre-commit
# ==============================================================================

# Install pre-commit git hook (one-time per clone)
pre-commit-install:
	uv run pre-commit install

# Run all pre-commit hooks across the whole repo (not just staged files)
pre-commit-run:
	uv run pre-commit run --all-files
