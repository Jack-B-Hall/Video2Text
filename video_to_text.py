#!/usr/bin/env python3
import os
import sys
import subprocess
import tempfile
import json
import re
import argparse
from pathlib import Path
import PyPDF2
import time
import ollama
import torch
import whisper
import signal
from fpdf import FPDF
from PIL import Image
import datetime

def signal_handler(sig, frame):
    print("\nScript interrupted. Exiting gracefully...")
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

def format_timestamp(seconds):
    """Convert seconds to HH:MM:SS format."""
    return str(datetime.timedelta(seconds=int(seconds)))

def extract_audio_from_video(video_path, audio_path):
    """Extract audio from video file using ffmpeg."""
    print(f"Extracting audio from {video_path}...")
    cmd = [
        'ffmpeg',
        '-i', video_path,
        '-q:a', '0',
        '-map', 'a',
        '-y',  # Overwrite output file if it exists
        audio_path
    ]
    subprocess.run(cmd, check=True)

def convert_audio_to_wav(mp3_path, wav_path):
    """Convert audio to WAV format for better compatibility."""
    print(f"Converting audio to WAV format...")
    cmd = [
        'ffmpeg',
        '-i', mp3_path,
        '-acodec', 'pcm_s16le',
        '-ar', '16000',
        '-ac', '1',
        '-y',
        wav_path
    ]
    subprocess.run(cmd, check=True)

def extract_screenshot(video_path, output_path, timestamp):
    """Extract a screenshot from the video at the given timestamp."""
    cmd = [
        'ffmpeg',
        '-ss', timestamp,
        '-i', video_path,
        '-frames:v', '1',
        '-q:v', '2',
        '-y',
        output_path
    ]
    subprocess.run(cmd, check=True)
    
    # Verify image was created
    if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
        print(f"Warning: Failed to extract screenshot at {timestamp}")
        return False
    return True

def split_audio_into_chunks(audio_path, chunk_dir, chunk_duration=300):
    """Split audio into smaller chunks for processing."""
    print(f"Splitting audio into {chunk_duration}-second chunks...")
    os.makedirs(chunk_dir, exist_ok=True)
    
    # Get total duration of the audio file
    cmd = [
        'ffprobe', 
        '-v', 'error', 
        '-show_entries', 'format=duration', 
        '-of', 'json', 
        audio_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    duration = float(json.loads(result.stdout)['format']['duration'])
    
    # Calculate number of chunks
    num_chunks = int(duration / chunk_duration) + 1
    chunk_files = []
    timestamps = []
    
    # Split audio into chunks
    for i in range(num_chunks):
        chunk_path = os.path.join(chunk_dir, f"chunk_{i:03d}.wav")
        start_time = i * chunk_duration
        
        cmd = [
            'ffmpeg',
            '-i', audio_path,
            '-ss', str(start_time),
            '-t', str(chunk_duration),
            '-c:a', 'pcm_s16le',
            '-ar', '16000',
            '-ac', '1',
            '-y',
            chunk_path
        ]
        subprocess.run(cmd, check=True)
        chunk_files.append(chunk_path)
        timestamps.append(start_time)
    
    return chunk_files, timestamps

def extract_text_from_pdf(pdf_path):
    """Extract text from PDF to use as context for transcription."""
    print(f"Extracting text from {pdf_path}...")
    pdf_text = ""
    with open(pdf_path, 'rb') as file:
        reader = PyPDF2.PdfReader(file)
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:  # Only add if text was successfully extracted
                pdf_text += page_text + "\n"
    return pdf_text

def transcribe_audio_chunk_with_whisper(audio_chunk, model_size="base", device="cpu"):
    """Transcribe audio chunk using Whisper model."""
    print(f"Transcribing {audio_chunk} with Whisper ({model_size} model on {device})...")
    
    try:
        # Load the model
        model = whisper.load_model(model_size, device=device)
        
        # Transcribe the audio
        result = model.transcribe(audio_chunk, fp16=(device == "cuda"))
        
        # Return the transcript with segment-level timestamps
        return result["text"], result.get("segments", [])
    except Exception as e:
        print(f"Error transcribing chunk {audio_chunk}: {e}")
        raise  # Re-raise the exception to stop processing

def improve_transcription_with_ollama(transcription, model_name, pdf_context=None, options=None):
    """Use Ollama to improve/correct a transcription with the ollama package."""
    if not transcription:
        raise ValueError("No valid transcription to improve")
    
    print(f"Improving transcription with Ollama using {model_name}...")
    
    # Create a prompt with context if available
    prompt = "I have a transcription of a medical lecture about the hypothalamus and pituitary gland that may contain inaccuracies. "
    prompt += "Please correct any errors, fill in any gaps where words don't make sense, and ensure all medical terminology is accurate. "
    
    if pdf_context and pdf_context.strip():
        prompt += "Use this reference material to help with technical terms and context:\n" + pdf_context[:2000] + "\n\n"
    
    prompt += "Original transcription:\n\n" + transcription + "\n\n"
    prompt += "Please output only the improved transcription without explanations or notes."
    
    try:
        ollama_options = options or {"temperature": 0.1}
        # Use the ollama Python package
        response = ollama.generate(model=model_name, prompt=prompt, options=ollama_options)
        return response['response']
    except Exception as e:
        print(f"Error improving transcription with Ollama: {e}")
        print("Returning original transcription instead.")
        return transcription  # Fall back to original rather than crashing

def create_pdf_with_screenshots(transcripts, screenshot_paths, output_pdf_path):
    """Create a PDF with screenshots and corresponding transcripts."""
    print(f"Creating PDF with screenshots and transcripts...")
    
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    
    # Set title
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, "Lecture Transcript with Visual References", ln=True, align='C')
    pdf.ln(5)
    
    # Add each screenshot and transcript
    for i, (timestamp, transcript) in enumerate(transcripts):
        # Add timestamp header
        pdf.set_font("Arial", 'B', 14)
        pdf.cell(0, 10, f"Time: {timestamp}", ln=True)
        
        # Add screenshot if available
        screenshot_path = screenshot_paths.get(timestamp)
        if screenshot_path and os.path.exists(screenshot_path):
            try:
                # Get image dimensions
                with Image.open(screenshot_path) as img:
                    width, height = img.size
                
                # Calculate aspect ratio and resize if needed
                pdf_width = 180  # PDF width in mm that we want to use
                pdf_height = pdf_width * height / width
                
                # Add image
                pdf.image(screenshot_path, x=15, w=pdf_width)
                pdf.ln(5)
            except Exception as e:
                print(f"Warning: Could not add image {screenshot_path} to PDF: {e}")
        
        # Add transcript text
        pdf.set_font("Arial", size=11)
        
        # Handle special characters and encode text properly
        clean_transcript = transcript.replace('\n', ' ').strip()
        pdf.multi_cell(0, 5, clean_transcript)
        
        # Add spacing between entries
        pdf.ln(10)
        
        # Add a new page every 2 entries or if the current page is getting full
        if (i + 1) % 2 == 0 or pdf.get_y() > 250:
            pdf.add_page()
    
    # Save the PDF
    try:
        pdf.output(output_pdf_path)
        print(f"PDF saved to {output_pdf_path}")
        return True
    except Exception as e:
        print(f"Error saving PDF: {e}")
        return False

def check_ollama_gpu_model_availability(requested_model=None):
    """Check available Ollama models and prefer GPU-compatible ones."""
    try:
        models = ollama.list()
        available_models = [model['name'] for model in models.get('models', [])]
        
        print(f"Available Ollama models: {', '.join(available_models)}")
        
        # Check if requested model is available first
        if requested_model and requested_model in available_models:
            return requested_model
        
        # Look for good default models
        for model_name in ["llama3.1:8b", "llama3.2:3b", "llama3.2", "mistral"]:
            if any(model_name in m for m in available_models):
                matching_models = [m for m in available_models if model_name in m]
                return matching_models[0]
        
        # Just return the first available model
        if available_models:
            return available_models[0]
        else:
            return None
    except Exception as e:
        print(f"Error checking Ollama models: {e}")
        return None

def parse_arguments():
    parser = argparse.ArgumentParser(description="Transcribe video to text with timestamps and screenshots.")
    parser.add_argument("video_file", help="Path to the video file to transcribe")
    parser.add_argument("--pdf", help="Optional PDF file for context", default=None)
    parser.add_argument("--output", help="Output file path for transcript (default: video filename with .txt extension)", default=None)
    parser.add_argument("--output-pdf", help="Output file path for PDF with screenshots (default: video filename with _transcript.pdf extension)", default=None)
    parser.add_argument("--whisper-model", help="Whisper model size (tiny, base, small, medium, large)", default="base")
    parser.add_argument("--ollama-model", help="Ollama model to use for transcription improvement", default=None)
    parser.add_argument("--no-gpu", help="Disable GPU usage for both Whisper and Ollama", action="store_true")
    parser.add_argument("--chunk-duration", help="Duration of each audio chunk in seconds", type=int, default=300)
    parser.add_argument("--timestamp-interval", help="Interval in seconds to create timestamps", type=int, default=60)
    parser.add_argument("--skip-ollama", help="Skip Ollama improvement and use raw Whisper output", action="store_true")
    parser.add_argument("--skip-pdf", help="Skip PDF generation", action="store_true")
    return parser.parse_args()

def main():
    args = parse_arguments()
    
    video_path = args.video_file
    pdf_path = args.pdf
    
    # Set output paths
    if args.output:
        output_path = args.output
    else:
        output_path = os.path.splitext(video_path)[0] + ".txt"
    
    if args.output_pdf:
        output_pdf_path = args.output_pdf
    else:
        output_pdf_path = os.path.splitext(video_path)[0] + "_transcript.pdf"
    
    # Determine device for Whisper
    if args.no_gpu:
        print("Forcing CPU-only mode as requested")
        device = "cpu"
        # Set environment variable for Ollama to use CPU
        os.environ["OLLAMA_HOST"] = "http://localhost:11434"
        os.environ["CUDA_VISIBLE_DEVICES"] = ""
    else:
        device = "cuda" if torch.cuda.is_available() else "cpu"
    
    print(f"Using device: {device} for Whisper")
    
    # Check available Ollama models if needed
    if not args.skip_ollama and not args.ollama_model:
        detected_model = check_ollama_gpu_model_availability()
        if detected_model:
            print(f"No Ollama model specified. Using detected model: {detected_model}")
            args.ollama_model = detected_model
        else:
            print("No suitable Ollama model found. Will try to use 'llama3.1:8b'")
            args.ollama_model = "llama3.1:8b"
    
    # Test Ollama connection if needed
    if not args.skip_ollama:
        try:
            ollama.list()
        except Exception as e:
            print(f"Error connecting to Ollama: {e}")
            print("Please make sure Ollama is running and accessible")
            if not args.skip_ollama:
                print("Continuing without Ollama improvement")
                args.skip_ollama = True
    
    # Create temporary directory for processing
    with tempfile.TemporaryDirectory() as temp_dir:
        # Directory for screenshots
        screenshots_dir = os.path.join(temp_dir, "screenshots")
        os.makedirs(screenshots_dir, exist_ok=True)
        
        # Extract audio from video
        audio_path = os.path.join(temp_dir, "audio.mp3")
        extract_audio_from_video(video_path, audio_path)
        
        # Convert to WAV
        wav_path = os.path.join(temp_dir, "audio.wav")
        convert_audio_to_wav(audio_path, wav_path)
        
        # Split audio into chunks
        chunk_dir = os.path.join(temp_dir, "chunks")
        audio_chunks, start_times = split_audio_into_chunks(wav_path, chunk_dir, args.chunk_duration)
        
        # Extract PDF text if available
        pdf_context = None
        if pdf_path:
            pdf_context = extract_text_from_pdf(pdf_path)
            # Trim if very long
            if pdf_context and len(pdf_context) > 10000:
                print(f"PDF content is long ({len(pdf_context)} chars). Trimming to 10,000 chars.")
                pdf_context = pdf_context[:10000]
        
        # Transcribe chunks and keep track of timestamps
        full_transcription = ""
        timestamped_chunks = []
        screenshots = {}
        
        # Open output file to write as we go
        with open(output_path, 'w') as f:
            for i, (chunk, start_time) in enumerate(zip(audio_chunks, start_times)):
                print(f"Processing chunk {i+1}/{len(audio_chunks)}...")
                try:
                    # First get raw transcription from Whisper with segments
                    raw_transcription, segments = transcribe_audio_chunk_with_whisper(
                        chunk, model_size=args.whisper_model, device=device
                    )
                    
                    # Process each segment to create timestamped entries
                    if segments:
                        for segment in segments:
                            segment_start = segment.get('start', 0) + start_time
                            segment_text = segment.get('text', '').strip()
                            
                            if not segment_text:
                                continue
                                
                            # Create timestamp string
                            timestamp = format_timestamp(segment_start)
                            
                            # Only take periodic screenshots based on timestamp_interval
                            if int(segment_start) % args.timestamp_interval < 5:  # Within 5 seconds of interval
                                screenshot_path = os.path.join(screenshots_dir, f"screenshot_{int(segment_start):06d}.jpg")
                                if extract_screenshot(video_path, screenshot_path, timestamp):
                                    screenshots[timestamp] = screenshot_path
                            
                            # Improve transcription with Ollama if requested
                            if not args.skip_ollama:
                                try:
                                    improved_text = improve_transcription_with_ollama(
                                        segment_text, args.ollama_model, pdf_context
                                    )
                                    segment_text = improved_text
                                except Exception as e:
                                    print(f"Failed to improve segment with Ollama: {e}")
                            
                            # Add to timestamped chunks
                            timestamped_chunks.append((timestamp, segment_text))
                            
                            # Write to file
                            entry = f"[{timestamp}] {segment_text}\n\n"
                            f.write(entry)
                            full_transcription += entry
                    else:
                        # Fallback if no segments
                        timestamp = format_timestamp(start_time)
                        
                        # Improve with Ollama if requested
                        if not args.skip_ollama:
                            try:
                                improved_text = improve_transcription_with_ollama(
                                    raw_transcription, args.ollama_model, pdf_context
                                )
                                transcription = improved_text
                            except Exception as e:
                                print(f"Failed to improve with Ollama: {e}")
                                transcription = raw_transcription
                        else:
                            transcription = raw_transcription
                        
                        # Take a screenshot
                        screenshot_path = os.path.join(screenshots_dir, f"screenshot_{int(start_time):06d}.jpg")
                        if extract_screenshot(video_path, screenshot_path, timestamp):
                            screenshots[timestamp] = screenshot_path
                        
                        # Add to timestamped chunks
                        timestamped_chunks.append((timestamp, transcription))
                        
                        # Write to file
                        entry = f"[{timestamp}] {transcription}\n\n"
                        f.write(entry)
                        full_transcription += entry
                        
                except Exception as e:
                    print(f"Error processing chunk {i+1}: {e}")
                    continue  # Try to continue with next chunk
        
        print(f"Transcript saved to {output_path}")
        
        # Create PDF with screenshots and transcripts if requested
        if not args.skip_pdf:
            pdf_success = create_pdf_with_screenshots(timestamped_chunks, screenshots, output_pdf_path)
            if pdf_success:
                print(f"PDF with screenshots saved to {output_pdf_path}")
            else:
                print("Failed to create PDF with screenshots")
                
        # Clean up
        print("Cleaning up temporary files...")

if __name__ == "__main__":
    main()