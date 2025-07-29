from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import base64
import json
from PIL import Image
import openai
import time
import threading
import uuid
from datetime import datetime
import queue

app = Flask(__name__)
CORS(app)

# Configure OpenAI client
client = openai.OpenAI(
    api_key=os.getenv('OPENAI_API_KEY'),
    timeout=60.0,
    max_retries=3
)

# Background job processing
job_queue = queue.Queue()
job_results = {}
job_status = {}

def process_job_in_background(job_id, images_base64, num_pages, file_type, user_id):
    """Process a job in the background"""
    try:
        print(f"Starting background processing for job {job_id}")
        job_status[job_id] = {
            'status': 'processing',
            'progress': 0,
            'total_pages': len(images_base64),
            'processed_pages': 0,
            'started_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat()
        }
        
        all_page_analyses = []
        start_time = time.time()
        max_total_time = 840  # 14 minutes
        
        # Process each page individually
        for i, img_base64 in enumerate(images_base64):
            page_num = i + 1
            print(f"Job {job_id}: Analyzing page {page_num}/{len(images_base64)}...")
            
            # Update progress
            job_status[job_id]['progress'] = int((page_num - 1) / len(images_base64) * 100)
            job_status[job_id]['processed_pages'] = page_num - 1
            job_status[job_id]['updated_at'] = datetime.now().isoformat()
            
            # Check if we're running out of time
            elapsed_time = time.time() - start_time
            remaining_time = max_total_time - elapsed_time
            
            if remaining_time < 60:
                print(f"Job {job_id}: Time limit approaching - stopping processing")
                break
            
            # Calculate timeout for this page
            page_timeout = min(60, remaining_time - 30)
            
            try:
                content = [
                    {
                        "type": "text",
                        "text": f"""Analyze page {page_num} of this {num_pages}-page {file_type} document. Provide:
1. Key content and main points from this page
2. Important information or data
3. How this page relates to the overall document

Be concise but thorough."""
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{img_base64}"}
                    }
                ]
                
                response = client.chat.completions.create(
                    model="gpt-4o",
                    messages=[{"role": "user", "content": content}],
                    max_tokens=1500,
                    timeout=page_timeout
                )
                
                page_analysis = response.choices[0].message.content
                all_page_analyses.append(f"**Page {page_num} Analysis:**\n{page_analysis}\n\n")
                print(f"Job {job_id}: ✅ Page {page_num} analysis completed")
                
            except Exception as e:
                print(f"Job {job_id}: ❌ Error analyzing page {page_num}: {str(e)}")
                all_page_analyses.append(f"**Page {page_num} Analysis:**\nError processing this page: {str(e)}\n\n")
                continue
        
        # Combine analyses
        combined_analysis = "\n".join(all_page_analyses)
        
        # Create final summary if time permits
        elapsed_time = time.time() - start_time
        if elapsed_time < max_total_time - 30:
            print(f"Job {job_id}: Creating final summary...")
            try:
                summary_content = [
                    {
                        "type": "text",
                        "text": f"""Based on the analysis of this {num_pages}-page {file_type} document, provide:

1. A brief summary (2-3 sentences)
2. Key insights in one paragraph

Structure as JSON:
{{"summary": "brief summary", "elevator_pitch": "key insights"}}

Document analysis:
{combined_analysis}"""
                    }
                ]

                response = client.chat.completions.create(
                    model="gpt-4o",
                    messages=[{"role": "user", "content": summary_content}],
                    max_tokens=800,
                    timeout=25
                )

                analysis_text = response.choices[0].message.content
                print(f"Job {job_id}: ✅ Final summary completed")

                # Try to extract JSON from the response
                try:
                    start_idx = analysis_text.find('{')
                    end_idx = analysis_text.rfind('}') + 1
                    if start_idx != -1 and end_idx != 0:
                        json_str = analysis_text[start_idx:end_idx]
                        result = json.loads(json_str)
                        final_result = {
                            'content': combined_analysis,
                            'summary': result.get('summary', ''),
                            'elevator_pitch': result.get('elevator_pitch', '')
                        }
                    else:
                        final_result = {
                            'content': combined_analysis,
                            'summary': analysis_text[:200] + '...' if len(analysis_text) > 200 else analysis_text,
                            'elevator_pitch': analysis_text[:300] + '...' if len(analysis_text) > 300 else analysis_text
                        }
                except json.JSONDecodeError:
                    final_result = {
                        'content': combined_analysis,
                        'summary': analysis_text[:200] + '...' if len(analysis_text) > 200 else analysis_text,
                        'elevator_pitch': analysis_text[:300] + '...' if len(analysis_text) > 300 else analysis_text
                    }
            except Exception as e:
                print(f"Job {job_id}: ❌ Error creating summary: {str(e)}")
                final_result = {
                    'content': combined_analysis,
                    'summary': f"Analysis of {num_pages}-page {file_type} document completed. Processed {len(all_page_analyses)} pages.",
                    'elevator_pitch': f"Document analysis completed with {len(all_page_analyses)} pages processed successfully."
                }
        else:
            print(f"Job {job_id}: ⚠️ Time limit approaching - returning partial results")
            final_result = {
                'content': combined_analysis,
                'summary': f"Analysis of {num_pages}-page {file_type} document completed. Processed {len(all_page_analyses)} pages.",
                'elevator_pitch': f"Document analysis completed with {len(all_page_analyses)} pages processed successfully."
            }
        
        # Store results
        job_results[job_id] = {
            'status': 'completed',
            'result': final_result,
            'completed_at': datetime.now().isoformat(),
            'processing_time': elapsed_time,
            'pages_processed': len(all_page_analyses)
        }
        
        # Update final status
        job_status[job_id]['status'] = 'completed'
        job_status[job_id]['progress'] = 100
        job_status[job_id]['processed_pages'] = len(images_base64)
        job_status[job_id]['updated_at'] = datetime.now().isoformat()
        
        print(f"Job {job_id}: ✅ Processing completed successfully")
        
    except Exception as e:
        print(f"Job {job_id}: ❌ Processing failed: {str(e)}")
        job_results[job_id] = {
            'status': 'failed',
            'error': str(e),
            'failed_at': datetime.now().isoformat()
        }
        job_status[job_id]['status'] = 'failed'
        job_status[job_id]['updated_at'] = datetime.now().isoformat()

def background_worker():
    """Background worker to process jobs"""
    while True:
        try:
            job_data = job_queue.get(timeout=1)
            if job_data is None:
                break
            
            job_id, images_base64, num_pages, file_type, user_id = job_data
            process_job_in_background(job_id, images_base64, num_pages, file_type, user_id)
            job_queue.task_done()
            
        except queue.Empty:
            continue
        except Exception as e:
            print(f"Background worker error: {str(e)}")
            continue

# Start background worker
worker_thread = threading.Thread(target=background_worker, daemon=True)
worker_thread.start()

@app.route('/', methods=['GET'])
def root():
    return jsonify({
        'message': 'AI Processing Microservice',
        'status': 'running',
        'endpoints': {
            'health': '/health',
            'test': '/test',
            'process_document': '/process-document',
            'job_status': '/job-status/<job_id>'
        },
        'version': '2.0.0',
        'processing': 'background'
    })

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({
        'status': 'healthy', 
        'service': 'ai-processing-microservice',
        'processing': 'background',
        'queue_size': job_queue.qsize(),
        'active_jobs': len([j for j in job_status.values() if j['status'] == 'processing'])
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
            # Queue the job for background processing
            job_queue.put((job_id, images_base64, num_pages, file_type, user_id))
            
            # Initialize job status
            job_status[job_id] = {
                'status': 'queued',
                'progress': 0,
                'total_pages': len(images_base64),
                'processed_pages': 0,
                'queued_at': datetime.now().isoformat(),
                'updated_at': datetime.now().isoformat()
            }
            
            return jsonify({
                'status': 'queued',
                'message': 'Document processing job queued successfully',
                'job_id': job_id,
                'user_id': user_id,
                'num_pages': num_pages,
                'file_type': file_type,
                'queue_position': job_queue.qsize(),
                'status_endpoint': f'/job-status/{job_id}'
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

@app.route('/job-status/<job_id>', methods=['GET'])
def get_job_status(job_id):
    """Get the status of a background job"""
    try:
        if job_id not in job_status:
            return jsonify({'error': 'Job not found'}), 404
        
        status = job_status[job_id].copy()
        
        # If job is completed, include results
        if status['status'] == 'completed' and job_id in job_results:
            status['result'] = job_results[job_id]['result']
            status['processing_time'] = job_results[job_id]['processing_time']
            status['pages_processed'] = job_results[job_id]['pages_processed']
        elif status['status'] == 'failed' and job_id in job_results:
            status['error'] = job_results[job_id]['error']
        
        return jsonify(status)
        
    except Exception as e:
        return jsonify({'error': f'Error retrieving job status: {str(e)}'}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 10000)))
