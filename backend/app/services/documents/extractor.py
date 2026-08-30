import os
import io
from typing import Optional


def extract_text_from_file(file_bytes: bytes, mime_type: str, filename: str) -> str:
    """
    Extract plain text from a document based on its MIME type.
    Supports PDF, TXT, DOCX, and Markdown formats.
    """
    if mime_type == "application/pdf" or filename.lower().endswith(".pdf"):
        return _extract_pdf(file_bytes)
    elif mime_type in ("text/plain", "text/markdown") or filename.lower().endswith((".txt", ".md")):
        return _extract_text(file_bytes)
    elif mime_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document" or filename.lower().endswith(".docx"):
        return _extract_docx(file_bytes)
    else:
        raise ValueError(f"Unsupported file type: {mime_type} ({filename})")


def _extract_pdf(file_bytes: bytes) -> str:
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(file_bytes))
    pages = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            pages.append(text.strip())
    return "\n\n".join(pages)


def _extract_text(file_bytes: bytes) -> str:
    return file_bytes.decode("utf-8", errors="replace")


def _extract_docx(file_bytes: bytes) -> str:
    from docx import Document
    doc = Document(io.BytesIO(file_bytes))
    paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    return "\n\n".join(paragraphs)
