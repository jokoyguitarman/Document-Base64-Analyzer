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
    return jsonify({'status': 'healthy', 'service': 'ai-processing-microservice'})

@app.route('/test', methods=['GET'])
def test_endpoint():
    return jsonify({'message': 'Test endpoint working', 'cors': 'enabled'})

def analyze_images_with_gpt(images_base64: list, num_pages: int, file_type: str) -> dict:
    """Analyze document images in batches to stay under 30-second timeout"""
    try:
        print(f"Processing {len(images_base64)} images in optimized batches...")
        
        all_page_analyses = []
        
        # For documents with many pages, process in smaller batches
        if len(images_base64) > 2:
            print(f"Document has {len(images_base64)} pages - processing in batches for efficiency")
            
            # Process first 2 pages together for initial analysis
            initial_content = [
                {
                    "type": "text",
                    "text": f"""Analyze the first 2 pages of this {num_pages}-page {file_type} document. Provide:
1. Key content and main points from these pages
2. Important information or data
3. How these pages relate to the overall document

Be concise but thorough."""
                }
            ]
            
            # Add first 2 images
            for i in range(min(2, len(images_base64))):
                initial_content.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/png;base64,{images_base64[i]}"
                    }
                })
            
            print("Analyzing first 2 pages...")
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[{
                    "role": "user",
                    "content": initial_content
                }],
                max_tokens=1500,
                timeout=20  # Stay well under 30s limit
            )
            
            initial_analysis = response.choices[0].message.content
            all_page_analyses.append(f"**Pages 1-2 Analysis:**\n{initial_analysis}\n\n")
            print("✅ Initial analysis completed")
            
            # If there are more pages, process them together
            if len(images_base64) > 2:
                remaining_content = [
                    {
                        "type": "text",
                        "text": f"""Analyze the remaining {len(images_base64)-2} pages of this {num_pages}-page {file_type} document. 
Based on the initial analysis: "{initial_analysis[:200]}..."

Provide additional key content and insights from these remaining pages."""
                    }
                ]
                
                # Add remaining images
                for i in range(2, len(images_base64)):
                    remaining_content.append({
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{images_base64[i]}"
                        }
                    })
                
                print(f"Analyzing remaining {len(images_base64)-2} pages...")
                response = client.chat.completions.create(
                    model="gpt-4o",
                    messages=[{
                        "role": "user",
                        "content": remaining_content
                    }],
                    max_tokens=1500,
                    timeout=20  # Stay well under 30s limit
                )
                
                remaining_analysis = response.choices[0].message.content
                all_page_analyses.append(f"**Pages 3-{len(images_base64)} Analysis:**\n{remaining_analysis}\n\n")
                print("✅ Remaining analysis completed")
        else:
            # For 1-2 page documents, process all together
            content = [
                {
                    "type": "text",
                    "text": f"""Analyze this {num_pages}-page {file_type} document. Provide:
1. Key content and main points
2. Important information or data
3. How the content relates to the overall document

Be concise but thorough."""
                }
            ]
            
            # Add all images
            for img_base64 in images_base64:
                content.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/png;base64,{img_base64}"
                    }
                })
            
            print(f"Analyzing all {len(images_base64)} pages together...")
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[{
                    "role": "user",
                    "content": content
                }],
                max_tokens=2000,
                timeout=25  # Stay well under 30s limit
            )
            
            combined_analysis = response.choices[0].message.content
            all_page_analyses.append(f"**Complete Document Analysis:**\n{combined_analysis}\n\n")
            print("✅ Analysis completed")
        
        # Combine all analyses
        combined_analysis = "\n".join(all_page_analyses)
        
        # Create final summary
        print("Creating final summary...")
        summary_content = [
            {
                "type": "text",
                "text": f"""Based on the analysis of this {num_pages}-page {file_type} document, provide:

1. A comprehensive overview of the entire document
2. A brief summary (2-3 sentences)
3. Key insights in one paragraph

Structure as JSON:
{{"content": "comprehensive analysis", "summary": "brief summary", "elevator_pitch": "key insights"}}

Document analysis:
{combined_analysis}"""
            }
        ]

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{
                "role": "user",
                "content": summary_content
            }],
            max_tokens=1500,
            timeout=20  # Stay well under 30s limit
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
                    'content': result.get('content', combined_analysis),
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
