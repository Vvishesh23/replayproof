FROM python:3.12-slim
WORKDIR /app
COPY requirements.lock .
RUN pip install --no-cache-dir -r requirements.lock
COPY . .
RUN find replayproof migrations tests scripts -type f -name '*.py' -exec chmod 0644 {} + \
    && pip install --no-cache-dir --no-deps .
CMD ["uvicorn", "replayproof.api:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
