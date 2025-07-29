from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import base64
import io
from PIL import Image
import openai
import json

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Configure OpenAI
openai.api_key = os.environ.get('OPENAI_API_KEY')

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
    return jsonify({'status': 'healthy', 'service': 'ai-processing-microservice'})

@app.route('/test', methods=['GET'])
def test_endpoint():
    return jsonify({'message': 'Test endpoint working', 'cors': 'enabled'})

def analyze_images_with_gpt(images_base64: list, num_pages: int, file_type: str) -> dict:
    """Analyze document images using GPT-4 Vision"""
    try:
        # Prepare the content for GPT-4 Vision
        content = [
            {
                "type": "text",
                "text": f"""You are an expert document analyzer. Analyze this {file_type} document with {num_pages} pages and provide:

1. A comprehensive analysis of the content
2. A brief summary (2-3 sentences)
3. Key points and insights
4. The main topics covered

Please structure your response as JSON with these fields:
- "content": The comprehensive analysis
- "summary": Brief summary
- "elevator_pitch": Key insights in one paragraph

Focus on extracting meaningful information and insights from the document."""
            }
        ]
        
        # Add images to the content
        for i, img_base64 in enumerate(images_base64):
            content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/png;base64,{img_base64}"
                }
            })
        
        # Call GPT-4 Vision
        response = openai.ChatCompletion.create(
            model="gpt-4-vision-preview",
            messages=[
                {
                    "role": "user",
                    "content": content
                }
            ],
            max_tokens=2000
        )
        
        # Parse the response
        analysis_text = response.choices[0].message.content
        
        # Try to extract JSON from the response
        try:
            # Look for JSON in the response
            start_idx = analysis_text.find('{')
            end_idx = analysis_text.rfind('}') + 1
            if start_idx != -1 and end_idx != 0:
                json_str = analysis_text[start_idx:end_idx]
                result = json.loads(json_str)
                return {
                    'content': result.get('content', analysis_text),
                    'summary': result.get('summary', ''),
                    'elevator_pitch': result.get('elevator_pitch', '')
                }
            else:
                # If no JSON found, return the full text
                return {
                    'content': analysis_text,
                    'summary': analysis_text[:200] + '...' if len(analysis_text) > 200 else analysis_text,
                    'elevator_pitch': analysis_text[:300] + '...' if len(analysis_text) > 300 else analysis_text
                }
        except json.JSONDecodeError:
            # If JSON parsing fails, return the full text
            return {
                'content': analysis_text,
                'summary': analysis_text[:200] + '...' if len(analysis_text) > 200 else analysis_text,
                'elevator_pitch': analysis_text[:300] + '...' if len(analysis_text) > 300 else analysis_text
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
        
        # Extract data from request
        job_id = data.get('job_id')
        user_id = data.get('user_id')
        image_urls = data.get('image_urls', [])
        num_pages = data.get('num_pages', 1)
        file_type = data.get('file_type', 'PDF')
        fallback_text = data.get('fallback_text', '')
        images_base64 = data.get('images_base64', [])
        
        print(f"Processing document: job_id={job_id}, user_id={user_id}, pages={num_pages}, type={file_type}")
        print(f"Received {len(images_base64)} images and {len(image_urls)} image URLs")
        
        # Validate required fields
        if not job_id or not user_id:
            return jsonify({'error': 'Missing required fields: job_id, user_id'}), 400
        
        # Process images if available
        if images_base64 and len(images_base64) > 0:
            print(f"Processing {len(images_base64)} images with GPT-4 Vision")
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
                'file_type': file_type
            })
        
        # Fallback to text processing if no images
        elif fallback_text and len(fallback_text.strip()) > 0:
            print("Processing fallback text with GPT-3.5")
            try:
                response = openai.ChatCompletion.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {
                            "role": "system",
                            "content": "You are an expert document analyzer. Analyze the provided text and extract key insights."
                        },
                        {
                            "role": "user",
                            "content": f"Analyze this {file_type} document text and provide a comprehensive analysis, summary, and key insights: {fallback_text}"
                        }
                    ],
                    max_tokens=1500
                )
                
                analysis_text = response.choices[0].message.content
                
                return jsonify({
                    'status': 'success',
                    'message': 'Document processed successfully with fallback text',
                    'content': analysis_text,
                    'summary': analysis_text[:200] + '...' if len(analysis_text) > 200 else analysis_text,
                    'elevator_pitch': analysis_text[:300] + '...' if len(analysis_text) > 300 else analysis_text,
                    'job_id': job_id,
                    'user_id': user_id,
                    'num_pages': num_pages,
                    'file_type': file_type
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
