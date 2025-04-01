import streamlit as st
import os
import tempfile
from pathlib import Path
import time
import datetime
import threading
import shutil
import logging
import json
from modules import utils, transcriber, pdf_generator
import ssl

ssl._create_default_https_context = ssl._create_unverified_context
os.environ['PYTHONHTTPSVERIFY'] = '0'

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Set page configuration
st.set_page_config(
    page_title="VideoToText Transcriber",
    page_icon="🎬",
    layout="wide"
)

# Create necessary directories
os.makedirs("output", exist_ok=True)
os.makedirs("jobs", exist_ok=True)
os.makedirs("temp_processing", exist_ok=True)

# Initialize session state
if 'current_job_id' not in st.session_state:
    st.session_state.current_job_id = None
if 'jobs' not in st.session_state:
    st.session_state.jobs = utils.list_jobs()
if 'show_job' not in st.session_state:
    st.session_state.show_job = None
if 'user_feedback' not in st.session_state:
    st.session_state.user_feedback = None

def update_job_progress(job_id, text, progress):
    """Update job progress in job status file."""
    job_status = utils.load_job_status(job_id) or {}
    job_status['status'] = text
    job_status['progress'] = progress
    job_status['updated_at'] = datetime.datetime.now().isoformat()
    utils.save_job_status(job_id, job_status)
    
    # Update jobs list in session state
    st.session_state.jobs = utils.list_jobs()

def process_video_thread(job_id, video_path, whisper_model, 
                         chunk_duration, timestamp_interval):
    """Process video in a separate thread."""
    try:
        # Update job status to "in progress"
        update_job_progress(job_id, "Starting processing...", 0)
        
        # Call the transcriber function with progress updates
        timestamped_chunks, screenshots = transcriber.process_video(
            job_id, video_path, whisper_model, 
            chunk_duration, timestamp_interval,
            progress_callback=update_job_progress
        )
        
        # Generate output file paths
        job_dir = os.path.join("output", job_id)
        os.makedirs(job_dir, exist_ok=True)
        
        txt_path = os.path.join(job_dir, "transcript.txt")
        pdf_path = os.path.join(job_dir, "transcript.pdf")
        
        # Save text transcript
        update_job_progress(job_id, "Saving text transcript...", 95)
        pdf_generator.save_transcript_to_text(timestamped_chunks, txt_path)
        
        # Create PDF with screenshots
        update_job_progress(job_id, "Creating PDF with screenshots...", 98)
        pdf_generator.create_pdf_with_screenshots(timestamped_chunks, screenshots, pdf_path)
        
        # Update job status to "completed"
        job_status = utils.load_job_status(job_id) or {}
        job_status['status'] = "Completed"
        job_status['progress'] = 100
        job_status['completed_at'] = datetime.datetime.now().isoformat()
        job_status['txt_path'] = txt_path
        job_status['pdf_path'] = pdf_path
        job_status['num_screenshots'] = len(screenshots)
        job_status['num_segments'] = len(timestamped_chunks)
        utils.save_job_status(job_id, job_status)
        
        # Update jobs list in session state
        st.session_state.jobs = utils.list_jobs()
        
    except Exception as e:
        logger.error(f"Error in processing thread: {str(e)}", exc_info=True)
        
        # Update job status to "failed"
        job_status = utils.load_job_status(job_id) or {}
        job_status['status'] = f"Failed: {str(e)}"
        job_status['error'] = str(e)
        utils.save_job_status(job_id, job_status)
        
        # Update jobs list in session state
        st.session_state.jobs = utils.list_jobs()

def create_new_job():
    """Create a new job and return the job ID."""
    job_id = utils.generate_job_id()
    
    # Create job status file
    job_status = {
        'job_id': job_id,
        'filename': video_file.name if video_file else "Unknown",
        'status': "Created",
        'progress': 0,
        'created_at': datetime.datetime.now().isoformat(),
        'settings': {
            'chunk_duration': chunk_duration,
            'timestamp_interval': timestamp_interval,
            'whisper_model': whisper_model
        }
    }
    utils.save_job_status(job_id, job_status)
    
    return job_id

def show_job_details(job_id):
    """Show job details in the main panel."""
    st.session_state.show_job = job_id

def refresh_jobs():
    """Refresh the jobs list."""
    st.session_state.jobs = utils.list_jobs()

def delete_job_handler(job_id):
    """Handle job deletion."""
    if utils.delete_job(job_id):
        # Remove from session state if this is the current job
        if st.session_state.show_job == job_id:
            st.session_state.show_job = None
        
        # Update job list
        st.session_state.jobs = utils.list_jobs()
        st.session_state.user_feedback = f"Job {job_id} deleted successfully."
        
        # Force a rerun to update the UI
        st.rerun()

def clear_all_jobs():
    """Clear all jobs."""
    jobs = utils.list_jobs()
    for job in jobs:
        utils.delete_job(job['job_id'])
    
    # Reset session state
    st.session_state.show_job = None
    st.session_state.jobs = []
    st.session_state.user_feedback = "All jobs cleared successfully."
    
    # Force a rerun to update the UI
    st.rerun()

# Create a sidebar for job management and display
with st.sidebar:
    st.header("Jobs")
    
    # Job management buttons
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Refresh Jobs"):
            refresh_jobs()
    
    with col2:
        if st.button("Clear All Jobs"):
            clear_all_jobs()
    
    # Display existing jobs
    if not st.session_state.jobs:
        st.info("No jobs available")
    else:
        for job in st.session_state.jobs:
            job_col1, job_col2, job_col3 = st.columns([3, 1, 1])
            with job_col1:
                job_name = f"{job['filename']}"
                if job['status'] == "Completed":
                    job_name = f"✅ {job_name}"
                elif job['status'].startswith("Failed"):
                    job_name = f"❌ {job_name}"
                else:
                    # Show progress if available
                    job_data = utils.load_job_status(job['job_id'])
                    if job_data and 'progress' in job_data:
                        progress = job_data.get('progress', 0)
                        job_name = f"🔄 {job_name} ({progress}%)"
                        # Add a mini progress bar
                        st.progress(progress / 100, f"Job {job['job_id']}")
                    else:
                        job_name = f"⏳ {job_name}"
                
                if st.button(job_name, key=f"job_{job['job_id']}", use_container_width=True):
                    show_job_details(job['job_id'])
            
            with job_col2:
                st.write(f"ID: {job['job_id'][:4]}")
            
            with job_col3:
                if st.button("🗑️", key=f"delete_{job['job_id']}"):
                    delete_job_handler(job['job_id'])
    
# Main panel
if st.session_state.show_job:
    # Show job details
    job_id = st.session_state.show_job
    job_data = utils.load_job_status(job_id)
    
    if job_data:
        st.header(f"Job: {job_data.get('filename', 'Unknown')}")
        
        # Create job info section
        col1, col2 = st.columns(2)
        with col1:
            st.write(f"**Status:** {job_data.get('status', 'Unknown')}")
            st.write(f"**Job ID:** {job_id}")
            
            # Show progress bar if job is in progress
            if job_data.get('status') != "Completed" and not job_data.get('status', '').startswith("Failed"):
                progress = job_data.get('progress', 0)
                st.progress(progress / 100, "Processing progress")
            
        with col2:
            st.write(f"**Created:** {job_data.get('created_at', 'Unknown')}")
            if job_data.get('completed_at'):
                st.write(f"**Completed:** {job_data.get('completed_at')}")
        
        # Display result files if completed
        if job_data.get('status') == "Completed":
            st.subheader("Results")
            
            col1, col2 = st.columns(2)
            
            # Text transcript
            txt_path = job_data.get('txt_path')
            if txt_path and os.path.exists(txt_path):
                with col1:
                    with open(txt_path, "rb") as file:
                        st.download_button(
                            label="Download Text Transcript",
                            data=file,
                            file_name=f"transcript_{job_id}.txt",
                            mime="text/plain"
                        )
                    
                    # Show a preview of the text
                    st.subheader("Text Preview")
                    try:
                        with open(txt_path, "r") as file:
                            text_content = file.read()
                            st.text_area("Transcript", text_content[:1000] + ("..." if len(text_content) > 1000 else ""), height=300)
                    except Exception as e:
                        st.error(f"Error reading transcript: {e}")
            
            # PDF with screenshots
            pdf_path = job_data.get('pdf_path')
            if pdf_path and os.path.exists(pdf_path):
                with col2:
                    with open(pdf_path, "rb") as file:
                        st.download_button(
                            label="Download PDF with Screenshots",
                            data=file,
                            file_name=f"transcript_{job_id}.pdf",
                            mime="application/pdf"
                        )
                    
                    # Show stats
                    st.subheader("Statistics")
                    st.write(f"- Segments: {job_data.get('num_segments', 'N/A')}")
                    st.write(f"- Screenshots: {job_data.get('num_screenshots', 'N/A')}")
                    
                    # Display a sample screenshot if available
                    output_dir = os.path.join("output", job_id)
                    if os.path.exists(output_dir):
                        screenshots = [f for f in os.listdir(output_dir) if f.startswith("screenshot_") and f.endswith(".jpg")]
                        
                        if screenshots:
                            st.subheader("Sample Screenshots")
                            sample_screenshot = os.path.join(output_dir, screenshots[0])
                            st.image(sample_screenshot, caption="Sample Screenshot")
        
        # Display error if job failed
        elif job_data.get('status', '').startswith("Failed"):
            st.error(f"Job failed: {job_data.get('error', 'Unknown error')}")
            
            # Option to retry
            if st.button("Retry Job"):
                # TODO: Implement retry logic
                st.write("Retry not implemented yet")
        
        # Display delete and back buttons
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Back to Job List"):
                st.session_state.show_job = None
                st.rerun()
        
        with col2:
            if st.button("Delete This Job"):
                delete_job_handler(job_id)
    else:
        st.error(f"Job {job_id} not found")
        if st.button("Back to Job List"):
            st.session_state.show_job = None
            st.rerun()
else:
    # Show new job creation form
    st.header("Video to Text Transcriber")
    st.write("Upload your video and get a timestamped transcript with screenshots")
    
    # File upload section
    st.header("Upload Files")
    
    video_file = st.file_uploader(
        "Upload video file",
        type=["mp4", "avi", "mov", "mkv"],
        help="Upload the video you want to transcribe"
    )
    
    # Configuration options
    st.header("Configuration")
    
    col1, col2 = st.columns(2)
    
    with col1:
        whisper_model = st.selectbox(
            "Whisper Model Size",
            ["tiny", "base", "small", "medium", "large"],
            index=1,  # Default to "base"
            help="Larger models are more accurate but slower. Base is a good balance."
        )
    
    with col2:
        chunk_duration = st.slider(
            "Audio Chunk Duration (seconds)",
            min_value=60,
            max_value=600,
            value=180,
            step=30,
            help="Smaller chunks may improve accuracy but increase processing time"
        )
    
    timestamp_interval = st.slider(
        "Screenshot Interval (seconds)",
        min_value=10,
        max_value=120,
        value=30,
        step=5,
        help="How often to take screenshots from the video"
    )
    
    # Submit button
    submit_button = st.button(
        "Start Transcription",
        disabled=(video_file is None),
        type="primary"
    )
    
    # Process submission
    if submit_button and video_file is not None:
        with st.spinner("Preparing job..."):
            try:
                # Create job directory
                job_id = create_new_job()
                
                # Create a folder for this job
                job_dir = os.path.join("temp_processing", job_id)
                os.makedirs(job_dir, exist_ok=True)
                
                # Save video file
                safe_filename = f"video_{video_file.name.replace(' ', '_')}"
                video_path = os.path.join(job_dir, safe_filename)
                
                with open(video_path, "wb") as f:
                    f.write(video_file.getbuffer())
                
                # Start processing in a thread
                thread = threading.Thread(
                    target=process_video_thread,
                    args=(job_id, video_path, whisper_model, chunk_duration, timestamp_interval)
                )
                thread.daemon = True
                thread.start()
                
                # Show success message and redirect to job view
                st.session_state.current_job_id = job_id
                st.session_state.show_job = job_id
                st.session_state.user_feedback = "Job started successfully. You can close this page and check back later."
                
                # Force a rerun to show the job page
                st.rerun()
                
            except Exception as e:
                logger.error(f"Error setting up job: {str(e)}", exc_info=True)
                st.error(f"Error: {str(e)}")

# Display user feedback if any
if st.session_state.user_feedback:
    st.success(st.session_state.user_feedback)
    # Clear feedback after displaying
    st.session_state.user_feedback = None