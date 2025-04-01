from fpdf import FPDF
from PIL import Image
import os

def create_pdf_with_screenshots(transcripts, screenshot_paths, output_pdf_path):
    """Create a PDF with screenshots and corresponding transcripts."""
    print(f"Creating PDF with screenshots and transcripts...")
    
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    
    # Set title
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, "Video Transcript with Visual References", ln=True, align='C')
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
        
        # Handle encoding issues
        try:
            # Replace problematic characters
            clean_transcript = clean_transcript.encode('latin-1', 'replace').decode('latin-1')
            
            pdf.multi_cell(0, 5, clean_transcript)
        except Exception as e:
            print(f"Error adding text to PDF: {e}")
            # Fall back to ASCII
            pdf.multi_cell(0, 5, clean_transcript.encode('ascii', 'replace').decode('ascii'))
        
        # Add spacing between entries
        pdf.ln(10)
        
        # Add a new page every 2 entries or if the current page is getting full
        if (i + 1) % 2 == 0 or pdf.get_y() > 250:
            pdf.add_page()
    
    # Save the PDF
    try:
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(output_pdf_path), exist_ok=True)
        
        pdf.output(output_pdf_path)
        print(f"PDF saved to {output_pdf_path}")
        return True
    except Exception as e:
        print(f"Error saving PDF: {e}")
        return False

def save_transcript_to_text(timestamped_chunks, output_path):
    """Save timestamped transcript to a text file."""
    try:
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        with open(output_path, 'w') as f:
            for timestamp, text in timestamped_chunks:
                entry = f"[{timestamp}] {text}\n\n"
                f.write(entry)
        print(f"Transcript saved to {output_path}")
        return True
    except Exception as e:
        print(f"Error saving transcript to text: {e}")
        return False