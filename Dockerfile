# Production-ready container for LATTICE · IITH Operations Console
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Initialize demo database
RUN python -m backend.seed_data

# Expose ports for Student (8000), Technician (8001), and Estate Admin (8002)
EXPOSE 8000 8001 8002

# Default execution: run the unified launcher
CMD ["bash", "start.sh"]
