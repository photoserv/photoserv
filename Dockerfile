# Stage 1: Base build stage
FROM python:3.14-slim AS builder

# Install build tools and Node.js for frontend
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
        build-essential \
        git \
        nodejs \
        npm \
    && rm -rf /var/lib/apt/lists/*

# Create app directory
RUN mkdir /app
WORKDIR /app

# Python env
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Upgrade pip and install dependencies
RUN pip install --upgrade pip
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy frontend code and run builds
COPY . .
RUN npm install
RUN npm run build:all

RUN python manage.py collectstatic

# Stage 2: Production stage
FROM python:3.14-slim AS runner

# Install supervisord
RUN apt-get update && apt-get install -y --no-install-recommends \
        supervisor nginx exiftool \
    && rm -rf /var/lib/apt/lists/*

# Create volumes and app dir
RUN useradd -m -r photoserv -u 1000 \
    && mkdir /app /database /content /plugins \
    && chown -R photoserv:photoserv /app /database /content /etc/supervisor/conf.d

# Nginx
RUN mkdir -p /var/run/nginx /var/log/nginx /var/lib/nginx/body \
    && chown -R photoserv:photoserv /var/run/nginx /var/log/nginx /var/lib/nginx

# Copy Python deps and frontend assets
COPY --from=builder /usr/local/lib/python3.14/site-packages/ /usr/local/lib/python3.14/site-packages/
COPY --from=builder /usr/local/bin/ /usr/local/bin/
COPY --from=builder /app/staticfiles /var/www/static
COPY --from=builder /app/package*.json /app/

# Set working dir and copy app code
WORKDIR /app
COPY --chown=photoserv:photoserv . .

# Supervisor config
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Nginx config
COPY nginx.conf /etc/nginx/nginx.conf

# Entrypoint
COPY entrypoint.sh .
RUN chmod +x /app/entrypoint.sh

# Env
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PHOTOSERV_IS_CONTAINER=true

# Switch to non-root user
USER photoserv

# Expose port
EXPOSE 8000

# Start supervisord
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
