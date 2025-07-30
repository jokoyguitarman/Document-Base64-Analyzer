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

def analyze_page_sync(base64_str, page_number, total_pages, file_type, job_id):
    """Analyze a single page synchronously (non-Celery version)"""
    try:
        print(f"Job {job_id}: Analyzing page {page_number}/{total_pages}")
        
        if not base64_str:
            raise ValueError("task_id must not be empty. Got None instead.")
        
        content = [
            {
                "type": "text",
                "text": f"""Act as a subject matter expert and master educator. I want you to help me understand the content in this document or dataset as if you're teaching it to someone who is serious about learning — someone who doesn't just want surface-level summaries, but wants to fully grasp the meaning, implications, and logic behind it.

For each section, page, or visual (e.g. table, chart, slide, paragraph):

Teach, don't just summarize. Begin by identifying the main idea or argument. Then walk me through it clearly and patiently, as if preparing me to teach it to someone else.

Interpret the data or visuals. Don't just describe what's shown — help me understand what comparisons are being made, what insights are hidden in the data, and what it reveals that isn't immediately obvious.

Add expert insight. Expand with deeper context, cross-references, or real-world applications. Explain assumptions, limitations, or nuance that an expert would naturally consider.

Clarify and anticipate confusion. If any concept might be complex, counterintuitive, or misinterpreted, break it down further. Use analogies, examples, or step-by-step logic to reinforce the idea.

Extract meaning and relevance. Conclude by explaining the significance — how this changes our understanding, why it matters, or how it connects to a larger framework.

I don't mind if the explanations are long — in fact, I prefer detailed, information-rich responses over short ones. Prioritize clarity, completeness, and depth over brevity. Speak like an expert guiding a serious learner in a deep-dive session or masterclass. Please don't start with "this document" "this page" "this material", talk to me as if you're not reading it off a material I provided.

Analyze page {page_number} of this {total_pages}-page {file_type} document using this approach."""
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
                "text": f"""Act as a subject matter expert and master educator. I want you to help me understand the content in this document or dataset as if you're teaching it to someone who is serious about learning — someone who doesn't just want surface-level summaries, but wants to fully grasp the meaning, implications, and logic behind it.

For each section, page, or visual (e.g. table, chart, slide, paragraph):

Teach, don't just summarize. Begin by identifying the main idea or argument. Then walk me through it clearly and patiently, as if preparing me to teach it to someone else.

Interpret the data or visuals. Don't just describe what's shown — help me understand what comparisons are being made, what insights are hidden in the data, and what it reveals that isn't immediately obvious.

Add expert insight. Expand with deeper context, cross-references, or real-world applications. Explain assumptions, limitations, or nuance that an expert would naturally consider.

Clarify and anticipate confusion. If any concept might be complex, counterintuitive, or misinterpreted, break it down further. Use analogies, examples, or step-by-step logic to reinforce the idea.

Extract meaning and relevance. Conclude by explaining the significance — how this changes our understanding, why it matters, or how it connects to a larger framework.

I don't mind if the explanations are long — in fact, I prefer detailed, information-rich responses over short ones. Prioritize clarity, completeness, and depth over brevity. Speak like an expert guiding a serious learner in a deep-dive session or masterclass. Please don't start with "this document" "this page" "this material", talk to me as if you're not reading it off a material I provided.

Analyze page {page_number} of this {total_pages}-page {file_type} document using this approach."""
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
                page_data = analyze_page_sync(img_base64, page_num, num_pages, file_type, job_id)
                
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
            webhook_url = os.getenv('WEBHOOK_URL', 'https://studycompanion.io/api/update-job-results')
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