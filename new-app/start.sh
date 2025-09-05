if [ -f "app.py" ]; then
    log "Found app.py in $(pwd)"
    # Set environment variable to prevent continuous download checks
    export DISABLE_AUTO_MODEL_DOWNLOAD=true
    log "Auto model download is disabled to prevent loops"

    if [ -d "venv" ] && [ -f "venv/bin/python" ]; then
        log "Using virtual environment Python to start application"
        venv/bin/python app.py
    else
        log "Virtual environment Python not found, using system Python"
        python3 app.py
    fi
