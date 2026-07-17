.PHONY: demo luma-demo report-demo test
PYTHON ?= uv run python

demo:
	$(MAKE) luma-demo
	$(MAKE) report-demo

luma-demo:
	$(PYTHON) -m lumabot_runtime.luma.demo

report-demo:
	$(PYTHON) -m lumabot_runtime.reports.demo

test:
	uv run pytest
