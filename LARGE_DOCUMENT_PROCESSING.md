# Large Document Processing with Redis Queue System

## 🚀 Overview

This system is optimized to process **500+ page documents** efficiently using Redis queues, Celery workers, and parallel batch processing.

## 📊 Performance Specifications

- **Processing Strategy**: Batch parallel processing for documents >50 pages
- **Batch Size**: 25 pages per batch for optimal performance
- **Parallel Workers**: Up to 6 concurrent page analysis workers
- **Estimated Speed**: ~5 minutes per 500 pages (with optimal configuration)
- **Maximum Document Size**: No hard limit (tested up to 1000+ pages)

## 🏗️ Architecture

```
Frontend Upload → Next.js API → Document Microservice → Images Storage
                                        ↓
Redis Queue ← AI Processing Microservice ← Base64 Images
    ↓
Celery Workers (Multiple Queues):
├── Page Processing Workers (6x) - Analyze individual pages
├── Batch Processing Workers (2x) - Coordinate batches  
├── Document Orchestration (2x) - Manage overall flow
└── Audio Generation Workers (2x) - Generate TTS
```

## 🔧 Configuration

### Environment Variables

```bash
# Redis Configuration
REDIS_URL=redis://your-redis-instance:port/0

# Worker Configuration
CELERY_CONCURRENCY=4
CELERY_QUEUES=default,page_processing,document_orchestration,batch_processing,audio_generation
CELERY_LOG_LEVEL=info

# Autoscaling (optional)
CELERY_AUTOSCALE=true
CELERY_AUTOSCALE_MAX=8
CELERY_AUTOSCALE_MIN=2

# AI Processing
OPENAI_API_KEY=your_openai_key
```

### Render Deployment

The system deploys multiple worker types on Render:

1. **Web Service**: Flask API endpoints
2. **General Worker**: Handles all queue types
3. **Page Workers** (6x): Dedicated to page processing
4. **Audio Workers** (2x): Dedicated to audio generation
5. **Orchestrator** (2x): Manages document workflow

## 📡 API Endpoints

### Large Document Processing
```bash
POST /process-large-document
{
  "job_id": "uuid",
  "user_id": "uuid", 
  "images_base64": ["base64_1", "base64_2", ...],
  "num_pages": 500,
  "file_type": "PDF"
}
```

**Response:**
```json
{
  "status": "queued",
  "processing_strategy": "batch_parallel",
  "batch_size": 25,
  "estimated_batches": 20,
  "estimated_completion_minutes": 42,
  "status_endpoint": "/batch-status/{job_id}",
  "cancel_endpoint": "/cancel-job/{job_id}"
}
```

### Batch Status Monitoring
```bash
GET /batch-status/{job_id}
```

**Response:**
```json
{
  "job_id": "uuid",
  "status": "processing",
  "progress": 65,
  "current_page": 325,
  "total_pages": 500,
  "batches": {
    "total": 20,
    "completed": 13,
    "active": 2,
    "failed": 0
  },
  "estimated_seconds_remaining": 630,
  "estimated_completion_iso": "2024-01-15T14:30:00"
}
```

### System Statistics
```bash
GET /batch-stats
```

### Cancel Processing
```bash
POST /cancel-job/{job_id}
```

## ⚡ Processing Flow for 500+ Page Documents

1. **Upload**: Document uploaded to Next.js API
2. **Conversion**: Document converted to images by unified microservice
3. **Storage**: Images stored in Supabase Storage
4. **Detection**: System detects large document (>50 pages)
5. **Batching**: Document split into 25-page batches
6. **Queue**: Batches queued in Redis with high priority
7. **Parallel Processing**: Multiple workers process batches simultaneously
8. **Progress Tracking**: Real-time progress updates via WebSocket/polling
9. **Aggregation**: Results collected and combined in order
10. **Summary**: Final summary generated from all analyses
11. **Storage**: Complete analysis stored in database
12. **Notification**: User notified of completion

## 🔍 Monitoring

### CLI Monitoring
```bash
# System statistics
python batch_monitor.py stats

# Job progress  
python batch_monitor.py job <job_id>

# Cancel job
python batch_monitor.py cancel <job_id>
```

### Worker Health
```bash
# Check worker status
GET /health

# Worker statistics by queue
GET /batch-stats
```

## 🎯 Performance Optimization Tips

### For 500+ Page Documents:

1. **Scale Workers**: Increase page processing workers to 6-8
2. **Redis Memory**: Ensure adequate Redis memory (2GB+ recommended)
3. **OpenAI Rate Limits**: Monitor API usage and implement backoff
4. **Network**: Stable connection for consistent throughput
5. **Memory Management**: Workers restart every 100 tasks to prevent leaks

### Batch Size Tuning:
- **25 pages**: Optimal for most documents
- **Smaller batches (15-20)**: For very complex pages
- **Larger batches (30-35)**: For simple text-heavy documents

## 🔧 Troubleshooting

### Common Issues:

1. **Worker Timeouts**: Increase `task_time_limit` in celery_config.py
2. **Memory Issues**: Reduce `worker_max_tasks_per_child` 
3. **Redis Connection**: Check `REDIS_URL` and connection limits
4. **OpenAI Rate Limits**: Implement exponential backoff
5. **Stuck Jobs**: Use cancel endpoint to clear stuck tasks

### Debug Commands:
```bash
# View active workers
celery -A celery_config.celery_app inspect active

# View task routes
celery -A celery_config.celery_app inspect registered

# Purge queue
celery -A celery_config.celery_app purge -Q page_processing
```

## 📈 Scaling Guidelines

### For Higher Volume:

1. **Horizontal Scaling**: Add more worker instances
2. **Queue Separation**: Dedicated Redis instances per queue type  
3. **Database Optimization**: Index job status queries
4. **CDN**: Use CDN for image storage and retrieval
5. **Load Balancing**: Multiple API instances behind load balancer

This system is designed to handle enterprise-scale document processing with reliability and performance for documents ranging from single pages to 1000+ page books.
