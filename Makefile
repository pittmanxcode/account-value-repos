PYTHON ?= python3.12
VENV ?= .venv
PIP := $(VENV)/bin/pip
AV := $(VENV)/bin/account-value

.PHONY: setup test lint doctor fixture

setup:
	$(PYTHON) -m venv $(VENV)
	$(PIP) install -q --upgrade pip
	$(PIP) install -q -e ".[dev]"
	npm install --prefix tmp exceljs@4.4.0 --no-fund --no-audit --loglevel=error
	@echo "Setup complete. Next: make doctor"

test:
	$(VENV)/bin/python -m pytest tests/

lint:
	$(VENV)/bin/ruff check src tests

doctor:
	$(AV) doctor

# Rebuild the golden Crunchyroll fixture with its original scripts.
fixture:
	cd examples/crunchyroll && \
	python3 scripts/01_parse_postings.py && \
	python3 scripts/02_build_value_model.py && \
	python3 scripts/03_validate.py
