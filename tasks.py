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

def rate_limit_delay(page_number, total_pages):
    """Add intelligent delays to prevent OpenAI rate limiting"""
    # Add 1-second delay between pages to stay well under rate limits
    # OpenAI allows 3,000 requests per minute, so 1 second between requests is very safe
    if page_number < total_pages:  # Don't delay after the last page
        time.sleep(1)
        print(f"Rate limiting: Added 1-second delay after page {page_number}")

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
    
    # NEW: Split very long sentences for TTS compatibility
    # Split sentences that are longer than 200 characters
    sentences = re.split(r'([.!?]+)\s+', clean)
    processed_sentences = []
    
    for i in range(0, len(sentences), 2):
        if i + 1 < len(sentences):
            sentence = sentences[i] + sentences[i + 1]
        else:
            sentence = sentences[i]
        
        # If sentence is too long, split it further
        if len(sentence) > 200:
            # Try to split on natural break points first
            if ',' in sentence:
                parts = sentence.split(', ')
                for part in parts:
                    if part.strip():
                        processed_sentences.append(part.strip() + '.')
            elif ';' in sentence:
                parts = sentence.split('; ')
                for part in parts:
                    if part.strip():
                        processed_sentences.append(part.strip() + '.')
            elif ':' in sentence and not re.match(r'^(R|S):', sentence.strip()):
                # Don't split on colons if it's a speaker marker (R: or S:)
                parts = sentence.split(': ')
                for part in parts:
                    if part.strip():
                        processed_sentences.append(part.strip() + '.')
            else:
                # Force split at word boundaries around 150 characters
                words = sentence.split()
                current_part = ""
                for word in words:
                    if len(current_part + " " + word) > 150:
                        if current_part:
                            processed_sentences.append(current_part.strip() + '.')
                        current_part = word
                    else:
                        current_part += " " + word if current_part else word
                if current_part:
                    processed_sentences.append(current_part.strip() + '.')
        else:
            if sentence.strip():
                processed_sentences.append(sentence.strip())
    
    # Join sentences back together
    clean = ' '.join(processed_sentences)
    
    # Remove extra spaces and normalize whitespace
    clean = re.sub(r'\s{2,}', ' ', clean)
    # Remove extra newlines
    clean = re.sub(r'\n{3,}', '\n\n', clean)
    
    return clean.strip()

def clean_text_for_tts_preserve_speakers(text):
    """Clean text for TTS while preserving R: and S: speaker markers"""
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
    # Remove headings (##, ###, etc.)
    clean = re.sub(r'^#+\s?', '', clean, flags=re.MULTILINE)
    # Remove bold/italic (**text**, *text*, __text__, _text_)
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
    
    # Split into lines to preserve speaker markers
    lines = clean.split('\n')
    processed_lines = []
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # Check if this line starts with R: or S:
        if re.match(r'^(R|S):', line):
            # This is a speaker line - preserve it exactly
            processed_lines.append(line)
        else:
            # This is dialogue - clean it normally
            # Split very long sentences for TTS compatibility
            if len(line) > 200:
                # Try to split on natural break points
                if ',' in line:
                    parts = line.split(', ')
                    for part in parts:
                        if part.strip():
                            processed_lines.append(part.strip() + '.')
                elif ';' in line:
                    parts = line.split('; ')
                    for part in parts:
                        if part.strip():
                            processed_lines.append(part.strip() + '.')
                else:
                    # Force split at word boundaries around 150 characters
                    words = line.split()
                    current_part = ""
                    for word in words:
                        if len(current_part + " " + word) > 150:
                            if current_part:
                                processed_lines.append(current_part.strip() + '.')
                            current_part = word
                        else:
                            current_part += " " + word if current_part else word
                    if current_part:
                        processed_lines.append(current_part.strip() + '.')
            else:
                if line.strip():
                    processed_lines.append(line.strip())
    
    # Join lines back together
    clean = '\n'.join(processed_lines)
    
    # Remove extra spaces and normalize whitespace
    clean = re.sub(r'\s{2,}', ' ', clean)
    # Remove extra newlines
    clean = re.sub(r'\n{3,}', '\n\n', clean)
    
    return clean.strip()

def generate_2speaker_podcast_script_chunk(content, chunk_index, total_chunks, speaker_1_name="R", speaker_2_name="S"):
    """Generate 2-speaker podcast script for a single chunk"""
    if not client:
        raise Exception('OpenAI is not available')
    
    context_info = f' (Part {chunk_index + 1} of {total_chunks})' if total_chunks > 1 else ''
    
    prompt = f"""Create a natural, engaging 2-person podcast conversation script about this educational content.

**REQUIREMENTS:**
- Two speakers: {speaker_1_name} (more knowledgeable, explains concepts) and {speaker_2_name} (curious learner, asks questions)
- Natural conversation flow with interruptions, laughter, and organic dialogue
- Vary speaking patterns: sometimes {speaker_1_name} explains, sometimes {speaker_2_name} has insights
- Include natural speech patterns like "You know what I mean?", "That's fascinating!", "Wait, let me get this straight..."
- Make it sound like two friends having an engaging discussion, not a formal presentation
- Avoid any meta-language about "this document" or "this content" - speak naturally
- Keep each speaker's lines reasonably short for TTS processing
- Characters can call each other by names in the dialogue, but speakers are always labeled as {speaker_1_name}: and {speaker_2_name}:

**FORMAT:**
{speaker_1_name}: [dialogue]
{speaker_2_name}: [dialogue]
{speaker_1_name}: [dialogue]
... and so on

**CONTENT TO DISCUSS:**
{content}

{context_info}

Make this sound like a real podcast conversation that would keep listeners engaged."""

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert script writer who creates natural, engaging 2-person podcast conversations. Focus on making dialogue sound authentic and conversational."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            max_tokens=2000,
            temperature=0.8,
        )

        generated_script = response.choices[0].message.content
        if not generated_script:
            raise Exception(f'No podcast script generated from ChatGPT for chunk {chunk_index + 1}')

        print(f'2-speaker podcast script chunk {chunk_index + 1}/{total_chunks} generated successfully')
        return generated_script
    except Exception as error:
        print(f'Error generating 2-speaker podcast script for chunk {chunk_index + 1}: {error}')
        raise error

def generate_2speaker_podcast_script(content):
    """Generate 2-speaker podcast-style script using ChatGPT with chunking"""
    if not client:
        raise Exception('OpenAI is not available')

    # Check if content is small enough to process in one go
    word_count = count_words(content)
    
    if word_count <= 4000:
        # Small content - process directly
        return generate_2speaker_podcast_script_chunk(content, 0, 1)

    # Large content - use chunking
    print(f'Content is {word_count} words, using chunking system for 2-speaker podcast...')
    
    chunks = chunk_content(content, target_chunk_size=3000, min_chunk_size=1000, max_chunk_size=4000, overlap_words=100)

    print(f'Split content into {len(chunks)} chunks for 2-speaker podcast')

    # Process chunks sequentially
    script_chunks = []
    
    for i, chunk in enumerate(chunks):
        print(f'Processing 2-speaker podcast chunk {i + 1}/{len(chunks)} ({chunk["word_count"]} words)...')
        
        try:
            script_chunk = generate_2speaker_podcast_script_chunk(chunk['content'], i, len(chunks))
            script_chunks.append(script_chunk)
            
            # Add a small delay between chunks to avoid rate limiting
            if i < len(chunks) - 1:
                time.sleep(1)
        except Exception as error:
            print(f'Failed to process 2-speaker podcast chunk {i + 1}: {error}')
            raise Exception(f'Failed to process 2-speaker podcast chunk {i + 1}: {str(error)}')

    # Combine script chunks with proper spacing
    combined_script = '\n\n'.join(script_chunks)
    print(f'Successfully generated 2-speaker podcast script from {len(chunks)} chunks')
    
    return combined_script

def parse_speaker_segments(script):
    """Parse podcast script to identify speaker changes and text"""
    import re
    
    print(f'🔍 DEBUG - Parsing script with {len(script)} characters')
    print(f'🔍 DEBUG - Script preview: {script[:300]}...')
    
    # Pattern to match speaker lines: "R: text" or "S: text"
    pattern = r'^(R|S):\s*(.+?)(?=\n[R|S]:|$)'
    
    segments = []
    lines = script.split('\n')
    current_speaker = None
    current_text = ""
    
    print(f'🔍 DEBUG - Found {len(lines)} lines to process')
    
    for i, line in enumerate(lines):
        line = line.strip()
        if not line:
            continue
            
        # Check if this line starts with R: or S:
        match = re.match(r'^(R|S):\s*(.+)', line)
        if match:
            print(f'🔍 DEBUG - Line {i+1}: Found speaker {match.group(1)} with text: {match.group(2)[:50]}...')
            # Save previous segment if exists
            if current_speaker and current_text:
                segments.append({
                    'speaker': current_speaker,
                    'text': current_text.strip()
                })
            
            # Start new segment
            current_speaker = match.group(1)  # R or S
            current_text = match.group(2)
        else:
            # Continue current speaker's text
            if current_speaker:
                current_text += " " + line
    
    # Add the last segment
    if current_speaker and current_text:
        segments.append({
            'speaker': current_speaker,
            'text': current_text.strip()
        })
    
    print(f'🔍 DEBUG - Parsed {len(segments)} speaker segments')
    for i, seg in enumerate(segments):
        print(f'🔍 DEBUG - Segment {i+1}: {seg["speaker"]}: {seg["text"][:50]}...')
    
    return segments

def generate_2speaker_tts_audio(script, voice_male, voice_female, job_id):
    """Generate TTS audio with multiple speakers using Google's Multi-Speaker TTS"""
    
    # Parse the script to identify speaker changes
    speaker_segments = parse_speaker_segments(script)
    
    # Convert to Google's Multi-Speaker format
    turns = []
    for segment in speaker_segments:
        speaker = segment['speaker']
        text = segment['text']
        
        # Map speaker names to Google's speaker identifiers
        if speaker == "R":  # Male speaker
            google_speaker = "R"
        else:  # speaker == "S" - Female speaker
            google_speaker = "S"
        
        turns.append({
            'text': text,
            'speaker': google_speaker
        })
    
    print(f'Job {job_id}: Generated {len(turns)} speaker turns for Multi-Speaker TTS')
    
    # Use Google's Multi-Speaker TTS
    try:
        print(f'Job {job_id}: 🔍 Attempting to import Google Multi-Speaker TTS...')
        # Import the beta version for multi-speaker support
        from google.cloud import texttospeech_v1beta1 as texttospeech
        print(f'Job {job_id}: ✅ Successfully imported Google Multi-Speaker TTS')
        
        client_tts = texttospeech.TextToSpeechClient()
        
        # Create multi-speaker markup
        multi_speaker_markup = texttospeech.MultiSpeakerMarkup(
            turns=[
                texttospeech.MultiSpeakerMarkup.Turn(
                    text=turn['text'],
                    speaker=turn['speaker']
                ) for turn in turns
            ]
        )
        
        # Set the text input to be synthesized
        synthesis_input = texttospeech.SynthesisInput(
            multi_speaker_markup=multi_speaker_markup
        )
        
        # Build the voice request - use the multi-speaker voice
        voice = texttospeech.VoiceSelectionParams(
            language_code="en-US",
            name="en-US-Studio-MultiSpeaker"
        )
        
        # Select the type of audio file you want returned
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3
        )
        
        print(f'Job {job_id}: Calling Google Multi-Speaker TTS API...')
        
        # Perform the text-to-speech request
        response = client_tts.synthesize_speech(
            input=synthesis_input,
            voice=voice,
            audio_config=audio_config
        )
        
        if not response.audio_content:
            raise Exception('No audio content returned from Google Multi-Speaker TTS')
        
        print(f'Job {job_id}: ✅ Multi-Speaker TTS completed successfully')
        return response.audio_content
        
    except ImportError:
        print(f'Job {job_id}: ⚠️ Multi-Speaker TTS not available, falling back to single-speaker with voice switching')
        # Fallback to the old method if multi-speaker not available
        return generate_2speaker_tts_audio_fallback(script, voice_male, voice_female, job_id)
    except Exception as e:
        print(f'Job {job_id}: ❌ Multi-Speaker TTS failed: {str(e)}, falling back to single-speaker')
        # Fallback to the old method if multi-speaker fails
        return generate_2speaker_tts_audio_fallback(script, voice_male, voice_female, job_id)

def generate_2speaker_tts_audio_fallback(script, voice_male, voice_female, job_id):
    """Fallback method for 2-speaker TTS when multi-speaker is not available"""
    print(f'Job {job_id}: Using fallback 2-speaker TTS method')
    
    # Parse the script to identify speaker changes
    speaker_segments = parse_speaker_segments(script)
    
    audio_buffers = []
    
    for segment in speaker_segments:
        speaker = segment['speaker']
        text = segment['text']
        
        # Determine which voice to use
        if speaker == "R":  # Male speaker
            voice = voice_male
            gender = texttospeech.SsmlVoiceGender.MALE
        else:  # speaker == "S" - Female speaker
            voice = voice_female
            gender = texttospeech.SsmlVoiceGender.FEMALE
        
        # Generate audio for this speaker segment
        audio_buffer = generate_speaker_audio(text, voice, gender)
        audio_buffers.append(audio_buffer)
        
        # Add a small pause between speakers for natural flow
        if len(audio_buffers) > 1:
            pause_buffer = generate_pause_audio(0.3)  # 300ms pause
            audio_buffers.append(pause_buffer)
    
    # Consolidate all audio segments
    consolidated_audio = b''.join(audio_buffers)
    return consolidated_audio

def generate_speaker_audio(text, voice, gender):
    """Generate TTS audio for a specific speaker"""
    client_tts = texttospeech.TextToSpeechClient()
    
    # Clean text for TTS
    cleaned_text = clean_text_for_tts(text)
    
    # Split into TTS-friendly chunks if needed
    text_chunks = split_text_by_bytes(cleaned_text, 5000)
    audio_buffers = []
    
    for chunk in text_chunks:
        response_tts = client_tts.synthesize_speech({
            'input': {'text': chunk},
            'voice': {
                'language_code': 'en-US',
                'name': voice,
                'ssml_gender': gender
            },
            'audio_config': {'audio_encoding': texttospeech.AudioEncoding.MP3},
        })
        
        if response_tts.audio_content:
            audio_buffers.append(response_tts.audio_content)
    
    return b''.join(audio_buffers)

def generate_pause_audio(duration_seconds):
    """Generate a brief pause between speakers"""
    # For now, return empty buffer - this can be enhanced later with actual pause generation
    return b''

def split_text_by_bytes(text, max_bytes):
    """Helper to split text into <=5000 byte chunks"""
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

def split_text_for_tts_safety(text, max_chars=150):
    """Additional safety function to split text for TTS compatibility"""
    if not text or len(text) <= max_chars:
        return [text]
    
    # Split on sentence boundaries first
    import re
    sentences = re.split(r'([.!?]+)\s+', text)
    chunks = []
    
    for i in range(0, len(sentences), 2):
        if i + 1 < len(sentences):
            sentence = sentences[i] + sentences[i + 1]
        else:
            sentence = sentences[i]
        
        if len(sentence) <= max_chars:
            chunks.append(sentence)
        else:
            # Split long sentences further
            words = sentence.split()
            current_chunk = ""
            
            for word in words:
                if len(current_chunk + " " + word) > max_chars:
                    if current_chunk:
                        chunks.append(current_chunk.strip())
                    current_chunk = word
                else:
                    current_chunk += " " + word if current_chunk else word
            
            if current_chunk:
                chunks.append(current_chunk.strip())
    
    return chunks

def parse_content_into_pages(content):
    """Parse document content into pages based on 'Page X' patterns"""
    if not content:
        return []
    
    import re
    
    # Look for patterns like "Page X", "Page X:", "Page X -", etc.
    page_pattern = r'Page\s+(\d+)\s*(?:Analysis|:|-\s*|\.\s*|$)' 
    matches = list(re.finditer(page_pattern, content, re.IGNORECASE))
    
    if len(matches) == 0:
        # No page markers found, treat as single page
        return [{
            'pageNumber': 1,
            'content': content,
            'title': 'Document Content'
        }]
    
    pages = []
    
    # Extract page content with boundary handling
    for i in range(len(matches)):
        match = matches[i]
        page_number = int(match.group(1))
        
        if i == 0:
            # First page: start from beginning of content
            start_index = 0
            end_index = matches[i + 1].start() if i + 1 < len(matches) else len(content)
            
            page_content = content[start_index:end_index].strip()
            lines = page_content.split('\n')
            title = lines[0].strip() if lines else f'Page {page_number}'
            
            pages.append({
                'pageNumber': page_number,
                'content': page_content,
                'title': title
            })
        else:
            # Subsequent pages: start from the page marker
            start_index = match.start()
            end_index = matches[i + 1].start() if i + 1 < len(matches) else len(content)
            
            page_content = content[start_index:end_index].strip()
            lines = page_content.split('\n')
            title = lines[0].strip() if lines else f'Page {page_number}'
            
            pages.append({
                'pageNumber': page_number,
                'content': page_content,
                'title': title
            })
    
    return pages

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

**IMPORTANT FORMATTING NOTE:** When creating headings or section titles, always end them with a colon (:). For example: "Main Idea:", "Key Insights:", "Expert Analysis:", etc.

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

**IMPORTANT FORMATTING NOTE:** When creating headings or section titles, always end them with a colon (:). For example: "Main Idea:", "Key Insights:", "Expert Analysis:", etc.

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
    """Process entire document by analyzing pages sequentially with rate limiting"""
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
        all_page_analyses = []
        
        # Process each page sequentially (your original approach)
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
            
            # Analyze this page directly (synchronous)
            try:
                page_data = analyze_page_sync(img_base64, page_num, num_pages, file_type, job_id)
                
                if page_data['status'] == 'completed':
                    all_page_analyses.append(f"**Page {page_num} Analysis:**\n{page_data['analysis']}\n\n")
                else:
                    all_page_analyses.append(f"**Page {page_num} Analysis:**\nError processing this page: {page_data['error']}\n\n")
            except Exception as e:
                print(f"Job {job_id}: ❌ Error analyzing page {page_num}: {str(e)}")
                all_page_analyses.append(f"**Page {page_num} Analysis:**\nError processing this page: {str(e)}\n\n")
            
            # Add 1-second delay between pages to prevent OpenAI rate limiting
            if i < len(images_base64) - 1:
                rate_limit_delay(page_num, num_pages)
        
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
def generate_audio_job(self, job_id, document_id, user_id, voice='en-US-Studio-Q', audio_style='single_speaker', pages_data=None):
    """Generate audio from document content using background processing with multiple style options and page-based chunking"""
    try:
        print(f'Job {job_id}: Starting audio generation for document {document_id} with style: {audio_style}')
        
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
                'status': f'Generating {"2-speaker podcast" if audio_style == "2speaker_podcast" else "podcast"} script',
                'job_id': job_id
            }
        )
        
        # Extract page information from document content if not provided
        if not pages_data or len(pages_data) == 0:
            print(f'Job {job_id}: No page data provided, extracting pages from document content...')
            # Parse content into pages based on "Page X" patterns
            pages_data = parse_content_into_pages(document_content)
            print(f'Job {job_id}: Extracted {len(pages_data)} pages from document content')
        
        # Use page-based processing
        print(f'Job {job_id}: Using page-based processing with {len(pages_data)} pages')
        chunks = pages_data
        chunk_type = "pages"
        
        # Generate script for each page
        script_chunks = []
        for i, chunk in enumerate(chunks):
            chunk_content = chunk.get('content', '') or chunk.get('text', '')
            cleaned_chunk = clean_text_for_tts(chunk_content)
            
            if audio_style == '2speaker_podcast':
                script_chunk = generate_2speaker_podcast_script_chunk(cleaned_chunk, i, len(chunks), "R", "S")
                print(f'Job {job_id}: 🔍 DEBUG - 2-speaker script preview: {script_chunk[:200]}...')
            else:
                script_chunk = generate_podcast_script_chunk(cleaned_chunk, i, len(chunks))
            
            script_chunks.append(script_chunk)
            print(f'Job {job_id}: ✅ Script generated for page {chunk.get("pageNumber", i + 1)}')
        
        # Process each page script through TTS separately (page-by-page processing)
        print(f'Job {job_id}: Generated scripts for {len(chunks)} pages, now processing each page through TTS...')
        
        # Update progress
        self.update_state(
            state='PROGRESS',
            meta={
                'current': 2,
                'total': 4,
                'status': f'Generating audio for {len(chunks)} pages',
                'job_id': job_id
            }
        )
        
        # Initialize Google TTS
        if os.getenv('GOOGLE_TTS_CREDENTIALS_JSON') and not os.getenv('GOOGLE_APPLICATION_CREDENTIALS'):
            key_path = '/tmp/google-tts-key.json'
            with open(key_path, 'w') as f:
                f.write(os.getenv('GOOGLE_TTS_CREDENTIALS_JSON'))
            os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = key_path
        
        client_tts = texttospeech.TextToSpeechClient()
        audio_buffers = []
        
        # Process each page script through TTS
        for i, (chunk, script_chunk) in enumerate(zip(chunks, script_chunks)):
            page_number = chunk.get('pageNumber', i + 1)
            print(f'Job {job_id}: Processing TTS for page {page_number}/{len(chunks)}...')
            
            # Update progress for each page
            self.update_state(
                state='PROGRESS',
                meta={
                    'current': 2 + (i / len(chunks)),
                    'total': 4,
                    'status': f'Generating audio for page {page_number}/{len(chunks)}',
                    'job_id': job_id
                }
            )
            
            # Clean and process this page script
            print(f'Job {job_id}: Cleaning text for page {page_number}...')
            if audio_style == '2speaker_podcast':
                # For 2-speaker podcast, preserve speaker markers (R: and S:)
                cleaned_script = clean_text_for_tts_preserve_speakers(script_chunk)
                print(f'Job {job_id}: 🔍 DEBUG - After cleaning (preserving speakers): {cleaned_script[:400]}...')
            else:
                cleaned_script = clean_text_for_tts(script_chunk)
            print(f'Job {job_id}: Page {page_number} script cleaned, length: {len(cleaned_script)} characters')
            
            # Process entire page through TTS (no chunking)
            print(f'Job {job_id}: Processing entire page {page_number} through TTS...')
            
            try:
                print(f'Job {job_id}: Calling Google TTS API for page {page_number}...')
                
                # For 2-speaker podcast, use the specialized multi-speaker function
                if audio_style == '2speaker_podcast':
                    print(f'Job {job_id}: Using 2-speaker podcast TTS processing for page {page_number}...')
                    print(f'Job {job_id}: 🔍 DEBUG - Script to process: {cleaned_script[:300]}...')
                    # Use the multi-speaker TTS function for 2-speaker podcast
                    voice_female = 'en-US-Studio-O' if voice == 'en-US-Studio-Q' else 'en-US-Studio-Q'
                    page_audio = generate_2speaker_tts_audio(cleaned_script, voice, voice_female, job_id)
                    audio_buffers.append(page_audio)
                    print(f'Job {job_id}: ✅ Page {page_number} 2-speaker TTS completed successfully')
                    continue
                else:
                    # Single speaker - use regular TTS
                    current_voice = voice
                    current_gender = texttospeech.SsmlVoiceGender.MALE if voice == 'en-US-Studio-Q' else texttospeech.SsmlVoiceGender.FEMALE
                
                response_tts = client_tts.synthesize_speech({
                    'input': {'text': cleaned_script},
                    'voice': {
                        'language_code': 'en-US',
                        'name': current_voice,
                        'ssml_gender': current_gender
                    },
                    'audio_config': {'audio_encoding': texttospeech.AudioEncoding.MP3},
                })
                
                if not response_tts.audio_content:
                    raise Exception('No audio content returned from Google TTS')
                
                audio_buffers.append(response_tts.audio_content)
                print(f'Job {job_id}: ✅ Page {page_number} TTS completed successfully')
                
            except Exception as tts_error:
                print(f'Job {job_id}: ❌ TTS failed for page {page_number}: {str(tts_error)}')
                print(f'Job {job_id}: Error type: {type(tts_error).__name__}')
                print(f'Job {job_id}: Full error details: {str(tts_error)}')
                raise Exception(f'TTS processing failed for page {page_number}: {str(tts_error)}')
            
            # Update progress after each page
            self.update_state(
                state='PROGRESS',
                meta={
                    'current': 2 + ((i + 1) / len(chunks)),
                    'total': 4,
                    'status': f'Completed TTS for {i + 1}/{len(chunks)} pages',
                    'job_id': job_id
                }
            )
        
        # Consolidate all page audio into final audio buffer
        print(f'Job {job_id}: Consolidating audio from {len(audio_buffers)} pages...')
        audio_buffer = b''.join(audio_buffers)
        print(f'Job {job_id}: ✅ All {len(chunks)} pages consolidated into single audio file')
        
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
        file_path = f'audio/{document_id}-{audio_style}-{int(time.time())}.mp3'
        
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
        

        
        return {
            'status': 'completed',
            'result': {
                'audio_url': file_path,
                'pages_processed': len(chunks),
                'audio_style': audio_style,
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

def generate_single_speaker_tts(final_text, voice, job_id):
    """Generate TTS audio for single speaker (existing logic)"""
    # Initialize Google TTS
    # Write TTS credentials to file if GOOGLE_TTS_CREDENTIALS_JSON is set
    if os.getenv('GOOGLE_TTS_CREDENTIALS_JSON') and not os.getenv('GOOGLE_APPLICATION_CREDENTIALS'):
        key_path = '/tmp/google-tts-key.json'
        with open(key_path, 'w') as f:
            f.write(os.getenv('GOOGLE_TTS_CREDENTIALS_JSON'))
        os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = key_path
    
    client_tts = texttospeech.TextToSpeechClient()
    
    # Additional safety: split into TTS-friendly character chunks first
    text_chunks = split_text_for_tts_safety(final_text, 150)
    
    # Further split into TTS-friendly byte chunks
    final_text_chunks = []
    for text_chunk in text_chunks:
        byte_chunks = split_text_by_bytes(text_chunk, 5000)
        final_text_chunks.extend(byte_chunks)
    
    audio_buffers = []
    
    for chunk in final_text_chunks:
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
    return audio_buffer

@celery_app.task(bind=True)
def generate_reading_audio_job(self, job_id, document_id, user_id, voice='en-US-Studio-Q', pages_data=None):
    """Generate reading companion audio from document content using actual page-based chunking"""
    try:
        print(f'Job {job_id}: Starting reading companion audio generation for document {document_id}')
        
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
                'total': 4,
                'status': 'Processing document by pages',
                'job_id': job_id
            }
        )
        
        # Extract page information from document content if not provided
        if not pages_data or len(pages_data) == 0:
            print(f'Job {job_id}: No page data provided, extracting pages from document content...')
            # Parse content into pages based on "Page X" patterns
            pages_data = parse_content_into_pages(document_content)
            print(f'Job {job_id}: Extracted {len(pages_data)} pages from document content')
        
        # Use page-based processing
        print(f'Job {job_id}: Using page-based processing with {len(pages_data)} pages')
        chunks = pages_data
        chunk_type = "pages"
        
        print(f'Job {job_id}: Processing {len(chunks)} {chunk_type}')
        
        # Update progress
        self.update_state(
            state='PROGRESS',
            meta={
                'current': 2,
                'total': 4,
                'status': f'Generating audio for {len(chunks)} {chunk_type}',
                'job_id': job_id
            }
        )
        
        # Initialize Google TTS
        if os.getenv('GOOGLE_TTS_CREDENTIALS_JSON') and not os.getenv('GOOGLE_APPLICATION_CREDENTIALS'):
            key_path = '/tmp/google-tts-key.json'
            with open(key_path, 'w') as f:
                f.write(os.getenv('GOOGLE_TTS_CREDENTIALS_JSON'))
            os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = key_path
        
        client_tts = texttospeech.TextToSpeechClient()
        audio_buffers = []
        
        # Process each chunk/page through TTS
        for i, chunk in enumerate(chunks):
            if chunk_type == "pages":
                # Extract content from page structure
                chunk_content = chunk.get('content', '') or chunk.get('text', '')
                chunk_info = f"page {chunk.get('pageNumber', i + 1)}"
            else:
                # Use content chunk structure - handle both dict and string formats
                if isinstance(chunk, dict):
                    chunk_content = chunk.get('content', '') or chunk.get('text', '')
                else:
                    chunk_content = str(chunk)
                chunk_info = f"chunk {i + 1}"
            
            print(f'Job {job_id}: Processing {chunk_info} ({len(chunk_content)} characters)...')
            
            # Update progress for each chunk
            self.update_state(
                state='PROGRESS',
                meta={
                    'current': 2 + (i / len(chunks)),
                    'total': 4,
                    'status': f'Generating audio for {chunk_info}',
                    'job_id': job_id
                }
            )
            
            # Clean and process this page
            print(f'Job {job_id}: Cleaning text for TTS...')
            chunk_text = clean_text_for_tts(chunk_content)
            print(f'Job {job_id}: Text cleaned, length: {len(chunk_text)} characters')
            
            # Process entire page through TTS (no chunking)
            print(f'Job {job_id}: Processing entire {chunk_info} through TTS...')
            
            try:
                print(f'Job {job_id}: Calling Google TTS API for {chunk_info}...')
                
                # Simple TTS call with better error handling
                response_tts = client_tts.synthesize_speech({
                    'input': {'text': chunk_text},
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
                print(f'Job {job_id}: ✅ {chunk_info} TTS completed successfully')
                
            except Exception as tts_error:
                print(f'Job {job_id}: ❌ TTS failed for {chunk_info}: {str(tts_error)}')
                print(f'Job {job_id}: Error type: {type(tts_error).__name__}')
                print(f'Job {job_id}: Full error details: {str(tts_error)}')
                raise Exception(f'TTS processing failed for {chunk_info}: {str(tts_error)}')
            
            # Update progress after each page
            self.update_state(
                state='PROGRESS',
                meta={
                    'current': 2 + ((i + 1) / len(chunks)),
                    'total': 4,
                    'status': f'Completed {i + 1}/{len(chunks)} pages',
                    'job_id': job_id
                }
            )
        
        # Consolidate all page audio
        print(f'Job {job_id}: Consolidating audio from {len(audio_buffers)} pages...')
        audio_buffer = b''.join(audio_buffers)
        print(f'Job {job_id}: ✅ All {len(chunks)} pages consolidated into single audio file')
        
        # Update progress
        self.update_state(
            state='PROGRESS',
            meta={
                'current': 3,
                'total': 4,
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
                'current': 4,
                'total': 4,
                'status': 'Reading companion audio generation completed',
                'job_id': job_id
            }
        )
        

        
        return {
            'status': 'completed',
            'result': {
                'audio_url': file_path,
                'content_length': len(document_content),
                'chunks_processed': len(chunks),
                'chunk_type': chunk_type,
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