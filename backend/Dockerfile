FROM python:3.12-slim

WORKDIR /workspace

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy pyproject.toml
COPY pyproject.toml .

# Install dependencies
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -e .[dev]

# Copy the rest of the application
COPY . .

# Expose FastAPI port
EXPOSE 8000

# Default command runs uvicorn with reload enabled
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
