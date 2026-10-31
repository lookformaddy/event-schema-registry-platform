.PHONY: test demo serve

test:
	PYTHONPATH=src python3 -m pytest -q

demo:
	PYTHONPATH=src python3 -m schema_registry.cli demo

serve:
	PYTHONPATH=src python3 -m uvicorn schema_registry.api:app --port 8000
