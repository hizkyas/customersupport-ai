import re
from typing import List, Dict, Any

CHUNK_SIZE = 1000       # characters per chunk
CHUNK_OVERLAP = 150     # character overlap between adjacent chunks


def chunk_text(text: str, document_name: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[Dict[str, Any]]:
    """
    Split text into overlapping chunks, preserving paragraph boundaries where possible.
    Each chunk retains metadata about the source document.
    """
    # Normalize whitespace
    text = re.sub(r"\n{3,}", "\n\n", text.strip())

    # Try to split on paragraph boundaries first
    paragraphs = text.split("\n\n")

    chunks: List[Dict[str, Any]] = []
    current_chunk = ""
    chunk_index = 0

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        # If adding this paragraph stays within size, add it
        if len(current_chunk) + len(para) + 2 <= chunk_size:
            current_chunk = (current_chunk + "\n\n" + para).strip()
        else:
            # Save the current chunk if not empty
            if current_chunk:
                chunks.append({
                    "content": current_chunk,
                    "chunk_index": chunk_index,
                    "metadata": {
                        "document_name": document_name,
                        "chunk_index": chunk_index,
                    }
                })
                chunk_index += 1
                # Carry over the last `overlap` characters for context continuity
                overlap_text = current_chunk[-overlap:] if len(current_chunk) > overlap else current_chunk
                current_chunk = overlap_text.strip() + "\n\n" + para
            else:
                # Single paragraph exceeds chunk_size — split it by words
                words = para.split()
                sub_chunk = ""
                for word in words:
                    if len(sub_chunk) + len(word) + 1 <= chunk_size:
                        sub_chunk = (sub_chunk + " " + word).strip()
                    else:
                        if sub_chunk:
                            chunks.append({
                                "content": sub_chunk,
                                "chunk_index": chunk_index,
                                "metadata": {
                                    "document_name": document_name,
                                    "chunk_index": chunk_index,
                                }
                            })
                            chunk_index += 1
                            overlap_text = sub_chunk[-overlap:] if len(sub_chunk) > overlap else sub_chunk
                            sub_chunk = overlap_text.strip() + " " + word
                        else:
                            sub_chunk = word
                if sub_chunk:
                    current_chunk = sub_chunk
                else:
                    current_chunk = ""

    # Flush remaining content
    if current_chunk.strip():
        chunks.append({
            "content": current_chunk.strip(),
            "chunk_index": chunk_index,
            "metadata": {
                "document_name": document_name,
                "chunk_index": chunk_index,
            }
        })

    return chunks
