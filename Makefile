PYTHON ?= python3
COMPOSE ?= docker compose

.PHONY: integration-test security-check infra-check demo-up demo-seed demo-run demo-logs demo-down

integration-test: security-check infra-check
	PYTHONPATH=. $(PYTHON) -m unittest discover -s integration_tests -p 'test_*.py'

security-check:
	PYTHONPATH=. $(PYTHON) scripts/security_check.py

infra-check:
	PYTHONPATH=. $(PYTHON) scripts/validate_infra.py

demo-up:
	$(COMPOSE) up -d

demo-seed:
	PYTHONPATH=. $(PYTHON) scripts/demo_seed.py

demo-run:
	PYTHONPATH=. $(PYTHON) scripts/run_fixture_workflow.py

demo-logs:
	$(COMPOSE) logs --tail=200

demo-down:
	$(COMPOSE) down --remove-orphans
