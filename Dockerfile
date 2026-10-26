FROM python:3.12-slim

# Prevent Python from creating .pyc files.
ENV PYTHONDONTWRITEBYTECODE=1

# Print Python logs immediately.
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install Python dependencies.
COPY requirements.txt .

RUN pip install --no-cache-dir \
    -r requirements.txt

# Create a non-root application user.
RUN useradd --create-home --uid 10001 appuser

# Copy application source.
COPY --chown=appuser:appuser app/ ./app/

# Run application without root privileges.
USER appuser

EXPOSE 8000

# Start the FastAPI application.
CMD ["uvicorn", "app.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000"]