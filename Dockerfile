# Use a lightweight Python base image
FROM python:3.11-slim

# Set working directory inside the container
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the project
COPY . .

# Ensure runtime directories exist
RUN mkdir -p /app/photo-storage \
    && mkdir -p /app/instance/cache/photos \
    && mkdir -p /app/instance/log

# (Optional) set permissions if you run as non-root
# RUN adduser --disabled-password --gecos '' flask \
#     && chown -R flask:flask /app/instance
# USER flask

# Expose Flask/Gunicorn port (default 5000, can be overridden)
EXPOSE 5050

# Default command: run your start script
CMD ["bash", "start.sh"]