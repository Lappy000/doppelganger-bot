FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY doppelganger/ ./doppelganger/

# Create data directory
RUN mkdir -p /app/data/profiles

# Run as non-root
RUN useradd -m botuser && chown -R botuser:botuser /app
USER botuser

CMD ["python", "-m", "doppelganger.bot"]
