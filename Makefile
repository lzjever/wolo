.PHONY: help clean install dev-install test test-cov lint format format-check check build sdist wheel docs html clean-docs run benchmark benchmark-all

# Use uv if available, otherwise fall back to pip
UV := $(shell command -v uv 2>/dev/null)
ifeq ($(UV),)
	PIP_CMD = pip
	PYTHON_CMD = python
	UV_SYNC = echo "uv not found, skipping sync"
else
	PIP_CMD = uv pip
	PYTHON_CMD = uv run
	UV_SYNC = uv sync
endif

help:
	@echo "Available targets:"
	@echo ""
	@echo "Setup:"
	@echo "  dev-install   - Install package with development dependencies (recommended)"
	@echo "  install       - Install the package"
	@echo ""
	@echo "Running:"
	@echo "  run           - Run wolo with a message (usage: make run MSG='your message')"
	@echo "  benchmark     - Run a single benchmark test"
	@echo "  benchmark-all - Run full benchmark suite"
	@echo ""
	@echo "Testing:"
	@echo "  test          - Run all unit tests"
	@echo "  test-cov      - Run tests with coverage report"
	@echo ""
	@echo "Code Quality:"
	@echo "  lint          - Run linting checks (ruff)"
	@echo "  format        - Format code with ruff"
	@echo "  format-check  - Check code formatting"
	@echo "  check         - Run all checks (lint + format check + tests)"
	@echo ""
	@echo "Building:"
	@echo "  build         - Build source and wheel distributions"
	@echo "  sdist         - Build source distribution"
	@echo "  wheel         - Build wheel distribution"
	@echo ""
	@echo "Cleanup:"
	@echo "  clean         - Clean build artifacts and cache files"
	@echo ""
	@if [ -n "$(UV)" ]; then \
		echo "Using uv for dependency management"; \
	else \
		echo "Using pip for dependency management (consider installing uv: curl -LsSf https://astral.sh/uv/install.sh | sh)"; \
	fi
	@echo ""

install:
	@if [ -n "$(UV)" ]; then \
		uv sync; \
	else \
		$(PIP_CMD) install -e .; \
	fi

dev-install:
	@echo "Installing package with all development dependencies..."
	@if [ -n "$(UV)" ]; then \
		uv sync --all-extras; \
	else \
		$(PIP_CMD) install -e ".[dev]"; \
	fi
	@echo "✅ Package and dependencies installed! Ready for development."

run:
	@if [ -z "$(MSG)" ]; then \
		echo "Usage: make run MSG='your message'"; \
		echo "Example: make run MSG='What is 2+2?'"; \
		exit 1; \
	fi
	$(PYTHON_CMD) -m wolo $(MSG)

benchmark:
	@if [ -z "$(MSG)" ]; then \
		$(PYTHON_CMD) -m wolo --benchmark "Read the file README.md and summarize it in one sentence."; \
	else \
		$(PYTHON_CMD) -m wolo --benchmark "$(MSG)"; \
	fi

benchmark-all:
	$(PYTHON_CMD) -m wolo.tests.benchmark

test:
	$(PYTHON_CMD) -m pytest tests/ -v -n auto

test-cov:
	$(PYTHON_CMD) -m pytest tests/ -v -n auto --cov=wolo --cov-report=html --cov-report=term

lint:
	$(PYTHON_CMD) -m ruff check wolo/ tests/ --output-format=concise --no-fix

format:
	$(PYTHON_CMD) -m ruff format wolo/ tests/

format-check:
	$(PYTHON_CMD) -m ruff format --check wolo/ tests/

check: lint format-check test
	@echo "All checks passed!"

build: clean
	@if [ -n "$(UV)" ]; then \
		uv sync --all-extras; \
	fi
	$(PYTHON_CMD) -m build

sdist: clean
	@if [ -n "$(UV)" ]; then \
		uv sync --all-extras; \
	fi
	$(PYTHON_CMD) -m build --sdist

wheel: clean
	@if [ -n "$(UV)" ]; then \
		uv sync --all-extras; \
	fi
	$(PYTHON_CMD) -m build --wheel

docs:
	@echo "Documentation is in README.md"

html:
	@echo "Documentation is in README.md"

clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info
	rm -rf .pytest_cache
	rm -rf .ruff_cache
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	rm -f benchmark_results.json
	@if [ -n "$(UV)" ]; then \
		echo "Note: To clean uv virtual environment, run: uv venv --clear"; \
	fi
