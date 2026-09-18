# wse-model developer entry points.
#
# `make check` is the repository gate. It intentionally avoids any dependency on
# the pyCircuit checkout so that the semantic core can always be validated.

PYTHON ?= python3
PYTEST ?= $(PYTHON) -m pytest
PYCIRCUIT_ROOT ?= ../pyCircuit

.DEFAULT_GOAL := help

.PHONY: help
help: ## Show this help
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) \
		| sort \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

.PHONY: install
install: ## Install the package in editable mode
	$(PYTHON) -m pip install -e .

.PHONY: dev
dev: ## Install with development extras
	$(PYTHON) -m pip install -e ".[dev]"

.PHONY: bootstrap
bootstrap: ## Install the package plus the pyCircuit agentic-circuit frontend
	PYCIRCUIT_ROOT=$(PYCIRCUIT_ROOT) bash tools/bootstrap-dev.sh

.PHONY: test
test: ## Run the full test suite
	$(PYTEST)

.PHONY: unit
unit: ## Run the fast pure-Python unit tests
	$(PYTEST) tests/unit -m unit

.PHONY: contract
contract: ## Run interface and schema contract tests
	$(PYTEST) tests/contracts -m contract

.PHONY: integration
integration: ## Run end-to-end model scenarios
	$(PYTEST) tests/integration

.PHONY: acir-tools
acir-tools: ## Build the native ACIR tools from a pyCircuit checkout
	bash tools/build-acir-tools.sh $(PYCIRCUIT_ROOT)

.PHONY: acir
acir: ## Run the ACIR model-layer tests (requires the native ACIR tools)
	@if [ -z "$$ACIR_OPT" ]; then \
		echo "ACIR_OPT is not set. Build the tools first:"; \
		echo "  bash tools/build-acir-tools.sh $${PYCIRCUIT_ROOT:-../pyCircuit}"; \
		exit 1; \
	fi
	$(PYTEST) tests/acir -m acir

.PHONY: coverage
coverage: ## Run tests with a coverage report
	$(PYTEST) --cov=wse_model --cov-report=term-missing --cov-report=xml

.PHONY: lint
lint: ## Run the linter
	$(PYTHON) -m ruff check .

.PHONY: format
format: ## Apply formatting and safe lint fixes
	$(PYTHON) -m ruff check --fix .
	$(PYTHON) -m ruff format .

.PHONY: typecheck
typecheck: ## Run the type checker when mypy is available
	$(PYTHON) -m mypy src/wse_model

.PHONY: docs
docs: ## Build the documentation site
	$(PYTHON) -m mkdocs build --strict

.PHONY: docs-serve
docs-serve: ## Serve the documentation site locally
	$(PYTHON) -m mkdocs serve

.PHONY: check
check: lint unit contract ## Run the repository gate (lint + unit + contract)
	@echo "wse-model gate passed"

.PHONY: pre-commit
pre-commit: ## Run all pre-commit hooks
	pre-commit run --all-files

.PHONY: clean
clean: ## Remove generated artifacts
	rm -rf build dist .pytest_cache .ruff_cache .mypy_cache htmlcov .coverage coverage.xml
	find . -name '__pycache__' -type d -prune -exec rm -rf {} +
	rm -rf site .wse_model_out
