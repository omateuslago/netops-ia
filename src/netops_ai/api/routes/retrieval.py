"""Lazy initialization keeps health and PDF previews independent of the model."""

import logging
from contextlib import contextmanager
from dataclasses import asdict

from fastapi import APIRouter, HTTPException, Request, UploadFile

from netops_ai.application.answers import Selection, compose_answer, select_evidence
from netops_ai.application.knowledge import KnowledgeService
from netops_ai.domain.documents import DocumentError
from netops_ai.domain.retrieval import RetrievalError
from netops_ai.infrastructure.pdf import read_pdf
from netops_ai.schemas.retrieval import (
    DocumentList,
    DocumentRecord,
    IndexResult,
    SearchMatch,
    SearchRequest,
    SearchResponse,
)

router = APIRouter(tags=["knowledge"])
logger = logging.getLogger(__name__)


@contextmanager
def retrieval_errors():
    try:
        yield
    except RetrievalError as exc:
        raise HTTPException(
            exc.status_code, detail={"code": exc.code, "message": str(exc)}
        ) from exc
    except DocumentError as exc:
        status = 415 if exc.code == "unsupported_file" else 422
        if exc.code in {"file_too_large", "too_many_pages", "too_much_text"}:
            status = 413
        raise HTTPException(status, detail={"code": exc.code, "message": str(exc)}) from exc
    except Exception as exc:
        # Do not include document contents, filenames, paths or queries in logs.
        logger.error("Local knowledge operation failed (%s)", type(exc).__name__)
        raise HTTPException(
            503,
            detail={
                "code": "knowledge_unavailable",
                "message": "Base local indisponível. Verifique espaço em disco, permissões e se "
                "há outro processo usando o mesmo diretório. Execute apenas um servidor.",
            },
        ) from exc


def get_knowledge(request: Request) -> KnowledgeService:
    state = request.app.state
    with state.knowledge_lock:
        if state.knowledge is None:
            state.knowledge = KnowledgeService(state.settings, state.embeddings)
        return state.knowledge


@router.post("/documents", response_model=IndexResult, summary="Salvar e indexar um PDF")
def index_document(request: Request, file: UploadFile) -> IndexResult:
    settings = request.app.state.settings
    try:
        with retrieval_errors():
            content = file.file.read(settings.max_upload_bytes + 1)
            document = read_pdf(
                content,
                file.filename or "",
                max_bytes=settings.max_upload_bytes,
                max_pages=settings.max_pdf_pages,
                max_chars=settings.max_extracted_chars,
            )
            service = get_knowledge(request)
            record, duplicate = service.index(document, content)
            return IndexResult(
                **asdict(record),
                duplicate=duplicate,
                embedding_model=service.embeddings.identity,
            )
    finally:
        file.file.close()


@router.get(
    "/documents", response_model=DocumentList, summary="Listar documentos e estado da indexação"
)
def list_documents(request: Request) -> DocumentList:
    with retrieval_errors():
        return DocumentList(
            documents=[
                DocumentRecord.model_validate(doc)
                for doc in get_knowledge(request).list_documents()
            ]
        )


@router.post(
    "/search", response_model=SearchResponse, summary="Buscar trechos e fontes, sem gerar resposta"
)
def search(request: Request, body: SearchRequest) -> SearchResponse:
    with retrieval_errors():
        hits = get_knowledge(request).search(body.query, body.top_k, body.document_id)
        return SearchResponse(
            query=body.query,
            matches=[SearchMatch(**asdict(hit.chunk), score=hit.score) for hit in hits],
        )


@router.post("/answer", summary="Selecionar evidência literal com avaliador local experimental")
def answer(request: Request, body: SearchRequest) -> dict:
    with retrieval_errors():
        hits = get_knowledge(request).search(body.query, body.top_k, body.document_id)
        selection = (
            select_evidence(body.query, hits, request.app.state.settings.ollama_model)
            if hits
            else Selection(evidence=[])
        )
        return compose_answer(body.query, hits, selection)
