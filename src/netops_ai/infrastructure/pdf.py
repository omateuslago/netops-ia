"""Read text PDFs without flattening their page boundaries."""

from hashlib import sha256
from io import BytesIO
from pathlib import PurePosixPath

from pypdf import PdfReader
from pypdf.errors import PyPdfError

from netops_ai.domain.documents import DocumentError, DocumentPage, ExtractedDocument


def read_pdf(
    content: bytes,
    filename: str,
    *,
    max_bytes: int,
    max_pages: int,
    max_chars: int,
) -> ExtractedDocument:
    """Extract all readable pages or fail, without saving the upload to knowledge/."""
    if min(max_bytes, max_pages, max_chars) <= 0:
        raise ValueError("Os limites de extração devem ser positivos.")

    # The client name is only a display label and is never used as a storage path.
    name = PurePosixPath(filename.replace("\\", "/")).name
    if not name or PurePosixPath(name).suffix.lower() != ".pdf":
        raise DocumentError("unsupported_file", "Envie um arquivo com extensão .pdf.")
    if len(content) > max_bytes:
        raise DocumentError("file_too_large", "O PDF excede o limite de tamanho permitido.")
    if not content.startswith(b"%PDF-"):
        raise DocumentError("invalid_pdf", "O arquivo está vazio ou não possui cabeçalho de PDF.")

    pages: list[DocumentPage] = []
    total_chars = 0
    reader: PdfReader | None = None
    try:
        reader = PdfReader(BytesIO(content), strict=True)
        if reader.is_encrypted:
            raise DocumentError("encrypted_pdf", "PDFs protegidos não são aceitos nesta etapa.")
        if len(reader.pages) > max_pages:
            raise DocumentError("too_many_pages", "O PDF excede o limite de páginas permitido.")
        for number, page in enumerate(reader.pages, start=1):
            text = (page.extract_text() or "").replace("\r\n", "\n").replace("\r", "\n").strip()
            total_chars += len(text)
            if total_chars > max_chars:
                raise DocumentError("too_much_text", "O texto do PDF excede o limite permitido.")
            pages.append(DocumentPage(number=number, text=text))
    except DocumentError:
        raise
    except (PyPdfError, ValueError, TypeError, KeyError, IndexError, RecursionError) as exc:
        # Never return raw parser errors, filesystem details or document content.
        raise DocumentError(
            "invalid_pdf", "Não foi possível ler este PDF. Verifique o arquivo."
        ) from exc
    finally:
        if reader is not None:
            reader.close()

    if not any(page.text for page in pages):
        raise DocumentError(
            "no_extractable_text",
            "O PDF não possui texto extraível. Arquivos digitalizados podem precisar de OCR.",
        )

    return ExtractedDocument(
        document_id=sha256(content).hexdigest(), filename=name, pages=tuple(pages)
    )
