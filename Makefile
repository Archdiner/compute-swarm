.PHONY: help install test lint format clean run-marketplace run-seller run-buyer

help:
	@echo "ComputeSwarm Development Commands"
	@echo ""
	@echo "Setup:"
	@echo "  make install          Install all dependencies"
	@echo "  make install-dev      Install with development dependencies"
	@echo ""
	@echo "Testing:"
	@echo "  make test             Run all tests"
	@echo "  make test-unit        Run unit tests only"
	@echo "  make test-integration Run integration tests only"
	@echo "  make test-cov         Run tests with coverage report"
	@echo "  make test-watch       Run tests in watch mode"
	@echo ""
	@echo "Code Quality:"
	@echo "  make lint             Run linters (flake8, mypy)"
	@echo "  make format           Format code (black, isort)"
	@echo "  make format-check     Check code formatting"
	@echo ""
	@echo "Running:"
	@echo "  make run-marketplace  Start marketplace server"
	@echo "  make run-seller       Start seller agent"
	@echo "  make run-buyer        Start buyer CLI"
	@echo ""
	@echo "Cleanup:"
	@echo "  make clean            Remove build artifacts and cache"

install:
	pip install -r requirements.txt

install-dev:
	pip install -r requirements.txt
	pip install -e .

test:
	pytest

test-unit:
	pytest -m unit

test-integration:
	pytest -m integration

test-cov:
	pytest --cov=src --cov-report=html --cov-report=term

test-watch:
	pytest-watch

lint:
	flake8 src tests
	mypy src

format:
	black src tests
	isort src tests

format-check:
	black --check src tests
	isort --check-only src tests

run-marketplace:
	./scripts/start_marketplace.sh

run-seller:
	./scripts/start_seller.sh

run-buyer:
	./scripts/start_buyer.sh

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	rm -rf htmlcov/ .coverage build/ dist/
