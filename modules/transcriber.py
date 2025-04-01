import os
import tempfile
import shutil
from pathlib import Path
import time
import torch

# Import the correct whisper package
import whisper as openai_whisper
from . import utils

def transcribe_audio_chunk_with_whisper(audio_chunk, model_size="small"):
    """Transcribe audio chunk using Whisper model on CPU."""
    print(f"Transcribing {audio_chunk} with Whisper ({model_size} model on CPU)...")
    
    try:
        # Force CPU by setting environment variable
        os.environ["CUDA_VISIBLE_DEVICES"] = ""
        device = "cpu"
        
        # Load the OpenAI Whisper model - explicitly use openai_whisper
        model = openai_whisper.load_model(model_size, device=device)
        
        # Transcribe the audio with fp16=False to ensure CPU compatibility
        result = model.transcribe(audio_chunk, fp16=False)
        
        # Return the transcript with segment-level timestamps
        return result["text"], result.get("segments", [])
    except Exception as e:
        print(f"Error transcribing chunk {audio_chunk}: {e}")
        raise  # Re-raise the exception to stop processing

def process_video(job_id, video_path, whisper_model="small", 
                  chunk_duration=300, timestamp_interval=30,
                  progress_callback=None):
    """
    Process a video file to generate a transcript with timestamps.
    
    Args:
        job_id: Unique job identifier
        video_path: Path to the video file
        whisper_model: Whisper model size
        chunk_duration: Duration of each audio chunk in seconds
        timestamp_interval: Interval for screenshots in seconds
        progress_callback: Function to call with progress updates
        
    Returns:
        Tuple of (timestamped_chunks, screenshots_dict)
    """
    # Force CPU at the beginning
    os.environ["CUDA_VISIBLE_DEVICES"] = ""
    
    if progress_callback:
        progress_callback(job_id, "Starting video processing...", 0)
    
    # Debug info
    print(f"Processing video: {video_path}")
    print(f"Video exists: {os.path.exists(video_path)}")
    
    # Create temporary directory for processing
    with tempfile.TemporaryDirectory() as temp_dir:
        if progress_callback:
            progress_callback(job_id, "Created temporary directory", 5)
        
        # Directory for screenshots
        screenshots_dir = os.path.join(temp_dir, "screenshots")
        os.makedirs(screenshots_dir, exist_ok=True)
        
        # Extract audio from video
        audio_path = os.path.join(temp_dir, "audio.mp3")
        utils.extract_audio_from_video(video_path, audio_path)
        
        if progress_callback:
            progress_callback(job_id, "Extracted audio from video", 10)
        
        # Convert to WAV format for Whisper
        wav_path = os.path.join(temp_dir, "audio.wav")
        utils.convert_audio_to_wav(audio_path, wav_path)
        
        if progress_callback:
            progress_callback(job_id, "Converted audio to WAV format", 15)
        
        # Split audio into chunks
        chunk_dir = os.path.join(temp_dir, "chunks")
        audio_chunks, start_times, num_chunks = utils.split_audio_into_chunks(wav_path, chunk_dir, chunk_duration)
        
        if progress_callback:
            progress_callback(job_id, f"Split audio into {num_chunks} chunks", 20)
        
        # Transcribe chunks and keep track of timestamps
        timestamped_chunks = []
        screenshots = {}
        
        # Calculate progress increments for transcription
        if len(audio_chunks) > 0:
            # Reserve 60% of the progress for chunk processing (30% to 90%)
            progress_per_chunk = 70 / len(audio_chunks)
        else:
            progress_per_chunk = 0
        
        for i, (chunk, start_time) in enumerate(zip(audio_chunks, start_times)):
            current_progress = 25 + (i * progress_per_chunk)
            if progress_callback:
                progress_callback(job_id, f"Transcribing chunk {i+1}/{len(audio_chunks)}...", 
                                 current_progress)
            
            try:
                # Transcribe with local Whisper
                _, segments = transcribe_audio_chunk_with_whisper(chunk, model_size=whisper_model)
                
                # Process segments
                for segment in segments:
                    segment_start = segment.get('start', 0) + start_time
                    segment_text = segment.get('text', '').strip()
                    
                    if not segment_text:
                        continue
                    
                    # Format timestamp
                    timestamp = utils.format_timestamp(segment_start)
                    
                    # Only take periodic screenshots based on timestamp_interval
                    if int(segment_start) % timestamp_interval < 5:  # Within 5 seconds of interval
                        screenshot_path = os.path.join(screenshots_dir, f"screenshot_{int(segment_start):06d}.jpg")
                        if utils.extract_screenshot(video_path, screenshot_path, timestamp):
                            screenshots[timestamp] = screenshot_path
                    
                    # Add to timestamped chunks
                    timestamped_chunks.append((timestamp, segment_text))
                
                if progress_callback:
                    progress_callback(job_id, f"Transcribed chunk {i+1}/{len(audio_chunks)}", 
                                     current_progress + progress_per_chunk/2)
                
            except Exception as e:
                print(f"Error processing chunk {i+1}: {e}")
                continue  # Try to continue with next chunk
        
        if progress_callback:
            progress_callback(job_id, "Finished transcription", 90)
        
        # Create persistent copies of screenshots
        persistent_screenshots = {}
        output_dir = os.path.join(os.getcwd(), "output", job_id)
        os.makedirs(output_dir, exist_ok=True)
        
        for timestamp, screenshot_path in screenshots.items():
            new_path = os.path.join(output_dir, os.path.basename(screenshot_path))
            try:
                # Copy the screenshot to a persistent location
                shutil.copy2(screenshot_path, new_path)
                persistent_screenshots[timestamp] = new_path
            except Exception as e:
                print(f"Error copying screenshot {screenshot_path}: {e}")
        
        if progress_callback:
            progress_callback(job_id, "Saved screenshots", 95)
    
    return timestamped_chunks, persistent_screenshots