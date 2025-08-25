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
from batch_monitor import BatchProcessingMonitor

# Load environment variables
load_dotenv()

app = Flask(__name__)
CORS(app)

# Initialize batch processing monitor
batch_monitor = BatchProcessingMonitor()

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
            'process_large_document': '/process-large-document',
            'process_document_selection': '/process-document-selection',
            'process_document_smart': '/process-document-smart',
            'batch_status': '/batch-status/<job_id>',
            'batch_stats': '/batch-stats',
            'cancel_job': '/cancel-job/<job_id>',
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
                        {"role": "user", "content": f"Analyze this {file_type} document and extract key insights: {fallback_text}\n\nPlease format your analysis using proper HTML tags to enhance readability and structure:\n- Use <h2> for main section headings (e.g., 'Document Analysis', 'Key Insights')\n- Use <h3> for subsection headings (e.g., 'Main Idea', 'Detailed Analysis', 'Expert Insights')\n- Use <p> for paragraphs and explanations\n- Use <ul> and <li> for lists and bullet points\n- Use <strong> for emphasis on key terms and concepts\n- Use <em> for secondary emphasis and important details\n- Structure the content hierarchically for better organization and readability\n- Ensure the HTML is properly formatted and valid"}
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

@app.route('/process-large-document', methods=['POST'])
def process_large_document():
    """Optimized endpoint for processing large documents (500+ pages) with batch processing"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400

        job_id = data.get('job_id')
        user_id = data.get('user_id')
        images_base64 = data.get('images_base64', [])
        num_pages = data.get('num_pages', len(images_base64))
        file_type = data.get('file_type', 'PDF')

        print(f"Received large document processing request: job_id={job_id}, user_id={user_id}, pages={num_pages}")

        if not job_id or not user_id:
            return jsonify({'error': 'Missing required fields: job_id, user_id'}), 400

        if not images_base64:
            return jsonify({'error': 'No images provided for processing'}), 400

        # Validate document size
        if len(images_base64) < 50:
            return jsonify({
                'error': 'Use /process-document endpoint for documents under 50 pages',
                'redirect_endpoint': '/process-document'
            }), 400

        # Queue the large document job with batch processing
        task = process_document_job.delay(job_id, images_base64, num_pages, file_type, user_id)
        
        # Calculate estimated processing time
        estimated_time = (len(images_base64) * 30) / 6  # 30 seconds per page, 6 parallel workers
        
        return jsonify({
            'status': 'queued',
            'message': f'Large document processing job queued (batch processing enabled)',
            'job_id': job_id,
            'task_id': task.id,
            'user_id': user_id,
            'num_pages': num_pages,
            'file_type': file_type,
            'processing_strategy': 'batch_parallel',
            'batch_size': 25,
            'estimated_batches': (len(images_base64) + 24) // 25,  # Round up
            'estimated_completion_minutes': int(estimated_time / 60),
            'status_endpoint': f'/batch-status/{job_id}',
            'task_endpoint': f'/task-status/{task.id}',
            'cancel_endpoint': f'/cancel-job/{job_id}'
        })

    except Exception as e:
        print(f"Error in process_large_document: {str(e)}")
        return jsonify({'error': f'Large document processing failed: {str(e)}'}), 500

@app.route('/batch-status/<job_id>', methods=['GET'])
def get_batch_status(job_id):
    """Get detailed batch processing status for large documents"""
    try:
        progress = batch_monitor.get_job_progress(job_id)
        
        # Add estimation if processing
        if progress['status'] == 'processing' and progress['current_page'] > 0:
            pages_remaining = progress['total_pages'] - progress['current_page']
            if pages_remaining > 0:
                estimation = batch_monitor.estimate_completion_time(job_id, pages_remaining)
                progress.update(estimation)
        
        return jsonify(progress)
        
    except Exception as e:
        return jsonify({
            'job_id': job_id,
            'error': f'Error retrieving batch status: {str(e)}',
            'status': 'error'
        }), 500

@app.route('/batch-stats', methods=['GET'])
def get_batch_stats():
    """Get overall batch processing system statistics"""
    try:
        stats = batch_monitor.get_batch_statistics()
        return jsonify(stats)
        
    except Exception as e:
        return jsonify({'error': f'Error retrieving batch stats: {str(e)}'}), 500

@app.route('/cancel-job/<job_id>', methods=['POST'])
def cancel_job(job_id):
    """Cancel a batch processing job and all its tasks"""
    try:
        result = batch_monitor.cancel_job(job_id)
        
        if result.get('error'):
            return jsonify(result), 500
        
        return jsonify({
            'status': 'cancelled',
            'message': f'Job {job_id} and {result["cancelled_tasks"]} associated tasks have been cancelled',
            **result
        })
        
    except Exception as e:
        return jsonify({
            'job_id': job_id,
            'error': f'Error cancelling job: {str(e)}',
            'status': 'error'
        }), 500

@app.route('/process-document-selection', methods=['POST'])
def process_document_selection():
    """Process only selected pages from a document"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400

        job_id = data.get('job_id')
        user_id = data.get('user_id')
        selected_pages = data.get('selected_pages', [])  # List of page numbers [15, 16, 17, ..., 45]
        all_images = data.get('images_base64', [])
        file_type = data.get('file_type', 'PDF')
        num_pages = data.get('num_pages', len(all_images))

        print(f"Received page selection request: job_id={job_id}, user_id={user_id}, selected_pages={selected_pages}, total_pages={len(all_images)}")

        # Validation
        if not job_id or not user_id:
            return jsonify({'error': 'Missing required fields: job_id, user_id'}), 400
        
        if not all_images:
            return jsonify({'error': 'No images provided for processing'}), 400
        
        if not selected_pages:
            return jsonify({'error': 'No pages selected for processing'}), 400

        # Validate page selection
        if len(selected_pages) > 30:
            return jsonify({
                'error': 'Maximum 30 pages can be selected per request',
                'selected_pages': len(selected_pages),
                'max_allowed': 30
            }), 400

        # Validate page numbers are within range
        max_page = len(all_images)
        invalid_pages = [p for p in selected_pages if p < 1 or p > max_page]
        if invalid_pages:
            return jsonify({
                'error': f'Invalid page numbers: {invalid_pages}. Valid range: 1-{max_page}',
                'invalid_pages': invalid_pages,
                'valid_range': f'1-{max_page}'
            }), 400

        # Filter images to only selected pages (convert to 0-based index)
        filtered_images = []
        for page_num in selected_pages:
            if 1 <= page_num <= len(all_images):
                filtered_images.append(all_images[page_num - 1])

        print(f"Filtered {len(filtered_images)} images from {len(all_images)} total pages")

        # Queue the job for background processing using Celery
        task = process_document_job.delay(job_id, filtered_images, len(filtered_images), file_type, user_id)
        
        # Calculate estimated processing time
        estimated_seconds = len(filtered_images) * 31  # 30 seconds per page + 1 second delay
        estimated_minutes = int(estimated_seconds / 60)
        
        return jsonify({
            'status': 'queued',
            'message': f'Page selection processing job queued successfully',
            'job_id': job_id,
            'task_id': task.id,
            'user_id': user_id,
            'selected_pages': selected_pages,
            'pages_to_process': len(filtered_images),
            'total_document_pages': len(all_images),
            'file_type': file_type,
            'processing_strategy': 'page_selection',
            'estimated_completion_minutes': estimated_minutes,
            'status_endpoint': f'/job-status/{job_id}',
            'task_endpoint': f'/task-status/{task.id}'
        })

    except Exception as e:
        print(f"Error in process_document_selection: {str(e)}")
        return jsonify({'error': f'Page selection processing failed: {str(e)}'}), 500

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



@app.route('/process-document-smart', methods=['POST'])
def process_document_smart():
    """Process entire document with AI-powered page skipping (skips unnecessary pages automatically)"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400

        job_id = data.get('job_id')
        user_id = data.get('user_id')
        all_images = data.get('images_base64', [])
        file_type = data.get('file_type', 'PDF')
        num_pages = data.get('num_pages', len(all_images))

        print(f"Received smart document processing request: job_id={job_id}, user_id={user_id}, total_pages={len(all_images)}")

        # Validation
        if not job_id or not user_id:
            return jsonify({'error': 'Missing required fields: job_id, user_id'}), 400

        if not all_images:
            return jsonify({'error': 'No images provided for processing'}), 400

        # Check document size limits
        if len(all_images) > 500:
            return jsonify({
                'error': f'Document too large: {len(all_images)} pages. Maximum allowed: 500 pages for smart processing.',
                'total_pages': len(all_images),
                'max_allowed': 500,
                'suggestion': 'Use page selection for documents over 500 pages'
            }), 400

        # Queue the job for background processing using Celery
        # The existing process_document_job will handle AI-powered page skipping
        task = process_document_job.delay(job_id, all_images, len(all_images), file_type, user_id)
        
        # Calculate estimated processing time (with potential skipping)
        # Assume 70% of pages will be processed (30% skipped as unnecessary)
        estimated_pages_to_process = int(len(all_images) * 0.7)
        estimated_minutes = estimated_pages_to_process * 0.5  # 30 seconds per page
        
        return jsonify({
            'status': 'queued',
            'message': f'Smart document processing job queued (AI will skip unnecessary pages)',
            'job_id': job_id,
            'task_id': task.id,
            'user_id': user_id,
            'total_document_pages': len(all_images),
            'estimated_pages_to_process': estimated_pages_to_process,
            'estimated_skipped_pages': len(all_images) - estimated_pages_to_process,
            'file_type': file_type,
            'processing_strategy': 'smart_processing',
            'estimated_completion_minutes': int(estimated_minutes),
            'status_endpoint': f'/job-status/{job_id}',
            'task_endpoint': f'/task-status/{task.id}'
        })

    except Exception as e:
        print(f"Error in process_document_smart: {str(e)}")
        return jsonify({'error': f'Smart document processing failed: {str(e)}'}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 10000)))
