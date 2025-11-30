# Makefile for F2L Web Refactor Backend

.PHONY: help install test test-unit test-integration test-e2e test-performance test-coverage clean lint format security

# Default target
help:
	@echo "Available targets:"
	@echo "  install          - Install dependencies"
	@echo "  test             - Run all tests"
	@echo "  test-unit        - Run unit tests only"
	@echo "  test-integration - Run integration tests only"
	@echo "  test-e2e         - Run end-to-end tests only"
	@echo "  test-performance - Run performance tests only"
	@echo "  test-coverage    - Run tests with coverage report"
	@echo "  test-fast        - Run fast tests only (unit + smoke)"
	@echo "  lint             - Run code linting"
	@echo "  format           - Format code"
	@echo "  security         - Run security checks"
	@echo "  clean            - Clean up generated files"

# Install dependencies
install:
	pip install -r requirements.txt
	pip install -r requirements-test.txt

# Run all tests
test:
	pytest

# Run unit tests only
test-unit:
	pytest -m "unit" --tb=short

# Run integration tests only
test-integration:
	pytest -m "integration" --tb=short

# Run end-to-end tests only
test-e2e:
	pytest -m "e2e" --tb=short

# Run performance tests only
test-performance:
	pytest -m "performance" --tb=short -v

# Run tests with coverage
test-coverage:
	pytest --cov=app --cov-report=html --cov-report=term-missing

# Run fast tests only (unit + smoke)
test-fast:
	pytest -m "unit or smoke" --tb=line

# Run tests in parallel
test-parallel:
	pytest -n auto

# Run specific test file
test-file:
	@read -p "Enter test file path: " file; \
	pytest $$file -v

# Run tests matching pattern
test-pattern:
	@read -p "Enter test pattern: " pattern; \
	pytest -k "$$pattern" -v

# Code linting
lint:
	flake8 app tests
	mypy app
	black --check app tests
	isort --check-only app tests

# Format code
format:
	black app tests
	isort app tests

# Security checks
security:
	bandit -r app
	safety check

# Clean up
clean:
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -rf .coverage
	rm -rf htmlcov/
	rm -rf .pytest_cache/
	rm -rf .mypy_cache/
	rm -rf dist/
	rm -rf build/

# Development setup
dev-setup: install
	pre-commit install

# Run tests with different Python versions (requires tox)
test-tox:
	tox

# Generate test report
test-report:
	pytest --html=report.html --self-contained-html

# Database setup for testing
test-db-setup:
	@echo "Setting up test database..."
	# Add database setup commands here

# Docker test environment
test-docker:
	docker-compose -f docker-compose.test.yml up --build --abort-on-container-exit

# Continuous testing (watch for changes)
test-watch:
	pytest-watch

# Benchmark tests
benchmark:
	pytest --benchmark-only --benchmark-sort=mean

# Memory profiling
test-memory:
	pytest --memray

# Test with different markers
test-smoke:
	pytest -m "smoke"

test-regression:
	pytest -m "regression"

test-security-tests:
	pytest -m "security"

# CI/CD targets
ci-test: lint security test-coverage

# Quick health check
health-check: test-fast lint

# Full validation (for pre-commit)
validate: format lint security test
