"""
Extracts text from uploaded files (PDF, DOCX, TXT) and splits it into
overlapping chunks suitable for embedding.
"""
from pypdf import PdfReader
import docx


def extract_text(file_path: str) -> str:
    lower = file_path.lower()
    if lower.endswith('.pdf'):
        return _extract_pdf(file_path)
    elif lower.endswith('.docx'):
        return _extract_docx(file_path)
    elif lower.endswith('.txt'):
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read()
    else:
        raise ValueError(f"Unsupported file type: {file_path}")


def _extract_pdf(file_path: str) -> str:
    reader = PdfReader(file_path)
    pages = []
    for page in reader.pages:
        pages.append(page.extract_text() or '')
    return '\n\n'.join(pages)


def _extract_docx(file_path: str) -> str:
    doc = docx.Document(file_path)
    return '\n'.join(p.text for p in doc.paragraphs)


def chunk_text(text: str, chunk_size: int = 800, overlap: int = 120) -> list[str]:
    """
    Simple sliding-window chunker by character count.
    Good enough for learning; for production consider a
    sentence-aware splitter (e.g. LangChain's RecursiveCharacterTextSplitter).
    """
    text = text.strip()
    if not text:
        return []

    chunks = []
    start = 0
    length = len(text)

    while start < length:
        end = start + chunk_size
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start += chunk_size - overlap  # move forward with overlap

    return chunks
