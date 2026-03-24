FROM python:3.12-slim

WORKDIR /app

# Install dependencies first (cached layer)
COPY pyproject.toml ./
RUN pip install --no-cache-dir .

# Copy application code
COPY garmin_tracker/ garmin_tracker/
COPY templates/ templates/
COPY static/ static/

# Create data directory for SQLite
RUN mkdir -p /data

ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["uvicorn", "garmin_tracker.app:app", "--host", "0.0.0.0", "--port", "8000"]
