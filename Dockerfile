# Use a lightweight Python base image
FROM python:3.11-slim

# Set working directory inside the container
WORKDIR /app

# Install OS packages
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the project
COPY . .

# Copy entrypoint script
COPY entrypoint.sh /app/entrypoint.sh

# Make entrypoint script executable
RUN chmod +x /app/entrypoint.sh

# (Optional) set permissions if you run as non-root
# RUN adduser --disabled-password --gecos '' flask \
#     && chown -R flask:flask /app/entrypoint.sh
# USER flask

RUN mkdir -p /photos /cache /logs /cache/photos /etc/photomatic

# Expose Flask port
EXPOSE 80

# Set entrypoint to the startup script
ENTRYPOINT ["/app/entrypoint.sh"]
