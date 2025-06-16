.PHONY: help install run test lint format clean

help:
	@echo "Available commands:"
	@echo "  make install    - Install dependencies"
	@echo "  make run        - Run the bot"
	@echo "  make test       - Run tests"
	@echo "  make lint       - Run linters"
	@echo "  make format     - Format code"
	@echo "  make clean      - Clean cache files"

install:
	pip install -r requirements.txt
	pre-commit install

run:
	python main.py

test:
	pytest tests/ -v --cov=.

lint:
	flake8 .
	mypy .

format:
	black .

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*.log" -delete
	rm -rf .coverage
	rm -rf htmlcov
	rm -rf .pytest_cache
	rm -rf .mypy_cache
