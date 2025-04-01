# VideoToText Transcriber

A Streamlit-based application that transcribes videos, generates timestamped transcripts, and creates PDFs with screenshots.

## Features

- **Video Processing**: Upload and process various video formats (MP4, AVI, MOV, MKV)
- **Speech-to-Text**: Transcribe audio using OpenAI's Whisper models
- **Automatic Screenshots**: Capture screenshots at configurable intervals
- **Multiple Output Formats**: 
  - Text file with timestamped transcripts
  - PDF with screenshots and corresponding text
- **Job Management System**:
  - View all transcription jobs
  - Track progress in real-time
  - Manage and delete completed jobs
- **Configurable Settings**:
  - Choice of Whisper model size (tiny, base, small, medium, large)
  - Customizable audio chunk duration
  - Adjustable screenshot intervals

## Requirements

- Python 3.8+
- FFmpeg (for video and audio processing)
- GPU recommended for larger Whisper models (but CPU mode supported)

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/videototext-transcriber.git
   cd videototext-transcriber
   ```

2. Create and activate a virtual environment (optional but recommended):
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install required Python packages:
   ```bash
   pip install -r requirements.txt
   ```

4. Install FFmpeg:
   - **Linux (Ubuntu/Debian)**:
     ```bash
     sudo apt update
     sudo apt install ffmpeg
     ```
   - **macOS** (using Homebrew):
     ```bash
     brew install ffmpeg
     ```
   - **Windows**: Download from [ffmpeg.org](https://ffmpeg.org/download.html) and add to PATH

   > **Note**: FFmpeg is **required** for this application to work. Verify installation with `ffmpeg -version`

## Configuration

### Increase Upload Size Limit

To process larger video files (>200MB), create a `.streamlit/config.toml` file in your project directory:

```toml
[server]
maxUploadSize = 2000
```

This increases the maximum upload size to 2000MB (about 2GB).

### SSL Certificate Issues

If you're in a corporate environment and see SSL certificate errors when downloading Whisper models, add this code at the top of `modules/transcriber.py`:

```python
# Add near the top of the file, before any other imports
import os
import ssl
ssl._create_default_https_context = ssl._create_unverified_context
os.environ['PYTHONHTTPSVERIFY'] = '0'
```

Alternatively, configure your corporate proxy settings:

```python
import os
os.environ['HTTP_PROXY'] = 'http://your-proxy-server:port'
os.environ['HTTPS_PROXY'] = 'http://your-proxy-server:port'
```

## Usage

1. Start the Streamlit app:
   ```bash
   streamlit run app.py
   ```

2. Access the web interface in your browser (typically http://localhost:8501)

3. Upload a video file and configure transcription settings:
   - Select Whisper model size
   - Set audio chunk duration
   - Choose screenshot interval

4. Click "Start Transcription" and monitor progress

5. When complete, download and view:
   - Text transcript with timestamps
   - PDF with screenshots and text

## Application Structure

```
.
├── app.py                     # Main Streamlit application
├── modules/
│   ├── __init__.py            # Package initialization
│   ├── transcriber.py         # Video processing and transcription
│   ├── pdf_generator.py       # PDF creation with screenshots
│   └── utils.py               # Utility functions
├── output/                    # Generated output files (created on first run)
├── jobs/                      # Job status files (created on first run)
└── temp_processing/           # Temporary processing files (created on first run)
```

## Configuration Options

### Whisper Model Size
- **tiny**: Fastest, least accurate
- **base**: Good balance of speed and accuracy
- **small**: Better accuracy, slower processing
- **medium**: High accuracy, slower
- **large**: Best accuracy, slowest processing

### Audio Chunk Duration
- Controls how the audio is split for processing
- Smaller chunks may improve accuracy but increase processing time
- Default: 180 seconds (3 minutes)
- Range: 60-600 seconds

### Screenshot Interval
- Controls how frequently screenshots are taken from the video
- Default: 30 seconds
- Range: 10-120 seconds

## Troubleshooting

### Common Issues

1. **"No such file or directory: 'ffmpeg'"**: FFmpeg is not installed or not in your PATH
   - Solution: Install FFmpeg and ensure it's in your system PATH

2. **"module 'whisper' has no attribute 'load_model'"**: You have the wrong Whisper package
   - Solution: Uninstall any existing whisper package and install OpenAI's package with `pip install openai-whisper`

3. **"File must be 200.0MB or smaller"**: Streamlit file size limit
   - Solution: Create the `.streamlit/config.toml` file as described in the Configuration section

4. **SSL Certificate errors**: Corporate firewall/proxy issues
   - Solution: Use the SSL workaround code described in the Configuration section

5. **Invalid JSON errors**: Corrupted job files
   - Solution: Clear the jobs directory with `rm -f jobs/*.json`

## License

MIT License

## Contributing

Contributions welcome! Please feel free to submit a Pull Request.