from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import base64
import json
from PIL import Image
import openai
import time

app = Flask(__name__)
CORS(app)

# Configure OpenAI client with better timeout settings
client = openai.OpenAI(
    api_key=os.getenv('OPENAI_API_KEY'),
    timeout=60.0,  # 60 seconds for the entire request
    max_retries=3  # Retry failed requests
)

@app.route('/', methods=['GET'])
def root():
    return jsonify({
        'message': 'AI Processing Microservice',
        'status': 'running',
        'endpoints': {
            'health': '/health',
            'test': '/test',
            'process_document': '/process-document'
        },
        'version': '1.0.0'
    })

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({
        'status': 'healthy', 
        'service': 'ai-processing-microservice',
        'timeout': '900s (15 minutes)',
        'worker_timeout': '900s',
        'max_pages_per_document': 'unlimited (time-based)',
        'processing_strategy': 'one page per API call'
    })

@app.route('/test', methods=['GET'])
def test_endpoint():
    return jsonify({'message': 'Test endpoint working', 'cors': 'enabled'})

def analyze_images_with_gpt(images_base64: list, num_pages: int, file_type: str) -> dict:
    """Analyze document images one page at a time with proper timeout handling"""
    try:
        print(f"Processing {len(images_base64)} images - one page per API call")
        
        all_page_analyses = []
        start_time = time.time()
        max_total_time = 840  # 14 minutes (leaving 1 minute buffer)
        
        # Process each page individually
        for i, img_base64 in enumerate(images_base64):
            page_num = i + 1
            print(f"Analyzing page {page_num}/{len(images_base64)}...")
            
            # Check if we're running out of time
            elapsed_time = time.time() - start_time
            remaining_time = max_total_time - elapsed_time
            
            if remaining_time < 60:  # Less than 1 minute remaining
                print(f"⚠️ Time limit approaching ({remaining_time:.1f}s remaining) - stopping processing")
                break
            
            # Calculate timeout for this page (max 60 seconds per page)
            page_timeout = min(60, remaining_time - 30)  # Leave 30s buffer
            
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
                print(f"✅ Page {page_num} analysis completed")
                
            except Exception as e:
                print(f"❌ Error analyzing page {page_num}: {str(e)}")
                all_page_analyses.append(f"**Page {page_num} Analysis:**\nError processing this page: {str(e)}\n\n")
                continue
        
        # Combine all analyses
        combined_analysis = "\n".join(all_page_analyses)
        
        # Create final summary if we have time
        elapsed_time = time.time() - start_time
        if elapsed_time < max_total_time - 30:
            print("Creating final summary...")
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

            try:
                response = client.chat.completions.create(
                    model="gpt-4o",
                    messages=[{"role": "user", "content": summary_content}],
                    max_tokens=800,
                    timeout=25
                )

                analysis_text = response.choices[0].message.content
                print("✅ Final summary completed")

                # Try to extract JSON from the response
                try:
                    start_idx = analysis_text.find('{')
                    end_idx = analysis_text.rfind('}') + 1
                    if start_idx != -1 and end_idx != 0:
                        json_str = analysis_text[start_idx:end_idx]
                        result = json.loads(json_str)
                        return {
                            'content': combined_analysis,
                            'summary': result.get('summary', ''),
                            'elevator_pitch': result.get('elevator_pitch', '')
                        }
                    else:
                        return {
                            'content': combined_analysis,
                            'summary': analysis_text[:200] + '...' if len(analysis_text) > 200 else analysis_text,
                            'elevator_pitch': analysis_text[:300] + '...' if len(analysis_text) > 300 else analysis_text
                        }
                except json.JSONDecodeError:
                    return {
                        'content': combined_analysis,
                        'summary': analysis_text[:200] + '...' if len(analysis_text) > 200 else analysis_text,
                        'elevator_pitch': analysis_text[:300] + '...' if len(analysis_text) > 300 else analysis_text
                    }
            except Exception as e:
                print(f"❌ Error creating summary: {str(e)}")
                return {
                    'content': combined_analysis,
                    'summary': f"Analysis of {num_pages}-page {file_type} document completed. Processed {len(all_page_analyses)} pages.",
                    'elevator_pitch': f"Document analysis completed with {len(all_page_analyses)} pages processed successfully."
                }
        else:
            # Time is running out, return partial results
            print("⚠️ Time limit approaching - returning partial results without summary")
            return {
                'content': combined_analysis,
                'summary': f"Analysis of {num_pages}-page {file_type} document completed. Processed {len(all_page_analyses)} pages.",
                'elevator_pitch': f"Document analysis completed with {len(all_page_analyses)} pages processed successfully."
            }

    except Exception as e:
        print(f"Error analyzing images with GPT: {str(e)}")
        return {
            'content': f"Error analyzing document: {str(e)}",
            'summary': "Analysis failed",
            'elevator_pitch': "Unable to process document"
        }

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

        print(f"Processing document: job_id={job_id}, user_id={user_id}, pages={num_pages}, type={file_type}")
        print(f"Received {len(images_base64)} images and {len(image_urls)} image URLs")

        if not job_id or not user_id:
            return jsonify({'error': 'Missing required fields: job_id, user_id'}), 400

        if images_base64:
            try:
                result = analyze_images_with_gpt(images_base64, num_pages, file_type)
                return jsonify({
                    'status': 'success',
                    'message': 'Document processed successfully with GPT-4 Vision',
                    'content': result['content'],
                    'summary': result['summary'],
                    'elevator_pitch': result['elevator_pitch'],
                    'job_id': job_id,
                    'user_id': user_id,
                    'num_pages': num_pages,
                    'file_type': file_type,
                    'pages_processed': len(images_base64)
                })
            except Exception as e:
                print(f"Error in image analysis: {str(e)}")
                return jsonify({
                    'status': 'partial_success',
                    'message': f'Document processing encountered an error: {str(e)}',
                    'content': f'Error during processing: {str(e)}',
                    'summary': 'Processing failed',
                    'elevator_pitch': 'Unable to complete document analysis',
                    'job_id': job_id,
                    'user_id': user_id,
                    'num_pages': num_pages,
                    'file_type': file_type,
                    'pages_processed': 0
                }), 500

        elif fallback_text.strip():
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

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 10000)))
