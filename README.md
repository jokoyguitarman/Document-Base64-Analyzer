# Document Base64 Analyzer

A Python Flask microservice for processing document images using OpenAI's GPT-4 Vision API. This service downloads images from Supabase Storage, converts them to base64, and analyzes them using ChatGPT to extract meaningful insights.

## Features

- **Image Processing**: Downloads images from Supabase Storage and converts to base64
- **AI Analysis**: Uses OpenAI GPT-4 Vision API for document interpretation
- **Retry Logic**: Implements robust retry mechanisms for API rate limits and errors
- **Fallback Support**: Handles text-only processing when images are unavailable
- **Comprehensive Output**: Generates both brief overviews and detailed analyses

## API Endpoints

### Health Check
```
GET /health
```
Returns service status and health information.

### Process Document
```
POST /process-document
```

**Request Body:**
```json
{
  "job_id": "string",
  "user_id": "string", 
  "image_urls": ["string"],
  "num_pages": 1,
  "file_type": "string",
  "fallback_text": "string"
}
```

**Response:**
```json
{
  "success": true,
  "briefOverview": "string",
  "comprehensiveAnalysis": "string",
  "numPages": 1,
  "fileType": "string",
  "totalAnalysisLength": 1000,
  "pagesProcessed": 1
}
```

## Environment Variables

- `SUPABASE_URL`: Your Supabase project URL
- `SUPABASE_SERVICE_ROLE_KEY`: Supabase service role key for Storage access
- `OPENAI_API_KEY`: OpenAI API key for GPT-4 Vision access
- `PORT`: Server port (default: 5000)

## Deployment

This service is designed to be deployed on Render.com as a web service.

### Local Development

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Set environment variables:
```bash
export SUPABASE_URL="your-supabase-url"
export SUPABASE_SERVICE_ROLE_KEY="your-service-key"
export OPENAI_API_KEY="your-openai-key"
```

3. Run the service:
```bash
python main.py
```

## Architecture

This microservice is part of a larger document processing pipeline:

1. **Document Upload**: Documents are uploaded to the main application
2. **Image Conversion**: First microservice converts documents to base64 images
3. **Storage Upload**: Images are uploaded to Supabase Storage
4. **AI Processing**: This microservice downloads images and processes with ChatGPT
5. **Results Storage**: Analysis results are stored in the database

## Error Handling

- **Rate Limiting**: Exponential backoff for OpenAI API rate limits
- **Network Errors**: Retry logic for timeouts and server errors
- **Image Processing**: Graceful handling of failed image downloads
- **Fallback Processing**: Text-only analysis when images are unavailable

## Dependencies

- Flask 2.3.3
- requests 2.31.0
- supabase 2.3.4
- python-dotenv 1.0.0
- gunicorn 21.2.0 