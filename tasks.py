import os
import json
import time
from datetime import datetime
import openai
import requests
from celery_config import celery_app

# Configure OpenAI client
client = openai.OpenAI(
    api_key=os.getenv('OPENAI_API_KEY'),
    timeout=60.0,
    max_retries=3
)

@celery_app.task(bind=True)
def analyze_page(self, base64_str, page_number, total_pages, file_type, job_id):
    """Analyze a single page in the background"""
    try:
        print(f"Job {job_id}: Analyzing page {page_number}/{total_pages}")
        
        # Update task state
        self.update_state(
            state='PROGRESS',
            meta={
                'current': page_number,
                'total': total_pages,
                'status': f'Analyzing page {page_number}',
                'job_id': job_id
            }
        )
        
        content = [
            {
                "type": "text",
                "text": f"""Analyze page {page_number} of this {total_pages}-page {file_type} document. Provide:
1. Key content and main points from this page
2. Important information or data
3. How this page relates to the overall document

Be concise but thorough."""
            },
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{base64_str}"}
            }
        ]
        
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": content}],
            max_tokens=1500,
            timeout=60
        )
        
        page_analysis = response.choices[0].message.content
        print(f"Job {job_id}: ✅ Page {page_number} analysis completed")
        
        return {
            'page_number': page_number,
            'analysis': page_analysis,
            'status': 'completed',
            'job_id': job_id
        }
        
    except Exception as e:
        print(f"Job {job_id}: ❌ Error analyzing page {page_number}: {str(e)}")
        return {
            'page_number': page_number,
            'error': str(e),
            'status': 'failed',
            'job_id': job_id
        }

@celery_app.task(bind=True)
def process_document_job(self, job_id, images_base64, num_pages, file_type, user_id):
    """Process entire document by analyzing each page and creating summary"""
    try:
        print(f"Starting document processing job {job_id}")
        
        # Update initial state
        self.update_state(
            state='PROGRESS',
            meta={
                'current': 0,
                'total': len(images_base64),
                'status': 'Starting document analysis',
                'job_id': job_id
            }
        )
        
        all_page_analyses = []
        start_time = time.time()
        
        # Process each page
        for i, img_base64 in enumerate(images_base64):
            page_num = i + 1
            
            # Update progress
            self.update_state(
                state='PROGRESS',
                meta={
                    'current': page_num,
                    'total': len(images_base64),
                    'status': f'Analyzing page {page_num}/{len(images_base64)}',
                    'job_id': job_id
                }
            )
            
            # Analyze this page directly (synchronous) instead of using .delay()
            try:
                page_data = analyze_page(img_base64, page_num, num_pages, file_type, job_id)
                
                if page_data['status'] == 'completed':
                    all_page_analyses.append(f"**Page {page_num} Analysis:**\n{page_data['analysis']}\n\n")
                else:
                    all_page_analyses.append(f"**Page {page_num} Analysis:**\nError processing this page: {page_data['error']}\n\n")
            except Exception as e:
                print(f"Job {job_id}: ❌ Error analyzing page {page_num}: {str(e)}")
                all_page_analyses.append(f"**Page {page_num} Analysis:**\nError processing this page: {str(e)}\n\n")
        
        # Combine analyses
        combined_analysis = "\n".join(all_page_analyses)
        
        # Create final summary
        self.update_state(
            state='PROGRESS',
            meta={
                'current': len(images_base64),
                'total': len(images_base64),
                'status': 'Creating final summary',
                'job_id': job_id
            }
        )
        
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
        
        processing_time = time.time() - start_time
        
        # Store results in database via webhook
        try:
            webhook_url = os.getenv('WEBHOOK_URL', 'https://your-app.vercel.app/api/update-job-results')
            webhook_data = {
                'job_id': job_id,
                'user_id': user_id,
                'status': 'completed',
                'result': final_result,
                'processing_time': processing_time,
                'pages_processed': len(all_page_analyses),
                'completed_at': datetime.now().isoformat()
            }
            
            response = requests.post(webhook_url, json=webhook_data, timeout=30)
            if response.status_code == 200:
                print(f"Job {job_id}: ✅ Results stored in database")
            else:
                print(f"Job {job_id}: ⚠️ Failed to store results in database: {response.status_code}")
        except Exception as e:
            print(f"Job {job_id}: ⚠️ Error storing results in database: {str(e)}")
        
        return {
            'status': 'completed',
            'result': final_result,
            'processing_time': processing_time,
            'pages_processed': len(all_page_analyses),
            'completed_at': datetime.now().isoformat(),
            'job_id': job_id,
            'user_id': user_id
        }
        
    except Exception as e:
        print(f"Job {job_id}: ❌ Processing failed: {str(e)}")
        return {
            'status': 'failed',
            'error': str(e),
            'failed_at': datetime.now().isoformat(),
            'job_id': job_id,
            'user_id': user_id
        } 