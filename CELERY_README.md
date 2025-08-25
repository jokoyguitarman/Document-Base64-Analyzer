# Celery Background Processing Setup

This microservice now uses Celery for robust background task processing.

## Architecture

- **Web Service**: Flask app that receives requests and queues tasks
- **Celery Worker**: Background process that executes document analysis tasks
- **Redis**: Message broker and result backend for Celery

## Files Structure

```
ai-processing-microservice/
├── main.py              # Flask web service
├── celery_config.py     # Celery configuration
├── tasks.py            # Celery tasks (document processing)
├── worker.py           # Celery worker startup script
├── requirements.txt    # Dependencies including Celery & Redis
└── Procfile           # Process definitions for deployment
```

## API Endpoints

### Submit Document for Processing
```
POST /process-document
```
Returns immediately with task_id for tracking.

### Check Task Status
```
GET /task-status/<task_id>
```
Returns real-time progress and results.

### Health Check
```
GET /health
```
Shows Celery worker status and registered tasks.

## Task States

- **PENDING**: Task is queued but not yet started
- **PROGRESS**: Task is running with progress updates
- **SUCCESS**: Task completed successfully with results
- **FAILURE**: Task failed with error details

## Local Development

1. **Install Redis** (if not already installed):
   ```bash
   # macOS
   brew install redis
   brew services start redis
   
   # Ubuntu
   sudo apt-get install redis-server
   sudo systemctl start redis
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Start Redis** (if not running as service):
   ```bash
   redis-server
   ```

4. **Start Celery worker** (in separate terminal):
   ```bash
   python worker.py
   ```

5. **Start Flask app** (in another terminal):
   ```bash
   python main.py
   ```

## Deployment (Render)

The Procfile automatically starts both processes:
- `web`: Flask application
- `worker`: Celery worker

## Environment Variables

### Required Variables

**Both the microservice and Celery worker need these environment variables:**

- `REDIS_URL`: Redis connection string
  - Local development: `redis://localhost:6379/0`
  - Production: `redis://your-redis-instance-url:port`
- `OPENAI_API_KEY`: Your OpenAI API key

### Setting Environment Variables

**Local Development:**
Create a `.env` file in the `ai-processing-microservice/` directory:
```bash
# .env file
REDIS_URL=redis://localhost:6379/0
OPENAI_API_KEY=your_openai_api_key_here
PORT=10000
```

**Production Deployment (Render):**
Set environment variables in your deployment platform:
- Go to your service settings
- Add environment variables:
  - `REDIS_URL`: Your Redis instance URL
  - `OPENAI_API_KEY`: Your OpenAI API key

**Why Both Services Need REDIS_URL:**
- **Microservice**: Queues tasks to Redis broker and checks task status
- **Celery Worker**: Connects to Redis broker to pick up tasks and store results

## Task Processing Flow

1. Client submits document to `/process-document`
2. Flask app queues task with Celery
3. Celery worker picks up task and processes document
4. Client polls `/task-status/<task_id>` for progress
5. Results are returned when processing completes

## Benefits

- ✅ **No timeout issues**: Tasks run independently of web requests
- ✅ **Scalable**: Multiple workers can process tasks in parallel
- ✅ **Reliable**: Redis persistence and task retry mechanisms
- ✅ **Real-time progress**: Detailed progress tracking per task
- ✅ **Error handling**: Graceful failure handling and reporting 