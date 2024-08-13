.PHONY: start_dev
start_dev:
	uvicorn main:app --reload --port 8080 --host 192.168.3.6
.PHONY: start stop format

PID_FILE := uvicorn.pid

start:
	@echo "Starting Uvicorn..."
	@nohup uvicorn main:app --reload --port 8080 > uvicorn.log 2>&1 & echo $$! > $(PID_FILE)
	@echo "Uvicorn started with PID: $$(cat $(PID_FILE))"

stop:
	@echo "Stopping Uvicorn..."
	@if [ -f $(PID_FILE) ]; then \
	    kill $$(cat $(PID_FILE)) && rm $(PID_FILE); \
	    echo "Uvicorn stopped."; \
	else \
	    echo "No PID file found. Is Uvicorn running?"; \
	fi
.PHONY: format
format:
	black .
	isort .