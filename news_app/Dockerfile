
# Use Python base image
FROM python:3.14-slim

# Set working directory
WORKDIR /app

# Prevent Python from generating bytecode
ENV PYTHONDONTWRITEBYTECODE=1

# Display Python output immediately
ENV PYTHONUNBUFFERED=1

# Install MariaDB/MySQL client build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    pkg-config \
    default-libmysqlclient-dev \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Create directory for SQLite database
RUN mkdir -p /app/data /app/staticfiles /app/media

# Expose Django application port
EXPOSE 8000

# Start Django using Gunicorn
CMD ["gunicorn", "news_app.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "1"]
