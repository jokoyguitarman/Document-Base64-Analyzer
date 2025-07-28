from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import os
import base64
import requests
import json
from supabase import create_client, Client
from typing import List, Dict, Any
import asyncio

app = FastAPI()

# Supabase configuration
SUPABASE_URL = os.environ.get('https://zjzhlnzfqpcydfwnoomi.supabase.co')
SUPABASE_SERVICE_KEY = os.environ.get('eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InpqemhsbnpmcXBjeWRmd25vb21pIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1Mjg1NTg2MCwiZXhwIjoyMDY4NDMxODYwfQ.8rlGDO3VslscQ_0cmcic9U6-YrjeOWGrsmF-Kka9K5E')
supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

# OpenAI configuration
OPENAI_API_KEY = os.environ.get('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')

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "ai-processing-microservice"}

@app.post("/process-document")
async def process_document(request: Request):
    try:
        data = await request.json()

        job_id = data.get('job_id')
        user_id = data.get('user_id')
        image_urls = data.get('image_urls', [])
        num_pages = data.get('num_pages', 1)
        file_type = data.get('file_type', 'UNKNOWN')
        fallback_text = data.get('fallback_text', '')

        if not job_id or not user_id:
            return JSONResponse(content={'error': 'Missing required fields: job_id, user_id'}, status_code=400)

        result = await process_document_images(
            job_id=job_id,
            user_id=user_id,
            image_urls=image_urls,
            num_pages=num_pages,
            file_type=file_type,
            fallback_text=fallback_text
        )

        return JSONResponse(content=result)

    except Exception as e:
        return JSONResponse(content={'error': f'Processing failed: {str(e)}'}, status_code=500)

# 🧠 Leave your async functions like process_document_images, call_openai_with_retries, etc. as-is.
# ✅ No need to modify them — they work natively in FastAPI.

# At the end: no need for if __name__ == '__main__' — Render runs via `uvicorn`

