# Deployment Guide

This guide covers deploying the Epstein Documents Browser in various environments, from local development to production clusters.

## Table of Contents

- [Quick Start](#quick-start)
- [Local Development](#local-development)
- [Production Deployment](#production-deployment)
- [Docker Deployment](#docker-deployment)
- [Cloud Deployment](#cloud-deployment)
- [Scaling Strategies](#scaling-strategies)
- [Monitoring & Logging](#monitoring--logging)
- [Security Considerations](#security-considerations)
- [Troubleshooting](#troubleshooting)

## Quick Start

### Prerequisites

- Python 3.8+
- 4GB+ RAM
- 100GB+ storage (for full document collection)
- Git

### Basic Setup

```bash
# Clone the repository
git clone https://github.com/actuallyrizzn/epstein-browser.git
cd epstein-browser

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up environment
cp .env.example .env
# Edit .env with your configuration

# Start the application
python app.py
```

## Local Development

### Development Environment

```bash
# Install development dependencies
pip install -r requirements-dev.txt

# Run tests
pytest

# Run with debug mode
export FLASK_ENV=development
python app.py
```

### Development Features

- **Hot reload**: Automatic restart on code changes
- **Debug mode**: Detailed error messages
- **Test database**: Isolated testing environment
- **Mock data**: Realistic test datasets

## Production Deployment

### System Requirements

**Minimum:**
- CPU: 2 cores
- RAM: 4GB
- Storage: 100GB SSD
- Network: 100 Mbps

**Recommended:**
- CPU: 4+ cores
- RAM: 8GB+
- Storage: 500GB+ SSD
- Network: 1 Gbps

### Production Setup

#### 1. Server Preparation

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Python and dependencies
sudo apt install python3 python3-pip python3-venv nginx

# Create application user
sudo useradd -m -s /bin/bash epstein-browser
sudo su - epstein-browser
```

#### 2. Application Deployment

```bash
# Clone repository
git clone https://github.com/actuallyrizzn/epstein-browser.git
cd epstein-browser

# Set up virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Set up environment
cp .env.example .env
nano .env  # Configure for production
```

#### 3. Environment Configuration

```bash
# .env for production
FLASK_ENV=production
SECRET_KEY=your-secret-key-here
DATABASE_PATH=/home/epstein-browser/images.db
DATA_DIR=/home/epstein-browser/data
HOST=127.0.0.1
PORT=5000
DEBUG=False
TESTING=False
LOG_LEVEL=INFO
```

#### 4. Process Management

```bash
# Install systemd service
sudo nano /etc/systemd/system/epstein-browser.service
```

```ini
[Unit]
Description=Epstein Documents Browser
After=network.target

[Service]
Type=simple
User=epstein-browser
WorkingDirectory=/home/epstein-browser/epstein-browser
Environment=PATH=/home/epstein-browser/epstein-browser/venv/bin
ExecStart=/home/epstein-browser/epstein-browser/venv/bin/python app.py
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
# Enable and start service
sudo systemctl daemon-reload
sudo systemctl enable epstein-browser
sudo systemctl start epstein-browser
```

#### 5. Nginx Configuration

```bash
# Create Nginx configuration
sudo nano /etc/nginx/sites-available/epstein-browser
```

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Static files
    location /static {
        alias /home/epstein-browser/epstein-browser/static;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # Images
    location /data {
        alias /home/epstein-browser/data;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}
```

```bash
# Enable site
sudo ln -s /etc/nginx/sites-available/epstein-browser /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

## Docker Deployment

### Dockerfile

```dockerfile
FROM python:3.9-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create data directory
RUN mkdir -p /app/data

# Expose port
EXPOSE 5000

# Set environment variables
ENV FLASK_APP=app.py
ENV FLASK_ENV=production

# Run application
CMD ["python", "app.py"]
```

### Docker Compose

```yaml
version: '3.8'

services:
  epstein-browser:
    build: .
    ports:
      - "5000:5000"
    volumes:
      - ./data:/app/data
      - ./images.db:/app/images.db
    environment:
      - FLASK_ENV=production
      - SECRET_KEY=your-secret-key
    restart: unless-stopped

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - ./data:/var/www/data
    depends_on:
      - epstein-browser
    restart: unless-stopped
```

### Docker Commands

```bash
# Build image
docker build -t epstein-browser .

# Run container
docker run -d \
  --name epstein-browser \
  -p 5000:5000 \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/images.db:/app/images.db \
  epstein-browser

# Using Docker Compose
docker-compose up -d
```

## Cloud Deployment

### AWS Deployment

#### EC2 Instance

```bash
# Launch EC2 instance (t3.medium or larger)
# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Clone and run
git clone https://github.com/actuallyrizzn/epstein-browser.git
cd epstein-browser
docker-compose up -d
```

#### ECS Deployment

```yaml
# task-definition.json
{
  "family": "epstein-browser",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "512",
  "memory": "1024",
  "executionRoleArn": "arn:aws:iam::account:role/ecsTaskExecutionRole",
  "containerDefinitions": [
    {
      "name": "epstein-browser",
      "image": "your-account.dkr.ecr.region.amazonaws.com/epstein-browser:latest",
      "portMappings": [
        {
          "containerPort": 5000,
          "protocol": "tcp"
        }
      ],
      "environment": [
        {
          "name": "FLASK_ENV",
          "value": "production"
        }
      ]
    }
  ]
}
```

### Google Cloud Platform

#### Cloud Run

```yaml
# cloudbuild.yaml
steps:
  - name: 'gcr.io/cloud-builders/docker'
    args: ['build', '-t', 'gcr.io/$PROJECT_ID/epstein-browser', '.']
  - name: 'gcr.io/cloud-builders/docker'
    args: ['push', 'gcr.io/$PROJECT_ID/epstein-browser']
  - name: 'gcr.io/cloud-builders/gcloud'
    args: ['run', 'deploy', 'epstein-browser', '--image', 'gcr.io/$PROJECT_ID/epstein-browser', '--platform', 'managed', '--region', 'us-central1']
```

### Azure Deployment

#### Container Instances

```bash
# Create resource group
az group create --name epstein-browser-rg --location eastus

# Deploy container
az container create \
  --resource-group epstein-browser-rg \
  --name epstein-browser \
  --image your-registry.azurecr.io/epstein-browser:latest \
  --dns-name-label epstein-browser \
  --ports 5000
```

## Scaling Strategies

### Horizontal Scaling

#### Load Balancer Configuration

```nginx
upstream epstein_browser {
    server 127.0.0.1:5000;
    server 127.0.0.1:5001;
    server 127.0.0.1:5002;
}

server {
    listen 80;
    location / {
        proxy_pass http://epstein_browser;
    }
}
```

#### Multiple Instances

```bash
# Start multiple instances
python app.py --port 5000 &
python app.py --port 5001 &
python app.py --port 5002 &
```

### Database Scaling

#### PostgreSQL Migration

```python
# config.py
import os

DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///images.db')

if DATABASE_URL.startswith('postgresql'):
    # Use PostgreSQL for production
    SQLALCHEMY_DATABASE_URI = DATABASE_URL
else:
    # Use SQLite for development
    SQLALCHEMY_DATABASE_URI = DATABASE_URL
```

#### Redis Caching

```python
# Add Redis for caching
import redis

redis_client = redis.Redis(host='localhost', port=6379, db=0)

def cache_search_results(query, results):
    redis_client.setex(f"search:{query}", 3600, json.dumps(results))
```

## Monitoring & Logging

### Application Monitoring

#### Health Checks

```python
# health.py
from flask import Flask, jsonify
import psutil
import os

def health_check():
    return {
        'status': 'healthy',
        'memory_usage': psutil.virtual_memory().percent,
        'disk_usage': psutil.disk_usage('/').percent,
        'database_size': os.path.getsize('images.db') if os.path.exists('images.db') else 0
    }
```

#### Logging Configuration

```python
# logging_config.py
import logging
from logging.handlers import RotatingFileHandler

def setup_logging(app):
    if not app.debug:
        file_handler = RotatingFileHandler('logs/epstein-browser.log', maxBytes=10240, backupCount=10)
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        ))
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)
        app.logger.setLevel(logging.INFO)
        app.logger.info('Epstein Browser startup')
```

### System Monitoring

#### Prometheus Metrics

```python
# metrics.py
from prometheus_client import Counter, Histogram, generate_latest

REQUEST_COUNT = Counter('http_requests_total', 'Total HTTP requests', ['method', 'endpoint'])
REQUEST_DURATION = Histogram('http_request_duration_seconds', 'HTTP request duration')

@app.route('/metrics')
def metrics():
    return generate_latest()
```

#### Grafana Dashboard

```json
{
  "dashboard": {
    "title": "Epstein Browser Metrics",
    "panels": [
      {
        "title": "Request Rate",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(http_requests_total[5m])"
          }
        ]
      }
    ]
  }
}
```

## Security Considerations

### Authentication & Authorization

#### Basic Authentication

```python
# auth.py
from functools import wraps
from flask import request, Response

def check_auth(username, password):
    return username == 'admin' and password == 'secret'

def authenticate():
    return Response('Authentication required', 401, {'WWW-Authenticate': 'Basic realm="Login Required"'})

def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()
        return f(*args, **kwargs)
    return decorated
```

#### API Rate Limiting

```python
# rate_limiting.py
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter = Limiter(
    app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"]
)

@app.route('/api/search')
@limiter.limit("10 per minute")
def search():
    # Search implementation
    pass
```

### Data Protection

#### Encryption at Rest

```python
# encryption.py
from cryptography.fernet import Fernet

def encrypt_file(file_path, key):
    with open(file_path, 'rb') as f:
        data = f.read()
    
    fernet = Fernet(key)
    encrypted_data = fernet.encrypt(data)
    
    with open(file_path + '.encrypted', 'wb') as f:
        f.write(encrypted_data)
```

#### HTTPS Configuration

```nginx
# nginx-ssl.conf
server {
    listen 443 ssl;
    server_name your-domain.com;
    
    ssl_certificate /path/to/certificate.crt;
    ssl_certificate_key /path/to/private.key;
    
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header X-Forwarded-Proto https;
    }
}
```

## Troubleshooting

### Common Issues

#### Database Lock Errors

```bash
# Check for database locks
sqlite3 images.db "PRAGMA busy_timeout=30000;"

# Rebuild database if corrupted
rm images.db
python index_images.py
```

#### Memory Issues

```bash
# Monitor memory usage
htop
ps aux | grep python

# Increase swap if needed
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
```

#### OCR Processing Issues

```bash
# Check OCR dependencies
python -c "import easyocr; print('EasyOCR OK')"
python -c "import pytesseract; print('Tesseract OK')"

# Test OCR on sample image
python -c "
from ocr_processor import process_image
result = process_image('test_image.jpg')
print(result)
"
```

### Performance Optimization

#### Database Optimization

```sql
-- Add indexes for better performance
CREATE INDEX idx_images_path ON images(file_path);
CREATE INDEX idx_images_has_ocr ON images(has_ocr_text);
CREATE INDEX idx_images_ocr_text ON images(ocr_text);
```

#### Caching Strategy

```python
# cache.py
from functools import lru_cache
import redis

redis_client = redis.Redis(host='localhost', port=6379, db=0)

@lru_cache(maxsize=1000)
def get_image_metadata(image_id):
    # Expensive database query
    pass

def cache_search_results(query, results):
    redis_client.setex(f"search:{query}", 3600, json.dumps(results))
```

### Backup & Recovery

#### Database Backup

```bash
# Create backup
sqlite3 images.db ".backup backup_$(date +%Y%m%d).db"

# Restore from backup
sqlite3 images.db ".restore backup_20250908.db"
```

#### File System Backup

```bash
# Backup data directory
tar -czf data_backup_$(date +%Y%m%d).tar.gz data/

# Restore data
tar -xzf data_backup_20250908.tar.gz
```

## Support

### Getting Help

- **GitHub Issues**: Bug reports and feature requests
- **Documentation**: Comprehensive guides and API docs
- **Community Forum**: User discussions and tips
- **Professional Support**: Available for enterprise deployments

### Contributing

- **Code contributions**: Pull requests welcome
- **Documentation**: Help improve guides and tutorials
- **Testing**: Report bugs and edge cases
- **Feature requests**: Suggest new capabilities

---

*This deployment guide covers various deployment scenarios for the Epstein Documents Browser. Choose the approach that best fits your needs and infrastructure.*
