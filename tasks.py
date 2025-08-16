import os
import json
import time
from datetime import datetime
import openai
import requests
from google.cloud import texttospeech
from celery_config import celery_app

# Configure OpenAI client
client = openai.OpenAI(
    api_key=os.getenv('OPENAI_API_KEY'),
    timeout=60.0,
    max_retries=3
)

def clean_text_for_tts(text):
    """Clean text for better text-to-speech output by removing markdown formatting and other artifacts"""
    import re
    
    if not text:
        return ""
    
    # Remove citations first
    # Remove URLs
    clean = re.sub(r'https?://[^\s)]+', '', text)
    # Remove parenthetical citations with URLs
    clean = re.sub(r'\([^)]*https?://[^)]*\)', '', clean)
    # Remove [number] citations
    clean = re.sub(r'\[\d+\]', '', clean)
    # Remove bibliography section and everything after
    clean = re.sub(r'Bibliography:[\s\S]*', '', clean, flags=re.IGNORECASE)
    
    # Remove markdown formatting
    # Remove headings (##, ###, etc.) - this addresses the #### issue
    clean = re.sub(r'^#+\s?', '', clean, flags=re.MULTILINE)
    # Remove bold/italic (**text**, *text*, __text__, _text_) - this addresses the **** issue
    clean = re.sub(r'\*\*([^*]+)\*\*', r'\1', clean)
    clean = re.sub(r'\*([^*]+)\*', r'\1', clean)
    clean = re.sub(r'__([^_]+)__', r'\1', clean)
    clean = re.sub(r'_([^_]+)_', r'\1', clean)
    # Remove unordered list markers
    clean = re.sub(r'^\s*[-*+]\s+', '', clean, flags=re.MULTILINE)
    # Remove ordered list markers
    clean = re.sub(r'^\s*\d+\.\s+', '', clean, flags=re.MULTILINE)
    # Remove blockquotes
    clean = re.sub(r'^>\s?', '', clean, flags=re.MULTILINE)
    # Remove inline code
    clean = re.sub(r'`([^`]+)`', r'\1', clean)
    # Remove code blocks
    clean = re.sub(r'```[\s\S]*?```', '', clean)
    # Remove extra spaces and normalize whitespace
    clean = re.sub(r'\s{2,}', ' ', clean)
    # Remove extra newlines
    clean = re.sub(r'\n{3,}', '\n\n', clean)
    
    return clean.strip()

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
def process_document_batch(self, job_id, batch_start, batch_end, images_base64_batch, num_pages, file_type, user_id):
    """Process a batch of pages in parallel for large documents"""
    try:
        print(f"Starting batch processing job {job_id} - pages {batch_start}-{batch_end}")
        
        # Update initial state
        self.update_state(
            state='PROGRESS',
            meta={
                'current': 0,
                'total': len(images_base64_batch),
                'status': f'Processing batch {batch_start}-{batch_end}',
                'job_id': job_id,
                'batch_start': batch_start,
                'batch_end': batch_end
            }
        )
        
        batch_results = []
        start_time = time.time()
        
        # Process pages in this batch in parallel using Celery group
        from celery import group
        
        # Create parallel tasks for this batch
        page_tasks = group(
            analyze_page.s(img_base64, batch_start + i, num_pages, file_type, job_id)
            for i, img_base64 in enumerate(images_base64_batch)
        )
        
        # Execute all page analyses in parallel
        job = page_tasks.apply_async()
        results = job.get(timeout=1500)  # 25 minute timeout for batch
        
        # Process results
        for i, page_result in enumerate(results):
            page_num = batch_start + i
            if page_result and page_result.get('status') == 'completed':
                batch_results.append({
                    'page_number': page_num,
                    'analysis': page_result['analysis'],
                    'status': 'completed'
                })
            else:
                error_msg = page_result.get('error', 'Unknown error') if page_result else 'No result returned'
                batch_results.append({
                    'page_number': page_num,
                    'analysis': f"Error processing page: {error_msg}",
                    'status': 'failed'
                })
        
        processing_time = time.time() - start_time
        
        return {
            'status': 'completed',
            'batch_start': batch_start,
            'batch_end': batch_end,
            'results': batch_results,
            'processing_time': processing_time,
            'pages_processed': len(batch_results),
            'job_id': job_id,
            'user_id': user_id
        }
        
    except Exception as e:
        print(f"Batch job {job_id} (pages {batch_start}-{batch_end}): ❌ Processing failed: {str(e)}")
        return {
            'status': 'failed',
            'batch_start': batch_start,
            'batch_end': batch_end,
            'error': str(e),
            'failed_at': datetime.now().isoformat(),
            'job_id': job_id,
            'user_id': user_id
        }

@celery_app.task(bind=True)
def process_document_job(self, job_id, images_base64, num_pages, file_type, user_id):
    """Process entire document by analyzing pages in batches for large documents"""
    try:
        print(f"Starting document processing job {job_id} with {len(images_base64)} pages")
        
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
        
        start_time = time.time()
        
        # Determine processing strategy based on document size
        if len(images_base64) > 50:  # Use batch processing for documents over 50 pages
            print(f"Job {job_id}: Large document detected ({len(images_base64)} pages), using batch processing")
            
            # Process in batches of 25 pages for optimal performance
            batch_size = 25
            batch_tasks = []
            all_page_analyses = []
            
            # Create batch tasks
            for i in range(0, len(images_base64), batch_size):
                batch_start = i + 1  # 1-indexed
                batch_end = min(i + batch_size, len(images_base64))
                batch_images = images_base64[i:i + batch_size]
                
                print(f"Job {job_id}: Creating batch for pages {batch_start}-{batch_end}")
                
                # Queue batch processing task
                batch_task = process_document_batch.delay(
                    job_id, batch_start, batch_end, batch_images, num_pages, file_type, user_id
                )
                batch_tasks.append(batch_task)
            
            # Wait for all batches to complete and collect results
            completed_pages = 0
            for batch_idx, batch_task in enumerate(batch_tasks):
                try:
                    print(f"Job {job_id}: Waiting for batch {batch_idx + 1}/{len(batch_tasks)}")
                    
                    # Update progress
                    self.update_state(
                        state='PROGRESS',
                        meta={
                            'current': completed_pages,
                            'total': len(images_base64),
                            'status': f'Processing batch {batch_idx + 1}/{len(batch_tasks)}',
                            'job_id': job_id
                        }
                    )
                    
                    batch_result = batch_task.get(timeout=1800)  # 30 minute timeout per batch
                    
                    if batch_result['status'] == 'completed':
                        # Sort results by page number and add to overall results
                        sorted_results = sorted(batch_result['results'], key=lambda x: x['page_number'])
                        for page_result in sorted_results:
                            page_num = page_result['page_number']
                            all_page_analyses.append(f"**Page {page_num} Analysis:**\n{page_result['analysis']}\n\n")
                            completed_pages += 1
                    else:
                        print(f"Job {job_id}: Batch {batch_idx + 1} failed: {batch_result.get('error', 'Unknown error')}")
                        # Add error entries for failed batch
                        batch_start = batch_result.get('batch_start', completed_pages + 1)
                        batch_end = batch_result.get('batch_end', completed_pages + 25)
                        for page_num in range(batch_start, batch_end + 1):
                            all_page_analyses.append(f"**Page {page_num} Analysis:**\nBatch processing failed: {batch_result.get('error', 'Unknown error')}\n\n")
                            completed_pages += 1
                            
                except Exception as e:
                    print(f"Job {job_id}: Error waiting for batch {batch_idx + 1}: {str(e)}")
                    # Add error entries for this batch
                    for _ in range(min(25, len(images_base64) - completed_pages)):
                        completed_pages += 1
                        all_page_analyses.append(f"**Page {completed_pages} Analysis:**\nBatch processing error: {str(e)}\n\n")
        
        else:  # Use sequential processing for smaller documents (<=50 pages)
            print(f"Job {job_id}: Small document ({len(images_base64)} pages), using sequential processing")
            all_page_analyses = []
            
            # Process each page sequentially
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
                
                # Analyze this page directly (synchronous) for smaller documents
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

# Content chunking functions (ported from TypeScript)
def count_words(text):
    """Count words in a string"""
    return len(text.strip().split())

def find_natural_breaks(text):
    """Find natural break points in text"""
    import re
    breaks = []
    
    # Split by major section breaks (double line breaks, headers, etc.)
    section_pattern = r'\n\s*\n\s*\n'
    for match in re.finditer(section_pattern, text):
        breaks.append(match.start())
    
    # Split by single paragraph breaks
    paragraph_pattern = r'\n\s*\n'
    for match in re.finditer(paragraph_pattern, text):
        if match.start() not in breaks:
            breaks.append(match.start())
    
    # Split by sentence endings (but be careful not to break on abbreviations)
    sentence_pattern = r'[.!?]\s+'
    for match in re.finditer(sentence_pattern, text):
        # Avoid breaking on common abbreviations
        before_match = text[max(0, match.start() - 10):match.start()]
        after_match = text[match.end():match.end() + 10]
        
        # Skip if it looks like an abbreviation (e.g., "Dr.", "Mr.", "etc.")
        if not before_match.strip().endswith('.') and not after_match.strip().startswith('ABCDEFGHIJKLMNOPQRSTUVWXYZ'):
            if match.end() - 1 not in breaks:
                breaks.append(match.end() - 1)
    
    return sorted(breaks)

def chunk_content(content, target_chunk_size=3000, min_chunk_size=1000, max_chunk_size=4000, overlap_words=100):
    """Intelligent content chunking function"""
    if not content or not content.strip():
        return []
    
    chunks = []
    natural_breaks = find_natural_breaks(content)
    current_index = 0
    chunk_id = 1
    
    while current_index < len(content):
        # Find the best break point within our target range
        end_index = current_index
        best_break_index = current_index
        
        # Look for natural breaks within our target range
        for break_index in natural_breaks:
            if break_index > current_index and break_index <= current_index + (target_chunk_size * 6):  # Rough estimate: 6 chars per word
                chunk_text = content[current_index:break_index]
                word_count = count_words(chunk_text)
                
                if min_chunk_size <= word_count <= max_chunk_size:
                    best_break_index = break_index
                    end_index = break_index
                    break
                elif word_count < min_chunk_size and break_index > best_break_index:
                    best_break_index = break_index
        
        # If no good natural break found, create a chunk up to max_chunk_size
        if best_break_index == current_index:
            # Find a reasonable break point within max_chunk_size
            temp_end = current_index + (max_chunk_size * 6)  # Rough estimate
            if temp_end > len(content):
                temp_end = len(content)
            
            # Look for the last sentence break within our range
            last_sentence_break = content.rfind('. ', current_index, temp_end)
            last_paragraph_break = content.rfind('\n\n', current_index, temp_end)
            
            if last_sentence_break > current_index and last_sentence_break > last_paragraph_break:
                end_index = last_sentence_break + 1
            elif last_paragraph_break > current_index:
                end_index = last_paragraph_break + 2
            else:
                end_index = temp_end
        else:
            end_index = best_break_index
        
        # Extract the chunk content
        chunk_content = content[current_index:end_index].strip()
        word_count = count_words(chunk_content)
        
        # Only add chunk if it has meaningful content
        if chunk_content and word_count >= min_chunk_size:
            chunks.append({
                'id': f'chunk-{chunk_id}',
                'content': chunk_content,
                'word_count': word_count,
                'start_index': current_index,
                'end_index': end_index,
                'is_complete': end_index in natural_breaks or end_index == len(content)
            })
            chunk_id += 1
        
        # Move to next chunk with overlap
        if overlap_words > 0 and end_index < len(content):
            overlap_text = ' '.join(chunk_content.split()[-overlap_words:])
            overlap_index = content.rfind(overlap_text, current_index, end_index)
            current_index = max(current_index + 1, overlap_index)
        else:
            current_index = end_index
        
        # Safety check to prevent infinite loops
        if chunks and current_index <= chunks[-1]['end_index']:
            current_index = end_index + 1
    
    return chunks

def generate_podcast_script_chunk(content, chunk_index, total_chunks):
    """Generate podcast-style script for a single chunk"""
    if not client:
        raise Exception('OpenAI is not available')
    
    context_info = f' (Part {chunk_index + 1} of {total_chunks})' if total_chunks > 1 else ''
    
    prompt = f"""Write a podcast-style narration script that sounds like it's being delivered by a confident, thoughtful speaker.

Do not include any introductions, podcast titles, greetings, or meta-language. Go straight into the subject.

Speak as if the narrator is drawing from their own expert knowledge — not reading or referring to any document. Do not mention phrases like "this document," "as shown," "according to this table," or anything that implies the speaker is referencing notes.

Use natural intonation and human pacing, as if it's being said aloud to an intelligent listener.

Write in simple, clean prose that flows naturally when spoken. Avoid any special formatting, HTML tags, or SSML markup.

The result should sound like a well-produced solo podcast segment — clean, clear, and engaging.

{context_info}

Here is the content to convert:

{content}"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert script writer who specializes in converting educational content into engaging podcast-style narration."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            max_tokens=2000,
            temperature=0.7,
        )

        generated_script = response.choices[0].message.content
        if not generated_script:
            raise Exception(f'No script generated from ChatGPT for chunk {chunk_index + 1}')

        print(f'Podcast script chunk {chunk_index + 1}/{total_chunks} generated successfully')
        return generated_script
    except Exception as error:
        print(f'Error generating podcast script for chunk {chunk_index + 1}: {error}')
        raise error

def generate_podcast_script(content):
    """Generate podcast-style script using ChatGPT with chunking"""
    if not client:
        raise Exception('OpenAI is not available')

    # Check if content is small enough to process in one go
    word_count = count_words(content)
    
    if word_count <= 4000:
        # Small content - process directly
        return generate_podcast_script_chunk(content, 0, 1)

    # Large content - use chunking
    print(f'Content is {word_count} words, using chunking system...')
    
    chunks = chunk_content(content, target_chunk_size=3000, min_chunk_size=1000, max_chunk_size=4000, overlap_words=100)

    print(f'Split content into {len(chunks)} chunks')

    # Process chunks sequentially
    script_chunks = []
    
    for i, chunk in enumerate(chunks):
        print(f'Processing chunk {i + 1}/{len(chunks)} ({chunk["word_count"]} words)...')
        
        try:
            script_chunk = generate_podcast_script_chunk(chunk['content'], i, len(chunks))
            script_chunks.append(script_chunk)
            
            # Add a small delay between chunks to avoid rate limiting
            if i < len(chunks) - 1:
                time.sleep(1)
        except Exception as error:
            print(f'Failed to process chunk {i + 1}: {error}')
            raise Exception(f'Failed to process chunk {i + 1}: {str(error)}')

    # Combine script chunks with proper spacing
    combined_script = '\n\n'.join(script_chunks)
    print(f'Successfully generated script from {len(chunks)} chunks')
    
    return combined_script

@celery_app.task(bind=True)
def generate_audio_job(self, job_id, document_id, user_id, voice='en-US-Studio-Q'):
    """Generate audio from document content using background processing"""
    try:
        print(f'Job {job_id}: Starting audio generation for document {document_id}')
        
        # Update task state
        self.update_state(
            state='PROGRESS',
            meta={
                'current': 0,
                'total': 4,
                'status': 'Fetching document content',
                'job_id': job_id
            }
        )
        
        # Fetch document content from Supabase
        from supabase import create_client, Client
        
        supabase_url = os.getenv('SUPABASE_URL')
        supabase_key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
        
        if not supabase_url or not supabase_key:
            raise Exception('Missing Supabase credentials')
        
        supabase: Client = create_client(supabase_url, supabase_key)
        
        # Fetch document
        response = supabase.table('documents').select('content, summary').eq('id', document_id).execute()
        if not response.data or len(response.data) == 0:
            raise Exception('Document not found')
        
        document = response.data[0]
        document_content = document.get('content') or document.get('summary') or ''
        
        if not document_content.strip():
            raise Exception('Document has no content to generate script from')
        
        # Update progress
        self.update_state(
            state='PROGRESS',
            meta={
                'current': 1,
                'total': 4,
                'status': 'Generating podcast script',
                'job_id': job_id
            }
        )
        
        # Clean the document content before generating script
        cleaned_content = clean_text_for_tts(document_content)
        
        # Generate podcast-style script from cleaned content
        final_text = generate_podcast_script(cleaned_content)
        print(f'Job {job_id}: Generated script length: {len(final_text)}')
        
        # Update progress
        self.update_state(
            state='PROGRESS',
            meta={
                'current': 2,
                'total': 4,
                'status': 'Generating audio',
                'job_id': job_id
            }
        )
        
        # Initialize Google TTS
        # Write TTS credentials to file if GOOGLE_TTS_CREDENTIALS_JSON is set
        if os.getenv('GOOGLE_TTS_CREDENTIALS_JSON') and not os.getenv('GOOGLE_APPLICATION_CREDENTIALS'):
            key_path = '/tmp/google-tts-key.json'
            with open(key_path, 'w') as f:
                f.write(os.getenv('GOOGLE_TTS_CREDENTIALS_JSON'))
            os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = key_path
        
        client_tts = texttospeech.TextToSpeechClient()
        
        # Helper to split text into <=5000 byte chunks
        def split_text_by_bytes(text, max_bytes):
            encoder = text.encode('utf-8')
            chunks = []
            current = ''
            for char in text:
                test = current + char
                if test.encode('utf-8').__sizeof__() > max_bytes:
                    chunks.append(current)
                    current = char
                else:
                    current = test
            if current:
                chunks.append(current)
            return chunks
        
        max_tts_bytes = 5000
        text_chunks = split_text_by_bytes(final_text, max_tts_bytes)
        audio_buffers = []
        
        for chunk in text_chunks:
            response_tts = client_tts.synthesize_speech({
                'input': {'text': chunk},
                'voice': {
                    'language_code': 'en-US',
                    'name': voice,
                    'ssml_gender': texttospeech.SsmlVoiceGender.MALE if voice == 'en-US-Studio-Q' else texttospeech.SsmlVoiceGender.FEMALE
                },
                'audio_config': {'audio_encoding': texttospeech.AudioEncoding.MP3},
            })
            
            if not response_tts.audio_content:
                raise Exception('No audio content returned from Google TTS')
            
            audio_buffers.append(response_tts.audio_content)
        
        audio_buffer = b''.join(audio_buffers)
        
        # Update progress
        self.update_state(
            state='PROGRESS',
            meta={
                'current': 3,
                'total': 4,
                'status': 'Uploading audio to storage',
                'job_id': job_id
            }
        )
        
        # Upload to Supabase Storage
        file_path = f'audio/{document_id}-{int(time.time())}.mp3'
        
        upload_response = supabase.storage.from_('documents').upload(
            file_path,
            audio_buffer,
            {'content-type': 'audio/mpeg', 'upsert': 'true'}
        )
        
        # Upload was successful (HTTP 200 OK indicates success)
        print(f'Job {job_id}: ✅ Audio uploaded to storage: {file_path}')
        
        # Update document with audio URL
        update_response = supabase.table('documents').update({
            'summary_audio_url': file_path,
            'updated_at': datetime.now().isoformat()
        }).eq('id', document_id).execute()
        
        print(f'Job {job_id}: ✅ Document updated with audio URL: {file_path}')
        
        # Update progress
        self.update_state(
            state='PROGRESS',
            meta={
                'current': 4,
                'total': 4,
                'status': 'Audio generation completed',
                'job_id': job_id
            }
        )
        
        # Store results via webhook
        try:
            webhook_url = os.getenv('WEBHOOK_URL', 'https://studycompanion.io/api/update-job-results')
            webhook_data = {
                'job_id': job_id,
                'user_id': user_id,
                'status': 'completed',
                'result': {
                    'audio_url': file_path,
                    'script_length': len(final_text),
                    'is_summary': True,
                    'generated_script': True
                },
                'processing_time': time.time(),
                'completed_at': datetime.now().isoformat()
            }
            
            response = requests.post(webhook_url, json=webhook_data, timeout=30)
            if response.status_code == 200:
                print(f'Job {job_id}: ✅ Results stored in database')
            else:
                print(f'Job {job_id}: ⚠️ Failed to store results in database: {response.status_code}')
        except Exception as e:
            print(f'Job {job_id}: ⚠️ Error storing results in database: {str(e)}')
        
        return {
            'status': 'completed',
            'result': {
                'audio_url': file_path,
                'script_length': len(final_text),
                'is_summary': True,
                'generated_script': True
            },
            'processing_time': time.time(),
            'completed_at': datetime.now().isoformat(),
            'job_id': job_id,
            'user_id': user_id
        }
        
    except Exception as e:
        print(f'Job {job_id}: ❌ Audio generation failed: {str(e)}')
        return {
            'status': 'failed',
            'error': str(e),
            'failed_at': datetime.now().isoformat(),
            'job_id': job_id,
            'user_id': user_id
        }

@celery_app.task(bind=True)
def generate_reading_audio_job(self, job_id, document_id, user_id, voice='en-US-Studio-Q'):
    """Generate reading companion audio from document content using direct text-to-speech"""
    try:
        print(f'Job {job_id}: Starting reading companion audio generation for document {document_id}')
        
        # Update task state
        self.update_state(
            state='PROGRESS',
            meta={
                'current': 0,
                'total': 3,
                'status': 'Fetching document content',
                'job_id': job_id
            }
        )
        
        # Fetch document content from Supabase
        from supabase import create_client, Client
        
        supabase_url = os.getenv('SUPABASE_URL')
        supabase_key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
        
        if not supabase_url or not supabase_key:
            raise Exception('Missing Supabase credentials')
        
        supabase: Client = create_client(supabase_url, supabase_key)
        
        # Fetch document - use content or summary for reading companion
        response = supabase.table('documents').select('content, summary').eq('id', document_id).execute()
        if not response.data or len(response.data) == 0:
            raise Exception('Document not found')
        
        document = response.data[0]
        # For reading companion, prefer content over summary, but use summary if content is not available
        document_content = document.get('content') or document.get('summary') or ''
        
        if not document_content.strip():
            raise Exception('Document has no content to generate reading companion audio from')
        
        # Update progress
        self.update_state(
            state='PROGRESS',
            meta={
                'current': 1,
                'total': 3,
                'status': 'Generating reading companion audio',
                'job_id': job_id
            }
        )
        
        # Initialize Google TTS
        # Write TTS credentials to file if GOOGLE_TTS_CREDENTIALS_JSON is set
        if os.getenv('GOOGLE_TTS_CREDENTIALS_JSON') and not os.getenv('GOOGLE_APPLICATION_CREDENTIALS'):
            key_path = '/tmp/google-tts-key.json'
            with open(key_path, 'w') as f:
                f.write(os.getenv('GOOGLE_TTS_CREDENTIALS_JSON'))
            os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = key_path
        
        client_tts = texttospeech.TextToSpeechClient()
        
        # Helper to split text into <=5000 byte chunks
        def split_text_by_bytes(text, max_bytes):
            encoder = text.encode('utf-8')
            chunks = []
            current = ''
            for char in text:
                test = current + char
                if test.encode('utf-8').__sizeof__() > max_bytes:
                    chunks.append(current)
                    current = char
                else:
                    current = test
            if current:
                chunks.append(current)
            return chunks
        
        # Clean the text for better audio output (remove markdown formatting)
        cleaned_content = clean_text_for_tts(document_content)
        
        max_tts_bytes = 5000
        text_chunks = split_text_by_bytes(cleaned_content, max_tts_bytes)
        audio_buffers = []
        
        for chunk in text_chunks:
            response_tts = client_tts.synthesize_speech({
                'input': {'text': chunk},
                'voice': {
                    'language_code': 'en-US',
                    'name': voice,
                    'ssml_gender': texttospeech.SsmlVoiceGender.MALE if voice == 'en-US-Studio-Q' else texttospeech.SsmlVoiceGender.FEMALE
                },
                'audio_config': {'audio_encoding': texttospeech.AudioEncoding.MP3},
            })
            
            if not response_tts.audio_content:
                raise Exception('No audio content returned from Google TTS')
            
            audio_buffers.append(response_tts.audio_content)
        
        audio_buffer = b''.join(audio_buffers)
        
        # Update progress
        self.update_state(
            state='PROGRESS',
            meta={
                'current': 2,
                'total': 3,
                'status': 'Uploading reading companion audio to storage',
                'job_id': job_id
            }
        )
        
        # Upload to Supabase Storage with reading companion naming
        file_path = f'audio/{document_id}-reading-{int(time.time())}.mp3'
        
        upload_response = supabase.storage.from_('documents').upload(
            file_path,
            audio_buffer,
            {'content-type': 'audio/mpeg', 'upsert': 'true'}
        )
        
        # Upload was successful (HTTP 200 OK indicates success)
        print(f'Job {job_id}: ✅ Reading companion audio uploaded to storage: {file_path}')
        
        # Update document with reading companion audio URL
        update_response = supabase.table('documents').update({
            'reading_companion_audio_url': file_path,
            'updated_at': datetime.now().isoformat()
        }).eq('id', document_id).execute()
        
        print(f'Job {job_id}: ✅ Document updated with reading companion audio URL: {file_path}')
        
        # Update progress
        self.update_state(
            state='PROGRESS',
            meta={
                'current': 3,
                'total': 3,
                'status': 'Reading companion audio generation completed',
                'job_id': job_id
            }
        )
        
        # Store results via webhook
        try:
            webhook_url = os.getenv('WEBHOOK_URL', 'https://studycompanion.io/api/update-job-results')
            webhook_data = {
                'job_id': job_id,
                'user_id': user_id,
                'status': 'completed',
                'result': {
                    'audio_url': file_path,
                    'content_length': len(document_content),
                    'is_reading_companion': True,
                    'generated_script': False
                },
                'processing_time': time.time(),
                'completed_at': datetime.now().isoformat()
            }
            
            response = requests.post(webhook_url, json=webhook_data, timeout=30)
            if response.status_code == 200:
                print(f'Job {job_id}: ✅ Results stored in database')
            else:
                print(f'Job {job_id}: ⚠️ Failed to store results in database: {response.status_code}')
        except Exception as e:
            print(f'Job {job_id}: ⚠️ Error storing results in database: {str(e)}')
        
        return {
            'status': 'completed',
            'result': {
                'audio_url': file_path,
                'content_length': len(document_content),
                'is_reading_companion': True,
                'generated_script': False
            },
            'processing_time': time.time(),
            'completed_at': datetime.now().isoformat(),
            'job_id': job_id,
            'user_id': user_id
        }
        
    except Exception as e:
        print(f'Job {job_id}: ❌ Reading companion audio generation failed: {str(e)}')
        return {
            'status': 'failed',
            'error': str(e),
            'failed_at': datetime.now().isoformat(),
            'job_id': job_id,
            'user_id': user_id
        } 