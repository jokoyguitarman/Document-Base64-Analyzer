# Testing Guide - Celery System

This guide helps you test that all components of the Celery background processing system work together properly.

## 🧪 Test Components

### 1. Health Check
- **Endpoint**: `GET /health`
- **Purpose**: Verify Flask app and Celery worker are running
- **Expected**: Returns worker status and registered tasks

### 2. Document Processing
- **Endpoint**: `POST /process-document`
- **Purpose**: Submit document for background processing
- **Expected**: Returns immediately with `task_id`

### 3. Task Status Monitoring
- **Endpoint**: `GET /task-status/<task_id>`
- **Purpose**: Track progress and get results
- **Expected**: Real-time progress updates, final results

### 4. Fallback Text Processing
- **Endpoint**: `POST /process-document` (with fallback_text)
- **Purpose**: Test immediate text processing
- **Expected**: Returns results immediately

## 🚀 Quick Test

### Local Testing
1. **Start Redis**:
   ```bash
   redis-server
   ```

2. **Start Celery Worker** (Terminal 1):
   ```bash
   python worker.py
   ```

3. **Start Flask App** (Terminal 2):
   ```bash
   python main.py
   ```

4. **Run Test Script** (Terminal 3):
   ```bash
   python test_celery_system.py
   ```

### Production Testing
1. **Update BASE_URL** in `test_celery_system.py`:
   ```python
   BASE_URL = "https://your-deployed-url.onrender.com"
   ```

2. **Run Test Script**:
   ```bash
   python test_celery_system.py
   ```

## 📋 Manual Testing

### Test 1: Health Check
```bash
curl http://localhost:10000/health
```

**Expected Response**:
```json
{
  "status": "healthy",
  "service": "ai-processing-microservice",
  "processing": "celery-background",
  "celery_workers": 1,
  "registered_tasks": 2
}
```

### Test 2: Submit Document
```bash
curl -X POST http://localhost:10000/process-document \
  -H "Content-Type: application/json" \
  -d '{
    "job_id": "test_123",
    "user_id": "user_456",
    "images_base64": ["base64_encoded_image_data"],
    "num_pages": 1,
    "file_type": "PDF"
  }'
```

**Expected Response**:
```json
{
  "status": "queued",
  "message": "Document processing job queued successfully",
  "job_id": "test_123",
  "task_id": "abc123-def456-ghi789",
  "user_id": "user_456",
  "num_pages": 1,
  "file_type": "PDF",
  "status_endpoint": "/job-status/test_123",
  "task_endpoint": "/task-status/abc123-def456-ghi789"
}
```

### Test 3: Check Task Status
```bash
curl http://localhost:10000/task-status/abc123-def456-ghi789
```

**Expected Response (Progress)**:
```json
{
  "task_id": "abc123-def456-ghi789",
  "state": "PROGRESS",
  "status": "Analyzing page 1/1",
  "current": 1,
  "total": 1,
  "progress": 100
}
```

**Expected Response (Complete)**:
```json
{
  "task_id": "abc123-def456-ghi789",
  "state": "SUCCESS",
  "status": "completed",
  "result": {
    "status": "completed",
    "result": {
      "content": "Page analysis...",
      "summary": "Brief summary...",
      "elevator_pitch": "Key insights..."
    },
    "processing_time": 45.2,
    "pages_processed": 1
  }
}
```

## 🔍 Troubleshooting

### Common Issues

1. **Redis Connection Error**:
   - Ensure Redis is running: `redis-server`
   - Check REDIS_URL environment variable

2. **Celery Worker Not Starting**:
   - Check for import errors in tasks.py
   - Verify celery_config.py is correct

3. **Tasks Not Processing**:
   - Check worker logs for errors
   - Verify task registration

4. **Timeout Issues**:
   - Increase task_time_limit in celery_config.py
   - Check OpenAI API rate limits

### Debug Commands

```bash
# Check Redis connection
redis-cli ping

# Check Celery worker status
celery -A celery_config inspect active

# Check registered tasks
celery -A celery_config inspect registered

# Monitor task queue
celery -A celery_config monitor
```

## ✅ Success Criteria

All tests pass when:
- ✅ Health check returns worker status
- ✅ Document submission returns task_id immediately
- ✅ Task status shows progress updates
- ✅ Final results are returned successfully
- ✅ Fallback text processing works immediately

## 🎯 Performance Expectations

- **Response Time**: < 2 seconds for task submission
- **Progress Updates**: Every 10-30 seconds
- **Processing Time**: 30-90 seconds per page (depending on content)
- **Reliability**: 99%+ success rate with proper error handling 