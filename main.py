from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import base64
import json
from PIL import Image
import openai
import time
from datetime import datetime
from dotenv import load_dotenv
from celery_config import celery_app
import tasks  # Import tasks to register them with Celery
from tasks import process_document_job, generate_audio_job, generate_reading_audio_job

# Load environment variables
load_dotenv()

app = Flask(__name__)
CORS(app)

# Configure OpenAI client
client = openai.OpenAI(
    api_key=os.getenv('OPENAI_API_KEY'),
    timeout=60.0,
    max_retries=3
)

@app.route('/', methods=['GET'])
def root():
    return jsonify({
        'message': 'AI Processing Microservice',
        'status': 'running',
        'endpoints': {
            'health': '/health',
            'test': '/test',
            'process_document': '/process-document',
            'generate_audio': '/generate-audio',
            'generate_reading_audio': '/generate-reading-audio',
            'job_status': '/job-status/<job_id>'
        },
        'version': '3.0.0',
        'processing': 'celery-background'
    })

@app.route('/health', methods=['GET'])
def health_check():
    # Check Celery worker status
    try:
        inspect = celery_app.control.inspect()
        active_workers = inspect.active()
        registered_tasks = inspect.registered()
        
        return jsonify({
            'status': 'healthy', 
            'service': 'ai-processing-microservice',
            'processing': 'celery-background',
            'celery_workers': len(active_workers) if active_workers else 0,
            'registered_tasks': len(registered_tasks) if registered_tasks else 0
        })
    except Exception as e:
        return jsonify({
            'status': 'warning',
            'service': 'ai-processing-microservice',
            'processing': 'celery-background',
            'celery_error': str(e)
        })

@app.route('/test', methods=['GET'])
def test_endpoint():
    return jsonify({'message': 'Test endpoint working', 'cors': 'enabled'})

@app.route('/process-document', methods=['POST'])
def process_document():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400

        job_id = data.get('job_id')
        user_id = data.get('user_id')
        image_urls = data.get('image_urls', [])
        num_pages = data.get('num_pages', 1)
        file_type = data.get('file_type', 'PDF')
        fallback_text = data.get('fallback_text', '')
        images_base64 = data.get('images_base64', [])

        print(f"Received document processing request: job_id={job_id}, user_id={user_id}, pages={num_pages}")

        if not job_id or not user_id:
            return jsonify({'error': 'Missing required fields: job_id, user_id'}), 400

        if images_base64:
            # Queue the job for background processing using Celery
            task = process_document_job.delay(job_id, images_base64, num_pages, file_type, user_id)
            
            return jsonify({
                'status': 'queued',
                'message': 'Document processing job queued successfully',
                'job_id': job_id,
                'task_id': task.id,
                'user_id': user_id,
                'num_pages': num_pages,
                'file_type': file_type,
                'status_endpoint': f'/job-status/{job_id}',
                'task_endpoint': f'/task-status/{task.id}'
            })

        elif fallback_text.strip():
            # For text-only processing, do it immediately
            try:
                response = client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": "You are an expert document analyzer."},
                        {"role": "user", "content": f"Analyze this {file_type} document and extract key insights: {fallback_text}"}
                    ],
                    max_tokens=1500,
                    timeout=30
                )

                analysis_text = response.choices[0].message.content
                return jsonify({
                    'status': 'success',
                    'message': 'Document processed with fallback text',
                    'content': analysis_text,
                    'summary': analysis_text[:200] + '...' if len(analysis_text) > 200 else analysis_text,
                    'elevator_pitch': analysis_text[:300] + '...' if len(analysis_text) > 300 else analysis_text,
                    'job_id': job_id,
                    'user_id': user_id,
                    'num_pages': num_pages,
                    'file_type': file_type,
                    'pages_processed': 1
                })

            except Exception as e:
                return jsonify({'error': f'Text processing failed: {str(e)}'}), 500

        else:
            return jsonify({'error': 'No images or text provided for processing'}), 400

    except Exception as e:
        print(f"Error in process_document: {str(e)}")
        return jsonify({'error': f'Processing failed: {str(e)}'}), 500

@app.route('/generate-audio', methods=['POST'])
def generate_audio():
    """Queue audio generation job for background processing"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400

        job_id = data.get('job_id')
        document_id = data.get('document_id')
        user_id = data.get('user_id')
        voice = data.get('voice', 'en-US-Studio-Q')

        print(f"Received audio generation request: job_id={job_id}, document_id={document_id}, user_id={user_id}")

        if not job_id or not document_id or not user_id:
            return jsonify({'error': 'Missing required fields: job_id, document_id, user_id'}), 400

        # Queue the audio generation job for background processing using Celery
        task = generate_audio_job.delay(job_id, document_id, user_id, voice)
        
        return jsonify({
            'status': 'queued',
            'message': 'Audio generation job queued successfully',
            'job_id': job_id,
            'task_id': task.id,
            'user_id': user_id,
            'document_id': document_id,
            'voice': voice,
            'status_endpoint': f'/job-status/{job_id}',
            'task_endpoint': f'/task-status/{task.id}'
        })

    except Exception as e:
        print(f"Error in generate_audio: {str(e)}")
        return jsonify({'error': f'Audio generation failed: {str(e)}'}), 500

@app.route('/generate-reading-audio', methods=['POST'])
def generate_reading_audio():
    """Queue reading companion audio generation job for background processing"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400

        job_id = data.get('job_id')
        document_id = data.get('document_id')
        user_id = data.get('user_id')
        voice = data.get('voice', 'en-US-Studio-Q')

        print(f"Received reading companion audio generation request: job_id={job_id}, document_id={document_id}, user_id={user_id}")

        if not job_id or not document_id or not user_id:
            return jsonify({'error': 'Missing required fields: job_id, document_id, user_id'}), 400

        # Queue the reading companion audio generation job for background processing using Celery
        task = generate_reading_audio_job.delay(job_id, document_id, user_id, voice)
        
        return jsonify({
            'status': 'queued',
            'message': 'Reading companion audio generation job queued successfully',
            'job_id': job_id,
            'task_id': task.id,
            'user_id': user_id,
            'document_id': document_id,
            'voice': voice,
            'status_endpoint': f'/job-status/{job_id}',
            'task_endpoint': f'/task-status/{task.id}'
        })

    except Exception as e:
        print(f"Error in generate_reading_audio: {str(e)}")
        return jsonify({'error': f'Reading companion audio generation failed: {str(e)}'}), 500

@app.route('/job-status/<job_id>', methods=['GET'])
def get_job_status(job_id):
    """Get the status of a background job by job_id"""
    try:
        # This endpoint can be used to track jobs by job_id
        # For now, we'll return a generic response since Celery tracks by task_id
        return jsonify({
            'job_id': job_id,
            'status': 'tracking_by_task_id',
            'message': 'Use /task-status/<task_id> endpoint for detailed status'
        })
        
    except Exception as e:
        return jsonify({'error': f'Error retrieving job status: {str(e)}'}), 500

@app.route('/task-status/<task_id>', methods=['GET'])
def get_task_status(task_id):
    """Get the status of a Celery task"""
    try:
        task_result = celery_app.AsyncResult(task_id)
        
        if task_result.state == 'PENDING':
            response = {
                'task_id': task_id,
                'state': task_result.state,
                'status': 'Task is pending...'
            }
        elif task_result.state == 'PROGRESS':
            response = {
                'task_id': task_id,
                'state': task_result.state,
                'status': task_result.info.get('status', ''),
                'current': task_result.info.get('current', 0),
                'total': task_result.info.get('total', 0),
                'progress': int((task_result.info.get('current', 0) / task_result.info.get('total', 1)) * 100) if task_result.info.get('total', 0) > 0 else 0
            }
        elif task_result.state == 'SUCCESS':
            response = {
                'task_id': task_id,
                'state': task_result.state,
                'status': 'completed',
                'result': task_result.result
            }
        else:
            response = {
                'task_id': task_id,
                'state': task_result.state,
                'status': 'failed',
                'error': str(task_result.info)
            }
        
        return jsonify(response)
        
    except Exception as e:
        return jsonify({'error': f'Error retrieving task status: {str(e)}'}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 10000)))
