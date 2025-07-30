# AI Processing Microservice

A Python Flask microservice with Celery background processing for analyzing documents using OpenAI's GPT-4 Vision API. This service processes document images and provides comprehensive analysis with real-time progress tracking.

## Features

- **Background Processing**: Celery-based task queuing for reliable document processing
- **Real-time Progress**: Track task status and progress updates
- **AI Analysis**: Uses OpenAI GPT-4 Vision API for document interpretation
- **Retry Logic**: Implements robust retry mechanisms for API rate limits and errors
- **Fallback Support**: Handles text-only processing when images are unavailable
- **Scalable Architecture**: Multiple workers can process tasks in parallel
- **Redis Integration**: Reliable message broker and result storage

## API Endpoints

### Health Check
```
GET /health
```
Returns service status and Celery worker information.

### Process Document
```
POST /process-document
```
Queues a document for background processing and returns immediately with task_id.

**Request Body:**
```json
{
  "job_id": "string",
  "user_id": "string", 
  "images_base64": ["string"],
  "num_pages": 1,
  "file_type": "string",
  "fallback_text": "string"
}
```

**Response:**
```json
{
  "status": "queued",
  "message": "Document processing job queued successfully",
  "job_id": "string",
  "task_id": "string",
  "user_id": "string",
  "num_pages": 1,
  "file_type": "string",
  "status_endpoint": "/job-status/job_id",
  "task_endpoint": "/task-status/task_id"
}
```

### Check Task Status
```
GET /task-status/<task_id>
```
Returns real-time progress and results for a specific task.

**Response:**
```json
{
  "task_id": "string",
  "state": "PROGRESS",
  "status": "Processing page 2 of 5",
  "current": 2,
  "total": 5,
  "progress": 40
}
```

## Environment Variables

### Required Variables

**Both the microservice and Celery worker need these environment variables:**

- `REDIS_URL`: Redis connection string
  - Local development: `redis://localhost:6379/0`
  - Production: `redis://your-redis-instance-url:port`
- `OPENAI_API_KEY`: OpenAI API key for GPT-4 Vision access
- `PORT`: Server port (default: 10000)

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

## Deployment

This service is designed to be deployed on Render.com as a web service.

### Local Development

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

3. **Create .env file**:
   ```bash
   # Create .env file in ai-processing-microservice/ directory
   REDIS_URL=redis://localhost:6379/0
   OPENAI_API_KEY=your_openai_api_key_here
   PORT=10000
   ```

4. **Start Celery worker** (in separate terminal):
   ```bash
   python worker.py
   ```

5. **Start Flask app** (in another terminal):
   ```bash
   python main.py
   ```

## Architecture

This microservice uses a robust background processing architecture:

1. **Web Service**: Flask app receives requests and queues tasks
2. **Redis Broker**: Message broker for task queuing and result storage
3. **Celery Workers**: Background processes that execute document analysis
4. **Task Management**: Real-time progress tracking and status updates

### Processing Flow

1. **Task Submission**: Client submits document to `/process-document`
2. **Task Queuing**: Flask app queues task with Celery (returns task_id immediately)
3. **Background Processing**: Celery worker picks up task and processes document
4. **Progress Tracking**: Client polls `/task-status/<task_id>` for updates
5. **Result Delivery**: Final results returned when processing completes

## Error Handling

- **Rate Limiting**: Exponential backoff for OpenAI API rate limits
- **Network Errors**: Retry logic for timeouts and server errors
- **Task Failures**: Graceful handling of failed tasks with detailed error reporting
- **Fallback Processing**: Text-only analysis when images are unavailable
- **Redis Connection**: Automatic retry mechanisms for Redis connectivity issues
- **Worker Recovery**: Failed tasks can be retried automatically

## Dependencies

- Flask 3.0.0+
- Celery 5.3.0+
- Redis 5.0.0+
- requests 2.31.0+
- python-dotenv 1.0.0+
- gunicorn 21.2.0+
- pillow 10.0.0+
- openai 1.3.0+ 