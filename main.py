from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import base64
import requests
import json
from supabase import create_client, Client
import time
from typing import List, Dict, Any

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Supabase configuration
SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_SERVICE_KEY = os.environ.get('SUPABASE_SERVICE_ROLE_KEY')
supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

# OpenAI configuration
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'healthy', 'service': 'ai-processing-microservice'})

@app.route('/process-document', methods=['POST'])
async def process_document():
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400
        
        # Extract job details
        job_id = data.get('job_id')
        user_id = data.get('user_id')
        image_urls = data.get('image_urls', [])
        num_pages = data.get('num_pages', 1)
        file_type = data.get('file_type', 'UNKNOWN')
        fallback_text = data.get('fallback_text', '')
        
        if not job_id or not user_id:
            return jsonify({'error': 'Missing required fields: job_id, user_id'}), 400
        
        print(f"Processing job {job_id} for user {user_id}")
        print(f"Image URLs: {len(image_urls)} images")
        print(f"Pages: {num_pages}, Type: {file_type}")
        
        # Process the document
        result = await process_document_images(
            job_id=job_id,
            user_id=user_id,
            image_urls=image_urls,
            num_pages=num_pages,
            file_type=file_type,
            fallback_text=fallback_text
        )
        
        return jsonify(result)
        
    except Exception as e:
        print(f"Error processing document: {str(e)}")
        return jsonify({'error': f'Processing failed: {str(e)}'}), 500

async def process_document_images(
    job_id: str,
    user_id: str,
    image_urls: List[str],
    num_pages: int,
    file_type: str,
    fallback_text: str
) -> Dict[str, Any]:
    """
    Process document images with ChatGPT Vision API
    """
    try:
        # Download and convert images from Supabase Storage
        print(f"Downloading {len(image_urls)} images from Supabase Storage...")
        base64_images = []
        
        for i, image_url in enumerate(image_urls):
            try:
                print(f"Downloading image {i+1}/{len(image_urls)}: {image_url}")
                
                # Download from Supabase Storage
                response = supabase.storage.from_('document-images').download(image_url)
                
                if response is None:
                    print(f"Failed to download image {i+1}")
                    continue
                
                # Convert to base64
                image_data = response
                base64_string = base64.b64encode(image_data).decode('utf-8')
                base64_images.append(base64_string)
                
                print(f"Successfully converted image {i+1} to base64 ({len(base64_string)} characters)")
                
            except Exception as e:
                print(f"Error processing image {i+1}: {str(e)}")
                continue
        
        if not base64_images:
            if fallback_text and len(fallback_text) > 500:
                print("No images available, using fallback text")
                return await process_document_text(fallback_text, num_pages, file_type)
            else:
                raise Exception("No images could be processed and no substantial fallback text available")
        
        print(f"Successfully prepared {len(base64_images)} images for processing")
        
        # Process images with ChatGPT
        return await process_images_with_chatgpt(base64_images, num_pages, file_type)
        
    except Exception as e:
        print(f"Error in process_document_images: {str(e)}")
        raise

async def process_images_with_chatgpt(
    base64_images: List[str],
    num_pages: int,
    file_type: str
) -> Dict[str, Any]:
    """
    Process images with ChatGPT Vision API
    """
    try:
        print(f"Processing {len(base64_images)} images with ChatGPT...")
        
        all_analyses = []
        total_analysis_length = 0
        
        # Process images one at a time to avoid rate limits
        for i, base64_image in enumerate(base64_images):
            print(f"Processing page {i+1}/{len(base64_images)}")
            print(f"Page {i+1}: Image data length: {len(base64_image)} characters")
            
            # Prepare the image for OpenAI
            image_data_url = f"data:image/png;base64,{base64_image}"
            
            # Create the prompt using the exact same format as your existing ai.ts file
            system_prompt = """You are an expert document analyst and educator. Your job is to interpret content from all kinds of documents — whether they are academic, technical, scientific, business, or legal. You go beyond just summarizing content. You explain what the information means, highlight its relevance, draw attention to important patterns or findings, and convey why the information matters. Think like a subject-matter expert speaking to an audience that values insight and clarity. IMPORTANT: Do not use any markdown formatting symbols like ##, **, or other formatting characters in your response. Write in plain text only."""

            user_prompt = f"""Please interpret this content from page {i+1} of {len(base64_images)}. Explain what it's about, summarize the key points, highlight any important patterns, data, or concepts, and discuss their significance or implications. Present the information clearly, thoughtfully, and in a way that brings out its value or purpose. Format the output with clear headings and bullet points for easy reading."""

            # Call OpenAI API with retries
            analysis = await call_openai_with_retries(image_data_url, system_prompt, user_prompt, i+1)
            
            if analysis:
                all_analyses.append(analysis)
                total_analysis_length += len(analysis)
                print(f"Page {i+1} analysis completed, length: {len(analysis)}")
                print(f"Total analysis length so far: {total_analysis_length} characters")
            
            # Wait between API calls to avoid rate limits
            if i < len(base64_images) - 1:
                print("Waiting 2 seconds before processing next page...")
                time.sleep(2)
        
        if not all_analyses:
            raise Exception("No pages were successfully analyzed")
        
        # Combine all analyses
        combined_analysis = "\n\n".join(all_analyses)
        
        # Generate final summaries
        brief_overview = await generate_brief_overview(combined_analysis, num_pages, file_type)
        comprehensive_analysis = await generate_comprehensive_analysis(combined_analysis, num_pages, file_type)
        
        return {
            'success': True,
            'briefOverview': brief_overview,
            'comprehensiveAnalysis': comprehensive_analysis,
            'numPages': num_pages,
            'fileType': file_type,
            'totalAnalysisLength': total_analysis_length,
            'pagesProcessed': len(all_analyses)
        }
        
    except Exception as e:
        print(f"Error in process_images_with_chatgpt: {str(e)}")
        raise

async def call_openai_with_retries(image_data_url: str, system_prompt: str, user_prompt: str, page_num: int, max_retries: int = 3) -> str:
    """
    Call OpenAI API with retry logic
    """
    for attempt in range(max_retries):
        try:
            print(f"Page {page_num}: Starting OpenAI API call...")
            print(f"OpenAI API call attempt {attempt + 1}/{max_retries}...")
            
            headers = {
                'Authorization': f'Bearer {OPENAI_API_KEY}',
                'Content-Type': 'application/json'
            }
            
            payload = {
                'model': 'gpt-4-vision-preview',
                'messages': [
                    {
                        'role': 'system',
                        'content': system_prompt
                    },
                    {
                        'role': 'user',
                        'content': [
                            {
                                'type': 'text',
                                'text': user_prompt
                            },
                            {
                                'type': 'image_url',
                                'image_url': {
                                    'url': image_data_url
                                }
                            }
                        ]
                    }
                ],
                'max_tokens': 4000,
                'temperature': 0.3
            }
            
            print(f"Page {page_num}: Preparing to send to OpenAI...")
            
            response = requests.post(
                'https://api.openai.com/v1/chat/completions',
                headers=headers,
                json=payload,
                timeout=60
            )
            
            if response.status_code == 200:
                result = response.json()
                analysis = result['choices'][0]['message']['content']
                print(f"Page {page_num}: OpenAI API call successful")
                return analysis
            else:
                print(f"Page {page_num}: OpenAI API error - Status: {response.status_code}")
                print(f"Page {page_num}: Response: {response.text}")
                
                if response.status_code == 429:  # Rate limit
                    wait_time = 60 * (attempt + 1)  # Exponential backoff
                    print(f"Page {page_num}: Rate limited, waiting {wait_time} seconds...")
                    time.sleep(wait_time)
                elif response.status_code >= 500:  # Server error
                    wait_time = 10 * (attempt + 1)
                    print(f"Page {page_num}: Server error, waiting {wait_time} seconds...")
                    time.sleep(wait_time)
                else:
                    break  # Don't retry for client errors
                    
        except requests.exceptions.Timeout:
            print(f"Page {page_num}: OpenAI API timeout on attempt {attempt + 1}")
            if attempt < max_retries - 1:
                time.sleep(10)
        except Exception as e:
            print(f"Page {page_num}: OpenAI API error on attempt {attempt + 1}: {str(e)}")
            if attempt < max_retries - 1:
                time.sleep(10)
    
    print(f"Page {page_num}: All OpenAI API attempts failed")
    return None

async def generate_brief_overview(combined_analysis: str, num_pages: int, file_type: str) -> str:
    """
    Generate a brief overview of the document
    """
    try:
        prompt = f"""Please create a brief 2-3 sentence overview describing what this document is about:

{combined_analysis[:4000]}  # Limit to first 4000 chars to avoid token limits"""

        headers = {
            'Authorization': f'Bearer {OPENAI_API_KEY}',
            'Content-Type': 'application/json'
        }
        
        payload = {
            'model': 'gpt-3.5-turbo',
            'messages': [
                {
                    'role': 'system',
                    'content': "You are an expert document analyst. Your task is to create a brief, engaging 2-3 sentence overview that describes what a document is about. Focus on the main topic, purpose, and key takeaway. Write in clear, accessible language that gives readers a quick understanding of the document's content and value. Keep it concise but informative. IMPORTANT: Do not use any markdown formatting symbols like ##, **, or other formatting characters in your response. Write in plain text only."
                },
                {
                    'role': 'user',
                    'content': prompt
                }
            ],
            'max_tokens': 150,
            'temperature': 0.3
        }
        
        response = requests.post(
            'https://api.openai.com/v1/chat/completions',
            headers=headers,
            json=payload,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            return result['choices'][0]['message']['content']
        else:
            return f"Brief overview of {num_pages}-page {file_type} document based on analysis."
            
    except Exception as e:
        print(f"Error generating brief overview: {str(e)}")
        return f"Brief overview of {num_pages}-page {file_type} document based on analysis."

async def generate_comprehensive_analysis(combined_analysis: str, num_pages: int, file_type: str) -> str:
    """
    Generate a comprehensive analysis of the document
    """
    try:
        prompt = f"""Please interpret this content. Explain what it's about, summarize the key points, highlight any important patterns, data, or concepts, and discuss their significance or implications. Present the information clearly, thoughtfully, and in a way that brings out its value or purpose. Format the output with clear headings and bullet points for easy reading.

{combined_analysis[:6000]}  # Limit to avoid token limits"""

        headers = {
            'Authorization': f'Bearer {OPENAI_API_KEY}',
            'Content-Type': 'application/json'
        }
        
        payload = {
            'model': 'gpt-3.5-turbo',
            'messages': [
                {
                    'role': 'system',
                    'content': "You are an expert document analyst and educator. Your job is to interpret content from all kinds of documents — whether they are academic, technical, scientific, business, or legal. You go beyond just summarizing content. You explain what the information means, highlight its relevance, draw attention to important patterns or findings, and convey why the information matters. Think like a subject-matter expert speaking to an audience that values insight and clarity. IMPORTANT: Do not use any markdown formatting symbols like ##, **, or other formatting characters in your response. Write in plain text only."
                },
                {
                    'role': 'user',
                    'content': prompt
                }
            ],
            'max_tokens': 1000,
            'temperature': 0.3
        }
        
        response = requests.post(
            'https://api.openai.com/v1/chat/completions',
            headers=headers,
            json=payload,
            timeout=60
        )
        
        if response.status_code == 200:
            result = response.json()
            return result['choices'][0]['message']['content']
        else:
            return combined_analysis[:2000] + "..."  # Fallback to truncated analysis
            
    except Exception as e:
        print(f"Error generating comprehensive analysis: {str(e)}")
        return combined_analysis[:2000] + "..."  # Fallback to truncated analysis

async def process_document_text(text: str, num_pages: int, file_type: str) -> Dict[str, Any]:
    """
    Process document text when no images are available
    """
    try:
        print(f"Processing document text ({len(text)} characters)")
        
        # Generate summaries from text
        brief_overview = await generate_brief_overview(text, num_pages, file_type)
        comprehensive_analysis = await generate_comprehensive_analysis(text, num_pages, file_type)
        
        return {
            'success': True,
            'briefOverview': brief_overview,
            'comprehensiveAnalysis': comprehensive_analysis,
            'numPages': num_pages,
            'fileType': file_type,
            'totalAnalysisLength': len(text),
            'pagesProcessed': 1,
            'processingMethod': 'text_only'
        }
        
    except Exception as e:
        print(f"Error in process_document_text: {str(e)}")
        raise

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False) 
