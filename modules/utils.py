import datetime
import os
import json
import subprocess
import tempfile
import shutil
from pathlib import Path
import uuid

def format_timestamp(seconds):
    """Convert seconds to HH:MM:SS format."""
    return str(datetime.timedelta(seconds=int(seconds)))

def extract_audio_from_video(video_path, audio_path):
    """Extract audio from video file using ffmpeg."""
    print(f"Extracting audio from {video_path}...")
    
    # Verify the video file exists
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Video file not found: {video_path}")
    
    # Create directory if it doesn't exist
    os.makedirs(os.path.dirname(audio_path), exist_ok=True)
    
    # Debug info
    print(f"Video path: {video_path}")
    print(f"Audio path: {audio_path}")
    
    # Use subprocess with shell=False for better security
    cmd = [
        'ffmpeg',
        '-i', video_path,
        '-q:a', '0',
        '-map', 'a',
        '-y',  # Overwrite output file if it exists
        audio_path
    ]
    
    try:
        process = subprocess.run(cmd, check=True, text=True, capture_output=True)
        print("Audio extraction successful")
    except subprocess.CalledProcessError as e:
        print(f"Error in ffmpeg: {e.stderr}")
        raise

def convert_audio_to_wav(mp3_path, wav_path):
    """Convert audio to WAV format for better compatibility."""
    print(f"Converting audio to WAV format...")
    
    # Verify the mp3 file exists
    if not os.path.exists(mp3_path):
        raise FileNotFoundError(f"Audio file not found: {mp3_path}")
    
    cmd = [
        'ffmpeg',
        '-i', mp3_path,
        '-acodec', 'pcm_s16le',
        '-ar', '16000',
        '-ac', '1',
        '-y',
        wav_path
    ]
    
    try:
        process = subprocess.run(cmd, check=True, text=True, capture_output=True)
        print("Audio conversion successful")
    except subprocess.CalledProcessError as e:
        print(f"Error in ffmpeg: {e.stderr}")
        raise

def extract_screenshot(video_path, output_path, timestamp):
    """Extract a screenshot from the video at the given timestamp."""
    # Verify the video file exists
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Video file not found: {video_path}")
    
    cmd = [
        'ffmpeg',
        '-ss', timestamp,
        '-i', video_path,
        '-frames:v', '1',
        '-q:v', '2',
        '-y',
        output_path
    ]
    
    try:
        process = subprocess.run(cmd, check=True, text=True, capture_output=True)
    except subprocess.CalledProcessError as e:
        print(f"Error extracting screenshot: {e.stderr}")
        return False
    
    # Verify image was created
    if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
        print(f"Warning: Failed to extract screenshot at {timestamp}")
        return False
    
    return True

def split_audio_into_chunks(audio_path, chunk_dir, chunk_duration=300):
    """Split audio into smaller chunks for processing."""
    print(f"Splitting audio into {chunk_duration}-second chunks...")
    
    # Verify the audio file exists
    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"Audio file not found: {audio_path}")
    
    os.makedirs(chunk_dir, exist_ok=True)
    
    # Get total duration of the audio file
    cmd = [
        'ffprobe', 
        '-v', 'error', 
        '-show_entries', 'format=duration', 
        '-of', 'json', 
        audio_path
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        duration = float(json.loads(result.stdout)['format']['duration'])
        print(f"Audio duration: {duration} seconds")
    except subprocess.CalledProcessError as e:
        print(f"Error getting audio duration: {e.stderr}")
        raise
    
    # Calculate number of chunks
    num_chunks = int(duration / chunk_duration) + 1
    chunk_files = []
    timestamps = []
    
    print(f"Splitting into {num_chunks} chunks...")
    
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
        
        try:
            subprocess.run(cmd, check=True, text=True, capture_output=True)
            print(f"Created chunk {i+1}/{num_chunks}")
        except subprocess.CalledProcessError as e:
            print(f"Error splitting audio chunk {i}: {e.stderr}")
            raise
            
        chunk_files.append(chunk_path)
        timestamps.append(start_time)
    
    return chunk_files, timestamps, num_chunks

def generate_job_id():
    """Generate a unique job ID."""
    return str(uuid.uuid4())[:8]

def get_jobs_dir():
    """Get jobs directory path."""
    jobs_dir = os.path.join(os.getcwd(), "jobs")
    os.makedirs(jobs_dir, exist_ok=True)
    return jobs_dir

def save_job_status(job_id, status_data):
    """Save job status to JSON file."""
    jobs_dir = get_jobs_dir()
    job_file = os.path.join(jobs_dir, f"{job_id}.json")
    
    try:
        with open(job_file, 'w') as f:
            json.dump(status_data, f, indent=2)
    except Exception as e:
        print(f"Error saving job status: {e}")

def load_job_status(job_id):
    """Load job status from JSON file."""
    jobs_dir = get_jobs_dir()
    job_file = os.path.join(jobs_dir, f"{job_id}.json")
    
    if os.path.exists(job_file):
        try:
            with open(job_file, 'r') as f:
                data = json.load(f)
                return data
        except json.JSONDecodeError:
            print(f"Error: Job file {job_file} contains invalid JSON")
            return {"status": "Error", "error": "Invalid job file format"}
        except Exception as e:
            print(f"Error loading job status: {e}")
            return {"status": "Error", "error": str(e)}
    return None

def list_jobs():
    """List all available jobs."""
    jobs_dir = get_jobs_dir()
    jobs = []
    
    if not os.path.exists(jobs_dir):
        return jobs
    
    for file in os.listdir(jobs_dir):
        if file.endswith('.json'):
            job_id = file.replace('.json', '')
            job_data = load_job_status(job_id)
            if job_data:
                jobs.append({
                    'job_id': job_id,
                    'filename': job_data.get('filename', 'Unknown'),
                    'status': job_data.get('status', 'Unknown'),
                    'created_at': job_data.get('created_at', 'Unknown'),
                    'completed_at': job_data.get('completed_at', '')
                })
    
    # Sort by creation time, newest first
    return sorted(jobs, key=lambda x: x.get('created_at', ''), reverse=True)

def delete_job(job_id):
    """Delete a job and its associated files."""
    # Delete job status file
    jobs_dir = get_jobs_dir()
    job_file = os.path.join(jobs_dir, f"{job_id}.json")
    
    if os.path.exists(job_file):
        os.remove(job_file)
    
    # Delete job output directory
    output_dir = os.path.join(os.getcwd(), "output", job_id)
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)
    
    # Delete job temp directory
    temp_dir = os.path.join(os.getcwd(), "temp_processing", job_id)
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)
    
    return True