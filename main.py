from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import base64
import json
from PIL import Image
from openai import OpenAI
from openai.types.chat import ChatCompletionMessageParam

app = Flask(__name__)
CORS(app)

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

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
    """Analyze document images efficiently using GPT-4o within 30-second limit"""
    try:
        print(f"Processing {len(images_base64)} images efficiently in single call...")
        
        # Create a single prompt with all images for fast processing
        content = [
            {
                "type": "text",
                "text": f"""Analyze this {num_pages}-page {file_type} document comprehensively. For each page, identify:
1. Main content and key information
2. Important details, data, or concepts
3. How each page contributes to the overall document

Provide a detailed analysis that covers all pages. Structure your response as JSON:
{{"content": "comprehensive analysis covering all pages in detail", "summary": "brief 2-3 sentence summary of the entire document", "elevator_pitch": "key insights and main takeaways in one paragraph"}}

Be thorough but efficient in your analysis."""
            }
        ]

        # Add all images to the prompt
        for i, img_base64 in enumerate(images_base64):
            content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/png;base64,{img_base64}"
                }
            })

        print(f"Analyzing all {len(images_base64)} pages in single GPT-4o call...")
        
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{
                "role": "user",
                "content": content
            }],
            max_tokens=2500,  # Higher limit for comprehensive analysis
            timeout=25  # Stay well under 30-second limit
        )

        analysis_text = response.choices[0].message.content
        print("✅ Analysis completed successfully")

        # Try to extract JSON from the response
        try:
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
                # If no JSON found, create a structured response
                return {
                    'content': analysis_text,
                    'summary': analysis_text[:200] + '...' if len(analysis_text) > 200 else analysis_text,
                    'elevator_pitch': analysis_text[:300] + '...' if len(analysis_text) > 300 else analysis_text
                }
        except json.JSONDecodeError:
            # Fallback if JSON parsing fails
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

        elif fallback_text.strip():
            try:
                response = client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": "You are an expert document analyzer."},
                        {"role": "user", "content": f"Analyze this {file_type} document and extract key insights: {fallback_text}"}
                    ],
                    max_tokens=1500
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
