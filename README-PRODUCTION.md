# Audio Extraction Analysis - Production Deployment Guide

## Version: 1.0.0+emergency

## Table of Contents
- [System Requirements](#system-requirements)
- [Installation](#installation)
- [Configuration](#configuration)
- [Deployment Options](#deployment-options)
- [Monitoring](#monitoring)
- [Scaling](#scaling)
- [Security](#security)
- [Backup & Recovery](#backup--recovery)
- [Troubleshooting](#troubleshooting)

## System Requirements

### Minimum Requirements
- **CPU**: 4 cores @ 2.4GHz
- **RAM**: 8GB (16GB recommended for Whisper large model)
- **Storage**: 20GB free space (for models and temporary files)
- **OS**: Ubuntu 20.04+, RHEL 8+, macOS 11+, Windows Server 2019+
- **Python**: 3.8+ (3.9+ recommended)
- **FFmpeg**: 4.0+ (required for audio extraction)

### GPU Requirements (for Whisper/Parakeet)
- **NVIDIA GPU**: CUDA 11.8+ compatible
- **VRAM**: 4GB minimum (10GB for large models)
- **Drivers**: NVIDIA Driver 515+

## Installation

### Production Installation

```bash
# 1. System dependencies
# Ubuntu/Debian
sudo apt update && sudo apt install -y ffmpeg python3-pip python3-venv

# RHEL/CentOS
sudo yum install -y ffmpeg python3-pip

# macOS
brew install ffmpeg python@3.9

# 2. Create virtual environment
python3 -m venv venv
source venv/bin/activate

# 3. Install package
# Install uv if not already installed
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install the package
uv pip install audio-extraction-analysis

# 4. Install optional features based on needs
# For TUI interface
uv pip install audio-extraction-analysis[tui]

# For local Whisper processing
uv pip install openai-whisper torch

# For NVIDIA Parakeet models
uv pip install audio-extraction-analysis[parakeet]

# 5. Verify installation
audio-extraction-analysis --version
```

### Docker Deployment

```dockerfile
# Dockerfile
FROM python:3.9-slim

# Install FFmpeg and system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Install uv package manager
RUN curl -LsSf https://astral.sh/uv/install.sh | sh

# Install Python package using uv
RUN /root/.cargo/bin/uv pip install --system --no-cache audio-extraction-analysis

# Create volume for output
VOLUME /output

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV OUTPUT_DIR=/output

# Run command
ENTRYPOINT ["audio-extraction-analysis"]
```

Build and run:
```bash
# Build image
docker build -t audio-extraction:latest .

# Run container
docker run -v $(pwd)/output:/output \
  -e DEEPGRAM_API_KEY=$DEEPGRAM_API_KEY \
  audio-extraction:latest process /input/video.mp4
```

## Configuration

### Environment Variables

Create `.env` file for production:
```bash
# API Keys
DEEPGRAM_API_KEY=your_production_key
ELEVENLABS_API_KEY=your_production_key

# Provider Selection
TRANSCRIPTION_PROVIDER=deepgram  # auto|deepgram|elevenlabs|whisper|parakeet

# Whisper Configuration (if using local processing)
WHISPER_MODEL=medium  # tiny|base|small|medium|large
WHISPER_DEVICE=cuda   # cuda|cpu
WHISPER_COMPUTE_TYPE=float16

# Performance
MAX_WORKERS=4
CHUNK_SIZE=1048576  # 1MB chunks
TEMP_DIR=/var/tmp/audio-extraction

# Logging
LOG_LEVEL=INFO
LOG_FILE=/var/log/audio-extraction/app.log
LOG_MAX_SIZE=10485760  # 10MB
LOG_BACKUP_COUNT=5

# Security
ALLOWED_FILE_EXTENSIONS=.mp4,.mp3,.wav,.m4a,.mov,.avi
MAX_FILE_SIZE=2147483648  # 2GB
SANITIZE_PATHS=true
```

### systemd Service (Linux)

Create `/etc/systemd/system/audio-extraction.service`:
```ini
[Unit]
Description=Audio Extraction Analysis Service
After=network.target

[Service]
Type=simple
User=audioservice
Group=audioservice
WorkingDirectory=/opt/audio-extraction
Environment="PATH=/opt/audio-extraction/venv/bin"
ExecStart=/opt/audio-extraction/venv/bin/python -m src.cli
Restart=always
RestartSec=10

# Security
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/var/lib/audio-extraction /var/log/audio-extraction

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable audio-extraction
sudo systemctl start audio-extraction
```

## Deployment Options

### 1. Standalone Server

```bash
# Install supervisor
uv pip install supervisor

# Create supervisor config
cat > /etc/supervisor/conf.d/audio-extraction.conf << EOF
[program:audio-extraction]
command=/opt/audio-extraction/venv/bin/python -m src.cli
directory=/opt/audio-extraction
user=audioservice
autostart=true
autorestart=true
stderr_logfile=/var/log/audio-extraction/error.log
stdout_logfile=/var/log/audio-extraction/output.log
EOF

# Start supervisor
supervisorctl reread
supervisorctl update
supervisorctl start audio-extraction
```

### 2. Kubernetes Deployment

```yaml
# k8s-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: audio-extraction
spec:
  replicas: 3
  selector:
    matchLabels:
      app: audio-extraction
  template:
    metadata:
      labels:
        app: audio-extraction
    spec:
      containers:
      - name: audio-extraction
        image: audio-extraction:latest
        env:
        - name: DEEPGRAM_API_KEY
          valueFrom:
            secretKeyRef:
              name: audio-secrets
              key: deepgram-key
        resources:
          requests:
            memory: "2Gi"
            cpu: "1"
          limits:
            memory: "4Gi"
            cpu: "2"
        volumeMounts:
        - name: output
          mountPath: /output
      volumes:
      - name: output
        persistentVolumeClaim:
          claimName: audio-output-pvc
```

### 3. AWS Lambda (Serverless)

```python
# lambda_handler.py
import json
from src.pipeline.simple_pipeline import process_pipeline

def lambda_handler(event, context):
    # Download file from S3
    s3_bucket = event['bucket']
    s3_key = event['key']
    
    # Process file
    result = process_pipeline(
        input_file=f"/tmp/{s3_key}",
        output_dir="/tmp/output"
    )
    
    # Upload results to S3
    # ... upload logic ...
    
    return {
        'statusCode': 200,
        'body': json.dumps(result)
    }
```

## Monitoring

### Event Streaming Integration

```python
# monitoring.py
import json
import subprocess
from datetime import datetime

def monitor_pipeline(video_file):
    """Monitor pipeline execution via event streaming."""
    process = subprocess.Popen(
        ['audio-extraction-analysis', 'process', video_file, '--jsonl'],
        stdout=subprocess.PIPE,
        text=True
    )
    
    for line in process.stdout:
        event = json.loads(line)
        
        # Send to monitoring system
        if event['type'] == 'error':
            send_alert(event)
        elif event['type'] == 'stage_end':
            log_metric(event['stage'], event['data']['duration'])
        
        # Log to centralized logging
        logger.info(f"Event: {event['type']} - {event.get('stage', 'N/A')}")
```

### Prometheus Metrics

```python
# metrics.py
from prometheus_client import Counter, Histogram, start_http_server

# Define metrics
processing_counter = Counter('audio_files_processed', 'Total processed files')
processing_duration = Histogram('processing_duration_seconds', 'Processing duration')
error_counter = Counter('processing_errors', 'Total processing errors')

# Start metrics server
start_http_server(8000)
```

### Health Check Endpoint

```python
# health.py
from flask import Flask, jsonify
from src.providers.factory import TranscriptionProviderFactory

app = Flask(__name__)

@app.route('/health')
def health_check():
    """Health check endpoint for load balancers."""
    providers = TranscriptionProviderFactory.get_available_providers()
    health_status = TranscriptionProviderFactory.check_all_provider_health()
    
    return jsonify({
        'status': 'healthy' if providers else 'unhealthy',
        'providers': health_status,
        'timestamp': datetime.utcnow().isoformat()
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
```

## Scaling

### Horizontal Scaling

```yaml
# k8s-hpa.yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: audio-extraction-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: audio-extraction
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
```

### Queue-Based Processing

```python
# queue_processor.py
import redis
from rq import Queue, Worker
from src.pipeline.simple_pipeline import process_pipeline

# Connect to Redis
redis_conn = redis.Redis(host='localhost', port=6379)
queue = Queue(connection=redis_conn)

# Enqueue job
def enqueue_processing(video_file, output_dir):
    job = queue.enqueue(
        process_pipeline,
        video_file,
        output_dir,
        job_timeout='2h'
    )
    return job.id

# Worker process
if __name__ == '__main__':
    worker = Worker([queue], connection=redis_conn)
    worker.work()
```

## Security

### API Key Management

```bash
# Use secrets management service
# AWS Secrets Manager
aws secretsmanager create-secret \
  --name audio-extraction/api-keys \
  --secret-string '{"deepgram":"key","elevenlabs":"key"}'

# Kubernetes Secrets
kubectl create secret generic audio-secrets \
  --from-literal=deepgram-key=$DEEPGRAM_API_KEY \
  --from-literal=elevenlabs-key=$ELEVENLABS_API_KEY
```

### File Upload Security

```python
# secure_upload.py
import os
from werkzeug.utils import secure_filename

ALLOWED_EXTENSIONS = {'.mp4', '.mp3', '.wav', '.m4a'}
MAX_FILE_SIZE = 2 * 1024 * 1024 * 1024  # 2GB

def validate_file(file):
    """Validate uploaded file."""
    filename = secure_filename(file.filename)
    
    # Check extension
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(f"Invalid file type: {ext}")
    
    # Check size
    file.seek(0, os.SEEK_END)
    size = file.tell()
    file.seek(0)
    
    if size > MAX_FILE_SIZE:
        raise ValueError(f"File too large: {size} bytes")
    
    return filename
```

## Backup & Recovery

### Automated Backups

```bash
#!/bin/bash
# backup.sh

# Configuration
BACKUP_DIR="/backup/audio-extraction"
OUTPUT_DIR="/var/lib/audio-extraction/output"
RETENTION_DAYS=30

# Create backup
DATE=$(date +%Y%m%d_%H%M%S)
tar -czf "$BACKUP_DIR/output_$DATE.tar.gz" "$OUTPUT_DIR"

# Upload to S3
aws s3 cp "$BACKUP_DIR/output_$DATE.tar.gz" \
  s3://backup-bucket/audio-extraction/

# Clean old backups
find "$BACKUP_DIR" -name "*.tar.gz" -mtime +$RETENTION_DAYS -delete
```

### Disaster Recovery

```yaml
# dr-plan.yaml
disaster_recovery:
  rpo: 4 hours  # Recovery Point Objective
  rto: 1 hour   # Recovery Time Objective
  
  backup_strategy:
    - type: incremental
      frequency: hourly
      retention: 7 days
    - type: full
      frequency: daily
      retention: 30 days
  
  recovery_steps:
    1. Provision new infrastructure
    2. Restore configuration from backup
    3. Restore data from S3/backup
    4. Validate provider connectivity
    5. Run smoke tests
```

## Troubleshooting

### Common Production Issues

#### High Memory Usage
```bash
# Monitor memory
watch -n 1 'ps aux | grep audio-extraction'

# Limit memory usage
ulimit -v 4194304  # 4GB limit

# Configure swap
sudo fallocate -l 4G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
```

#### API Rate Limiting
```python
# rate_limiter.py
from functools import wraps
import time

def rate_limit(calls_per_second=1):
    min_interval = 1.0 / calls_per_second
    last_called = [0.0]
    
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            elapsed = time.time() - last_called[0]
            left_to_wait = min_interval - elapsed
            if left_to_wait > 0:
                time.sleep(left_to_wait)
            ret = func(*args, **kwargs)
            last_called[0] = time.time()
            return ret
        return wrapper
    return decorator
```

#### Debugging Production Issues
```bash
# Enable debug logging
export LOG_LEVEL=DEBUG
export PYTHONFAULTHANDLER=1

# Profile performance
python -m cProfile -o profile.stats src/cli.py process video.mp4

# Analyze profile
python -m pstats profile.stats

# Monitor with strace
strace -f -e trace=file audio-extraction-analysis process video.mp4
```

### Performance Tuning

```bash
# CPU optimization
export OMP_NUM_THREADS=4
export MKL_NUM_THREADS=4

# GPU optimization (for Whisper/Parakeet)
export CUDA_VISIBLE_DEVICES=0,1
export TF_FORCE_GPU_ALLOW_GROWTH=true

# Memory optimization
export MALLOC_TRIM_THRESHOLD_=100000
export MALLOC_MMAP_THRESHOLD_=100000
```

## Support

- **Documentation**: See `/docs` directory
- **Issues**: Report via GitHub Issues
- **Monitoring Dashboard**: Configure based on your monitoring stack
- **Logs**: Check `/var/log/audio-extraction/`

---

*Last Updated: November 2024*
*Version: 1.0.0+emergency*
