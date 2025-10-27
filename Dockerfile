FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    portaudio19-dev \
    libasound-dev \
    libportaudio2 \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Copy project
COPY . .

# Create logs directory
RUN mkdir -p logs

# Collect static files
RUN python manage.py collectstatic --noinput || true

# Expose port (Cloud Run uses PORT env variable, default to 8000 for local)
ENV PORT=8000
EXPOSE $PORT

# Run migrations and start server
CMD sh -c "python manage.py migrate && daphne -b 0.0.0.0 -p ${PORT} voicegen.asgi:application"

