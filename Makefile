.PHONY: start
start:
	uvicorn main:app --reload --port 8080 --host 192.168.3.6

.PHONY: format
format:
	black .
	isort .