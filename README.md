# VideoToText

A Python tool to transcribe lecture videos to text, using contextual information from PDF slides.

## Requirements

- Python 3.7+
- ffmpeg (must be installed and available in PATH)
- Ollama running locally with the "llava" model (or another model that can process audio)

## Installation

```bash
pip install -r requirements.txt
```

## Usage

Basic usage:
```bash
python video_to_text.py <video_file> [pdf_file] [output_file]
```

Example:
```bash
python video_to_text.py "ERS Hypothalamus and Pituitary Gland Medicine 2A MMED9250 ONC-U .mp4" "Hypothalamas and Pituitary gland Prac.pdf"
```

The program will:
1. Extract audio from the video
2. Split the audio into manageable chunks
3. Use Ollama to transcribe each chunk, using the PDF for context
4. Save the transcription as text with each sentence on a new line

## Output

The output will be saved to a text file with the same name as the video file (unless specified otherwise).