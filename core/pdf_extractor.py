import zipfile
import os
import tempfile

try:
    import pymupdf as fitz
except ImportError:
    try:
        import fitz
    except ImportError:
        fitz = None

def extract_text_from_zip(zip_path):
    """
    Extracts all PDFs from a ZIP file and returns their concatenated text.
    """
    full_text = ""
    
    with tempfile.TemporaryDirectory() as tmpdir:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(tmpdir)
            
        # Walk through the extracted files
        for root, _, files in os.walk(tmpdir):
            for file in files:
                if file.lower().endswith('.pdf'):
                    pdf_path = os.path.join(root, file)
                    try:
                        doc = fitz.open(pdf_path)
                        for page in doc:
                            full_text += page.get_text()
                    except Exception as e:
                        print(f"Failed to read {pdf_path}: {e}")
                        
    return full_text

def extract_text_from_pdfs(file_paths):
    """
    Extracts text from a list of PDF or TXT file paths and returns their concatenated text.
    """
    full_text = ""
    for path in file_paths:
        try:
            if path.lower().endswith('.txt'):
                with open(path, 'r', encoding='utf-8') as f:
                    full_text += f.read() + "\n"
            else:
                if fitz is not None:
                    doc = fitz.open(path)
                    for page in doc:
                        full_text += page.get_text()
        except Exception as e:
            print(f"Failed to read {path}: {e}")
    return full_text

if __name__ == "__main__":
    # Test run
    # Needs a valid zip path to test
    pass
