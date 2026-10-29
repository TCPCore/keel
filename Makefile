PY ?= $(shell if [ -x .venv/bin/python ]; then echo .venv/bin/python; else echo python3; fi)

.PHONY: help install demo test lint audit hook clean

help:
	@echo "make install   install the package in editable mode"
	@echo "make demo      run the synthetic scan and write examples/"
	@echo "make test      run the test suite"
	@echo "make lint      ruff"
	@echo "make audit     test + lint + the diff a reviewer needs to read"
	@echo "make hook      enable the pre-push audit gate for this clone"
	@echo "make clean     remove caches and generated cards"

install:
	$(PY) -m pip install -e ".[dev]"

demo:
	PYTHONPATH=src $(PY) -m keel.cli demo --out examples

test:
	PYTHONPATH=src $(PY) -m pytest

lint:
	$(PY) -m ruff check src tests scripts space

audit: test lint
	@echo ""
	@echo "--- changes on this branch ---"
	@git diff --stat main...HEAD 2>/dev/null || git status --short
	@echo ""
	@echo "Read the diff against muse/NN-*.md, then sign audit/NN-*.md."
	@echo "Commit with: git commit --trailer 'Audited-by: <name>'"

hook:
	git config core.hooksPath .githooks
	@echo "audit gate enabled for this clone"

clean:
	rm -rf .pytest_cache .ruff_cache build dist *.egg-info
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
