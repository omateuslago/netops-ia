"""PDF upload preview, available directly from the interactive API docs."""

from fastapi import APIRouter, HTTPException, Request, UploadFile

from netops_ai.application.chunking import PIPELINE_VERSION, chunk_document
from netops_ai.core.settings import Settings
from netops_ai.domain.documents import DocumentError
from netops_ai.infrastructure.pdf import read_pdf
from netops_ai.schemas.documents import ChunkPreview, DocumentPreview

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post(
    "/preview",
    response_model=DocumentPreview,
    summary="Inspecionar páginas e trechos de um PDF",
    description=(
        "Recebe um PDF com texto selecionável e retorna trechos com página e hash SHA-256. "
        "Esta prévia não grava documentos na base nem usa um modelo de IA. "
        "Limites padrão: 10 MiB, 100 páginas e 250.000 caracteres extraídos."
    ),
    responses={
        413: {"description": "Tamanho, páginas ou texto excedem os limites configurados."},
        415: {"description": "Extensão de arquivo não suportada."},
        422: {"description": "Arquivo ausente, inválido, protegido ou sem texto extraível."},
    },
)
def preview_document(request: Request, file: UploadFile) -> DocumentPreview:
    # A sync route runs the CPU/file work in FastAPI's thread pool.
    settings: Settings = request.app.state.settings
    try:
        content = file.file.read(settings.max_upload_bytes + 1)
        document = read_pdf(
            content,
            file.filename or "",
            max_bytes=settings.max_upload_bytes,
            max_pages=settings.max_pdf_pages,
            max_chars=settings.max_extracted_chars,
        )
        chunks = chunk_document(
            document, chunk_size=settings.chunk_size, chunk_overlap=settings.chunk_overlap
        )
    except DocumentError as exc:
        status_code = 422
        if exc.code == "unsupported_file":
            status_code = 415
        elif exc.code in {"file_too_large", "too_many_pages", "too_much_text"}:
            status_code = 413
        raise HTTPException(
            status_code=status_code, detail={"code": exc.code, "message": str(exc)}
        ) from exc
    finally:
        file.file.close()

    empty_pages = [page.number for page in document.pages if not page.text]
    warnings = []
    if empty_pages:
        warnings.append(
            "Algumas páginas não possuem texto extraível e não geraram trechos. "
            "Confira a lista empty_pages; OCR ainda não está disponível."
        )
    return DocumentPreview(
        document_id=document.document_id,
        filename=document.filename,
        page_count=len(document.pages),
        empty_pages=empty_pages,
        chunk_count=len(chunks),
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
        pipeline_version=PIPELINE_VERSION,
        warnings=warnings,
        chunks=[ChunkPreview.model_validate(chunk) for chunk in chunks],
    )
