.PHONY: install sync test lint format check clean build

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
