"""A measurable, page-aware character chunking baseline."""

from collections.abc import Iterator
from hashlib import sha256

from netops_ai.domain.documents import DocumentChunk, ExtractedDocument

PIPELINE_VERSION = "pdf-text-v1"


def _split_text(text: str, size: int, overlap: int) -> Iterator[str]:
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        if end < len(text):
            # Prefer a nearby paragraph/line/word boundary while ensuring progress.
            boundary_start = start + max(size // 2, overlap + 1)
            for separator in ("\n\n", "\n", " "):
                boundary = text.rfind(separator, boundary_start, end)
                if boundary >= 0:
                    end = boundary + len(separator)
                    break
        chunk = text[start:end].strip()
        if chunk:
            yield chunk
        if end == len(text):
            break
        start = end - overlap


def chunk_document(
    document: ExtractedDocument, *, chunk_size: int = 900, chunk_overlap: int = 150
) -> list[DocumentChunk]:
    """Keep chunks on a single page and retain line breaks inside each chunk."""
    if chunk_size <= 0 or not 0 <= chunk_overlap < chunk_size:
        raise ValueError("Use chunk_size > 0 e 0 <= chunk_overlap < chunk_size.")

    chunks: list[DocumentChunk] = []
    for page in document.pages:
        for index, text in enumerate(_split_text(page.text, chunk_size, chunk_overlap)):
            identity = (
                f"{PIPELINE_VERSION}:{document.document_id}:{page.number}:{index}:"
                f"{chunk_size}:{chunk_overlap}:{text}"
            )
            chunks.append(
                DocumentChunk(
                    chunk_id=sha256(identity.encode("utf-8")).hexdigest(),
                    document_id=document.document_id,
                    filename=document.filename,
                    page=page.number,
                    index=index,
                    text=text,
                )
            )
    return chunks
